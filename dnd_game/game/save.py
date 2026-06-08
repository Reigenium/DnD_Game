"""Save / load to ``save.json`` (right next to main.py).

Permadeath rules:
- Save is written when the player quits via Q in EXPLORE.
- Save is written automatically on every floor descent (safety net).
- Save is deleted on death — there is no rollback.

Format is a compact JSON. Tile data is stored as one char-string per column
(``#`` wall, ``.`` floor, ``>`` stairs down, ``?`` encounter marker), and
explored bitmaps as ``0``/``1`` strings.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from ..entities.monster import spawn_monster
from ..world import tile as tile_mod
from ..world.dungeon import Dungeon, EncounterMarker, Room

if TYPE_CHECKING:
    from .state import Game

SAVE_PATH = Path("save.json")
SAVE_VERSION = 1


def has_save() -> bool:
    return SAVE_PATH.exists()


def delete_save() -> None:
    if SAVE_PATH.exists():
        try:
            SAVE_PATH.unlink()
        except OSError:
            pass


def _tile_char(tiles, x: int, y: int) -> str:
    t = tiles[x, y]
    if not bool(t["walkable"]) and not bool(t["transparent"]):
        return "#"
    ch = int(t["dark"]["ch"])
    if ch == ord(">"):
        return ">"
    if ch == ord("?"):
        return "?"
    return "."


_TILE_BY_CHAR = {
    "#": tile_mod.wall,
    ".": tile_mod.floor,
    ">": tile_mod.stairs_down,
    "?": tile_mod.encounter_marker,
}


def save_game(game: "Game") -> None:
    p = game.player
    d = game.dungeon
    if d is None:
        return

    tile_cols = [
        "".join(_tile_char(d.tiles, x, y) for y in range(d.height))
        for x in range(d.width)
    ]
    explored_cols = [
        "".join("1" if bool(d.explored[x, y]) else "0" for y in range(d.height))
        for x in range(d.width)
    ]

    data = {
        "version": SAVE_VERSION,
        "floor": game.floor,
        "player": {
            "name": p.name,
            "class": p.char_class,
            "level": p.level,
            "xp": p.xp,
            "xp_to_next": p.xp_to_next,
            "str": p.str_, "dex": p.dex, "con": p.con,
            "int": p.int_, "wis": p.wis, "cha": p.cha,
            "max_hp": p.max_hp, "current_hp": p.current_hp,
            "proficiency_bonus": p.proficiency_bonus,
            "x": p.x, "y": p.y,
            "weapon_id": p.equipped_weapon.id if p.equipped_weapon else None,
            "armor_id": p.equipped_armor.id if p.equipped_armor else None,
            "shield_id": p.equipped_shield.id if p.equipped_shield else None,
            "inv_weapons": [w.id for w in p.inventory.weapons],
            "inv_armors": [a.id for a in p.inventory.armors],
            "inv_consumables": [c.id for c in p.inventory.consumables],
            "gold": p.inventory.gold,
        },
        "dungeon": {
            "width": d.width, "height": d.height,
            "stairs_down": list(d.stairs_down) if d.stairs_down else None,
            "player_start": list(d.player_start),
            "rooms": [[r.x, r.y, r.w, r.h] for r in d.rooms],
            "tile_cols": tile_cols,
            "explored_cols": explored_cols,
            "monsters": [
                {"id": m.id, "x": m.x, "y": m.y,
                 "current_hp": m.current_hp, "max_hp": m.max_hp}
                for m in d.monsters if m.is_alive
            ],
            "encounters": [
                {"id": e.encounter_id, "x": e.x, "y": e.y, "triggered": e.triggered}
                for e in d.encounters
            ],
        },
        "message_log": game.message_log[-50:],
    }
    SAVE_PATH.write_text(
        json.dumps(data, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )


def load_game(game: "Game") -> bool:
    """Mutate ``game`` in place from save.json. Returns True on success."""
    if not SAVE_PATH.exists():
        return False
    try:
        data = json.loads(SAVE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if data.get("version") != SAVE_VERSION:
        return False

    pdata = data["player"]
    p = game.player
    p.name = pdata["name"]
    p.char_class = pdata["class"]
    p.level = pdata["level"]
    p.xp = pdata["xp"]
    p.xp_to_next = pdata["xp_to_next"]
    p.str_ = pdata["str"]; p.dex = pdata["dex"]; p.con = pdata["con"]
    p.int_ = pdata["int"]; p.wis = pdata["wis"]; p.cha = pdata["cha"]
    p.max_hp = pdata["max_hp"]; p.current_hp = pdata["current_hp"]
    p.proficiency_bonus = pdata["proficiency_bonus"]
    p.x = pdata["x"]; p.y = pdata["y"]
    p.equipped_weapon = game.weapons.get(pdata["weapon_id"]) if pdata.get("weapon_id") else None
    p.equipped_armor = game.armors.get(pdata["armor_id"]) if pdata.get("armor_id") else None
    p.equipped_shield = game.armors.get(pdata["shield_id"]) if pdata.get("shield_id") else None
    p.inventory.weapons = [
        game.weapons[w] for w in pdata.get("inv_weapons", []) if w in game.weapons
    ]
    p.inventory.armors = [
        game.armors[a] for a in pdata.get("inv_armors", []) if a in game.armors
    ]
    p.inventory.consumables = [
        game.consumables_by_id[c]
        for c in pdata.get("inv_consumables", [])
        if c in game.consumables_by_id
    ]
    p.inventory.gold = pdata.get("gold", 0)

    ddata = data["dungeon"]
    d = Dungeon(ddata["width"], ddata["height"])
    for x, col in enumerate(ddata["tile_cols"]):
        for y, ch in enumerate(col):
            tile = _TILE_BY_CHAR.get(ch, tile_mod.wall)
            d.tiles[x, y] = tile
    for x, col in enumerate(ddata.get("explored_cols", [])):
        for y, ch in enumerate(col):
            d.explored[x, y] = (ch == "1")
    d.stairs_down = tuple(ddata["stairs_down"]) if ddata.get("stairs_down") else None
    d.player_start = tuple(ddata["player_start"])
    d.rooms = [Room(*r) for r in ddata.get("rooms", [])]
    for mdata in ddata.get("monsters", []):
        m = spawn_monster(mdata["id"], mdata["x"], mdata["y"])
        m.max_hp = mdata.get("max_hp", m.max_hp)
        m.current_hp = mdata.get("current_hp", m.max_hp)
        d.monsters.append(m)
    for edata in ddata.get("encounters", []):
        d.encounters.append(EncounterMarker(
            edata["x"], edata["y"], edata["id"], edata.get("triggered", False)
        ))

    game.dungeon = d
    game.dungeon.update_fov(p.x, p.y)
    game.floor = data.get("floor", 1)
    game.message_log = list(data.get("message_log", []))
    return True
