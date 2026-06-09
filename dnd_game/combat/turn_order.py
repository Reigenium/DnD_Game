"""CTB (Conditional Turn Battle) timeline — inspired by Final Fantasy X.

Speed formula: speed = max(1, 3 + dex_modifier)
Base delay   : 100 // speed   (lower = acts more often)

Player always starts first (initial ticks = 0).
Enemies start at base_delay + random jitter [0, base_delay//4].

After acting, a combatant's ticks reset to base_delay.
Haste would multiply base_delay by 0.7; Slow by 1.5.

UI uses preview_next_n(7) to show the turn-order strip.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _Entry:
    actor: object
    ticks: int
    base_delay: int


def _speed_of(combatant) -> int:
    try:
        dex_mod = combatant.mod("dex")
    except Exception:
        dex_mod = 0
    return max(1, 3 + dex_mod)


class TurnOrder:
    def __init__(self, combatants: list, rng) -> None:
        self._entries: list[_Entry] = []
        player = combatants[0] if combatants else None
        for c in combatants:
            speed = _speed_of(c)
            base_delay = 100 // speed
            # Player goes first.
            initial = 0 if c is player else base_delay + rng.randint(0, max(1, base_delay // 4))
            self._entries.append(_Entry(actor=c, ticks=initial, base_delay=base_delay))
        self._sort()

    def _sort(self) -> None:
        self._entries.sort(key=lambda e: e.ticks)

    # ── Public API ────────────────────────────────────────────────────────

    def enemies_in_order(self) -> list:
        """Return all non-player entries sorted by speed (fastest first)."""
        from ..entities.monster import Monster
        return [e.actor for e in self._entries if isinstance(e.actor, Monster)]

    def remove(self, actor) -> None:
        self._entries = [e for e in self._entries if e.actor is not actor]

    def add_delay(self, actor, extra: int) -> None:
        """Push actor's turn further into the future (stagger, slow)."""
        for e in self._entries:
            if e.actor is actor:
                e.ticks += extra
                break
        self._sort()

    def preview_next_n(self, n: int) -> list:
        """Simulate and return next n actors in turn order (for UI strip)."""
        sim = [[e.actor, e.ticks, e.base_delay] for e in self._entries]
        result: list = []
        for _ in range(n * 3):  # upper bound to avoid infinite loop
            if len(result) >= n:
                break
            sim.sort(key=lambda e: e[1])
            actor = sim[0][0]
            result.append(actor)
            sim[0][1] += sim[0][2]
        return result[:n]
