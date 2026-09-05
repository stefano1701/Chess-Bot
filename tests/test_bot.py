import random
import unittest

import chess

from chess_bot.bot import MinimaxBot, OnePlyMaterialBot, RandomBot
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


class MinimaxBotTests(unittest.TestCase):
    def setUp(self) -> None:
        evaluator = MaterialEvaluator(MaterialValues(100, 320, 330, 500, 900))
        self.bot = MinimaxBot(evaluator, depth=2, rng=random.Random(7))

    def test_avoids_a_capture_that_loses_the_queen_on_the_reply(self) -> None:
        board = chess.Board("3rk3/8/8/8/8/8/8/K2Q4 w - - 0 1")
        original_fen = board.fen()
        poisoned_capture = chess.Move.from_uci("d1d8")

        one_ply = OnePlyMaterialBot(
            self.bot.evaluator,
            rng=random.Random(7),
        )
        one_ply_move = one_ply.choose_move(board)
        minimax_move = self.bot.choose_move(board)

        self.assertEqual(one_ply_move, poisoned_capture)
        self.assertNotEqual(minimax_move, poisoned_capture)
        self.assertEqual(board.fen(), original_fen)
        self.assertEqual(self.bot.last_search_stats.depth, 2)
        self.assertGreater(self.bot.last_search_stats.nodes, len(list(board.legal_moves)))

    def test_black_also_avoids_a_poisoned_capture(self) -> None:
        board = chess.Board("k2q4/8/8/8/8/8/8/3RK3 b - - 0 1")
        poisoned_capture = chess.Move.from_uci("d8d1")

        one_ply = OnePlyMaterialBot(
            self.bot.evaluator,
            rng=random.Random(7),
        )

        self.assertEqual(one_ply.choose_move(board), poisoned_capture)
        self.assertNotEqual(self.bot.choose_move(board), poisoned_capture)

    def test_rejects_finished_positions(self) -> None:
        board = chess.Board("7k/5Q2/7K/8/8/8/8/8 b - - 0 1")

        with self.assertRaisesRegex(ValueError, "finished position"):
            self.bot.choose_move(board)

    def test_rejects_non_positive_search_depth(self) -> None:
        with self.assertRaisesRegex(ValueError, "depth must be positive"):
            MinimaxBot(self.bot.evaluator, depth=0)


if __name__ == "__main__":
    unittest.main()
