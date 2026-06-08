"""End-to-end flow smoke check (no window).

Walks through: name entry → forced combat with scrolls → descend → restart.
"""
from __future__ import annotations

from dnd_game.core.rng import seed
from dnd_game.entities.monster import spawn_monster
from dnd_game.game import save as save_mod
from dnd_game.game.state import Game, GameState


def main() -> None:
    save_mod.delete_save()
    seed(99)
    g = Game()
    assert g.state == GameState.NAME_ENTRY
    g.pending_name = "Гром"
    g.name_entry_confirm()
    assert g.state == GameState.EXPLORE
    print(f"After name entry: floor={g.floor}, player={g.player.name}, HP={g.player.current_hp}")

    # Force a multi-enemy combat with mages worth of HP.
    enemies = [
        spawn_monster("skeleton", g.player.x + 1, g.player.y),
        spawn_monster("goblin", g.player.x + 1, g.player.y + 1),
    ]
    g.start_combat(enemies)
    assert g.state == GameState.COMBAT
    print(f"Combat started with {len(g.combat.alive_enemies)} enemies.")

    # Use a magic missile scroll.
    mm = g.consumables_by_id["scroll_magic_missile"]
    g.player.inventory.consumables.append(mm)
    print(f"Pre-MM target HP: {g.combat.current_target.current_hp}")
    g.combat_action("item", mm)
    if g.combat:
        print(f"Post-MM target HP: {g.combat.alive_enemies[0].current_hp if g.combat.alive_enemies else 'all dead'}")

    # Bash through remaining turns.
    steps = 0
    while g.combat and steps < 50:
        g.combat_action("attack")
        steps += 1
    print(f"Combat ended in state {g.state} after {steps} attacks.")

    # If we won, try descending.
    if g.state == GameState.EXPLORE and g.dungeon is not None:
        # Force player onto stairs.
        sx, sy = g.dungeon.stairs_down
        g.player.x, g.player.y = sx - 1, sy
        # take_damage so descent's short rest does something
        g.player.take_damage(5)
        before_hp = g.player.current_hp
        g.move_player(1, 0)
        if g.state == GameState.EXPLORE:
            print(f"Descended to floor {g.floor}, HP {before_hp} → {g.player.current_hp}")

    # Restart from any non-active state.
    g.state = GameState.GAME_OVER
    g.restart()
    assert g.state == GameState.NAME_ENTRY
    assert g.floor == 1
    print(f"Restarted: state={g.state}, floor={g.floor}, dungeon={g.dungeon}")

    save_mod.delete_save()
    print("Flow smoke check passed.")


if __name__ == "__main__":
    main()
