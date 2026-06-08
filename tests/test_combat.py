from __future__ import annotations

from dnd_game.core.rng import seed
from dnd_game.rules.combat import make_attack


def test_hit_at_or_above_ac():
    seed(1)
    hits, misses = 0, 0
    for _ in range(2000):
        r = make_attack(
            attacker_name="A", target_name="B",
            attack_bonus=5,
            damage_expression="1d6", damage_modifier=2,
            target_ac=10,
        )
        if r.hit:
            hits += 1
            assert r.damage_total > 0
        else:
            misses += 1
            assert r.damage_total == 0
    assert hits > misses, "with +5 vs AC10 should hit far more often than miss"


def test_natural_20_always_hits_and_crits():
    seed(42)
    saw_crit = False
    for _ in range(2000):
        r = make_attack(
            attacker_name="A", target_name="B",
            attack_bonus=-5,
            damage_expression="1d6", damage_modifier=0,
            target_ac=99,  # impossible without nat 20
        )
        if r.attack_roll.crit:
            saw_crit = True
            assert r.hit
            assert r.crit
            assert r.damage_total >= 2  # crit always doubles dice
    assert saw_crit, "nat 20 should occur in 2000 rolls"


def test_natural_1_always_misses():
    seed(0)
    saw_fumble = False
    for _ in range(2000):
        r = make_attack(
            attacker_name="A", target_name="B",
            attack_bonus=100,  # would always hit otherwise
            damage_expression="1d6", damage_modifier=0,
            target_ac=0,
        )
        if r.attack_roll.fumble:
            saw_fumble = True
            assert not r.hit
            assert r.damage_total == 0
    assert saw_fumble, "nat 1 should occur in 2000 rolls"


def test_advantage_increases_hit_rate():
    seed(0)
    normal_hits = 0
    for _ in range(2000):
        r = make_attack(
            attacker_name="A", target_name="B",
            attack_bonus=0,
            damage_expression="1d4", damage_modifier=0,
            target_ac=15,
        )
        if r.hit:
            normal_hits += 1

    seed(0)
    adv_hits = 0
    for _ in range(2000):
        r = make_attack(
            attacker_name="A", target_name="B",
            attack_bonus=0,
            damage_expression="1d4", damage_modifier=0,
            target_ac=15,
            advantage=True,
        )
        if r.hit:
            adv_hits += 1

    assert adv_hits > normal_hits, "advantage must hit more often than a flat roll"


def test_damage_includes_modifier_on_hit():
    seed(11)
    found = False
    for _ in range(500):
        r = make_attack(
            attacker_name="A", target_name="B",
            attack_bonus=10,
            damage_expression="1d4", damage_modifier=3,
            target_ac=5,
        )
        if r.hit and not r.crit:
            assert r.damage_total >= 1 + 3
            assert r.damage_total <= 4 + 3
            found = True
            break
    assert found
