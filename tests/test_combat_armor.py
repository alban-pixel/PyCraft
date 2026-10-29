"""Unit tests for the Combat engine, Armor formula, EPF, Invulnerability, and A* pathfinding."""
import math
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from combat import (
    CombatEngine, InvulnerabilityTracker, MobCapManager, AStarPathfinder,
    INVULNERABILITY_TICKS
)


class MockWorldAStar:
    def __init__(self, solids=None):
        self.solids = set(solids or [])

    def is_solid(self, x, y, z):
        return (x, y, z) in self.solids


def test_armor_mitigation_formula():
    # Base case: 0 armor -> no reduction
    assert CombatEngine.calculate_armor_damage(10.0, armor=0.0) == 10.0

    # 20 armor points, 0 toughness, 4 damage:
    # reduction_val = max(20/5, 20 - (4*4)/(8+0)) = max(4, 20 - 2) = 18.
    # min(20, 18) = 18.
    # multiplier = 1 - 18/25 = 1 - 0.72 = 0.28 (72% damage reduction)
    # net = 4 * 0.28 = 1.12
    dmg_net = CombatEngine.calculate_armor_damage(4.0, armor=20.0, toughness=0.0)
    assert math.isclose(dmg_net, 1.12, rel_tol=1e-5)

    # High damage (30 damage) on armor with high toughness (T=8) vs low toughness (T=0)
    dmg_low_t = CombatEngine.calculate_armor_damage(30.0, armor=20.0, toughness=0.0)
    dmg_high_t = CombatEngine.calculate_armor_damage(30.0, armor=20.0, toughness=8.0)
    # Higher toughness reduces damage much more under heavy hits!
    assert dmg_high_t < dmg_low_t


def test_protection_epf_formula():
    # EPF = 20 gives maximum 80% damage reduction: (20 * 4) / 100 = 0.80
    mitigated = CombatEngine.apply_protection_enchantment(10.0, epf=20)
    assert math.isclose(mitigated, 2.0, rel_tol=1e-5)

    # EPF = 10 gives 40% reduction
    mitigated_half = CombatEngine.apply_protection_enchantment(10.0, epf=10)
    assert math.isclose(mitigated_half, 6.0, rel_tol=1e-5)


def test_invulnerability_window_and_differential_damage():
    tracker = InvulnerabilityTracker()
    assert tracker.invulnerable_ticks == 0

    # Initial hit of 4 damage
    taken1 = tracker.attempt_damage(4.0)
    assert taken1 == 4.0
    assert tracker.invulnerable_ticks == INVULNERABILITY_TICKS

    # Weaker hit of 2 damage during invulnerability -> blocked completely (0.0)
    taken2 = tracker.attempt_damage(2.0)
    assert taken2 == 0.0

    # Stronger hit of 7 damage during invulnerability -> only takes difference (7 - 4 = 3)
    taken3 = tracker.attempt_damage(7.0)
    assert taken3 == 3.0

    # Wait out the 10 ticks
    for _ in range(INVULNERABILITY_TICKS):
        tracker.tick()
    assert tracker.invulnerable_ticks == 0

    # New hit of 5 damage applies fully
    taken4 = tracker.attempt_damage(5.0)
    assert taken4 == 5.0


def test_mob_cap_and_despawn_radii():
    # Mob cap for 289 chunks (17x17)
    cap_hostile = MobCapManager.get_mob_cap(chunk_count=289, is_hostile=True)
    assert cap_hostile == 70

    cap_passive = MobCapManager.get_mob_cap(chunk_count=289, is_hostile=False)
    assert cap_passive == 10

    # Despawn radii
    assert MobCapManager.evaluate_despawn(15.0) == "keep"
    assert MobCapManager.evaluate_despawn(30.0) == "keep"
    assert MobCapManager.evaluate_despawn(150.0) == "instant_despawn"


def test_astar_pathfinding():
    # Flat surface along X: ground at y=0, walkable at y=1
    solids = [(x, 0, 0) for x in range(10)]
    world = MockWorldAStar(solids)

    path = AStarPathfinder.find_path(world, start=(0, 1, 0), goal=(5, 1, 0))
    assert path is not None
    assert path[0] == (0, 1, 0)
    assert path[-1] == (5, 1, 0)
    assert len(path) == 6  # 0, 1, 2, 3, 4, 5
