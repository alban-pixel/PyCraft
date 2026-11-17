import numpy as np

import blocks as B
import items as I
from inventory import (EMPTY, Inventory, click, craft_all, give_back, grid_items, shift_click, take_result)


def test_add_fills_hotbar_first_and_merges():
    inv = Inventory()
    assert inv.add(B.DIRT, 70) == 0
    assert inv.add(B.DIRT, 10) == 0
    assert inv.slots[0] == (B.DIRT, 64, 0) and inv.slots[1] == (B.DIRT, 16, 0)


def test_add_tops_up_main_before_empty_hotbar():
    inv = Inventory()
    inv.slots[9] = (B.STONE, 10, 0)
    inv.add(B.STONE, 5)
    assert inv.slots[9] == (B.STONE, 15, 0) and inv.slots[0] == EMPTY


def test_add_full_returns_leftover():
    inv = Inventory()
    for i in range(36):
        inv.slots[i] = (B.STONE, 64, 0)
    assert inv.add(B.STONE, 5) == 5


def test_tools_dont_stack():
    inv = Inventory()
    inv.add(I.WOODEN_PICKAXE, 1)
    inv.add(I.WOODEN_PICKAXE, 1)
    assert inv.slots[0] == (I.WOODEN_PICKAXE, 1, 0) and inv.slots[1] == (I.WOODEN_PICKAXE, 1, 0)


def test_left_click_pick_up_and_put_down():
    slots = [(B.DIRT, 10, 0), EMPTY]
    slots, cursor = click(slots, EMPTY, 0, "left")
    assert slots[0] == EMPTY and cursor == (B.DIRT, 10, 0)
    slots, cursor = click(slots, cursor, 1, "left")
    assert slots[1] == (B.DIRT, 10, 0) and cursor == EMPTY


def test_left_click_merge():
    slots, cursor = click([(B.DIRT, 40, 0)], (B.DIRT, 40, 0), 0, "left")
    assert slots[0] == (B.DIRT, 64, 0) and cursor == (B.DIRT, 16, 0)


def test_left_click_swap():
    slots, cursor = click([(B.DIRT, 3, 0)], (B.STONE, 5, 0), 0, "left")
    assert slots[0] == (B.STONE, 5, 0) and cursor == (B.DIRT, 3, 0)


def test_right_click_takes_half_and_puts_one():
    slots, cursor = click([(B.DIRT, 7, 0)], EMPTY, 0, "right")
    assert cursor == (B.DIRT, 4, 0) and slots[0] == (B.DIRT, 3, 0)
    slots, cursor = click([EMPTY], (B.DIRT, 5, 0), 0, "right")
    assert slots[0] == (B.DIRT, 1, 0) and cursor == (B.DIRT, 4, 0)
    slots, cursor = click([(B.STONE, 1, 0)], (B.DIRT, 5, 0), 0, "right")  # another item: nothing
    assert slots[0] == (B.STONE, 1, 0) and cursor == (B.DIRT, 5, 0)


def test_click_does_not_change_its_input():
    slots = [(B.DIRT, 7, 0)]
    click(slots, EMPTY, 0, "left")
    assert slots == [(B.DIRT, 7, 0)]


def test_shift_click_hotbar_to_main():
    inv = Inventory()
    inv.slots[0] = (B.DIRT, 20, 0)
    inv.slots[9] = (B.DIRT, 60, 0)
    slots = shift_click(inv.slots, 0, list(range(9, 36)))
    assert slots[9] == (B.DIRT, 64, 0) and slots[10] == (B.DIRT, 16, 0) and slots[0] == EMPTY


def test_shift_click_keeps_what_doesnt_fit():
    slots = [(B.DIRT, 20, 0), (B.STONE, 64, 0)]
    slots = shift_click(slots, 0, [1])
    assert slots[0] == (B.DIRT, 20, 0)


def test_damage_tool_breaks():
    inv = Inventory()
    inv.slots[2] = (I.WOODEN_PICKAXE, 1, 57)
    assert not inv.damage_tool(2)
    assert inv.slots[2] == (I.WOODEN_PICKAXE, 1, 58)
    assert inv.damage_tool(2)
    assert inv.slots[2] == EMPTY


def test_remove_from():
    inv = Inventory()
    inv.slots[0] = (B.DIRT, 2, 0)
    inv.remove_from(0, 1)
    assert inv.slots[0] == (B.DIRT, 1, 0)
    inv.remove_from(0, 1)
    assert inv.slots[0] == EMPTY


def test_grid_items():
    slots = [EMPTY] * 3 + [(B.LOG, 1, 0), EMPTY, EMPTY, EMPTY]
    assert grid_items(slots, 2, 2) == [[0, B.LOG], [0, 0]]


def test_take_result_and_craft_all():
    grid = [(B.LOG, 1, 0), EMPTY, EMPTY, EMPTY]
    grid, cursor, crafted = take_result(grid, 2, EMPTY)
    assert crafted and cursor == (B.PLANKS, 4, 0) and grid == [EMPTY] * 4
    grid = [(B.LOG, 3, 0), EMPTY, EMPTY, EMPTY]
    inv = Inventory()
    grid = craft_all(grid, 2, inv)
    assert grid == [EMPTY] * 4 and inv.slots[0] == (B.PLANKS, 12, 0)


def test_take_result_needs_room_in_cursor():
    grid = [(B.LOG, 1, 0), EMPTY, EMPTY, EMPTY]
    grid2, cursor, crafted = take_result(grid, 2, (B.PLANKS, 62, 0))  # 4 more wouldn't fit
    assert not crafted and cursor == (B.PLANKS, 62, 0) and grid2 == grid
    grid2, cursor, crafted = take_result(grid, 2, (B.DIRT, 1, 0))  # another item
    assert not crafted
    grid2, cursor, crafted = take_result(grid, 2, (B.PLANKS, 60, 0))
    assert crafted and cursor == (B.PLANKS, 64, 0)


def test_take_result_nothing_to_craft():
    grid, cursor, crafted = take_result([EMPTY] * 4, 2, EMPTY)
    assert not crafted and cursor == EMPTY


def test_give_back_counts_lost():
    inv = Inventory()
    for i in range(35):
        inv.slots[i] = (B.STONE, 64, 0)
    lost = give_back(inv, [(B.DIRT, 10, 0), EMPTY, (B.STONE, 3, 0)])
    assert lost == 3 and inv.slots[35] == (B.DIRT, 10, 0)


def test_array_roundtrip():
    inv = Inventory()
    inv.slots[4] = (I.IRON_PICKAXE, 1, 17)
    inv.slots[30] = (B.DIRT, 33, 0)
    arr = inv.to_array()
    assert arr.shape == (36, 3) and arr.dtype == np.int32
    assert Inventory.from_array(arr).slots == inv.slots
