"""Position evaluation functions used at search leaves."""

from __future__ import annotations

import chess

from chess_bot.config import MaterialValues


class MaterialEvaluator:
    """Score terminal outcomes and the material remaining on the board."""

    def __init__(
        self,
        values: MaterialValues,
        *,
        mate_score: int = 100_000,
        draw_score: int = 0,
    ) -> None:
        self.values = values
        self.mate_score = mate_score
        self.draw_score = draw_score

    def evaluate(self, board: chess.Board) -> int:
        """Return centipawns from White's perspective."""
        outcome = board.outcome(claim_draw=True)
        if outcome is not None:
            if outcome.winner is chess.WHITE:
                return self.mate_score
            if outcome.winner is chess.BLACK:
                return -self.mate_score
            return self.draw_score

        score = 0
        for piece_type in chess.PIECE_TYPES:
            value = self.values.for_piece_type(piece_type)
            score += len(board.pieces(piece_type, chess.WHITE)) * value
            score -= len(board.pieces(piece_type, chess.BLACK)) * value
        return score
