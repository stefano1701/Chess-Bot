import unittest

import chess

from chess_bot.display import render_board


class BoardRenderingTests(unittest.TestCase):
    def test_white_orientation_has_black_back_rank_at_top(self) -> None:
        rendered = render_board(chess.Board(), chess.WHITE)

        self.assertIn("8 │ ♜  ♞  ♝  ♛  ♚  ♝  ♞  ♜ │ 8", rendered)
        self.assertTrue(rendered.startswith("    a  b  c  d  e  f  g  h "))

    def test_black_orientation_rotates_board_and_labels(self) -> None:
        rendered = render_board(chess.Board(), chess.BLACK)

        self.assertIn("1 │ ♖  ♘  ♗  ♔  ♕  ♗  ♘  ♖ │ 1", rendered)
        self.assertTrue(rendered.startswith("    h  g  f  e  d  c  b  a "))


if __name__ == "__main__":
    unittest.main()
