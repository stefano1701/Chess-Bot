from dataclasses import replace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility.
    import tomli as tomllib

from chess_bot.cli import (
    create_material_profile_interactively,
    prompt_bot_profile,
    prompt_tournament_game_count,
)
from chess_bot.config import load_engine_config


class ProfileMenuTests(unittest.TestCase):
    def test_blank_profile_selection_uses_the_default(self) -> None:
        config = load_engine_config()

        with (
            patch("builtins.input", return_value=""),
            redirect_stdout(StringIO()),
        ):
            selected = prompt_bot_profile(config, "Choose")

        self.assertEqual(selected, config.default_profile)

    def test_interactive_profile_creation_saves_entered_values(self) -> None:
        config = load_engine_config()
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        isolated_config = replace(
            config,
            profiles_directory=Path(temporary_directory.name),
        )
        answers = ["My Values", "", "300", "300", "", ""]

        with (
            patch("chess_bot.cli.clear_screen"),
            patch("builtins.input", side_effect=answers),
            redirect_stdout(StringIO()),
        ):
            profile_id = create_material_profile_interactively(isolated_config)

        self.assertEqual(profile_id, "my-values")
        with (Path(temporary_directory.name) / "my-values.toml").open("rb") as file:
            profile_data = tomllib.load(file)
        self.assertEqual(profile_data["material"]["pawn"], 100)
        self.assertEqual(profile_data["material"]["knight"], 300)
        self.assertEqual(profile_data["material"]["bishop"], 300)
        self.assertEqual(profile_data["material"]["rook"], 500)
        self.assertEqual(profile_data["material"]["queen"], 900)

    def test_tournament_game_count_rejects_invalid_input(self) -> None:
        with (
            patch("builtins.input", side_effect=["zero", "0", "7"]),
            redirect_stdout(StringIO()),
        ):
            games = prompt_tournament_game_count(20)

        self.assertEqual(games, 7)

    def test_tournament_profile_can_match_first_selection(self) -> None:
        config = load_engine_config()
        with (
            patch("builtins.input", return_value="1"),
            redirect_stdout(StringIO()),
        ):
            selected = prompt_bot_profile(config, "Choose Black")

        self.assertEqual(selected, config.default_profile)


if __name__ == "__main__":
    unittest.main()
