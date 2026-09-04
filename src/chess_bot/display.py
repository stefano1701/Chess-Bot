"""Unicode terminal rendering."""

from __future__ import annotations

import os
import sys

import chess


SQUARE_WIDTH = 3
LIGHT_SQUARE_FILL = " "
DARK_SQUARE_FILL = "░"
LIGHT_SQUARE_BACKGROUND = "\033[48;5;255m"
DARK_SQUARE_BACKGROUND = "\033[48;5;245m"
PIECE_FOREGROUND = "\033[38;5;16m"
RESET_COLOR = "\033[0m"


def render_board(
    board: chess.Board,
    orientation: chess.Color = chess.WHITE,
    use_color: bool | None = None,
) -> str:
    """Render a filled checkerboard with the chosen side at the bottom."""
    if use_color is None:
        use_color = sys.stdout.isatty()

    if orientation is chess.WHITE:
        files = list(range(8))
        ranks = list(range(7, -1, -1))
    else:
        files = list(range(7, -1, -1))
        ranks = list(range(8))

    file_labels = "   " + "".join(
        f"{chess.FILE_NAMES[file]:^{SQUARE_WIDTH}}" for file in files
    )
    horizontal_border = "─" * (len(files) * SQUARE_WIDTH)
    lines = [file_labels, f"  ┌{horizontal_border}┐"]
    for rank in ranks:
        cells: list[str] = []
        for file in files:
            square = chess.square(file, rank)
            piece = board.piece_at(square)
            symbol = piece.unicode_symbol() if piece else " "
            is_dark_square = (file + rank) % 2 == 0

            if use_color:
                background = (
                    DARK_SQUARE_BACKGROUND if is_dark_square else LIGHT_SQUARE_BACKGROUND
                )
                cells.append(
                    f"{background}{PIECE_FOREGROUND} {symbol} {RESET_COLOR}"
                )
            else:
                fill = DARK_SQUARE_FILL if is_dark_square else LIGHT_SQUARE_FILL
                cells.append(
                    f"{fill}{symbol}{fill}" if piece else fill * SQUARE_WIDTH
                )
        label = str(rank + 1)
        lines.append(f"{label} │{''.join(cells)}│ {label}")
    lines.extend([f"  └{horizontal_border}┘", file_labels])
    return "\n".join(lines)


def clear_screen() -> None:
    """Clear an interactive terminal while leaving redirected output readable."""
    if sys.stdout.isatty():
        command = "cls" if os.name == "nt" else "clear"
        os.system(command)
