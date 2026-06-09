"""Targeting modes for combat actions."""
from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..entities.monster import Monster


class TargetMode(Enum):
    SINGLE = "single"        # current target only
    ALL_ENEMIES = "all"      # every alive enemy (AoE)
    CLEAVE = "cleave"        # primary target + first adjacent (overflow)
    LOWEST_HP = "lowest_hp"  # auto-target lowest HP enemy


def resolve_targets(mode: TargetMode, primary: "Monster | None",
                    alive_enemies: "list[Monster]") -> "list[Monster]":
    if not alive_enemies:
        return []

    if mode == TargetMode.SINGLE:
        return [primary] if primary is not None else []

    if mode == TargetMode.ALL_ENEMIES:
        return list(alive_enemies)

    if mode == TargetMode.CLEAVE:
        if primary is None:
            return list(alive_enemies[:2])
        others = [e for e in alive_enemies if e is not primary]
        return [primary] + others[:1]

    if mode == TargetMode.LOWEST_HP:
        return [min(alive_enemies, key=lambda e: e.current_hp)]

    return [primary] if primary is not None else []
