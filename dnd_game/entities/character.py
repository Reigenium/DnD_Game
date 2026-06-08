"""Player character (only Fighter for MVP)."""
from __future__ import annotations

from dataclasses import dataclass, field

from ..items.item import Armor, Consumable, Weapon
from ..rules.ability import modifier


@dataclass
class Inventory:
    weapons: list[Weapon] = field(default_factory=list)
    armors: list[Armor] = field(default_factory=list)
    consumables: list[Consumable] = field(default_factory=list)
    gold: int = 0


@dataclass
class Character:
    name: str = "Боргх"
    char_class: str = "fighter"
    level: int = 1

    str_: int = 16
    dex: int = 12
    con: int = 14
    int_: int = 10
    wis: int = 12
    cha: int = 8

    max_hp: int = 12
    current_hp: int = 12

    proficiency_bonus: int = 2

    equipped_weapon: Weapon | None = None
    equipped_armor: Armor | None = None
    equipped_shield: Armor | None = None

    inventory: Inventory = field(default_factory=Inventory)

    x: int = 0
    y: int = 0

    xp: int = 0
    xp_to_next: int = 300

    # transient combat state
    blessed_turns: int = 0
    dodge_active: bool = False
    shield_active: bool = False
    second_wind_used: bool = False  # reset on each new fight

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
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def spell_attack_bonus(self) -> int:
        return self.proficiency_bonus + self.mod("int")

    def take_damage(self, amount: int) -> int:
        amount = max(0, amount)
        self.current_hp = max(0, self.current_hp - amount)
        return amount

    def heal(self, amount: int) -> int:
        before = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + max(0, amount))
        return self.current_hp - before

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

    # ---- Class metadata for the character sheet UI ----

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
        if self.char_class == "fighter":
            return [
                "Боевой стиль (Защита)",
                "Второе дыхание — лечение 1d10 + уровень, 1 раз за бой",
            ]
        return []

    @property
    def class_name_ru(self) -> str:
        return {"fighter": "Воин"}.get(self.char_class, self.char_class)
