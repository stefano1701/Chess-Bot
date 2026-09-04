"""Load and validate the engine's TOML configuration."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised only on Python 3.10.
    import tomli as tomllib


CONFIG_ENVIRONMENT_VARIABLE = "CHESS_BOT_CONFIG"
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "engine.toml"
SUPPORTED_STRATEGIES = {"random"}


class ConfigError(ValueError):
    """Raised when the engine configuration is missing or unsupported."""


@dataclass(frozen=True)
class EngineConfig:
    """Validated active settings plus the complete future-facing config tree."""

    source: Path
    name: str
    strategy: str
    random_seed: int | None
    settings: dict[str, Any]


def load_engine_config(path: str | Path | None = None) -> EngineConfig:
    """Load the selected TOML file and validate currently active settings."""
    selected_path = _select_config_path(path)
    try:
        with selected_path.open("rb") as config_file:
            settings = tomllib.load(config_file)
    except FileNotFoundError as error:
        raise ConfigError(f"Engine config not found: {selected_path}") from error
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"Invalid TOML in {selected_path}: {error}") from error

    engine = settings.get("engine")
    if not isinstance(engine, dict):
        raise ConfigError("engine.toml must contain an [engine] section.")

    name = engine.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError("engine.name must be a non-empty string.")

    strategy = engine.get("strategy")
    if not isinstance(strategy, str) or strategy not in SUPPORTED_STRATEGIES:
        supported = ", ".join(sorted(SUPPORTED_STRATEGIES))
        raise ConfigError(
            f"Unsupported engine.strategy {strategy!r}; currently supported: {supported}."
        )

    configured_seed = engine.get("random_seed", -1)
    if isinstance(configured_seed, bool) or not isinstance(configured_seed, int):
        raise ConfigError("engine.random_seed must be -1 or a non-negative integer.")
    if configured_seed < -1:
        raise ConfigError("engine.random_seed must be -1 or a non-negative integer.")

    return EngineConfig(
        source=selected_path,
        name=name.strip(),
        strategy=strategy,
        random_seed=None if configured_seed == -1 else configured_seed,
        settings=settings,
    )


def _select_config_path(path: str | Path | None) -> Path:
    if path is not None:
        return Path(path).expanduser().resolve()

    environment_path = os.environ.get(CONFIG_ENVIRONMENT_VARIABLE)
    if environment_path:
        return Path(environment_path).expanduser().resolve()

    return DEFAULT_CONFIG_PATH
