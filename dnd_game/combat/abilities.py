"""Loader for data/abilities.json — maneuvers and combat abilities."""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"

_CACHE: dict[str, dict] | None = None


def _load() -> dict[str, dict]:
    global _CACHE
    if _CACHE is None:
        path = DATA_DIR / "abilities.json"
        if path.exists():
            with open(path, encoding="utf-8") as f:
                _CACHE = json.load(f)
        else:
            _CACHE = {}
    return _CACHE


def get_ability(ability_id: str) -> dict | None:
    return _load().get(ability_id)


def all_maneuver_ids() -> list[str]:
    return [k for k, v in _load().items() if v.get("type") == "maneuver"]


# Convenience registry exposed to Character.class_features_ru
ABILITY_REGISTRY: dict[str, dict] = {}


def _refresh_registry() -> None:
    ABILITY_REGISTRY.clear()
    ABILITY_REGISTRY.update(_load())


# Populate on import (lazy-ish — file may not exist yet during first load).
try:
    _refresh_registry()
except Exception:
    pass
