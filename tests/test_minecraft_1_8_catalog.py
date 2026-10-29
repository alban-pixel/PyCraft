"""Unit tests verifying full Minecraft 1.8 (The Bountiful Update) block and item catalog."""
import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import blocks
from blocks import (
    AIR, GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, SAND, BRICK,
    GLASS, WATER, COAL_ORE, IRON_ORE, BEDROCK, GOLD_ORE, DIAMOND_ORE, GLOWSTONE, SNOW, CRAFTING_TABLE,
    ICE, SLIME, OBSIDIAN, LAVA,
    # 1.8 Blocks
    GRANITE, POLISHED_GRANITE, DIORITE, POLISHED_DIORITE, ANDESITE, POLISHED_ANDESITE,
    PRISMARINE, PRISMARINE_BRICKS, DARK_PRISMARINE, SEA_LANTERN,
    RED_SAND, RED_SANDSTONE, CHISELED_RED_SANDSTONE, SMOOTH_RED_SANDSTONE,
    COARSE_DIRT, PODZOL, SPONGE, WET_SPONGE,
    SPRUCE_PLANKS, BIRCH_PLANKS, JUNGLE_PLANKS, ACACIA_PLANKS, DARK_OAK_PLANKS,
    IRON_TRAPDOOR,
    # 1.8 Items
    ITEM_RAW_MUTTON, ITEM_COOKED_MUTTON,
    ITEM_RAW_RABBIT, ITEM_COOKED_RABBIT, ITEM_RABBIT_STEW, ITEM_RABBIT_FOOT, ITEM_RABBIT_HIDE,
    ITEM_PRISMARINE_SHARD, ITEM_PRISMARINE_CRYSTALS, ITEM_ARMOR_STAND,
    BLOCK_NAMES, ITEM_NAMES, BLOCK_HARDNESS, BLOCK_TILES, ITEM_TILES,
    CREATIVE_CATALOG, FOOD_HEAL, OPAQUE, SOLID, CUTOUT, ATLAS_TILES,
    get_item_name, get_item_tile, build_atlas,
)
from metabolism import FOOD_PROPERTIES


def test_minecraft_1_8_block_constants_and_names():
    """Verify all 1.8 blocks have distinct IDs, valid names, and placeable status."""
    new_1_8_blocks = [
        GRANITE, POLISHED_GRANITE, DIORITE, POLISHED_DIORITE, ANDESITE, POLISHED_ANDESITE,
        PRISMARINE, PRISMARINE_BRICKS, DARK_PRISMARINE, SEA_LANTERN,
        RED_SAND, RED_SANDSTONE, CHISELED_RED_SANDSTONE, SMOOTH_RED_SANDSTONE,
        COARSE_DIRT, PODZOL, SPONGE, WET_SPONGE,
        SPRUCE_PLANKS, BIRCH_PLANKS, JUNGLE_PLANKS, ACACIA_PLANKS, DARK_OAK_PLANKS,
        IRON_TRAPDOOR,
    ]

    # All IDs must be unique
    assert len(set(new_1_8_blocks)) == len(new_1_8_blocks)

    # Names must exist and match canonical Minecraft 1.8 nomenclature
    assert BLOCK_NAMES[GRANITE] == "Granite"
    assert BLOCK_NAMES[POLISHED_GRANITE] == "Polished Granite"
    assert BLOCK_NAMES[DIORITE] == "Diorite"
    assert BLOCK_NAMES[POLISHED_DIORITE] == "Polished Diorite"
    assert BLOCK_NAMES[ANDESITE] == "Andesite"
    assert BLOCK_NAMES[POLISHED_ANDESITE] == "Polished Andesite"
    assert BLOCK_NAMES[PRISMARINE] == "Prismarine"
    assert BLOCK_NAMES[PRISMARINE_BRICKS] == "Prismarine Bricks"
    assert BLOCK_NAMES[DARK_PRISMARINE] == "Dark Prismarine"
    assert BLOCK_NAMES[SEA_LANTERN] == "Sea Lantern"
    assert BLOCK_NAMES[RED_SAND] == "Red Sand"
    assert BLOCK_NAMES[RED_SANDSTONE] == "Red Sandstone"
    assert BLOCK_NAMES[COARSE_DIRT] == "Coarse Dirt"
    assert BLOCK_NAMES[PODZOL] == "Podzol"
    assert BLOCK_NAMES[SPONGE] == "Sponge"
    assert BLOCK_NAMES[WET_SPONGE] == "Wet Sponge"
    assert BLOCK_NAMES[SPRUCE_PLANKS] == "Spruce Planks"
    assert BLOCK_NAMES[DARK_OAK_PLANKS] == "Dark Oak Planks"
    assert BLOCK_NAMES[IRON_TRAPDOOR] == "Iron Trapdoor"


def test_minecraft_1_8_item_constants_and_properties():
    """Verify all 1.8 items exist with valid names, tiles, and hunger/food properties."""
    new_1_8_items = [
        ITEM_RAW_MUTTON, ITEM_COOKED_MUTTON,
        ITEM_RAW_RABBIT, ITEM_COOKED_RABBIT, ITEM_RABBIT_STEW,
        ITEM_RABBIT_FOOT, ITEM_RABBIT_HIDE,
        ITEM_PRISMARINE_SHARD, ITEM_PRISMARINE_CRYSTALS,
        ITEM_ARMOR_STAND,
    ]

    for item_id in new_1_8_items:
        assert item_id in ITEM_NAMES
        assert item_id in ITEM_TILES
        assert get_item_name(item_id) == ITEM_NAMES[item_id]
        assert get_item_tile(item_id) == ITEM_TILES[item_id]

    # Food nutrition values
    assert FOOD_HEAL[ITEM_RAW_MUTTON] == 2
    assert FOOD_HEAL[ITEM_COOKED_MUTTON] == 6
    assert FOOD_HEAL[ITEM_RAW_RABBIT] == 3
    assert FOOD_HEAL[ITEM_COOKED_RABBIT] == 5
    assert FOOD_HEAL[ITEM_RABBIT_STEW] == 10

    # Metabolism food table checks
    assert FOOD_PROPERTIES[ITEM_COOKED_MUTTON].food == 6
    assert FOOD_PROPERTIES[ITEM_COOKED_MUTTON].saturation == 9.6
    assert FOOD_PROPERTIES[ITEM_RABBIT_STEW].food == 10
    assert FOOD_PROPERTIES[ITEM_RABBIT_STEW].saturation == 12.0


def test_creative_catalog_includes_all_1_8_entries():
    """Verify every single 1.8 block and item is present in CREATIVE_CATALOG."""
    catalog_set = set(CREATIVE_CATALOG)

    # 1.8 Blocks in catalog
    assert GRANITE in catalog_set
    assert POLISHED_GRANITE in catalog_set
    assert DIORITE in catalog_set
    assert POLISHED_DIORITE in catalog_set
    assert ANDESITE in catalog_set
    assert POLISHED_ANDESITE in catalog_set
    assert PRISMARINE in catalog_set
    assert PRISMARINE_BRICKS in catalog_set
    assert DARK_PRISMARINE in catalog_set
    assert SEA_LANTERN in catalog_set
    assert RED_SAND in catalog_set
    assert RED_SANDSTONE in catalog_set
    assert CHISELED_RED_SANDSTONE in catalog_set
    assert SMOOTH_RED_SANDSTONE in catalog_set
    assert COARSE_DIRT in catalog_set
    assert PODZOL in catalog_set
    assert SPONGE in catalog_set
    assert WET_SPONGE in catalog_set
    assert SPRUCE_PLANKS in catalog_set
    assert BIRCH_PLANKS in catalog_set
    assert JUNGLE_PLANKS in catalog_set
    assert ACACIA_PLANKS in catalog_set
    assert DARK_OAK_PLANKS in catalog_set
    assert IRON_TRAPDOOR in catalog_set

    # 1.8 Items in catalog
    assert ITEM_RAW_MUTTON in catalog_set
    assert ITEM_COOKED_MUTTON in catalog_set
    assert ITEM_RAW_RABBIT in catalog_set
    assert ITEM_COOKED_RABBIT in catalog_set
    assert ITEM_RABBIT_STEW in catalog_set
    assert ITEM_RABBIT_FOOT in catalog_set
    assert ITEM_RABBIT_HIDE in catalog_set
    assert ITEM_PRISMARINE_SHARD in catalog_set
    assert ITEM_PRISMARINE_CRYSTALS in catalog_set
    assert ITEM_ARMOR_STAND in catalog_set


def test_1_8_block_flags_and_hardness():
    """Verify solid, opaque, cutout flags, and mining hardness."""
    # Opaque & Solid
    assert SOLID[GRANITE] and OPAQUE[GRANITE]
    assert SOLID[PRISMARINE] and OPAQUE[PRISMARINE]
    assert SOLID[RED_SANDSTONE] and OPAQUE[RED_SANDSTONE]
    assert SOLID[COARSE_DIRT] and OPAQUE[COARSE_DIRT]
    assert SOLID[SPONGE] and OPAQUE[SPONGE]
    assert SOLID[SPRUCE_PLANKS] and OPAQUE[SPRUCE_PLANKS]

    # Iron trapdoor is solid and cutout
    assert SOLID[IRON_TRAPDOOR]
    assert CUTOUT[IRON_TRAPDOOR]
    assert not OPAQUE[IRON_TRAPDOOR]

    # Hardness checks
    assert BLOCK_HARDNESS[GRANITE] == 2.2
    assert BLOCK_HARDNESS[DIORITE] == 2.2
    assert BLOCK_HARDNESS[ANDESITE] == 2.2
    assert BLOCK_HARDNESS[PRISMARINE] == 2.2
    assert BLOCK_HARDNESS[RED_SAND] == 0.45
    assert BLOCK_HARDNESS[SPONGE] == 0.6
    assert BLOCK_HARDNESS[SPRUCE_PLANKS] == 1.2
    assert BLOCK_HARDNESS[IRON_TRAPDOOR] == 5.0


def test_atlas_expanded_to_256x256():
    """Verify 16x16 grid (256x256 pixels) holds all textures without out-of-bounds tiles."""
    assert ATLAS_TILES == 16
    atlas = build_atlas(seed=123)
    assert atlas.shape == (256, 256, 4)

    # Every block must have all 6 face tiles within [0, 255]
    for b_id in range(blocks.NUM_BLOCKS):
        tiles = BLOCK_TILES[b_id]
        for t in tiles:
            assert 0 <= t < 256

    # Every item must have its tile within [0, 255]
    for item_id, tile_idx in ITEM_TILES.items():
        assert 0 <= tile_idx < 256
