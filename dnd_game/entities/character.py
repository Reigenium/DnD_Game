"""Player character — inherits Combatant for hp/statuses/resources."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..items.item import Armor, Consumable, Weapon
from ..rules.ability import modifier
from ..rules.status import (
    ActionSurgeUsedStatus, BlessedStatus, DodgingStatus, RiposteStatus,
    ShieldedStatus,
)
from .combatant import Combatant


@dataclass
class Inventory:
    weapons: list[Weapon] = field(default_factory=list)
    armors: list[Armor] = field(default_factory=list)
    consumables: list[Consumable] = field(default_factory=list)
    gold: int = 0


@dataclass
class Character(Combatant):
    # ── Identity ──────────────────────────────────────────────────────────
    name: str = "Боргх"
    char_class: str = "fighter"
    level: int = 1

    # ── Ability scores ────────────────────────────────────────────────────
    str_: int = 16
    dex: int = 12
    con: int = 14
    int_: int = 10
    wis: int = 12
    cha: int = 8

    # ── Progression ───────────────────────────────────────────────────────
    proficiency_bonus: int = 2
    xp: int = 0
    xp_to_next: int = 300

    # ── Equipment ─────────────────────────────────────────────────────────
    equipped_weapon: Weapon | None = None
    equipped_armor: Armor | None = None
    equipped_shield: Armor | None = None
    inventory: Inventory = field(default_factory=Inventory)

    # ── Position ──────────────────────────────────────────────────────────
    x: int = 0
    y: int = 0

    # ── Progression unlocks (set as player levels up) ─────────────────────
    maneuvers: list[str] = field(default_factory=list)
    battle_style: str = "defense"  # defense | dueling | archery | great_weapon

    # ── Ability helpers ───────────────────────────────────────────────────

    def mod(self, ability: str) -> int:
        return modifier(self._score(ability))

    def _score(self, ability: str) -> int:
        return {
            "str": self.str_, "dex": self.dex, "con": self.con,
            "int": self.int_, "wis": self.wis, "cha": self.cha,
        }[ability]

    @property
    def ability_scores(self) -> dict[str, int]:
        return {
            "str": self.str_, "dex": self.dex, "con": self.con,
            "int": self.int_, "wis": self.wis, "cha": self.cha,
        }

    # ── Derived combat stats ──────────────────────────────────────────────

    @property
    def ac(self) -> int:
        if self.equipped_armor is not None:
            base = self.equipped_armor.ac
            dex_cap = self.equipped_armor.dex_bonus
            total = base + min(self.mod("dex"), dex_cap)
        else:
            total = 10 + self.mod("dex")
        if self.equipped_shield is not None:
            total += self.equipped_shield.ac_bonus
        return total

    def _attack_ability(self) -> str:
        w = self.equipped_weapon
        if w is None:
            return "str"
        if w.finesse:
            return "dex" if self.mod("dex") > self.mod("str") else "str"
        return w.ability

    @property
    def attack_bonus(self) -> int:
        return self.proficiency_bonus + self.mod(self._attack_ability())

    @property
    def damage_bonus(self) -> int:
        return self.mod(self._attack_ability())

    @property
    def damage_expression(self) -> str:
        return self.equipped_weapon.damage if self.equipped_weapon else "1d4"

    @property
    def damage_type(self) -> str:
        return self.equipped_weapon.damage_type if self.equipped_weapon else "bludgeoning"

    @property
    def spell_attack_bonus(self) -> int:
        return self.proficiency_bonus + self.mod("int")

    # ── Focus resource ────────────────────────────────────────────────────

    @property
    def focus_max(self) -> int:
        return 3 + self.level // 2

    @property
    def focus(self) -> int:
        return self.get_resource("focus")

    @focus.setter
    def focus(self, value: int) -> None:
        self.set_resource("focus", max(0, min(self.focus_max, value)))

    def gain_focus(self, amount: int) -> int:
        return self.mod_resource("focus", amount, max_val=self.focus_max)

    def spend_focus(self, amount: int) -> bool:
        if self.focus < amount:
            return False
        self.mod_resource("focus", -amount)
        return True

    # ── Backward-compat status properties ─────────────────────────────────
    # Old code that reads/writes these plain attributes continues to work.

    @property
    def dodge_active(self) -> bool:
        return self.has_status("dodging")

    @dodge_active.setter
    def dodge_active(self, value: bool) -> None:
        if value:
            self.add_status(DodgingStatus(duration=1))
        else:
            self.remove_status("dodging")

    @property
    def shield_active(self) -> bool:
        return self.has_status("shielded")

    @shield_active.setter
    def shield_active(self, value: bool) -> None:
        if value:
            self.add_status(ShieldedStatus(duration=-1))
        else:
            self.remove_status("shielded")

    @property
    def blessed_turns(self) -> int:
        s = self.get_status("blessed")
        return s.duration if s is not None else 0

    @blessed_turns.setter
    def blessed_turns(self, value: int) -> None:
        if value <= 0:
            self.remove_status("blessed")
        else:
            existing = self.get_status("blessed")
            if existing is not None:
                existing.duration = value
            else:
                self.add_status(BlessedStatus(duration=value))

    @property
    def second_wind_used(self) -> bool:
        return bool(self.get_resource("second_wind_used"))

    @second_wind_used.setter
    def second_wind_used(self, value: bool) -> None:
        self.set_resource("second_wind_used", int(value))

    @property
    def riposte_active(self) -> bool:
        return self.has_status("riposte")

    # ── Extra Attack (level 5 Fighter) ────────────────────────────────────

    @property
    def attacks_per_action(self) -> int:
        return 2 if self.level >= 5 else 1

    # ── Progression ───────────────────────────────────────────────────────

    def gain_xp(self, amount: int) -> bool:
        if amount <= 0:
            return False
        self.xp += amount
        leveled = False
        while self.xp >= self.xp_to_next:
            self.level_up()
            leveled = True
        return leveled

    def level_up(self) -> None:
        self.level += 1
        gain = 6 + self.mod("con")
        self.max_hp += max(1, gain)
        self.current_hp = self.max_hp
        self.xp_to_next = int(self.xp_to_next * 1.5)
        if self.level >= 5:
            self.proficiency_bonus = 3

    # ── Character sheet metadata ──────────────────────────────────────────

    @property
    def proficiencies_ru(self) -> list[str]:
        if self.char_class == "fighter":
            return [
                "Простое оружие",
                "Воинское оружие",
                "Лёгкие, средние, тяжёлые доспехи",
                "Щиты",
                "Спасброски: СИЛ, ТЕЛ",
            ]
        return []

    @property
    def class_features_ru(self) -> list[str]:
        feats = [
            "Боевой стиль: " + {
                "defense": "Защита",
                "dueling": "Дуэлянт",
                "archery": "Стрельба",
                "great_weapon": "Великое оружие",
            }.get(self.battle_style, self.battle_style),
            "Второе дыхание — лечение 1d10 + уровень, 1 раз за бой",
        ]
        if self.level >= 2:
            feats.append("Action Surge — доп. действие 1 раз за бой")
        if self.level >= 5:
            feats.append("Дополнительная атака — 2 удара за 1 действие")
        from ..combat.abilities import ABILITY_REGISTRY
        for mid in self.maneuvers:
            ab = ABILITY_REGISTRY.get(mid)
            if ab:
                feats.append(f"Манёвр: {ab['name_ru']}")
        return feats

    @property
    def class_name_ru(self) -> str:
        return {"fighter": "Воин"}.get(self.char_class, self.char_class)
