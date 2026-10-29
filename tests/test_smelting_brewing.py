"""Tests for smelting, blast furnaces, brewing stands, and anvil metallurgy mechanics."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from smelting_brewing import FurnaceState, FurnaceType, BrewingStandState, AnvilLogic
import blocks


def test_furnace_smelting_and_fuel_consumption():
    furnace = FurnaceState(furnace_type=FurnaceType.STANDARD)
    # Put 1 Cobblestone in input slot
    furnace.input_slot = [blocks.COBBLESTONE, 1]
    # Put 1 Coal in fuel slot (provides 80 burn ticks)
    furnace.fuel_slot = [blocks.COAL_ORE, 1]

    # Tick 1: fuel is consumed
    furnace.tick()
    assert furnace.fuel_slot[1] == 0  # Consumed
    assert furnace.burn_time_remaining == 80
    assert furnace.cook_progress == 1

    # Fast forward remaining 199 ticks to complete 200 tick cook cycle
    # (furnace needs another fuel if 80 runs out, so give extra fuel)
    furnace.fuel_slot = [blocks.COAL_ORE, 2]
    for _ in range(199):
        furnace.tick()

    # Output produced: Stone
    assert furnace.output_slot == [blocks.STONE, 1]
    assert furnace.input_slot == [0, 0]


def test_blast_furnace_speed():
    furnace = FurnaceState(furnace_type=FurnaceType.BLAST_FURNACE)
    assert furnace.cook_time_needed == 100


def test_anvil_unit_repair():
    # Diamond tool with max_dur = 1561, currently at 500
    tool = (blocks.ITEM_DIAMOND_PICKAXE, 1, 500)
    # 1 diamond adds 25% of 1561 = 390
    repaired, cost, new_prior = AnvilLogic.unit_repair(tool, material_count=1, prior_work=0, max_dur=1561)

    assert repaired is not None
    assert repaired[2] == 500 + int(1561 * 0.25)
    assert cost == 1  # 0 penalty + 1 material
    assert new_prior == 1


def test_anvil_tool_fusion_and_too_expensive():
    tool_a = (blocks.ITEM_DIAMOND_SWORD, 1, 300)
    tool_b = (blocks.ITEM_DIAMOND_SWORD, 1, 400)
    max_dur = 1561
    bonus = int(max_dur * 0.12)

    # First fusion with 0 prior work
    fused, cost, new_prior = AnvilLogic.fuse_tools(tool_a, tool_b, prior_a=0, prior_b=0, max_dur=max_dur)
    assert fused is not None
    assert fused[2] == 300 + 400 + bonus
    assert cost == 2
    assert new_prior == 1

    # Prior work penalty test: prior work = 5 -> penalty = 2^5 - 1 = 31 levels
    # Combined with prior work 4 (15 levels): 31 + 15 + 2 = 48 levels >= 40 -> Too Expensive!
    fused_exp, cost_exp, _ = AnvilLogic.fuse_tools(tool_a, tool_b, prior_a=5, prior_b=4, max_dur=max_dur)
    assert fused_exp is None  # Blocked!
    assert cost_exp >= 40


def test_furnace_ui_open_and_close(headless_app):
    """Verify right-clicking a furnace block in the world opens furnace UI."""
    app = headless_app
    fx, fy, fz = 10, 20, 10
    app.world.set(fx, fy, fz, blocks.FURNACE)
    app.target = ((fx, fy, fz), (fx, fy + 1, fz))

    app.open_furnace_at(fx, fy, fz)
    assert app.state == "furnace"
    assert app.active_furnace is not None
    assert app.active_furnace_pos == (fx, fy, fz)

    # Check furnace layout keys
    lay = app.craft_layout()
    assert lay["type"] == "furnace"
    assert "in_x" in lay and "fuel_x" in lay and "out_x" in lay
    assert "flame_x" in lay and "arrow_x" in lay

    # Closing inventory retains furnace items in world
    app.active_furnace.input_slot = [blocks.COBBLESTONE, 10]
    app.close_inventory()
    assert app.state == "playing"
    assert app.active_furnace is None
    # Re-opening furnace preserves the 10 cobblestones
    app.open_furnace_at(fx, fy, fz)
    assert app.active_furnace.input_slot == [blocks.COBBLESTONE, 10]


def test_furnace_shift_click_routing(headless_app):
    """Shift-clicking fuels or smeltables in inventory routes directly to furnace slots."""
    app = headless_app
    app.open_furnace_at(5, 10, 5)
    furn = app.active_furnace

    # Slot 0 in inventory has Coal (fuel)
    app.inventory[0] = [blocks.COAL_ORE, 8]
    app.handle_slot_click("inventory", 0, is_right_click=False, is_shift_click=True)
    assert furn.fuel_slot == [blocks.COAL_ORE, 8]
    assert app.inventory[0] == [0, 0]

    # Slot 1 in inventory has Cobblestone (smeltable)
    app.inventory[1] = [blocks.COBBLESTONE, 16]
    app.handle_slot_click("inventory", 1, is_right_click=False, is_shift_click=True)
    assert furn.input_slot == [blocks.COBBLESTONE, 16]
    assert app.inventory[1] == [0, 0]


def test_furnace_world_ticking_and_lit_state(headless_app):
    """Furnace ticks at 20Hz and updates world block between FURNACE and LIT_FURNACE."""
    app = headless_app
    fx, fy, fz = 15, 25, 15
    app.world.set(fx, fy, fz, blocks.FURNACE)
    app.open_furnace_at(fx, fy, fz)
    furn = app.active_furnace
    furn.input_slot = [blocks.COBBLESTONE, 5]
    furn.fuel_slot = [blocks.COAL_ORE, 4]

    # Tick 1: starts burning, world block turns into LIT_FURNACE
    app.tick_furnaces()
    assert furn.is_burning
    assert app.world.get(fx, fy, fz) == blocks.LIT_FURNACE

    # Tick 200 times to complete 1 cook cycle
    for _ in range(199):
        app.tick_furnaces()
    assert furn.output_slot == [blocks.STONE, 1]
    assert furn.input_slot == [blocks.COBBLESTONE, 4]


def test_furnace_break_drops_contents(headless_app):
    """Breaking a furnace drops all its contents (input, fuel, output) and drops regular FURNACE."""
    app = headless_app
    app.player.mode = "survival"
    fx, fy, fz = 20, 30, 20
    app.world.set(fx, fy, fz, blocks.LIT_FURNACE)
    app.open_furnace_at(fx, fy, fz)
    furn = app.active_furnace
    furn.input_slot = [blocks.SAND, 3]
    furn.fuel_slot = [blocks.PLANKS, 2]
    furn.output_slot = [blocks.GLASS, 4]
    app.close_inventory()

    # Break block
    app.break_target_block((fx, fy, fz), blocks.LIT_FURNACE)
    assert app.world.get(fx, fy, fz) == 0
    assert (fx, fy, fz) not in app.furnaces

    # Verify dropped items exist in entity_mgr
    dropped_types = [item.item_id for item in app.entity_mgr.dropped_items]
    assert blocks.FURNACE in dropped_types  # LIT_FURNACE drops as FURNACE
    assert blocks.SAND in dropped_types
    assert blocks.PLANKS in dropped_types
    assert blocks.GLASS in dropped_types


def test_furnace_save_and_load(headless_app):
    """World snapshot serializes furnaces and start_game restores them."""
    app = headless_app
    fx, fy, fz = 7, 14, 21
    app.open_furnace_at(fx, fy, fz)
    furn = app.active_furnace
    furn.input_slot = [blocks.IRON_ORE, 3]
    furn.fuel_slot = [blocks.COAL_ORE, 5]
    furn.output_slot = [blocks.STONE, 2]
    furn.burn_time_remaining = 42
    furn.burn_time_max = 80
    furn.cook_progress = 55
    app.close_inventory()

    # Snapshot world
    snap = app.snapshot()
    assert "furnaces" in snap
    assert snap["furnaces"].shape[0] >= 1

    # Simulate reloading world save_data
    app.save_data = snap
    app.start_game(new_world=False)

    assert (fx, fy, fz) in app.furnaces
    loaded_furn = app.furnaces[(fx, fy, fz)]
    assert loaded_furn.input_slot == [blocks.IRON_ORE, 3]
    assert loaded_furn.fuel_slot == [blocks.COAL_ORE, 5]
    assert loaded_furn.output_slot == [blocks.STONE, 2]
    assert loaded_furn.burn_time_remaining == 42
    assert loaded_furn.burn_time_max == 80
    assert loaded_furn.cook_progress == 55


