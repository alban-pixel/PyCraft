import numpy as np

import blocks as B
import items as I
import recipes as R
from furnace import FurnaceState, Furnaces
from inventory import EMPTY
from sim import Simulation
from world import World

Y = 3000
POS = (0, Y, 0)


def bench(block=B.FURNACE):
    world = World(11)
    sim = Simulation(world, lambda *a: None)
    furnaces = Furnaces()
    sim.every_tick.append(furnaces.tick)
    sim.set_block(*POS, block)
    return world, sim, furnaces


def run(sim, ticks):
    for _ in range(ticks):
        sim.tick()


def test_smelts_iron_with_coal():
    world, sim, furnaces = bench()
    f = furnaces.get(POS)
    f.slots = [(B.IRON_ORE, 8, 0), (I.COAL, 1, 0), EMPTY]
    run(sim, 8 * R.COOK_TICKS + 5)
    assert f.slots == [EMPTY, EMPTY, (I.IRON_INGOT, 8, 0)]
    assert world.get(*POS) == B.FURNACE


def test_lit_while_burning():
    world, sim, furnaces = bench(B.FURNACE_SOUTH)
    furnaces.get(POS).slots = [(B.SAND, 1, 0), (B.PLANKS, 1, 0), EMPTY]
    run(sim, 5)
    assert world.get(*POS) == B.FURNACE_ON_SOUTH
    assert furnaces.get(POS).slots[1] == EMPTY  # the planks are burning
    run(sim, 300)  # 1.5 items' worth of fire: one sand cooks, then the fire dies down
    assert world.get(*POS) == B.FURNACE_SOUTH
    assert furnaces.get(POS).slots[2] == (B.GLASS, 1, 0)


def test_output_full_stops():
    world, sim, furnaces = bench()
    f = furnaces.get(POS)
    f.slots = [(B.SAND, 5, 0), (I.COAL, 1, 0), (B.GLASS, 63, 0)]
    run(sim, 3 * R.COOK_TICKS)
    assert f.slots[2] == (B.GLASS, 64, 0) and f.slots[0] == (B.SAND, 4, 0)
    assert f.cook == 0


def test_output_holds_something_else():
    world, sim, furnaces = bench()
    f = furnaces.get(POS)
    f.slots = [(B.SAND, 5, 0), (I.COAL, 1, 0), (I.IRON_INGOT, 1, 0)]
    run(sim, 50)
    assert f.slots[1] == (I.COAL, 1, 0) and f.burn_left == 0  # nothing can come out: no coal burnt


def test_no_fuel_no_cook():
    world, sim, furnaces = bench()
    f = furnaces.get(POS)
    f.slots = [(B.IRON_ORE, 1, 0), EMPTY, EMPTY]
    run(sim, 400)
    assert f.slots[0] == (B.IRON_ORE, 1, 0) and f.cook == 0 and world.get(*POS) == B.FURNACE


def test_fuel_spent_only_when_smelting():
    world, sim, furnaces = bench()
    f = furnaces.get(POS)
    f.slots = [(B.DIRT, 3, 0), (I.COAL, 2, 0), EMPTY]
    run(sim, 100)
    assert f.slots[1] == (I.COAL, 2, 0)


def test_array_roundtrip():
    world, sim, furnaces = bench()
    f = furnaces.get(POS)
    f.slots = [(B.IRON_ORE, 3, 0), (I.COAL, 2, 0), (I.IRON_INGOT, 4, 0)]
    f.burn_left, f.burn_total, f.cook = 120, 1600, 37
    arr = furnaces.to_array()
    assert arr.shape == (1, 12) and arr.dtype == np.int64
    back = Furnaces.from_array(arr).get(POS)
    assert back == FurnaceState([(B.IRON_ORE, 3, 0), (I.COAL, 2, 0), (I.IRON_INGOT, 4, 0)], 120, 1600, 37)
    assert Furnaces.from_array(np.zeros((0, 12), np.int64)).states == {}


def test_removed_when_block_gone():
    world, sim, furnaces = bench()
    furnaces.get(POS).slots = [(B.IRON_ORE, 3, 0), EMPTY, EMPTY]
    sim.set_block(*POS, B.AIR)
    run(sim, 1)
    assert POS not in furnaces.states


def test_remove_gives_contents():
    world, sim, furnaces = bench()
    furnaces.get(POS).slots = [(B.IRON_ORE, 3, 0), EMPTY, (I.IRON_INGOT, 2, 0)]
    assert furnaces.remove(POS) == [(B.IRON_ORE, 3, 0), (I.IRON_INGOT, 2, 0)]
    assert POS not in furnaces.states and furnaces.remove(POS) == []
