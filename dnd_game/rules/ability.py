"""Ability scores and modifiers per D&D 5e."""
from __future__ import annotations

ABILITIES: tuple[str, ...] = ("str", "dex", "con", "int", "wis", "cha")

ABILITY_NAMES_RU: dict[str, str] = {
    "str": "СИЛ",
    "dex": "ЛВК",
    "con": "ТЕЛ",
    "int": "ИНТ",
    "wis": "МДР",
    "cha": "ХАР",
}


def modifier(score: int) -> int:
    return (score - 10) // 2
