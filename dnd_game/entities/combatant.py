"""Shared combat base for Character and Monster.

Provides: hp, statuses, resources, take_damage, heal, tick_statuses.
UI and world layers (tcod) are never imported here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..rules.status import BaseStatus


@dataclass
class Combatant:
    max_hp: int = 0
    current_hp: int = 0
    statuses: list["BaseStatus"] = field(default_factory=list)
    resources: dict[str, int] = field(default_factory=dict)

    # ── HP ──────────────────────────────────────────────────────────────────

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    def take_damage(self, amount: int) -> int:
        amount = max(0, amount)
        self.current_hp = max(0, self.current_hp - amount)
        return amount

    def heal(self, amount: int) -> int:
        before = self.current_hp
        self.current_hp = min(self.max_hp, self.current_hp + max(0, amount))
        return self.current_hp - before

    # ── Statuses ─────────────────────────────────────────────────────────────

    def add_status(self, status: "BaseStatus") -> list[str]:
        existing = self.get_status(status.id)
        if existing is not None:
            # Refresh duration to the longer of the two.
            if status.duration == -1 or (existing.duration != -1 and status.duration > existing.duration):
                existing.duration = status.duration
            return []
        self.statuses.append(status)
        return status.on_apply(self)

    def remove_status(self, status_id: str) -> None:
        self.statuses = [s for s in self.statuses if s.id != status_id]

    def has_status(self, status_id: str) -> bool:
        return any(s.id == status_id for s in self.statuses)

    def get_status(self, status_id: str) -> "BaseStatus | None":
        for s in self.statuses:
            if s.id == status_id:
                return s
        return None

    def tick_statuses(self) -> list[str]:
        """Call on_turn_start for all statuses; remove expired ones."""
        messages: list[str] = []
        for status in list(self.statuses):
            msgs = status.on_turn_start(self)
            messages.extend(msgs)
        expired = [s for s in self.statuses if s.duration == 0]
        for s in expired:
            messages.extend(s.on_expire(self))
            self.remove_status(s.id)
        return messages

    # ── Resources ────────────────────────────────────────────────────────────

    def get_resource(self, name: str, default: int = 0) -> int:
        return self.resources.get(name, default)

    def set_resource(self, name: str, value: int) -> None:
        self.resources[name] = value

    def mod_resource(self, name: str, delta: int, *, min_val: int = 0, max_val: int = 9999) -> int:
        """Change resource by delta, clamped to [min_val, max_val]. Returns actual change."""
        current = self.get_resource(name)
        new_val = max(min_val, min(max_val, current + delta))
        self.resources[name] = new_val
        return new_val - current
