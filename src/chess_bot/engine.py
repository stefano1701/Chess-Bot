"""Construct the engine selected by configuration."""

from __future__ import annotations

import random

from chess_bot.bot import RandomBot
from chess_bot.config import ConfigError, EngineConfig


def create_bot(
    config: EngineConfig,
    *,
    name: str | None = None,
    seed_offset: int = 0,
) -> RandomBot:
    """Build a configured bot behind the shared ``choose_move`` interface."""
    if config.strategy == "random":
        seed = None if config.random_seed is None else config.random_seed + seed_offset
        rng = None if seed is None else random.Random(seed)
        return RandomBot(name=name or config.name, rng=rng)

    raise ConfigError(f"No implementation exists for strategy {config.strategy!r}.")
