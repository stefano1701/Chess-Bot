"""Load, validate, and create engine profiles from TOML configuration."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
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
SUPPORTED_STRATEGIES = {"minimax", "one_ply", "random"}
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
class PieceSquareWeights:
    pawn: float = 1.0
    knight: float = 1.0
    bishop: float = 1.0
    rook: float = 1.0
    queen: float = 1.0
    king: float = 1.0

    def for_piece_type(self, piece_type: int) -> float:
        piece_names = {
            1: "pawn",
            2: "knight",
            3: "bishop",
            4: "rook",
            5: "queen",
            6: "king",
        }
        try:
            return getattr(self, piece_names[piece_type])
        except KeyError as error:
            raise ValueError(f"Unknown chess piece type: {piece_type}") from error

    def as_dict(self) -> dict[str, float]:
        return {piece: getattr(self, piece) for piece in MATERIAL_PIECES}


@dataclass(frozen=True)
class PieceSquareTableSet:
    id: str
    source: Path
    name: str
    description: str
    tables: dict[str, tuple[int, ...]]

    def for_piece_type(self, piece_type: int) -> tuple[int, ...]:
        piece_names = {
            1: "pawn",
            2: "knight",
            3: "bishop",
            4: "rook",
            5: "queen",
            6: "king",
        }
        try:
            return self.tables[piece_names[piece_type]]
        except KeyError as error:
            raise ValueError(f"Unknown chess piece type: {piece_type}") from error


@dataclass(frozen=True)
class BotProfile:
    id: str
    source: Path
    name: str
    strategy: str
    description: str
    random_seed: int | None
    material: MaterialValues
    piece_square_weight: float
    piece_square_table_set_id: str
    piece_square_weights: PieceSquareWeights
    search_depth: int


@dataclass(frozen=True)
class EngineConfig:
    source: Path
    profiles_directory: Path
    default_profile_id: str
    default_material: MaterialValues
    piece_square_tables_enabled: bool
    piece_square_tables_directory: Path
    default_piece_square_table_set_id: str
    default_piece_square_weight: float
    default_piece_square_weights: PieceSquareWeights
    piece_square_table_sets: dict[str, PieceSquareTableSet]
    mate_score: int
    draw_score: int
    search_max_depth: int
    search_alpha_beta: bool
    search_move_ordering: str
    elo_initial_rating: int
    elo_prior_std_deviation: int
    elo_ratings_file: Path
    tournament_default_games: int
    tournament_default_seed: int | None
    tournament_progress_bar_width: int
    tournament_results_file: Path
    round_robin_default_players: int
    round_robin_games_per_colour: int
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

    def get_piece_square_table_set(self, table_set_id: str) -> PieceSquareTableSet:
        try:
            return self.piece_square_table_sets[table_set_id]
        except KeyError as error:
            raise ConfigError(
                f"Unknown piece-square table set: {table_set_id!r}."
            ) from error


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
    evaluation_weights = evaluation.get("weights", {})
    if not isinstance(evaluation_weights, dict):
        raise ConfigError("evaluation.weights must be a table.")
    piece_square_settings = evaluation.get("piece_square_tables", {})
    if not isinstance(piece_square_settings, dict):
        raise ConfigError("evaluation.piece_square_tables must be a table.")
    piece_square_tables_enabled = _boolean(
        piece_square_settings,
        "enabled",
        "evaluation.piece_square_tables.enabled",
        default=False,
    )
    piece_square_tables_directory_name = piece_square_settings.get(
        "directory", "piece-square-tables"
    )
    if (
        not isinstance(piece_square_tables_directory_name, str)
        or not piece_square_tables_directory_name.strip()
    ):
        raise ConfigError(
            "evaluation.piece_square_tables.directory must be non-empty text."
        )
    piece_square_tables_directory = (
        selected_path.parent / piece_square_tables_directory_name.strip()
    ).resolve()
    default_piece_square_table_set_id = piece_square_settings.get(
        "default_table_set", "simplified"
    )
    if (
        not isinstance(default_piece_square_table_set_id, str)
        or not default_piece_square_table_set_id.strip()
    ):
        raise ConfigError(
            "evaluation.piece_square_tables.default_table_set must be non-empty text."
        )
    default_piece_square_table_set_id = default_piece_square_table_set_id.strip()
    interpolate_piece_square_tables = _boolean(
        piece_square_settings,
        "interpolate_by_phase",
        "evaluation.piece_square_tables.interpolate_by_phase",
        default=False,
    )
    if interpolate_piece_square_tables:
        raise ConfigError(
            "Piece-square game-phase interpolation is not implemented yet."
        )
    piece_square_weight_settings = evaluation.get("piece_square_weights", {})
    if not isinstance(piece_square_weight_settings, dict):
        raise ConfigError("evaluation.piece_square_weights must be a table.")
    default_piece_square_weights = _piece_square_weights(
        piece_square_weight_settings,
        None,
        "evaluation.piece_square_weights",
    )
    default_piece_square_weight = _non_negative_number(
        evaluation_weights,
        "piece_square_tables",
        "evaluation.weights.piece_square_tables",
        default=0.0,
    )
    if not piece_square_tables_enabled and default_piece_square_weight > 0:
        raise ConfigError(
            "evaluation.weights.piece_square_tables must be 0 when "
            "evaluation.piece_square_tables.enabled is false."
        )
    piece_square_table_sets = (
        _load_piece_square_table_sets(piece_square_tables_directory)
        if piece_square_tables_enabled
        else {}
    )
    if (
        piece_square_tables_enabled
        and default_piece_square_table_set_id not in piece_square_table_sets
    ):
        raise ConfigError(
            "evaluation.piece_square_tables.default_table_set does not match "
            f"a table file: {default_piece_square_table_set_id!r}."
        )
    mate_score = _non_negative_integer(
        evaluation, "mate_score", "evaluation.mate_score"
    )
    draw_score = _integer(evaluation, "draw_score", "evaluation.draw_score")
    search = settings.get("search", {})
    if not isinstance(search, dict):
        raise ConfigError("engine.search must be a table.")
    search_max_depth = _positive_integer(
        search, "max_depth", "search.max_depth", default=4
    )
    search_move_ordering = search.get("move_ordering", "captures")
    if search_move_ordering not in {"none", "captures"}:
        raise ConfigError("search.move_ordering must be 'none' or 'captures'.")
    pruning = search.get("pruning", {})
    if not isinstance(pruning, dict):
        raise ConfigError("search.pruning must be a table.")
    search_alpha_beta = _boolean(
        pruning,
        "alpha_beta",
        "search.pruning.alpha_beta",
        default=True,
    )
    elo = settings.get("elo", {})
    if not isinstance(elo, dict):
        raise ConfigError("engine.elo must be a table.")
    elo_initial_rating = _positive_integer(
        elo, "initial_rating", "elo.initial_rating", default=1500
    )
    elo_prior_std_deviation = _positive_integer(
        elo,
        "prior_std_deviation",
        "elo.prior_std_deviation",
        default=100,
    )
    elo_ratings_file_name = elo.get("ratings_file", "bot-ratings.json")
    if not isinstance(elo_ratings_file_name, str) or not elo_ratings_file_name.strip():
        raise ConfigError("elo.ratings_file must be a non-empty string.")
    elo_ratings_file = (
        selected_path.parent / elo_ratings_file_name.strip()
    ).resolve()
    tournament = settings.get("tournament")
    if not isinstance(tournament, dict):
        raise ConfigError("engine.toml must contain a [tournament] section.")
    tournament_default_games = _positive_integer(
        tournament, "default_games", "tournament.default_games"
    )
    configured_tournament_seed = _integer(
        tournament,
        "default_seed",
        "tournament.default_seed",
        default=-1,
    )
    if configured_tournament_seed < -1:
        raise ConfigError("tournament.default_seed must be -1 or non-negative.")
    tournament_default_seed = (
        None if configured_tournament_seed == -1 else configured_tournament_seed
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
    round_robin_default_players = _positive_integer(
        tournament,
        "round_robin_default_players",
        "tournament.round_robin_default_players",
        default=4,
    )
    if not 2 <= round_robin_default_players <= 12:
        raise ConfigError("tournament.round_robin_default_players must be 2 to 12.")
    round_robin_games_per_colour = _positive_integer(
        tournament,
        "round_robin_games_per_colour",
        "tournament.round_robin_games_per_colour",
        default=1,
    )
    if tournament.get("alternate_colors") is not True:
        raise ConfigError("tournament.alternate_colors must be true.")
    profiles = _load_profiles(
        profiles_directory,
        default_material,
        piece_square_tables_enabled,
        piece_square_table_sets,
        default_piece_square_table_set_id,
        default_piece_square_weight,
        default_piece_square_weights,
        search_max_depth,
    )

    if default_profile_id not in profiles:
        raise ConfigError(
            f"engine.default_profile {default_profile_id!r} does not match a profile."
        )

    return EngineConfig(
        source=selected_path,
        profiles_directory=profiles_directory,
        default_profile_id=default_profile_id,
        default_material=default_material,
        piece_square_tables_enabled=piece_square_tables_enabled,
        piece_square_tables_directory=piece_square_tables_directory,
        default_piece_square_table_set_id=default_piece_square_table_set_id,
        default_piece_square_weight=default_piece_square_weight,
        default_piece_square_weights=default_piece_square_weights,
        piece_square_table_sets=piece_square_table_sets,
        mate_score=mate_score,
        draw_score=draw_score,
        search_max_depth=search_max_depth,
        search_alpha_beta=search_alpha_beta,
        search_move_ordering=search_move_ordering,
        elo_initial_rating=elo_initial_rating,
        elo_prior_std_deviation=elo_prior_std_deviation,
        elo_ratings_file=elo_ratings_file,
        tournament_default_games=tournament_default_games,
        tournament_default_seed=tournament_default_seed,
        tournament_progress_bar_width=tournament_progress_bar_width,
        tournament_results_file=tournament_results_file,
        round_robin_default_players=round_robin_default_players,
        round_robin_games_per_colour=round_robin_games_per_colour,
        profiles=profiles,
        settings=settings,
    )


def save_material_profile(
    config: EngineConfig,
    name: str,
    material: MaterialValues,
    search_depth: int = 1,
    piece_square_weight: float = 0.0,
    piece_square_table_set_id: str | None = None,
    piece_square_weights: PieceSquareWeights | None = None,
) -> Path:
    """Create a uniquely named configurable search profile and return its path."""
    clean_name = name.strip()
    if not clean_name:
        raise ConfigError("Profile name cannot be empty.")
    if search_depth <= 0:
        raise ConfigError("Search depth must be positive.")
    if (
        isinstance(piece_square_weight, bool)
        or not isinstance(piece_square_weight, (int, float))
        or not math.isfinite(piece_square_weight)
        or piece_square_weight < 0
    ):
        raise ConfigError("Piece-square weight must be a non-negative number.")
    if piece_square_weight > 0 and not config.piece_square_tables_enabled:
        raise ConfigError("Piece-square tables are disabled in engine.toml.")
    selected_table_set_id = (
        config.default_piece_square_table_set_id
        if piece_square_table_set_id is None
        else piece_square_table_set_id.strip()
    )
    if not selected_table_set_id:
        raise ConfigError("Piece-square table set cannot be empty.")
    if (
        piece_square_weight > 0
        and selected_table_set_id not in config.piece_square_table_sets
    ):
        raise ConfigError(f"Unknown piece-square table set: {selected_table_set_id!r}.")
    selected_piece_weights = (
        config.default_piece_square_weights
        if piece_square_weights is None
        else piece_square_weights
    )
    _validate_piece_square_weights(selected_piece_weights)

    profile_id = _unique_profile_id(config.profiles_directory, clean_name)
    profile_path = config.profiles_directory / f"{profile_id}.toml"
    values = material.as_dict()
    strategy = "one_ply" if search_depth == 1 else "minimax"
    description = (
        "Custom one-ply material profile."
        if search_depth == 1
        else f"Custom depth-{search_depth} minimax material profile."
    )
    if piece_square_weight > 0:
        description = description.removesuffix(".") + " with positional tables."
    positional_values = selected_piece_weights.as_dict()
    contents = (
        "[profile]\n"
        f"name = {json.dumps(clean_name, ensure_ascii=False)}\n"
        f"strategy = {json.dumps(strategy)}\n"
        f"description = {json.dumps(description)}\n"
        "random_seed = -1\n\n"
        "[search]\n"
        f"depth = {search_depth}\n\n"
        "[evaluation]\n"
        f"piece_square_tables = {float(piece_square_weight)}\n"
        f"piece_square_table_set = {json.dumps(selected_table_set_id)}\n\n"
        "[evaluation.piece_square_weights]\n"
        + "".join(
            f"{piece} = {positional_values[piece]}\n"
            for piece in MATERIAL_PIECES
        )
        + "\n"
        "[material]\n"
        + "".join(f"{piece} = {values[piece]}\n" for piece in MATERIAL_PIECES)
    )
    config.profiles_directory.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(contents, encoding="utf-8")
    return profile_path


def _load_profiles(
    profiles_directory: Path,
    default_material: MaterialValues,
    piece_square_tables_enabled: bool,
    piece_square_table_sets: dict[str, PieceSquareTableSet],
    default_piece_square_table_set_id: str,
    default_piece_square_weight: float,
    default_piece_square_weights: PieceSquareWeights,
    default_search_depth: int,
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
        evaluation_overrides = data.get("evaluation", {})
        if not isinstance(evaluation_overrides, dict):
            raise ConfigError(f"{profile_id}.evaluation must be a table.")
        piece_square_weight = _non_negative_number(
            evaluation_overrides,
            "piece_square_tables",
            f"{profile_id}.evaluation.piece_square_tables",
            default=default_piece_square_weight,
        )
        piece_square_table_set_id = evaluation_overrides.get(
            "piece_square_table_set", default_piece_square_table_set_id
        )
        if (
            not isinstance(piece_square_table_set_id, str)
            or not piece_square_table_set_id.strip()
        ):
            raise ConfigError(
                f"{profile_id}.evaluation.piece_square_table_set must be "
                "non-empty text."
            )
        piece_square_table_set_id = piece_square_table_set_id.strip()
        piece_weight_overrides = evaluation_overrides.get(
            "piece_square_weights", {}
        )
        if not isinstance(piece_weight_overrides, dict):
            raise ConfigError(
                f"{profile_id}.evaluation.piece_square_weights must be a table."
            )
        piece_square_weights = _piece_square_weights(
            piece_weight_overrides,
            default_piece_square_weights,
            f"{profile_id}.evaluation.piece_square_weights",
        )
        if piece_square_weight > 0 and not piece_square_tables_enabled:
            raise ConfigError(
                f"{profile_id} enables piece-square tables, but "
                "evaluation.piece_square_tables.enabled is false."
            )
        if (
            piece_square_weight > 0
            and piece_square_table_set_id not in piece_square_table_sets
        ):
            raise ConfigError(
                f"{profile_id}.evaluation.piece_square_table_set does not match "
                f"a table file: {piece_square_table_set_id!r}."
            )
        search_overrides = data.get("search", {})
        if not isinstance(search_overrides, dict):
            raise ConfigError(f"{profile_id}.search must be a table.")
        search_depth = (
            _positive_integer(
                search_overrides,
                "depth",
                f"{profile_id}.search.depth",
                default=default_search_depth,
            )
            if strategy == "minimax"
            else 1
        )
        profiles[profile_id] = BotProfile(
            id=profile_id,
            source=profile_path,
            name=name,
            strategy=strategy,
            description=description.strip(),
            random_seed=None if configured_seed == -1 else configured_seed,
            material=material,
            piece_square_weight=piece_square_weight,
            piece_square_table_set_id=piece_square_table_set_id,
            piece_square_weights=piece_square_weights,
            search_depth=search_depth,
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


def _piece_square_weights(
    values: dict[str, Any],
    defaults: PieceSquareWeights | None,
    location: str,
) -> PieceSquareWeights:
    resolved: dict[str, float] = {}
    for piece in MATERIAL_PIECES:
        fallback = getattr(defaults, piece) if defaults is not None else 1.0
        resolved[piece] = _non_negative_number(
            values,
            piece,
            f"{location}.{piece}",
            default=fallback,
        )
    return PieceSquareWeights(**resolved)


def _validate_piece_square_weights(weights: PieceSquareWeights) -> None:
    for piece, value in weights.as_dict().items():
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            raise ConfigError(
                f"Piece-square {piece} weight must be a non-negative number."
            )


def _load_piece_square_table_sets(
    tables_directory: Path,
) -> dict[str, PieceSquareTableSet]:
    if not tables_directory.is_dir():
        raise ConfigError(
            f"Piece-square tables directory not found: {tables_directory}"
        )

    table_sets: dict[str, PieceSquareTableSet] = {}
    for table_path in sorted(tables_directory.glob("*.toml")):
        table_set_id = table_path.stem
        data = _load_toml(table_path, "Piece-square table set")
        metadata = data.get("meta", {})
        if not isinstance(metadata, dict):
            raise ConfigError(f"{table_path}.meta must be a table.")
        name = metadata.get("name", table_set_id)
        description = metadata.get("description", "")
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"{table_path}.meta.name must be non-empty text.")
        if not isinstance(description, str):
            raise ConfigError(f"{table_path}.meta.description must be text.")
        raw_tables = data.get("tables")
        if not isinstance(raw_tables, dict):
            raise ConfigError(f"{table_path} must contain a [tables] section.")
        tables = {
            piece: _piece_square_table(
                raw_tables.get(piece),
                f"{table_set_id}.tables.{piece}",
            )
            for piece in MATERIAL_PIECES
        }
        table_sets[table_set_id] = PieceSquareTableSet(
            id=table_set_id,
            source=table_path,
            name=name.strip(),
            description=description.strip(),
            tables=tables,
        )

    if not table_sets:
        raise ConfigError(f"No .toml table sets found in {tables_directory}.")
    return table_sets


def _piece_square_table(value: Any, location: str) -> tuple[int, ...]:
    if not isinstance(value, list) or len(value) != 8:
        raise ConfigError(f"{location} must contain eight ranks.")
    flattened: list[int] = []
    for rank_number, rank in enumerate(value, start=1):
        if not isinstance(rank, list) or len(rank) != 8:
            raise ConfigError(
                f"{location} rank {rank_number} must contain eight values."
            )
        for square_value in rank:
            if isinstance(square_value, bool) or not isinstance(square_value, int):
                raise ConfigError(f"{location} values must be whole centipawns.")
            flattened.append(square_value)
    return tuple(flattened)


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


def _boolean(
    values: dict[str, Any],
    key: str,
    location: str,
    default: bool,
) -> bool:
    value = values.get(key, default)
    if not isinstance(value, bool):
        raise ConfigError(f"{location} must be true or false.")
    return value


def _non_negative_number(
    values: dict[str, Any],
    key: str,
    location: str,
    default: float,
) -> float:
    value = values.get(key, default)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or value < 0
    ):
        raise ConfigError(f"{location} must be a non-negative number.")
    return float(value)


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
    default: int | None = None,
) -> int:
    value = _integer(values, key, location, default)
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
