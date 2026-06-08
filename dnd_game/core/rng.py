"""Shared RNG. Use `seed()` to make a run reproducible (handy for tests)."""
from __future__ import annotations

import random

_rng = random.Random()


def seed(value: int | None = None) -> None:
    _rng.seed(value)


def get_rng() -> random.Random:
    return _rng
