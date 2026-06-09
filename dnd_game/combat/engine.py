"""Turn-based JRPG combat engine.

Phase 0: unified status system, Focus resource.
Phase 1: Sweep (AoE), Riposte (counter), Trip (stun), Action Surge, Extra Attack.
Phase 2: CTB turn-order timeline via TurnOrder, poise/break, intent telegraph.

Player always starts first (JRPG convention).  After each player action the engine
processes all enemy turns (in speed order) before returning to PLAYER_TURN.
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
from ..rules.status import (
    ActionSurgeUsedStatus, DodgingStatus, RiposteStatus, ShieldedStatus,
    StaggeredStatus, StunnedStatus,
)
from .targeting import TargetMode, resolve_targets
from .turn_order import TurnOrder


class CombatPhase(Enum):
    PLAYER_TURN = "player_turn"
    ENEMY_TURN = "enemy_turn"
    VICTORY = "victory"
    DEFEAT = "defeat"
    FLED = "fled"


MELEE_DAMAGE_TYPES = {"slashing", "piercing", "bludgeoning"}
TRIP_STR_DC = 13


@dataclass
class CombatEngine:
    player: Character
    enemies: list[Monster]
    log: list[str] = field(default_factory=list)
    phase: CombatPhase = CombatPhase.PLAYER_TURN
    target_index: int = 0
    xp_gained: int = 0

    # Extra actions remaining this turn (Action Surge grants 1).
    extra_actions: int = 0

    # TurnOrder for Phase 2 (enemy turn ordering by speed).
    turn_order: TurnOrder = field(init=False)

    def __post_init__(self) -> None:
        from ..core.rng import get_rng
        self.turn_order = TurnOrder([self.player] + self.enemies, get_rng())
        names = ", ".join(e.name_ru for e in self.enemies)
        self.log.append(f"Бой! В строю: {names}.")
        self._refresh_all_intents()

    # ── Target helpers ────────────────────────────────────────────────────

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

    # ── Intent ───────────────────────────────────────────────────────────

    def _refresh_all_intents(self) -> None:
        from ..core.rng import get_rng
        rng = get_rng()
        for e in self.alive_enemies:
            e.choose_intent(rng)

    # ── Player actions ────────────────────────────────────────────────────

    def player_attack(self) -> None:
        target = self.current_target
        if target is None:
            return
        attacks = self.player.attacks_per_action
        for i in range(attacks):
            if not target.is_alive:
                # Shift to next alive enemy.
                alive = self.alive_enemies
                if not alive:
                    break
                self.target_index = 0
                target = alive[0]
            self._do_player_attack(target)
            if not target.is_alive:
                self._on_kill(target)
                target = self.current_target
                if target is None:
                    break
        self._end_player_turn()

    def _do_player_attack(self, target: Monster) -> None:
        blessed_bonus = 0
        bs = self.player.get_status("blessed")
        if bs is not None:
            blessed_bonus = getattr(bs, "attack_bonus", 2)

        # Dueling style: +2 damage when wielding a one-handed weapon, no off-hand.
        style_dmg_bonus = 0
        if self.player.battle_style == "dueling":
            w = self.player.equipped_weapon
            if w is not None and not w.ranged:
                style_dmg_bonus = 2

        bonus = self.player.attack_bonus + blessed_bonus
        result = make_attack(
            attacker_name=self.player.name,
            target_name=target.name_ru,
            attack_bonus=bonus,
            damage_expression=self.player.damage_expression,
            damage_modifier=self.player.damage_bonus + style_dmg_bonus,
            target_ac=target.ac,
            damage_type=self.player.damage_type,
        )
        self.log.append(result.log)
        if result.hit:
            dmg, newly_enraged = target.take_damage(result.damage_total, self.player.damage_type)
            # Report resistance/vulnerability adjustments.
            self._log_damage_mods(target, result.damage_total, dmg, self.player.damage_type)
            if newly_enraged:
                self.log.append(f"  → {target.name_ru} впадает в ярость! +2 к атакам.")
            if dmg > 0:
                # Stagger announcement.
                if target.has_status("staggered") and not target.has_status("staggered"):
                    pass  # handled in take_damage
                # Focus gain on hit.
                gained = self.player.gain_focus(1)
                if gained > 0:
                    self.log.append(f"  → Фокус +1 ({self.player.focus}/{self.player.focus_max})")
            if not target.is_alive:
                pass  # caller handles _on_kill
            else:
                self._maybe_acid_splash(target)

    def _log_damage_mods(self, target: Monster, raw: int, applied: int, dtype: str) -> None:
        if dtype in target.immunities:
            self.log.append(f"  → {target.name_ru} иммунен к {dtype}!")
        elif dtype in target.vulnerabilities and applied > raw:
            self.log.append(f"  → {target.name_ru} уязвим к {dtype}! Двойной урон: {applied}.")
        elif dtype in target.resistances and applied < raw:
            self.log.append(f"  → {target.name_ru} устойчив к {dtype}: урон {applied}.")
        elif "undead_resist" in target.traits and dtype in ("slashing", "piercing"):
            if dtype not in target.resistances:
                self.log.append(f"  → {target.name_ru} (нежить): урон уполовинен → {applied}.")

    def player_sweep(self) -> None:
        """AoE attack hitting ALL alive enemies — primary at full damage, others at half."""
        if not self.player.spend_focus(2):
            self.log.append("Недостаточно Фокуса для Размаха (нужно 2).")
            return
        targets = self.alive_enemies
        if not targets:
            return
        primary = self.current_target
        self.log.append(f"{self.player.name} делает Размах по всем противникам!")

        blessed_bonus = 0
        bs = self.player.get_status("blessed")
        if bs is not None:
            blessed_bonus = getattr(bs, "attack_bonus", 2)
        bonus = self.player.attack_bonus + blessed_bonus

        for i, target in enumerate(targets):
            result = make_attack(
                attacker_name=self.player.name,
                target_name=target.name_ru,
                attack_bonus=bonus - (2 if i > 0 else 0),  # -2 for secondary
                damage_expression=self.player.damage_expression,
                damage_modifier=self.player.damage_bonus,
                target_ac=target.ac,
                damage_type=self.player.damage_type,
            )
            self.log.append(result.log)
            if result.hit:
                raw = result.damage_total
                final = raw if target is primary else max(1, raw // 2)
                dmg, newly_enraged = target.take_damage(final, self.player.damage_type)
                if i > 0 and result.hit:
                    self.log.append(f"  → {target.name_ru}: {dmg} (половина).")
                if newly_enraged:
                    self.log.append(f"  → {target.name_ru} впадает в ярость!")
                if not target.is_alive:
                    self._on_kill(target)

        self.player.gain_focus(1)
        self._end_player_turn()

    def player_riposte(self) -> None:
        """Riposte stance: counter-attack on the next incoming hit."""
        if not self.player.spend_focus(1):
            self.log.append("Недостаточно Фокуса для Рипоста (нужно 1).")
            return
        self.player.add_status(RiposteStatus(duration=-1))
        self.log.append(f"{self.player.name} принимает боевую стойку Рипост — контратакует при следующем ударе!")
        self._end_player_turn()

    def player_trip(self) -> None:
        """Trip attack: on hit, target must pass STR save DC 13 or be stunned."""
        target = self.current_target
        if target is None:
            return
        if not self.player.spend_focus(1):
            self.log.append("Недостаточно Фокуса для Подсечки (нужно 1).")
            return

        blessed_bonus = 0
        bs = self.player.get_status("blessed")
        if bs is not None:
            blessed_bonus = getattr(bs, "attack_bonus", 2)

        result = make_attack(
            attacker_name=self.player.name,
            target_name=target.name_ru,
            attack_bonus=self.player.attack_bonus + blessed_bonus,
            damage_expression=self.player.damage_expression,
            damage_modifier=self.player.damage_bonus,
            target_ac=target.ac,
            damage_type=self.player.damage_type,
        )
        self.log.append(result.log)
        if result.hit:
            dmg, newly_enraged = target.take_damage(result.damage_total, self.player.damage_type)
            if newly_enraged:
                self.log.append(f"  → {target.name_ru} впадает в ярость!")
            if target.is_alive:
                # STR saving throw.
                str_save = d20(target.mod("str"))
                if str_save.total < TRIP_STR_DC:
                    target.add_status(StunnedStatus(duration=1))
                    self.log.append(
                        f"  → {target.name_ru} подсечён! СИЛ {str_save} vs DC {TRIP_STR_DC} → провал, пропускает ход."
                    )
                else:
                    self.log.append(
                        f"  → {target.name_ru} устоял. СИЛ {str_save} vs DC {TRIP_STR_DC} → успех."
                    )
            else:
                self._on_kill(target)
            self.player.gain_focus(1)
        self._end_player_turn()

    def player_action_surge(self) -> None:
        """Grant one extra action this turn (once per combat)."""
        if self.player.has_status("action_surge_used"):
            self.log.append("Action Surge уже использован в этом бою.")
            return
        if self.extra_actions > 0:
            self.log.append("Action Surge уже активирован.")
            return
        self.player.add_status(ActionSurgeUsedStatus(duration=-1))
        self.extra_actions = 1
        self.log.append(f"{self.player.name} использует Action Surge — ещё одно действие!")
        # Phase stays PLAYER_TURN — don't call _end_player_turn.

    def player_dodge(self) -> None:
        self.player.add_status(DodgingStatus(duration=-1))  # removed after enemy phase
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
            self.log.append(f"{self.player.name} пьёт {consumable.name_ru}: +{healed} HP {r}.")
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
            applied, newly_enraged = target.take_damage(total, "force")
            if newly_enraged:
                self.log.append(f"  → {target.name_ru} впадает в ярость!")
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
            result = make_attack(
                attacker_name=f"{self.player.name} (Луч заморозки)",
                target_name=target.name_ru,
                attack_bonus=self.player.spell_attack_bonus,
                damage_expression="1d8",
                damage_modifier=0,
                target_ac=target.ac,
                damage_type="cold",
            )
            self.log.append(result.log)
            if result.hit:
                applied, newly_enraged = target.take_damage(result.damage_total, "cold")
                self._log_damage_mods(target, result.damage_total, applied, "cold")
                if newly_enraged:
                    self.log.append(f"  → {target.name_ru} впадает в ярость!")
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
                f"{self.player.name} зачитывает «{consumable.name_ru}»: следующая атака провалится."
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

    # ── Kill / Victory ────────────────────────────────────────────────────

    def _on_kill(self, target: Monster) -> None:
        self.log.append(f"{target.name_ru} повержен! (+{target.xp} XP)")
        self.xp_gained += target.xp
        kill_heal = max(2, int(target.max_hp * 0.2 + target.cr * 2))
        actual = self.player.heal(kill_heal)
        if actual > 0:
            self.log.append(f"  → ты черпаешь силы из победы: +{actual} HP.")
        gained = self.player.gain_focus(2)
        if gained > 0:
            self.log.append(f"  → Фокус +2 ({self.player.focus}/{self.player.focus_max})")
        self.turn_order.remove(target)

    # ── Phase plumbing ────────────────────────────────────────────────────

    def _end_player_turn(self) -> None:
        if not self.alive_enemies:
            self.phase = CombatPhase.VICTORY
            self.log.append(f"Победа! Получено {self.xp_gained} XP.")
            return
        # Decrement blessed status (per player action, not per enemy).
        bs = self.player.get_status("blessed")
        if bs is not None and bs.duration > 0:
            bs.duration -= 1
            if bs.duration == 0:
                self.player.remove_status("blessed")

        if self.extra_actions > 0:
            self.extra_actions -= 1
            self.phase = CombatPhase.PLAYER_TURN  # surge: another action
            return
        self.phase = CombatPhase.ENEMY_TURN

    def enemy_turn(self) -> None:
        """Process all enemy turns in speed order, then return to player."""
        # Remove dodge — it covered the entire enemy phase.
        self.player.remove_status("dodging")

        for enemy in self.turn_order.enemies_in_order():
            if not self.player.is_alive:
                break
            if not enemy.is_alive:
                continue

            # Tick enemy statuses (DoT, frozen duration countdown, etc.).
            msgs = enemy.tick_statuses()
            self.log.extend(msgs)

            if not enemy.is_alive:
                self._on_kill(enemy)
                continue

            skip_statuses = {"frozen", "stunned", "staggered"}
            if any(enemy.has_status(s) for s in skip_statuses):
                if enemy.has_status("staggered"):
                    self.log.append(f"{enemy.name_ru} сбит с толку — пропускает ход.")
                    enemy.remove_status("staggered")
                else:
                    self.log.append(f"{enemy.name_ru} скован — пропускает ход.")
            else:
                self._enemy_attack(enemy)
                # Choose intent for NEXT round.
                from ..core.rng import get_rng
                enemy.choose_intent(get_rng())

        if not self.player.is_alive:
            self.phase = CombatPhase.DEFEAT
            self.log.append(f"{self.player.name} пал в бою...")
        else:
            # Tick player statuses at start of their next turn.
            msgs = self.player.tick_statuses()
            self.log.extend(msgs)
            if not self.player.is_alive:
                self.phase = CombatPhase.DEFEAT
                self.log.append(f"{self.player.name} пал от последствий статуса...")
            else:
                self.phase = CombatPhase.PLAYER_TURN

    # ── Enemy attack logic ────────────────────────────────────────────────

    def _enemy_attack(self, enemy: Monster) -> None:
        if not enemy.attacks:
            return

        # Shield scroll blocks one attack entirely.
        if self.player.shield_active:
            self.log.append(f"{enemy.name_ru} атакует, но магический щит отбивает удар!")
            self.player.remove_status("shielded")
            return

        attack = enemy.attacks[0]
        rage_bonus = 0
        enr = enemy.get_status("enraged")
        if enr is not None:
            rage_bonus = getattr(enr, "attack_bonus", 2)

        # Intent: heavy attack variant.
        heavy = (enemy.current_intent == "heavy_attack")
        if heavy:
            attack_bonus_override = attack.to_hit + rage_bonus - 2
            damage_expr = attack.damage  # rolled twice for heavy
        else:
            attack_bonus_override = attack.to_hit + rage_bonus
            damage_expr = attack.damage

        # Pack tactics: advantage if another living ally is present.
        has_ally = "pack_tactics" in enemy.traits and any(
            other is not enemy for other in self.alive_enemies
        )
        dodge_active = self.player.has_status("dodging")
        advantage = has_ally and not dodge_active
        disadvantage = dodge_active and not has_ally

        # Weakened: attacks with disadvantage.
        if enemy.has_status("weakened"):
            disadvantage = True
            advantage = False

        result = make_attack(
            attacker_name=enemy.name_ru + (" (ярость)" if enemy.enraged else "")
                          + (" (тяж.удар)" if heavy else ""),
            target_name=self.player.name,
            attack_bonus=attack_bonus_override,
            damage_expression=damage_expr,
            damage_modifier=0,
            target_ac=self.player.ac,
            damage_type=attack.damage_type,
            advantage=advantage,
            disadvantage=disadvantage,
        )

        if has_ally and "pack_tactics" in enemy.traits and not dodge_active:
            self.log.append(f"  → стайная тактика {enemy.name_ru}: преимущество.")
        self.log.append(result.log)

        if result.hit:
            raw_dmg = result.damage_total
            # Heavy attack: add a second damage roll.
            if heavy:
                bonus_r = roll(damage_expr)
                raw_dmg += bonus_r.total
                self.log.append(f"  → тяжёлый удар! Доп. урон: {bonus_r}.")
            # Staggered player takes double damage.
            if self.player.has_status("staggered"):
                raw_dmg *= 2
                self.log.append("  → ты сбит — двойной урон!")
            self.player.take_damage(raw_dmg)
            self._maybe_acid_splash(enemy)
            # Riposte: counter if player is in riposte stance.
            if self.player.has_status("riposte"):
                self.player.remove_status("riposte")
                self._riposte_counter(enemy)

    def _maybe_acid_splash(self, enemy: Monster) -> None:
        if "acid_splash" in enemy.traits and self.player.damage_type in MELEE_DAMAGE_TYPES:
            actual = self.player.take_damage(1)
            if actual > 0:
                self.log.append(f"  → кислотный отклик {enemy.name_ru}: {actual} урона тебе.")

    def _riposte_counter(self, enemy: Monster) -> None:
        if not enemy.is_alive:
            return
        result = make_attack(
            attacker_name=f"{self.player.name} (рипост)",
            target_name=enemy.name_ru,
            attack_bonus=self.player.attack_bonus,
            damage_expression=self.player.damage_expression,
            damage_modifier=self.player.damage_bonus,
            target_ac=enemy.ac,
            damage_type=self.player.damage_type,
        )
        self.log.append(result.log)
        if result.hit:
            dmg, newly_enraged = enemy.take_damage(result.damage_total, self.player.damage_type)
            if newly_enraged:
                self.log.append(f"  → {enemy.name_ru} впадает в ярость!")
            if not enemy.is_alive:
                self._on_kill(enemy)
