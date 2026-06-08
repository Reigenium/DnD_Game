"""Entry point for the DnD Roguelike MVP."""
from __future__ import annotations

import sys
from pathlib import Path

import tcod
import tcod.console
import tcod.context
import tcod.event
import tcod.tileset

from dnd_game.core.rng import seed
from dnd_game.game.state import Game
from dnd_game.ui.input_handler import handle_event
from dnd_game.ui.renderer import render

SCREEN_WIDTH = 80
SCREEN_HEIGHT = 50

# Tile size in pixels. Bumped from 12x16 → 16x20 for sharper, larger glyphs.
# Window will open at SCREEN_WIDTH*TILE_W × SCREEN_HEIGHT*TILE_H pixels.
# On a 1920×1080 screen that's 1280×1000, leaving room for taskbar.
# If too big or too small for you, change the numbers below.
TILE_W = 12
TILE_H = 20


def _load_tileset() -> tcod.tileset.Tileset | None:
    """Load a TTF that has Cyrillic glyphs. Falls back to tcod default."""
    candidates = [
        Path("C:/Windows/Fonts/consola.ttf"),
        Path("C:/Windows/Fonts/lucon.ttf"),
        Path("C:/Windows/Fonts/cour.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
    ]
    for path in candidates:
        if path.exists():
            try:
                return tcod.tileset.load_truetype_font(str(path), TILE_W, TILE_H)
            except Exception:  # noqa: BLE001
                continue
    return None


def _enable_text_input() -> None:
    """Best-effort attempt to ensure TextInput events fire for name entry.

    On most platforms SDL2 has text input on by default; this is just a safety net.
    """
    for path in (
        "tcod.sdl.start_text_input",
        "tcod.event.start_text_input",
    ):
        mod_name, _, fn_name = path.rpartition(".")
        try:
            mod = __import__(mod_name, fromlist=[fn_name])
            fn = getattr(mod, fn_name, None)
            if callable(fn):
                fn()
                return
        except (ImportError, AttributeError):
            continue


def main() -> None:
    seed()
    tileset = _load_tileset()

    game = Game()

    context_kwargs = dict(
        columns=SCREEN_WIDTH,
        rows=SCREEN_HEIGHT,
        title="DnD Roguelike — MVP",
        vsync=True,
    )
    if tileset is not None:
        context_kwargs["tileset"] = tileset

    with tcod.context.new(**context_kwargs) as context:
        _enable_text_input()
        console = tcod.console.Console(SCREEN_WIDTH, SCREEN_HEIGHT, order="F")
        running = True
        while running:
            render(console, game)
            context.present(console)
            # Collect all pending events, convert them, then process TextInput
            # before KeyDown so the Latin-letter fallback dedup works correctly.
            events = list(tcod.event.wait())
            for e in events:
                context.convert_event(e)
            for event in sorted(
                events,
                key=lambda e: 0 if isinstance(e, tcod.event.TextInput) else 1,
            ):
                result = handle_event(event, game)
                if result == "quit":
                    running = False
                    break


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
