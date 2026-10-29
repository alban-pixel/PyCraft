"""Unit tests for the cellular automata fluids: discrete levels, infinite sources, and reactions."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from fluids import FluidAutomata
from blocks import AIR, WATER, LAVA, OBSIDIAN, COBBLESTONE, STONE


class MockFluidWorld:
    def __init__(self, sx=16, sy=16, sz=16):
        self.size = (sx, sy, sz)
        self.grid = {}

    def inside(self, x, y, z):
        sx, sy, sz = self.size
        return 0 <= x < sx and 0 <= y < sy and 0 <= z < sz

    def get(self, x, y, z):
        return self.grid.get((x, y, z), AIR)

    def set(self, x, y, z, block):
        self.grid[(x, y, z)] = block

    def is_solid(self, x, y, z):
        return self.grid.get((x, y, z), AIR) in (STONE, COBBLESTONE, OBSIDIAN)


def test_infinite_water_source_generation():
    w = MockFluidWorld()
    # Solid floor at y=0
    for x in range(5):
        for z in range(5):
            w.set(x, 0, z, STONE)

    automata = FluidAutomata(w)

    # Place two water sources at (1, 1, 2) and (3, 1, 2)
    # Target center block is (2, 1, 2) which is AIR with solid underneath
    w.set(1, 1, 2, WATER)
    automata.add_fluid(1, 1, 2, WATER, level=0)
    w.set(3, 1, 2, WATER)
    automata.add_fluid(3, 1, 2, WATER, level=0)

    # Tick: center block (2, 1, 2) should regenerate into a new WATER source
    automata.tick()
    assert w.get(2, 1, 2) == WATER
    assert automata.fluid_voxels.get((2, 1, 2)).level == 0


def test_hydrothermal_water_onto_lava_source_makes_obsidian():
    w = MockFluidWorld()
    automata = FluidAutomata(w)

    # Lava source at (5, 5, 5)
    w.set(5, 5, 5, LAVA)
    automata.add_fluid(5, 5, 5, LAVA, level=0)

    # Water adjacent at (5, 5, 6)
    w.set(5, 5, 6, WATER)
    automata.add_fluid(5, 5, 6, WATER, level=0)

    # Tick hydrothermal reaction
    automata.tick()
    # Lava source touching water turns into OBSIDIAN!
    assert w.get(5, 5, 5) == OBSIDIAN


def test_hydrothermal_water_onto_flowing_lava_makes_cobblestone():
    w = MockFluidWorld()
    automata = FluidAutomata(w)

    # Flowing lava (level 2) at (5, 5, 5)
    w.set(5, 5, 5, LAVA)
    automata.add_fluid(5, 5, 5, LAVA, level=2)

    # Water adjacent at (5, 5, 6)
    w.set(5, 5, 6, WATER)
    automata.add_fluid(5, 5, 6, WATER, level=0)

    automata.tick()
    # Flowing lava touching water turns into COBBLESTONE!
    assert w.get(5, 5, 5) == COBBLESTONE
