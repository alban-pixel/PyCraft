import random

import numpy as np

from pycraft import blocks as B
from pycraft import items as I
from pycraft.inventory import EMPTY, Inventory
from pycraft.survival import CREATIVE, SURVIVAL, convert_old_save, harvest, parse_gamemode


def test_old_save_becomes_creative():
    data = {"hotbar": np.array([B.STONE, B.DIRT, 0, B.GLASS, B.LOG, B.PLANKS, B.SAND, B.TNT, B.LEVER])}
    mode, inv = convert_old_save(data)
    assert mode == CREATIVE
    assert inv.slots[0] == (B.STONE, 1, 0) and inv.slots[1] == (B.DIRT, 1, 0) and inv.slots[2] == EMPTY
    assert inv.slots[8] == (B.LEVER, 1, 0) and inv.slots[9:] == [EMPTY] * 27


def test_new_save_reads_back():
    inv = Inventory()
    inv.slots[3] = (I.STONE_PICKAXE, 1, 12)
    inv.slots[20] = (B.COBBLESTONE, 40, 0)
    mode, back = convert_old_save({"mode": np.int64(SURVIVAL), "inventory": inv.to_array()})
    assert mode == SURVIVAL and back.slots == inv.slots


def test_parse_gamemode():
    for text in ("survival", "s", "0", " Survival "):
        assert parse_gamemode(text) == SURVIVAL
    for text in ("creative", "c", "1", "CREATIVE"):
        assert parse_gamemode(text) == CREATIVE
    for text in ("", "spectator", "2", "creatif"):
        assert parse_gamemode(text) is None


def test_harvest_puts_drops_in_inventory():
    inv = Inventory()
    inv.slots[0] = (I.WOODEN_PICKAXE, 1, 0)
    lost, broke = harvest(inv, 0, B.STONE, random.Random(1))
    assert (lost, broke) == (0, None)
    assert inv.slots[1] == (B.COBBLESTONE, 1, 0) and inv.slots[0] == (I.WOODEN_PICKAXE, 1, 1)


def test_harvest_by_hand_gets_nothing_from_stone():
    inv = Inventory()
    assert harvest(inv, 0, B.STONE, random.Random(1)) == (0, None)
    assert inv.slots == [EMPTY] * 36


def test_harvest_full_inventory_loses_the_drop():
    inv = Inventory()
    inv.slots = [(B.DIRT, 64, 0)] * 36
    lost, _ = harvest(inv, 0, B.LOG, random.Random(1))
    assert lost == 1


def test_harvest_tool_breaks():
    inv = Inventory()
    inv.slots[4] = (I.GOLDEN_PICKAXE, 1, 31)
    lost, broke = harvest(inv, 4, B.STONE, random.Random(1))
    assert broke == "Golden pickaxe" and inv.slots[4] == EMPTY
    assert inv.slots[0] == (B.COBBLESTONE, 1, 0)  # the last blow still harvests


def test_harvest_instant_block_keeps_tool():
    inv = Inventory()
    inv.slots[0] = (I.IRON_AXE, 1, 0)
    harvest(inv, 0, B.POPPY, random.Random(1))
    assert inv.slots[0] == (I.IRON_AXE, 1, 0)


def test_harvest_furnace_gives_contents():
    inv = Inventory()
    inv.slots[0] = (I.STONE_PICKAXE, 1, 0)
    contents = [(B.IRON_ORE, 3, 0), (I.IRON_INGOT, 2, 0)]
    harvest(inv, 0, B.FURNACE_ON_WEST, random.Random(1), contents)
    assert sorted(s for s in inv.slots[1:] if s != EMPTY) == sorted([(B.FURNACE, 1, 0), *contents])
