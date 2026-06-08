"""Modal inventory screen — list & equip/use."""
from __future__ import annotations

from tcod.console import Console

from ...items.item import Armor, Consumable, Weapon
from .. import colors as col


def render_inventory(console: Console, game) -> None:
    p = game.player

    box_x, box_y, box_w, box_h = 6, 3, 68, 40
    console.draw_frame(box_x, box_y, box_w, box_h, clear=True, fg=col.YELLOW)
    title = " ИНВЕНТАРЬ "
    console.print(box_x + (box_w - len(title)) // 2, box_y, title, fg=col.GOLD)

    console.print(
        box_x + 2, box_y + 1,
        f"Золото: {p.inventory.gold} зм",
        fg=col.GOLD,
    )

    items = game.inventory_items_flat()

    y = box_y + 3
    console.print(box_x + 2, y, "ОРУЖИЕ", fg=col.TITLE_FG)
    y += 1
    weapon_indices = [i for i, (k, _) in enumerate(items) if k == "weapon"]
    if not weapon_indices and p.equipped_weapon is None:
        console.print(box_x + 4, y, "— пусто —", fg=col.DIM)
        y += 1
    if p.equipped_weapon is not None:
        console.print(
            box_x + 4, y,
            f"  ◆ {p.equipped_weapon.name_ru}  ({p.equipped_weapon.damage} {_damage_type_ru(p.equipped_weapon.damage_type)})  [экипировано]",
            fg=col.GREEN,
        )
        y += 1
    for idx in weapon_indices:
        w: Weapon = items[idx][1]  # type: ignore[assignment]
        key = f"[{idx + 1}]" if idx < 9 else "[ ]"
        console.print(
            box_x + 4, y,
            f"{key} {w.name_ru}  ({w.damage} {_damage_type_ru(w.damage_type)})",
            fg=col.LIGHT_GRAY,
        )
        y += 1

    y += 1
    console.print(box_x + 2, y, "ДОСПЕХИ И ЩИТЫ", fg=col.TITLE_FG)
    y += 1
    armor_indices = [i for i, (k, _) in enumerate(items) if k == "armor"]
    if p.equipped_armor is not None:
        console.print(
            box_x + 4, y,
            f"  ◆ {p.equipped_armor.name_ru}  (AC {p.equipped_armor.ac})  [экипировано]",
            fg=col.GREEN,
        )
        y += 1
    if p.equipped_shield is not None:
        console.print(
            box_x + 4, y,
            f"  ◆ {p.equipped_shield.name_ru}  (+{p.equipped_shield.ac_bonus} AC)  [экипировано]",
            fg=col.GREEN,
        )
        y += 1
    if not armor_indices and p.equipped_armor is None and p.equipped_shield is None:
        console.print(box_x + 4, y, "— пусто —", fg=col.DIM)
        y += 1
    for idx in armor_indices:
        a: Armor = items[idx][1]  # type: ignore[assignment]
        key = f"[{idx + 1}]" if idx < 9 else "[ ]"
        if a.type == "shield":
            line = f"{key} {a.name_ru}  (+{a.ac_bonus} AC)"
        else:
            line = f"{key} {a.name_ru}  (AC {a.ac}, {_armor_type_ru(a.type)})"
        console.print(box_x + 4, y, line, fg=col.LIGHT_GRAY)
        y += 1

    y += 1
    console.print(box_x + 2, y, "РАСХОДНИКИ (зелья и свитки)", fg=col.TITLE_FG)
    y += 1
    cons_indices = [i for i, (k, _) in enumerate(items) if k == "consumable"]
    # Group by id for the count column.
    counts: dict[str, int] = {}
    order: list[Consumable] = []
    cons_idx_by_first_id: dict[str, int] = {}
    for idx in cons_indices:
        c: Consumable = items[idx][1]  # type: ignore[assignment]
        if c.id not in counts:
            counts[c.id] = 1
            order.append(c)
            cons_idx_by_first_id[c.id] = idx
        else:
            counts[c.id] += 1
    if not order:
        console.print(box_x + 4, y, "— пусто —", fg=col.DIM)
        y += 1
    for c in order:
        first_idx = cons_idx_by_first_id[c.id]
        key = f"[{first_idx + 1}]" if first_idx < 9 else "[ ]"
        cnt = counts[c.id]
        cnt_str = f" ×{cnt}" if cnt > 1 else ""
        eff = _effect_summary(c)
        line = f"{key} {c.name_ru}{cnt_str} — {eff}"
        console.print(box_x + 4, y, line, fg=col.CYAN if c.effect != "heal" else col.LIGHT_GRAY)
        y += 1

    # Footer
    fy = box_y + box_h - 3
    console.draw_rect(box_x + 1, fy, box_w - 2, 1, ord("─"), fg=col.DIM)
    console.print(
        box_x + 2, fy + 1,
        "Цифра — экипировать/использовать  •  C — лист персонажа  •  I/Esc — закрыть",
        fg=col.DIM,
    )


def _damage_type_ru(t: str) -> str:
    return {
        "slashing": "рубящ.",
        "piercing": "колющ.",
        "bludgeoning": "дроб.",
        "fire": "огонь",
        "cold": "холод",
        "acid": "кислота",
        "force": "силовой",
        "psychic": "псих.",
    }.get(t, t)


def _armor_type_ru(t: str) -> str:
    return {
        "light": "лёгк.",
        "medium": "ср.",
        "heavy": "тяж.",
        "shield": "щит",
    }.get(t, t)


def _effect_summary(c: Consumable) -> str:
    if c.effect == "heal":
        return f"лечение {c.amount}"
    if c.effect == "magic_missile":
        return "3 силовые стрелы (3d4+3, авто-попадание, только в бою)"
    if c.effect == "ray_of_frost":
        return "холод 1d8 + заморозка на 1 ход (только в бою)"
    if c.effect == "shield":
        return "следующая атака по тебе провалится"
    return c.effect
