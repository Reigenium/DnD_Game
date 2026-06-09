"""Top-level game state machine + controller methods the UI calls.

States:
  NAME_ENTRY     — pre-game name input.
  EXPLORE        — walking the dungeon.
  COMBAT         — modal JRPG turn-based fight.
  ENCOUNTER      — modal dialog from data/encounters.json.
  STAIRS_PROMPT  — modal Y/N confirm "descend to floor N+1?".
  INVENTORY      — modal inventory + equipment management.
  CHARACTER      — modal character sheet (read-only stats).
  LEVEL_UP       — modal level-up choice screen.
  GAME_OVER      — death screen.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from ..combat.engine import CombatEngine, CombatPhase
from ..core.dice import d20, roll
from ..core.rng import get_rng
from ..encounters.encounter import EncounterDef
from ..encounters.loader import load_encounters
from ..entities.character import Character
from ..entities.monster import Monster, spawn_monster
from ..items.item import Armor, Consumable, Weapon
from ..items.loader import load_armor, load_consumables, load_weapons
from ..world import tile as tile_mod
from ..world.dungeon import Dungeon, EncounterMarker, LootItem
from ..world.generator import generate_floor
from . import save as save_mod


class GameState(Enum):
    NAME_ENTRY = "name_entry"
    EXPLORE = "explore"
    COMBAT = "combat"
    ENCOUNTER = "encounter"
    STAIRS_PROMPT = "stairs_prompt"
    INVENTORY = "inventory"
    CHARACTER = "character"
    LEVEL_UP = "level_up"
    GAME_OVER = "game_over"


@dataclass
class ActiveEncounter:
    definition: EncounterDef
    marker: EncounterMarker
    resolved: bool = False
    message: str = ""


class Game:
    MAP_WIDTH = 80
    MAP_HEIGHT = 43
    MOVE_REPEAT_INTERVAL = 0.13
    MAX_COMBAT_ENEMIES = 3
    MAX_ORCS_PER_FIGHT = 1
    BUMP_PULL_PROBABILITY = 0.35

    # Level-up choices: levels that require player to pick a maneuver.
    CHOICE_LEVELS: set[int] = {3, 4, 6, 7, 8, 9, 10}

    def __init__(self) -> None:
        self.weapons: dict[str, Weapon] = load_weapons()
        self.armors: dict[str, Armor] = load_armor()
        self.consumables_by_id: dict[str, Consumable] = load_consumables()
        self.encounter_defs: dict[str, EncounterDef] = load_encounters()

        self.player: Character = self._create_fighter("Боргх")
        self.dungeon: Dungeon | None = None
        self.floor: int = 1
        self.state: GameState = GameState.NAME_ENTRY
        self.message_log: list[str] = []
        self.combat: CombatEngine | None = None
        self.encounter: ActiveEncounter | None = None
        self.combat_item_menu_open: bool = False
        self.pending_name: str = ""
        self.last_move_time: float = 0.0
        self.last_text_input_at: float = 0.0
        # Level-up pending choices (list of maneuver ids or "stat_str" etc.)
        self.levelup_choices: list[str] = []
        self.levelup_level: int = 0

        if save_mod.has_save():
            if save_mod.load_game(self):
                self.state = GameState.EXPLORE
                self.add_log("Забег продолжен.")
            else:
                save_mod.delete_save()

    # ── Character bootstrap ───────────────────────────────────────────────

    def _create_fighter(self, name: str) -> Character:
        c = Character(
            name=name,
            char_class="fighter",
            level=1,
            str_=16, dex=12, con=14, int_=10, wis=12, cha=8,
            max_hp=12, current_hp=12,
            proficiency_bonus=2,
        )
        c.equipped_weapon = self.weapons["shortsword"]
        c.equipped_armor = self.armors["chain_shirt"]
        c.equipped_shield = self.armors["shield"]
        c.inventory.weapons.append(self.weapons["shortbow"])
        c.inventory.consumables.append(self.consumables_by_id["healing_potion"])
        c.inventory.consumables.append(self.consumables_by_id["healing_potion"])
        c.inventory.consumables.append(self.consumables_by_id["scroll_shield"])
        c.inventory.gold = 25
        return c

    def add_log(self, msg: str) -> None:
        if not msg:
            return
        self.message_log.append(msg)
        if len(self.message_log) > 200:
            self.message_log = self.message_log[-200:]

    # ── NAME ENTRY ────────────────────────────────────────────────────────

    def name_entry_add(self, text: str) -> None:
        for ch in text:
            if len(self.pending_name) >= 20:
                return
            if ch.isalpha() or ch in " -'":
                self.pending_name += ch

    def name_entry_backspace(self) -> None:
        self.pending_name = self.pending_name[:-1]

    def name_entry_confirm(self) -> None:
        name = self.pending_name.strip() or "Боргх"
        self.player.name = name
        self.floor = 1
        self.dungeon = generate_floor(self.MAP_WIDTH, self.MAP_HEIGHT, floor=1)
        self.player.x, self.player.y = self.dungeon.player_start
        self.dungeon.update_fov(self.player.x, self.player.y)
        self.state = GameState.EXPLORE
        self.message_log = [f"Добро пожаловать, {name}!", "Этаж 1."]
        save_mod.save_game(self)

    def restart(self) -> None:
        save_mod.delete_save()
        self.player = self._create_fighter("Боргх")
        self.dungeon = None
        self.floor = 1
        self.combat = None
        self.encounter = None
        self.combat_item_menu_open = False
        self.state = GameState.NAME_ENTRY
        self.message_log = []
        self.pending_name = ""
        self.levelup_choices = []

    def save(self) -> None:
        if self.dungeon is None:
            return
        if self.state in (GameState.COMBAT, GameState.ENCOUNTER, GameState.GAME_OVER):
            return
        save_mod.save_game(self)

    # ── EXPLORE ───────────────────────────────────────────────────────────

    def move_player(self, dx: int, dy: int, *, is_repeat: bool = False) -> None:
        if self.state != GameState.EXPLORE or self.dungeon is None:
            return
        if is_repeat:
            now = time.monotonic()
            if now - self.last_move_time < self.MOVE_REPEAT_INTERVAL:
                return
            self.last_move_time = now
        else:
            self.last_move_time = time.monotonic()

        if dx == 0 and dy == 0:
            return

        nx, ny = self.player.x + dx, self.player.y + dy
        if not self.dungeon.is_walkable(nx, ny):
            return

        monster = self.dungeon.monster_at(nx, ny)
        if monster is not None:
            self._start_combat_from_bump(monster)
            return

        prev_pos = (self.player.x, self.player.y)
        self.player.x, self.player.y = nx, ny
        self.dungeon.update_fov(nx, ny)

        # Loot pickup auto-prompt (or press G separately).
        loot = self.dungeon.loot_at(nx, ny)
        if loot is not None:
            self._pick_up_loot(loot)

        # Trap check.
        if self.dungeon.is_trap(nx, ny) and not self.dungeon.is_trap_revealed(nx, ny):
            self._trigger_trap(nx, ny)

        enc_marker = self.dungeon.encounter_at(nx, ny)
        if enc_marker is not None:
            self.start_encounter(enc_marker)
            return

        if self.dungeon.stairs_down == (nx, ny) and prev_pos != self.dungeon.stairs_down:
            self.state = GameState.STAIRS_PROMPT

        # Tick monster AI.
        self._tick_monster_ai()

    def pick_up_item(self) -> None:
        """G key: pick up loot at player position."""
        if self.dungeon is None:
            return
        loot = self.dungeon.loot_at(self.player.x, self.player.y)
        if loot is None:
            self.add_log("Здесь нечего подбирать.")
            return
        self._pick_up_loot(loot)

    def _pick_up_loot(self, loot: LootItem) -> None:
        assert self.dungeon is not None
        if loot.gold > 0:
            self.player.inventory.gold += loot.gold
            self.add_log(f"Подобрано {loot.gold} зм.")
        for item_id in loot.consumable_ids:
            c = self.consumables_by_id.get(item_id)
            if c:
                self.player.inventory.consumables.append(c)
                self.add_log(f"Подобрано: {c.name_ru}.")
        self.dungeon.remove_loot(loot.x, loot.y)

    def _trigger_trap(self, x: int, y: int) -> None:
        assert self.dungeon is not None
        from ..core.dice import roll as roll_dice, d20
        save = d20(self.player.mod("dex"))
        self.dungeon.reveal_trap(x, y)
        if save.total >= 12:
            self.add_log(f"Ловушка! ЛВК {save} vs DC 12 → успех, избежал.")
        else:
            dmg_roll = roll_dice("1d6")
            actual = self.player.take_damage(dmg_roll.total)
            self.add_log(f"Ловушка! ЛВК {save} vs DC 12 → провал: {actual} урона {dmg_roll}.")
            if not self.player.is_alive:
                self.state = GameState.GAME_OVER
                save_mod.delete_save()

    def _tick_monster_ai(self) -> None:
        if self.dungeon is None:
            return
        from ..world.ai import tick_monster_ai
        for m in self.dungeon.monsters:
            if m.is_alive:
                tick_monster_ai(m, self.player, self.dungeon)

    def open_inventory(self) -> None:
        if self.state == GameState.EXPLORE:
            self.state = GameState.INVENTORY

    def open_character(self) -> None:
        if self.state == GameState.EXPLORE:
            self.state = GameState.CHARACTER

    def close_modal(self) -> None:
        if self.state in (GameState.INVENTORY, GameState.CHARACTER):
            self.state = GameState.EXPLORE

    # ── STAIRS PROMPT ─────────────────────────────────────────────────────

    def confirm_descent(self) -> None:
        if self.state != GameState.STAIRS_PROMPT:
            return
        self._descend_to_next_floor()
        self.state = GameState.EXPLORE

    def decline_descent(self) -> None:
        if self.state != GameState.STAIRS_PROMPT:
            return
        self.state = GameState.EXPLORE
        self.add_log("Ты решаешь пока остаться на этом этаже.")

    def _descend_to_next_floor(self) -> None:
        assert self.dungeon is not None
        self.floor += 1
        self.dungeon = generate_floor(self.MAP_WIDTH, self.MAP_HEIGHT, floor=self.floor)
        self.player.x, self.player.y = self.dungeon.player_start
        self.dungeon.update_fov(self.player.x, self.player.y)
        rest = self.player.heal(max(1, self.player.max_hp // 4))
        self.add_log(f"Этаж {self.floor}. (Короткий привал: +{rest} HP.)")
        save_mod.save_game(self)

    # ── COMBAT ────────────────────────────────────────────────────────────

    def _start_combat_from_bump(self, target: Monster) -> None:
        enemies: list[Monster] = [target]
        rng = get_rng()
        has_orc = (target.id == "orc")

        nearby = [
            m for m in self.dungeon.monsters
            if m is not target and m.is_alive
            and abs(m.x - target.x) <= 2 and abs(m.y - target.y) <= 2
        ]
        rng.shuffle(nearby)
        for m in nearby:
            if len(enemies) >= self.MAX_COMBAT_ENEMIES:
                break
            if m.id == "orc" and has_orc:
                continue
            if rng.random() < self.BUMP_PULL_PROBABILITY:
                enemies.append(m)
                if m.id == "orc":
                    has_orc = True
        self.start_combat(enemies)

    def start_combat(self, enemies: list[Monster]) -> None:
        self.player.second_wind_used = False
        self.player.focus = 0  # reset Focus at start of fight
        self.combat = CombatEngine(self.player, enemies)
        self.combat_item_menu_open = False
        self.state = GameState.COMBAT

    def combat_action(self, action: str, payload=None) -> None:
        if self.combat is None or self.state != GameState.COMBAT:
            return
        if self.combat.phase != CombatPhase.PLAYER_TURN:
            return

        acted = True
        if action == "attack":
            self.combat.player_attack()
        elif action == "dodge":
            self.combat.player_dodge()
        elif action == "second_wind":
            used = self.combat.player_second_wind()
            if not used:
                return
        elif action == "sweep":
            self.combat.player_sweep()
        elif action == "riposte":
            self.combat.player_riposte()
        elif action == "trip":
            self.combat.player_trip()
        elif action == "action_surge":
            self.combat.player_action_surge()
            acted = False  # surge doesn't end turn by itself
        elif action == "item":
            if isinstance(payload, Consumable):
                used = self.combat.player_use_item(payload)
                if not used:
                    return
                self.combat_item_menu_open = False
        elif action == "flee":
            self.combat.player_flee()
        elif action == "cycle_target":
            self.combat.cycle_target()
            return
        elif action == "select_target":
            if isinstance(payload, int):
                self.combat.select_target(payload)
            return
        else:
            return

        if not acted:
            return

        if self.combat.phase == CombatPhase.ENEMY_TURN:
            self.combat.enemy_turn()

        if self.combat.phase == CombatPhase.VICTORY:
            self._finish_combat_victory()
        elif self.combat.phase == CombatPhase.DEFEAT:
            self._finish_combat_defeat()
        elif self.combat.phase == CombatPhase.FLED:
            self._finish_combat_flee()

    def toggle_combat_item_menu(self) -> None:
        if self.state != GameState.COMBAT or self.combat is None:
            return
        if self.combat.phase != CombatPhase.PLAYER_TURN:
            return
        self.combat_item_menu_open = not self.combat_item_menu_open

    def _drain_combat_log(self) -> None:
        if self.combat is None:
            return
        for line in self.combat.log:
            self.add_log(line)

    def _finish_combat_victory(self) -> None:
        assert self.combat is not None
        self._drain_combat_log()
        dead = {id(m) for m in self.combat.enemies if not m.is_alive}
        assert self.dungeon is not None

        # Drop loot from dead monsters.
        for m in self.combat.enemies:
            if not m.is_alive:
                self._drop_monster_loot(m)

        self.dungeon.monsters = [m for m in self.dungeon.monsters if id(m) not in dead]

        leveled = self.player.gain_xp(self.combat.xp_gained)
        if leveled:
            self.add_log(f"Уровень повышен! Теперь {self.player.level}.")
            # Action Surge unlocked at level 2 (auto).
            if self.player.level == 2:
                self.add_log("Разблокировано: Action Surge [U]!")
            if self.player.level == 5:
                self.add_log("Разблокировано: Дополнительная атака (2 удара за [A])!")

        self.combat = None
        self.combat_item_menu_open = False

        # Show level-up choice screen if needed.
        if leveled and self.player.level in self.CHOICE_LEVELS:
            self._prepare_levelup_choices()
            self.state = GameState.LEVEL_UP
        else:
            self.state = GameState.EXPLORE

    def _drop_monster_loot(self, monster: Monster) -> None:
        if not monster.loot_table or self.dungeon is None:
            return
        rng = get_rng()
        gold = 0
        consumable_ids: list[str] = []
        for entry in monster.loot_table:
            if rng.random() < entry.get("chance", 0):
                if entry.get("type") == "gold":
                    gold += rng.randint(entry.get("min", 1), entry.get("max", 5))
                elif entry.get("type") == "consumable":
                    item_id = entry.get("id", "")
                    if item_id in self.consumables_by_id:
                        consumable_ids.append(item_id)
        if gold > 0 or consumable_ids:
            self.dungeon.add_loot(LootItem(monster.x, monster.y, gold, consumable_ids))

    def _finish_combat_defeat(self) -> None:
        self._drain_combat_log()
        self.combat = None
        self.combat_item_menu_open = False
        self.state = GameState.GAME_OVER
        save_mod.delete_save()

    def _finish_combat_flee(self) -> None:
        assert self.combat is not None and self.dungeon is not None
        self._drain_combat_log()
        rng = get_rng()
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (-1, 1), (1, -1)]
        rng.shuffle(directions)
        for dx, dy in directions:
            nx, ny = self.player.x + dx, self.player.y + dy
            if self.dungeon.is_walkable(nx, ny) and self.dungeon.monster_at(nx, ny) is None:
                self.player.x, self.player.y = nx, ny
                self.dungeon.update_fov(nx, ny)
                break
        self.combat = None
        self.combat_item_menu_open = False
        self.state = GameState.EXPLORE

    # ── LEVEL UP ──────────────────────────────────────────────────────────

    def _prepare_levelup_choices(self) -> None:
        from ..combat.abilities import all_maneuver_ids, ABILITY_REGISTRY
        all_ids = all_maneuver_ids()
        known = set(self.player.maneuvers)
        available = [mid for mid in all_ids if mid not in known]
        level = self.player.level

        if level in (3, 6):
            # Pick one of 3 maneuvers.
            rng = get_rng()
            rng.shuffle(available)
            self.levelup_choices = available[:3]
        elif level in (4, 7, 8, 9, 10):
            # +2 stat OR maneuver.
            rng = get_rng()
            rng.shuffle(available)
            self.levelup_choices = ["stat_str", "stat_dex", "stat_con"] + available[:2]
        else:
            self.levelup_choices = []
        self.levelup_level = level

    def levelup_choose(self, index: int) -> None:
        if self.state != GameState.LEVEL_UP:
            return
        if not (0 <= index < len(self.levelup_choices)):
            return
        choice = self.levelup_choices[index]
        if choice == "stat_str":
            self.player.str_ += 2
            self.add_log("СИЛ +2!")
        elif choice == "stat_dex":
            self.player.dex += 2
            self.add_log("ЛВК +2!")
        elif choice == "stat_con":
            self.player.con += 2
            self.player.max_hp += 2
            self.player.current_hp += 2
            self.add_log("ТЕЛ +2! Макс. HP +2.")
        else:
            # It's a maneuver id.
            from ..combat.abilities import ABILITY_REGISTRY
            ab = ABILITY_REGISTRY.get(choice, {})
            self.player.maneuvers.append(choice)
            self.add_log(f"Изучен манёвр: {ab.get('name_ru', choice)}!")
        self.levelup_choices = []
        self.state = GameState.EXPLORE
        save_mod.save_game(self)

    # ── ENCOUNTERS ────────────────────────────────────────────────────────

    def start_encounter(self, marker: EncounterMarker) -> None:
        edef = self.encounter_defs.get(marker.encounter_id)
        if edef is None:
            return
        self.encounter = ActiveEncounter(definition=edef, marker=marker)
        self.state = GameState.ENCOUNTER

    def encounter_choose(self, index: int) -> None:
        if self.encounter is None or self.state != GameState.ENCOUNTER:
            return
        if self.encounter.resolved:
            self._close_encounter()
            return

        choices = self.encounter.definition.choices
        if not (0 <= index < len(choices)):
            return
        choice = choices[index]

        if "gold" in choice.requires and self.player.inventory.gold < choice.requires["gold"]:
            self.encounter.message = "Не хватает золота."
            return
        if "item" in choice.requires:
            item_id = choice.requires["item"]
            if not any(c.id == item_id for c in self.player.inventory.consumables):
                self.encounter.message = "У тебя нет нужного предмета."
                return

        messages: list[str] = []

        if choice.check is not None:
            success, msg = self._run_check(choice.check)
            messages.append(msg)
            if success:
                if choice.on_success_text:
                    messages.append(choice.on_success_text)
                for eff in choice.on_success:
                    messages.extend(self._apply_effect(eff))
            else:
                if choice.on_fail_text:
                    messages.append(choice.on_fail_text)
                for eff in choice.on_fail:
                    messages.extend(self._apply_effect(eff))

        if choice.branch is not None:
            taken_true = self._evaluate_condition(choice.branch.get("condition", {}))
            target = choice.branch.get("if_true" if taken_true else "if_false")
            if isinstance(target, dict):
                messages.extend(self._apply_effect(target))

        for eff in choice.effects:
            messages.extend(self._apply_effect(eff))

        self.encounter.message = "\n".join(m for m in messages if m)
        self.encounter.resolved = True

        if self.state == GameState.COMBAT:
            self._consume_encounter_marker()
            self.encounter = None

    def _close_encounter(self) -> None:
        self._consume_encounter_marker()
        if self.encounter is not None:
            for line in (self.encounter.message or "").split("\n"):
                self.add_log(line)
        self.encounter = None
        self.state = GameState.EXPLORE

    def _consume_encounter_marker(self) -> None:
        if self.encounter is None or self.dungeon is None:
            return
        m = self.encounter.marker
        m.triggered = True
        self.dungeon.tiles[m.x, m.y] = tile_mod.floor

    def _run_check(self, check_data: dict) -> tuple[bool, str]:
        ability = check_data["ability"]
        dc = int(check_data["dc"])
        result = d20(self.player.mod(ability))
        success = result.total >= dc
        verdict = "успех" if success else "провал"
        return success, f"Проверка {ability.upper()} DC {dc}: {result} → {verdict}."

    def _evaluate_condition(self, cond: dict) -> bool:
        if cond.get("type") == "random":
            return get_rng().random() < float(cond.get("chance", 0.5))
        return False

    def _apply_effect(self, eff: dict) -> list[str]:
        msgs: list[str] = []
        etype = eff.get("type")

        if etype == "damage":
            dmg = roll(eff["amount"])
            actual = self.player.take_damage(dmg.total)
            msgs.append(f"Ты получаешь {actual} урона {dmg}.")
            if not self.player.is_alive:
                self.state = GameState.GAME_OVER
                save_mod.delete_save()

        elif etype == "heal":
            h = roll(eff["amount"])
            actual = self.player.heal(h.total)
            msgs.append(f"Восстановлено {actual} HP {h}.")

        elif etype == "give_xp":
            amount = int(eff["amount"])
            leveled = self.player.gain_xp(amount)
            msgs.append(f"Получено {amount} опыта.")
            if leveled:
                msgs.append(f"Уровень повышен! Теперь {self.player.level}.")

        elif etype == "give_gold":
            amount = int(eff["amount"])
            self.player.inventory.gold += amount
            msgs.append(f"Получено {amount} зм.")

        elif etype == "spend_gold":
            amount = int(eff["amount"])
            self.player.inventory.gold = max(0, self.player.inventory.gold - amount)
            msgs.append(f"Потрачено {amount} зм.")

        elif etype == "give_item":
            item_id = eff["item"]
            cons = self.consumables_by_id.get(item_id)
            if cons is not None:
                self.player.inventory.consumables.append(cons)
                msgs.append(f"Получено: {cons.name_ru}.")

        elif etype == "remove_item":
            item_id = eff["item"]
            for c in self.player.inventory.consumables:
                if c.id == item_id:
                    self.player.inventory.consumables.remove(c)
                    msgs.append(f"Отдано: {c.name_ru}.")
                    break

        elif etype == "buff":
            if eff.get("name") == "blessed":
                self.player.blessed_turns = int(eff.get("duration", 10))
                msgs.append(
                    f"Благословение: +2 к атакам на {self.player.blessed_turns} ходов боя."
                )

        elif etype == "short_rest":
            hd = roll("1d10")
            healed = self.player.heal(hd.total + self.player.mod("con"))
            msgs.append(f"Короткий привал: +{healed} HP {hd}+ТЕЛ.")

        elif etype == "spawn_combat":
            monster_id = eff["monster"]
            label = eff.get("label", "")
            m = spawn_monster(monster_id, self.player.x, self.player.y)
            if label:
                m.name_ru = f"{label.capitalize()} ({m.name_ru})"
            self.start_combat([m])

        elif etype == "give_loot":
            rng = get_rng()
            gold = rng.randint(10, 30)
            self.player.inventory.gold += gold
            msgs.append(f"В сундуке золото: +{gold} зм.")
            roll_r = rng.random()
            if roll_r < 0.35:
                pot = self.consumables_by_id["healing_potion"]
                self.player.inventory.consumables.append(pot)
                msgs.append(f"А ещё: {pot.name_ru}.")
            elif roll_r < 0.55:
                scroll_id = rng.choice([
                    "scroll_magic_missile", "scroll_ray_of_frost", "scroll_shield"
                ])
                sc = self.consumables_by_id[scroll_id]
                self.player.inventory.consumables.append(sc)
                msgs.append(f"А ещё: {sc.name_ru}.")

        return msgs

    # ── Inventory actions ─────────────────────────────────────────────────

    def inventory_items_flat(self) -> list[tuple[str, object]]:
        items: list[tuple[str, object]] = []
        for w in self.player.inventory.weapons:
            items.append(("weapon", w))
        for a in self.player.inventory.armors:
            items.append(("armor", a))
        for c in self.player.inventory.consumables:
            items.append(("consumable", c))
        return items

    def inventory_use(self, index: int) -> str | None:
        items = self.inventory_items_flat()
        if not (0 <= index < len(items)):
            return None
        kind, obj = items[index]
        if kind == "weapon":
            return self._equip_weapon(obj)  # type: ignore[arg-type]
        if kind == "armor":
            return self._equip_armor(obj)  # type: ignore[arg-type]
        if kind == "consumable":
            return self._use_consumable_outside_combat(obj)  # type: ignore[arg-type]
        return None

    def _equip_weapon(self, weapon: Weapon) -> str:
        if self.player.equipped_weapon is weapon:
            return f"{weapon.name_ru} уже экипировано."
        old = self.player.equipped_weapon
        self.player.equipped_weapon = weapon
        if old is not None:
            self.player.inventory.weapons.append(old)
        try:
            self.player.inventory.weapons.remove(weapon)
        except ValueError:
            pass
        msg = f"Экипировано: {weapon.name_ru}."
        self.add_log(msg)
        return msg

    def _equip_armor(self, armor: Armor) -> str:
        slot = "equipped_shield" if armor.type == "shield" else "equipped_armor"
        old: Armor | None = getattr(self.player, slot)
        if old is armor:
            return f"{armor.name_ru} уже экипировано."
        setattr(self.player, slot, armor)
        if old is not None:
            self.player.inventory.armors.append(old)
        try:
            self.player.inventory.armors.remove(armor)
        except ValueError:
            pass
        msg = f"Экипировано: {armor.name_ru}."
        self.add_log(msg)
        return msg

    def _use_consumable_outside_combat(self, c: Consumable) -> str:
        if c.effect == "heal":
            r = roll(c.amount)
            healed = self.player.heal(r.total)
            if healed == 0:
                return "Здоровье уже полное."
            self.player.inventory.consumables.remove(c)
            msg = f"Использовано {c.name_ru}: +{healed} HP {r}."
            self.add_log(msg)
            return msg
        if c.effect == "shield":
            self.player.shield_active = True
            self.player.inventory.consumables.remove(c)
            msg = f"Зачитан «{c.name_ru}»: следующая атака провалится."
            self.add_log(msg)
            return msg
        if c.effect in ("magic_missile", "ray_of_frost"):
            return f"{c.name_ru} можно использовать только в бою."
        return "Этим нельзя пользоваться сейчас."
