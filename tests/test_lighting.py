"""Tests for the dual-channel lighting engine: skylight casting, blocklight diffusion, and circadian modulation."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from lighting import LightingEngine, get_block_opacity
import blocks


class MockWorld:
    def __init__(self, size=(16, 32, 16)):
        self.size = size
        self.grid = {}

    def inside(self, x, y, z):
        sx, sy, sz = self.size
        return 0 <= x < sx and 0 <= y < sy and 0 <= z < sz

    def get(self, x, y, z):
        return self.grid.get((x, y, z), blocks.AIR)

    def set(self, x, y, z, b):
        self.grid[(x, y, z)] = b


def test_skylight_vertical_penetration():
    world = MockWorld((8, 16, 8))
    # Place stone floor at y=4
    for x in range(8):
        for z in range(8):
            world.set(x, 4, z, blocks.STONE)

    engine = LightingEngine((8, 16, 8))
    engine.compute_initial_lighting(world)

    # Above floor (y=5..15) in open air, skylight should be max (15 or close)
    assert engine.skylight[4, 15, 4] == 15
    assert engine.skylight[4, 5, 4] == 15

    # Beneath solid stone floor (y=0..3), direct vertical skylight should be 0
    assert engine.skylight[4, 3, 4] == 0
    assert engine.skylight[4, 0, 4] == 0


def test_blocklight_emission_and_radial_falloff():
    world = MockWorld((16, 16, 16))
    # Place Glowstone at (8, 8, 8)
    world.set(8, 8, 8, blocks.GLOWSTONE)

    engine = LightingEngine((16, 16, 16))
    engine.compute_initial_lighting(world)

    # Center is 15
    assert engine.blocklight[8, 8, 8] == 15
    # 1 block away in air: 14
    assert engine.blocklight[9, 8, 8] == 14
    assert engine.blocklight[8, 9, 8] == 14
    assert engine.blocklight[8, 8, 9] == 14
    # 2 blocks away: 13
    assert engine.blocklight[10, 8, 8] == 13
    # 3 blocks away: 12
    assert engine.blocklight[11, 8, 8] == 12


def test_circadian_solar_modulation():
    world = MockWorld((8, 8, 8))
    engine = LightingEngine((8, 8, 8))
    engine.skylight[4, 4, 4] = 15

    # Daytime (zenith / noon) -> maximum perceived light
    light_day = engine.get_light(4, 4, 4, time_of_day=0.25)
    assert light_day > 0.90

    # Nighttime (midnight) -> ambient minimal light level
    light_night = engine.get_light(4, 4, 4, time_of_day=0.75)
    assert light_night < 0.20
    assert light_night >= 0.05
