"""Dungeon level: tiles, rooms, entities, FOV state."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import tcod.map

from ..entities.monster import Monster
from . import tile as tile_mod


@dataclass
class Room:
    x: int
    y: int
    w: int
    h: int

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.w // 2, self.y + self.h // 2

    @property
    def inner(self) -> tuple[slice, slice]:
        return slice(self.x + 1, self.x + self.w - 1), slice(self.y + 1, self.y + self.h - 1)

    def intersects(self, other: "Room") -> bool:
        return (
            self.x <= other.x + other.w
            and self.x + self.w >= other.x
            and self.y <= other.y + other.h
            and self.y + self.h >= other.y
        )


@dataclass
class EncounterMarker:
    x: int
    y: int
    encounter_id: str
    triggered: bool = False


class Dungeon:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.tiles: np.ndarray = np.full((width, height), fill_value=tile_mod.wall, order="F")
        self.visible: np.ndarray = np.full((width, height), fill_value=False, order="F")
        self.explored: np.ndarray = np.full((width, height), fill_value=False, order="F")
        self.rooms: list[Room] = []
        self.monsters: list[Monster] = []
        self.encounters: list[EncounterMarker] = []
        self.stairs_down: tuple[int, int] | None = None
        self.player_start: tuple[int, int] = (0, 0)

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and bool(self.tiles[x, y]["walkable"])

    def monster_at(self, x: int, y: int) -> Monster | None:
        for m in self.monsters:
            if m.is_alive and m.x == x and m.y == y:
                return m
        return None

    def encounter_at(self, x: int, y: int) -> EncounterMarker | None:
        for e in self.encounters:
            if not e.triggered and e.x == x and e.y == y:
                return e
        return None

    def update_fov(self, x: int, y: int, radius: int = 8) -> None:
        self.visible[:] = tcod.map.compute_fov(
            self.tiles["transparent"], (x, y), radius=radius
        )
        self.explored |= self.visible
