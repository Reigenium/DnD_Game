"""Monster AI: idle patrol → alert chase.

States (stored on monster.alerted):
  False = IDLE: random walk within room boundaries.
  True  = ALERT: move toward player by BFS.

Transition IDLE→ALERT: monster sees player within FOV radius 6.
Transition ALERT→IDLE: never (once alerted, stays alerted).

No tcod imported here — pure logic.
"""
from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..entities.monster import Monster
    from ..entities.character import Character
    from ..world.dungeon import Dungeon

ALERT_RADIUS = 6


def tick_monster_ai(monster: "Monster", player: "Character", dungeon: "Dungeon") -> None:
    if not monster.is_alive:
        return

    # Check if player is within detection radius and in explored area.
    dx = abs(monster.x - player.x)
    dy = abs(monster.y - player.y)
    if dx <= ALERT_RADIUS and dy <= ALERT_RADIUS:
        # Chebyshev distance ≤ ALERT_RADIUS and dungeon.visible at monster pos.
        if dungeon.in_bounds(monster.x, monster.y) and bool(dungeon.visible[monster.x, monster.y]):
            monster.alerted = True

    if monster.alerted:
        _chase(monster, player, dungeon)
    else:
        _idle(monster, dungeon)


def _idle(monster: "Monster", dungeon: "Dungeon") -> None:
    from ..core.rng import get_rng
    rng = get_rng()
    if rng.random() < 0.4:  # 40% chance to move each tick
        dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        rng.shuffle(dirs)
        for dx, dy in dirs:
            nx, ny = monster.x + dx, monster.y + dy
            if dungeon.is_walkable(nx, ny) and dungeon.monster_at(nx, ny) is None:
                monster.x, monster.y = nx, ny
                break


def _chase(monster: "Monster", player: "Character", dungeon: "Dungeon") -> None:
    """Move one step toward player using BFS."""
    step = _bfs_step(monster.x, monster.y, player.x, player.y, dungeon)
    if step is not None:
        nx, ny = step
        # Don't step onto another monster.
        if dungeon.monster_at(nx, ny) is None:
            monster.x, monster.y = nx, ny


def _bfs_step(
    sx: int, sy: int, tx: int, ty: int, dungeon: "Dungeon"
) -> tuple[int, int] | None:
    """Return the first step from (sx,sy) toward (tx,ty) avoiding walls."""
    if (sx, sy) == (tx, ty):
        return None
    visited: set[tuple[int, int]] = {(sx, sy)}
    queue: deque[list[tuple[int, int]]] = deque([[]])
    # (position, path from start)
    frontier: deque[tuple[tuple[int, int], tuple[int, int] | None]] = deque()
    frontier.append(((sx, sy), None))
    first_step: dict[tuple[int, int], tuple[int, int]] = {}

    q: deque[tuple[int, int]] = deque([(sx, sy)])
    parent: dict[tuple[int, int], tuple[int, int] | None] = {(sx, sy): None}
    first: dict[tuple[int, int], tuple[int, int]] = {}

    dirs = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    while q:
        cx, cy = q.popleft()
        for dx, dy in dirs:
            nx, ny = cx + dx, cy + dy
            if (nx, ny) in parent:
                continue
            if not dungeon.is_walkable(nx, ny):
                continue
            parent[(nx, ny)] = (cx, cy)
            # Track first step from start.
            if (cx, cy) == (sx, sy):
                first[(nx, ny)] = (nx, ny)
            else:
                first[(nx, ny)] = first.get((cx, cy), (nx, ny))
            if nx == tx and ny == ty:
                return first[(nx, ny)]
            q.append((nx, ny))
        if len(parent) > 400:  # safety cap
            break
    return None
