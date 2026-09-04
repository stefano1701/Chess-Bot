import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import chess

from chess_bot.config import ConfigError, load_engine_config
from chess_bot.engine import create_bot


class DefaultConfigTests(unittest.TestCase):
    def test_default_config_describes_the_current_random_engine(self) -> None:
        config = load_engine_config()

        self.assertEqual(config.name, "Random Bot")
        self.assertEqual(config.strategy, "random")
        self.assertIsNone(config.random_seed)
        self.assertFalse(config.settings["search"]["enabled"])
        self.assertFalse(config.settings["evaluation"]["enabled"])
        self.assertFalse(config.settings["tactics"]["enabled"])
        self.assertFalse(config.settings["strategy"]["enabled"])
        self.assertEqual(
            config.settings["strategy"]["random_move_probability"], 1.0
        )

    def test_configured_seed_makes_move_selection_repeatable(self) -> None:
        config_path = self._write_config(
            "[engine]\n"
            'name = "Seeded Bot"\n'
            'strategy = "random"\n'
            "random_seed = 42\n"
        )
        config = load_engine_config(config_path)
        board = chess.Board()

        first_move = create_bot(config).choose_move(board)
        repeated_move = create_bot(config).choose_move(board)

        self.assertEqual(first_move, repeated_move)
        self.assertIn(first_move, board.legal_moves)

    def test_environment_variable_can_select_an_alternate_config(self) -> None:
        config_path = self._write_config(
            "[engine]\n"
            'name = "Alternate Bot"\n'
            'strategy = "random"\n'
            "random_seed = -1\n"
        )

        with patch.dict(os.environ, {"CHESS_BOT_CONFIG": str(config_path)}):
            config = load_engine_config()

        self.assertEqual(config.name, "Alternate Bot")
        self.assertEqual(config.source, config_path.resolve())

    def test_unsupported_strategy_has_a_clear_error(self) -> None:
        config_path = self._write_config(
            "[engine]\n"
            'name = "Future Bot"\n'
            'strategy = "alpha_beta"\n'
            "random_seed = -1\n"
        )

        with self.assertRaisesRegex(ConfigError, "Unsupported engine.strategy"):
            load_engine_config(config_path)

    def _write_config(self, contents: str) -> Path:
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        config_path = Path(temporary_directory.name) / "engine.toml"
        config_path.write_text(contents, encoding="utf-8")
        return config_path


if __name__ == "__main__":
    unittest.main()
