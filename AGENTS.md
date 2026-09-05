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

Version: 0.8.0

Three strategies are implemented: `random`, `one_ply`, and `minimax`. The one-ply
strategy chooses the best immediate material result. Minimax searches to the
profile's fixed depth, maximizing on White's turns and minimizing on Black's, so
depth 2 examines the opponent's best immediate reply. Terminal mate and draw
scores are respected at any searched depth. There is no alpha-beta pruning, move
ordering, positional evaluation, tactical/quiescence search, opening book,
tablebase, clock management, or online adapter yet.

The terminal application currently supports:

- Human vs a selected bot profile, with White, Black, or random colour selection.
- Bot vs bot spectator mode with separate White and Black profiles.
- Headless repeated bot tournaments. The setup selects the game count and the
  profiles assigned White and Black in game 1, then alternates their colours.
  A progress-only panel and final report split results overall, as White, and
  as Black. Completed reports are timestamped and appended to a configurable
  local text file.
- Interactive creation of material profiles with a configurable search depth.
- Per-move node counts for minimax in human and spectator games.
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
  overrides and search depth. One-ply and two-ply examples are included.
- `src/chess_bot/config.py`: loads, validates, and creates profiles.
- `src/chess_bot/engine.py`: constructs the selected engine implementation.
  Add future strategies here rather than branching in the terminal UI.
- `src/chess_bot/bot.py`: contains `RandomBot`, `OnePlyMaterialBot`, and the
  recursive fixed-depth `MinimaxBot`.
- `src/chess_bot/evaluation.py`: terminal-outcome and material evaluation.
- `src/chess_bot/game.py`: move parsing, move history, and result formatting.
- `src/chess_bot/display.py`: Unicode and terminal-colour board rendering.
- `src/chess_bot/tournament.py`: headless game loop, alternating scheduling,
  result aggregation, and profile/colour breakdowns.
- `src/chess_bot/cli.py`: menus, interactive game loops, and tournament report
  formatting; engine decisions do not belong here.
- `scripts/mike-chess`: personal macOS Terminal launcher.
- `tests/`: unit tests for rules-facing behavior, display, configuration, and
  bot move selection.

## Configuration contract

`engine.toml` deliberately contains settings for planned work as well as the
current fixed-depth search. Settings under disabled sections are documentation and
tuning placeholders; they must not affect play until the corresponding feature
is implemented and its section is enabled. Bot-specific settings belong in
`profiles/*.toml`.

The menu selects a profile, and each profile selects `profile.strategy`. At
present, validation accepts `random`, `one_ply`, and `minimax`. A minimax profile
uses `[search].depth`, falling back to global `search.max_depth`; non-minimax
profiles always report depth 1. When adding a strategy:

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

`[tournament]` supplies the default number of games, progress-bar width, and
results log path. Relative log paths resolve beside the selected `engine.toml`.
The default `tournament-results.txt` is deliberately gitignored. Tournament
colour alternation is currently mandatory. Competitors are tracked separately as
Player 1 and Player 2, so they may use different profiles or the same profile
while retaining unambiguous statistics. Games run synchronously and headlessly:
no board is rendered, but progress is redrawn after every game.

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
2. Material evaluation with one-ply move selection and profiles (complete).
3. Minimax search to a fixed configurable depth (current).
4. Alpha-beta pruning and basic move ordering (next).
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
