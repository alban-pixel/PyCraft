from pycraft import redstone
from pycraft.blocks import (AIR, BEDROCK, DIRT, EAST, LEVER, OBSIDIAN, PISTON, PISTON_HEAD, POPPY, STICKY_PISTON, STONE, TNT,
                            UP, WEST)
from tests.test_redstone import Bench, Y


def piston_bench(block=PISTON, behind=None):
    """A piston at x=0 facing east, a lever behind it (west) at x=-1, things in front from x=1."""
    b = Bench()
    b.put(0, 0, block, EAST)
    b.put(-1, 0, LEVER, UP)
    for x, blk in enumerate(behind or [], start=1):
        b.put(x, 0, blk)
    b.run(3)
    return b


def flip(b):
    redstone.toggle_lever(b.sim, -1, Y, 0)
    b.run(5)


def test_piston_extends_with_head():
    b = piston_bench()
    flip(b)
    assert b.state(0, 0) & 8 and b.get(1, 0) == PISTON_HEAD
    assert b.state(1, 0) & 7 == EAST


def test_piston_pushes_12():
    b = piston_bench(behind=[DIRT] * 12)
    flip(b)
    assert b.get(1, 0) == PISTON_HEAD
    assert [b.get(x, 0) for x in range(2, 14)] == [DIRT] * 12


def test_piston_blocked_at_13():
    b = piston_bench(behind=[DIRT] * 13)
    flip(b)
    assert not b.state(0, 0) & 8
    assert [b.get(x, 0) for x in range(1, 14)] == [DIRT] * 13


def test_piston_blocked_by_bedrock():
    for wall in (BEDROCK, OBSIDIAN):
        b = piston_bench(behind=[DIRT, wall])
        flip(b)
        assert not b.state(0, 0) & 8 and b.get(1, 0) == DIRT


def test_piston_breaks_plant_in_the_way():
    b = piston_bench(behind=[DIRT, POPPY])
    flip(b)
    assert b.get(1, 0) == PISTON_HEAD and b.get(2, 0) == DIRT and b.get(3, 0) == AIR


def test_head_removed_on_retract():
    b = piston_bench(behind=[DIRT])
    flip(b)
    flip(b)
    assert not b.state(0, 0) & 8 and b.get(1, 0) == AIR and b.get(2, 0) == DIRT


def test_sticky_pulls_back():
    b = piston_bench(STICKY_PISTON, behind=[DIRT])
    flip(b)
    assert b.get(2, 0) == DIRT and b.state(1, 0) & 8  # a sticky head
    flip(b)
    assert b.get(1, 0) == DIRT and b.get(2, 0) == AIR


def test_broken_base_takes_its_head():
    b = piston_bench()
    flip(b)
    b.sim.set_block(0, Y, 0, AIR)
    b.run(3)
    assert b.get(1, 0) == AIR


def test_not_powered_from_its_front():
    b = Bench()
    b.put(0, 0, PISTON, WEST)  # facing the lever
    b.put(-1, 0, LEVER, UP | 8)
    b.run(5)
    assert not b.state(0, 0) & 8


def test_tnt_explodes_after_80_ticks():
    b = Bench()
    b.put(0, 0, TNT)
    b.put(3, 0, STONE)
    b.put(-1, 0, LEVER, UP | 8)
    b.run(79)
    assert b.get(0, 0) == TNT
    b.run(3)
    assert b.get(0, 0) == AIR and b.get(3, 0) == AIR


def test_tnt_spares_bedrock_and_chains():
    b = Bench()
    b.put(0, 0, TNT)
    b.put(2, 0, BEDROCK)
    b.put(0, 3, TNT)  # within reach: lit by the blast
    b.put(0, 7, TNT)  # 7 from the first, 4 from the second: lit by the second
    b.put(-1, 0, LEVER, UP | 8)
    b.run(85)
    assert b.get(2, 0) == BEDROCK and b.get(0, 3) == TNT
    b.run(40)
    assert b.get(0, 3) == AIR
    b.run(40)
    assert b.get(0, 7) == AIR
