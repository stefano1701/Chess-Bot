import random
import unittest

import chess

from chess_bot.bot import RandomBot


class RandomBotTests(unittest.TestCase):
    def test_returns_a_legal_move_without_changing_the_board(self) -> None:
        board = chess.Board()
        original_fen = board.fen()

        move = RandomBot(rng=random.Random(7)).choose_move(board)

        self.assertIn(move, board.legal_moves)
        self.assertEqual(board.fen(), original_fen)

    def test_rejects_finished_positions(self) -> None:
        board = chess.Board("7k/5Q2/7K/8/8/8/8/8 b - - 0 1")

        with self.assertRaisesRegex(ValueError, "finished position"):
            RandomBot().choose_move(board)


if __name__ == "__main__":
    unittest.main()
