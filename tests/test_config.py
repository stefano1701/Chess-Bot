import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from chess_bot.bot import OnePlyMaterialBot, RandomBot
from chess_bot.config import (
    ConfigError,
    MaterialValues,
    load_engine_config,
    save_material_profile,
)
from chess_bot.engine import create_bot


class ProfileConfigTests(unittest.TestCase):
    def test_default_config_provides_the_three_initial_profiles(self) -> None:
        config = load_engine_config()

        self.assertEqual(config.default_profile_id, "standard-material")
        self.assertEqual(
            set(config.profiles), {"random", "standard-material", "equal-minors"}
        )
        self.assertIsInstance(create_bot(config, "random"), RandomBot)
        self.assertIsInstance(
            create_bot(config, "standard-material"), OnePlyMaterialBot
        )
        self.assertEqual(config.tournament_default_games, 20)
        self.assertEqual(config.tournament_progress_bar_width, 32)

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

    def test_material_search_is_the_only_enabled_evaluation(self) -> None:
        config = load_engine_config()

        self.assertTrue(config.settings["search"]["enabled"])
        self.assertEqual(config.settings["search"]["max_depth"], 1)
        self.assertTrue(config.settings["evaluation"]["enabled"])
        self.assertTrue(config.settings["evaluation"]["material"]["enabled"])
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
        self.assertEqual(saved_profile.material, values)

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
    ) -> Path:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        root = Path(temporary_directory.name)
        profiles_directory = root / "profiles"
        profiles_directory.mkdir()
        config_path = root / "engine.toml"
        config_path.write_text(
            "[engine]\n"
            'default_profile = "test"\n'
            'profiles_directory = "profiles"\n\n'
            "[evaluation]\n"
            "mate_score = 100000\n"
            "draw_score = 0\n\n"
            "[evaluation.material]\n"
            "pawn = 100\n"
            "knight = 320\n"
            "bishop = 330\n"
            "rook = 500\n"
            "queen = 900\n"
            "king = 0\n\n"
            "[tournament]\n"
            "default_games = 20\n"
            "progress_bar_width = 32\n"
            "alternate_colors = true\n",
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
