from collections.abc import Iterator
import unittest

import chess

from chess_bot.cli import format_tournament_progress
from chess_bot.config import load_engine_config
from chess_bot.tournament import CompletedGame, run_tournament


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

        standard = result.profile_stats["standard-material"]
        equal_minors = result.profile_stats["equal-minors"]
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

        self.assertIn("Game 2 of 2  [██████████] 100.0%", output)
        self.assertIn("Standard Material: 2 games", output)
        self.assertIn("as White: 1 game", output)
        self.assertIn("as Black: 1 game", output)
        self.assertIn("White wins: 2 (100.0%)", output)
        self.assertIn("Endings: checkmate: 2", output)

    def test_same_profile_cannot_play_both_sides(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be different"):
            run_tournament(
                self.config,
                "standard-material",
                "standard-material",
                2,
            )


if __name__ == "__main__":
    unittest.main()
