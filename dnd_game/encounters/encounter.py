"""Encounter data classes. Effects live in game/state.py via _apply_effect()."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EncounterChoice:
    label: str
    requires: dict[str, Any] = field(default_factory=dict)
    check: dict[str, Any] | None = None
    effects: list[dict[str, Any]] = field(default_factory=list)
    on_success: list[dict[str, Any]] = field(default_factory=list)
    on_fail: list[dict[str, Any]] = field(default_factory=list)
    on_success_text: str = ""
    on_fail_text: str = ""
    branch: dict[str, Any] | None = None


@dataclass
class EncounterDef:
    id: str
    title: str
    description: str
    choices: list[EncounterChoice]
