"""Unified status-effect system.

Every status is a dataclass that inherits BaseStatus.  Hooks:
  on_apply(target)      — called once when the status is first applied.
  on_turn_start(target) — called at the start of *that combatant's* turn;
                          decrements duration, handles DOT damage, etc.
  on_expire(target)     — called just before the status is removed (duration==0).

Duration semantics:
  -1  = permanent (never auto-expires, removed explicitly)
   0  = expired (will be removed by Combatant.tick_statuses on next tick)
   N  = N more calls to on_turn_start before expiry
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..entities.combatant import Combatant


@dataclass
class BaseStatus:
    id: str = ""
    duration: int = -1

    def on_apply(self, target: "Combatant") -> list[str]:
        return []

    def on_turn_start(self, target: "Combatant") -> list[str]:
        if self.duration > 0:
            self.duration -= 1
        return []

    def on_expire(self, target: "Combatant") -> list[str]:
        return []


# ── Existing statuses (migrated from ad-hoc fields) ────────────────────────

@dataclass
class FrozenStatus(BaseStatus):
    """Skip next turn."""
    id: str = "frozen"


@dataclass
class EnragedStatus(BaseStatus):
    """Attack bonus when at low HP (rage_at_half trait)."""
    id: str = "enraged"
    attack_bonus: int = 2


@dataclass
class BlessedStatus(BaseStatus):
    """Altar blessing: +2 to attack rolls for N rounds."""
    id: str = "blessed"
    attack_bonus: int = 2


@dataclass
class DodgingStatus(BaseStatus):
    """Attacks against this target have disadvantage for one enemy phase."""
    id: str = "dodging"


@dataclass
class ShieldedStatus(BaseStatus):
    """Next incoming attack is blocked entirely (magic shield scroll)."""
    id: str = "shielded"


@dataclass
class ActionSurgeUsedStatus(BaseStatus):
    """Marks that Action Surge has been spent this combat."""
    id: str = "action_surge_used"


# ── Phase 1 statuses ────────────────────────────────────────────────────────

@dataclass
class RiposteStatus(BaseStatus):
    """On the next hit received, player makes a free counter-attack."""
    id: str = "riposte"


# ── Phase 2 statuses ────────────────────────────────────────────────────────

@dataclass
class PoisonedStatus(BaseStatus):
    """Deals damage each turn."""
    id: str = "poisoned"
    damage_per_turn: int = 2

    def on_turn_start(self, target: "Combatant") -> list[str]:
        msgs = super().on_turn_start(target)
        actual = target.take_damage(self.damage_per_turn)
        if actual > 0:
            msgs.append(f"  → яд: {actual} урона.")
        return msgs


@dataclass
class BurningStatus(BaseStatus):
    """Fire damage each turn."""
    id: str = "burning"
    damage_per_turn: int = 3

    def on_turn_start(self, target: "Combatant") -> list[str]:
        msgs = super().on_turn_start(target)
        actual = target.take_damage(self.damage_per_turn)
        if actual > 0:
            msgs.append(f"  → огонь: {actual} урона.")
        return msgs


@dataclass
class StaggeredStatus(BaseStatus):
    """Breaks enemy stance: skip 1 turn + receive double damage."""
    id: str = "staggered"


@dataclass
class StunnedStatus(BaseStatus):
    """Skip turn (from trip/knockdown)."""
    id: str = "stunned"


@dataclass
class WeakenedStatus(BaseStatus):
    """Attacks made by this combatant have disadvantage."""
    id: str = "weakened"


@dataclass
class MarkedStatus(BaseStatus):
    """Next hit against this target deals bonus damage."""
    id: str = "marked"
    bonus_damage: int = 3


# ── Registry ────────────────────────────────────────────────────────────────

# Map id → class for use by the effect resolver and save system.
STATUS_REGISTRY: dict[str, type[BaseStatus]] = {
    cls.id.default if hasattr(cls.id, "default") else cls.__dataclass_fields__["id"].default: cls  # type: ignore[attr-defined]
    for cls in [
        FrozenStatus, EnragedStatus, BlessedStatus, DodgingStatus, ShieldedStatus,
        ActionSurgeUsedStatus, RiposteStatus, PoisonedStatus, BurningStatus,
        StaggeredStatus, StunnedStatus, WeakenedStatus, MarkedStatus,
    ]
}
