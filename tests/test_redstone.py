"""Tests for the deterministic Redstone Logic Engine: signal attenuation, repeaters, comparators, pistons, and Java QC."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from redstone import RedstoneSimulator
import blocks


class MockWorld:
    def __init__(self, size=(32, 16, 32)):
        self.size = size
        self.grid = {}

    def inside(self, x, y, z):
        sx, sy, sz = self.size
        return 0 <= x < sx and 0 <= y < sy and 0 <= z < sz

    def get(self, x, y, z):
        return self.grid.get((x, y, z), 0)

    def set(self, x, y, z, b):
        self.grid[(x, y, z)] = b


def test_redstone_signal_dissipation():
    world = MockWorld()
    sim = RedstoneSimulator(world)

    # Set power source at (0, 1, 0) with power 15
    sim.set_power_source(0, 1, 0, power=15)

    assert sim.get_signal(0, 1, 0) == 15
    assert sim.get_signal(1, 1, 0) == 14
    assert sim.get_signal(5, 1, 0) == 10
    assert sim.get_signal(14, 1, 0) == 1
    # Beyond 15 blocks: signal dies out to 0
    assert sim.get_signal(15, 1, 0) == 0


def test_redstone_repeater_amplification_and_delay():
    world = MockWorld()
    sim = RedstoneSimulator(world)

    # Power source at (0, 1, 0) with attenuated power 3
    sim.set_power_source(0, 1, 0, power=3)
    # Repeater at (2, 1, 0) facing East (1, 0, 0) with 1-tick delay
    sim.add_repeater(2, 1, 0, direction=(1, 0, 0), delay_ticks=1)

    # Before tick: repeater has not activated output
    assert sim.repeaters[(2, 1, 0)].powered is False

    # Tick 1: repeater counts down and activates output
    sim.tick_redstone()
    assert sim.repeaters[(2, 1, 0)].powered is True
    # Output at (3, 1, 0) is amplified back to full 15!
    assert sim.get_signal(3, 1, 0) == 15


def test_redstone_comparator_modes():
    world = MockWorld()
    sim = RedstoneSimulator(world)

    # Comparator at (5, 1, 5) facing East (1, 0, 0)
    # Rear input A wire at (4, 1, 5), side input B wire at (5, 1, 6)
    sim.add_comparator(5, 1, 5, direction=(1, 0, 0), subtract_mode=False)
    sim.add_wire(4, 1, 5)
    sim.add_wire(5, 1, 6)

    # Test Compare Mode: A=10, B=6 -> Output=10
    sim.set_power_source(4, 1, 5, power=10)
    sim.set_power_source(5, 1, 6, power=6)
    sim.tick_redstone()
    assert sim.comparators[(5, 1, 5)].output_power == 10

    # Test Compare Mode when A < B: A=5, B=6 -> Output=0
    sim.set_power_source(4, 1, 5, power=5)
    sim.tick_redstone()
    assert sim.comparators[(5, 1, 5)].output_power == 0

    # Switch to Subtract Mode: A=10, B=6 -> Output = 10 - 6 = 4
    sim.comparators[(5, 1, 5)].subtract_mode = True
    sim.set_power_source(4, 1, 5, power=10)
    sim.tick_redstone()
    assert sim.comparators[(5, 1, 5)].output_power == 4


def test_piston_push_limit_and_immovable_blocks():
    world = MockWorld()
    sim = RedstoneSimulator(world)

    # Place piston at (5, 1, 5) facing East (1, 0, 0)
    sim.add_piston(5, 1, 5, direction=(1, 0, 0))

    # Place 3 dirt blocks in front: (6, 1, 5), (7, 1, 5), (8, 1, 5)
    world.set(6, 1, 5, blocks.DIRT)
    world.set(7, 1, 5, blocks.DIRT)
    world.set(8, 1, 5, blocks.DIRT)

    # Power piston directly
    sim.set_power_source(4, 1, 5, power=15)
    sim.tick_redstone()

    assert sim.pistons[(5, 1, 5)].extended is True
    assert world.get(6, 1, 5) == 0  # Extended arm space
    assert world.get(7, 1, 5) == blocks.DIRT
    assert world.get(8, 1, 5) == blocks.DIRT
    assert world.get(9, 1, 5) == blocks.DIRT

    # Test immovable block: Obsidian blocks piston extension
    world2 = MockWorld()
    sim2 = RedstoneSimulator(world2)
    sim2.add_piston(5, 1, 5, direction=(1, 0, 0))
    world2.set(6, 1, 5, blocks.OBSIDIAN)
    sim2.set_power_source(4, 1, 5, power=15)
    sim2.tick_redstone()
    # Piston cannot extend against Obsidian
    assert sim2.pistons[(5, 1, 5)].extended is False


def test_piston_quasi_connectivity():
    world = MockWorld()
    sim = RedstoneSimulator(world)

    # Piston at (5, 1, 5)
    sim.add_piston(5, 1, 5, direction=(1, 0, 0))
    world.set(6, 1, 5, blocks.STONE)

    # Power block at (5, 2, 5) directly above the piston (QC position)
    sim.set_power_source(5, 2, 5, power=15)
    sim.tick_redstone()

    # Java Quasi-Connectivity: piston extends when block above is powered!
    assert sim.pistons[(5, 1, 5)].extended is True
