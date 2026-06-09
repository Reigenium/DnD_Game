"""Modal JRPG combat screen.

Layout (80×50 console):
  [0-1]   Title bar
  [2-10]  Enemy list with HP bars, poise, intents, status tags
  [11-13] Timeline strip (next 7 actors)
  [14]    separator
  [15-19] Player block: name, HP, Focus, statuses
  [20]    separator
  [21-30] Action menu OR item picker
  [31]    separator
  [32-49] Combat log (last 17 lines)
"""
from __future__ import annotations

from tcod.console import Console

from .. import colors as col


# ── Intent display ───────────────────────────────────────────────────────────

_INTENT_LABELS: dict[str, str] = {
    "attack":       "⚔ АТАКА",
    "heavy_attack": "💥 ТЯЖ.УДАР",
    "defend":       "🛡 ЗАЩИТА",
    "heal":         "💊 ЛЕЧЕНИЕ",
    "": "",
}


def render_combat(console: Console, game) -> None:
    combat = game.combat
    player = game.player

    console.draw_frame(0, 0, 80, 50, clear=True, fg=col.WHITE)
    title = " БОЙ "
    console.print((80 - len(title)) // 2, 0, title, fg=col.TITLE_FG)

    # ── Enemy list ────────────────────────────────────────────────────────
    console.print(2, 2, "Противники: [T] цикл  [1-3] выбор", fg=col.TITLE_FG)
    y = 3
    alive_only = combat.alive_enemies
    for i, e in enumerate(combat.enemies):
        if not e.is_alive:
            console.print(2, y, f"     {e.name_ru} — повержен", fg=col.DIM)
            y += 1
            continue

        is_target = (e is combat.current_target)
        marker = ">" if is_target else " "
        try:
            live_idx = alive_only.index(e)
            idx_label = f"[{live_idx + 1}]"
        except ValueError:
            idx_label = "[ ]"

        hp_bar = _bar(e.current_hp, e.max_hp, 12)

        # Status tags.
        tags = []
        if e.has_status("frozen"):
            tags.append("❄")
        if e.has_status("stunned"):
            tags.append("⚡")
        if e.has_status("staggered"):
            tags.append("★ПЕРЕЛОМ")
        if e.has_status("enraged"):
            tags.append("ЯРОСТЬ")
        if e.has_status("burning"):
            tags.append("🔥")
        if e.has_status("poisoned"):
            tags.append("☠")
        if "pack_tactics" in e.traits and len(alive_only) > 1:
            tags.append("СТАЯ")
        tag_str = " " + " ".join(tags) if tags else ""

        # Intent.
        intent_str = _INTENT_LABELS.get(e.current_intent, e.current_intent)
        if intent_str:
            intent_str = f" │{intent_str}"

        # Poise bar.
        poise_str = ""
        if e.max_poise > 0:
            poise_bar = _bar(e.poise, e.max_poise, 6)
            poise_str = f" Ст[{poise_bar}]"

        line = (
            f"{marker} {idx_label} {e.name_ru:<12} "
            f"HP {e.current_hp:>3}/{e.max_hp:<3} {hp_bar}"
            f"{poise_str}{tag_str}{intent_str}"
        )

        if e.has_status("staggered"):
            line_fg = col.ORANGE
        elif e.has_status("enraged"):
            line_fg = col.RED
        elif "pack_tactics" in e.traits and len(alive_only) > 1:
            line_fg = col.ORANGE
        else:
            line_fg = tuple(e.color)

        console.print(2, y, line[:76], fg=line_fg if is_target else _dim(line_fg))
        y += 1

    # ── Timeline strip ────────────────────────────────────────────────────
    tl_y = 11
    console.print(2, tl_y, "Следующий ход:", fg=col.TITLE_FG)
    try:
        preview = combat.turn_order.preview_next_n(7)
        strip_parts: list[str] = []
        strip_colors: list[tuple[int, int, int]] = []
        for actor in preview:
            if actor is player:
                strip_parts.append("[ТЫ]")
                strip_colors.append(col.YELLOW)
            else:
                from ...entities.monster import Monster
                if isinstance(actor, Monster) and actor.is_alive:
                    name = actor.name_ru[:6]
                    strip_parts.append(f"[{name}]")
                    strip_colors.append(tuple(actor.color))
        x_offset = 18
        for part, color in zip(strip_parts, strip_colors):
            console.print(x_offset, tl_y, part, fg=color)
            x_offset += len(part) + 1
    except Exception:
        pass

    console.draw_rect(2, 13, 76, 1, ord("─"), fg=col.DIM)

    # ── Player block ──────────────────────────────────────────────────────
    py = 14
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
    hp_bar = _bar(player.current_hp, player.max_hp, 20)
    console.print(
        2, py + 2,
        f"HP {player.current_hp:>3}/{player.max_hp:<3}  AC {player.ac}   {hp_bar}",
        fg=hp_color,
    )

    # Focus bar.
    focus_bar = _bar(player.focus, player.focus_max, 10)
    console.print(
        2, py + 3,
        f"Фокус {player.focus}/{player.focus_max} [{focus_bar}]",
        fg=col.CYAN,
    )

    # Status icons.
    extras = []
    if player.dodge_active:
        extras.append("[уклон]")
    if player.shield_active:
        extras.append("[щит]")
    if player.blessed_turns > 0:
        extras.append(f"[благ.{player.blessed_turns}]")
    if player.has_status("riposte"):
        extras.append("[РИПОСТ]")
    if player.has_status("burning"):
        extras.append("[🔥ожог]")
    if player.has_status("poisoned"):
        extras.append("[☠яд]")
    if combat.extra_actions > 0:
        extras.append("[SURGE!]")
    if extras:
        console.print(2, py + 4, "  ".join(extras), fg=col.CYAN)

    console.draw_rect(2, 20, 76, 1, ord("─"), fg=col.DIM)

    # ── Action menu / item picker ─────────────────────────────────────────
    if game.combat_item_menu_open:
        _render_item_picker(console, game, top_y=21)
    else:
        _render_action_menu(console, game, top_y=21)

    # ── Combat log ────────────────────────────────────────────────────────
    ly = 32
    console.draw_rect(2, ly, 76, 1, ord("─"), fg=col.DIM)
    console.print(2, ly, " Лог боя ", fg=col.TITLE_FG)
    log_lines = combat.log[-16:]
    for i, line in enumerate(log_lines):
        fg = col.LIGHT_GRAY if i == len(log_lines) - 1 else col.GRAY
        console.print(2, ly + 1 + i, line[:76], fg=fg)


def _render_action_menu(console: Console, game, top_y: int) -> None:
    player = game.player
    combat = game.combat
    console.print(2, top_y, "Действия:", fg=col.TITLE_FG)

    pots_n = sum(1 for c in player.inventory.consumables if c.effect == "heal")
    scrolls_n = sum(1 for c in player.inventory.consumables if c.effect != "heal")
    sw_used = player.second_wind_used
    sw_desc = "уже использовано" if sw_used else f"лечение 1d10+{player.level}"
    surge_available = player.level >= 2 and not player.has_status("action_surge_used")
    surge_desc = "доп. действие 1×/бой" if surge_available else "(использован)"
    atk_desc = f"атака {player.attacks_per_action}× по цели"

    focus = player.focus
    sweep_ok = focus >= 2
    riposte_ok = focus >= 1
    trip_ok = focus >= 1

    items = [
        ("[A]", "Атака",      atk_desc,                                                col.LIGHT_GRAY),
        ("[W]", "Размах",     f"все враги, пол-урона доп. (нужно 2 Ф, есть {focus})",  col.CYAN if sweep_ok else col.DIM),
        ("[R]", "Рипост",     f"контратака при уд. по тебе (нужно 1 Ф, есть {focus})", col.CYAN if riposte_ok else col.DIM),
        ("[P]", "Подсечка",   f"атака+оглушение СИЛ DC13 (нужно 1 Ф, есть {focus})",  col.CYAN if trip_ok else col.DIM),
        ("[U]", "Surge",      surge_desc,                                               col.ORANGE if surge_available else col.DIM),
        ("[D]", "Защита",     "атаки по тебе с помехой",                               col.LIGHT_GRAY),
        ("[S]", "2-е дых.",   sw_desc,                                                  col.DIM if sw_used else col.CYAN),
        ("[I]", "Предмет",    f"({pots_n} зелий, {scrolls_n} свитков)",                col.LIGHT_GRAY),
        ("[T]", "Цель",       "цикл / 1-3 прямой",                                     col.LIGHT_GRAY),
        ("[F]", "Побег",      "ЛВК vs DC",                                             col.LIGHT_GRAY),
    ]
    for i, (key, name, desc, fg) in enumerate(items):
        if top_y + 1 + i > 30:
            break
        console.print(2, top_y + 1 + i, f"{key} {name:<10} {desc}", fg=fg)


def _render_item_picker(console: Console, game, top_y: int) -> None:
    player = game.player
    console.print(2, top_y, "Выбери предмет (Esc / I — отмена):", fg=col.TITLE_FG)
    cons = player.inventory.consumables
    if not cons:
        console.print(2, top_y + 1, "— инвентарь пуст —", fg=col.DIM)
        return
    for i, c in enumerate(cons):
        if i >= 9 or top_y + 1 + i > 30:
            break
        key = f"[{i + 1}]"
        hint = {
            "magic_missile": "→ волш. стрелы (3 атаки)",
            "ray_of_frost":  "→ 1d8 холод + заморозка",
            "shield":        "→ щит: блок след. атаки",
            "heal":          f"→ лечение {c.amount}",
        }.get(c.effect, "")
        fg = col.CYAN if c.effect != "heal" else col.LIGHT_GRAY
        console.print(2, top_y + 1 + i, f"{key} {c.name_ru}  {hint}"[:76], fg=fg)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bar(current: int, maximum: int, width: int) -> str:
    if maximum <= 0:
        return "─" * width
    filled = max(0, min(width, int(width * current / maximum)))
    return "█" * filled + "░" * (width - filled)


def _dim(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return (color[0] // 2, color[1] // 2, color[2] // 2)
