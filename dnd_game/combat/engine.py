"""Turn-based, JRPG-style combat encounter.

JRPG flavor:
- Player always acts first each round.
- Killing a monster refunds a chunk of HP (~20% of its max), so you can
  survive a war of attrition.
- Per-combat resources reset at the start of each fight (Second Wind).

Monster traits (string flags read from data/monsters.json):
- ``undead_resist``   — halves incoming slashing/piercing damage.
- ``pack_tactics``    — this monster attacks with advantage if any other
                         living enemy is in the fight.
- ``rage_at_half``    — once HP drops to half, +2 to all attack rolls.
- ``acid_splash``     — splashes 1 acid damage to a melee attacker on hit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from ..core.dice import d20, roll
from ..entities.character import Character
from ..entities.monster import Monster
from ..items.item import Consumable
from ..rules.combat import make_attack


class CombatPhase(Enum):
    PLAYER_TURN = "player_turn"
    ENEMY_TURN = "enemy_turn"
    VICTORY = "victory"
    DEFEAT = "defeat"
    FLED = "fled"


# Damage types considered "melee" for the slime's acid splash counter.
MELEE_DAMAGE_TYPES = {"slashing", "piercing", "bludgeoning"}


@dataclass
class CombatEngine:
    player: Character
    enemies: list[Monster]
    log: list[str] = field(default_factory=list)
    phase: CombatPhase = CombatPhase.PLAYER_TURN
    target_index: int = 0
    xp_gained: int = 0

    def __post_init__(self) -> None:
        names = ", ".join(e.name_ru for e in self.enemies)
        self.log.append(f"Бой! В строю: {names}.")

    @property
    def alive_enemies(self) -> list[Monster]:
        return [e for e in self.enemies if e.is_alive]

    @property
    def current_target(self) -> Optional[Monster]:
        alive = self.alive_enemies
        if not alive:
            return None
        if self.target_index >= len(alive):
            self.target_index = 0
        return alive[self.target_index]

    def cycle_target(self) -> None:
        alive = self.alive_enemies
        if alive:
            self.target_index = (self.target_index + 1) % len(alive)

    def select_target(self, index: int) -> None:
        alive = self.alive_enemies
        if alive and 0 <= index < len(alive):
            self.target_index = index

    # ----- Player actions -----

    def player_attack(self) -> None:
        target = self.current_target
        if target is None:
            return
        bonus = self.player.attack_bonus + (2 if self.player.blessed_turns > 0 else 0)
        result = make_attack(
            attacker_name=self.player.name,
            target_name=target.name_ru,
            attack_bonus=bonus,
            damage_expression=self.player.damage_expression,
            damage_modifier=self.player.damage_bonus,
            target_ac=target.ac,
            damage_type=self.player.damage_type,
        )
        self.log.append(result.log)
        if result.hit:
            dmg = self._apply_player_damage_to(target, result.damage_total, self.player.damage_type)
            if not target.is_alive:
                self._on_kill(target)
            else:
                self._maybe_acid_splash(target)
        self._end_player_turn()

    def _apply_player_damage_to(self, target: Monster, raw_damage: int, damage_type: str) -> int:
        dmg = raw_damage
        if "undead_resist" in target.traits and damage_type in ("slashing", "piercing"):
            dmg = max(1, dmg // 2)
            self.log.append(
                f"  → {target.name_ru} (нежить): {damage_type} урон уполовинен → {dmg}."
            )
        applied, newly_enraged = target.take_damage(dmg)
        if newly_enraged:
            self.log.append(f"  → {target.name_ru} впадает в ярость! +2 к атакам.")
        return applied

    def _maybe_acid_splash(self, target: Monster) -> None:
        # Counter for melee-only swings.
        if "acid_splash" in target.traits and self.player.damage_type in MELEE_DAMAGE_TYPES:
            actual = self.player.take_damage(1)
            if actual > 0:
                self.log.append(f"  → кислотный отклик {target.name_ru}: {actual} урона тебе.")

    def player_dodge(self) -> None:
        self.player.dodge_active = True
        self.log.append(f"{self.player.name} принимает защитную стойку (атаки с помехой).")
        self._end_player_turn()

    def player_second_wind(self) -> bool:
        if self.player.second_wind_used:
            self.log.append("Второе дыхание уже использовано в этом бою.")
            return False
        if self.player.current_hp >= self.player.max_hp:
            self.log.append("Здоровье полное — Второе дыхание не нужно.")
            return False
        self.player.second_wind_used = True
        r = roll("1d10")
        healed = self.player.heal(r.total + self.player.level)
        self.log.append(
            f"{self.player.name} использует Второе дыхание: +{healed} HP {r}+ур.{self.player.level}."
        )
        self._end_player_turn()
        return True

    def player_flee(self) -> None:
        alive = self.alive_enemies
        if not alive:
            self.phase = CombatPhase.VICTORY
            return
        dc = int(10 + max(e.cr for e in alive) * 2)
        check = d20(self.player.mod("dex"))
        if check.total >= dc:
            self.log.append(f"{self.player.name} убегает! ЛВК {check} vs DC {dc} → успех.")
            self.phase = CombatPhase.FLED
        else:
            self.log.append(f"{self.player.name} не может уйти: ЛВК {check} vs DC {dc} → провал.")
            self._end_player_turn()

    def player_use_item(self, consumable: Consumable) -> bool:
        effect = consumable.effect

        if effect == "heal":
            r = roll(consumable.amount)
            healed = self.player.heal(r.total)
            self.log.append(
                f"{self.player.name} пьёт {consumable.name_ru}: +{healed} HP {r}."
            )
            self._remove_consumable(consumable)
            self._end_player_turn()
            return True

        if effect == "magic_missile":
            target = self.current_target
            if target is None:
                self.log.append("Нет цели для волшебных стрел.")
                return False
            total = 0
            rolls_log: list[str] = []
            for _ in range(3):
                r = roll("1d4+1")
                rolls_log.append(str(r))
                total += r.total
            self.log.append(
                f"{self.player.name} зачитывает «{consumable.name_ru}» в "
                f"{target.name_ru}: 3 стрелы, итого {total} силового урона."
            )
            self.log.append("  → " + "  ".join(rolls_log))
            # force damage ignores resistances; raw apply.
            applied, newly_enraged = target.take_damage(total)
            if newly_enraged:
                self.log.append(f"  → {target.name_ru} впадает в ярость! +2 к атакам.")
            if not target.is_alive:
                self._on_kill(target)
            self._remove_consumable(consumable)
            self._end_player_turn()
            return True

        if effect == "ray_of_frost":
            target = self.current_target
            if target is None:
                self.log.append("Нет цели для луча заморозки.")
                return False
            atk_mod = self.player.spell_attack_bonus
            result = make_attack(
                attacker_name=f"{self.player.name} (Луч заморозки)",
                target_name=target.name_ru,
                attack_bonus=atk_mod,
                damage_expression="1d8",
                damage_modifier=0,
                target_ac=target.ac,
                damage_type="cold",
            )
            self.log.append(result.log)
            if result.hit:
                applied, newly_enraged = target.take_damage(result.damage_total)
                if newly_enraged:
                    self.log.append(f"  → {target.name_ru} впадает в ярость! +2 к атакам.")
                if target.is_alive:
                    target.frozen_turns = max(target.frozen_turns, 1)
                    self.log.append(f"{target.name_ru} скован холодом — пропустит следующий ход.")
                else:
                    self._on_kill(target)
            self._remove_consumable(consumable)
            self._end_player_turn()
            return True

        if effect == "shield":
            self.player.shield_active = True
            self.log.append(
                f"{self.player.name} зачитывает «{consumable.name_ru}»: "
                f"следующая атака провалится."
            )
            self._remove_consumable(consumable)
            self._end_player_turn()
            return True

        return False

    def _remove_consumable(self, consumable: Consumable) -> None:
        try:
            self.player.inventory.consumables.remove(consumable)
        except ValueError:
            pass

    def _on_kill(self, target: Monster) -> None:
        self.log.append(f"{target.name_ru} повержен! (+{target.xp} XP)")
        self.xp_gained += target.xp
        # JRPG-style: killing refunds some HP — a steady drip vs. a swarm.
        kill_heal = max(2, target.max_hp // 5)
        actual = self.player.heal(kill_heal)
        if actual > 0:
            self.log.append(f"  → ты черпаешь силы из победы: +{actual} HP.")

    # ----- Phase plumbing -----

    def _end_player_turn(self) -> None:
        if not self.alive_enemies:
            self.phase = CombatPhase.VICTORY
            self.log.append(f"Победа! Получено {self.xp_gained} XP.")
            return
        if self.player.blessed_turns > 0:
            self.player.blessed_turns -= 1
        self.phase = CombatPhase.ENEMY_TURN

    def enemy_turn(self) -> None:
        for enemy in list(self.alive_enemies):
            if not self.player.is_alive:
                break
            if enemy.frozen_turns > 0:
                self.log.append(f"{enemy.name_ru} скован холодом — пропускает ход.")
                enemy.frozen_turns -= 1
                continue
            self._enemy_attack(enemy)
        self.player.dodge_active = False
        if not self.player.is_alive:
            self.phase = CombatPhase.DEFEAT
            self.log.append(f"{self.player.name} пал в бою...")
        else:
            self.phase = CombatPhase.PLAYER_TURN

    def _enemy_attack(self, enemy: Monster) -> None:
        if not enemy.attacks:
            return
        if self.player.shield_active:
            self.log.append(
                f"{enemy.name_ru} атакует, но магический щит отбивает удар!"
            )
            self.player.shield_active = False
            return
        attack = enemy.attacks[0]
        rage_bonus = 2 if enemy.enraged else 0

        # Pack tactics: advantage if there's any other living enemy in the fight.
        has_ally = False
        if "pack_tactics" in enemy.traits:
            has_ally = any(other is not enemy for other in self.alive_enemies)

        advantage = has_ally and not self.player.dodge_active
        disadvantage = self.player.dodge_active and not has_ally

        result = make_attack(
            attacker_name=enemy.name_ru + (" (ярость)" if enemy.enraged else ""),
            target_name=self.player.name,
            attack_bonus=attack.to_hit + rage_bonus,
            damage_expression=attack.damage,
            damage_modifier=0,
            target_ac=self.player.ac,
            damage_type=attack.damage_type,
            advantage=advantage,
            disadvantage=disadvantage,
        )
        if has_ally and "pack_tactics" in enemy.traits and not self.player.dodge_active:
            self.log.append(f"  → стайная тактика {enemy.name_ru}: преимущество.")
        self.log.append(result.log)
        if result.hit:
            self.player.take_damage(result.damage_total)
