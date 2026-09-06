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

Version: 0.10.0

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
- Headless repeated bot tournaments. The setup selects the game count, a
  replayable tournament seed, and profiles assigned White and Black in game 1,
  then alternates their colours. Adjacent games pair each player's random stream
  across the colour swap. A progress-only panel includes elapsed time and splits
  results overall, as White, and as Black. The final report adds total duration,
  speed, an approximate score confidence interval, and tournament performance
  Elo. Completed reports are timestamped and appended to a configurable local
  text file.
- Interactive creation of material profiles with a configurable search depth.
- Per-move node counts for minimax in human and spectator games.
- Persistent profile Elo ratings with K=16, updated game-by-game for tournaments
  between different profiles. Same-profile self-play is explicitly unrated.
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
  result aggregation, profile/colour breakdowns, and Elo integration.
- `src/chess_bot/ratings.py`: standard Elo calculations, lifetime profile
  records, JSON validation, and atomic persistence.
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
makes random moves and equal-score tie breaking reproducible outside tournaments;
the tournament runner deliberately overrides profile seeds with its reported
tournament seed. `CHESS_BOT_CONFIG` may point to an alternate global TOML file;
its profiles directory is resolved relative to that file.

`[tournament]` supplies the default number of games, default seed, progress-bar
width, and results log path. A seed of `-1` generates a fresh non-negative seed;
the selected seed is displayed and logged for replay. Relative log paths resolve
beside the selected `engine.toml`. The default `tournament-results.txt` is
deliberately gitignored. Tournament colour alternation is currently mandatory.
Competitors are tracked separately as Player 1 and Player 2, so they may use
different profiles or the same profile while retaining unambiguous statistics.
Adjacent colour-swapped games reuse each player's assigned random seed to reduce
tie-breaking noise. Games run synchronously and headlessly: no board is rendered,
but progress and elapsed time are redrawn after every game.

`[elo]` supplies the initial rating (1500 by default), K-factor (16), and local
ratings JSON path. Ratings are keyed by stable profile ID rather than display
name. Different-profile tournament games update Elo sequentially in memory and
the completed tournament saves `bot-ratings.json` atomically. This file is
gitignored. Historical text reports are not backfilled. Same-profile self-play
must remain unrated because both competitors share one rating identity.

Tournament performance Elo is separate from persistent Elo. It converts Player
1's aggregate tournament score to an Elo difference against Player 2 and is never
saved as a rating. The accompanying approximate 95% confidence interval uses the
observed win/draw/loss score variance. Both are descriptive tournament statistics;
the paired games mean the confidence interval's independence assumption is only
approximate.

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
