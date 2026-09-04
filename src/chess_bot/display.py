"""Unicode terminal rendering."""

from __future__ import annotations

import os
import sys

import chess


EMPTY_LIGHT = "·"
EMPTY_DARK = "•"


def render_board(board: chess.Board, orientation: chess.Color = chess.WHITE) -> str:
    """Render *board* with coordinates and the chosen side at the bottom."""
    if orientation is chess.WHITE:
        files = list(range(8))
        ranks = list(range(7, -1, -1))
    else:
        files = list(range(7, -1, -1))
        ranks = list(range(8))

    square_width = 3
    file_labels = "   " + "".join(
        f"{chess.FILE_NAMES[file]:^{square_width}}" for file in files
    )
    horizontal_border = "─" * (len(files) * square_width)
    lines = [file_labels, f"  ┌{horizontal_border}┐"]
    for rank in ranks:
        cells: list[str] = []
        for file in files:
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            if piece:
                symbol = piece.unicode_symbol()
            else:
                symbol = EMPTY_DARK if (file + rank) % 2 == 0 else EMPTY_LIGHT
            cells.append(f"{symbol:^{square_width}}")
        label = str(rank + 1)
        lines.append(f"{label} │{''.join(cells)}│ {label}")
    lines.extend([f"  └{horizontal_border}┘", file_labels])
    return "\n".join(lines)


def clear_screen() -> None:
    """Clear an interactive terminal while leaving redirected output readable."""
    if sys.stdout.isatty():
        command = "cls" if os.name == "nt" else "clear"
        os.system(command)
