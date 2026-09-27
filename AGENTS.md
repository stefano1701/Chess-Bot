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

Version: 0.15.1

Three strategies are implemented: `random`, `one_ply`, and `minimax`. The one-ply
strategy chooses the best immediate material result. Minimax searches to the
profile's fixed depth, maximizing on White's turns and minimizing on Black's. The
bundled minimax profiles now search to depth 4. Alpha-beta pruning removes
branches that cannot change the result, while promotions and captures are
searched first to improve pruning. Terminal mate and draw scores are respected
at any searched depth. Profiles may add named, editable static piece-square table
sets to material, with both an overall weight and six per-piece weights. There is
no pawn-structure or mobility evaluation, game-phase interpolation,
tactical/quiescence search, opening book, transposition table, clock management,
or online adapter yet.

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
- Headless round-robin tournaments for two to twelve player slots. Every pairing
  plays a configurable number of games in each colour, giving every entrant an
  exactly balanced White/Black schedule. Player slots remain separate when a
  profile is selected more than once; games between the same profile ID are
  unrated. Live and logged reports contain standings and colour splits; final
  reports also contain a player-by-player percentage score matrix.
- Interactive creation of material profiles with a configurable search depth.
- A table-set chooser, overall piece-square weight, and six per-piece weights when
  creating profiles. Zero keeps the original material-only evaluator.
- Per-move node and alpha-beta cutoff counts for minimax in human and spectator
  games.
- Persistent profile Elo ratings fitted in an order-independent batch from all
  saved head-to-head results after each tournament. Same-profile self-play is
  explicitly unrated.
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
  overrides, search depth, table set, and positional weights. Bundled examples
  include eleven material-only depth-4 profiles drawn from the historical value
  sets in the Chess Programming Wiki Point Value table. Coxeter's otherwise
  unspecified pawn is explicitly assumed to be 100.
- `piece-square-tables/*.toml`: named positional table sets. Every file contains
  all 384 editable square values and appears in the profile-creation chooser.
- `src/chess_bot/config.py`: loads, validates, and creates profiles.
- `src/chess_bot/engine.py`: constructs the selected engine implementation.
  Add future strategies here rather than branching in the terminal UI.
- `src/chess_bot/bot.py`: contains `RandomBot`, `OnePlyMaterialBot`, and the
  recursive fixed-depth `MinimaxBot`.
- `src/chess_bot/evaluation.py`: terminal-outcome, material, and static
  piece-square evaluation.
- `src/chess_bot/game.py`: move parsing, move history, and result formatting.
- `src/chess_bot/display.py`: Unicode and terminal-colour board rendering.
- `src/chess_bot/tournament.py`: headless game loop, alternating scheduling,
  result aggregation, profile/colour breakdowns, and Elo integration.
- `src/chess_bot/ratings.py`: regularized batch Elo fitting, cumulative matchup
  and lifetime profile records, JSON migration/validation, and atomic persistence.
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

`search.pruning.alpha_beta` enables exact alpha-beta pruning and defaults to
true. `search.move_ordering` accepts `captures` or `none`; `captures` searches
promotions and high-value captures first below the root. Root moves are shuffled
with the bot's seeded random generator, and the first best move is retained. This
keeps selection uniform among tied best moves while allowing bounds to be shared
between root moves. Disabling alpha-beta retains exhaustive minimax as a testing
and teaching baseline. Search statistics count visited nodes and cutoffs.

`evaluation.piece_square_tables.enabled` makes table sets available. Its
`directory` is resolved beside `engine.toml`, and `default_table_set` must match
the stem of a valid TOML file there. `evaluation.weights.piece_square_tables` is
the default overall profile weight and remains zero so existing material profiles
do not silently change. A profile may override the overall weight and table-set
ID under `[evaluation]`, plus any of the six defaults under
`[evaluation.piece_square_weights]`. All weights are non-negative floats.

Every table-set file must provide an 8×8 integer-centipawn matrix for each of
`pawn`, `knight`, `bishop`, `rook`, `queen`, and `king`. Matrices are rank 1 to 8,
with each row ordered file a to h. Black square values are looked up through
`chess.square_mirror()`. The built-in `four-ply-positional` profile selects the
`simplified` set with all weights at 1. The tables remain static and have no
opening/endgame interpolation.

`[tournament]` supplies the two-player default game count, round-robin defaults,
default seed, progress-bar width, and results log path. A seed of `-1` generates
a fresh non-negative seed; the selected seed is displayed and logged for replay.
Relative log paths resolve beside the selected `engine.toml`. The default
`tournament-results.txt` is deliberately gitignored. Tournament colour
alternation is mandatory. The original tournament tracks Player 1 and Player 2
separately, even when both use the same profile. A round robin accepts two to
twelve independently selected player slots. If its games-per-colour value is G,
each pair plays 2G games and each entrant plays G games as White and G as Black
against every opponent. Adjacent colour-swapped games reuse each player's
assigned random seed to reduce tie-breaking noise. Games run synchronously and
headlessly: no board is rendered, but progress and elapsed time are redrawn after
every game.

`[elo]` supplies the initial rating (1500 by default), batch prior standard
deviation (100 Elo), and local ratings JSON path. Ratings are keyed by stable
profile ID rather than display name. After a tournament, the standard Elo
logistic model is fitted simultaneously to all cumulative profile-vs-profile
results stored in `bot-ratings.json`; a Gaussian prior around the initial rating
keeps sparse or perfect records finite. The fit is independent of game and
pairing order. The JSON file is saved atomically and gitignored. Version-1 files
preserve lifetime W/D/L totals but reset their unconvertible sequential ratings
to the initial rating because they did not store opponent-level results.
Historical text reports are not backfilled. Same-profile self-play must remain
unrated because both competitors share one rating identity.

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
4. Static piece-square positional evaluation (current).
5. Alpha-beta pruning and basic move ordering (complete).
6. Quiescence search for tactical stability (next).
7. Further positional features: mobility, pawn structure, dynamic king safety,
   space, development, and endgame adjustments.
8. Iterative deepening, transposition tables, and time management.
9. Online-bot protocol adapter, resilience, and observability.

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
