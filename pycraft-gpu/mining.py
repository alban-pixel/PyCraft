"""Mathematical mining damage model, tool tiers, environmental penalties, and durability.

Implements the deterministic mining system:
- Damage per tick: P_tick = S_tool / (H_block * C)
    C = 30 if tool is adequate/effective, C = 100 if inadequate or bare hand.
- Tool multipliers: Hand 1.0, Wood 2.0, Stone 4.0, Iron 6.0, Diamond 8.0, Netherite 9.0, Gold 12.0.
- Efficiency enchantment bonus: +(N^2 + 1).
- Environmental penalties:
    In water without Aqua Affinity: / 5 (x 0.20).
    In air (not on ground): / 5 (x 0.20).
- Instamine: If P_tick >= 1.0 -> breaks in 1 tick, 0 consecutive latency.
- Break time: T_ticks = ceil(1 / P_tick) + 5 ticks consecutive latency.
- Tool durability table and consumption.
"""
from dataclasses import dataclass
import math
from typing import Dict, Optional, Tuple

from blocks import (
    BEDROCK, BRICK, COAL_ORE, COBBLESTONE, CRAFTING_TABLE, DIAMOND_ORE,
    DIRT, GLASS, GLOWSTONE, GOLD_ORE, GRASS, ICE, IRON_ORE, LEAVES,
    LOG, OBSIDIAN, PLANKS, SAND, SLIME, SNOW, STONE,
    ITEM_WOOD_PICKAXE, ITEM_STONE_PICKAXE, ITEM_IRON_PICKAXE, ITEM_DIAMOND_PICKAXE,
    ITEM_WOOD_SWORD, ITEM_STONE_SWORD, ITEM_IRON_SWORD, ITEM_DIAMOND_SWORD,
)

# Canonical block hardness values
BLOCK_HARDNESS_TABLE: Dict[int, float] = {
    BEDROCK: -1.0,      # Unbreakable
    OBSIDIAN: 50.0,
    STONE: 1.5,
    COBBLESTONE: 2.0,
    BRICK: 2.0,
    IRON_ORE: 3.0,
    GOLD_ORE: 3.0,
    COAL_ORE: 3.0,
    DIAMOND_ORE: 3.0,
    LOG: 2.0,
    PLANKS: 2.0,
    CRAFTING_TABLE: 2.5,
    DIRT: 0.5,
    GRASS: 0.6,
    SAND: 0.5,
    SNOW: 0.2,
    ICE: 0.5,
    GLASS: 0.3,
    GLOWSTONE: 0.3,
    LEAVES: 0.2,
    SLIME: 0.0,
}

# Base tool speeds S_tool
TOOL_TIER_SPEEDS: Dict[int, float] = {
    ITEM_WOOD_PICKAXE: 2.0,
    ITEM_STONE_PICKAXE: 4.0,
    ITEM_IRON_PICKAXE: 6.0,
    ITEM_DIAMOND_PICKAXE: 8.0,
}

# Max durability per tool tier
TOOL_DURABILITY_TABLE: Dict[int, int] = {
    ITEM_WOOD_PICKAXE: 59,
    ITEM_WOOD_SWORD: 59,
    ITEM_STONE_PICKAXE: 131,
    ITEM_STONE_SWORD: 131,
    ITEM_IRON_PICKAXE: 250,
    ITEM_IRON_SWORD: 250,
    ITEM_DIAMOND_PICKAXE: 1561,
    ITEM_DIAMOND_SWORD: 1561,
}

# Blocks effectively mined by pickaxes
PICKAXE_EFFECTIVE_BLOCKS = {
    STONE, COBBLESTONE, BRICK, IRON_ORE, GOLD_ORE, COAL_ORE, DIAMOND_ORE, OBSIDIAN, ICE
}


class MiningEngine:
    """Calculates tick-by-tick voxel destruction progress, penalties, and tool durability."""

    @staticmethod
    def is_tool_adequate(tool_id: int, block_id: int) -> bool:
        """True if tool is the appropriate type for this block category."""
        if tool_id in TOOL_TIER_SPEEDS and block_id in PICKAXE_EFFECTIVE_BLOCKS:
            return True
        return False

    @classmethod
    def compute_damage_per_tick(cls,
                                tool_id: int,
                                block_id: int,
                                efficiency_level: int = 0,
                                in_water: bool = False,
                                has_aqua_affinity: bool = False,
                                on_ground: bool = True) -> float:
        """Compute the fractional damage P_tick dealt to the block in one 20 Hz tick.

        Returns 0.0 if block is unbreakable.
        """
        hardness = BLOCK_HARDNESS_TABLE.get(block_id, 1.0)
        if hardness < 0:
            return 0.0  # Unbreakable (Bedrock)
        if hardness == 0.0:
            return 1.0  # Instabreak (Instant)

        is_adequate = cls.is_tool_adequate(tool_id, block_id)
        speed = TOOL_TIER_SPEEDS.get(tool_id, 1.0)

        # Efficiency enchantment bonus: +(N^2 + 1)
        if efficiency_level > 0 and is_adequate:
            speed += (efficiency_level * efficiency_level + 1)

        # Environmental penalties
        if in_water and not has_aqua_affinity:
            speed *= 0.20
        if not on_ground:
            speed *= 0.20

        # Divisor C: 30 if adequate tool, 100 otherwise
        c = 30.0 if is_adequate else 100.0

        return speed / (hardness * c)

    @classmethod
    def calculate_break_ticks(cls,
                              tool_id: int,
                              block_id: int,
                              efficiency_level: int = 0,
                              in_water: bool = False,
                              has_aqua_affinity: bool = False,
                              on_ground: bool = True) -> Tuple[int, bool]:
        """Compute required break ticks and whether instamine applies.

        Returns:
            (ticks_required, is_instamine)
        """
        p_tick = cls.compute_damage_per_tick(
            tool_id, block_id, efficiency_level, in_water, has_aqua_affinity, on_ground
        )
        if p_tick <= 0.0:
            return -1, False  # Unbreakable
        if p_tick >= 1.0:
            return 1, True  # Instamine in 1 tick

        # T_ticks = ceil(1 / P_tick)
        return math.ceil(1.0 / p_tick), False

    @classmethod
    def apply_tool_wear(cls, tool_slot: list, block_id: int) -> bool:
        """Consume 1 durability (2 if sword). Returns True if tool was broken.

        tool_slot format: [item_id, count, durability] or [item_id, count]
        """
        if not tool_slot or len(tool_slot) < 2 or tool_slot[0] == 0:
            return False

        tool_id = tool_slot[0]
        max_dur = TOOL_DURABILITY_TABLE.get(tool_id)
        if not max_dur:
            return False  # Not a durable tool (e.g. regular block)

        # Ensure slot has durability tracked
        if len(tool_slot) == 2:
            tool_slot.append(max_dur)

        wear = 2 if tool_id in (ITEM_WOOD_SWORD, ITEM_STONE_SWORD, ITEM_IRON_SWORD, ITEM_DIAMOND_SWORD) else 1
        tool_slot[2] -= wear

        if tool_slot[2] <= 0:
            # Tool broke!
            tool_slot[0] = 0
            tool_slot[1] = 0
            tool_slot[2] = 0
            return True
        return False
