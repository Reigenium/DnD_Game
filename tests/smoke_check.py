"""Manual smoke check: instantiate Game without launching the tcod window."""
from __future__ import annotations

from dnd_game.core.rng import seed
from dnd_game.game.state import Game


def main() -> None:
    seed(123)
    g = Game()
    p = g.player
    print(f"State: {g.state}")
    print(
        f"Player: {p.name} class={p.char_class} lvl={p.level} "
        f"HP {p.current_hp}/{p.max_hp} AC {p.ac} ATK+{p.attack_bonus} "
        f"weapon={p.equipped_weapon.name_ru if p.equipped_weapon else '-'}"
    )
    d = g.dungeon
    print(
        f"Dungeon: {d.width}x{d.height} rooms={len(d.rooms)} "
        f"monsters={len(d.monsters)} encounters={len(d.encounters)}"
    )
    print(f"Player at {p.x},{p.y}, stairs at {d.stairs_down}")
    print(f"Monster sample: {[(m.id, m.x, m.y, m.current_hp) for m in d.monsters[:3]]}")
    print(f"Encounter sample: {[(e.encounter_id, e.x, e.y) for e in d.encounters[:3]]}")

    # Try one combat round with the first monster (forced).
    if d.monsters:
        m = d.monsters[0]
        print(f"\nForcing combat against {m.name_ru} (HP {m.current_hp}/{m.max_hp})...")
        g.start_combat([m])
        steps = 0
        while g.combat is not None and steps < 30:
            g.combat_action("attack")
            steps += 1
        for line in g.message_log[-5:]:
            print(f"  log: {line}")
        print(f"Final state after forced combat: {g.state}")


if __name__ == "__main__":
    main()
