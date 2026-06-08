"""Tile types. Brighter palette for readability."""
from __future__ import annotations

import numpy as np

graphic_dt = np.dtype([
    ("ch", np.int32),
    ("fg", "3B"),
    ("bg", "3B"),
])

tile_dt = np.dtype([
    ("walkable", np.bool_),
    ("transparent", np.bool_),
    ("dark", graphic_dt),
    ("light", graphic_dt),
])


def _tile(walkable: bool, transparent: bool, dark, light) -> np.ndarray:
    return np.array((walkable, transparent, dark, light), dtype=tile_dt)


SHROUD = np.array((ord(" "), (255, 255, 255), (0, 0, 0)), dtype=graphic_dt)

floor = _tile(
    walkable=True, transparent=True,
    dark=(ord("."), (75, 80, 100), (12, 12, 22)),
    light=(ord("."), (210, 200, 165), (38, 38, 48)),
)

wall = _tile(
    walkable=False, transparent=False,
    dark=(ord("#"), (90, 70, 40), (22, 14, 4)),
    light=(ord("#"), (215, 165, 95), (58, 36, 14)),
)

stairs_down = _tile(
    walkable=True, transparent=True,
    dark=(ord(">"), (140, 140, 140), (12, 12, 22)),
    light=(ord(">"), (255, 255, 255), (40, 40, 50)),
)

encounter_marker = _tile(
    walkable=True, transparent=True,
    dark=(ord("?"), (130, 80, 130), (12, 12, 22)),
    light=(ord("?"), (255, 130, 255), (40, 40, 50)),
)
