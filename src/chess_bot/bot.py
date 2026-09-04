"""Chess-playing agents.

The intentionally tiny interface here gives later search algorithms a natural
place to live without coupling them to terminal input/output.
"""

from __future__ import annotations

import random

import chess

from chess_bot.evaluation import MaterialEvaluator


class RandomBot:
    """A bot that chooses uniformly from the current legal moves."""

    def __init__(self, name: str = "Random Bot", rng: random.Random | None = None) -> None:
        self.name = name
        self._rng = rng or random.Random()

    def choose_move(self, board: chess.Board) -> chess.Move:
        """Return a random legal move without modifying *board*."""
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            raise ValueError("Cannot choose a move from a finished position.")
        return self._rng.choice(legal_moves)


class OnePlyMaterialBot:
    """Choose the move with the best immediate material evaluation."""

    def __init__(
        self,
        evaluator: MaterialEvaluator,
        name: str = "Material Bot",
        rng: random.Random | None = None,
    ) -> None:
        self.name = name
        self.evaluator = evaluator
        self._rng = rng or random.Random()

    def choose_move(self, board: chess.Board) -> chess.Move:
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            raise ValueError("Cannot choose a move from a finished position.")

        moving_color = board.turn
        best_score: int | None = None
        best_moves: list[chess.Move] = []

        for move in legal_moves:
            board.push(move)
            try:
                white_score = self.evaluator.evaluate(board)
            finally:
                board.pop()

            score = white_score if moving_color is chess.WHITE else -white_score
            if best_score is None or score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        return self._rng.choice(best_moves)
