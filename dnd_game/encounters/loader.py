"""Loads encounters.json into EncounterDef objects."""
from __future__ import annotations

import json
from pathlib import Path

from .encounter import EncounterChoice, EncounterDef

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def load_encounters() -> dict[str, EncounterDef]:
    with open(DATA_DIR / "encounters.json", encoding="utf-8") as f:
        data = json.load(f)
    result: dict[str, EncounterDef] = {}
    for eid, edata in data.items():
        choices = [EncounterChoice(**c) for c in edata["choices"]]
        result[eid] = EncounterDef(
            id=eid,
            title=edata["title"],
            description=edata["description"],
            choices=choices,
        )
    return result
