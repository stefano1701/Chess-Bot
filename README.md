# Chess Bot

A deliberately simple chess bot for learning how chess engines evaluate positions
and search game trees. It now includes a random baseline and the first real search
stage: choosing the move with the best immediate material result.

## Current features

- Play against a selected bot profile as White or Black
- Watch two independently selected profiles play each other
- Run headless multi-game tournaments with alternating colours, a live progress
  bar, and overall/White/Black statistics for each profile
- Create material-value profiles from the terminal menu
- Filled Unicode checkerboard with white and shaded squares, rotated to the
  human player's point of view
- Enter moves in standard algebraic notation (`e4`, `Nf3`, `Qh5`) or coordinate
  notation (`e2e4`, `g1f3`, `d1h5`)
- Detect checkmate, stalemate, repetition, insufficient material, and move-rule draws
- Central `engine.toml` configuration plus individual profile files

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

## Engine configuration

[`engine.toml`](engine.toml) controls shared engine behavior and points to the
[`profiles`](profiles) directory. The default is the one-ply material bot:

```toml
[engine]
default_profile = "standard-material"
profiles_directory = "profiles"
```

Three profiles are included:

- **Random Bot:** chooses any legal move uniformly.
- **Standard Material:** `P=100, N=320, B=330, R=500, Q=900`.
- **Equal Minor Pieces:** `P=100, N=300, B=300, R=500, Q=900`.

The two material bots inspect every legal move, evaluate the resulting material,
and select the best score. They do not yet examine the opponent's reply. Equal
best moves are selected randomly.

Choose **Create a material bot profile** in the main menu to enter another set of
values. Each custom profile is saved as an editable TOML file in `profiles/` and
automatically appears in the play, spectator, and tournament selection menus.

Choose **Run a bot tournament** to compare two different profiles over multiple
games. Select the game count and each profile's colour for game 1; the profiles
then swap colours after every game. Tournament boards are not drawn. The terminal
instead shows a live progress bar and each profile's wins, draws, losses, win
percentage, and chess score percentage, both overall and split by colour. The
final report also shows White/Black results, average game length, and how games
ended. With an odd game count, the first profile selected receives one extra game
as White.

Each profile also has a `random_seed`: `-1` gives fresh tie-breaking choices,
while a non-negative integer makes them repeatable. The remaining global sections
scaffold positional evaluation, deeper search, tactics, time management, online
play, and diagnostics. The `[tournament]` section controls the default game count
and progress-bar width; colour alternation is required.

Set the `CHESS_BOT_CONFIG` environment variable to experiment with a separate
configuration without editing the default file.

[`AGENTS.md`](AGENTS.md) is the project handover for future Codex sessions. It
records the learning objective, current milestone, architecture, design rules,
and intended development sequence.

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

1. Material-only one-ply evaluation (current).
2. Add negamax/minimax search so the bot examines opponent replies.
3. Add alpha-beta pruning and move ordering.
4. Expand positional evaluation (piece-square tables, pawn structure, mobility,
   king safety, and more).
5. Add time management and an adapter for online bot play.

The engine and terminal UI are kept separate so each of these steps can be added
without rewriting the interface.
