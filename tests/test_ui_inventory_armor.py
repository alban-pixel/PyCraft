"""Tests for full 41-slot inventory, armor defense rating, and UI slot interaction."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from main import App
import blocks


def test_player_41_slots_and_armor_points(headless_app):
    app = headless_app
    p = app.player

    # 4 armor slots + 1 offhand slot
    assert len(p.armor_slots) == 4
    assert len(p.offhand_slot) == 2
    assert p.armor_points == 0

    # Equip helmet and chestplate (e.g. standard items)
    p.armor_slots[0] = [blocks.ITEM_IRON_PICKAXE, 1]  # Helmet slot +2
    p.armor_slots[1] = [blocks.ITEM_IRON_SWORD, 1]    # Chestplate slot +6
    assert p.armor_points == 8

    # Equip full set
    p.armor_slots[2] = [blocks.STONE, 1]              # Leggings +5
    p.armor_slots[3] = [blocks.DIRT, 1]               # Boots +2
    assert p.armor_points == 15


def test_craft_layout_41_slots_slots_under_mouse(headless_app):
    app = headless_app
    app.craft_size = 2
    lay = app.craft_layout()

    # Armor coordinates are present in 2x2 player inventory layout
    assert "arm_x0" in lay
    assert "off_x0" in lay

    # Test slot under mouse for armor slot 0
    arm_x0, arm_y0 = lay["arm_x0"], lay["arm_y0"]
    slot_s = lay["slot_s"]
    found = app.get_slot_under_mouse(arm_x0 + 2, arm_y0 + 2)
    assert found is not None
    assert found[0] == "armor"
    assert found[1] == 0

    # Test slot under mouse for off-hand
    off_x0, off_y0 = lay["off_x0"], lay["off_y0"]
    found_off = app.get_slot_under_mouse(off_x0 + 2, off_y0 + 2)
    assert found_off is not None
    assert found_off[0] == "offhand"
    assert found_off[1] == 0


def test_armor_slot_click_and_equip(headless_app):
    app = headless_app
    app.craft_size = 2
    app.player.armor_slots = [[0, 0] for _ in range(4)]

    # Put an item on cursor
    app.cursor_item = [blocks.ITEM_DIAMOND_SWORD, 1]

    # Click armor slot 0 (helmet)
    app.handle_slot_click("armor", 0, is_right_click=False, is_shift_click=False)

    # Item moved to armor slot
    assert app.player.armor_slots[0] == [blocks.ITEM_DIAMOND_SWORD, 1]
    assert app.cursor_item == [0, 0]
    assert app.player.armor_points == 2
