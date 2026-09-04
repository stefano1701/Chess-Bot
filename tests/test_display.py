import unittest

import chess

from chess_bot.display import (
    DARK_SQUARE_BACKGROUND,
    LIGHT_SQUARE_BACKGROUND,
    render_board,
)


class BoardRenderingTests(unittest.TestCase):
    def test_white_orientation_has_black_back_rank_at_top(self) -> None:
        rendered = render_board(chess.Board(), chess.WHITE, use_color=False)

        self.assertIn("8 │ ♜ ░♞░ ♝ ░♛░ ♚ ░♝░ ♞ ░♜░│ 8", rendered)
        self.assertIn("6 │   ░░░   ░░░   ░░░   ░░░│ 6", rendered)
        self.assertTrue(rendered.startswith("    a  b  c  d  e  f  g  h "))

    def test_black_orientation_rotates_board_and_labels(self) -> None:
        rendered = render_board(chess.Board(), chess.BLACK, use_color=False)

        self.assertIn("1 │ ♖ ░♘░ ♗ ░♔░ ♕ ░♗░ ♘ ░♖░│ 1", rendered)
        self.assertTrue(rendered.startswith("    h  g  f  e  d  c  b  a "))

    def test_color_mode_uses_white_and_shaded_backgrounds(self) -> None:
        rendered = render_board(chess.Board(), use_color=True)

        self.assertIn(LIGHT_SQUARE_BACKGROUND, rendered)
        self.assertIn(DARK_SQUARE_BACKGROUND, rendered)
        self.assertNotIn("·", rendered)
        self.assertNotIn("•", rendered)


if __name__ == "__main__":
    unittest.main()
