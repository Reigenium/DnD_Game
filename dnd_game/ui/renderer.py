"""Top-level renderer. Dispatches per game state to the right screen."""
from __future__ import annotations

import numpy as np
from tcod.console import Console

from ..game.state import Game, GameState
from ..world.tile import SHROUD
from . import colors as col
from .screens.character_screen import render_character
from .screens.combat_screen import render_combat
from .screens.encounter_screen import render_encounter
from .screens.inventory_screen import render_inventory
from .screens.levelup_screen import render_levelup
from .screens.name_entry_screen import render_name_entry
from .screens.stairs_prompt_screen import render_stairs_prompt

MAP_WIDTH = 80
MAP_HEIGHT = 43


def render(console: Console, game: Game) -> None:
    console.clear()

    if game.state == GameState.NAME_ENTRY:
        render_name_entry(console, game)
        return

    if game.state == GameState.COMBAT and game.combat is not None:
        render_combat(console, game)
        return

    # Explore-like states all show the map + HUD + log underneath any modal.
    _render_map(console, game)
    _render_hud(console, game)
    _render_log(console, game)

    if game.state == GameState.ENCOUNTER and game.encounter is not None:
        render_encounter(console, game)
    elif game.state == GameState.STAIRS_PROMPT:
        render_stairs_prompt(console, game)
    elif game.state == GameState.INVENTORY:
        render_inventory(console, game)
    elif game.state == GameState.CHARACTER:
        render_character(console, game)
    elif game.state == GameState.LEVEL_UP:
        render_levelup(console, game)
    elif game.state == GameState.GAME_OVER:
        _render_game_over(console)


def _render_map(console: Console, game: Game) -> None:
    d = game.dungeon
    if d is None:
        return
    display = np.select(
        condlist=[d.visible, d.explored],
        choicelist=[d.tiles["light"], d.tiles["dark"]],
        default=SHROUD,
    )
    console.rgb[0:d.width, 0:d.height] = display

    # Loot items on floor.
    for loot in d.loot:
        if d.visible[loot.x, loot.y]:
            console.print(loot.x, loot.y, "$", fg=col.GOLD)

    # Revealed traps.
    for tx, ty in d._traps_revealed:
        if d.visible[tx, ty] or d.explored[tx, ty]:
            console.print(tx, ty, "^", fg=col.RED)

    for m in d.monsters:
        if m.is_alive and d.visible[m.x, m.y]:
            console.print(m.x, m.y, m.char, fg=m.color)

    console.print(game.player.x, game.player.y, "@", fg=col.PLAYER_FG)


def _hp_color(current: int, maximum: int):
    if maximum <= 0:
        return col.HP_FG
    frac = current / maximum
    if frac > 0.6:
        return col.HP_FG
    if frac > 0.3:
        return col.HP_MID_FG
    return col.HP_LOW_FG


def _render_hud(console: Console, game: Game) -> None:
    p = game.player
    y = MAP_HEIGHT
    console.draw_rect(0, y, 80, 1, ord("─"), fg=col.DIM)

    pots = sum(1 for c in p.inventory.consumables if c.effect == "heal")
    scrolls = sum(1 for c in p.inventory.consumables if c.effect != "heal")

    console.print(
        1, y + 1,
        f"{p.name} — {p.class_name_ru} ур.{p.level}   Этаж {game.floor}",
        fg=col.TITLE_FG,
    )

    hp_color = _hp_color(p.current_hp, p.max_hp)
    hp_text = f"HP {p.current_hp:>3}/{p.max_hp:<3}"
    console.print(1, y + 2, hp_text, fg=hp_color)

    bar_x, bar_w = 14, 18
    console.draw_rect(bar_x, y + 2, bar_w, 1, ord("·"), fg=col.HP_BG)
    if p.max_hp > 0:
        filled = max(0, int(bar_w * p.current_hp / p.max_hp))
        if filled > 0:
            console.draw_rect(bar_x, y + 2, filled, 1, ord("█"), fg=hp_color)

    console.print(36, y + 1, f"AC {p.ac}", fg=col.LIGHT_GRAY)
    console.print(36, y + 2, f"XP {p.xp}/{p.xp_to_next}", fg=col.LIGHT_GRAY)
    focus_bar = "█" * p.focus + "░" * (p.focus_max - p.focus)
    console.print(46, y + 1, f"Золото: {p.inventory.gold} зм", fg=col.GOLD)
    console.print(46, y + 2, f"Фокус [{focus_bar}] {p.focus}/{p.focus_max}", fg=col.CYAN)
    console.print(64, y + 1, f"Зелья:{pots} Св:{scrolls}", fg=col.LIGHT_GRAY)
    console.print(
        1, y + 3,
        "hjkl/стрелки · yubn-диаг · g-лут · i-инв · c-лист · q-выход",
        fg=col.DIM,
    )


def _render_log(console: Console, game: Game) -> None:
    y0 = 47
    lines = game.message_log[-3:]
    for i, line in enumerate(lines):
        fg = col.LIGHT_GRAY if i == len(lines) - 1 else col.GRAY
        console.print(1, y0 + i, line[:78], fg=fg)


def _render_game_over(console: Console) -> None:
    box_x, box_y, box_w, box_h = 22, 19, 36, 9
    console.draw_frame(box_x, box_y, box_w, box_h, clear=True, fg=col.RED)
    title = " ТЫ ПАЛ В ПОДЗЕМЕЛЬЕ "
    console.print(box_x + (box_w - len(title)) // 2, box_y, title, fg=col.RED)
    msg = "Permadeath: забег окончен."
    sub1 = "[R] — новый забег"
    sub2 = "[Q] / [Esc] — выйти"
    console.print(box_x + (box_w - len(msg)) // 2, box_y + 2, msg, fg=col.LIGHT_GRAY)
    console.print(box_x + (box_w - len(sub1)) // 2, box_y + 4, sub1, fg=col.GOLD)
    console.print(box_x + (box_w - len(sub2)) // 2, box_y + 5, sub2, fg=col.DIM)
