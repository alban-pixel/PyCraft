import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import blocks
from world import World


def test_fluid_downward_flow():
    w = World(size=(16, 32, 16), seed=1, generate=False)
    # Place water in air at (5, 10, 5)
    w.set(5, 10, 5, blocks.WATER)
    w.trigger_water(5, 10, 5)

    assert (5, 10, 5) in w.active_water
    assert w.get(5, 9, 5) == blocks.AIR

    # Tick fluids: water should flow straight down
    modified = w.tick_fluids()
    assert w.get(5, 9, 5) == blocks.WATER
    assert (0, 0) in modified  # chunk (0, 0) for (5, 5)
    assert (5, 9, 5) in w.active_water


def test_fluid_horizontal_spread():
    w = World(size=(16, 32, 16), seed=1, generate=False)
    # Solid block underneath at (5, 4, 5)
    w.set(5, 4, 5, blocks.STONE)
    w.set(5, 5, 5, blocks.WATER)
    w.trigger_water(5, 5, 5)

    # When downward path is blocked, water spreads horizontally
    modified = w.tick_fluids()
    assert (0, 0) in modified
    assert w.get(6, 5, 5) == blocks.WATER
    assert w.get(4, 5, 5) == blocks.WATER
    assert w.get(5, 5, 6) == blocks.WATER
    assert w.get(5, 5, 4) == blocks.WATER


def test_fluid_no_active_water():
    w = World(size=(16, 32, 16), seed=1, generate=False)
    assert len(w.active_water) == 0
    modified = w.tick_fluids()
    assert modified == set()
