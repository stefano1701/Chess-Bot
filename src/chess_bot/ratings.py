"""Persistent Elo ratings for bot profiles."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 1


class RatingError(ValueError):
    """Raised when a stored ratings file is invalid."""


@dataclass
class RatingRecord:
    rating: float
    games: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0

    def record(self, score: float) -> None:
        self.games += 1
        if score == 1.0:
            self.wins += 1
        elif score == 0.5:
            self.draws += 1
        else:
            self.losses += 1


@dataclass(frozen=True)
class EloUpdate:
    first_before: float
    first_after: float
    second_before: float
    second_after: float


class EloRatings:
    """A profile-keyed Elo table using the standard logistic expectation."""

    def __init__(
        self,
        path: Path,
        initial_rating: int = 1500,
        k_factor: int = 32,
        records: dict[str, RatingRecord] | None = None,
    ) -> None:
        if initial_rating <= 0:
            raise ValueError("Initial Elo rating must be positive.")
        if k_factor <= 0:
            raise ValueError("Elo K-factor must be positive.")
        self.path = path
        self.initial_rating = initial_rating
        self.k_factor = k_factor
        self.records = records or {}

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        initial_rating: int = 1500,
        k_factor: int = 32,
    ) -> EloRatings:
        if not path.exists():
            return cls(path, initial_rating, k_factor)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise RatingError(f"Could not read Elo ratings from {path}: {error}") from error

        if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
            raise RatingError(f"Unsupported Elo ratings format in {path}.")
        stored_records = data.get("ratings")
        if not isinstance(stored_records, dict):
            raise RatingError(f"Elo ratings in {path} must be an object.")

        records = {
            profile_id: _parse_record(profile_id, values, path)
            for profile_id, values in stored_records.items()
        }
        return cls(path, initial_rating, k_factor, records)

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

    def record_game(
        self,
        first_profile_id: str,
        second_profile_id: str,
        first_score: float,
    ) -> EloUpdate | None:
        """Rate one game; self-play is intentionally excluded."""
        if first_score not in {0.0, 0.5, 1.0}:
            raise ValueError("An Elo score must be 0, 0.5, or 1.")
        if first_profile_id == second_profile_id:
            return None

        first = self.record_for(first_profile_id)
        second = self.record_for(second_profile_id)
        first_before = first.rating
        second_before = second.rating
        expected_first = 1.0 / (
            1.0 + 10.0 ** ((second_before - first_before) / 400.0)
        )
        change = self.k_factor * (first_score - expected_first)
        first.rating += change
        second.rating -= change
        first.record(first_score)
        second.record(1.0 - first_score)
        return EloUpdate(
            first_before=first_before,
            first_after=first.rating,
            second_before=second_before,
            second_after=second.rating,
        )

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "schema_version": SCHEMA_VERSION,
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
        }
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(self.path)


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
