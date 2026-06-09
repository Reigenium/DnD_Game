"""Level-up choice screen."""
from __future__ import annotations

from tcod.console import Console

from .. import colors as col

_STAT_LABELS = {
    "stat_str": ("СИЛ +2", "Сила: +2 к атаке и урону в ближнем бою"),
    "stat_dex": ("ЛВК +2", "Ловкость: +2 к уклонению, инициативе, стрельбе"),
    "stat_con": ("ТЕЛ +2", "Телосложение: +2 к характеристике и +2 к макс. HP"),
}


def render_levelup(console: Console, game) -> None:
    from ...combat.abilities import ABILITY_REGISTRY

    console.draw_frame(15, 8, 50, 34, clear=True, fg=col.ORANGE)
    title = f" УРОВЕНЬ {game.player.level}! "
    console.print(15 + (50 - len(title)) // 2, 8, title, fg=col.YELLOW)

    console.print(17, 10, "Выбери улучшение:", fg=col.TITLE_FG)
    console.print(17, 11, f"Воин ур.{game.player.level} — {game.player.name}", fg=col.LIGHT_GRAY)

    choices = game.levelup_choices
    for i, choice_id in enumerate(choices):
        y = 13 + i * 4
        if y > 38:
            break
        key = f"[{i + 1}]"

        if choice_id in _STAT_LABELS:
            short, desc = _STAT_LABELS[choice_id]
        else:
            ab = ABILITY_REGISTRY.get(choice_id, {})
            short = ab.get("name_ru", choice_id)
            desc = ab.get("description_ru", "")

        console.print(17, y, f"{key} {short}", fg=col.CYAN)
        # Wrap description.
        words = desc.split()
        line = ""
        dy = 1
        for word in words:
            if len(line) + len(word) + 1 > 44:
                console.print(19, y + dy, line, fg=col.LIGHT_GRAY)
                line = word
                dy += 1
            else:
                line = (line + " " + word).strip()
        if line:
            console.print(19, y + dy, line, fg=col.LIGHT_GRAY)

    console.print(17, 39, "Нажми 1-" + str(len(choices)) + " для выбора", fg=col.DIM)
