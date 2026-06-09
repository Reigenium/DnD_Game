"""Monster runtime entities, spawned from data/monsters.json."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path

from ..rules.ability import modifier
from ..rules.status import EnragedStatus, StaggeredStatus
from .combatant import Combatant

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


@dataclass
class MonsterAttack:
    name: str
    to_hit: int
    damage: str
    damage_type: str


@dataclass
class Monster(Combatant):
    # ── Identity ──────────────────────────────────────────────────────────
    id: str = ""
    name_ru: str = ""
    char: str = "?"
    color: tuple[int, int, int] = (255, 255, 255)

    # ── Stats ─────────────────────────────────────────────────────────────
    ac: int = 10
    str_: int = 10
    dex: int = 10
    con: int = 10
    int_: int = 10
    wis: int = 10
    cha: int = 10

    # ── Combat data ───────────────────────────────────────────────────────
    attacks: list[MonsterAttack] = field(default_factory=list)
    xp: int = 0
    cr: float = 0.0
    description: str = ""
    traits: list[str] = field(default_factory=list)

    # ── Damage type modifiers (Phase 2) ───────────────────────────────────
    resistances: list[str] = field(default_factory=list)    # half damage
    vulnerabilities: list[str] = field(default_factory=list)  # double damage
    immunities: list[str] = field(default_factory=list)     # no damage

    # ── Poise / Break (Phase 2) ───────────────────────────────────────────
    max_poise: int = 0   # 0 = no poise system for this monster
    poise: int = 0

    # ── Intent telegraph (Phase 2) ────────────────────────────────────────
    intent_pool: list[str] = field(default_factory=list)   # e.g. ["attack","heavy_attack"]
    current_intent: str = ""                               # chosen at round start

    # ── Loot ──────────────────────────────────────────────────────────────
    loot_table: list[dict] = field(default_factory=list)   # [{id, chance}]

    # ── Position ──────────────────────────────────────────────────────────
    x: int = 0
    y: int = 0

    # ── AI state ──────────────────────────────────────────────────────────
    alerted: bool = False   # True when monster noticed the player

    # ── Ability helper ────────────────────────────────────────────────────

    def mod(self, ability: str) -> int:
        return modifier({
            "str": self.str_, "dex": self.dex, "con": self.con,
            "int": self.int_, "wis": self.wis, "cha": self.cha,
        }[ability])

    # ── Backward-compat properties ────────────────────────────────────────

    @property
    def frozen_turns(self) -> int:
        s = self.get_status("frozen")
        return s.duration if s is not None else 0

    @frozen_turns.setter
    def frozen_turns(self, value: int) -> None:
        if value <= 0:
            self.remove_status("frozen")
        else:
            from ..rules.status import FrozenStatus
            existing = self.get_status("frozen")
            if existing is not None:
                existing.duration = value
            else:
                self.add_status(FrozenStatus(duration=value))

    @property
    def enraged(self) -> bool:
        return self.has_status("enraged")

    @enraged.setter
    def enraged(self, value: bool) -> None:
        if value:
            self.add_status(EnragedStatus(duration=-1))
        else:
            self.remove_status("enraged")

    # ── Damage resolution ─────────────────────────────────────────────────

    def take_damage(self, amount: int, damage_type: str = "physical") -> tuple[int, bool]:
        """Apply damage with resist/vuln/immunity resolution.

        Returns (damage_applied, newly_enraged).
        """
        if damage_type in self.immunities:
            return 0, False

        if damage_type in self.vulnerabilities:
            amount = amount * 2
        elif damage_type in self.resistances:
            amount = max(1, amount // 2)

        # Legacy undead_resist trait (replaced by data but kept for saves compat).
        if "undead_resist" in self.traits and damage_type in ("slashing", "piercing"):
            if damage_type not in self.resistances:  # don't double-apply
                amount = max(1, amount // 2)

        was_enraged = self.has_status("enraged")
        was_above_half = self.current_hp > self.max_hp // 2

        applied = super().take_damage(amount)

        newly_enraged = False
        if ("rage_at_half" in self.traits
                and not was_enraged
                and was_above_half
                and self.current_hp <= self.max_hp // 2
                and self.is_alive):
            self.add_status(EnragedStatus(duration=-1))
            newly_enraged = True

        # Poise damage from vulnerability hits.
        if self.max_poise > 0 and damage_type in self.vulnerabilities and self.poise > 0:
            self.poise -= 1
            if self.poise == 0:
                self.add_status(StaggeredStatus(duration=1))
                self.poise = self.max_poise  # reset for next break

        return applied, newly_enraged

    def choose_intent(self, rng) -> None:
        """Pick next intent from intent_pool (called at round start)."""
        if self.intent_pool:
            self.current_intent = rng.choice(self.intent_pool)
        else:
            self.current_intent = "attack"


# ── Data loading ─────────────────────────────────────────────────────────────

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
    poise_val = md.get("poise", 0)
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
        resistances=list(md.get("resistances", [])),
        vulnerabilities=list(md.get("vulnerabilities", [])),
        immunities=list(md.get("immunities", [])),
        max_poise=poise_val,
        poise=poise_val,
        intent_pool=list(md.get("intent_pool", ["attack"])),
        loot_table=list(md.get("loot_table", [])),
        x=x, y=y,
    )


def all_monster_ids() -> list[str]:
    return list(_load_data().keys())
