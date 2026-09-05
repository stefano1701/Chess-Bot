"""Headless, alternating-colour bot tournaments and their statistics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

import chess

from chess_bot.config import BotProfile, EngineConfig
from chess_bot.engine import ChessBot, create_bot


@dataclass(frozen=True)
class CompletedGame:
    winner: chess.Color | None
    termination: str
    plies: int


@dataclass
class ResultBreakdown:
    games: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0

    def record(self, profile_color: chess.Color, winner: chess.Color | None) -> None:
        self.games += 1
        if winner is None:
            self.draws += 1
        elif winner == profile_color:
            self.wins += 1
        else:
            self.losses += 1

    @property
    def win_percentage(self) -> float:
        return _percentage(self.wins, self.games)

    @property
    def draw_percentage(self) -> float:
        return _percentage(self.draws, self.games)

    @property
    def score_percentage(self) -> float:
        if not self.games:
            return 0.0
        return 100.0 * (self.wins + self.draws / 2) / self.games


@dataclass
class ProfileTournamentStats:
    profile: BotProfile
    overall: ResultBreakdown = field(default_factory=ResultBreakdown)
    as_white: ResultBreakdown = field(default_factory=ResultBreakdown)
    as_black: ResultBreakdown = field(default_factory=ResultBreakdown)

    def record(self, color: chess.Color, winner: chess.Color | None) -> None:
        self.overall.record(color, winner)
        color_breakdown = self.as_white if color is chess.WHITE else self.as_black
        color_breakdown.record(color, winner)


@dataclass
class TournamentResult:
    games_requested: int
    first_white: BotProfile
    first_black: BotProfile
    games_completed: int = 0
    white_wins: int = 0
    black_wins: int = 0
    draws: int = 0
    total_plies: int = 0
    terminations: Counter[str] = field(default_factory=Counter)
    profile_stats: dict[str, ProfileTournamentStats] = field(init=False)

    def __post_init__(self) -> None:
        self.profile_stats = {
            self.first_white.id: ProfileTournamentStats(self.first_white),
            self.first_black.id: ProfileTournamentStats(self.first_black),
        }

    @property
    def average_plies(self) -> float:
        if not self.games_completed:
            return 0.0
        return self.total_plies / self.games_completed

    def record_game(
        self,
        white_profile: BotProfile,
        black_profile: BotProfile,
        game: CompletedGame,
    ) -> None:
        self.games_completed += 1
        self.total_plies += game.plies
        self.terminations[game.termination] += 1
        if game.winner is chess.WHITE:
            self.white_wins += 1
        elif game.winner is chess.BLACK:
            self.black_wins += 1
        else:
            self.draws += 1

        self.profile_stats[white_profile.id].record(chess.WHITE, game.winner)
        self.profile_stats[black_profile.id].record(chess.BLACK, game.winner)


GameRunner = Callable[[ChessBot, ChessBot], CompletedGame]
ProgressCallback = Callable[[TournamentResult], None]


def run_tournament(
    config: EngineConfig,
    first_white_profile_id: str,
    first_black_profile_id: str,
    games: int,
    *,
    progress_callback: ProgressCallback | None = None,
    game_runner: GameRunner | None = None,
) -> TournamentResult:
    """Run hidden games, swapping the two profiles' colours after every game."""
    if games <= 0:
        raise ValueError("Tournament games must be positive.")
    if first_white_profile_id == first_black_profile_id:
        raise ValueError("Tournament profiles must be different.")

    first_white = config.get_profile(first_white_profile_id)
    first_black = config.get_profile(first_black_profile_id)
    result = TournamentResult(games, first_white, first_black)
    play_game = game_runner or _play_game
    if progress_callback is not None:
        progress_callback(result)

    for game_index in range(games):
        if game_index % 2 == 0:
            white_profile, black_profile = first_white, first_black
        else:
            white_profile, black_profile = first_black, first_white

        white_bot = create_bot(
            config,
            white_profile.id,
            seed_offset=game_index * 2,
        )
        black_bot = create_bot(
            config,
            black_profile.id,
            seed_offset=game_index * 2 + 1,
        )
        completed_game = play_game(white_bot, black_bot)
        result.record_game(white_profile, black_profile, completed_game)
        if progress_callback is not None:
            progress_callback(result)

    return result


def _play_game(white_bot: ChessBot, black_bot: ChessBot) -> CompletedGame:
    board = chess.Board()
    while not board.is_game_over(claim_draw=True):
        bot = white_bot if board.turn is chess.WHITE else black_bot
        move = bot.choose_move(board)
        board.push(move)

    outcome = board.outcome(claim_draw=True)
    if outcome is None:  # Defensive: the loop exits only for a finished game.
        raise RuntimeError("Tournament game ended without an outcome.")
    return CompletedGame(
        winner=outcome.winner,
        termination=outcome.termination.name.lower().replace("_", " "),
        plies=len(board.move_stack),
    )


def _percentage(amount: int, total: int) -> float:
    if not total:
        return 0.0
    return 100.0 * amount / total
