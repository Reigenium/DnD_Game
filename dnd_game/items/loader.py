"""JSON loaders for item data. Returns dicts keyed by id."""
from __future__ import annotations

import json
from pathlib import Path

from .item import Armor, Consumable, Weapon

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def load_weapons() -> dict[str, Weapon]:
    with open(DATA_DIR / "weapons.json", encoding="utf-8") as f:
        data = json.load(f)
    return {wid: Weapon(id=wid, **wdata) for wid, wdata in data.items()}


def load_armor() -> dict[str, Armor]:
    with open(DATA_DIR / "armor.json", encoding="utf-8") as f:
        data = json.load(f)
    return {aid: Armor(id=aid, **adata) for aid, adata in data.items()}


def load_consumables() -> dict[str, Consumable]:
    with open(DATA_DIR / "consumables.json", encoding="utf-8") as f:
        data = json.load(f)
    return {cid: Consumable(id=cid, **cdata) for cid, cdata in data.items()}
