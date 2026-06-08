"""Core combat math: attack rolls, damage rolls, results.

Independent of UI and entity classes — it only sees primitive numbers / strings.
This is the part that should stay rock-solid; tests in tests/test_combat.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..core.dice import Roll, d20, roll


@dataclass
class AttackResult:
    attacker: str
    target: str
    attack_roll: Roll
    target_ac: int
    hit: bool
    crit: bool
    damage_rolls: list[Roll] = field(default_factory=list)
    damage_total: int = 0
    damage_type: str = "physical"
    log: str = ""


def make_attack(
    *,
    attacker_name: str,
    target_name: str,
    attack_bonus: int,
    damage_expression: str,
    damage_modifier: int,
    target_ac: int,
    damage_type: str = "physical",
    advantage: bool = False,
    disadvantage: bool = False,
) -> AttackResult:
    """Resolve a single attack action.

    Rules followed:
    - Nat 20 = always hits + critical (double dice, single modifier).
    - Nat 1 = always misses.
    - Otherwise hit if ``attack_total >= target_ac``.
    """
    attack = d20(attack_bonus, advantage=advantage, disadvantage=disadvantage)

    hit = attack.crit or (not attack.fumble and attack.total >= target_ac)
    crit = attack.crit and not attack.fumble

    damage_rolls: list[Roll] = []
    damage_total = 0
    if hit:
        base = roll(damage_expression)
        damage_rolls.append(base)
        damage_total = base.total + damage_modifier
        if crit:
            # 5e crit: roll the weapon's damage dice an extra time, no extra mod.
            extra = roll(damage_expression)
            damage_rolls.append(extra)
            damage_total += sum(extra.rolls)
        damage_total = max(1, damage_total) if hit else 0

    if attack.fumble:
        log = f"{attacker_name} → {target_name}: натуральная 1, промах."
    elif crit:
        log = (
            f"{attacker_name} → {target_name}: КРИТ! {attack} vs AC {target_ac}, "
            f"урон {damage_total}."
        )
    elif hit:
        log = (
            f"{attacker_name} → {target_name}: {attack} vs AC {target_ac} → попадание, "
            f"урон {damage_total}."
        )
    else:
        log = f"{attacker_name} → {target_name}: {attack} vs AC {target_ac} → промах."

    return AttackResult(
        attacker=attacker_name,
        target=target_name,
        attack_roll=attack,
        target_ac=target_ac,
        hit=hit,
        crit=crit,
        damage_rolls=damage_rolls,
        damage_total=damage_total,
        damage_type=damage_type,
        log=log,
    )


def ability_check(modifier_value: int, dc: int, *, advantage: bool = False, disadvantage: bool = False) -> tuple[bool, Roll]:
    """Generic ability check / save: d20+mod vs DC."""
    r = d20(modifier_value, advantage=advantage, disadvantage=disadvantage)
    return r.total >= dc, r
