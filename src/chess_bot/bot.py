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
    cutoffs: int = 0


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
    """Search fixed-depth minimax with optional alpha-beta pruning."""

    def __init__(
        self,
        evaluator: MaterialEvaluator,
        depth: int,
        name: str = "Minimax Bot",
        rng: random.Random | None = None,
        alpha_beta: bool = True,
        move_ordering: str = "captures",
    ) -> None:
        if depth <= 0:
            raise ValueError("Search depth must be positive.")
        self.name = name
        self.evaluator = evaluator
        self.depth = depth
        self._rng = rng or random.Random()
        self.alpha_beta = alpha_beta
        if move_ordering not in {"none", "captures"}:
            raise ValueError("Move ordering must be 'none' or 'captures'.")
        self.move_ordering = move_ordering
        self._nodes = 0
        self._cutoffs = 0
        self.last_search_stats = SearchStats(depth=depth, nodes=0, cutoffs=0)

    def choose_move(self, board: chess.Board) -> chess.Move:
        legal_moves = list(board.legal_moves)
        if not legal_moves:
            raise ValueError("Cannot choose a move from a finished position.")
        # Searching a random root order makes the first equally best move a
        # uniform, seeded choice without needing to search every tied move twice.
        self._rng.shuffle(legal_moves)

        maximizing = board.turn is chess.WHITE
        best_score: int | None = None
        best_move: chess.Move | None = None
        self._nodes = 0
        self._cutoffs = 0
        alpha = -float("inf")
        beta = float("inf")

        for move in legal_moves:
            board.push(move)
            try:
                score = self._search(board, self.depth - 1, alpha, beta)
            finally:
                board.pop()

            is_better = (
                best_score is None
                or (maximizing and score > best_score)
                or (not maximizing and score < best_score)
            )
            if is_better:
                best_score = score
                best_move = move
            if self.alpha_beta and best_score is not None:
                if maximizing:
                    alpha = max(alpha, best_score)
                else:
                    beta = min(beta, best_score)

        self.last_search_stats = SearchStats(
            depth=self.depth,
            nodes=self._nodes,
            cutoffs=self._cutoffs,
        )
        if best_move is None:  # Defensive: legal_moves was checked above.
            raise RuntimeError("Search failed to select a legal move.")
        return best_move

    def _search(
        self,
        board: chess.Board,
        depth_remaining: int,
        alpha: float,
        beta: float,
    ) -> int:
        self._nodes += 1
        if depth_remaining == 0 or board.is_game_over(claim_draw=True):
            return self.evaluator.evaluate(board)

        maximizing = board.turn is chess.WHITE
        best_score: int | None = None
        for move in self._ordered_moves(board):
            board.push(move)
            try:
                score = self._search(board, depth_remaining - 1, alpha, beta)
            finally:
                board.pop()

            if best_score is None or (
                maximizing and score > best_score
            ) or (not maximizing and score < best_score):
                best_score = score
            if self.alpha_beta:
                if maximizing:
                    alpha = max(alpha, score)
                else:
                    beta = min(beta, score)
                if alpha >= beta:
                    self._cutoffs += 1
                    break

        if best_score is None:  # Defensive: terminal nodes return above.
            return self.evaluator.evaluate(board)
        return best_score

    def _ordered_moves(self, board: chess.Board) -> list[chess.Move]:
        moves = list(board.legal_moves)
        if self.move_ordering == "none":
            return moves
        return sorted(
            moves,
            key=lambda move: self._move_order_key(board, move),
            reverse=True,
        )

    def _move_order_key(
        self,
        board: chess.Board,
        move: chess.Move,
    ) -> tuple[bool, bool, int, int, int]:
        """Put promotions and valuable captures before quiet moves."""
        is_capture = board.is_capture(move)
        captured_piece_type: int | None = None
        if board.is_en_passant(move):
            captured_piece_type = chess.PAWN
        elif is_capture:
            captured_piece = board.piece_at(move.to_square)
            if captured_piece is not None:
                captured_piece_type = captured_piece.piece_type

        captured_value = (
            self.evaluator.values.for_piece_type(captured_piece_type)
            if captured_piece_type is not None
            else 0
        )
        moving_piece = board.piece_at(move.from_square)
        moving_value = (
            self.evaluator.values.for_piece_type(moving_piece.piece_type)
            if moving_piece is not None
            else 0
        )
        promotion_value = (
            self.evaluator.values.for_piece_type(move.promotion)
            if move.promotion is not None
            else 0
        )
        return (
            move.promotion is not None,
            is_capture,
            captured_value,
            -moving_value,
            promotion_value,
        )
