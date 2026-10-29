"""Tests for multi-dimensional topology, Nether portals, void damage, and Elytra aerodynamics."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from dimension import Dimension, PortalManager, DimensionManager, ElytraPhysics
import blocks


class MockWorld:
    def __init__(self, size=(32, 32, 32)):
        self.size = size
        self.grid = {}

    def inside(self, x, y, z):
        sx, sy, sz = self.size
        return 0 <= x < sx and 0 <= y < sy and 0 <= z < sz

    def get(self, x, y, z):
        return self.grid.get((x, y, z), 0)

    def set(self, x, y, z, b):
        self.grid[(x, y, z)] = b


def test_nether_coordinate_scaling():
    # 1 Nether block = 8 Overworld blocks
    overworld_pos = (800.0, 64.0, -1600.0)
    nether_pos = PortalManager.convert_coordinates(overworld_pos, Dimension.OVERWORLD, Dimension.NETHER)
    assert nether_pos == (100.0, 64.0, -200.0)

    roundtrip = PortalManager.convert_coordinates(nether_pos, Dimension.NETHER, Dimension.OVERWORLD)
    assert roundtrip == (800.0, 64.0, -1600.0)


def test_nether_portal_frame_validation():
    world = MockWorld()
    # Build complete 4x5 obsidian frame along X at (5, 5, 5)
    for dy in range(5):
        for dx in range(4):
            if dy == 0 or dy == 4 or dx == 0 or dx == 3:
                world.set(5 + dx, 5 + dy, 5, blocks.OBSIDIAN)

    # Frame is valid
    assert PortalManager.validate_nether_portal(world, 5, 5, 5, axis="x") is True

    # Break one corner/border block -> invalid
    world.set(5, 5, 5, blocks.AIR)
    assert PortalManager.validate_nether_portal(world, 5, 5, 5, axis="x") is False


def test_dimension_environmental_rules():
    # Water placement check
    assert DimensionManager.can_place_water(Dimension.OVERWORLD) is True
    assert DimensionManager.can_place_water(Dimension.NETHER) is False  # Evaporates!

    # Void damage check
    assert DimensionManager.check_void_damage(10.0, Dimension.END) == 0
    assert DimensionManager.check_void_damage(-5.0, Dimension.END) == 4  # Below Y=0 in End


def test_elytra_gliding_and_diving():
    elytra = ElytraPhysics()
    assert elytra.gliding is False

    # Start gliding from fall
    elytra.start_gliding(fall_speed=-1.0)
    assert elytra.gliding is True
    assert elytra.speed >= 1.0

    # Dive down (-45 degrees) for 1 second -> should accelerate speed
    initial_speed = elytra.speed
    horiz, vert = elytra.update(pitch=-45.0, dt=1.0)
    assert elytra.speed > initial_speed
    assert vert < 0  # Falling downwards with dive

    # Pull up (+30 degrees) -> converts speed to vertical climb
    fast_speed = elytra.speed
    horiz_climb, vert_climb = elytra.update(pitch=30.0, dt=0.5)
    assert vert_climb > 0  # Climbing!
    assert elytra.speed < fast_speed  # Decelerates while climbing
