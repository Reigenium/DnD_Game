"""Keyboard input → game-controller calls."""
from __future__ import annotations

import time

import tcod.event

from ..game import save as save_mod
from ..game.state import Game, GameState

MOVE_KEYS = {
    tcod.event.KeySym.UP: (0, -1),
    tcod.event.KeySym.DOWN: (0, 1),
    tcod.event.KeySym.LEFT: (-1, 0),
    tcod.event.KeySym.RIGHT: (1, 0),
    tcod.event.KeySym.K: (0, -1),
    tcod.event.KeySym.J: (0, 1),
    tcod.event.KeySym.H: (-1, 0),
    tcod.event.KeySym.L: (1, 0),
    tcod.event.KeySym.Y: (-1, -1),
    tcod.event.KeySym.U: (1, -1),
    tcod.event.KeySym.B: (-1, 1),
    tcod.event.KeySym.N: (1, 1),
    tcod.event.KeySym.PERIOD: (0, 0),
}

NUM_KEYS = {
    tcod.event.KeySym.N1: 0,
    tcod.event.KeySym.N2: 1,
    tcod.event.KeySym.N3: 2,
    tcod.event.KeySym.N4: 3,
    tcod.event.KeySym.N5: 4,
    tcod.event.KeySym.N6: 5,
    tcod.event.KeySym.N7: 6,
    tcod.event.KeySym.N8: 7,
    tcod.event.KeySym.N9: 8,
}

LETTER_KEYS = {
    tcod.event.KeySym.A: "a", tcod.event.KeySym.B: "b", tcod.event.KeySym.C: "c",
    tcod.event.KeySym.D: "d", tcod.event.KeySym.E: "e", tcod.event.KeySym.F: "f",
    tcod.event.KeySym.G: "g", tcod.event.KeySym.H: "h", tcod.event.KeySym.I: "i",
    tcod.event.KeySym.J: "j", tcod.event.KeySym.K: "k", tcod.event.KeySym.L: "l",
    tcod.event.KeySym.M: "m", tcod.event.KeySym.N: "n", tcod.event.KeySym.O: "o",
    tcod.event.KeySym.P: "p", tcod.event.KeySym.Q: "q", tcod.event.KeySym.R: "r",
    tcod.event.KeySym.S: "s", tcod.event.KeySym.T: "t", tcod.event.KeySym.U: "u",
    tcod.event.KeySym.V: "v", tcod.event.KeySym.W: "w", tcod.event.KeySym.X: "x",
    tcod.event.KeySym.Y: "y", tcod.event.KeySym.Z: "z",
}

TEXT_INPUT_DEDUP_WINDOW = 0.05


def _shift_held(event_mod) -> bool:
    shift_bits = (
        tcod.event.Modifier.SHIFT
        | tcod.event.Modifier.LSHIFT
        | tcod.event.Modifier.RSHIFT
    )
    return bool(event_mod & shift_bits)


def handle_event(event: tcod.event.Event, game: Game) -> str | None:
    if isinstance(event, tcod.event.Quit):
        if game.state == GameState.EXPLORE:
            game.save()
        return "quit"

    if game.state == GameState.NAME_ENTRY:
        return _handle_name_entry(event, game)

    if not isinstance(event, tcod.event.KeyDown):
        return None
    sym = event.sym

    if game.state == GameState.EXPLORE:
        return _handle_explore(sym, event, game)
    if game.state == GameState.COMBAT:
        return _handle_combat(sym, game)
    if game.state == GameState.ENCOUNTER:
        return _handle_encounter(sym, game)
    if game.state == GameState.STAIRS_PROMPT:
        return _handle_stairs_prompt(sym, game)
    if game.state == GameState.INVENTORY:
        return _handle_inventory(sym, game)
    if game.state == GameState.CHARACTER:
        return _handle_character(sym, game)
    if game.state == GameState.LEVEL_UP:
        return _handle_levelup(sym, game)
    if game.state == GameState.GAME_OVER:
        return _handle_game_over(sym, game)
    return None


def _handle_name_entry(event, game: Game) -> str | None:
    if isinstance(event, tcod.event.TextInput):
        game.name_entry_add(event.text)
        game.last_text_input_at = time.monotonic()
        return None
    if isinstance(event, tcod.event.KeyDown):
        sym = event.sym
        if sym == tcod.event.KeySym.RETURN:
            game.name_entry_confirm()
            return None
        if sym == tcod.event.KeySym.BACKSPACE:
            game.name_entry_backspace()
            return None
        if sym == tcod.event.KeySym.ESCAPE:
            return "quit"
        if sym in LETTER_KEYS or sym == tcod.event.KeySym.SPACE:
            if time.monotonic() - game.last_text_input_at < TEXT_INPUT_DEDUP_WINDOW:
                return None
            ch = " " if sym == tcod.event.KeySym.SPACE else LETTER_KEYS[sym]
            if _shift_held(event.mod) and ch.isalpha():
                ch = ch.upper()
            game.name_entry_add(ch)
    return None


def _handle_explore(sym, event, game: Game) -> str | None:
    if sym in MOVE_KEYS:
        is_repeat = bool(getattr(event, "repeat", False))
        dx, dy = MOVE_KEYS[sym]
        game.move_player(dx, dy, is_repeat=is_repeat)
        return None
    if sym == tcod.event.KeySym.G:
        game.pick_up_item()
        return None
    if sym == tcod.event.KeySym.I:
        game.open_inventory()
        return None
    if sym == tcod.event.KeySym.C:
        game.open_character()
        return None
    if sym in (tcod.event.KeySym.Q, tcod.event.KeySym.ESCAPE):
        game.save()
        return "quit"
    return None


def _handle_combat(sym, game: Game) -> str | None:
    if game.combat_item_menu_open:
        if sym == tcod.event.KeySym.ESCAPE or sym == tcod.event.KeySym.I:
            game.combat_item_menu_open = False
            return None
        if sym in NUM_KEYS:
            idx = NUM_KEYS[sym]
            cons = game.player.inventory.consumables
            if idx < len(cons):
                game.combat_action("item", cons[idx])
        return None

    if sym == tcod.event.KeySym.A:
        game.combat_action("attack")
    elif sym == tcod.event.KeySym.D:
        game.combat_action("dodge")
    elif sym == tcod.event.KeySym.S:
        game.combat_action("second_wind")
    elif sym == tcod.event.KeySym.W:
        game.combat_action("sweep")
    elif sym == tcod.event.KeySym.R:
        game.combat_action("riposte")
    elif sym == tcod.event.KeySym.P:
        game.combat_action("trip")
    elif sym == tcod.event.KeySym.U:
        # U is used for diagonal movement in explore; in combat → action surge.
        game.combat_action("action_surge")
    elif sym == tcod.event.KeySym.T:
        game.combat_action("cycle_target")
    elif sym == tcod.event.KeySym.F:
        game.combat_action("flee")
    elif sym == tcod.event.KeySym.I:
        if game.player.inventory.consumables:
            game.toggle_combat_item_menu()
    elif sym in NUM_KEYS:
        idx = NUM_KEYS[sym]
        if game.combat and idx < len(game.combat.alive_enemies):
            game.combat_action("select_target", idx)
    return None


def _handle_encounter(sym, game: Game) -> str | None:
    if game.encounter is None:
        return None
    if game.encounter.resolved:
        if sym in (
            tcod.event.KeySym.RETURN,
            tcod.event.KeySym.SPACE,
            tcod.event.KeySym.ESCAPE,
        ):
            game.encounter_choose(-1)
        return None
    if sym in NUM_KEYS:
        idx = NUM_KEYS[sym]
        if idx < len(game.encounter.definition.choices):
            game.encounter_choose(idx)
    return None


def _handle_stairs_prompt(sym, game: Game) -> str | None:
    if sym in (tcod.event.KeySym.Y, tcod.event.KeySym.RETURN, tcod.event.KeySym.SPACE):
        game.confirm_descent()
    elif sym in (tcod.event.KeySym.N, tcod.event.KeySym.ESCAPE):
        game.decline_descent()
    return None


def _handle_inventory(sym, game: Game) -> str | None:
    if sym in (tcod.event.KeySym.ESCAPE, tcod.event.KeySym.I):
        game.close_modal()
        return None
    if sym == tcod.event.KeySym.C:
        game.state = GameState.CHARACTER
        return None
    if sym in NUM_KEYS:
        idx = NUM_KEYS[sym]
        game.inventory_use(idx)
    return None


def _handle_character(sym, game: Game) -> str | None:
    if sym in (tcod.event.KeySym.ESCAPE, tcod.event.KeySym.C):
        game.close_modal()
        return None
    if sym == tcod.event.KeySym.I:
        game.state = GameState.INVENTORY
        return None
    return None


def _handle_levelup(sym, game: Game) -> str | None:
    if sym in NUM_KEYS:
        idx = NUM_KEYS[sym]
        game.levelup_choose(idx)
    return None


def _handle_game_over(sym, game: Game) -> str | None:
    if sym == tcod.event.KeySym.R:
        game.restart()
        return None
    if sym in (
        tcod.event.KeySym.Q,
        tcod.event.KeySym.ESCAPE,
        tcod.event.KeySym.RETURN,
        tcod.event.KeySym.SPACE,
    ):
        save_mod.delete_save()
        return "quit"
    return None
