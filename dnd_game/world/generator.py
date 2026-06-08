"""Procedural floor generation. Difficulty scales with floor index."""
from __future__ import annotations

from collections.abc import Iterator

from ..core.rng import get_rng
from ..entities.monster import spawn_monster
from . import tile as tile_mod
from .dungeon import Dungeon, EncounterMarker, Room


def _line(x1: int, y1: int, x2: int, y2: int) -> Iterator[tuple[int, int]]:
    if x1 == x2:
        for y in range(min(y1, y2), max(y1, y2) + 1):
            yield x1, y
    elif y1 == y2:
        for x in range(min(x1, x2), max(x1, x2) + 1):
            yield x, y1


def _tunnel_between(a: tuple[int, int], b: tuple[int, int]) -> Iterator[tuple[int, int]]:
    x1, y1 = a
    x2, y2 = b
    rng = get_rng()
    corner = (x2, y1) if rng.random() < 0.5 else (x1, y2)
    yield from _line(x1, y1, *corner)
    yield from _line(*corner, x2, y2)


def _monster_weights_for_floor(floor: int) -> tuple[list[str], list[int]]:
    """Return (pool, weights) per floor. Orcs become more common deeper."""
    pool = ["goblin", "skeleton", "wolf", "slime", "orc"]
    if floor <= 1:
        weights = [4, 3, 3, 3, 1]
    elif floor == 2:
        weights = [3, 3, 3, 2, 2]
    elif floor == 3:
        weights = [2, 3, 3, 2, 3]
    elif floor == 4:
        weights = [2, 3, 3, 1, 4]
    else:
        weights = [1, 2, 3, 1, 5]
    return pool, weights


def generate_floor(
    width: int = 80,
    height: int = 43,
    *,
    floor: int = 1,
    max_rooms: int = 14,
    room_min_size: int = 5,
    room_max_size: int = 10,
) -> Dungeon:
    """Generate one floor. ``floor`` index scales monster count and pool."""
    rng = get_rng()
    dungeon = Dungeon(width, height)

    extra = max(0, floor - 1) * 2
    monsters_per_floor = (8 + extra, 12 + extra)
    encounters_per_floor = (3, 5)

    monster_pool, monster_weights = _monster_weights_for_floor(floor)
    encounter_pool = ["chest_or_mimic", "merchant", "beggar", "shrine", "campfire"]

    rooms: list[Room] = []
    for _ in range(max_rooms):
        w = rng.randint(room_min_size, room_max_size)
        h = rng.randint(room_min_size, room_max_size)
        x = rng.randint(1, width - w - 2)
        y = rng.randint(1, height - h - 2)
        room = Room(x, y, w, h)
        if any(room.intersects(r) for r in rooms):
            continue

        xs, ys = room.inner
        dungeon.tiles[xs, ys] = tile_mod.floor

        if rooms:
            for tx, ty in _tunnel_between(rooms[-1].center, room.center):
                if dungeon.in_bounds(tx, ty):
                    dungeon.tiles[tx, ty] = tile_mod.floor

        rooms.append(room)

    if not rooms:
        return dungeon

    dungeon.rooms = rooms
    dungeon.player_start = rooms[0].center

    sx, sy = rooms[-1].center
    dungeon.tiles[sx, sy] = tile_mod.stairs_down
    dungeon.stairs_down = (sx, sy)

    candidate_rooms = rooms[1:]
    used: set[tuple[int, int]] = {dungeon.stairs_down}

    n_monsters = rng.randint(*monsters_per_floor)
    for _ in range(n_monsters * 3):
        if (not candidate_rooms
                or sum(1 for m in dungeon.monsters if m.is_alive) >= n_monsters):
            break
        room = rng.choice(candidate_rooms)
        mx = rng.randint(room.x + 1, room.x + room.w - 2)
        my = rng.randint(room.y + 1, room.y + room.h - 2)
        if (mx, my) in used or dungeon.monster_at(mx, my):
            continue
        monster_id = rng.choices(monster_pool, weights=monster_weights, k=1)[0]
        dungeon.monsters.append(spawn_monster(monster_id, mx, my))
        used.add((mx, my))

    n_enc = rng.randint(*encounters_per_floor)
    placed = 0
    for _ in range(n_enc * 5):
        if placed >= n_enc or not candidate_rooms:
            break
        room = rng.choice(candidate_rooms)
        ex = rng.randint(room.x + 1, room.x + room.w - 2)
        ey = rng.randint(room.y + 1, room.y + room.h - 2)
        if (ex, ey) in used or dungeon.monster_at(ex, ey):
            continue
        encounter_id = rng.choice(encounter_pool)
        dungeon.encounters.append(EncounterMarker(ex, ey, encounter_id))
        dungeon.tiles[ex, ey] = tile_mod.encounter_marker
        used.add((ex, ey))
        placed += 1

    return dungeon
