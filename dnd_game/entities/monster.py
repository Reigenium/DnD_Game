"""Monster runtime entities, spawned from data/monsters.json."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from ..rules.ability import modifier

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@dataclass
class MonsterAttack:
    name: str
    to_hit: int
    damage: str
    damage_type: str


@dataclass
class Monster:
    id: str
    name_ru: str
    char: str
    color: tuple[int, int, int]
    max_hp: int
    current_hp: int
    ac: int
    str_: int
    dex: int
    con: int
    int_: int
    wis: int
    cha: int
    attacks: list[MonsterAttack] = field(default_factory=list)
    xp: int = 0
    cr: float = 0.0
    description: str = ""
    traits: list[str] = field(default_factory=list)

    x: int = 0
    y: int = 0

    # Transient combat state.
    frozen_turns: int = 0
    enraged: bool = False

    def mod(self, ability: str) -> int:
        return modifier({
            "str": self.str_, "dex": self.dex, "con": self.con,
            "int": self.int_, "wis": self.wis, "cha": self.cha,
        }[ability])

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    def take_damage(self, amount: int) -> tuple[int, bool]:
        """Apply damage. Returns (actual, newly_enraged)."""
        amount = max(0, amount)
        was_above_half = self.current_hp > self.max_hp // 2
        was_enraged = self.enraged
        self.current_hp = max(0, self.current_hp - amount)
        newly_enraged = False
        if ("rage_at_half" in self.traits and not was_enraged
                and was_above_half
                and self.current_hp <= self.max_hp // 2
                and self.is_alive):
            self.enraged = True
            newly_enraged = True
        return amount, newly_enraged


_MONSTER_DATA: dict[str, dict] | None = None


def _load_data() -> dict[str, dict]:
    global _MONSTER_DATA
    if _MONSTER_DATA is None:
        with open(DATA_DIR / "monsters.json", encoding="utf-8") as f:
            _MONSTER_DATA = json.load(f)
    return _MONSTER_DATA


def spawn_monster(monster_id: str, x: int = 0, y: int = 0) -> Monster:
    data = _load_data()
    if monster_id not in data:
        raise KeyError(f"Unknown monster id: {monster_id!r}")
    md = deepcopy(data[monster_id])
    attacks = [MonsterAttack(**a) for a in md.get("attacks", [])]
    return Monster(
        id=monster_id,
        name_ru=md["name_ru"],
        char=md["char"],
        color=tuple(md["color"]),
        max_hp=md["max_hp"],
        current_hp=md["max_hp"],
        ac=md["ac"],
        str_=md["str"], dex=md["dex"], con=md["con"],
        int_=md["int"], wis=md["wis"], cha=md["cha"],
        attacks=attacks,
        xp=md.get("xp", 0),
        cr=md.get("cr", 0.0),
        description=md.get("description", ""),
        traits=list(md.get("traits", [])),
        x=x, y=y,
    )


def all_monster_ids() -> list[str]:
    return list(_load_data().keys())
