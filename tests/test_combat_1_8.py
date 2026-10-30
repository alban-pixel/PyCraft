"""Unit tests for Vanilla 1.8 combat parity, critical hits, armor mitigation, and spam clicking."""
import math
import pytest
from combat import (
    CombatEngine, InvulnerabilityTracker, calculate_1_8_armor,
    calculate_attack_damage, calculate_damage_with_crit, is_critical_hit
)


def test_1_8_armor_formula():
    assert calculate_1_8_armor(10.0, 0.0) == 10.0
    # 20 defense points -> 80% reduction -> deals 20%
    assert math.isclose(calculate_1_8_armor(10.0, 20.0), 2.0)
    # 10 defense points -> 40% reduction -> deals 60%
    assert math.isclose(calculate_1_8_armor(10.0, 10.0), 6.0)
    # Armor capped at 20 points
    assert math.isclose(calculate_1_8_armor(10.0, 30.0), 2.0)
    # Negative or zero damage
    assert calculate_1_8_armor(-5.0, 10.0) == 0.0
    assert calculate_1_8_armor(0.0, 10.0) == 0.0


def test_1_8_critical_hits():
    assert is_critical_hit(vel_y=-0.5, on_ground=False, in_water=False) is True
    assert is_critical_hit(vel_y=0.5, on_ground=False, in_water=False) is False
    assert is_critical_hit(vel_y=-0.5, on_ground=True, in_water=False) is False
    assert is_critical_hit(vel_y=-0.5, on_ground=False, in_water=True) is False

    assert calculate_damage_with_crit(10.0, is_crit=False) == 10.0
    assert calculate_damage_with_crit(10.0, is_crit=True) == 15.0


def test_1_8_spam_clicking():
    # Full base damage regardless of zero elapsed ticks
    assert calculate_attack_damage(7.0, elapsed_ticks=0) == 7.0
    assert calculate_attack_damage(7.0, elapsed_ticks=10) == 7.0


def test_10_tick_invulnerability_differential():
    tracker = InvulnerabilityTracker()
    assert tracker.attempt_damage(5.0) == 5.0
    assert tracker.invulnerable_ticks == 10

    tracker.tick()
    assert tracker.invulnerable_ticks == 9
    # Weaker hit during immunity
    assert tracker.attempt_damage(3.0) == 0.0
    # Stronger hit during immunity takes differential
    assert tracker.attempt_damage(8.0) == 3.0
