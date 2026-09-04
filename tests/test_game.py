import unittest

import chess

from chess_bot.game import InvalidMoveError, move_history, parse_move, result_text


class MoveParsingTests(unittest.TestCase):
    def test_parses_uci(self) -> None:
        self.assertEqual(parse_move(chess.Board(), "e2e4"), chess.Move.from_uci("e2e4"))

    def test_rejects_san(self) -> None:
        with self.assertRaises(InvalidMoveError):
            parse_move(chess.Board(), "Nf3")

    def test_rejects_illegal_move(self) -> None:
        with self.assertRaises(InvalidMoveError):
            parse_move(chess.Board(), "e2e5")

    def test_parses_castling_as_a_king_move(self) -> None:
        board = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")

        self.assertEqual(parse_move(board, "e1g1"), chess.Move.from_uci("e1g1"))

    def test_parses_promotion_suffix(self) -> None:
        board = chess.Board("7k/P7/8/8/8/8/8/7K w - - 0 1")

        self.assertEqual(parse_move(board, "a7a8q"), chess.Move.from_uci("a7a8q"))

    def test_formats_move_history(self) -> None:
        board = chess.Board()
        for notation in ("e4", "e5", "Nf3"):
            board.push_san(notation)

        self.assertEqual(move_history(board), "1. e2e4 e7e5  2. g1f3")


class ResultTextTests(unittest.TestCase):
    def test_reports_checkmate(self) -> None:
        board = chess.Board()
        for notation in ("f3", "e5", "g4", "Qh4#"):
            board.push_san(notation)

        self.assertEqual(result_text(board), "0-1 — Black wins by checkmate.")


if __name__ == "__main__":
    unittest.main()
