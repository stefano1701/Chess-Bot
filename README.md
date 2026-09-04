# Chess Bot

A deliberately simple chess bot for learning how chess engines evaluate positions
and search game trees. The first version focuses on a clean, playable terminal
interface. Its entire strategy is to choose a random legal move.

## Current features

- Play against the bot as White or Black
- Watch two random-move bots play each other
- Unicode board that rotates to the human player's point of view
- Enter moves in simple UCI notation (`e2e4`, `g1f3`, `e7e8q`)
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

During a game, enter `help` to see the available commands. Press `Ctrl+C` at any
time to return to the main menu.

Castling is entered as the king's move (`e1g1` or `e1c1` for White), and a pawn
promotion adds the new piece at the end (`e7e8q`).

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
