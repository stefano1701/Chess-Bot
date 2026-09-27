import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from chess_bot.bot import MinimaxBot, OnePlyMaterialBot, RandomBot
from chess_bot.config import (
    ConfigError,
    MaterialValues,
    PieceSquareWeights,
    load_engine_config,
    save_material_profile,
)
from chess_bot.engine import create_bot


class ProfileConfigTests(unittest.TestCase):
    def test_default_config_provides_the_initial_profiles(self) -> None:
        config = load_engine_config()

        self.assertEqual(config.default_profile_id, "four-ply-material")
        self.assertTrue(
            {
                "random",
                "standard-material",
                "equal-minors",
                "four-ply-material",
                "four-ply-positional",
            }
            <= set(config.profiles)
        )
        self.assertIsInstance(create_bot(config, "random"), RandomBot)
        self.assertIsInstance(
            create_bot(config, "standard-material"), OnePlyMaterialBot
        )
        minimax_bot = create_bot(config, "four-ply-material")
        self.assertIsInstance(minimax_bot, MinimaxBot)
        self.assertEqual(minimax_bot.depth, 4)
        self.assertTrue(minimax_bot.alpha_beta)
        self.assertEqual(minimax_bot.move_ordering, "captures")
        positional = config.get_profile("four-ply-positional")
        positional_bot = create_bot(config, positional.id)
        self.assertEqual(positional.search_depth, 4)
        self.assertEqual(positional.piece_square_weight, 1.0)
        self.assertEqual(positional.piece_square_table_set_id, "simplified")
        self.assertEqual(positional.piece_square_weights, PieceSquareWeights())
        self.assertEqual(positional_bot.evaluator.piece_square_weight, 1.0)
        self.assertEqual(config.get_profile("four-ply-material").piece_square_weight, 0)
        self.assertEqual(config.tournament_default_games, 20)
        self.assertEqual(config.tournament_progress_bar_width, 32)
        self.assertEqual(config.tournament_results_file.name, "tournament-results.txt")
        self.assertEqual(config.round_robin_default_players, 4)
        self.assertEqual(config.round_robin_games_per_colour, 1)

    def test_equal_minor_profile_overrides_standard_values(self) -> None:
        config = load_engine_config()
        standard = config.get_profile("standard-material").material
        equal_minors = config.get_profile("equal-minors").material
        standard_bot = create_bot(config, "standard-material")
        equal_minors_bot = create_bot(config, "equal-minors")

        self.assertEqual((standard.knight, standard.bishop), (320, 330))
        self.assertEqual((equal_minors.knight, equal_minors.bishop), (300, 300))
        self.assertEqual(equal_minors.rook, 500)
        self.assertEqual(equal_minors.queen, 900)
        self.assertEqual(standard_bot.evaluator.values, standard)
        self.assertEqual(equal_minors_bot.evaluator.values, equal_minors)

    def test_historical_depth_four_profiles_match_published_point_values(self) -> None:
        config = load_engine_config()
        expected_values = {
            "4-ply-coxeter-1940": (100, 300, 350, 550, 1000),
            "4-ply-euwe-kramer-1944": (100, 350, 350, 550, 1000),
            "4-ply-shannon-1949": (100, 300, 300, 500, 900),
            "4-ply-turing-1953": (100, 300, 350, 500, 1000),
            "4-ply-mac-hack-1967": (100, 325, 350, 500, 975),
            "4-ply-chess-4-5-1977": (100, 325, 350, 500, 900),
            "4-ply-michniewski-1995": (100, 320, 330, 500, 900),
            "4-ply-berliner-1999": (100, 320, 333, 510, 880),
            "4-ply-kaufman-1999": (100, 325, 325, 500, 975),
            "4-ply-fruit-et-al-2005": (100, 400, 400, 600, 1200),
            "4-ply-kaufman-2012": (100, 350, 350, 525, 1000),
        }

        for profile_id, expected in expected_values.items():
            with self.subTest(profile_id=profile_id):
                profile = config.get_profile(profile_id)
                material = profile.material
                self.assertEqual(profile.strategy, "minimax")
                self.assertEqual(profile.search_depth, 4)
                self.assertEqual(profile.piece_square_weight, 0.0)
                self.assertEqual(
                    (
                        material.pawn,
                        material.knight,
                        material.bishop,
                        material.rook,
                        material.queen,
                    ),
                    expected,
                )
                self.assertEqual(material.king, 0)

    def test_piece_square_evaluation_is_available_but_off_by_default(self) -> None:
        config = load_engine_config()

        self.assertTrue(config.settings["search"]["enabled"])
        self.assertEqual(config.settings["search"]["max_depth"], 4)
        self.assertEqual(config.search_max_depth, 4)
        self.assertTrue(config.search_alpha_beta)
        self.assertEqual(config.search_move_ordering, "captures")
        self.assertEqual(config.elo_initial_rating, 1500)
        self.assertEqual(config.elo_prior_std_deviation, 100)
        self.assertEqual(config.elo_ratings_file.name, "bot-ratings.json")
        self.assertIsNone(config.tournament_default_seed)
        self.assertTrue(config.settings["evaluation"]["enabled"])
        self.assertTrue(config.settings["evaluation"]["material"]["enabled"])
        self.assertTrue(config.piece_square_tables_enabled)
        self.assertEqual(config.default_piece_square_weight, 0)
        self.assertTrue(
            config.settings["evaluation"]["piece_square_tables"]["enabled"]
        )
        self.assertEqual(
            config.settings["evaluation"]["piece_square_tables"][
                "default_table_set"
            ],
            "simplified",
        )
        simplified = config.get_piece_square_table_set("simplified")
        self.assertEqual(simplified.name, "Simplified")
        self.assertEqual(len(simplified.for_piece_type(2)), 64)
        self.assertEqual(simplified.for_piece_type(2)[21], 10)
        self.assertFalse(config.settings["tactics"]["enabled"])

    def test_configured_seed_makes_random_profile_repeatable(self) -> None:
        config_path = self._write_config(
            profile_name="Seeded Bot",
            strategy="random",
            random_seed=42,
        )
        config = load_engine_config(config_path)
        first_bot = create_bot(config)
        repeated_bot = create_bot(config)

        import chess

        board = chess.Board()
        self.assertEqual(first_bot.choose_move(board), repeated_bot.choose_move(board))

    def test_environment_variable_can_select_an_alternate_config(self) -> None:
        config_path = self._write_config(
            profile_name="Alternate Bot",
            strategy="random",
        )

        with patch.dict(os.environ, {"CHESS_BOT_CONFIG": str(config_path)}):
            config = load_engine_config()

        self.assertEqual(config.default_profile.name, "Alternate Bot")
        self.assertEqual(config.source, config_path.resolve())

    def test_custom_material_profile_is_saved_and_reloaded(self) -> None:
        config_path = self._write_config(
            profile_name="Initial Bot",
            strategy="random",
        )
        config = load_engine_config(config_path)
        values = MaterialValues(100, 300, 300, 500, 900)

        saved_path = save_material_profile(config, "My Equal Minors", values)
        reloaded = load_engine_config(config_path)
        saved_profile = reloaded.get_profile(saved_path.stem)

        self.assertEqual(saved_path.name, "my-equal-minors.toml")
        self.assertEqual(saved_profile.name, "My Equal Minors")
        self.assertEqual(saved_profile.strategy, "one_ply")
        self.assertEqual(saved_profile.search_depth, 1)
        self.assertEqual(saved_profile.material, values)

    def test_custom_minimax_profile_saves_its_search_depth(self) -> None:
        config_path = self._write_config(
            profile_name="Initial Bot",
            strategy="random",
        )
        config = load_engine_config(config_path)
        values = MaterialValues(100, 320, 330, 500, 900)

        saved_path = save_material_profile(
            config,
            "Depth Three",
            values,
            search_depth=3,
        )
        profile = load_engine_config(config_path).get_profile(saved_path.stem)

        self.assertEqual(profile.strategy, "minimax")
        self.assertEqual(profile.search_depth, 3)
        self.assertEqual(create_bot(load_engine_config(config_path), profile.id).depth, 3)

    def test_custom_profile_saves_piece_square_weight(self) -> None:
        config_path = self._write_config(
            profile_name="Initial Bot",
            strategy="random",
            piece_square_tables_enabled=True,
        )
        config = load_engine_config(config_path)
        values = MaterialValues(100, 320, 330, 500, 900)

        saved_path = save_material_profile(
            config,
            "Half Positional",
            values,
            search_depth=2,
            piece_square_weight=0.5,
            piece_square_table_set_id="simplified",
            piece_square_weights=PieceSquareWeights(knight=1.5, king=0.0),
        )
        profile = load_engine_config(config_path).get_profile(saved_path.stem)

        self.assertEqual(profile.piece_square_weight, 0.5)
        self.assertEqual(profile.piece_square_table_set_id, "simplified")
        self.assertEqual(profile.piece_square_weights.knight, 1.5)
        self.assertEqual(profile.piece_square_weights.king, 0.0)
        positional_bot = create_bot(load_engine_config(config_path), profile.id)
        self.assertEqual(positional_bot.depth, 2)

    def test_additional_piece_square_table_files_are_discovered(self) -> None:
        config_path = self._write_config(
            profile_name="Initial Bot",
            strategy="random",
            piece_square_tables_enabled=True,
        )
        tables_directory = config_path.parent / "piece-square-tables"
        source = tables_directory / "simplified.toml"
        experimental = tables_directory / "experimental.toml"
        experimental.write_text(
            source.read_text(encoding="utf-8").replace(
                'name = "Simplified"',
                'name = "Experimental"',
                1,
            ),
            encoding="utf-8",
        )

        config = load_engine_config(config_path)

        self.assertEqual(
            set(config.piece_square_table_sets),
            {"simplified", "experimental"},
        )
        self.assertEqual(
            config.get_piece_square_table_set("experimental").name,
            "Experimental",
        )

    def test_unsupported_profile_strategy_has_a_clear_error(self) -> None:
        config_path = self._write_config(
            profile_name="Future Bot",
            strategy="alpha_beta",
        )

        with self.assertRaisesRegex(ConfigError, "Unsupported strategy"):
            load_engine_config(config_path)

    def _write_config(
        self,
        *,
        profile_name: str,
        strategy: str,
        random_seed: int = -1,
        piece_square_tables_enabled: bool = False,
    ) -> Path:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        root = Path(temporary_directory.name)
        profiles_directory = root / "profiles"
        profiles_directory.mkdir()
        if piece_square_tables_enabled:
            tables_directory = root / "piece-square-tables"
            tables_directory.mkdir()
            shutil.copyfile(
                Path(__file__).parents[1]
                / "piece-square-tables"
                / "simplified.toml",
                tables_directory / "simplified.toml",
            )
        config_path = root / "engine.toml"
        config_path.write_text(
            "[engine]\n"
            'default_profile = "test"\n'
            'profiles_directory = "profiles"\n\n'
            "[evaluation]\n"
            "mate_score = 100000\n"
            "draw_score = 0\n\n"
            "[evaluation.weights]\n"
            "piece_square_tables = 0.0\n\n"
            "[evaluation.material]\n"
            "pawn = 100\n"
            "knight = 320\n"
            "bishop = 330\n"
            "rook = 500\n"
            "queen = 900\n"
            "king = 0\n\n"
            "[evaluation.piece_square_tables]\n"
            f"enabled = {str(piece_square_tables_enabled).lower()}\n\n"
            'directory = "piece-square-tables"\n'
            'default_table_set = "simplified"\n\n'
            "[tournament]\n"
            "default_games = 20\n"
            "progress_bar_width = 32\n"
            "alternate_colors = true\n"
            'results_file = "tournament-results.txt"\n',
            encoding="utf-8",
        )
        (profiles_directory / "test.toml").write_text(
            "[profile]\n"
            f'name = "{profile_name}"\n'
            f'strategy = "{strategy}"\n'
            f"random_seed = {random_seed}\n",
            encoding="utf-8",
        )
        return config_path


if __name__ == "__main__":
    unittest.main()
