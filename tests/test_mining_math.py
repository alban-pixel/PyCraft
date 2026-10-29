"""Unit tests for the Mining damage math, tool multipliers, environmental penalties, and durability."""
import math
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from mining import (
    MiningEngine, BLOCK_HARDNESS_TABLE, TOOL_DURABILITY_TABLE,
    ITEM_WOOD_PICKAXE, ITEM_STONE_PICKAXE, ITEM_DIAMOND_PICKAXE, ITEM_IRON_SWORD,
    BEDROCK, STONE, DIRT, SLIME, OBSIDIAN
)


def test_bedrock_unbreakable():
    p_tick = MiningEngine.compute_damage_per_tick(ITEM_DIAMOND_PICKAXE, BEDROCK)
    assert p_tick == 0.0

    ticks, instamine = MiningEngine.calculate_break_ticks(ITEM_DIAMOND_PICKAXE, BEDROCK)
    assert ticks == -1
    assert instamine is False


def test_slime_instamine():
    ticks, instamine = MiningEngine.calculate_break_ticks(0, SLIME)
    assert ticks == 1
    assert instamine is True


def test_stone_mining_ticks_progression():
    # Stone hardness = 1.5
    # Bare hand: S=1.0, C=100 -> P_tick = 1.0 / (1.5 * 100) = 1/150 -> 150 ticks (7.5s)
    hand_ticks, hand_insta = MiningEngine.calculate_break_ticks(0, STONE)
    assert hand_ticks == 150
    assert hand_insta is False

    # Wooden pickaxe: S=2.0, C=30 -> P_tick = 2.0 / (1.5 * 30) = 2/45 -> ceil(45/2) = 23 ticks (1.15s)
    wood_ticks, _ = MiningEngine.calculate_break_ticks(ITEM_WOOD_PICKAXE, STONE)
    assert wood_ticks == 23

    # Diamond pickaxe: S=8.0, C=30 -> P_tick = 8.0 / (1.5 * 30) = 8/45 -> ceil(45/8) = 6 ticks (0.3s)
    dia_ticks, _ = MiningEngine.calculate_break_ticks(ITEM_DIAMOND_PICKAXE, STONE)
    assert dia_ticks == 6


def test_efficiency_enchantment_bonus():
    # Diamond pickaxe on stone: base speed 8.0
    # Efficiency V (N=5): speed bonus = +(5^2 + 1) = +26 -> Total speed = 34.0
    # P_tick = 34.0 / (1.5 * 30) = 34 / 45 -> ceil(45/34) = 2 ticks!
    eff5_ticks, _ = MiningEngine.calculate_break_ticks(
        ITEM_DIAMOND_PICKAXE, STONE, efficiency_level=5
    )
    assert eff5_ticks == 2


def test_environmental_penalties():
    # Diamond pickaxe on stone on ground: 6 ticks
    # Not on ground (in air): speed * 0.2 -> ceil(45 / 1.6) = 29 ticks
    air_ticks, _ = MiningEngine.calculate_break_ticks(
        ITEM_DIAMOND_PICKAXE, STONE, on_ground=False
    )
    assert air_ticks == 29

    # Underwater without aqua affinity: speed * 0.2 -> 29 ticks
    water_ticks, _ = MiningEngine.calculate_break_ticks(
        ITEM_DIAMOND_PICKAXE, STONE, in_water=True, has_aqua_affinity=False
    )
    assert water_ticks == 29

    # Both underwater and in air: speed * 0.04 -> ceil(45 / 0.32) = 141 ticks
    both_ticks, _ = MiningEngine.calculate_break_ticks(
        ITEM_DIAMOND_PICKAXE, STONE, in_water=True, has_aqua_affinity=False, on_ground=False
    )
    assert both_ticks == 141


def test_tool_wear_and_breakage():
    # Iron pickaxe: max durability 250
    slot = [ITEM_STONE_PICKAXE, 1, 3]  # Only 3 durability left
    broke = MiningEngine.apply_tool_wear(slot, STONE)
    assert broke is False
    assert slot[2] == 2

    broke = MiningEngine.apply_tool_wear(slot, STONE)
    assert broke is False
    assert slot[2] == 1

    # Final use breaks the tool
    broke = MiningEngine.apply_tool_wear(slot, STONE)
    assert broke is True
    assert slot[0] == 0  # Replaced by empty
    assert slot[1] == 0


def test_sword_double_wear_mining():
    slot = [ITEM_IRON_SWORD, 1, 10]
    broke = MiningEngine.apply_tool_wear(slot, DIRT)
    assert broke is False
    assert slot[2] == 8  # Swords lose 2 durability when used to mine blocks!
