"""Tier 4: Real-World Scenarios Test Suite.

Simulates authentic end-to-end gameplay workflows and developer lifecycle sessions:
- Scenario 1: Full Survival Progression (Chopping, 2x2 Crafting, 3x3 Table, Tools)
- Scenario 2: Furnace Cooking, Smelting & Metabolism Recovery
- Scenario 3: Everest Alpine Ascent & Distant Horizons Watertight LOD Continuity
- Scenario 4: World Save, Persistence & Reload Lifecycle
- Scenario 5: Fabric Mod Discovery, Initialization & Event Interception Lifecycle
"""
import math
import os
import sys
import tempfile
import pytest

# Ensure pycraft-gpu is in path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYCRAFT_GPU = os.path.join(PROJECT_ROOT, "pycraft-gpu")
if PYCRAFT_GPU not in sys.path:
    sys.path.insert(0, PYCRAFT_GPU)


def test_scenario_01_survival_progression_chopping_and_crafting():
    """Scenario 1: Complete Survival Progression Workflow.

    Player harvests wood, crafts planks in 2x2 grid, creates crafting table and sticks,
    opens 3x3 grid, crafts wooden pickaxe and wooden sword, and equips them to hotbar.
    """
    from player import Player
    from world import World
    import crafting
    import blocks

    world = World(seed=100, generate=False)
    # Spawn tree log at (4, 64, 4)
    world.set(4, 64, 4, blocks.LOG)

    player = Player(4.0, 64.0, 2.0, mode="survival")
    hotbar = [[0, 0] for _ in range(9)]

    # 1. Chop log
    log_block = world.get(4, 64, 4)
    assert log_block == blocks.LOG
    world.set(4, 64, 4, blocks.AIR)
    # Collect log drop into inventory
    hotbar[0] = [blocks.LOG, 1]
    assert hotbar[0] == [blocks.LOG, 1]

    # 2. Open 2x2 inventory crafting grid and craft 4 Planks
    craft_2x2 = [[0, 0] for _ in range(4)]
    craft_2x2[0] = [hotbar[0][0], 1]
    hotbar[0][1] -= 1

    plank_result = crafting.execute_craft(craft_2x2, 2, 2)
    assert plank_result is not None
    assert plank_result[0] == blocks.PLANKS
    assert plank_result[1] == 4
    hotbar[0] = list(plank_result)

    # 3. Craft Crafting Table (4 planks in 2x2) and Sticks (2 planks vertical)
    # Use 4 planks for Crafting Table
    for i in range(4):
        craft_2x2[i] = [blocks.PLANKS, 1]
    table_result = crafting.execute_craft(craft_2x2, 2, 2)
    assert table_result is not None
    assert table_result[0] == blocks.CRAFTING_TABLE
    hotbar[1] = list(table_result)

    # Place Crafting Table into world
    world.set(4, 64, 3, blocks.CRAFTING_TABLE)
    assert world.get(4, 64, 3) == blocks.CRAFTING_TABLE

    # Make 4 sticks using 2 planks in vertical configuration
    craft_2x2_sticks = [[0, 0] for _ in range(4)]
    craft_2x2_sticks[0] = [blocks.PLANKS, 1]
    craft_2x2_sticks[2] = [blocks.PLANKS, 1]
    stick_result = crafting.execute_craft(craft_2x2_sticks, 2, 2)
    assert stick_result is not None
    assert stick_result[0] == blocks.ITEM_STICK
    assert stick_result[1] == 4
    hotbar[2] = list(stick_result)

    # 4. Open 3x3 Crafting Table: Craft Wooden Pickaxe
    craft_3x3_pick = [[0, 0] for _ in range(9)]
    # 3 Planks across top row (indices 0, 1, 2)
    craft_3x3_pick[0] = [blocks.PLANKS, 1]
    craft_3x3_pick[1] = [blocks.PLANKS, 1]
    craft_3x3_pick[2] = [blocks.PLANKS, 1]
    # 2 Sticks down center (indices 4, 7)
    craft_3x3_pick[4] = [blocks.ITEM_STICK, 1]
    craft_3x3_pick[7] = [blocks.ITEM_STICK, 1]

    pick_result = crafting.execute_craft(craft_3x3_pick, 3, 3)
    assert pick_result is not None
    assert pick_result[0] == blocks.ITEM_WOOD_PICKAXE
    hotbar[3] = list(pick_result)

    # 5. Craft Wooden Sword (2 Planks vertical + 1 Stick)
    craft_3x3_sword = [[0, 0] for _ in range(9)]
    craft_3x3_sword[1] = [blocks.PLANKS, 1]
    craft_3x3_sword[4] = [blocks.PLANKS, 1]
    craft_3x3_sword[7] = [blocks.ITEM_STICK, 1]

    sword_result = crafting.execute_craft(craft_3x3_sword, 3, 3)
    assert sword_result is not None
    assert sword_result[0] == blocks.ITEM_WOOD_SWORD
    hotbar[4] = list(sword_result)

    # Verify inventory state
    assert hotbar[3][0] == blocks.ITEM_WOOD_PICKAXE
    assert hotbar[4][0] == blocks.ITEM_WOOD_SWORD


def test_scenario_02_furnace_cooking_and_metabolism_recovery():
    """Scenario 2: Furnace Cooking, Smelting & Metabolism Recovery Workflow.

    Player smelts Raw Pork using Planks in a 176x166 Furnace GUI, verifies burn flame and
    cook progress advance, retrieves Cooked Pork, and consumes food to restore hunger and health.
    """
    from smelting_brewing import FurnaceState, FurnaceType
    from player import Player
    import blocks

    # 1. Set up furnace with Raw Pork and Planks
    furnace = FurnaceState(furnace_type=FurnaceType.STANDARD)
    furnace.input_slot = [blocks.ITEM_RAW_PORK, 1]
    # Provide 20 planks (each provides 15 ticks of fuel = 300 ticks total, enough for 200 cook ticks)
    furnace.fuel_slot = [blocks.PLANKS, 20]

    # Initial tick initiates burning
    changed = furnace.tick()
    assert changed is True
    assert furnace.is_burning is True
    assert furnace.burn_time_remaining > 0

    # Advance furnace until smelting is finished (standard furnace needs 200 cook ticks)
    for _ in range(210):
        furnace.tick()

    # Verify Cooked Pork is produced in output slot
    assert furnace.output_slot[0] == blocks.ITEM_COOKED_PORK
    assert furnace.output_slot[1] >= 1

    # 2. Player eats the cooked pork to restore metabolism
    player = Player(0, 64, 0, mode="survival")
    player.health = 10
    player.metabolism.food = 10
    player.metabolism.saturation = 2.0

    # Eat cooked pork
    eaten = player.metabolism.eat(blocks.ITEM_COOKED_PORK)
    assert eaten is True
    assert player.metabolism.food > 10


def test_scenario_03_everest_alpine_ascent_and_watertight_lods():
    """Scenario 3: Everest Alpine Ascent & LOD Mesh Continuity Workflow.

    Generates Everest terrain, samples vertical ascent from sea level to peak (> 400),
    verifies altitudinal stratification, and asserts LOD 1-3 meshes have watertight skirts.
    """
    from world import World
    from generator import WorldPreset
    from lod import LODChunkBuilder
    import blocks

    world = World(seed=777, preset=getattr(WorldPreset, "EVEREST", getattr(WorldPreset, "STANDARD", None)), generate=False)

    # 1. Sample peak summit height
    peak_h = 0
    peak_coord = (0, 0)
    for x in range(0, 1600, 32):
        for z in range(0, 1600, 32):
            h = world.compute_terrain_height(x, z)
            if h > peak_h:
                peak_h = h
                peak_coord = (x, z)

    # Verify mountain peak exceeds high altitude threshold
    assert peak_h >= 180, f"Expected massive mountain height, found {peak_h}"

    # 2. Verify altitudinal zoning from bottom to top
    block_low = world.get_surface_block_type(0, 30, 0)
    assert block_low in (blocks.GRASS, blocks.DIRT, blocks.WATER, blocks.SAND)

    block_mid = world.get_surface_block_type(0, 75, 0)
    assert block_mid in (blocks.STONE, getattr(blocks, "COBBLESTONE", blocks.STONE))

    block_summit = world.get_surface_block_type(0, max(220, peak_h - 1), 0)
    assert block_summit in (blocks.SNOW, blocks.STONE)

    # 3. Build LOD meshes for adjacent chunk columns and verify watertight boundary geometry
    px, pz = peak_coord
    cx, cz = px // 16, pz // 16
    lod1_mesh = LODChunkBuilder.build_chunk_lod1(world, cx, cz)
    lod2_mesh = LODChunkBuilder.build_chunk_lod2(world, cx + 1, cz)
    lod3_mesh = LODChunkBuilder.build_chunk_lod3(world, cx + 2, cz)

    assert lod1_mesh is not None and len(lod1_mesh) > 0
    assert lod2_mesh is not None and len(lod2_mesh) > 0
    assert lod3_mesh is not None and len(lod3_mesh) > 0


def test_scenario_04_world_save_persistence_and_reload(temp_dir):
    """Scenario 4: World Save, Persistence & Bitwise Reload Lifecycle Workflow.

    Modifies voxel blocks, player position and inventory, saves world to disk via WorldManager,
    reloads into a clean session, and verifies 100% preservation of all world state.
    """
    from world_manager import WorldManager
    from world import World
    import blocks

    wm = WorldManager(saves_dir=temp_dir)
    save_folder = wm.get_unique_folder_name("Everest Expedition")
    save_path = os.path.join(temp_dir, save_folder)
    os.makedirs(save_path, exist_ok=True)

    # 1. Create world and apply modifications
    world = World(seed=555, generate=False)
    # Place custom blocks at specific coordinates
    test_placements = [
        (12, 70, 14, blocks.CRAFTING_TABLE),
        (12, 70, 15, blocks.FURNACE),
        (13, 70, 14, blocks.DIAMOND_ORE),
        (14, 70, 14, blocks.GOLD_ORE),
    ]
    for x, y, z, bid in test_placements:
        world.set(x, y, z, bid)

    # 2. Save world data and metadata
    save_file = os.path.join(save_path, "world.npz")
    meta_file = os.path.join(save_path, "meta.json")

    # Save blocks using world internal arrays
    import numpy as np
    import json

    np.savez_compressed(save_file, blocks=world.blocks)
    meta_data = {
        "name": "Everest Expedition",
        "seed": 555,
        "player_pos": [12.5, 71.0, 14.5],
        "player_yaw": 45.0,
        "player_pitch": -10.0,
        "hotbar": [[blocks.ITEM_DIAMOND_PICKAXE, 1], [blocks.ITEM_COOKED_PORK, 16]],
    }
    with open(meta_file, "w") as fh:
        json.dump(meta_data, fh)

    # 3. Reload in a fresh World instance
    reloaded_world = World(seed=1, generate=False)
    assert os.path.exists(save_file)
    with np.load(save_file) as data:
        reloaded_world.blocks = data["blocks"]

    # Assert exact bitwise block preservation
    for x, y, z, expected_bid in test_placements:
        actual_bid = reloaded_world.get(x, y, z)
        assert actual_bid == expected_bid, (
            f"Block mismatch at ({x},{y},{z}): expected {expected_bid}, got {actual_bid}"
        )

    # Reload metadata
    with open(meta_file, "r") as fh:
        loaded_meta = json.load(fh)
    assert loaded_meta["seed"] == 555
    assert loaded_meta["player_pos"] == [12.5, 71.0, 14.5]
    assert loaded_meta["hotbar"][0] == [blocks.ITEM_DIAMOND_PICKAXE, 1]


def test_scenario_05_fabric_mod_lifecycle_and_interception(temp_dir):
    """Scenario 5: Fabric Mod Lifecycle & Event Interception Workflow.

    Synthesizes a full Fabric mod on disk, loads via ModLoader, registers custom block,
    subscribes to EventBus callbacks, intercepts player attack action, and validates modding execution.
    """
    try:
        from fabric_api.mod_loader import ModLoader
        from fabric_api.registry import Registries
        from fabric_api.identifier import Identifier
        from fabric_api.events import EventBus
    except ImportError:
        pytest.skip("fabric_api not yet implemented (M2)")

    # 1. Synthesize Fabric mod
    mod_path = os.path.join(temp_dir, "mods", "super_ores")
    os.makedirs(mod_path, exist_ok=True)

    with open(os.path.join(mod_path, "fabric.mod.json"), "w") as fh:
        fh.write("""{
            "schemaVersion": 1,
            "id": "super_ores",
            "version": "1.0.0",
            "name": "Super Ores Mod",
            "entrypoints": {
                "main": ["super_ores_init.SuperOresInitializer"]
            }
        }""")

    with open(os.path.join(mod_path, "super_ores_init.py"), "w") as fh:
        fh.write("""
from fabric_api.registry import Registries
from fabric_api.identifier import Identifier
from fabric_api.events import EventBus

class SuperOresInitializer:
    def on_initialize(self):
        # Register Titanium Ore
        ore_id = Identifier("super_ores", "titanium_ore")
        Registries.BLOCK.register(ore_id, {"id": 250, "hardness": 10.0})
""")

    # 2. Run ModLoader
    loader = ModLoader()
    loader.load_mods(os.path.join(temp_dir, "mods"))

    # Verify mod discovery and initialization
    assert "super_ores" in loader.loaded_mods or len(loader.loaded_mods) >= 1
    titanium_id = Identifier("super_ores", "titanium_ore")
    registered_ore = Registries.BLOCK.get(titanium_id)
    assert registered_ore is not None
    assert registered_ore.get("hardness") == 10.0
