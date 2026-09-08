"""Headless two-player and round-robin bot tournaments and their statistics."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
import math
from pathlib import Path
import random
import secrets
from time import perf_counter

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
        return 100.0 * self.score_fraction

    @property
    def score_fraction(self) -> float:
        if not self.games:
            return 0.0
        return (self.wins + self.draws / 2) / self.games

    @property
    def score_standard_error(self) -> float:
        if not self.games:
            return 0.0
        mean = self.score_fraction
        mean_square = (self.wins + self.draws / 4) / self.games
        variance = max(0.0, mean_square - mean * mean)
        return math.sqrt(variance / self.games)

    @property
    def score_confidence_interval(self) -> tuple[float, float]:
        margin = 1.96 * self.score_standard_error
        return (
            max(0.0, self.score_fraction - margin),
            min(1.0, self.score_fraction + margin),
        )


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
    seed: int
    games_completed: int = 0
    white_wins: int = 0
    black_wins: int = 0
    draws: int = 0
    total_plies: int = 0
    elapsed_seconds: float = 0.0
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

    @property
    def games_per_second(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return self.games_completed / self.elapsed_seconds

    @property
    def performance_elo_difference(self) -> float | None:
        score = self.profile_stats[0].overall.score_fraction
        if not self.games_completed:
            return None
        if score == 0.0:
            return -math.inf
        if score == 1.0:
            return math.inf
        return 400.0 * math.log10(score / (1.0 - score))

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


@dataclass
class RoundRobinEloStats:
    k_factor: int
    before_by_profile: dict[str, float]
    current_by_profile: dict[str, float]
    rated_games: int = 0
    unrated_same_profile_games: int = 0

    def record(
        self,
        first_profile_id: str,
        second_profile_id: str,
        update: EloUpdate | None,
    ) -> None:
        if update is None:
            self.unrated_same_profile_games += 1
            return
        self.current_by_profile[first_profile_id] = update.first_after
        self.current_by_profile[second_profile_id] = update.second_after
        self.rated_games += 1


@dataclass
class RoundRobinTournamentResult:
    games_per_colour: int
    profiles: tuple[BotProfile, ...]
    seed: int
    games_requested: int = field(init=False)
    games_completed: int = 0
    white_wins: int = 0
    black_wins: int = 0
    draws: int = 0
    total_plies: int = 0
    elapsed_seconds: float = 0.0
    terminations: Counter[str] = field(default_factory=Counter)
    profile_stats: tuple[ProfileTournamentStats, ...] = field(init=False)
    elo: RoundRobinEloStats | None = None

    def __post_init__(self) -> None:
        player_count = len(self.profiles)
        self.games_requested = (
            self.games_per_colour * player_count * (player_count - 1)
        )
        self.profile_stats = tuple(
            ProfileTournamentStats(profile) for profile in self.profiles
        )

    @property
    def average_plies(self) -> float:
        if not self.games_completed:
            return 0.0
        return self.total_plies / self.games_completed

    @property
    def games_per_second(self) -> float:
        if self.elapsed_seconds <= 0:
            return 0.0
        return self.games_completed / self.elapsed_seconds

    def record_game(
        self,
        white_player_index: int,
        black_player_index: int,
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

        self.profile_stats[white_player_index].record(chess.WHITE, game.winner)
        self.profile_stats[black_player_index].record(chess.BLACK, game.winner)

    def enable_elo(self, ratings: EloRatings) -> None:
        profile_ids = {profile.id for profile in self.profiles}
        before = {
            profile_id: ratings.rating_for(profile_id)
            for profile_id in profile_ids
        }
        self.elo = RoundRobinEloStats(
            k_factor=ratings.k_factor,
            before_by_profile=before,
            current_by_profile=dict(before),
        )


GameRunner = Callable[[ChessBot, ChessBot], CompletedGame]
ProgressCallback = Callable[[TournamentResult], None]
RoundRobinProgressCallback = Callable[[RoundRobinTournamentResult], None]
Clock = Callable[[], float]


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
    seed: int | None = None,
    clock: Clock = perf_counter,
) -> TournamentResult:
    """Run hidden games, swapping the two profiles' colours after every game."""
    if games <= 0:
        raise ValueError("Tournament games must be positive.")
    if seed is not None and (isinstance(seed, bool) or seed < 0):
        raise ValueError("Tournament seed must be non-negative.")
    first_white = config.get_profile(first_white_profile_id)
    first_black = config.get_profile(first_black_profile_id)
    selected_seed = secrets.randbits(63) if seed is None else seed
    result = TournamentResult(games, first_white, first_black, selected_seed)
    if ratings is not None:
        result.enable_elo(ratings)
    play_game = game_runner or _play_game
    seed_generator = random.Random(selected_seed)
    paired_player_seeds = [
        (seed_generator.getrandbits(63), seed_generator.getrandbits(63))
        for _ in range((games + 1) // 2)
    ]
    started_at = clock()
    if progress_callback is not None:
        progress_callback(result)

    for game_index in range(games):
        first_player_seed, second_player_seed = paired_player_seeds[game_index // 2]
        if game_index % 2 == 0:
            white_profile, black_profile = first_white, first_black
            white_seed, black_seed = first_player_seed, second_player_seed
        else:
            white_profile, black_profile = first_black, first_white
            white_seed, black_seed = second_player_seed, first_player_seed

        white_bot = create_bot(
            config,
            white_profile.id,
            rng_seed=white_seed,
        )
        black_bot = create_bot(
            config,
            black_profile.id,
            rng_seed=black_seed,
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
        result.elapsed_seconds = max(0.0, clock() - started_at)
        if progress_callback is not None:
            progress_callback(result)

    return result


def run_round_robin_tournament(
    config: EngineConfig,
    profile_ids: Sequence[str],
    games_per_colour: int,
    *,
    progress_callback: RoundRobinProgressCallback | None = None,
    game_runner: GameRunner | None = None,
    ratings: EloRatings | None = None,
    seed: int | None = None,
    clock: Clock = perf_counter,
) -> RoundRobinTournamentResult:
    """Run a complete double round-robin for two to eight player slots."""
    if not 2 <= len(profile_ids) <= 8:
        raise ValueError("A round-robin tournament requires 2 to 8 players.")
    if games_per_colour <= 0:
        raise ValueError("Games per colour must be positive.")
    if seed is not None and (isinstance(seed, bool) or seed < 0):
        raise ValueError("Tournament seed must be non-negative.")

    profiles = tuple(config.get_profile(profile_id) for profile_id in profile_ids)
    selected_seed = secrets.randbits(63) if seed is None else seed
    result = RoundRobinTournamentResult(
        games_per_colour,
        profiles,
        selected_seed,
    )
    if ratings is not None:
        result.enable_elo(ratings)
    play_game = game_runner or _play_game
    seed_generator = random.Random(selected_seed)
    started_at = clock()
    if progress_callback is not None:
        progress_callback(result)

    for _round_number in range(games_per_colour):
        for first_player_index in range(len(profiles) - 1):
            for second_player_index in range(first_player_index + 1, len(profiles)):
                first_seed = seed_generator.getrandbits(63)
                second_seed = seed_generator.getrandbits(63)
                _play_round_robin_pairing(
                    config,
                    result,
                    first_player_index,
                    second_player_index,
                    first_seed,
                    second_seed,
                    play_game,
                    ratings,
                    progress_callback,
                    clock,
                    started_at,
                )
                _play_round_robin_pairing(
                    config,
                    result,
                    second_player_index,
                    first_player_index,
                    second_seed,
                    first_seed,
                    play_game,
                    ratings,
                    progress_callback,
                    clock,
                    started_at,
                )

    return result


def _play_round_robin_pairing(
    config: EngineConfig,
    result: RoundRobinTournamentResult,
    white_player_index: int,
    black_player_index: int,
    white_seed: int,
    black_seed: int,
    play_game: GameRunner,
    ratings: EloRatings | None,
    progress_callback: RoundRobinProgressCallback | None,
    clock: Clock,
    started_at: float,
) -> None:
    white_profile = result.profiles[white_player_index]
    black_profile = result.profiles[black_player_index]
    white_bot = create_bot(
        config,
        white_profile.id,
        name=f"Player {white_player_index + 1} · {white_profile.name}",
        rng_seed=white_seed,
    )
    black_bot = create_bot(
        config,
        black_profile.id,
        name=f"Player {black_player_index + 1} · {black_profile.name}",
        rng_seed=black_seed,
    )
    completed_game = play_game(white_bot, black_bot)
    result.record_game(white_player_index, black_player_index, completed_game)
    if ratings is not None and result.elo is not None:
        white_score = _score_for_color(completed_game.winner, chess.WHITE)
        update = ratings.record_game(
            white_profile.id,
            black_profile.id,
            white_score,
        )
        result.elo.record(white_profile.id, black_profile.id, update)
    result.elapsed_seconds = max(0.0, clock() - started_at)
    if progress_callback is not None:
        progress_callback(result)


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
