import random
import unittest

import chess

from chess_bot.bot import OnePlyMaterialBot, RandomBot
from chess_bot.config import MaterialValues
from chess_bot.evaluation import MaterialEvaluator


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


class OnePlyMaterialBotTests(unittest.TestCase):
    def setUp(self) -> None:
        evaluator = MaterialEvaluator(MaterialValues(100, 320, 330, 500, 900))
        self.bot = OnePlyMaterialBot(evaluator, rng=random.Random(7))

    def test_captures_the_most_valuable_available_piece(self) -> None:
        board = chess.Board("4k3/8/8/8/8/8/q7/R3K3 w Q - 0 1")
        original_fen = board.fen()

        move = self.bot.choose_move(board)

        self.assertEqual(move, chess.Move.from_uci("a1a2"))
        self.assertEqual(board.fen(), original_fen)

    def test_black_optimizes_material_from_blacks_perspective(self) -> None:
        board = chess.Board("r3k3/Q7/8/8/8/8/8/4K3 b q - 0 1")

        move = self.bot.choose_move(board)

        self.assertEqual(move, chess.Move.from_uci("a8a7"))

    def test_rejects_finished_positions(self) -> None:
        board = chess.Board("7k/5Q2/7K/8/8/8/8/8 b - - 0 1")

        with self.assertRaisesRegex(ValueError, "finished position"):
            self.bot.choose_move(board)


if __name__ == "__main__":
    unittest.main()
