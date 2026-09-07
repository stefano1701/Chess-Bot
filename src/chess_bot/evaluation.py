"""Position evaluation functions used at search leaves."""

from __future__ import annotations

import chess

from chess_bot.config import (
    MaterialValues,
    PieceSquareTableSet,
    PieceSquareWeights,
)


class MaterialEvaluator:
    """Score terminal outcomes, material, and optional piece-square values."""

    def __init__(
        self,
        values: MaterialValues,
        *,
        mate_score: int = 100_000,
        draw_score: int = 0,
        piece_square_weight: float = 0.0,
        piece_square_table_set: PieceSquareTableSet | None = None,
        piece_square_weights: PieceSquareWeights | None = None,
    ) -> None:
        self.values = values
        self.mate_score = mate_score
        self.draw_score = draw_score
        self.piece_square_weight = piece_square_weight
        self.piece_square_table_set = piece_square_table_set
        self.piece_square_weights = piece_square_weights or PieceSquareWeights()
        if piece_square_weight > 0 and piece_square_table_set is None:
            raise ValueError(
                "A piece-square table set is required when its weight is positive."
            )

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

    def piece_square_score(self, board: chess.Board) -> float:
        """Return the per-piece-weighted table score from White's perspective."""
        if self.piece_square_table_set is None:
            return 0.0
        score = 0.0
        for piece_type in chess.PIECE_TYPES:
            table = self.piece_square_table_set.for_piece_type(piece_type)
            piece_weight = self.piece_square_weights.for_piece_type(piece_type)
            for square in board.pieces(piece_type, chess.WHITE):
                score += table[square] * piece_weight
            for square in board.pieces(piece_type, chess.BLACK):
                score -= table[chess.square_mirror(square)] * piece_weight
        return score
