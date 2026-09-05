"""Interactive terminal interface for the chess bot."""

from __future__ import annotations

import random
import time

import chess

from chess_bot.config import (
    BotProfile,
    ConfigError,
    EngineConfig,
    MaterialValues,
    load_engine_config,
    save_material_profile,
)
from chess_bot.display import clear_screen, render_board
from chess_bot.engine import ChessBot, create_bot
from chess_bot.game import InvalidMoveError, move_history, parse_move, result_text
from chess_bot.ratings import EloRatings, RatingError
from chess_bot.tournament import (
    ResultBreakdown,
    TournamentResult,
    append_tournament_report,
    run_tournament,
)


TITLE = "♔  CHESS BOT  ♚"


def draw_game(
    board: chess.Board,
    orientation: chess.Color = chess.WHITE,
    status: str = "",
) -> None:
    clear_screen()
    print(TITLE)
    print()
    print(render_board(board, orientation))
    print()
    print(move_history(board))
    if board.is_check() and not board.is_game_over(claim_draw=True):
        print("Check!")
    if status:
        print(status)
    print()


def prompt_human_color() -> chess.Color:
    while True:
        answer = input("Play as [W]hite, [B]lack, or [R]andom? ").strip().lower()
        if answer in {"w", "white"}:
            return chess.WHITE
        if answer in {"b", "black"}:
            return chess.BLACK
        if answer in {"r", "random", ""}:
            return random.choice([chess.WHITE, chess.BLACK])
        print("Please enter W, B, or R.")


def prompt_spectator_delay() -> float | None:
    while True:
        answer = input(
            "Seconds between moves [0.5], or S for step-through mode: "
        ).strip().lower()
        if answer in {"s", "step"}:
            return None
        if answer == "":
            return 0.5
        try:
            delay = float(answer)
        except ValueError:
            print("Enter a non-negative number or S.")
            continue
        if delay >= 0:
            return delay
        print("The delay cannot be negative.")


def profile_summary(
    profile: BotProfile,
    ratings: EloRatings | None = None,
) -> str:
    if profile.strategy == "random":
        summary = f"{profile.name} — random moves"
    else:
        values = profile.material
        search = (
            "one ply"
            if profile.strategy == "one_ply"
            else f"minimax depth {profile.search_depth}"
        )
        summary = (
            f"{profile.name} — {search}; "
            f"P={values.pawn} N={values.knight} B={values.bishop} "
            f"R={values.rook} Q={values.queen}"
        )

    if ratings is not None:
        rating = ratings.rating_for(profile.id)
        games = ratings.games_for(profile.id)
        summary += f" | Elo {rating:.1f} ({games} rated games)"
    return summary


def prompt_bot_profile(
    config: EngineConfig,
    heading: str,
    ratings: EloRatings | None = None,
) -> BotProfile | None:
    default = config.default_profile
    others = sorted(
        (
            profile
            for profile in config.profiles.values()
            if profile.id != default.id
        ),
        key=lambda profile: profile.name.lower(),
    )
    profiles = [default, *others]

    while True:
        print(f"\n{heading}")
        for index, profile in enumerate(profiles, start=1):
            default_marker = " (default)" if profile.id == default.id else ""
            print(
                f"{index}. {profile_summary(profile, ratings)}{default_marker}"
            )
        answer = input("Choose a profile, or Q to cancel › ").strip().lower()
        if answer in {"q", "quit", "cancel"}:
            return None
        if answer == "":
            return default
        try:
            selected_index = int(answer) - 1
        except ValueError:
            print("Choose one of the listed profile numbers.")
            continue
        if 0 <= selected_index < len(profiles):
            return profiles[selected_index]
        print("Choose one of the listed profile numbers.")


def prompt_tournament_game_count(default: int) -> int | None:
    while True:
        answer = input(f"Number of games [{default}], or Q to cancel › ").strip().lower()
        if answer in {"q", "quit", "cancel"}:
            return None
        if answer == "":
            return default
        try:
            games = int(answer)
        except ValueError:
            print("Enter a positive whole number.")
            continue
        if games > 0:
            return games
        print("Enter a positive whole number.")


def format_tournament_progress(
    result: TournamentResult,
    progress_bar_width: int,
    *,
    final: bool = False,
) -> str:
    """Build the progress-only tournament screen (never a chess board)."""
    completed = result.games_completed
    requested = result.games_requested
    proportion = completed / requested
    filled = min(progress_bar_width, int(proportion * progress_bar_width))
    bar = "█" * filled + "░" * (progress_bar_width - filled)
    heading = "TOURNAMENT COMPLETE" if final else "BOT TOURNAMENT"
    lines = [
        f"━━━ {heading} ━━━",
        (
            f"Progress  [{bar}]  {completed}/{requested} "
            f"({proportion * 100:5.1f}%)"
        ),
        "",
        "Game-one colours",
        f"  ♙ White  Player 1 · {result.first_white.name}",
        f"  ♟ Black  Player 2 · {result.first_black.name}",
        "  ↻ Colours alternate after every game",
        _elo_status_text(result),
        "",
        "┌─ PROFILE RESULTS",
    ]

    for player_number, stats in enumerate(result.profile_stats, start=1):
        lines.extend(
            [
                (
                    f"│ Player {player_number} · {stats.profile.name}  "
                    f"[{stats.profile.id}]"
                ),
                f"│   {_profile_strategy_text(stats.profile)}",
            ]
        )
        elo_line = _profile_elo_line(result, player_number)
        if elo_line is not None:
            lines.append(elo_line)
        lines.extend(
            [
                _format_result_line("Overall", stats.overall),
                _format_result_line("♙ White", stats.as_white),
                _format_result_line("♟ Black", stats.as_black),
                "│",
            ]
        )
    lines[-1] = "└" + "─" * 70

    if final:
        lines.extend(
            [
                "",
                "┌─ TOURNAMENT TOTALS",
                (
                    f"│ White wins  {result.white_wins} "
                    f"({_percentage(result.white_wins, completed):.1f}%) | "
                    f"Black wins  {result.black_wins} "
                    f"({_percentage(result.black_wins, completed):.1f}%) | "
                    f"Draws  {result.draws} "
                    f"({_percentage(result.draws, completed):.1f}%)"
                ),
                f"│ Average length  {result.average_plies:.1f} half-moves",
            ]
        )
        if result.terminations:
            endings = ", ".join(
                f"{name}: {count}"
                for name, count in sorted(result.terminations.items())
            )
            lines.append(f"│ Endings  {endings}")
        if result.elo is not None:
            if result.elo.self_play:
                lines.append("│ Elo  Unchanged · same-profile self-play is unrated")
            else:
                first_delta = result.elo.first_current - result.elo.first_before
                second_delta = result.elo.second_current - result.elo.second_before
                lines.append(
                    f"│ Elo  Player 1 {result.elo.first_before:.1f} → "
                    f"{result.elo.first_current:.1f} ({first_delta:+.1f}) | "
                    f"Player 2 {result.elo.second_before:.1f} → "
                    f"{result.elo.second_current:.1f} ({second_delta:+.1f})"
                )
        lines.append("└" + "─" * 70)

    return "\n".join(lines)


def _format_result_line(label: str, results: ResultBreakdown) -> str:
    return (
        f"│   {label:<8} {results.games:>3} GP  │ "
        f"W {results.wins:>3}  D {results.draws:>3}  L {results.losses:>3}  │ "
        f"Win {results.win_percentage:5.1f}%  "
        f"Score {results.score_percentage:5.1f}%"
    )


def _profile_strategy_text(profile: BotProfile) -> str:
    if profile.strategy == "random":
        return "random legal moves"
    values = profile.material
    search = (
        "one ply"
        if profile.strategy == "one_ply"
        else f"minimax depth {profile.search_depth}"
    )
    return (
        f"{search} · P={values.pawn} N={values.knight} B={values.bishop} "
        f"R={values.rook} Q={values.queen}"
    )


def _elo_status_text(result: TournamentResult) -> str:
    if result.elo is None:
        return ""
    if result.elo.self_play:
        return "  Elo: unrated self-play (both players use the same profile)"
    return f"  Elo: rated tournament · K={result.elo.k_factor}"


def _profile_elo_line(
    result: TournamentResult,
    player_number: int,
) -> str | None:
    if result.elo is None:
        return None
    if player_number == 1:
        before = result.elo.first_before
        current = result.elo.first_current
    else:
        before = result.elo.second_before
        current = result.elo.second_current
    delta = current - before
    return f"│   Elo {current:.1f}  ({delta:+.1f} this tournament)"


def _percentage(amount: int, total: int) -> float:
    return 100.0 * amount / total if total else 0.0


def display_tournament_progress(
    result: TournamentResult,
    progress_bar_width: int,
    *,
    final: bool = False,
) -> None:
    clear_screen()
    print(TITLE)
    print()
    print(
        format_tournament_progress(
            result,
            progress_bar_width,
            final=final,
        )
    )


def run_bot_tournament_interactively(
    config: EngineConfig,
    ratings: EloRatings,
) -> None:
    clear_screen()
    print(TITLE)
    print("\nBot tournament setup")
    games = prompt_tournament_game_count(config.tournament_default_games)
    if games is None:
        return

    first_white = prompt_bot_profile(
        config,
        "Choose White for game 1",
        ratings,
    )
    if first_white is None:
        return
    first_black = prompt_bot_profile(
        config,
        "Choose Black for game 1",
        ratings,
    )
    if first_black is None:
        return

    result = run_tournament(
        config,
        first_white.id,
        first_black.id,
        games,
        ratings=ratings,
        progress_callback=lambda progress: display_tournament_progress(
            progress,
            config.tournament_progress_bar_width,
        ),
    )
    final_report = format_tournament_progress(
        result,
        config.tournament_progress_bar_width,
        final=True,
    )
    save_messages = [f"Results appended to {config.tournament_results_file}"]
    try:
        append_tournament_report(config.tournament_results_file, final_report)
    except OSError as error:
        save_messages[0] = f"Could not save results: {error}"
    if result.elo is not None and not result.elo.self_play:
        try:
            ratings.save()
            save_messages.append(f"Elo ratings saved to {ratings.path}")
        except OSError as error:
            save_messages.append(f"Could not save Elo ratings: {error}")
    else:
        save_messages.append("Elo unchanged because same-profile self-play is unrated")
    display_tournament_progress(
        result,
        config.tournament_progress_bar_width,
        final=True,
    )
    for message in save_messages:
        print(f"\n✎ {message}")
    input("\nPress Enter to return to the menu…")


def create_material_profile_interactively(config: EngineConfig) -> str | None:
    clear_screen()
    print(TITLE)
    print("\nCreate a material-search bot profile\n")
    name = input("Profile name (blank to cancel) › ").strip()
    if not name:
        return None

    defaults = config.default_material
    print("Enter whole-number centipawn values, or press Enter for the default.")
    material = MaterialValues(
        pawn=_prompt_piece_value("Pawn", defaults.pawn),
        knight=_prompt_piece_value("Knight", defaults.knight),
        bishop=_prompt_piece_value("Bishop", defaults.bishop),
        rook=_prompt_piece_value("Rook", defaults.rook),
        queen=_prompt_piece_value("Queen", defaults.queen),
        king=0,
    )
    print("A ply is one player's move. Depth 2 also examines the opponent's reply.")
    search_depth = _prompt_search_depth(config.search_max_depth)
    profile_path = save_material_profile(
        config,
        name,
        material,
        search_depth=search_depth,
    )
    return profile_path.stem


def _prompt_piece_value(piece_name: str, default: int) -> int:
    while True:
        answer = input(f"{piece_name} [{default}] › ").strip()
        if answer == "":
            return default
        try:
            value = int(answer)
        except ValueError:
            print("Enter a non-negative whole number.")
            continue
        if value >= 0:
            return value
        print("Enter a non-negative whole number.")


def _prompt_search_depth(default: int) -> int:
    while True:
        answer = input(f"Search depth in plies [{default}] › ").strip()
        if answer == "":
            return default
        try:
            depth = int(answer)
        except ValueError:
            print("Enter a positive whole number. Depth 4 and above may be slow.")
            continue
        if depth > 0:
            return depth
        print("Enter a positive whole number. Depth 4 and above may be slow.")


def _bot_move_status(bot: ChessBot, notation: str) -> str:
    status = f"{bot.name} played {notation}."
    search_stats = getattr(bot, "last_search_stats", None)
    if search_stats is not None:
        status += (
            f" Searched {search_stats.nodes:,} positions "
            f"to depth {search_stats.depth}."
        )
    return status


def print_help() -> None:
    print(
        "\nMove formats:\n"
        "  Algebraic: e4, Nf3, Qh5, Bxe6, O-O, e8=Q\n"
        "  Coordinates also work: e2e4, g1f3, d1h5, e7e8q\n\n"
        "Commands:\n"
        "  moves   list every legal move\n"
        "  board   redraw the board\n"
        "  resign  concede this game\n"
        "  quit    return to the main menu\n"
        "  help    show this message\n"
    )


def prompt_human_move(board: chess.Board) -> chess.Move | str:
    """Prompt until a move or an in-game command is supplied."""
    while True:
        answer = input("Your move (e.g. e4 or Qh5) › ").strip()
        command = answer.lower()

        if command in {"quit", "q", "exit"}:
            return "quit"
        if command in {"resign", "r"}:
            return "resign"
        if command in {"help", "h", "?"}:
            print_help()
            continue
        if command in {"board", "b"}:
            return "redraw"
        if command in {"moves", "legal"}:
            legal_moves = sorted(board.san(move) for move in board.legal_moves)
            print("Legal moves: " + ", ".join(legal_moves))
            continue

        try:
            return parse_move(board, answer)
        except InvalidMoveError as error:
            print(error)


def play_human_vs_bot(
    human_color: chess.Color,
    config: EngineConfig,
    profile: BotProfile,
) -> None:
    board = chess.Board()
    bot = create_bot(config, profile.id)
    color_name = "White" if human_color is chess.WHITE else "Black"
    status = f"You are {color_name}. Opponent: {profile.name}."

    while not board.is_game_over(claim_draw=True):
        draw_game(board, human_color, status)

        if board.turn == human_color:
            action = prompt_human_move(board)
            if action == "quit":
                return
            if action == "resign":
                winner = "Black" if human_color is chess.WHITE else "White"
                print(f"You resigned. {winner} wins.")
                input("Press Enter to return to the menu…")
                return
            if action == "redraw":
                status = "Board redrawn."
                continue
            move = action
            assert isinstance(move, chess.Move)
            notation = board.san(move)
            board.push(move)
            status = f"You played {notation}."
        else:
            move = bot.choose_move(board)
            notation = board.san(move)
            board.push(move)
            status = _bot_move_status(bot, notation)

    draw_game(board, human_color, result_text(board))
    input("Press Enter to return to the menu…")


def watch_bot_match(
    delay: float | None,
    config: EngineConfig,
    white_profile: BotProfile,
    black_profile: BotProfile,
) -> None:
    board = chess.Board()
    white = create_bot(config, white_profile.id, name=white_profile.name)
    black = create_bot(
        config,
        black_profile.id,
        name=black_profile.name,
        seed_offset=1,
    )
    status = f"White: {white_profile.name}  |  Black: {black_profile.name}"

    while not board.is_game_over(claim_draw=True):
        draw_game(board, chess.WHITE, status)
        bot = white if board.turn is chess.WHITE else black
        if delay is None:
            input(f"Press Enter for {bot.name}'s move…")
        elif delay:
            time.sleep(delay)

        move = bot.choose_move(board)
        notation = board.san(move)
        board.push(move)
        status = _bot_move_status(bot, notation)

    draw_game(board, chess.WHITE, result_text(board))
    input("Press Enter to return to the menu…")


def main() -> None:
    try:
        config = load_engine_config()
        ratings = EloRatings.load(
            config.elo_ratings_file,
            initial_rating=config.elo_initial_rating,
            k_factor=config.elo_k_factor,
        )
    except (ConfigError, RatingError) as error:
        print(f"Configuration error: {error}")
        return

    while True:
        clear_screen()
        print(TITLE)
        print("\nLearn chess programming one idea at a time.\n")
        print(f"Default: {profile_summary(config.default_profile, ratings)}")
        print("1. Play against a bot")
        print("2. Watch bot vs bot")
        print("3. Create a material-search bot profile")
        print("4. Run a bot tournament")
        print("5. Quit")
        choice = input("\nChoose an option › ").strip().lower()

        try:
            if choice in {"1", "play", "p"}:
                profile = prompt_bot_profile(
                    config,
                    "Choose your opponent",
                    ratings,
                )
                if profile is not None:
                    play_human_vs_bot(prompt_human_color(), config, profile)
            elif choice in {"2", "watch", "w"}:
                white_profile = prompt_bot_profile(
                    config,
                    "Choose White's profile",
                    ratings,
                )
                if white_profile is None:
                    continue
                black_profile = prompt_bot_profile(
                    config,
                    "Choose Black's profile",
                    ratings,
                )
                if black_profile is not None:
                    watch_bot_match(
                        prompt_spectator_delay(),
                        config,
                        white_profile,
                        black_profile,
                    )
            elif choice in {"3", "create", "c"}:
                profile_id = create_material_profile_interactively(config)
                if profile_id is not None:
                    config = load_engine_config(config.source)
                    print(
                        "\nCreated: "
                        + profile_summary(config.get_profile(profile_id), ratings)
                    )
                    input("Press Enter to return to the menu…")
            elif choice in {"4", "tournament", "t"}:
                run_bot_tournament_interactively(config, ratings)
            elif choice in {"5", "quit", "q", "exit"}:
                print("Thanks for playing!")
                return
        except (KeyboardInterrupt, EOFError):
            print("\nReturning to the main menu…")
            time.sleep(0.7)


if __name__ == "__main__":
    main()
