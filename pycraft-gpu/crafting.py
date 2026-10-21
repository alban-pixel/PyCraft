"""Crafting system: recipes matching for 2x2 and 3x3 grids."""
from blocks import (
    COBBLESTONE, CRAFTING_TABLE, DIAMOND_ORE, IRON_ORE, ITEM_COOKED_PORK, ITEM_DIAMOND_PICKAXE,
    ITEM_DIAMOND_SWORD, ITEM_IRON_PICKAXE, ITEM_IRON_SWORD, ITEM_RAW_PORK, ITEM_STICK,
    ITEM_STONE_PICKAXE, ITEM_STONE_SWORD, ITEM_WOOD_PICKAXE, ITEM_WOOD_SWORD, LOG, PLANKS,
)

# Pattern format: list of rows (each row is a tuple of item_id or None)
RECIPES = [
    # 1 Log -> 4 Planks (shapeless 1x1)
    (((LOG,),), (PLANKS, 4)),
    # 4 Planks in 2x2 -> 1 Crafting Table
    (((PLANKS, PLANKS), (PLANKS, PLANKS)), (CRAFTING_TABLE, 1)),
    # 2 Planks vertical -> 4 Sticks
    (((PLANKS,), (PLANKS,)), (ITEM_STICK, 4)),
    # 1 Raw pork -> 1 Cooked pork
    (((ITEM_RAW_PORK,),), (ITEM_COOKED_PORK, 1)),

    # Wooden Pickaxe (3 Planks + 2 Sticks)
    (
        (
            (PLANKS, PLANKS, PLANKS),
            (None, ITEM_STICK, None),
            (None, ITEM_STICK, None),
        ),
        (ITEM_WOOD_PICKAXE, 1),
    ),
    # Stone Pickaxe (3 Cobblestone + 2 Sticks)
    (
        (
            (COBBLESTONE, COBBLESTONE, COBBLESTONE),
            (None, ITEM_STICK, None),
            (None, ITEM_STICK, None),
        ),
        (ITEM_STONE_PICKAXE, 1),
    ),
    # Iron Pickaxe (3 Iron + 2 Sticks)
    (
        (
            (IRON_ORE, IRON_ORE, IRON_ORE),
            (None, ITEM_STICK, None),
            (None, ITEM_STICK, None),
        ),
        (ITEM_IRON_PICKAXE, 1),
    ),
    # Diamond Pickaxe (3 Diamond + 2 Sticks)
    (
        (
            (DIAMOND_ORE, DIAMOND_ORE, DIAMOND_ORE),
            (None, ITEM_STICK, None),
            (None, ITEM_STICK, None),
        ),
        (ITEM_DIAMOND_PICKAXE, 1),
    ),

    # Wooden Sword (2 Planks + 1 Stick)
    (
        (
            (PLANKS,),
            (PLANKS,),
            (ITEM_STICK,),
        ),
        (ITEM_WOOD_SWORD, 1),
    ),
    # Stone Sword (2 Cobblestone + 1 Stick)
    (
        (
            (COBBLESTONE,),
            (COBBLESTONE,),
            (ITEM_STICK,),
        ),
        (ITEM_STONE_SWORD, 1),
    ),
    # Iron Sword (2 Iron + 1 Stick)
    (
        (
            (IRON_ORE,),
            (IRON_ORE,),
            (ITEM_STICK,),
        ),
        (ITEM_IRON_SWORD, 1),
    ),
    # Diamond Sword (2 Diamond + 1 Stick)
    (
        (
            (DIAMOND_ORE,),
            (DIAMOND_ORE,),
            (ITEM_STICK,),
        ),
        (ITEM_DIAMOND_SWORD, 1),
    ),
]


def trim_grid(grid_slots, width, height):
    """Extract subgrid containing all items, trimming empty outer rows and columns.

    grid_slots is a list of [item_id, count] of length width * height.
    Returns (pattern, coords_list) where pattern is a tuple of tuples, or (None, None).
    """
    matrix = []
    for r in range(height):
        row = []
        for c in range(width):
            slot = grid_slots[r * width + c]
            item = slot[0] if (slot and slot[1] > 0 and slot[0] != 0) else None
            row.append(item)
        matrix.append(row)

    # Find non-empty bounds
    min_r, max_r = height, -1
    min_c, max_c = width, -1
    for r in range(height):
        for c in range(width):
            if matrix[r][c] is not None:
                min_r = min(min_r, r)
                max_r = max(max_r, r)
                min_c = min(min_c, c)
                max_c = max(max_c, c)

    if max_r == -1:
        return None, None

    pattern = tuple(
        tuple(matrix[r][c] for c in range(min_c, max_c + 1))
        for r in range(min_r, max_r + 1)
    )
    coords = [
        r * width + c
        for r in range(min_r, max_r + 1)
        for c in range(min_c, max_c + 1)
        if matrix[r][c] is not None
    ]
    return pattern, coords


def check_craft(grid_slots, width, height):
    """Check if the grid matches any recipe. Returns (result_item, result_count) or None."""
    pattern, _ = trim_grid(grid_slots, width, height)
    if pattern is None:
        return None
    for rec_pattern, result in RECIPES:
        if pattern == rec_pattern:
            return result
    return None


def execute_craft(grid_slots, width, height):
    """Consume 1 item from each ingredient slot in the recipe. Returns (result_item, result_count) or None."""
    pattern, coords = trim_grid(grid_slots, width, height)
    if pattern is None:
        return None
    for rec_pattern, result in RECIPES:
        if pattern == rec_pattern:
            for idx in coords:
                slot = grid_slots[idx]
                if slot and slot[1] > 0:
                    slot[1] -= 1
                    if slot[1] <= 0:
                        slot[0] = 0
            return result
    return None
