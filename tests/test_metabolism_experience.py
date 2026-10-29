"""Unit tests for the Player Metabolism, Hunger, Saturation, and 3-Tier Polynomial XP."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from metabolism import (
    Metabolism, TICKS_SATURATED_REGEN, TICKS_STANDARD_REGEN, TICKS_STARVATION,
    EXHAUSTION_HEAL_PER_HP, EXHAUSTION_SPRINT_PER_M,
)


def test_metabolism_initial_state():
    meta = Metabolism()
    assert meta.health == 20
    assert meta.food == 20
    assert meta.saturation == 5.0
    assert meta.exhaustion == 0.0
    assert meta.can_sprint is True
    assert meta.level == 0
    assert meta.level_progress == 0.0


def test_exhaustion_depletes_saturation_then_food():
    meta = Metabolism()
    meta.saturation = 2.0
    meta.food = 20

    # Adding 4.0 exhaustion should deplete 1.0 saturation
    meta.add_exhaustion(4.0)
    assert meta.saturation == 1.0
    assert meta.food == 20
    assert meta.exhaustion == 0.0

    # Deplete remaining saturation
    meta.add_exhaustion(4.0)
    assert meta.saturation == 0.0
    assert meta.food == 20

    # Now that saturation is 0, exhaustion depletes food!
    meta.add_exhaustion(4.0)
    assert meta.saturation == 0.0
    assert meta.food == 19


def test_sprint_disabled_when_hungry():
    meta = Metabolism()
    meta.food = 7
    assert meta.can_sprint is True

    meta.food = 6
    assert meta.can_sprint is False

    meta.food = 0
    assert meta.can_sprint is False


def test_saturated_fast_regeneration():
    meta = Metabolism()
    meta.health = 15
    meta.food = 20
    meta.saturation = 5.0

    # Tick 9 ticks -> no healing yet
    for _ in range(TICKS_SATURATED_REGEN - 1):
        h, d = meta.tick()
        assert h == 0

    # 10th tick -> +1 HP healed, +6.0 exhaustion added
    h, d = meta.tick()
    assert h == 1
    assert meta.health == 16
    # 6.0 exhaustion caused 4.0 to trigger: 1 saturation lost, 2.0 remaining exhaustion
    assert meta.saturation == 4.0
    assert meta.exhaustion == 2.0


def test_standard_regeneration():
    meta = Metabolism()
    meta.health = 15
    meta.food = 19
    meta.saturation = 0.0  # No saturation -> standard regen

    # Tick 79 ticks -> no healing yet
    for _ in range(TICKS_STANDARD_REGEN - 1):
        h, d = meta.tick()
        assert h == 0

    # 80th tick -> +1 HP healed
    h, d = meta.tick()
    assert h == 1
    assert meta.health == 16


def test_starvation_damage():
    meta = Metabolism()
    meta.health = 10
    meta.food = 0
    meta.saturation = 0.0

    for _ in range(TICKS_STARVATION - 1):
        h, d = meta.tick(difficulty="hard")
        assert d == 0

    h, d = meta.tick(difficulty="hard")
    assert d == 1
    assert meta.health == 9


def test_food_consumption():
    meta = Metabolism()
    meta.food = 10
    meta.saturation = 0.0

    # Eat Cooked Pork (ID 110: +8 food, +12.8 sat)
    consumed = meta.eat(110)
    assert consumed is True
    assert meta.food == 18
    # Saturation is capped at current food level (18)
    assert meta.saturation == 12.8

    # Cannot eat when full
    meta.food = 20
    assert meta.eat(110) is False

    # Golden Apple (114) can be eaten even when full
    assert meta.eat(114) is True


def test_polynomial_xp_calculations():
    # Tier 1 (L <= 16): Total XP = L^2 + 6L
    assert Metabolism.get_xp_for_level(0) == 0
    assert Metabolism.get_xp_for_level(1) == 7
    assert Metabolism.get_xp_for_level(15) == 15 * 15 + 6 * 15  # 315

    # Tier 2 (16 < L <= 31): Total XP = 2.5 L^2 - 40.5 L + 360
    assert Metabolism.get_xp_for_level(16) == 352
    assert Metabolism.get_xp_for_level(30) == int(2.5 * 900 - 40.5 * 30 + 360)  # 1395

    # Tier 3 (L > 31): Total XP = 4.5 L^2 - 162.5 L + 2220
    assert Metabolism.get_xp_for_level(32) == int(4.5 * 32 * 32 - 162.5 * 32 + 2220)

    # XP progression
    meta = Metabolism()
    assert meta.level == 0
    meta.add_xp(7)
    assert meta.level == 1
    assert meta.level_progress == 0.0
