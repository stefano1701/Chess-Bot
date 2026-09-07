"""Position evaluation functions used at search leaves."""

from __future__ import annotations

import chess

from chess_bot.config import MaterialValues


def _table(*ranks: tuple[int, ...]) -> tuple[int, ...]:
    """Flatten ranks 1 to 8, each ordered from file a to file h."""
    if len(ranks) != 8 or any(len(rank) != 8 for rank in ranks):
        raise ValueError("A piece-square table must contain eight ranks of eight.")
    return tuple(value for rank in ranks for value in rank)


# Small, deliberately understandable centipawn adjustments. The tables are from
# White's point of view; black's squares are mirrored before lookup. They reward
# central knights, developed bishops and pawns, active rooks/queens, advanced
# pawns, and a king kept near castling squares during this first positional stage.
PIECE_SQUARE_TABLES: dict[int, tuple[int, ...]] = {
    chess.PAWN: _table(
        (0, 0, 0, 0, 0, 0, 0, 0),
        (5, 10, 10, -20, -20, 10, 10, 5),
        (5, -5, -10, 0, 0, -10, -5, 5),
        (0, 0, 0, 20, 20, 0, 0, 0),
        (5, 5, 10, 25, 25, 10, 5, 5),
        (10, 10, 20, 30, 30, 20, 10, 10),
        (50, 50, 50, 50, 50, 50, 50, 50),
        (0, 0, 0, 0, 0, 0, 0, 0),
    ),
    chess.KNIGHT: _table(
        (-50, -40, -30, -30, -30, -30, -40, -50),
        (-40, -20, 0, 5, 5, 0, -20, -40),
        (-30, 5, 10, 15, 15, 10, 5, -30),
        (-30, 0, 15, 20, 20, 15, 0, -30),
        (-30, 5, 15, 20, 20, 15, 5, -30),
        (-30, 0, 10, 15, 15, 10, 0, -30),
        (-40, -20, 0, 0, 0, 0, -20, -40),
        (-50, -40, -30, -30, -30, -30, -40, -50),
    ),
    chess.BISHOP: _table(
        (-20, -10, -10, -10, -10, -10, -10, -20),
        (-10, 5, 0, 0, 0, 0, 5, -10),
        (-10, 10, 10, 10, 10, 10, 10, -10),
        (-10, 0, 10, 10, 10, 10, 0, -10),
        (-10, 5, 10, 10, 10, 10, 5, -10),
        (-10, 5, 5, 10, 10, 5, 5, -10),
        (-10, 0, 5, 0, 0, 5, 0, -10),
        (-20, -10, -10, -10, -10, -10, -10, -20),
    ),
    chess.ROOK: _table(
        (0, 0, 0, 5, 5, 0, 0, 0),
        (-5, 0, 0, 0, 0, 0, 0, -5),
        (-5, 0, 0, 0, 0, 0, 0, -5),
        (-5, 0, 0, 0, 0, 0, 0, -5),
        (-5, 0, 0, 0, 0, 0, 0, -5),
        (-5, 0, 0, 0, 0, 0, 0, -5),
        (5, 10, 10, 10, 10, 10, 10, 5),
        (0, 0, 0, 0, 0, 0, 0, 0),
    ),
    chess.QUEEN: _table(
        (-20, -10, -10, -5, -5, -10, -10, -20),
        (-10, 0, 0, 0, 0, 0, 0, -10),
        (-10, 0, 5, 5, 5, 5, 0, -10),
        (-5, 0, 5, 5, 5, 5, 0, -5),
        (-5, 0, 5, 5, 5, 5, 0, -5),
        (-10, 5, 5, 5, 5, 5, 0, -10),
        (-10, 0, 5, 0, 0, 0, 0, -10),
        (-20, -10, -10, -5, -5, -10, -10, -20),
    ),
    chess.KING: _table(
        (20, 30, 10, 0, 0, 10, 30, 20),
        (20, 20, 0, 0, 0, 0, 20, 20),
        (-10, -20, -20, -20, -20, -20, -20, -10),
        (-20, -30, -30, -40, -40, -30, -30, -20),
        (-30, -40, -40, -50, -50, -40, -40, -30),
        (-30, -40, -40, -50, -50, -40, -40, -30),
        (-30, -40, -40, -50, -50, -40, -40, -30),
        (-30, -40, -40, -50, -50, -40, -40, -30),
    ),
}


class MaterialEvaluator:
    """Score terminal outcomes, material, and optional piece-square values."""

    def __init__(
        self,
        values: MaterialValues,
        *,
        mate_score: int = 100_000,
        draw_score: int = 0,
        piece_square_weight: float = 0.0,
    ) -> None:
        self.values = values
        self.mate_score = mate_score
        self.draw_score = draw_score
        self.piece_square_weight = piece_square_weight

    def evaluate(self, board: chess.Board) -> int:
        """Return centipawns from White's perspective."""
        outcome = board.outcome(claim_draw=True)
        if outcome is not None:
            if outcome.winner is chess.WHITE:
                return self.mate_score
            if outcome.winner is chess.BLACK:
                return -self.mate_score
            return self.draw_score

        material_score = 0
        for piece_type in chess.PIECE_TYPES:
            value = self.values.for_piece_type(piece_type)
            material_score += len(board.pieces(piece_type, chess.WHITE)) * value
            material_score -= len(board.pieces(piece_type, chess.BLACK)) * value

        if self.piece_square_weight == 0:
            return material_score
        positional_score = self.piece_square_score(board)
        return material_score + round(self.piece_square_weight * positional_score)

    def piece_square_score(self, board: chess.Board) -> int:
        """Return the unweighted positional-table score for White."""
        score = 0
        for piece_type, table in PIECE_SQUARE_TABLES.items():
            for square in board.pieces(piece_type, chess.WHITE):
                score += table[square]
            for square in board.pieces(piece_type, chess.BLACK):
                score -= table[chess.square_mirror(square)]
        return score
