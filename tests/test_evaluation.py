import unittest

import chess

from chess_bot.evaluation import MaterialEvaluator
from chess_bot.config import MaterialValues


class MaterialEvaluatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.standard = MaterialEvaluator(MaterialValues(100, 320, 330, 500, 900))

    def test_starting_position_is_equal(self) -> None:
        self.assertEqual(self.standard.evaluate(chess.Board()), 0)

    def test_missing_black_queen_is_plus_nine_hundred(self) -> None:
        board = chess.Board()
        board.remove_piece_at(chess.D8)

        self.assertEqual(self.standard.evaluate(board), 900)

    def test_profile_values_change_the_evaluation(self) -> None:
        board = chess.Board()
        board.remove_piece_at(chess.C8)
        board.remove_piece_at(chess.B1)
        equal_minors = MaterialEvaluator(MaterialValues(100, 300, 300, 500, 900))

        self.assertEqual(self.standard.evaluate(board), 10)
        self.assertEqual(equal_minors.evaluate(board), 0)

    def test_checkmate_outranks_material(self) -> None:
        board = chess.Board()
        for notation in ("f3", "e5", "g4", "Qh4#"):
            board.push_san(notation)

        self.assertEqual(self.standard.evaluate(board), -100_000)


if __name__ == "__main__":
    unittest.main()
