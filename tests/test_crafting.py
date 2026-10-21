import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import blocks
from crafting import RECIPES, check_craft, execute_craft, trim_grid


def test_crafting_trim_grid():
    # 3x3 grid with a single item at center (1, 1)
    grid = [[0, 0] for _ in range(9)]
    grid[4] = [blocks.LOG, 2]

    pattern, coords = trim_grid(grid, 3, 3)
    assert pattern == ((blocks.LOG,),)
    assert coords == [4]


def test_crafting_log_to_planks():
    # 2x2 grid with 1 log in top-left
    grid = [[blocks.LOG, 1], [0, 0], [0, 0], [0, 0]]
    result = check_craft(grid, 2, 2)
    assert result == (blocks.PLANKS, 4)

    # Execute crafting
    crafted = execute_craft(grid, 2, 2)
    assert crafted == (blocks.PLANKS, 4)
    assert grid[0] == [0, 0]  # consumed log


def test_crafting_table_recipe():
    # 2x2 grid filled with planks
    grid = [
        [blocks.PLANKS, 2], [blocks.PLANKS, 1],
        [blocks.PLANKS, 3], [blocks.PLANKS, 1],
    ]
    result = check_craft(grid, 2, 2)
    assert result == (blocks.CRAFTING_TABLE, 1)

    crafted = execute_craft(grid, 2, 2)
    assert crafted == (blocks.CRAFTING_TABLE, 1)
    # Remaining counts
    assert grid[0] == [blocks.PLANKS, 1]
    assert grid[1] == [0, 0]
    assert grid[2] == [blocks.PLANKS, 2]
    assert grid[3] == [0, 0]


def test_crafting_wooden_pickaxe_3x3():
    # 3x3 grid:
    # [P] [P] [P]
    # [.] [S] [.]
    # [.] [S] [.]
    grid = [[0, 0] for _ in range(9)]
    grid[0] = [blocks.PLANKS, 1]
    grid[1] = [blocks.PLANKS, 1]
    grid[2] = [blocks.PLANKS, 1]
    grid[4] = [blocks.ITEM_STICK, 1]
    grid[7] = [blocks.ITEM_STICK, 1]

    result = check_craft(grid, 3, 3)
    assert result == (blocks.ITEM_WOOD_PICKAXE, 1)

    crafted = execute_craft(grid, 3, 3)
    assert crafted == (blocks.ITEM_WOOD_PICKAXE, 1)
    for slot in grid:
        assert slot == [0, 0]


def test_crafting_diamond_sword_3x3():
    # 3x3 grid:
    # [.] [D] [.]
    # [.] [D] [.]
    # [.] [S] [.]
    grid = [[0, 0] for _ in range(9)]
    grid[1] = [blocks.DIAMOND_ORE, 1]
    grid[4] = [blocks.DIAMOND_ORE, 1]
    grid[7] = [blocks.ITEM_STICK, 1]

    result = check_craft(grid, 3, 3)
    assert result == (blocks.ITEM_DIAMOND_SWORD, 1)


def test_crafting_invalid_pattern():
    # Random invalid arrangement
    grid = [[0, 0] for _ in range(4)]
    grid[0] = [blocks.STONE, 1]
    grid[1] = [blocks.DIRT, 1]

    result = check_craft(grid, 2, 2)
    assert result is None
    crafted = execute_craft(grid, 2, 2)
    assert crafted is None
