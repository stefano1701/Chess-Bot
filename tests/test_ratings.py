import json
from pathlib import Path
import tempfile
import unittest

from chess_bot.ratings import EloRatings, MatchupResult, RatingError


class EloRatingsTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.path = Path(temporary_directory.name) / "ratings.json"
        self.ratings = EloRatings(
            self.path,
            initial_rating=1500,
            prior_std_deviation=100,
        )

    def test_complete_period_is_fitted_as_batch_elo(self) -> None:
        update = self.ratings.record_period(
            [MatchupResult("first", "second", 60, 0, 40)]
        )

        self.assertEqual(update.rated_games, 100)
        self.assertAlmostEqual(self.ratings.rating_for("first"), 1533.1396, places=3)
        self.assertAlmostEqual(self.ratings.rating_for("second"), 1466.8604, places=3)
        self.assertAlmostEqual(
            self.ratings.rating_for("first") + self.ratings.rating_for("second"),
            3000.0,
        )
        self.assertEqual((self.ratings.record_for("first").games, self.ratings.record_for("first").wins), (100, 60))

    def test_batch_ratings_do_not_depend_on_matchup_order(self) -> None:
        matchups = [
            MatchupResult("first", "second", 60, 20, 20),
            MatchupResult("first", "third", 40, 20, 40),
            MatchupResult("second", "third", 30, 20, 50),
        ]
        reversed_ratings = EloRatings(
            self.path.with_name("reversed.json"),
            initial_rating=1500,
            prior_std_deviation=100,
        )

        self.ratings.record_period(matchups)
        reversed_ratings.record_period(reversed(matchups))

        for profile_id in ("first", "second", "third"):
            self.assertAlmostEqual(
                self.ratings.rating_for(profile_id),
                reversed_ratings.rating_for(profile_id),
                places=9,
            )

    def test_drawn_period_leaves_equal_profiles_at_initial_rating(self) -> None:
        self.ratings.record_period(
            [MatchupResult("first", "second", 0, 10, 0)]
        )

        self.assertEqual(self.ratings.rating_for("first"), 1500.0)
        self.assertEqual(self.ratings.rating_for("second"), 1500.0)
        self.assertEqual(self.ratings.record_for("first").draws, 10)

    def test_same_profile_self_play_is_not_rated(self) -> None:
        update = self.ratings.record_period(
            [MatchupResult("same", "same", 1, 0, 1)]
        )

        self.assertEqual(update.rated_games, 0)
        self.assertEqual(update.unrated_same_profile_games, 2)
        self.assertEqual(self.ratings.rating_for("same"), 1500.0)
        self.assertEqual(self.ratings.games_for("same"), 0)

    def test_later_periods_use_all_recorded_head_to_head_results(self) -> None:
        self.ratings.record_period(
            [MatchupResult("first", "second", 60, 0, 40)]
        )
        first_rating = self.ratings.rating_for("first")
        self.ratings.record_period(
            [MatchupResult("first", "second", 40, 0, 60)]
        )

        self.assertEqual(self.ratings.rating_for("first"), 1500.0)
        self.assertEqual(self.ratings.rating_for("second"), 1500.0)
        self.assertGreater(first_rating, 1500.0)
        self.assertEqual(self.ratings.games_for("first"), 200)

    def test_ratings_matchups_and_lifetime_results_round_trip_through_json(self) -> None:
        self.ratings.record_period(
            [MatchupResult("first", "second", 6, 2, 2)]
        )
        self.ratings.save()

        reloaded = EloRatings.load(
            self.path,
            initial_rating=1500,
            prior_std_deviation=100,
        )

        self.assertAlmostEqual(
            reloaded.rating_for("first"),
            self.ratings.rating_for("first"),
            places=6,
        )
        self.assertEqual(reloaded.record_for("first").wins, 6)
        self.assertEqual(reloaded.record_for("second").losses, 6)
        self.assertEqual(reloaded.matchups[("first", "second")].draws, 2)

    def test_legacy_sequential_ratings_reset_but_keep_lifetime_counts(self) -> None:
        self.path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "ratings": {
                        "first": {
                            "rating": 1574.2,
                            "games": 100,
                            "wins": 60,
                            "draws": 20,
                            "losses": 20,
                        }
                    },
                }
            ),
            encoding="utf-8",
        )

        migrated = EloRatings.load(
            self.path,
            initial_rating=1500,
            prior_std_deviation=100,
        )

        self.assertEqual(migrated.rating_for("first"), 1500.0)
        self.assertEqual(migrated.games_for("first"), 100)
        self.assertEqual(migrated.record_for("first").wins, 60)
        self.assertEqual(migrated.matchups, {})
        self.assertTrue(migrated.legacy_ratings_reset)

    def test_invalid_ratings_file_has_a_clear_error(self) -> None:
        self.path.write_text("not json", encoding="utf-8")

        with self.assertRaisesRegex(RatingError, "Could not read Elo ratings"):
            EloRatings.load(self.path)


if __name__ == "__main__":
    unittest.main()
