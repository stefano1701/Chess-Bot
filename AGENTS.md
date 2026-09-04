# Chess Bot: Agent Handover

Read this file before changing the project. Keep it current whenever a milestone
changes the engine architecture, user experience, or development direction.

## Product intent

This is Mike's learning project. The eventual goal is a chess bot that can play
other bots online, but the immediate purpose is to learn positional evaluation,
search, tactics, and engine design one understandable step at a time.

Implementation sophistication is not the goal by itself. Prefer small, visible,
well-tested engine improvements that Mike can reason about. Do not skip directly
to a mature engine or hide the interesting decisions behind an external engine.

## Current milestone

Version: 0.6.0

Two strategies are implemented: `random` and `one_ply`. The one-ply strategy
examines every legal move, evaluates the resulting material from White's
perspective, and chooses the best immediate score for the moving side. It detects
immediate mate and draw outcomes, but it does not examine the opponent's reply.
There is no positional evaluation, deeper tree search, tactical/quiescence search,
opening book, tablebase, clock management, or online adapter yet.

The terminal application currently supports:

- Human vs a selected bot profile, with White, Black, or random colour selection.
- Bot vs bot spectator mode with separate White and Black profiles.
- Interactive creation of one-ply material profiles.
- SAN input such as `e4`, `Nf3`, `Qh5`, and `O-O`.
- UCI coordinate input such as `e2e4`, `g1f3`, and `e7e8q`.
- A Unicode board with white and shaded squares, rotated for a Black player.
- Standard game outcomes handled by `python-chess`.
- A personal `mike-chess` launcher that temporarily uses 24-point text in
  macOS Terminal and restores the previous font size on exit.

## Source map

- `engine.toml`: the single source of truth for engine behavior and future
  shared tuning values. Read it before doing engine work.
- `profiles/*.toml`: bot names, strategies, seeds, and optional material-value
  overrides. Standard Material and Equal Minor Pieces are included examples.
- `src/chess_bot/config.py`: loads, validates, and creates profiles.
- `src/chess_bot/engine.py`: constructs the selected engine implementation.
  Add future strategies here rather than branching in the terminal UI.
- `src/chess_bot/bot.py`: contains `RandomBot` and `OnePlyMaterialBot`.
- `src/chess_bot/evaluation.py`: terminal-outcome and material evaluation.
- `src/chess_bot/game.py`: move parsing, move history, and result formatting.
- `src/chess_bot/display.py`: Unicode and terminal-colour board rendering.
- `src/chess_bot/cli.py`: menus and interactive game loops only.
- `scripts/mike-chess`: personal macOS Terminal launcher.
- `tests/`: unit tests for rules-facing behavior, display, configuration, and
  bot move selection.

## Configuration contract

`engine.toml` deliberately contains settings for planned work as well as the
current one-ply search. Settings under disabled sections are documentation and
tuning placeholders; they must not affect play until the corresponding feature
is implemented and its section is enabled. Bot-specific settings belong in
`profiles/*.toml`.

The menu selects a profile, and each profile selects `profile.strategy`. At
present, validation accepts `random` and `one_ply`. When adding a strategy:

1. Implement it behind the same `choose_move(board)` boundary used by
   `RandomBot`.
2. Add it to the factory in `src/chess_bot/engine.py`.
3. Extend config validation only for settings that implementation actually uses.
4. Enable and tune the relevant `engine.toml` sections.
5. Add deterministic unit tests and update this file and the README.

`profile.random_seed = -1` means fresh system randomness. A non-negative integer
makes random moves and equal-score tie breaking reproducible. `CHESS_BOT_CONFIG`
may point to an alternate global TOML file; its profiles directory is resolved
relative to that file.

## Design rules

- Let `python-chess` remain the authority for legal moves, check, checkmate,
  draw rules, SAN, UCI, and board state.
- Keep the UI separate from engine decisions. The online adapter should
  eventually call the same engine boundary as the terminal UI.
- Do not call Stockfish or another external engine to choose moves. That would
  defeat the learning objective. External engines may eventually be used only
  for optional testing or comparison when Mike asks for it.
- Preserve both SAN and UCI input unless Mike explicitly changes that decision.
- Prefer scores in centipawns. Positive evaluation should consistently mean an
  advantage for White unless a later documented decision changes the convention.
- Make randomness injectable or seedable so engine behavior can be tested.
- Keep new heuristics individually switchable and weighted in `engine.toml`.
- Explain new chess ideas in plain language in documentation or the UI; the
  learning value matters as much as playing strength.
- Avoid premature performance complexity. Measure before adding caches,
  pruning, concurrency, or native extensions.

## Intended learning sequence

1. Random legal moves (complete).
2. Material evaluation with one-ply move selection and profiles (current).
3. Negamax/minimax search to a fixed depth.
4. Alpha-beta pruning and basic move ordering.
5. Quiescence search for tactical stability.
6. Positional features: piece-square tables, mobility, pawn structure, king
   safety, space, development, and endgame adjustments.
7. Iterative deepening, transposition tables, and time management.
8. Online-bot protocol adapter, resilience, and observability.

This sequence is guidance, not permission to implement future stages early.
Follow Mike's requested pace.

## Development workflow

From the repository root:

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
mike-chess
```

Before handing off a change:

- Run the complete unit test suite.
- Smoke-test the affected interactive path where practical.
- Run `git diff --check`.
- Update `engine.toml`, this handover, and the README when their claims change.
- Keep the working tree free of generated files and unrelated edits.

The public repository is `https://github.com/stefano1701/Chess-Bot`, with `main`
as its default branch.
