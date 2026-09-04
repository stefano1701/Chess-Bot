"""Chess-playing agents.

The intentionally tiny interface here gives later search algorithms a natural
place to live without coupling them to terminal input/output.
"""

from __future__ import annotations

import random

import chess


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
