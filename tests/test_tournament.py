from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

import chess

from chess_bot.cli import format_tournament_progress
from chess_bot.config import load_engine_config
from chess_bot.tournament import (
    CompletedGame,
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
        self.assertIn("♙ White", output)
        self.assertIn("♟ Black", output)
        self.assertIn("White wins  2 (100.0%)", output)
        self.assertIn("Endings  checkmate: 2", output)

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


if __name__ == "__main__":
    unittest.main()
