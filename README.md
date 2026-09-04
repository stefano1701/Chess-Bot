# Chess Bot

A deliberately simple chess bot for learning how chess engines evaluate positions
and search game trees. The first version focuses on a clean, playable terminal
interface. Its entire strategy is to choose a random legal move.

## Current features

- Play against the bot as White or Black
- Watch two random-move bots play each other
- Filled Unicode checkerboard with white and shaded squares, rotated to the
  human player's point of view
- Enter moves in standard algebraic notation (`e4`, `Nf3`, `Qh5`) or coordinate
  notation (`e2e4`, `g1f3`, `d1h5`)
- Detect checkmate, stalemate, repetition, insufficient material, and move-rule draws

## Run it

Python 3.10 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
chess-bot
```

You can also start it with:

```bash
python -m chess_bot
```

On macOS, the included `scripts/mike-chess` launcher temporarily enlarges the
current Terminal tab to 24-point text, then restores its previous font size when
the game exits. Install the personal command with:

```bash
ln -s "$(pwd)/scripts/mike-chess" "$HOME/.local/bin/mike-chess"
```

Set a different size for one launch with, for example,
`MIKE_CHESS_FONT_SIZE=28 mike-chess`.

During a game, enter `help` to see the available commands. Press `Ctrl+C` at any
time to return to the main menu.

Castling can be entered as `O-O` or `O-O-O`. Pawn promotion is written as `e8=Q`.
The coordinate equivalents (`e1g1` and `e7e8q`) continue to work too.

The size of Unicode chess pieces is controlled by your terminal font. On macOS,
the `mike-chess` launcher handles that automatically. `Command` + `+` can still
be used to adjust it manually.

## Test it

```bash
python -m unittest discover -s tests
```

## Planned learning path

1. Replace random moves with a material-only evaluation.
2. Add minimax search.
3. Add alpha-beta pruning and move ordering.
4. Expand positional evaluation (piece-square tables, pawn structure, mobility,
   king safety, and more).
5. Add time management and an adapter for online bot play.

The engine and terminal UI are kept separate so each of these steps can be added
without rewriting the interface.
