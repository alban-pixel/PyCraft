import math
import random

import pytest

from pycraft import blocks as B
from pycraft.blocks import PLACEABLE, BLOCK_NAMES
from pycraft import items as I


def test_numbering():
    assert I.STICK == 256
    assert I.FIRST_ITEM == 256
    assert I.ITEM_NAMES[I.WOODEN_PICKAXE] == "Wooden pickaxe"
    assert I.max_stack(I.STONE_PICKAXE) == 1
    assert I.max_stack(I.COAL) == 64
    assert I.BRICK == I.CLAY_BALL + 1
    assert I.WOODEN_PICKAXE == I.BRICK + 1
    assert I.NUM_ITEMS == len(I.ITEM_NAMES) == 13 + 15
    assert I.name(B.STONE) == "Stone" and I.is_block(B.STONE) and not I.is_block(I.STICK)


def test_break_times():
    assert I.break_seconds(B.STONE, 0) == pytest.approx(7.5)
    assert I.break_seconds(B.STONE, I.WOODEN_PICKAXE) == pytest.approx(1.125)
    assert I.break_seconds(B.DIRT, 0) == pytest.approx(0.75)
    assert I.break_seconds(B.DIRT, I.STONE_SHOVEL) == pytest.approx(0.1875)
    assert I.TOOLS[I.STONE_SHOVEL].speed == 4
    assert I.break_seconds(B.TALL_GRASS, 0) == 0
    assert I.break_seconds(B.BEDROCK, I.DIAMOND_PICKAXE) == math.inf


def test_harvest_levels():
    assert I.needed_level(B.IRON_ORE) == 1
    assert not I.can_harvest(B.IRON_ORE, I.WOODEN_PICKAXE)
    assert I.can_harvest(B.IRON_ORE, I.STONE_PICKAXE)
    assert I.needed_level(B.DIAMOND_ORE) == 2
    assert I.needed_level(B.OBSIDIAN) == 3
    assert not I.can_harvest(B.IRON_ORE, I.GOLDEN_PICKAXE)
    assert I.can_harvest(B.DIRT, 0)
    assert I.needed_level(B.DIRT) is None
    assert I.best_tool(B.DIRT) == "shovel" and I.best_tool(B.LOG) == "axe"


def test_drops():
    r = random.Random(1)
    assert I.drops(B.STONE, I.WOODEN_PICKAXE, r) == [(B.COBBLESTONE, 1)]
    assert I.drops(B.STONE, 0, r) == []
    assert I.drops(B.GRASS, 0, r) == [(B.DIRT, 1)]
    assert I.drops(B.COAL_ORE, I.WOODEN_PICKAXE, r) == [(I.COAL, 1)]
    for seed in range(50):
        (item, n), = I.drops(B.LAPIS_ORE, I.STONE_PICKAXE, random.Random(seed))
        assert item == I.LAPIS and 4 <= n <= 8
    assert I.drops(B.GLASS, 0, r) == []
    assert I.drops(B.FURNACE_WEST, I.WOODEN_PICKAXE, r) == [(B.FURNACE, 1)]
    assert I.drops(B.FURNACE_ON_NORTH, I.WOODEN_PICKAXE, r) == [(B.FURNACE, 1)]
    assert I.drops(B.REDSTONE_LAMP, 0, r) == [(B.REDSTONE_LAMP_OFF, 1)]
    flint = sum(I.drops(B.GRAVEL, 0, r)[0][0] == I.FLINT for _ in range(2000))
    assert 100 <= flint <= 300


def test_furnace_lit_blocks():
    assert B.LIT_FURNACE[B.FURNACE_SOUTH] == B.FURNACE_ON_SOUTH
    assert B.UNLIT_FURNACE[B.FURNACE_ON] == B.FURNACE
    assert B.FURNACE_ON not in PLACEABLE
    assert BLOCK_NAMES[B.FURNACE_ON_NORTH] == "Furnace"
    assert B.FURNACE_ON_NORTH in B.TURNED
    assert I.base_item(B.FURNACE_ON_WEST) == B.FURNACE


def test_hardness_groups_do_not_overlap():
    seen = {}
    for value, group in I._HARDNESS_GROUPS:
        for b in group:
            assert b not in seen, f"{B.BLOCK_NAMES[b]} is in the groups {seen[b]} and {value}"
            seen[b] = value
    assert all(I.hardness(b) == v for b, v in seen.items())


def test_ungrouped_block_has_default_hardness():
    grouped = {b for _, group in I._HARDNESS_GROUPS for b in group}
    # every real block is in a group today, so test the default with an id no group holds
    assert B.NUM_BLOCKS not in grouped
    assert I.hardness(B.NUM_BLOCKS) == 0.5


def test_name_of_empty_slot():
    assert I.name(0) == ""
