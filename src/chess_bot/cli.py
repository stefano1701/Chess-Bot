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
from chess_bot.engine import create_bot
from chess_bot.game import InvalidMoveError, move_history, parse_move, result_text


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


def profile_summary(profile: BotProfile) -> str:
    if profile.strategy == "random":
        return f"{profile.name} — random moves"

    values = profile.material
    return (
        f"{profile.name} — one ply; "
        f"P={values.pawn} N={values.knight} B={values.bishop} "
        f"R={values.rook} Q={values.queen}"
    )


def prompt_bot_profile(config: EngineConfig, heading: str) -> BotProfile | None:
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
            print(f"{index}. {profile_summary(profile)}{default_marker}")
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


def create_material_profile_interactively(config: EngineConfig) -> str | None:
    clear_screen()
    print(TITLE)
    print("\nCreate a one-ply material bot profile\n")
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
    profile_path = save_material_profile(config, name, material)
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
            status = f"{bot.name} played {notation}."

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
        status = f"{bot.name} played {notation}."

    draw_game(board, chess.WHITE, result_text(board))
    input("Press Enter to return to the menu…")


def main() -> None:
    try:
        config = load_engine_config()
    except ConfigError as error:
        print(f"Configuration error: {error}")
        return

    while True:
        clear_screen()
        print(TITLE)
        print("\nLearn chess programming one idea at a time.\n")
        print(f"Default: {profile_summary(config.default_profile)}")
        print("1. Play against a bot")
        print("2. Watch bot vs bot")
        print("3. Create a material bot profile")
        print("4. Quit")
        choice = input("\nChoose an option › ").strip().lower()

        try:
            if choice in {"1", "play", "p"}:
                profile = prompt_bot_profile(config, "Choose your opponent")
                if profile is not None:
                    play_human_vs_bot(prompt_human_color(), config, profile)
            elif choice in {"2", "watch", "w"}:
                white_profile = prompt_bot_profile(config, "Choose White's profile")
                if white_profile is None:
                    continue
                black_profile = prompt_bot_profile(config, "Choose Black's profile")
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
                    print(f"\nCreated: {profile_summary(config.get_profile(profile_id))}")
                    input("Press Enter to return to the menu…")
            elif choice in {"4", "quit", "q", "exit"}:
                print("Thanks for playing!")
                return
        except (KeyboardInterrupt, EOFError):
            print("\nReturning to the main menu…")
            time.sleep(0.7)


if __name__ == "__main__":
    main()
