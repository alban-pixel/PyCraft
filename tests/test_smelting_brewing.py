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
