"""Load, validate, and create engine profiles from TOML configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on Python 3.10.
    import tomli as tomllib


CONFIG_ENVIRONMENT_VARIABLE = "CHESS_BOT_CONFIG"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "engine.toml"
SUPPORTED_STRATEGIES = {"random", "one_ply"}
MATERIAL_PIECES = ("pawn", "knight", "bishop", "rook", "queen", "king")


class ConfigError(ValueError):
    """Raised when engine or profile configuration is invalid."""


@dataclass(frozen=True)
class MaterialValues:
    pawn: int
    knight: int
    bishop: int
    rook: int
    queen: int
    king: int = 0

    def for_piece_type(self, piece_type: int) -> int:
        values = {
            1: self.pawn,
            2: self.knight,
            3: self.bishop,
            4: self.rook,
            5: self.queen,
            6: self.king,
        }
        try:
            return values[piece_type]
        except KeyError as error:
            raise ValueError(f"Unknown chess piece type: {piece_type}") from error

    def as_dict(self) -> dict[str, int]:
        return {piece: getattr(self, piece) for piece in MATERIAL_PIECES}


@dataclass(frozen=True)
class BotProfile:
    id: str
    source: Path
    name: str
    strategy: str
    description: str
    random_seed: int | None
    material: MaterialValues


@dataclass(frozen=True)
class EngineConfig:
    source: Path
    profiles_directory: Path
    default_profile_id: str
    default_material: MaterialValues
    mate_score: int
    draw_score: int
    tournament_default_games: int
    tournament_progress_bar_width: int
    tournament_results_file: Path
    profiles: dict[str, BotProfile]
    settings: dict[str, Any]

    @property
    def default_profile(self) -> BotProfile:
        return self.profiles[self.default_profile_id]

    def get_profile(self, profile_id: str) -> BotProfile:
        try:
            return self.profiles[profile_id]
        except KeyError as error:
            raise ConfigError(f"Unknown bot profile: {profile_id!r}.") from error


def load_engine_config(path: str | Path | None = None) -> EngineConfig:
    """Load global engine settings and every profile in its profile directory."""
    selected_path = _select_config_path(path)
    settings = _load_toml(selected_path, "Engine config")

    engine = settings.get("engine")
    if not isinstance(engine, dict):
        raise ConfigError("engine.toml must contain an [engine] section.")

    default_profile_id = _required_text(
        engine, "default_profile", "engine.default_profile"
    )
    profiles_directory_name = _required_text(
        engine, "profiles_directory", "engine.profiles_directory"
    )
    profiles_directory = (selected_path.parent / profiles_directory_name).resolve()

    evaluation = settings.get("evaluation")
    if not isinstance(evaluation, dict):
        raise ConfigError("engine.toml must contain an [evaluation] section.")
    material_settings = evaluation.get("material")
    if not isinstance(material_settings, dict):
        raise ConfigError("engine.toml must contain [evaluation.material].")

    default_material = _material_values(material_settings, None, "evaluation.material")
    mate_score = _non_negative_integer(evaluation, "mate_score", "evaluation.mate_score")
    draw_score = _integer(evaluation, "draw_score", "evaluation.draw_score")
    tournament = settings.get("tournament")
    if not isinstance(tournament, dict):
        raise ConfigError("engine.toml must contain a [tournament] section.")
    tournament_default_games = _positive_integer(
        tournament, "default_games", "tournament.default_games"
    )
    tournament_progress_bar_width = _positive_integer(
        tournament, "progress_bar_width", "tournament.progress_bar_width"
    )
    tournament_results_file_name = _required_text(
        tournament, "results_file", "tournament.results_file"
    )
    tournament_results_file = (
        selected_path.parent / tournament_results_file_name
    ).resolve()
    if tournament.get("alternate_colors") is not True:
        raise ConfigError("tournament.alternate_colors must be true.")
    profiles = _load_profiles(profiles_directory, default_material)

    if default_profile_id not in profiles:
        raise ConfigError(
            f"engine.default_profile {default_profile_id!r} does not match a profile."
        )

    return EngineConfig(
        source=selected_path,
        profiles_directory=profiles_directory,
        default_profile_id=default_profile_id,
        default_material=default_material,
        mate_score=mate_score,
        draw_score=draw_score,
        tournament_default_games=tournament_default_games,
        tournament_progress_bar_width=tournament_progress_bar_width,
        tournament_results_file=tournament_results_file,
        profiles=profiles,
        settings=settings,
    )


def save_material_profile(
    config: EngineConfig,
    name: str,
    material: MaterialValues,
) -> Path:
    """Create a uniquely named one-ply material profile and return its path."""
    clean_name = name.strip()
    if not clean_name:
        raise ConfigError("Profile name cannot be empty.")

    profile_id = _unique_profile_id(config.profiles_directory, clean_name)
    profile_path = config.profiles_directory / f"{profile_id}.toml"
    values = material.as_dict()
    contents = (
        "[profile]\n"
        f"name = {json.dumps(clean_name, ensure_ascii=False)}\n"
        'strategy = "one_ply"\n'
        'description = "Custom one-ply material profile."\n'
        "random_seed = -1\n\n"
        "[material]\n"
        + "".join(f"{piece} = {values[piece]}\n" for piece in MATERIAL_PIECES)
    )
    config.profiles_directory.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(contents, encoding="utf-8")
    return profile_path


def _load_profiles(
    profiles_directory: Path,
    default_material: MaterialValues,
) -> dict[str, BotProfile]:
    if not profiles_directory.is_dir():
        raise ConfigError(f"Profiles directory not found: {profiles_directory}")

    profiles: dict[str, BotProfile] = {}
    for profile_path in sorted(profiles_directory.glob("*.toml")):
        profile_id = profile_path.stem
        data = _load_toml(profile_path, "Bot profile")
        profile_settings = data.get("profile")
        if not isinstance(profile_settings, dict):
            raise ConfigError(f"{profile_path} must contain a [profile] section.")

        name = _required_text(profile_settings, "name", f"{profile_id}.profile.name")
        strategy = _required_text(
            profile_settings, "strategy", f"{profile_id}.profile.strategy"
        )
        if strategy not in SUPPORTED_STRATEGIES:
            supported = ", ".join(sorted(SUPPORTED_STRATEGIES))
            raise ConfigError(
                f"Unsupported strategy {strategy!r} in {profile_path}; "
                f"currently supported: {supported}."
            )

        description = profile_settings.get("description", "")
        if not isinstance(description, str):
            raise ConfigError(f"{profile_id}.profile.description must be text.")
        configured_seed = _integer(
            profile_settings,
            "random_seed",
            f"{profile_id}.profile.random_seed",
            default=-1,
        )
        if configured_seed < -1:
            raise ConfigError(
                f"{profile_id}.profile.random_seed must be -1 or non-negative."
            )

        material_overrides = data.get("material")
        if material_overrides is not None and not isinstance(material_overrides, dict):
            raise ConfigError(f"{profile_id}.material must be a table.")
        material = _material_values(
            material_overrides or {}, default_material, f"{profile_id}.material"
        )
        profiles[profile_id] = BotProfile(
            id=profile_id,
            source=profile_path,
            name=name,
            strategy=strategy,
            description=description.strip(),
            random_seed=None if configured_seed == -1 else configured_seed,
            material=material,
        )

    if not profiles:
        raise ConfigError(f"No .toml bot profiles found in {profiles_directory}.")
    return profiles


def _material_values(
    values: dict[str, Any],
    defaults: MaterialValues | None,
    location: str,
) -> MaterialValues:
    resolved: dict[str, int] = {}
    for piece in MATERIAL_PIECES:
        fallback = getattr(defaults, piece) if defaults is not None else None
        resolved[piece] = _non_negative_integer(
            values, piece, f"{location}.{piece}", default=fallback
        )
    return MaterialValues(**resolved)


def _load_toml(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open("rb") as config_file:
            return tomllib.load(config_file)
    except FileNotFoundError as error:
        raise ConfigError(f"{label} not found: {path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"Invalid TOML in {path}: {error}") from error


def _required_text(values: dict[str, Any], key: str, location: str) -> str:
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{location} must be a non-empty string.")
    return value.strip()


def _integer(
    values: dict[str, Any],
    key: str,
    location: str,
    default: int | None = None,
) -> int:
    value = values.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{location} must be an integer.")
    return value


def _non_negative_integer(
    values: dict[str, Any],
    key: str,
    location: str,
    default: int | None = None,
) -> int:
    value = _integer(values, key, location, default)
    if value < 0:
        raise ConfigError(f"{location} must be non-negative.")
    return value


def _positive_integer(
    values: dict[str, Any],
    key: str,
    location: str,
) -> int:
    value = _integer(values, key, location)
    if value <= 0:
        raise ConfigError(f"{location} must be positive.")
    return value


def _unique_profile_id(profiles_directory: Path, name: str) -> str:
    base_id = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "profile"
    profile_id = base_id
    suffix = 2
    while (profiles_directory / f"{profile_id}.toml").exists():
        profile_id = f"{base_id}-{suffix}"
        suffix += 1
    return profile_id


def _select_config_path(path: str | Path | None) -> Path:
    if path is not None:
        return Path(path).expanduser().resolve()

    environment_path = os.environ.get(CONFIG_ENVIRONMENT_VARIABLE)
    if environment_path:
        return Path(environment_path).expanduser().resolve()

    return DEFAULT_CONFIG_PATH
