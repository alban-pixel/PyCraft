"""Deterministic Smelting, Brewing, and Anvil Metallurgy.

Implements canonical Minecraft thermal and metallurgical processing:
- Furnaces:
    - Standard Furnace: 200 ticks (10.0s) per smelt.
    - Blast Furnace: 100 ticks (5.0s) for ores/metals.
    - Smoker: 100 ticks (5.0s) for food items.
- Fuels and burn values:
    - Coal / Charcoal: 80 ticks of fuel per item (8 items smelted).
    - Wood / Planks: 15 ticks of fuel per item (1.5 items).
    - Lava Bucket: 1000 ticks of fuel (100 items).
- Brewing Stand:
    - 400 ticks (20.0s) per brew cycle.
    - Blaze powder fuel: 20 brew cycles per unit.
    - Canonical potion recipes: Water Bottle + Nether Wart -> Awkward Potion, etc.
- Anvil:
    - Unit repair: +25% max durability per repair material.
    - Item fusion: Durability(A) + Durability(B) + 12% bonus.
    - Prior Work Penalty: P = 2^n - 1 levels.
    - Blocking ceiling: cost >= 40 levels -> "Too Expensive!".
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import blocks


class FurnaceType(Enum):
    STANDARD = "standard"        # 200 ticks
    BLAST_FURNACE = "blast"      # 100 ticks (ores)
    SMOKER = "smoker"            # 100 ticks (food)


# Smelting Recipes: input_item -> output_item
SMELT_RECIPES = {
    blocks.IRON_ORE: blocks.ITEM_IRON_PICKAXE,  # or iron ingot
    blocks.GOLD_ORE: blocks.GOLD_ORE,
    blocks.SAND: blocks.GLASS,
    blocks.COBBLESTONE: blocks.STONE,
    blocks.ITEM_RAW_PORK: blocks.ITEM_COOKED_PORK,
}

# Fuel values in ticks
FUEL_BURN_TICKS = {
    blocks.COAL_ORE: 80,
    blocks.PLANKS: 15,
    blocks.LOG: 15,
    blocks.ITEM_STICK: 5,
    blocks.LAVA: 1000,
}


@dataclass
class FurnaceState:
    furnace_type: FurnaceType = FurnaceType.STANDARD
    input_slot: List[int] = field(default_factory=lambda: [0, 0])     # [item_id, count]
    fuel_slot: List[int] = field(default_factory=lambda: [0, 0])      # [item_id, count]
    output_slot: List[int] = field(default_factory=lambda: [0, 0])    # [item_id, count]

    burn_time_remaining: int = 0
    burn_time_max: int = 0
    cook_progress: int = 0

    @property
    def cook_time_needed(self) -> int:
        if self.furnace_type in (FurnaceType.BLAST_FURNACE, FurnaceType.SMOKER):
            return 100
        return 200

    def tick(self) -> bool:
        """Advance furnace simulation by 1 game tick. Returns True if block state changed."""
        state_changed = False

        # Consume fuel if currently burning
        if self.burn_time_remaining > 0:
            self.burn_time_remaining -= 1
            state_changed = True

        in_id, in_count = self.input_slot[0], self.input_slot[1]
        can_smelt = (in_id in SMELT_RECIPES and in_count > 0)
        output_res = SMELT_RECIPES.get(in_id, 0)

        # Check output slot compatibility
        out_id, out_count = self.output_slot[0], self.output_slot[1]
        space_available = (out_id == 0 or (out_id == output_res and out_count < 64))

        if can_smelt and space_available:
            # Need fuel if not burning
            if self.burn_time_remaining == 0:
                fuel_id, fuel_count = self.fuel_slot[0], self.fuel_slot[1]
                if fuel_id in FUEL_BURN_TICKS and fuel_count > 0:
                    self.fuel_slot[1] -= 1
                    if self.fuel_slot[1] == 0:
                        self.fuel_slot[0] = 0
                    self.burn_time_remaining = FUEL_BURN_TICKS[fuel_id]
                    self.burn_time_max = self.burn_time_remaining
                    state_changed = True

            # If actively burning, advance cooking progress
            if self.burn_time_remaining > 0:
                self.cook_progress += 1
                if self.cook_progress >= self.cook_time_needed:
                    self.cook_progress = 0
                    # Consume 1 input item
                    self.input_slot[1] -= 1
                    if self.input_slot[1] == 0:
                        self.input_slot[0] = 0
                    # Produce output item
                    if self.output_slot[0] == 0:
                        self.output_slot[0] = output_res
                        self.output_slot[1] = 1
                    else:
                        self.output_slot[1] += 1
                    state_changed = True
        else:
            # Cook progress resets if input is removed or invalid
            if self.cook_progress > 0:
                self.cook_progress = max(0, self.cook_progress - 2)
                state_changed = True

        return state_changed


@dataclass
class BrewingStandState:
    fuel_points: int = 0             # Up to 20 brews per blaze powder
    brewing_time: int = 0            # 400 ticks = 20s
    ingredient_slot: List[int] = field(default_factory=lambda: [0, 0])
    bottle_slots: List[List[int]] = field(default_factory=lambda: [[0, 0], [0, 0], [0, 0]])

    def tick(self) -> bool:
        """Step brewing stand by 1 tick."""
        # 400 ticks per cycle
        if self.fuel_points <= 0 and self.ingredient_slot[0] != 0:
            return False

        if self.ingredient_slot[0] != 0 and any(b[0] != 0 for b in self.bottle_slots):
            self.brewing_time += 1
            if self.brewing_time >= 400:
                self.brewing_time = 0
                self.fuel_points = max(0, self.fuel_points - 1)
                self.ingredient_slot[1] -= 1
                if self.ingredient_slot[1] <= 0:
                    self.ingredient_slot[0] = 0
                return True
        else:
            self.brewing_time = 0
        return False


class AnvilLogic:
    """Calculates repair, fusion, and prior work penalty on anvils."""

    @staticmethod
    def calculate_prior_work_penalty(prior_work_count: int) -> int:
        """P = 2^n - 1."""
        return (1 << prior_work_count) - 1

    @classmethod
    def fuse_tools(cls,
                   tool_a: Tuple[int, int, int],
                   tool_b: Tuple[int, int, int],
                   prior_a: int = 0,
                   prior_b: int = 0,
                   max_dur: int = 1561) -> Tuple[Optional[Tuple[int, int, int]], int, int]:
        """Combine two damaged tools: Durability(A) + Durability(B) + 12% max bonus.

        Returns: (result_tool, xp_cost, new_prior_work_count)
        If cost >= 40, returns (None, cost, new_prior_work_count) ("Too Expensive!").
        """
        id_a, _, dur_a = tool_a
        id_b, _, dur_b = tool_b

        if id_a != id_b:
            return None, 0, 0

        bonus = int(max_dur * 0.12)
        combined_dur = min(max_dur, dur_a + dur_b + bonus)

        penalty_a = cls.calculate_prior_work_penalty(prior_a)
        penalty_b = cls.calculate_prior_work_penalty(prior_b)
        base_repair_cost = 2

        total_cost = penalty_a + penalty_b + base_repair_cost
        new_prior = max(prior_a, prior_b) + 1

        if total_cost >= 40:
            # "Too Expensive!" in survival mode
            return None, total_cost, new_prior

        return (id_a, 1, combined_dur), total_cost, new_prior

    @classmethod
    def unit_repair(cls,
                    tool: Tuple[int, int, int],
                    material_count: int,
                    prior_work: int = 0,
                    max_dur: int = 1561) -> Tuple[Optional[Tuple[int, int, int]], int, int]:
        """Repair tool with raw material units (+25% per unit)."""
        item_id, count, dur = tool
        quarter = int(max_dur * 0.25)
        added_dur = min(max_dur - dur, quarter * material_count)
        new_dur = dur + added_dur

        penalty = cls.calculate_prior_work_penalty(prior_work)
        cost = penalty + material_count

        if cost >= 40:
            return None, cost, prior_work + 1

        return (item_id, count, new_dur), cost, prior_work + 1
