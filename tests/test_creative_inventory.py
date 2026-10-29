"""Tests for Creative Mode Inventory Catalog, Item Spawning, Tabs, and Trash Slot."""
import pyxel
import pytest
from blocks import (
    BLOCK_NAMES, CREATIVE_CATALOG, ITEM_NAMES, NON_STACKABLE,
    GRASS, DIRT, STONE, BEDROCK, ITEM_DIAMOND_SWORD, ITEM_DIAMOND_PICKAXE,
    ITEM_COOKED_PORK, ITEM_STICK,
)


def test_creative_catalog_completeness():
    """Verify CREATIVE_CATALOG includes all placeable blocks and items."""
    # 23 blocks (IDs 1..23) + 11 items (IDs 100..110) = 34 total items
    assert len(CREATIVE_CATALOG) == 34

    # Every item in catalog must have a valid name in BLOCK_NAMES or ITEM_NAMES
    for item_id in CREATIVE_CATALOG:
        if item_id < len(BLOCK_NAMES):
            assert BLOCK_NAMES[item_id] != "Air"
        else:
            assert item_id in ITEM_NAMES

    # Non-stackables set must contain swords and pickaxes
    assert ITEM_DIAMOND_SWORD in NON_STACKABLE
    assert ITEM_DIAMOND_PICKAXE in NON_STACKABLE
    assert GRASS not in NON_STACKABLE
    assert ITEM_STICK not in NON_STACKABLE


def test_creative_inventory_layout_and_tabs(headless_app):
    """Verify craft_layout returns catalog layout in Creative mode and tabs."""
    app = headless_app
    app.player.mode = "creative"
    app.craft_size = 2
    app.creative_tab = "catalog"

    lay = app.craft_layout()
    assert lay["type"] == "creative_catalog"
    assert lay["cat_rows"] == 5
    assert lay["cat_cols"] == 9
    assert "trash_x" in lay
    assert "trash_y" in lay
    assert "tab_cat" in lay
    assert "tab_surv" in lay

    # When tab switched to survival, returns standard 2x2 layout with tabs
    app.creative_tab = "survival"
    lay_surv = app.craft_layout()
    assert lay_surv.get("type") != "creative_catalog"
    assert "arm_x0" in lay_surv
    assert "tab_cat" in lay_surv
    assert "tab_surv" in lay_surv

    # In survival mode, no creative tabs are included
    app.player.mode = "survival"
    lay_survival_mode = app.craft_layout()
    assert "tab_cat" not in lay_survival_mode
    assert "tab_surv" not in lay_survival_mode


def test_slot_under_mouse_creative(headless_app):
    """Verify mouse hit-testing for tabs, trash, catalog slots, and hotbar in creative layout."""
    app = headless_app
    app.player.mode = "creative"
    app.craft_size = 2
    app.creative_tab = "catalog"
    lay = app.craft_layout()

    # 1. Tabs
    tx, ty, tw, th = lay["tab_cat"]
    found = app.get_slot_under_mouse(tx + 2, ty + 2)
    assert found is not None and found[0] == "tab" and found[1] == "catalog"

    tx, ty, tw, th = lay["tab_surv"]
    found = app.get_slot_under_mouse(tx + 2, ty + 2)
    assert found is not None and found[0] == "tab" and found[1] == "survival"

    # 2. Trash slot
    tx, ty, tw, th = lay["trash_x"], lay["trash_y"], lay["trash_w"], lay["trash_h"]
    found = app.get_slot_under_mouse(tx + 2, ty + 2)
    assert found is not None and found[0] == "trash"

    # 3. Catalog slots (row 0, col 0)
    cat_x, cat_y = lay["cat_x0"], lay["cat_y0"]
    found = app.get_slot_under_mouse(cat_x + 2, cat_y + 2)
    assert found is not None and found[0] == "creative_catalog" and found[1] == 0

    # 4. Hotbar slot 0
    hx, hy = lay["hx0"], lay["hy0"]
    found = app.get_slot_under_mouse(hx + 2, hy + 2)
    assert found is not None and found[0] == "hotbar" and found[1] == 0


def test_creative_catalog_item_spawning(headless_app):
    """Left-click spawns a full stack (64 for blocks, 1 for tools), right-click spawns 1."""
    app = headless_app
    app.player.mode = "creative"
    app.craft_size = 2
    app.creative_tab = "catalog"
    app.cursor_item = [0, 0]

    # GRASS is index 0 in CREATIVE_CATALOG (stackable block)
    app.handle_slot_click("creative_catalog", 0, is_right_click=False, is_shift_click=False)
    assert app.cursor_item == [GRASS, 64]

    # ITEM_DIAMOND_SWORD index in catalog
    sword_idx = CREATIVE_CATALOG.index(ITEM_DIAMOND_SWORD)
    app.cursor_item = [0, 0]
    app.handle_slot_click("creative_catalog", sword_idx, is_right_click=False, is_shift_click=False)
    assert app.cursor_item == [ITEM_DIAMOND_SWORD, 1]

    # Right click spawns 1 single item
    app.cursor_item = [0, 0]
    app.handle_slot_click("creative_catalog", 0, is_right_click=True, is_shift_click=False)
    assert app.cursor_item == [GRASS, 1]

    # Right click again on same stackable item increments count
    app.handle_slot_click("creative_catalog", 0, is_right_click=True, is_shift_click=False)
    assert app.cursor_item == [GRASS, 2]


def test_creative_catalog_shift_click_hotbar(headless_app):
    """Shift-click on catalog slot moves full stack directly to hotbar."""
    app = headless_app
    app.player.mode = "creative"
    app.craft_size = 2
    app.creative_tab = "catalog"
    for s in app.hotbar:
        s[0], s[1] = 0, 0

    # Shift-click on Stone in catalog
    stone_idx = CREATIVE_CATALOG.index(STONE)
    app.handle_slot_click("creative_catalog", stone_idx, is_right_click=False, is_shift_click=True)
    assert app.hotbar[0] == [STONE, 64]

    # Shift-click on Diamond Sword (non-stackable tool)
    sword_idx = CREATIVE_CATALOG.index(ITEM_DIAMOND_SWORD)
    app.handle_slot_click("creative_catalog", sword_idx, is_right_click=False, is_shift_click=True)
    assert app.hotbar[1] == [ITEM_DIAMOND_SWORD, 1]


def test_creative_trash_slot_and_clear_all(headless_app):
    """Clicking trash destroys held item; shift-clicking trash clears all hotbar and inventory."""
    app = headless_app
    app.player.mode = "creative"
    app.craft_size = 2
    app.creative_tab = "catalog"

    # Single item trash
    app.cursor_item = [BEDROCK, 64]
    app.handle_slot_click("trash", 0, is_right_click=False, is_shift_click=False)
    assert app.cursor_item == [0, 0]

    # Shift-click trash clears all inventory and hotbar
    app.hotbar[0] = [DIRT, 64]
    app.inventory[0] = [STONE, 64]
    app.cursor_item = [GRASS, 64]

    app.handle_slot_click("trash", 0, is_right_click=False, is_shift_click=True)
    assert all(s[0] == 0 and s[1] == 0 for s in app.hotbar)
    assert all(s[0] == 0 and s[1] == 0 for s in app.inventory)
    assert app.cursor_item == [0, 0]


def test_creative_tab_switching(headless_app):
    """Clicking tab switches between catalog and survival tabs."""
    app = headless_app
    app.player.mode = "creative"
    app.creative_tab = "catalog"

    app.handle_slot_click("tab", "survival", is_right_click=False, is_shift_click=False)
    assert app.creative_tab == "survival"

    app.handle_slot_click("tab", "catalog", is_right_click=False, is_shift_click=False)
    assert app.creative_tab == "catalog"


def test_creative_hotbar_clear_shift_click(headless_app):
    """Shift-clicking a hotbar slot in creative catalog clears the slot."""
    app = headless_app
    app.player.mode = "creative"
    app.craft_size = 2
    app.creative_tab = "catalog"
    app.hotbar[2] = [GRASS, 64]

    app.handle_slot_click("hotbar", 2, is_right_click=False, is_shift_click=True)
    assert app.hotbar[2] == [0, 0]


def test_creative_inventory_close_clears_cursor(headless_app):
    """Closing inventory in creative mode cleanly clears cursor item."""
    app = headless_app
    app.player.mode = "creative"
    app.cursor_item = [BEDROCK, 64]

    app.close_inventory()
    assert app.cursor_item == [0, 0]
    assert app.state == "playing"
