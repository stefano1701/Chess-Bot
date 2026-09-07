"""Construct the engine selected by a bot profile."""

from __future__ import annotations

import random
from typing import Protocol

import chess

from chess_bot.bot import MinimaxBot, OnePlyMaterialBot, RandomBot
from chess_bot.config import BotProfile, ConfigError, EngineConfig
from chess_bot.evaluation import MaterialEvaluator


class ChessBot(Protocol):
    name: str

    def choose_move(self, board: chess.Board) -> chess.Move:
        ...


def create_bot(
    config: EngineConfig,
    profile_id: str | None = None,
    *,
    name: str | None = None,
    seed_offset: int = 0,
    rng_seed: int | None = None,
) -> ChessBot:
    """Build a bot from a named profile or from the configured default."""
    profile = (
        config.default_profile
        if profile_id is None
        else config.get_profile(profile_id)
    )
    rng = (
        random.Random(rng_seed)
        if rng_seed is not None
        else _profile_rng(profile, seed_offset)
    )
    bot_name = name or profile.name
    piece_square_table_set = (
        config.get_piece_square_table_set(profile.piece_square_table_set_id)
        if profile.piece_square_weight > 0
        else None
    )

    if profile.strategy == "random":
        return RandomBot(name=bot_name, rng=rng)
    if profile.strategy == "one_ply":
        evaluator = MaterialEvaluator(
            profile.material,
            mate_score=config.mate_score,
            draw_score=config.draw_score,
            piece_square_weight=profile.piece_square_weight,
            piece_square_table_set=piece_square_table_set,
            piece_square_weights=profile.piece_square_weights,
        )
        return OnePlyMaterialBot(evaluator=evaluator, name=bot_name, rng=rng)
    if profile.strategy == "minimax":
        evaluator = MaterialEvaluator(
            profile.material,
            mate_score=config.mate_score,
            draw_score=config.draw_score,
            piece_square_weight=profile.piece_square_weight,
            piece_square_table_set=piece_square_table_set,
            piece_square_weights=profile.piece_square_weights,
        )
        return MinimaxBot(
            evaluator=evaluator,
            depth=profile.search_depth,
            name=bot_name,
            rng=rng,
        )

    raise ConfigError(f"No implementation exists for strategy {profile.strategy!r}.")


def _profile_rng(profile: BotProfile, seed_offset: int) -> random.Random | None:
    if profile.random_seed is None:
        return None
    return random.Random(profile.random_seed + seed_offset)
