from __future__ import annotations

import pytest

from dnd_game.core.dice import d20, roll
from dnd_game.core.rng import seed


def test_roll_basic_in_range():
    seed(42)
    r = roll("1d6")
    assert 1 <= r.total <= 6
    assert len(r.rolls) == 1
    assert r.modifier == 0


def test_roll_with_positive_modifier():
    seed(1)
    r = roll("2d6+3")
    assert 5 <= r.total <= 15
    assert len(r.rolls) == 2
    assert r.modifier == 3


def test_roll_with_negative_modifier():
    seed(1)
    r = roll("1d20-2")
    assert -1 <= r.total <= 18
    assert r.modifier == -2


def test_invalid_expression_raises():
    with pytest.raises(ValueError):
        roll("garbage")
    with pytest.raises(ValueError):
        roll("0d6")
    with pytest.raises(ValueError):
        roll("d0")


def test_d20_advantage_keeps_higher_roll():
    seed(42)
    for _ in range(50):
        r = d20(0, advantage=True)
        assert len(r.rolls) == 2
        assert r.total == max(r.rolls)


def test_d20_disadvantage_keeps_lower_roll():
    seed(42)
    for _ in range(50):
        r = d20(0, disadvantage=True)
        assert len(r.rolls) == 2
        assert r.total == min(r.rolls)


def test_d20_crit_and_fumble_flags():
    seed(0)
    crits = fumbles = 0
    for _ in range(2000):
        r = d20()
        if r.crit:
            crits += 1
            assert r.rolls[0] == 20
        if r.fumble:
            fumbles += 1
            assert r.rolls[0] == 1
    # Each should happen ~100 times in 2000 — we just want non-zero.
    assert crits > 0
    assert fumbles > 0


def test_d20_modifier_applied_to_total():
    seed(7)
    r = d20(5)
    assert r.total == r.rolls[0] + 5
