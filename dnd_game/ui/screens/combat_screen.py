"""Modal JRPG combat screen with item picker submenu."""
from __future__ import annotations

from tcod.console import Console

from .. import colors as col


def render_combat(console: Console, game) -> None:
    combat = game.combat
    player = game.player

    console.draw_frame(0, 0, 80, 50, clear=True, fg=col.WHITE)
    title = " БОЙ "
    console.print((80 - len(title)) // 2, 0, title, fg=col.TITLE_FG)

    # ---- Enemy list (numbered) ----
    console.print(2, 2, "Противники: [T] цикл  [1-3] выбор", fg=col.TITLE_FG)
    y = 3
    alive_only = combat.alive_enemies
    for i, e in enumerate(combat.enemies):
        if not e.is_alive:
            console.print(2, y, f"     {e.name_ru} — повержен", fg=col.DIM)
        else:
            is_target = (e is combat.current_target)
            marker = ">" if is_target else " "
            # Determine enemy index among living
            try:
                live_idx = alive_only.index(e)
                idx_label = f"[{live_idx + 1}]"
            except ValueError:
                idx_label = "[ ]"
            bar = _bar(e.current_hp, e.max_hp, 14)
            fg = e.color if is_target else _dim(e.color)
            tags = []
            if e.frozen_turns > 0:
                tags.append("❄")
            if e.enraged:
                tags.append("ЯРОСТЬ")
            if "pack_tactics" in e.traits and len(combat.alive_enemies) > 1:
                tags.append("СТАЯ")
            tag_str = "  " + " ".join(tags) if tags else ""
            line = (
                f"{marker} {idx_label} {e.name_ru:<14} HP {e.current_hp:>3}/{e.max_hp:<3} "
                f"AC {e.ac:<2} {bar}{tag_str}"
            )
            line_fg = col.RED if e.enraged else (col.ORANGE if "pack_tactics" in e.traits and len(combat.alive_enemies) > 1 else fg)
            console.print(2, y, line[:76], fg=line_fg if is_target else _dim(line_fg))
        y += 1

    # ---- Player block ----
    py = 16
    console.print(2, py, "Ты:", fg=col.TITLE_FG)
    weapon_name = player.equipped_weapon.name_ru if player.equipped_weapon else "—"
    console.print(
        2, py + 1,
        f"{player.name} ({player.class_name_ru} ур.{player.level})  Оружие: {weapon_name}",
        fg=col.YELLOW,
    )
    hp_color = (
        col.HP_FG if player.current_hp > player.max_hp * 0.6
        else col.HP_MID_FG if player.current_hp > player.max_hp * 0.3
        else col.HP_LOW_FG
    )
    bar = _bar(player.current_hp, player.max_hp, 24)
    console.print(
        2, py + 2,
        f"HP {player.current_hp:>3}/{player.max_hp:<3}  AC {player.ac}   {bar}",
        fg=hp_color,
    )
    extras = []
    if player.dodge_active:
        extras.append("[защита]")
    if player.shield_active:
        extras.append("[магич. щит]")
    if player.blessed_turns > 0:
        extras.append(f"[благ. {player.blessed_turns}]")
    if extras:
        console.print(2, py + 3, "  ".join(extras), fg=col.CYAN)

    # ---- Action menu / item picker ----
    if game.combat_item_menu_open:
        _render_item_picker(console, game, top_y=21)
    else:
        _render_action_menu(console, game, top_y=21)

    # ---- Combat log ----
    ly = 32
    console.draw_rect(2, ly, 76, 1, ord("─"), fg=col.DIM)
    console.print(2, ly, " Лог боя ", fg=col.TITLE_FG)
    log_lines = combat.log[-15:]
    for i, line in enumerate(log_lines):
        fg = col.LIGHT_GRAY if i == len(log_lines) - 1 else col.GRAY
        console.print(2, ly + 1 + i, line[:76], fg=fg)


def _render_action_menu(console: Console, game, top_y: int) -> None:
    player = game.player
    console.print(2, top_y, "Действия:", fg=col.TITLE_FG)
    pots_n = sum(1 for c in player.inventory.consumables if c.effect == "heal")
    scrolls_n = sum(1 for c in player.inventory.consumables if c.effect != "heal")
    sw_used = player.second_wind_used
    sw_desc = "уже использовано в этом бою" if sw_used else f"лечение 1d10+{player.level} HP"
    items = [
        ("[A]", "Атака",          "по выбранной цели",                            col.LIGHT_GRAY),
        ("[D]", "Защита",         "уклонение — атаки по тебе с помехой",           col.LIGHT_GRAY),
        ("[S]", "2-е дыхание",    sw_desc,                                         col.DIM if sw_used else col.CYAN),
        ("[I]", "Предмет",        f"открыть ({pots_n} зелий, {scrolls_n} свитков)", col.LIGHT_GRAY),
        ("[T]", "Цель",           "переключить (или 1-3 — прямой выбор)",           col.LIGHT_GRAY),
        ("[F]", "Побег",          "проверка ЛВК vs DC",                            col.LIGHT_GRAY),
    ]
    for i, (key, name, desc, fg) in enumerate(items):
        console.print(2, top_y + 1 + i, f"{key} {name:<14} — {desc}", fg=fg)


def _render_item_picker(console: Console, game, top_y: int) -> None:
    player = game.player
    console.print(2, top_y, "Выбери предмет (Esc / I — отмена):", fg=col.TITLE_FG)
    cons = player.inventory.consumables
    if not cons:
        console.print(2, top_y + 1, "— инвентарь пуст —", fg=col.DIM)
        return
    shown = 0
    seen_ids: dict[str, int] = {}
    for i, c in enumerate(cons):
        if shown >= 9:
            break
        key = f"[{i + 1}]"
        effect_hint = ""
        if c.effect == "magic_missile":
            effect_hint = "  → волш. стрелы (3 атаки, 3d4+3)"
        elif c.effect == "ray_of_frost":
            effect_hint = "  → 1d8 холода + заморозка"
        elif c.effect == "shield":
            effect_hint = "  → щит: блок след. атаки"
        elif c.effect == "heal":
            effect_hint = f"  → лечение {c.amount}"
        line = f"{key} {c.name_ru}{effect_hint}"
        console.print(2, top_y + 1 + shown, line[:76], fg=col.CYAN if c.effect != "heal" else col.LIGHT_GRAY)
        shown += 1
        seen_ids[c.id] = i


def _bar(current: int, maximum: int, width: int) -> str:
    if maximum <= 0:
        return "─" * width
    filled = max(0, min(width, int(width * current / maximum)))
    return "█" * filled + "░" * (width - filled)


def _dim(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return (color[0] // 2, color[1] // 2, color[2] // 2)
