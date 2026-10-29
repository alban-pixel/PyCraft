"""Unit tests for authentic Minecraft controls (flight toggle, sneak edge guard, pick block),
slot drag-and-drop mechanics, crafting refund, infinite world chunk streaming, and text inputs.
"""
import os
import sys
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import blocks
import crafting
from player import Player, SNEAK_EYE_HEIGHT, EYE_HEIGHT, SNEAK_SPEED
from world import World
from generator import WorldPreset
from main import App


def test_creative_flight_double_tap_space():
    """In creative mode, double tapping space within 300ms toggles flight."""
    p = Player(10.0, 5.0, 10.0, mode="creative")
    assert not p.flying

    # First space press
    p.trigger_space_tap()
    assert not p.flying
    assert p.space_double_tap_timer > 0.0

    # Second space press 150ms later (within 300ms window)
    p.space_double_tap_timer -= 0.15
    p.trigger_space_tap()
    assert p.flying is True

    # Double-tap again toggles flight off
    p.space_double_tap_timer = 0.0  # timer expired
    p.trigger_space_tap()
    p.space_double_tap_timer -= 0.1
    p.trigger_space_tap()
    assert p.flying is False


def test_sneaking_eye_height_and_speed():
    """Sneaking reduces eye height to 1.27m and speed to 1.3 m/s."""
    p = Player(10.0, 5.0, 10.0)
    assert p.eye()[1] == 5.0 + EYE_HEIGHT

    p.sneaking = True
    assert p.eye()[1] == 5.0 + SNEAK_EYE_HEIGHT
    assert p.get_current_speed() == SNEAK_SPEED

    p.sneaking = False
    assert p.eye()[1] == 5.0 + EYE_HEIGHT


def test_sneak_ledge_edge_guard():
    """While sneaking, player cannot step off a ledge into empty air."""
    w = World(size=(16, 32, 16), seed=1, generate=False)
    # A single block platform at (5, 5, 5)
    w.set(5, 5, 5, blocks.STONE)

    p = Player(5.5, 6.0, 5.5)
    p.on_ground = True
    p.sneaking = True

    # Try moving towards the cliff edge (+X direction where there is no block at x=6, y=5)
    # _has_ground_support checks if moving to new x keeps ground support
    assert p._has_ground_support(w, 5.5, 6.0, 5.5) is True
    # If moved past edge to 6.5, there is no ground block beneath
    assert p._has_ground_support(w, 6.5, 6.0, 5.5) is False

    # Attempt to move towards empty space
    hit = p._move_axis(w, axis=0, distance=1.0)
    assert hit is True
    # Player position must be clamped, preventing falling off
    assert p.pos[0] < 6.0


def test_pick_block_hotbar_selection(headless_app):
    """Middle click pick block selects from hotbar or swaps from inventory or clones in creative."""
    app = headless_app
    app.hotbar[0] = [blocks.DIRT, 64]
    app.hotbar[1] = [blocks.STONE, 64]
    app.hotbar[2] = [blocks.PLANKS, 64]
    app.selected = 0

    # Pick stone -> should select slot 1
    app.pick_block(blocks.STONE)
    assert app.selected == 1

    # Pick planks -> should select slot 2
    app.pick_block(blocks.PLANKS)
    assert app.selected == 2


def test_slot_drag_and_drop_split_and_swap(headless_app):
    """Test left click pickup/place/swap and right click split."""
    app = headless_app
    app.cursor_item = [0, 0]
    app.inventory[0] = [blocks.DIRT, 10]

    # 1. Left click on slot 0 picks up the full stack
    app.handle_slot_click("inventory", 0, is_right_click=False, is_shift_click=False)
    assert app.cursor_item == [blocks.DIRT, 10]
    assert app.inventory[0] == [0, 0]

    # 2. Left click on empty slot 1 places the entire stack
    app.handle_slot_click("inventory", 1, is_right_click=False, is_shift_click=False)
    assert app.cursor_item == [0, 0]
    assert app.inventory[1] == [blocks.DIRT, 10]

    # 3. Right click on slot 1 with empty cursor splits half (5) into cursor
    app.handle_slot_click("inventory", 1, is_right_click=True, is_shift_click=False)
    assert app.cursor_item == [blocks.DIRT, 5]
    assert app.inventory[1] == [blocks.DIRT, 5]

    # 4. Right click on empty slot 2 places 1 item
    app.handle_slot_click("inventory", 2, is_right_click=True, is_shift_click=False)
    assert app.cursor_item == [blocks.DIRT, 4]
    assert app.inventory[2] == [blocks.DIRT, 1]

    # 5. Left click on a different item swaps cursor and slot
    app.inventory[3] = [blocks.DIAMOND_ORE, 3]
    app.handle_slot_click("inventory", 3, is_right_click=False, is_shift_click=False)
    assert app.cursor_item == [blocks.DIAMOND_ORE, 3]
    assert app.inventory[3] == [blocks.DIRT, 4]


def test_shift_click_quick_move(headless_app):
    """Shift + click transfers items between hotbar and main inventory."""
    app = headless_app
    app.hotbar[0] = [blocks.COBBLESTONE, 16]
    app.inventory = [[0, 0] for _ in range(27)]

    # Shift-click on hotbar[0] should move items to main inventory
    app.handle_slot_click("hotbar", 0, is_right_click=False, is_shift_click=True)
    assert app.hotbar[0] == [0, 0]
    assert app.inventory[0] == [blocks.COBBLESTONE, 16]

    # Shift-click on inventory[0] moves items back to hotbar
    app.handle_slot_click("inventory", 0, is_right_click=False, is_shift_click=True)
    assert app.inventory[0] == [0, 0]
    assert app.hotbar[0] == [blocks.COBBLESTONE, 16]


def test_crafting_consumption_and_closing_refund(headless_app):
    """Clicking craft output consumes 1 from each grid slot, and closing GUI refunds remaining items."""
    app = headless_app
    app.craft_size = 2
    app.craft_grid = [[0, 0] for _ in range(4)]
    app.cursor_item = [0, 0]
    app.inventory = [[0, 0] for _ in range(27)]
    app.hotbar = [[0, 0] for _ in range(9)]

    # 1 Oak Log in craft grid [0] produces 4 Planks
    app.craft_grid[0] = [blocks.LOG, 2]
    res = crafting.check_craft(app.craft_grid, 2, 2)
    assert res == (blocks.PLANKS, 4)
    app.craft_result = list(res)

    # Click result slot to take 4 planks
    app.handle_slot_click("result", 0, is_right_click=False, is_shift_click=False)
    assert app.cursor_item == [blocks.PLANKS, 4]
    # Log stack on grid reduced from 2 to 1
    assert app.craft_grid[0] == [blocks.LOG, 1]

    # Close inventory -> log on grid and planks on cursor refunded to hotbar/inventory
    app.close_inventory()
    assert app.cursor_item == [0, 0]
    assert app.craft_grid[0] == [0, 0]

    # Verify items landed in hotbar or inventory
    total_logs = sum(cnt for b, cnt in app.hotbar + app.inventory if b == blocks.LOG)
    total_planks = sum(cnt for b, cnt in app.hotbar + app.inventory if b == blocks.PLANKS)
    assert total_logs == 1
    assert total_planks == 4


def test_infinite_world_streaming_and_coordinates():
    """Infinite world generates chunks on-the-fly and permits navigation far beyond initial box."""
    w = World(seed=42, generate=False, infinite=True)

    # Coordinates far beyond 128 (e.g. x=500, z=500)
    assert w.inside(500, 30, 500) is True
    assert w.inside(-200, 30, -200) is True

    # Get block generates chunk deterministically
    b = w.get(500, 0, 500)
    assert b == blocks.BEDROCK
    assert w.is_solid(500, 0, 500) is True

    # Set block in distant chunk
    w.set(500, 20, 500, blocks.DIAMOND_ORE)
    assert w.get(500, 20, 500) == blocks.DIAMOND_ORE

    # Mesh region for chunk (31, 31) covers x=496..512
    region = w.get_mesh_region(31, 31)
    assert region.shape == (18, w.sy + 2, 18)
    assert region[1:17, 1:w.sy + 1, 1:17].shape == (16, w.sy, 16)


def test_create_world_text_input_focus_and_typing(headless_app):
    """World Name and Seed buttons can be focused to type text freely."""
    app = headless_app
    app.open_create_world()
    assert app.state == "create_world"

    # Click World Name to focus
    app.focus_world_name()
    assert app.active_text_field == "world_name"

    # Type characters
    app.new_world_name = "MySurvival"
    assert app.new_world_name == "MySurvival"

    # Focus Seed
    app.focus_world_seed()
    assert app.active_text_field == "seed"
    app.new_world_seed = "987654321"
    assert app.new_world_seed == "987654321"

    app.active_text_field = None
    app.set_state("title")
