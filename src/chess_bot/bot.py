"""Chess-playing agents.

The intentionally tiny interface here gives later search algorithms a natural
place to live without coupling them to terminal input/output.
"""

from __future__ import annotations

from dataclasses import dataclass
import random

import chess

from chess_bot.evaluation import MaterialEvaluator


@dataclass(frozen=True)
class SearchStats:
    depth: int
    nodes: int


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


class MinimaxBot:
    """Search a fixed number of plies, assuming optimal replies."""

    def __init__(
        self,
        evaluator: MaterialEvaluator,
        depth: int,
        name: str = "Minimax Bot",
        rng: random.Random | None = None,
    ) -> None:
        if depth <= 0:
            raise ValueError("Search depth must be positive.")
        self.name = name
        self.evaluator = evaluator
        self.depth = depth
        self._rng = rng or random.Random()
        self._nodes = 0
        self.last_search_stats = SearchStats(depth=depth, nodes=0)

    def choose_move(self, board: chess.Board) -> chess.Move:
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            raise ValueError("Cannot choose a move from a finished position.")

        maximizing = board.turn is chess.WHITE
        best_score: int | None = None
        best_moves: list[chess.Move] = []
        self._nodes = 0

        for move in legal_moves:
            board.push(move)
            try:
                score = self._search(board, self.depth - 1)
            finally:
                board.pop()

            is_better = (
                best_score is None
                or (maximizing and score > best_score)
                or (not maximizing and score < best_score)
            )
            if is_better:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)

        self.last_search_stats = SearchStats(depth=self.depth, nodes=self._nodes)
        return self._rng.choice(best_moves)

    def _search(self, board: chess.Board, depth_remaining: int) -> int:
        self._nodes += 1
        if depth_remaining == 0 or board.is_game_over(claim_draw=True):
            return self.evaluator.evaluate(board)

        maximizing = board.turn is chess.WHITE
        best_score: int | None = None
        for move in board.legal_moves:
            board.push(move)
            try:
                score = self._search(board, depth_remaining - 1)
            finally:
                board.pop()

            if (
                best_score is None
                or (maximizing and score > best_score)
                or (not maximizing and score < best_score)
            ):
                best_score = score

        if best_score is None:  # Defensive: terminal nodes return above.
            return self.evaluator.evaluate(board)
        return best_score
