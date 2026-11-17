"""Findings of the final review of the redstone branch."""
from pycraft import redstone
from pycraft.blocks import AIR, DIRT, EAST, LEVER, PISTON, REDSTONE_LAMP, REDSTONE_LAMP_OFF, REDSTONE_WIRE, STONE, UP
from pycraft.app import right_click
from pycraft.render import affected_sections
from tests.test_redstone import Bench, Y


def test_one_remesh_per_section():
    # 16 dust in one section, changed in the same frame: one section to remesh (plus none around)
    changes = [(x, 600, 5) for x in range(1, 15)]
    assert affected_sections(changes) == {(0, 600 >> 4, 0)}
    # On a border: the neighbor section too
    assert affected_sections([(0, 600, 5)]) == {(0, 37, 0), (-1, 37, 0)}


def test_dust_carpet_solved_once_per_tick(monkeypatch):
    b = Bench()
    b.put(-1, 0, LEVER, UP)
    for x in range(0, 20):
        for z in range(-3, 4):
            b.put(x, z, REDSTONE_WIRE)
    b.run(5)
    calls = [0]
    real = redstone.wire_neighbors

    def counted(world, pos):
        calls[0] += 1
        return real(world, pos)
    monkeypatch.setattr(redstone, "wire_neighbors", counted)
    redstone.toggle_lever(b.sim, -1, Y, 0)
    b.run(3)
    assert b.state(0, 0) & 15 == 15
    # A solve of the 140 dust looks at each a few times; solving it once per dust would be
    # thousands of looks
    assert calls[0] < 2500, calls[0]


def test_crushed_dust_unpowers_lamp():
    b = Bench()
    b.put(0, 0, LEVER, UP | 8)
    b.put(1, 0, REDSTONE_WIRE)
    b.put(2, 0, REDSTONE_WIRE)
    b.put(3, 0, STONE)
    b.put(4, 0, REDSTONE_LAMP_OFF)
    b.put(2, 1, PISTON, 5)  # north-facing piston south of the second dust
    b.put(2, 2, LEVER, UP)
    b.run(10)
    assert b.get(4, 0) == REDSTONE_LAMP
    redstone.toggle_lever(b.sim, 2, Y, 2)  # the piston's head crushes the second dust
    b.run(10)
    assert b.get(2, 0) != REDSTONE_WIRE
    assert b.get(4, 0) == REDSTONE_LAMP_OFF


def test_holding_right_click_on_a_lever_never_places():
    assert right_click(LEVER, first_press=True) == "act"
    assert right_click(LEVER, first_press=False) is None
    assert right_click(STONE, first_press=False) == "place"
    _ = (AIR, DIRT, EAST)
