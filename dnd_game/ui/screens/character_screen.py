"""Modal character sheet — read-only stats overview."""
from __future__ import annotations

from tcod.console import Console

from ...rules.ability import ABILITY_NAMES_RU
from .. import colors as col


def render_character(console: Console, game) -> None:
    p = game.player

    box_x, box_y, box_w, box_h = 10, 3, 60, 40
    console.draw_frame(box_x, box_y, box_w, box_h, clear=True, fg=col.YELLOW)
    title = " ЛИСТ ПЕРСОНАЖА "
    console.print(box_x + (box_w - len(title)) // 2, box_y, title, fg=col.GOLD)

    y = box_y + 2
    console.print(box_x + 2, y, p.name, fg=col.YELLOW)
    y += 1
    console.print(
        box_x + 2, y,
        f"{p.class_name_ru} — уровень {p.level}   Этаж {game.floor}",
        fg=col.LIGHT_GRAY,
    )
    y += 1
    console.print(
        box_x + 2, y,
        f"XP {p.xp}/{p.xp_to_next}   Proficiency Bonus +{p.proficiency_bonus}",
        fg=col.LIGHT_GRAY,
    )
    y += 2

    console.print(box_x + 2, y, f"HP {p.current_hp}/{p.max_hp}", fg=col.HP_FG)
    console.print(box_x + 18, y, f"AC {p.ac}", fg=col.LIGHT_GRAY)
    console.print(box_x + 28, y, f"Атака: +{p.attack_bonus}", fg=col.LIGHT_GRAY)
    console.print(box_x + 44, y, f"Урон: {p.damage_expression}+{p.damage_bonus}", fg=col.LIGHT_GRAY)
    y += 2

    console.print(box_x + 2, y, "Характеристики:", fg=col.TITLE_FG)
    y += 1
    scores = p.ability_scores
    abilities_in_order = ["str", "dex", "con", "int", "wis", "cha"]
    for i in range(3):
        left = abilities_in_order[i]
        right = abilities_in_order[i + 3]
        l_score = scores[left]
        r_score = scores[right]
        l_mod = p.mod(left)
        r_mod = p.mod(right)
        l_line = f"  {ABILITY_NAMES_RU[left]} {l_score:>2}  ({_fmt_mod(l_mod)})"
        r_line = f"  {ABILITY_NAMES_RU[right]} {r_score:>2}  ({_fmt_mod(r_mod)})"
        console.print(box_x + 2, y, l_line, fg=col.LIGHT_GRAY)
        console.print(box_x + 22, y, r_line, fg=col.LIGHT_GRAY)
        y += 1

    y += 1
    console.print(box_x + 2, y, "Снаряжение:", fg=col.TITLE_FG)
    y += 1
    if p.equipped_weapon:
        w = p.equipped_weapon
        console.print(
            box_x + 4, y,
            f"Оружие: {w.name_ru}  ({w.damage} {w.damage_type})",
            fg=col.LIGHT_GRAY,
        )
        y += 1
    if p.equipped_armor:
        a = p.equipped_armor
        console.print(
            box_x + 4, y,
            f"Доспех: {a.name_ru}  (AC {a.ac})",
            fg=col.LIGHT_GRAY,
        )
        y += 1
    if p.equipped_shield:
        s = p.equipped_shield
        console.print(
            box_x + 4, y,
            f"Щит:    {s.name_ru}  (+{s.ac_bonus} AC)",
            fg=col.LIGHT_GRAY,
        )
        y += 1

    y += 1
    console.print(box_x + 2, y, "Владения:", fg=col.TITLE_FG)
    y += 1
    for prof in p.proficiencies_ru:
        console.print(box_x + 4, y, f"• {prof}", fg=col.LIGHT_GRAY)
        y += 1

    y += 1
    console.print(box_x + 2, y, "Способности класса:", fg=col.TITLE_FG)
    y += 1
    for feat in p.class_features_ru:
        console.print(box_x + 4, y, f"• {feat}", fg=col.LIGHT_GRAY)
        y += 1

    y += 1
    console.print(box_x + 2, y, f"Золото: {p.inventory.gold} зм", fg=col.GOLD)

    fy = box_y + box_h - 2
    console.print(
        box_x + 2, fy,
        "I — инвентарь  •  C / Esc — закрыть",
        fg=col.DIM,
    )


def _fmt_mod(m: int) -> str:
    if m >= 0:
        return f"+{m}"
    return str(m)
