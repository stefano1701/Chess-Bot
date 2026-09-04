"""Interactive terminal interface for the chess bot."""

from __future__ import annotations

import random
import time

import chess

from chess_bot.bot import RandomBot
from chess_bot.display import clear_screen, render_board
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


def print_help() -> None:
    print(
        "\nMove format:\n"
        "  Enter the start and end squares: e2e4 or g1f3\n"
        "  Castle by moving the king: e1g1 or e1c1\n"
        "  Add a promotion piece at the end: e7e8q\n\n"
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
        answer = input("Your move (e.g. e2e4) › ").strip()
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
            legal_moves = sorted(move.uci() for move in board.legal_moves)
            print("Legal moves: " + ", ".join(legal_moves))
            continue

        try:
            return parse_move(board, answer)
        except InvalidMoveError as error:
            print(error)


def play_human_vs_bot(human_color: chess.Color) -> None:
    board = chess.Board()
    bot = RandomBot()
    color_name = "White" if human_color is chess.WHITE else "Black"
    status = f"You are {color_name}."

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
            notation = move.uci()
            board.push(move)
            status = f"You played {notation}."
        else:
            move = bot.choose_move(board)
            notation = move.uci()
            board.push(move)
            status = f"{bot.name} played {notation}."

    draw_game(board, human_color, result_text(board))
    input("Press Enter to return to the menu…")


def watch_bot_match(delay: float | None) -> None:
    board = chess.Board()
    white = RandomBot("White Bot")
    black = RandomBot("Black Bot")
    status = "Random bot vs random bot"

    while not board.is_game_over(claim_draw=True):
        draw_game(board, chess.WHITE, status)
        bot = white if board.turn is chess.WHITE else black
        if delay is None:
            input(f"Press Enter for {bot.name}'s move…")
        elif delay:
            time.sleep(delay)

        move = bot.choose_move(board)
        notation = move.uci()
        board.push(move)
        status = f"{bot.name} played {notation}."

    draw_game(board, chess.WHITE, result_text(board))
    input("Press Enter to return to the menu…")


def main() -> None:
    while True:
        clear_screen()
        print(TITLE)
        print("\nLearn chess programming one idea at a time.\n")
        print("1. Play against the random bot")
        print("2. Watch random bot vs random bot")
        print("3. Quit")
        choice = input("\nChoose an option › ").strip().lower()

        try:
            if choice in {"1", "play", "p"}:
                play_human_vs_bot(prompt_human_color())
            elif choice in {"2", "watch", "w"}:
                watch_bot_match(prompt_spectator_delay())
            elif choice in {"3", "quit", "q", "exit"}:
                print("Thanks for playing!")
                return
        except (KeyboardInterrupt, EOFError):
            print("\nReturning to the main menu…")
            time.sleep(0.7)


if __name__ == "__main__":
    main()
