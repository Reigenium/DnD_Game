"""Confirmation dialog shown when the player steps onto stairs."""
from __future__ import annotations

from tcod.console import Console

from .. import colors as col


def render_stairs_prompt(console: Console, game) -> None:
    box_x, box_y, box_w, box_h = 18, 20, 44, 9
    console.draw_frame(box_x, box_y, box_w, box_h, clear=True, fg=col.YELLOW)

    title = f" Этаж {game.floor + 1} "
    console.print(box_x + (box_w - len(title)) // 2, box_y, title, fg=col.TITLE_FG)

    msg = f"Перейти на этаж {game.floor + 1}?"
    console.print(box_x + (box_w - len(msg)) // 2, box_y + 2, msg, fg=col.LIGHT_GRAY)

    hint = "Подземелье становится опаснее с каждым уровнем."
    console.print(box_x + (box_w - len(hint)) // 2, box_y + 3, hint, fg=col.DIM)

    yes = "[Y] / [Enter] — Да, вперёд!"
    no  = "[N] / [Esc]   — Нет, остаться"
    console.print(box_x + 3, box_y + 5, yes, fg=col.GREEN)
    console.print(box_x + 3, box_y + 6, no,  fg=col.RED)
