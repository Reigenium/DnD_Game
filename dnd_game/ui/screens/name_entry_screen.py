"""Title / name entry screen, shown before the first floor."""
from __future__ import annotations

from tcod.console import Console

from .. import colors as col


def render_name_entry(console: Console, game) -> None:
    cx = 40
    console.print(cx - 11, 8, "D&D Roguelike — MVP", fg=col.GOLD)
    console.print(cx - 19, 10, "Подземелье, кости, и одна жизнь.", fg=col.LIGHT_GRAY)

    console.print(cx - 13, 16, "Введи имя своего воина:", fg=col.TITLE_FG)

    name_display = game.pending_name if game.pending_name else "Боргх"
    name_color = col.YELLOW if game.pending_name else col.DIM
    box_x = cx - 12
    console.draw_frame(box_x, 18, 24, 3, clear=True, fg=col.DIM)
    console.print(box_x + 2, 19, f"{name_display}_", fg=name_color)

    console.print(cx - 24, 23, "Enter — начать забег. Backspace — стереть. Esc — выйти.", fg=col.DIM)
    if not game.pending_name:
        console.print(cx - 23, 25, "(Пусто = «Боргх». Cyrillic вводится через раскладку.)", fg=col.GRAY)

    console.print(cx - 10, 30, "Класс: Воин (Fighter)", fg=col.LIGHT_GRAY)
    console.print(cx - 16, 31, "Старт: меч • кольчуга • щит • 2 зелья + свиток щита", fg=col.GRAY)
