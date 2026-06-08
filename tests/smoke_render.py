"""Renderer smoke check: draw each game state to an offscreen console.

Doesn't open a window — just verifies the render pipeline doesn't crash.
"""
from __future__ import annotations

from pathlib import Path

from tcod.console import Console

from dnd_game.core.rng import seed
from dnd_game.entities.monster import spawn_monster
from dnd_game.game import save as save_mod
from dnd_game.game.state import ActiveEncounter, Game, GameState
from dnd_game.ui.renderer import render
from dnd_game.world.dungeon import EncounterMarker


def main() -> None:
    # Start clean — no save carried over from a previous run.
    save_mod.delete_save()
    seed(7)
    g = Game()
    console = Console(80, 50, order="F")

    print("Rendering NAME_ENTRY state...")
    render(console, g)
    print("  ok")

    # Confirm name and enter EXPLORE.
    g.pending_name = "Тестий"
    g.name_entry_confirm()
    assert g.state == GameState.EXPLORE
    assert g.dungeon is not None
    print(
        f"  → state={g.state}, floor={g.floor}, rooms={len(g.dungeon.rooms)}, "
        f"monsters={len(g.dungeon.monsters)}, encounters={len(g.dungeon.encounters)}"
    )

    print("Rendering EXPLORE state...")
    render(console, g)
    print("  ok")

    print("Rendering INVENTORY state...")
    g.open_inventory()
    render(console, g)
    print("  ok")
    g.close_modal()

    print("Rendering CHARACTER state...")
    g.open_character()
    render(console, g)
    print("  ok")
    g.close_modal()

    print("Rendering COMBAT state...")
    g.start_combat([
        spawn_monster("goblin", g.player.x + 1, g.player.y),
        spawn_monster("skeleton", g.player.x + 2, g.player.y),
    ])
    render(console, g)
    print("  ok")
    print("Rendering COMBAT with item picker open...")
    g.combat_item_menu_open = True
    render(console, g)
    print("  ok")
    g.combat_item_menu_open = False
    g.combat = None
    g.state = GameState.EXPLORE

    print("Rendering ENCOUNTER state...")
    marker = EncounterMarker(g.player.x, g.player.y, "merchant")
    edef = g.encounter_defs["merchant"]
    g.encounter = ActiveEncounter(definition=edef, marker=marker)
    g.state = GameState.ENCOUNTER
    render(console, g)
    print("  ok")
    g.encounter = None
    g.state = GameState.EXPLORE

    print("Save/load round-trip...")
    save_mod.save_game(g)
    assert Path("save.json").exists()
    # corrupt the in-memory state then reload it
    saved_floor = g.floor
    saved_name = g.player.name
    saved_x, saved_y = g.player.x, g.player.y
    g.floor = 99
    g.player.name = "WRECKED"
    g.player.x = 0
    g.player.y = 0
    loaded = save_mod.load_game(g)
    assert loaded
    assert g.floor == saved_floor
    assert g.player.name == saved_name
    assert (g.player.x, g.player.y) == (saved_x, saved_y)
    print("  ok")
    save_mod.delete_save()

    print("Rendering GAME_OVER state...")
    g.state = GameState.GAME_OVER
    render(console, g)
    print("  ok")

    print("All states render without exceptions.")


if __name__ == "__main__":
    main()
