"""Rules-facing helpers shared by the terminal UI and future integrations."""

from __future__ import annotations

import chess


class InvalidMoveError(ValueError):
    """Raised when user input is not a legal move in the current position."""


def parse_move(board: chess.Board, text: str) -> chess.Move:
    """Parse a legal move in algebraic or UCI coordinate notation."""
    notation = text.strip()
    if not notation:
        raise InvalidMoveError("Enter a move, such as e4, Qh5, or e2e4.")

    try:
        return board.parse_san(notation)
    except ValueError:
        pass

    try:
        move = chess.Move.from_uci(notation.lower())
    except ValueError as error:
        raise InvalidMoveError(
            f"I couldn't understand {notation!r}. Try Qh5 or d1h5."
        ) from error

    if move not in board.legal_moves:
        raise InvalidMoveError(f"{notation!r} is not legal in this position.")
    return move


def result_text(board: chess.Board) -> str:
    """Return a friendly description of a finished board's outcome."""
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        return "Game in progress."

    reasons = {
        chess.Termination.CHECKMATE: "checkmate",
        chess.Termination.STALEMATE: "stalemate",
        chess.Termination.INSUFFICIENT_MATERIAL: "insufficient material",
        chess.Termination.SEVENTYFIVE_MOVES: "the seventy-five-move rule",
        chess.Termination.FIVEFOLD_REPETITION: "fivefold repetition",
        chess.Termination.FIFTY_MOVES: "the fifty-move rule",
        chess.Termination.THREEFOLD_REPETITION: "threefold repetition",
        chess.Termination.VARIANT_WIN: "a variant win",
        chess.Termination.VARIANT_LOSS: "a variant loss",
        chess.Termination.VARIANT_DRAW: "a variant draw",
    }
    reason = reasons.get(outcome.termination, outcome.termination.name.lower().replace("_", " "))

    if outcome.winner is chess.WHITE:
        return f"1-0 — White wins by {reason}."
    if outcome.winner is chess.BLACK:
        return f"0-1 — Black wins by {reason}."
    return f"1/2-1/2 — Draw by {reason}."


def move_history(board: chess.Board, max_full_moves: int = 6) -> str:
    """Format the latest moves as compact, numbered algebraic move pairs."""
    replay = board.root()
    moves: list[str] = []
    for move in board.move_stack:
        moves.append(replay.san(move))
        replay.push(move)

    pairs = [
        f"{index // 2 + 1}. {moves[index]}"
        + (f" {moves[index + 1]}" if index + 1 < len(moves) else "")
        for index in range(0, len(moves), 2)
    ]
    if len(pairs) > max_full_moves:
        pairs = ["…"] + pairs[-max_full_moves:]
    return "  ".join(pairs) if pairs else "No moves yet"
