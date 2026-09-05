# Chess Bot

A deliberately simple chess bot for learning how chess engines evaluate positions
and search game trees. It includes random and one-ply baselines plus fixed-depth
minimax, which assumes the opponent will choose their strongest available reply.

## Current features

- Play against a selected bot profile as White or Black
- Watch two independently selected profiles play each other
- Run headless multi-game tournaments with alternating colours, a live progress
  bar, and overall/White/Black statistics for each profile
- Create material-value profiles with a chosen search depth from the terminal menu
- See how many positions minimax examined after each move
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
[`profiles`](profiles) directory. The default is the two-ply minimax bot:

```toml
[engine]
default_profile = "two-ply-material"
profiles_directory = "profiles"
```

Four profiles are included:

- **Random Bot:** chooses any legal move uniformly.
- **Standard Material:** one ply; `P=100, N=320, B=330, R=500, Q=900`.
- **Equal Minor Pieces:** one ply; `P=100, N=300, B=300, R=500, Q=900`.
- **Two-Ply Material:** minimax depth 2; standard material values.

The one-ply bots inspect every legal move and select the best immediate material
score. The minimax bot also inspects every legal opponent reply, assumes the
opponent chooses the reply worst for it, and selects the move with the best
surviving score. Equal best moves are selected randomly. Search depth is measured
in plies: one ply is one player's move, so depth 2 means our move plus their reply.

Choose **Create a material-search bot profile** in the main menu to enter another
set of values and a search depth. Depth 1 creates the original one-ply strategy;
depth 2 or higher creates a minimax profile. Each custom profile is saved as an
editable TOML file in `profiles/` and automatically appears in the play,
spectator, and tournament selection menus. Depth 4 and above may become slow
without the pruning planned for the next milestone.

Choose **Run a bot tournament** to compare two bot players over multiple games.
Each player may use a different profile, or both may use the same profile to show
how that style plays against itself. Select the game count and each player's
profile for game 1; the players then swap colours after every game. Tournament
boards are not drawn. The terminal instead shows a live progress bar and a panel
for each player containing wins, draws, losses, win percentage, and chess score
percentage, both overall and split by colour. The final report also shows
White/Black results, average game length, and how games ended. With an odd game
count, Player 1 receives one extra game as White.

Every completed report is timestamped and appended to
`tournament-results.txt` in the project directory. The file is ignored by Git so
local tournament history does not create repository changes. Change
`tournament.results_file` if you want the log somewhere else.

Each profile also has a `random_seed`: `-1` gives fresh tie-breaking choices,
while a non-negative integer makes them repeatable. The remaining global sections
scaffold positional evaluation, deeper search, tactics, time management, online
play, and diagnostics. The `[tournament]` section controls the default game count,
progress-bar width, and results-file location; colour alternation is required.

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

1. Material-only one-ply evaluation (complete).
2. Fixed-depth minimax so the bot examines opponent replies (current).
3. Add alpha-beta pruning and move ordering.
4. Expand positional evaluation (piece-square tables, pawn structure, mobility,
   king safety, and more).
5. Add time management and an adapter for online bot play.

The engine and terminal UI are kept separate so each of these steps can be added
without rewriting the interface.
