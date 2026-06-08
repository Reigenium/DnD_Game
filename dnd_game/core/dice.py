"""Dice rolling primitives for D&D mechanics.

A ``Roll`` carries the full audit trail (individual dice, modifier, total)
so the UI layer can show players exactly what happened, JRPG-log style.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .rng import get_rng

_DICE_RE = re.compile(r"\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*", re.IGNORECASE)


@dataclass
class Roll:
    expression: str
    rolls: list[int] = field(default_factory=list)
    modifier: int = 0
    total: int = 0
    advantage: bool = False
    disadvantage: bool = False
    crit: bool = False
    fumble: bool = False

    def __str__(self) -> str:
        dice_part = "+".join(str(r) for r in self.rolls)
        mod_part = f"{self.modifier:+d}" if self.modifier else ""
        flag = ""
        if self.advantage:
            flag = " adv"
        elif self.disadvantage:
            flag = " dis"
        return f"[{dice_part}]{mod_part}{flag} = {self.total}"


def roll(expression: str) -> Roll:
    """Roll a standard dice expression like ``2d6+3`` or ``d20-1``."""
    match = _DICE_RE.fullmatch(expression)
    if not match:
        raise ValueError(f"Bad dice expression: {expression!r}")
    count = int(match.group(1) or "1")
    sides = int(match.group(2))
    mod_str = (match.group(3) or "0").replace(" ", "")
    modifier = int(mod_str)
    if count <= 0 or sides <= 0:
        raise ValueError(f"Bad dice expression: {expression!r}")
    rng = get_rng()
    rolls = [rng.randint(1, sides) for _ in range(count)]
    total = sum(rolls) + modifier
    return Roll(expression=expression, rolls=rolls, modifier=modifier, total=total)


def d20(modifier: int = 0, *, advantage: bool = False, disadvantage: bool = False) -> Roll:
    """A D&D-style d20 roll with optional (dis)advantage and crit/fumble flags."""
    rng = get_rng()
    if advantage and not disadvantage:
        a, b = rng.randint(1, 20), rng.randint(1, 20)
        rolls = [a, b]
        natural = max(a, b)
    elif disadvantage and not advantage:
        a, b = rng.randint(1, 20), rng.randint(1, 20)
        rolls = [a, b]
        natural = min(a, b)
    else:
        natural = rng.randint(1, 20)
        rolls = [natural]
    return Roll(
        expression="d20",
        rolls=rolls,
        modifier=modifier,
        total=natural + modifier,
        advantage=advantage and not disadvantage,
        disadvantage=disadvantage and not advantage,
        crit=(natural == 20),
        fumble=(natural == 1),
    )
