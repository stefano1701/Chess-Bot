"""Persistent, order-independent batch Elo ratings for bot profiles."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1
_ELO_SCALE = math.log(10.0) / 400.0


class RatingError(ValueError):
    """Raised when a stored ratings file is invalid."""


@dataclass
class RatingRecord:
    rating: float
    games: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0

    def record(self, wins: int, draws: int, losses: int) -> None:
        self.games += wins + draws + losses
        self.wins += wins
        self.draws += draws
        self.losses += losses


@dataclass(frozen=True)
class MatchupResult:
    """Aggregated results from the first profile's perspective."""

    first_profile_id: str
    second_profile_id: str
    first_wins: int
    draws: int
    first_losses: int

    @property
    def games(self) -> int:
        return self.first_wins + self.draws + self.first_losses


@dataclass
class MatchupRecord:
    """Lifetime results for a canonical, alphabetically ordered profile pair."""

    first_wins: int = 0
    draws: int = 0
    first_losses: int = 0

    @property
    def games(self) -> int:
        return self.first_wins + self.draws + self.first_losses

    def add(self, first_wins: int, draws: int, first_losses: int) -> None:
        self.first_wins += first_wins
        self.draws += draws
        self.first_losses += first_losses


@dataclass(frozen=True)
class BatchEloUpdate:
    before_by_profile: dict[str, float]
    after_by_profile: dict[str, float]
    rated_games: int
    unrated_same_profile_games: int


class EloRatings:
    """Profile Elo fitted to all recorded head-to-head results as one batch."""

    def __init__(
        self,
        path: Path,
        initial_rating: int = 1500,
        prior_std_deviation: int = 100,
        records: dict[str, RatingRecord] | None = None,
        matchups: dict[tuple[str, str], MatchupRecord] | None = None,
        legacy_ratings_reset: bool = False,
    ) -> None:
        if initial_rating <= 0:
            raise ValueError("Initial Elo rating must be positive.")
        if prior_std_deviation <= 0:
            raise ValueError("Elo prior standard deviation must be positive.")
        self.path = path
        self.initial_rating = initial_rating
        self.prior_std_deviation = prior_std_deviation
        self.records = records if records is not None else {}
        self.matchups = matchups if matchups is not None else {}
        self.legacy_ratings_reset = legacy_ratings_reset

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        initial_rating: int = 1500,
        prior_std_deviation: int = 100,
    ) -> EloRatings:
        if not path.exists():
            return cls(path, initial_rating, prior_std_deviation)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RatingError(f"Could not read Elo ratings from {path}: {error}") from error

        if not isinstance(data, dict):
            raise RatingError(f"Unsupported Elo ratings format in {path}.")
        schema_version = data.get("schema_version")
        if schema_version not in {LEGACY_SCHEMA_VERSION, SCHEMA_VERSION}:
            raise RatingError(f"Unsupported Elo ratings format in {path}.")
        stored_records = data.get("ratings")
        if not isinstance(stored_records, dict):
            raise RatingError(f"Elo ratings in {path} must be an object.")

        records = {
            profile_id: _parse_record(profile_id, values, path)
            for profile_id, values in stored_records.items()
        }
        if schema_version == LEGACY_SCHEMA_VERSION:
            # Version 1 did not retain opponent results, so its sequential,
            # order-sensitive ratings cannot be converted to batch Elo. Preserve
            # lifetime W/D/L counts but restart the ratings from a neutral anchor.
            for record in records.values():
                record.rating = float(initial_rating)
            return cls(
                path,
                initial_rating,
                prior_std_deviation,
                records,
                legacy_ratings_reset=True,
            )

        stored_matchups = data.get("matchups")
        if not isinstance(stored_matchups, list):
            raise RatingError(f"Elo matchups in {path} must be a list.")
        matchups: dict[tuple[str, str], MatchupRecord] = {}
        for values in stored_matchups:
            first_id, second_id, matchup = _parse_matchup(values, path)
            key = (first_id, second_id)
            if key in matchups:
                raise RatingError(f"Duplicate Elo matchup {key!r} in {path}.")
            matchups[key] = matchup
        return cls(
            path,
            initial_rating,
            prior_std_deviation,
            records,
            matchups,
        )

    def record_for(self, profile_id: str) -> RatingRecord:
        return self.records.setdefault(
            profile_id,
            RatingRecord(float(self.initial_rating)),
        )

    def rating_for(self, profile_id: str) -> float:
        record = self.records.get(profile_id)
        return record.rating if record is not None else float(self.initial_rating)

    def games_for(self, profile_id: str) -> int:
        record = self.records.get(profile_id)
        return record.games if record is not None else 0

    def record_period(self, results: Iterable[MatchupResult]) -> BatchEloUpdate:
        """Record a complete rating period and refit Elo without game-order bias."""
        period_results = tuple(results)
        for result in period_results:
            _validate_matchup_result(result)
        affected_ids = {
            profile_id
            for result in period_results
            for profile_id in (result.first_profile_id, result.second_profile_id)
        }
        before = {
            profile_id: self.rating_for(profile_id) for profile_id in affected_ids
        }
        rated_games = 0
        unrated_same_profile_games = 0

        for result in period_results:
            if result.first_profile_id == result.second_profile_id:
                unrated_same_profile_games += result.games
                continue
            rated_games += result.games
            first_record = self.record_for(result.first_profile_id)
            second_record = self.record_for(result.second_profile_id)
            first_record.record(result.first_wins, result.draws, result.first_losses)
            second_record.record(result.first_losses, result.draws, result.first_wins)

            first_id, second_id, wins, losses = _canonical_result(result)
            matchup = self.matchups.setdefault((first_id, second_id), MatchupRecord())
            matchup.add(wins, result.draws, losses)

        if rated_games:
            self._recalculate_ratings()
        after = {
            profile_id: self.rating_for(profile_id) for profile_id in affected_ids
        }
        return BatchEloUpdate(
            before_by_profile=before,
            after_by_profile=after,
            rated_games=rated_games,
            unrated_same_profile_games=unrated_same_profile_games,
        )

    def _recalculate_ratings(self) -> None:
        """Fit regularized Bradley-Terry/Elo ratings with Newton iteration."""
        profile_ids = sorted(
            {
                profile_id
                for pairing in self.matchups
                for profile_id in pairing
            }
        )
        if not profile_ids:
            return
        indexes = {profile_id: index for index, profile_id in enumerate(profile_ids)}
        ratings = [float(self.initial_rating)] * len(profile_ids)
        prior_precision = 1.0 / self.prior_std_deviation**2

        for _ in range(100):
            gradient = [
                (rating - self.initial_rating) * prior_precision
                for rating in ratings
            ]
            hessian = [[0.0 for _ in profile_ids] for _ in profile_ids]
            for index in range(len(profile_ids)):
                hessian[index][index] = prior_precision

            for (first_id, second_id), matchup in self.matchups.items():
                first_index = indexes[first_id]
                second_index = indexes[second_id]
                expected_fraction = 1.0 / (
                    1.0
                    + 10.0
                    ** (
                        (ratings[second_index] - ratings[first_index]) / 400.0
                    )
                )
                actual_score = matchup.first_wins + matchup.draws / 2.0
                expected_score = matchup.games * expected_fraction
                residual = expected_score - actual_score
                gradient[first_index] += _ELO_SCALE * residual
                gradient[second_index] -= _ELO_SCALE * residual
                information = (
                    _ELO_SCALE**2
                    * matchup.games
                    * expected_fraction
                    * (1.0 - expected_fraction)
                )
                hessian[first_index][first_index] += information
                hessian[second_index][second_index] += information
                hessian[first_index][second_index] -= information
                hessian[second_index][first_index] -= information

            step = _solve_linear_system(hessian, [-value for value in gradient])
            largest_step = max(abs(value) for value in step)
            if largest_step > 200.0:
                scale = 200.0 / largest_step
                step = [value * scale for value in step]
                largest_step = 200.0
            ratings = [rating + change for rating, change in zip(ratings, step)]
            if largest_step < 1e-7:
                break
        else:  # pragma: no cover - defensive guard for unexpected numeric trouble.
            raise RatingError("Batch Elo calculation did not converge.")

        for profile_id, rating in zip(profile_ids, ratings):
            self.record_for(profile_id).rating = rating

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": SCHEMA_VERSION,
            "method": "regularized_batch_elo",
            "ratings": {
                profile_id: {
                    "rating": round(record.rating, 6),
                    "games": record.games,
                    "wins": record.wins,
                    "draws": record.draws,
                    "losses": record.losses,
                }
                for profile_id, record in sorted(self.records.items())
            },
            "matchups": [
                {
                    "first_profile_id": first_id,
                    "second_profile_id": second_id,
                    "first_wins": matchup.first_wins,
                    "draws": matchup.draws,
                    "first_losses": matchup.first_losses,
                }
                for (first_id, second_id), matchup in sorted(self.matchups.items())
            ],
        }
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(self.path)
        self.legacy_ratings_reset = False


def _canonical_result(result: MatchupResult) -> tuple[str, str, int, int]:
    if result.first_profile_id < result.second_profile_id:
        return (
            result.first_profile_id,
            result.second_profile_id,
            result.first_wins,
            result.first_losses,
        )
    return (
        result.second_profile_id,
        result.first_profile_id,
        result.first_losses,
        result.first_wins,
    )


def _validate_matchup_result(result: MatchupResult) -> None:
    if (
        not isinstance(result.first_profile_id, str)
        or not isinstance(result.second_profile_id, str)
        or not result.first_profile_id
        or not result.second_profile_id
    ):
        raise ValueError("Rated profile IDs cannot be empty.")
    counts = (result.first_wins, result.draws, result.first_losses)
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in counts
    ):
        raise ValueError("Matchup result counts must be non-negative integers.")
    if result.games <= 0:
        raise ValueError("A matchup result must contain at least one game.")


def _solve_linear_system(matrix: list[list[float]], values: list[float]) -> list[float]:
    """Solve a small dense system using partial-pivot Gaussian elimination."""
    size = len(values)
    augmented = [row[:] + [value] for row, value in zip(matrix, values)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-15:
            raise RatingError("Batch Elo calculation produced a singular system.")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        pivot_value = augmented[column][column]
        for entry in range(column, size + 1):
            augmented[column][entry] /= pivot_value
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            for entry in range(column, size + 1):
                augmented[row][entry] -= factor * augmented[column][entry]
    return [augmented[row][size] for row in range(size)]


def _parse_record(
    profile_id: str,
    values: Any,
    path: Path,
) -> RatingRecord:
    if not isinstance(profile_id, str) or not isinstance(values, dict):
        raise RatingError(f"Invalid Elo record in {path}.")
    rating = values.get("rating")
    counts = {key: values.get(key) for key in ("games", "wins", "draws", "losses")}
    if (
        isinstance(rating, bool)
        or not isinstance(rating, (int, float))
        or not math.isfinite(rating)
        or rating <= 0
    ):
        raise RatingError(f"Invalid rating for {profile_id!r} in {path}.")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in counts.values()
    ):
        raise RatingError(f"Invalid game counts for {profile_id!r} in {path}.")
    if counts["games"] != counts["wins"] + counts["draws"] + counts["losses"]:
        raise RatingError(f"Game counts do not add up for {profile_id!r} in {path}.")
    return RatingRecord(rating=float(rating), **counts)


def _parse_matchup(
    values: Any,
    path: Path,
) -> tuple[str, str, MatchupRecord]:
    if not isinstance(values, dict):
        raise RatingError(f"Invalid Elo matchup in {path}.")
    first_id = values.get("first_profile_id")
    second_id = values.get("second_profile_id")
    counts = {
        key: values.get(key) for key in ("first_wins", "draws", "first_losses")
    }
    if (
        not isinstance(first_id, str)
        or not isinstance(second_id, str)
        or not first_id
        or first_id >= second_id
    ):
        raise RatingError(f"Invalid canonical Elo matchup in {path}.")
    if any(
        isinstance(value, bool) or not isinstance(value, int) or value < 0
        for value in counts.values()
    ) or sum(counts.values()) <= 0:
        raise RatingError(f"Invalid Elo matchup counts in {path}.")
    return first_id, second_id, MatchupRecord(**counts)
