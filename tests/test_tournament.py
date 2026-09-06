from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

import chess

from chess_bot.cli import format_tournament_progress
from chess_bot.config import load_engine_config
from chess_bot.ratings import EloRatings
from chess_bot.tournament import (
    CompletedGame,
    ResultBreakdown,
    TournamentResult,
    append_tournament_report,
    run_tournament,
)


class TournamentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_engine_config()

    def test_profiles_alternate_colours_and_stats_are_split_by_colour(self) -> None:
        games: Iterator[CompletedGame] = iter(
            [
                CompletedGame(chess.WHITE, "checkmate", 31),
                CompletedGame(chess.BLACK, "checkmate", 42),
                CompletedGame(None, "threefold repetition", 50),
            ]
        )
        progress_counts: list[int] = []

        result = run_tournament(
            self.config,
            "standard-material",
            "equal-minors",
            3,
            game_runner=lambda _white, _black: next(games),
            progress_callback=lambda progress: progress_counts.append(
                progress.games_completed
            ),
        )

        standard, equal_minors = result.profile_stats
        self.assertEqual(progress_counts, [0, 1, 2, 3])
        self.assertEqual(
            (standard.overall.wins, standard.overall.draws, standard.overall.losses),
            (2, 1, 0),
        )
        self.assertEqual(
            (standard.as_white.games, standard.as_white.wins, standard.as_white.draws),
            (2, 1, 1),
        )
        self.assertEqual(
            (standard.as_black.games, standard.as_black.wins),
            (1, 1),
        )
        self.assertEqual(
            (
                equal_minors.as_white.games,
                equal_minors.as_black.games,
                equal_minors.overall.losses,
                equal_minors.overall.draws,
            ),
            (1, 2, 2, 1),
        )
        self.assertEqual((result.white_wins, result.black_wins, result.draws), (1, 1, 1))
        self.assertAlmostEqual(result.average_plies, 41.0)

    def test_final_progress_contains_percentage_and_colour_breakdowns(self) -> None:
        result = run_tournament(
            self.config,
            "standard-material",
            "equal-minors",
            2,
            game_runner=lambda _white, _black: CompletedGame(
                chess.WHITE, "checkmate", 20
            ),
        )

        output = format_tournament_progress(result, 10, final=True)

        self.assertIn("Progress  [██████████]  2/2 (100.0%)", output)
        self.assertIn("Player 1 · Standard Material  [standard-material]", output)
        self.assertIn("one ply · P=100 N=320 B=330 R=500 Q=900", output)
        self.assertIn("♙ White", output)
        self.assertIn("♟ Black", output)
        self.assertIn("White wins  2 (100.0%)", output)
        self.assertIn("Endings  checkmate: 2", output)
        self.assertIn("Tournament seed", output)
        self.assertIn("Performance Elo", output)

    def test_seed_replays_random_choices_and_pairs_colour_swaps(self) -> None:
        def observed_moves(seed: int) -> list[tuple[chess.Move, chess.Move]]:
            moves: list[tuple[chess.Move, chess.Move]] = []

            def record_first_moves(white, black) -> CompletedGame:
                board = chess.Board()
                moves.append((white.choose_move(board), black.choose_move(board)))
                return CompletedGame(None, "stalemate", 1)

            run_tournament(
                self.config,
                "random",
                "random",
                4,
                seed=seed,
                game_runner=record_first_moves,
            )
            return moves

        first_run = observed_moves(8675309)
        replay = observed_moves(8675309)

        self.assertEqual(first_run, replay)
        self.assertEqual(first_run[1], tuple(reversed(first_run[0])))
        self.assertEqual(first_run[3], tuple(reversed(first_run[2])))

    def test_elapsed_time_uses_supplied_clock(self) -> None:
        times = iter([100.0, 102.0, 105.0])
        result = run_tournament(
            self.config,
            "standard-material",
            "equal-minors",
            2,
            seed=12345,
            clock=lambda: next(times),
            game_runner=lambda _white, _black: CompletedGame(
                None, "stalemate", 1
            ),
        )

        self.assertEqual(result.elapsed_seconds, 5.0)
        self.assertAlmostEqual(result.games_per_second, 0.4)
        output = format_tournament_progress(result, 10, final=True)
        self.assertIn("Duration  00:00:05.0", output)
        self.assertIn("Tournament seed  12345", output)

    def test_performance_elo_and_score_confidence_interval(self) -> None:
        result = TournamentResult(
            1000,
            self.config.get_profile("two-ply-material"),
            self.config.get_profile("equal-minors"),
            seed=42,
        )
        result.games_completed = 1000
        result.profile_stats[0].overall = ResultBreakdown(
            games=1000,
            wins=432,
            draws=180,
            losses=388,
        )

        low, high = result.profile_stats[0].overall.score_confidence_interval
        self.assertAlmostEqual(result.performance_elo_difference, 15.297, places=3)
        self.assertAlmostEqual(low, 0.4940, places=4)
        self.assertAlmostEqual(high, 0.5500, places=4)
        output = format_tournament_progress(result, 10, final=True)
        self.assertIn("Player 1 52.2% (approx. 95% CI 49.4–55.0%)", output)
        self.assertIn("Performance Elo  Player 1 +15.3 vs Player 2", output)

    def test_negative_tournament_seed_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "seed must be non-negative"):
            run_tournament(
                self.config,
                "random",
                "random",
                1,
                seed=-1,
            )

    def test_text_reports_are_appended_instead_of_replaced(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        results_path = Path(temporary_directory.name) / "results.txt"
        completed_at = datetime(2026, 9, 5, 12, 30, tzinfo=timezone.utc)

        append_tournament_report(
            results_path,
            "FIRST TOURNAMENT",
            completed_at=completed_at,
        )
        append_tournament_report(
            results_path,
            "SECOND TOURNAMENT",
            completed_at=completed_at,
        )

        saved = results_path.read_text(encoding="utf-8")
        self.assertIn("Completed: 2026-09-05T12:30:00+00:00", saved)
        self.assertIn("FIRST TOURNAMENT", saved)
        self.assertIn("SECOND TOURNAMENT", saved)
        self.assertEqual(saved.count("=" * 72), 2)

    def test_same_profile_can_compete_as_two_separate_players(self) -> None:
        result = run_tournament(
            self.config,
            "standard-material",
            "standard-material",
            2,
            game_runner=lambda _white, _black: CompletedGame(
                chess.WHITE, "checkmate", 20
            ),
        )

        player_one, player_two = result.profile_stats
        self.assertEqual(player_one.profile, player_two.profile)
        self.assertEqual(
            (player_one.overall.wins, player_one.overall.losses),
            (1, 1),
        )
        self.assertEqual(
            (player_two.overall.wins, player_two.overall.losses),
            (1, 1),
        )
        self.assertEqual(player_one.as_white.wins, 1)
        self.assertEqual(player_two.as_white.wins, 1)

    def test_different_profiles_update_elo_after_each_game(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        ratings = EloRatings(
            Path(temporary_directory.name) / "ratings.json",
            initial_rating=1500,
            k_factor=32,
        )
        games = iter(
            [
                CompletedGame(chess.WHITE, "checkmate", 20),
                CompletedGame(chess.BLACK, "checkmate", 20),
            ]
        )

        result = run_tournament(
            self.config,
            "standard-material",
            "equal-minors",
            2,
            game_runner=lambda _white, _black: next(games),
            ratings=ratings,
        )

        self.assertIsNotNone(result.elo)
        self.assertEqual(result.elo.rated_games, 2)
        self.assertAlmostEqual(result.elo.first_current, 1530.5305, places=3)
        self.assertAlmostEqual(result.elo.second_current, 1469.4695, places=3)
        self.assertEqual(ratings.games_for("standard-material"), 2)
        report = format_tournament_progress(result, 10, final=True)
        self.assertIn("Elo  Player 1 1500.0 → 1530.5 (+30.5)", report)

    def test_same_profile_tournament_is_marked_unrated(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        ratings = EloRatings(Path(temporary_directory.name) / "ratings.json")

        result = run_tournament(
            self.config,
            "standard-material",
            "standard-material",
            1,
            game_runner=lambda _white, _black: CompletedGame(
                chess.WHITE, "checkmate", 20
            ),
            ratings=ratings,
        )

        self.assertTrue(result.elo.self_play)
        self.assertEqual(result.elo.rated_games, 0)
        self.assertEqual(ratings.games_for("standard-material"), 0)


if __name__ == "__main__":
    unittest.main()
