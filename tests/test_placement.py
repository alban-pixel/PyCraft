from pycraft.blocks import (AIR, DOWN, EAST, GLASS, LEVER, NORTH, PISTON, REDSTONE_TORCH, REDSTONE_WIRE, REPEATER, SOUTH,
                            STONE, STONE_BUTTON, UP, WEST)
from pycraft.play import placement
from pycraft.screens.inventory import block_category
from pycraft.world import World

Y = 3000


def world_with_stone():
    w = World(8)
    w.set(0, Y, 0, STONE)
    return w


def test_lever_on_wall_faces_out():
    w = world_with_stone()
    # Aiming at the stone's east side: the lever goes in the cell east of it, facing east
    block, state = placement(LEVER, (0, Y, 0), (1, Y, 0), (-1, 0, 0), w)
    assert block == LEVER and state & 7 == EAST


def test_lever_on_floor_turns_with_the_look():
    w = world_with_stone()
    _, along_z = placement(LEVER, (0, Y, 0), (0, Y + 1, 0), (0.1, -0.5, 0.9), w)
    _, along_x = placement(LEVER, (0, Y, 0), (0, Y + 1, 0), (0.9, -0.5, 0.1), w)
    assert along_z & 7 == UP and not along_z & 16 and along_x & 16


def test_button_needs_a_full_block():
    w = World(8)
    w.set(0, Y, 0, GLASS)
    assert placement(STONE_BUTTON, (0, Y, 0), (1, Y, 0), (-1, 0, 0), w) is None


def test_torch_not_on_ceiling():
    w = world_with_stone()
    assert placement(REDSTONE_TORCH, (0, Y, 0), (0, Y - 1, 0), (0, 1, 0), w) is None
    assert placement(REDSTONE_TORCH, (0, Y, 0), (0, Y + 1, 0), (0, -1, 0), w) == (REDSTONE_TORCH, UP)


def test_wire_needs_floor():
    w = world_with_stone()
    assert placement(REDSTONE_WIRE, (0, Y, 0), (0, Y + 1, 0), (0, -1, 0), w) == (REDSTONE_WIRE, 0)
    assert placement(REDSTONE_WIRE, (0, Y, 0), (1, Y, 0), (-1, 0, 0), w) is None  # on a wall: nothing under it


def test_repeater_faces_look():
    w = world_with_stone()
    block, state = placement(REPEATER, (0, Y, 0), (0, Y + 1, 0), (0.2, -0.6, -0.8), w)
    assert block == REPEATER and state & 7 == NORTH


def test_piston_faces_player():
    w = world_with_stone()
    _, s1 = placement(PISTON, (0, Y, 0), (1, Y, 0), (-0.9, -0.1, 0.2), w)
    assert s1 & 7 == EAST  # the player looks west: the piston's face looks back at them
    _, s2 = placement(PISTON, (0, Y, 0), (0, Y + 1, 0), (0.1, -0.95, 0.1), w)
    assert s2 & 7 == UP
    _, s3 = placement(PISTON, (0, Y, 0), (0, Y + 1, 0), (0.1, 0.2, 0.95), w)
    assert s3 & 7 == NORTH


def test_plain_block():
    w = world_with_stone()
    assert placement(STONE, (0, Y, 0), (0, Y + 1, 0), (0, -1, 0), w) == (STONE, 0)


def test_redstone_tab():
    assert block_category(LEVER) == "Redstone" and block_category(PISTON) == "Redstone"
    _ = (AIR, DOWN, SOUTH, WEST)
