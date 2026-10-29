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


def test_fluid_max_spread_limit():
    # Long strip of stone floor at y=0, air above
    w = World(size=(32, 16, 16), seed=1, generate=False)
    for x in range(32):
        for z in range(16):
            w.set(x, 0, z, blocks.STONE)

    # Place single water source at (15, 1, 8)
    w.set(15, 1, 8, blocks.WATER)
    w.trigger_water(15, 1, 8)

    # Tick fluids multiple times until settled
    for _ in range(15):
        w.tick_fluids()

    # Max horizontal spread distance is 7 blocks: x=15+7=22 should have water, x=15+8=23 MUST be air!
    assert w.get(15 + 7, 1, 8) == blocks.WATER
    assert w.get(15 + 8, 1, 8) == blocks.AIR
    assert w.get(15 - 7, 1, 8) == blocks.WATER
    assert w.get(15 - 8, 1, 8) == blocks.AIR


def test_fluid_dissipation_when_source_removed():
    w = World(size=(16, 16, 16), seed=1, generate=False)
    for x in range(16):
        for z in range(16):
            w.set(x, 0, z, blocks.STONE)

    # Place water source at (5, 1, 5)
    w.set(5, 1, 5, blocks.WATER)
    w.trigger_water(5, 1, 5)

    # Flow outward for 3 ticks
    for _ in range(3):
        w.tick_fluids()

    assert w.get(6, 1, 5) == blocks.WATER

    # Remove the water source (turn it back to AIR)
    w.set(5, 1, 5, blocks.AIR)
    w.trigger_water(5, 1, 5)

    # Tick fluids until all dependent flowing water dissipates
    for _ in range(6):
        w.tick_fluids()

    # All flowing cells should have dissipated back to AIR
    assert w.get(6, 1, 5) == blocks.AIR
    assert w.get(4, 1, 5) == blocks.AIR
    assert w.get(5, 1, 6) == blocks.AIR
    assert w.get(5, 1, 4) == blocks.AIR

