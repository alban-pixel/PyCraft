"""Small circuits built block by block, run tick by tick."""
import redstone
from blocks import (AIR, EAST, LEVER, NORTH, REDSTONE_BLOCK, REDSTONE_LAMP, REDSTONE_LAMP_OFF, REDSTONE_TORCH,
                    REDSTONE_WIRE, REPEATER, SOUTH, STONE, STONE_BUTTON, STONE_PRESSURE_PLATE, UP, WEST)
from sim import MAX_UPDATES, Simulation
from world import World

Y = 3000


class Bench:
    def __init__(self):
        self.world = World(11)
        self.sim = Simulation(self.world, lambda *a: None)
        redstone.install(self.sim)
        for x in range(-4, 24):
            for z in range(-4, 6):
                self.world.set(x, Y - 1, z, STONE)  # a floor

    def put(self, x, z, block, state=0, y=0):
        self.sim.set_block(x, Y + y, z, block, state)

    def get(self, x, z, y=0):
        return self.world.get(x, Y + y, z)

    def state(self, x, z, y=0):
        return self.world.get_state(x, Y + y, z)

    def run(self, ticks=10):
        return [self.sim.tick() for _ in range(ticks)]


def test_lever_powers_lamp_next_to_it():
    b = Bench()
    b.put(0, 0, REDSTONE_LAMP_OFF)
    b.put(1, 0, LEVER, UP)
    b.run()
    assert b.get(0, 0) == REDSTONE_LAMP_OFF
    redstone.toggle_lever(b.sim, 1, Y, 0)
    b.run()
    assert b.get(0, 0) == REDSTONE_LAMP
    redstone.toggle_lever(b.sim, 1, Y, 0)
    b.run(1)
    assert b.get(0, 0) == REDSTONE_LAMP  # a lamp goes out 2 ticks later
    b.run()
    assert b.get(0, 0) == REDSTONE_LAMP_OFF


def wire_line(b, length, lamp_at_end=True):
    b.put(0, 0, LEVER, UP | 8)
    for x in range(1, length + 1):
        b.put(x, 0, REDSTONE_WIRE)
    if lamp_at_end:
        b.put(length + 1, 0, REDSTONE_LAMP_OFF)
    b.run(20)


def test_wire_line_decays_and_lights_lamp_at_15_blocks():
    b = Bench()
    wire_line(b, 15)
    assert [b.state(x, 0) & 15 for x in range(1, 16)] == list(range(15, 0, -1))
    assert b.get(16, 0) == REDSTONE_LAMP


def test_wire_too_long_no_lamp():
    b = Bench()
    wire_line(b, 16)
    assert b.state(16, 0) & 15 == 0
    assert b.get(17, 0) == REDSTONE_LAMP_OFF


def test_wire_goes_dark_when_lever_off():
    b = Bench()
    wire_line(b, 5)
    redstone.toggle_lever(b.sim, 0, Y, 0)
    b.run(20)
    assert all(b.state(x, 0) & 15 == 0 for x in range(1, 6))
    assert b.get(6, 0) == REDSTONE_LAMP_OFF


def test_torch_inverter():
    b = Bench()
    b.put(0, 0, STONE)
    b.put(1, 0, REDSTONE_TORCH, EAST)  # on the east side of the stone
    b.put(2, 0, REDSTONE_LAMP_OFF)
    b.put(-1, 0, LEVER, WEST)  # on the west side of the stone
    b.run(10)
    assert b.get(2, 0) == REDSTONE_LAMP  # the torch is lit
    redstone.toggle_lever(b.sim, -1, Y, 0)
    b.run(10)
    assert b.state(1, 0) & 8  # the torch went out
    assert b.get(2, 0) == REDSTONE_LAMP_OFF


def test_torch_clock_is_bounded():
    b = Bench()
    # A torch on the stone's east side; its dust runs round to a repeater that powers the stone
    b.put(0, 0, STONE)
    b.put(1, 0, REDSTONE_TORCH, EAST)
    b.put(1, 1, REDSTONE_WIRE)
    b.put(1, 2, REDSTONE_WIRE)
    b.put(0, 2, REDSTONE_WIRE)
    b.put(0, 1, REPEATER, NORTH)
    states = []
    for _ in range(200):
        assert b.sim.tick() <= MAX_UPDATES
        states.append(b.state(1, 0) & 8)
    toggles = sum(1 for a, c in zip(states, states[1:]) if a != c)
    assert toggles >= 4  # it did run as a clock...
    assert toggles < 60  # ...and burnt out instead of flickering forever


def test_repeater_delay():
    b = Bench()
    b.put(0, 0, LEVER, UP)
    b.put(1, 0, REPEATER, EAST | (2 << 3))  # 3 notches: 6 ticks
    b.put(2, 0, REDSTONE_LAMP_OFF)
    b.run(5)
    redstone.toggle_lever(b.sim, 0, Y, 0)
    ticks = 0
    while b.get(2, 0) != REDSTONE_LAMP and ticks < 30:
        b.run(1)
        ticks += 1
    assert 5 <= ticks <= 8


def test_repeater_only_one_way():
    b = Bench()
    b.put(2, 0, LEVER, UP | 8)
    b.put(1, 0, REPEATER, EAST)  # points away from the lever's side? no: from x=1 toward x=2
    b.put(0, 0, REDSTONE_LAMP_OFF)
    b.run(20)
    assert b.get(0, 0) == REDSTONE_LAMP_OFF  # the lever is at its output, not its input


def test_button_releases_after_20_ticks():
    b = Bench()
    b.put(0, 0, STONE_BUTTON, UP)
    b.put(1, 0, REDSTONE_LAMP_OFF)
    redstone.press_button(b.sim, 0, Y, 0)
    b.run(3)
    assert b.get(1, 0) == REDSTONE_LAMP
    b.run(25)
    assert not b.state(0, 0) & 8 and b.get(1, 0) == REDSTONE_LAMP_OFF


def test_pressure_plate():
    b = Bench()
    b.put(0, 0, STONE_PRESSURE_PLATE)
    b.put(1, 0, REDSTONE_LAMP_OFF)
    b.sim.occupied = {(0, Y, 0)}
    b.run(3)
    assert b.get(1, 0) == REDSTONE_LAMP
    b.sim.occupied = set()
    b.run(30)
    assert b.get(1, 0) == REDSTONE_LAMP_OFF


def test_lever_breaks_without_support():
    b = Bench()
    b.put(0, 0, STONE)
    b.put(1, 0, LEVER, EAST)
    b.put(0, 0, AIR)
    b.run(2)
    assert b.get(1, 0) == AIR


def test_wire_breaks_without_floor():
    b = Bench()
    b.put(0, 0, REDSTONE_WIRE)
    b.sim.set_block(0, Y - 1, 0, AIR)
    b.run(2)
    assert b.get(0, 0) == AIR


def test_redstone_block_powers_lamp():
    b = Bench()
    b.put(1, 0, REDSTONE_LAMP_OFF)
    b.put(0, 0, REDSTONE_BLOCK)
    b.run(3)
    assert b.get(1, 0) == REDSTONE_LAMP


def test_lever_powers_through_block():
    b = Bench()
    b.put(0, 0, STONE)
    b.put(0, 1, LEVER, SOUTH | 8)  # on the stone's south side, on
    b.put(0, -1, REDSTONE_LAMP_OFF)  # on the stone's north side
    b.run(5)
    assert b.get(0, -1) == REDSTONE_LAMP
