from pathlib import Path
import tempfile
import unittest

from chess_bot.ratings import EloRatings, RatingError


class EloRatingsTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.path = Path(temporary_directory.name) / "ratings.json"
        self.ratings = EloRatings(self.path, initial_rating=1500, k_factor=32)

    def test_equal_ratings_move_sixteen_points_after_a_decisive_game(self) -> None:
        update = self.ratings.record_game("winner", "loser", 1.0)

        self.assertIsNotNone(update)
        self.assertAlmostEqual(self.ratings.rating_for("winner"), 1516.0)
        self.assertAlmostEqual(self.ratings.rating_for("loser"), 1484.0)
        winner = self.ratings.record_for("winner")
        loser = self.ratings.record_for("loser")
        self.assertEqual((winner.games, winner.wins), (1, 1))
        self.assertEqual((loser.games, loser.losses), (1, 1))

    def test_updates_are_applied_sequentially_and_conserve_total_rating(self) -> None:
        self.ratings.record_game("first", "second", 1.0)
        self.ratings.record_game("first", "second", 1.0)

        first = self.ratings.rating_for("first")
        second = self.ratings.rating_for("second")
        self.assertAlmostEqual(first, 1530.5305, places=3)
        self.assertAlmostEqual(first + second, 3000.0)

    def test_draw_records_half_a_point(self) -> None:
        self.ratings.record_game("first", "second", 0.5)

        self.assertEqual(self.ratings.rating_for("first"), 1500.0)
        self.assertEqual(self.ratings.rating_for("second"), 1500.0)
        self.assertEqual(self.ratings.record_for("first").draws, 1)
        self.assertEqual(self.ratings.record_for("second").draws, 1)

    def test_same_profile_self_play_is_not_rated(self) -> None:
        update = self.ratings.record_game("same", "same", 1.0)

        self.assertIsNone(update)
        self.assertEqual(self.ratings.rating_for("same"), 1500.0)
        self.assertEqual(self.ratings.games_for("same"), 0)

    def test_ratings_and_lifetime_results_round_trip_through_json(self) -> None:
        self.ratings.record_game("first", "second", 1.0)
        self.ratings.save()

        reloaded = EloRatings.load(
            self.path,
            initial_rating=1500,
            k_factor=32,
        )

        self.assertAlmostEqual(reloaded.rating_for("first"), 1516.0)
        self.assertEqual(reloaded.record_for("first").wins, 1)
        self.assertEqual(reloaded.record_for("second").losses, 1)

    def test_invalid_ratings_file_has_a_clear_error(self) -> None:
        self.path.write_text("not json", encoding="utf-8")

        with self.assertRaisesRegex(RatingError, "Could not read Elo ratings"):
            EloRatings.load(self.path)


if __name__ == "__main__":
    unittest.main()
