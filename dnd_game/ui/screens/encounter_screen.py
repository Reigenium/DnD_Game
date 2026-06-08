"""Modal encounter dialog (drawn on top of the map)."""
from __future__ import annotations

from tcod.console import Console

from .. import colors as col


def render_encounter(console: Console, game) -> None:
    enc = game.encounter
    edef = enc.definition

    box_x, box_y, box_w, box_h = 8, 6, 64, 36
    console.draw_frame(box_x, box_y, box_w, box_h, clear=True, fg=col.MAGENTA)
    title = f" {edef.title} "
    console.print(box_x + (box_w - len(title)) // 2, box_y, title, fg=col.MAGENTA)

    y = box_y + 2
    for line in _wrap(edef.description, box_w - 4):
        console.print(box_x + 2, y, line, fg=col.LIGHT_GRAY)
        y += 1

    y += 1

    if not enc.resolved:
        for i, choice in enumerate(edef.choices):
            key = f"[{i + 1}]"
            console.print(box_x + 2, y, f"{key} {choice.label}", fg=col.YELLOW)
            y += 1
        if enc.message:
            y += 1
            for line in _wrap(enc.message, box_w - 4):
                console.print(box_x + 2, y, line, fg=col.GOLD)
                y += 1
    else:
        for line in _wrap(enc.message or "...", box_w - 4):
            console.print(box_x + 2, y, line, fg=col.GOLD)
            y += 1
        y += 1
        console.print(
            box_x + 2, y,
            "[ Enter / Space — продолжить ]",
            fg=col.DIM,
        )


def _wrap(text: str, width: int) -> list[str]:
    out: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        if not words:
            out.append("")
            continue
        line = ""
        for w in words:
            if len(line) + len(w) + (1 if line else 0) > width:
                out.append(line)
                line = w
            else:
                line = f"{line} {w}".strip() if line else w
        if line:
            out.append(line)
    return out
