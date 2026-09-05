"""Headless, alternating-colour bot tournaments and their statistics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import chess

from chess_bot.config import BotProfile, EngineConfig
from chess_bot.engine import ChessBot, create_bot
from chess_bot.ratings import EloRatings, EloUpdate


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
class TournamentEloStats:
    k_factor: int
    self_play: bool
    first_before: float
    first_current: float
    second_before: float
    second_current: float
    rated_games: int = 0

    def record(self, update: EloUpdate | None) -> None:
        if update is None:
            return
        self.first_current = update.first_after
        self.second_current = update.second_after
        self.rated_games += 1


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
    profile_stats: tuple[ProfileTournamentStats, ProfileTournamentStats] = field(
        init=False
    )
    elo: TournamentEloStats | None = None

    def __post_init__(self) -> None:
        self.profile_stats = (
            ProfileTournamentStats(self.first_white),
            ProfileTournamentStats(self.first_black),
        )

    @property
    def average_plies(self) -> float:
        if not self.games_completed:
            return 0.0
        return self.total_plies / self.games_completed

    def record_game(self, game: CompletedGame) -> None:
        first_player_color = (
            chess.WHITE if self.games_completed % 2 == 0 else chess.BLACK
        )
        second_player_color = not first_player_color
        self.games_completed += 1
        self.total_plies += game.plies
        self.terminations[game.termination] += 1
        if game.winner is chess.WHITE:
            self.white_wins += 1
        elif game.winner is chess.BLACK:
            self.black_wins += 1
        else:
            self.draws += 1

        self.profile_stats[0].record(first_player_color, game.winner)
        self.profile_stats[1].record(second_player_color, game.winner)

    def enable_elo(self, ratings: EloRatings) -> None:
        first_rating = ratings.rating_for(self.first_white.id)
        second_rating = ratings.rating_for(self.first_black.id)
        self.elo = TournamentEloStats(
            k_factor=ratings.k_factor,
            self_play=self.first_white.id == self.first_black.id,
            first_before=first_rating,
            first_current=first_rating,
            second_before=second_rating,
            second_current=second_rating,
        )


GameRunner = Callable[[ChessBot, ChessBot], CompletedGame]
ProgressCallback = Callable[[TournamentResult], None]


def append_tournament_report(
    path: Path,
    report: str,
    *,
    completed_at: datetime | None = None,
) -> None:
    """Append one timestamped tournament report to a readable text log."""
    timestamp = completed_at or datetime.now().astimezone()
    path.parent.mkdir(parents=True, exist_ok=True)
    needs_separator = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8") as results_file:
        if needs_separator:
            results_file.write("\n")
        results_file.write("=" * 72 + "\n")
        results_file.write(
            f"Completed: {timestamp.isoformat(timespec='seconds')}\n\n"
        )
        results_file.write(report.rstrip() + "\n")


def run_tournament(
    config: EngineConfig,
    first_white_profile_id: str,
    first_black_profile_id: str,
    games: int,
    *,
    progress_callback: ProgressCallback | None = None,
    game_runner: GameRunner | None = None,
    ratings: EloRatings | None = None,
) -> TournamentResult:
    """Run hidden games, swapping the two profiles' colours after every game."""
    if games <= 0:
        raise ValueError("Tournament games must be positive.")
    first_white = config.get_profile(first_white_profile_id)
    first_black = config.get_profile(first_black_profile_id)
    result = TournamentResult(games, first_white, first_black)
    if ratings is not None:
        result.enable_elo(ratings)
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
        result.record_game(completed_game)
        if ratings is not None and result.elo is not None:
            first_player_color = chess.WHITE if game_index % 2 == 0 else chess.BLACK
            first_score = _score_for_color(completed_game.winner, first_player_color)
            update = ratings.record_game(
                first_white.id,
                first_black.id,
                first_score,
            )
            result.elo.record(update)
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


def _score_for_color(
    winner: chess.Color | None,
    color: chess.Color,
) -> float:
    if winner is None:
        return 0.5
    return 1.0 if winner == color else 0.0
