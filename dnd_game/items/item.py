"""Item dataclasses. Pure data — no logic beyond what's needed for equipping."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Weapon:
    id: str
    name_ru: str
    damage: str  # dice expression, e.g. "1d6"
    damage_type: str
    ability: str  # "str" or "dex" (primary)
    finesse: bool  # if True, may use higher of str/dex
    ranged: bool
    value: int


@dataclass
class Armor:
    id: str
    name_ru: str
    ac: int  # base AC (0 for shields)
    ac_bonus: int  # shield bonus
    dex_bonus: int  # cap on DEX mod applied (10 == unlimited)
    type: str  # "light" | "medium" | "heavy" | "shield"
    value: int


@dataclass
class Consumable:
    id: str
    name_ru: str
    effect: str  # "heal" (room to grow)
    amount: str  # dice expression
    value: int
