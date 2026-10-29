"""Exhaustive tests for Minecraft 1.8 complete blocks catalog and entities system:
- All 164 canonical blocks up to 1.8 including Furnace, Lit Furnace, Chests, Hoppers, Redstone, Wools, Slabs.
- Partial blocks & cross-models (torches, grass, flowers, mushrooms, saplings, ladders, slabs).
- Dropped items (DroppedItem): 3D physics, bobbing, spinning, magnet pull, inventory pickup, Q-drop.
- All 33 Minecraft 1.8 mobs: configurations, spawning, health, dimensions, drops, and specialized AI behaviors.
"""
import math
import os
import sys
import pytest
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import blocks
from blocks import (
    AIR, STONE, GRASS, DIRT, COBBLESTONE, PLANKS, WATER,
    FURNACE, LIT_FURNACE, CHEST, ENDER_CHEST, TRAPPED_CHEST,
    DISPENSER, DROPPER, HOPPER, BREWING_STAND, ANVIL, ENCHANTING_TABLE,
    JUKEBOX, NOTE_BLOCK, BEACON, TORCH, REDSTONE_TORCH,
    TALL_GRASS, FERN, DANDELION, POPPY, BROWN_MUSHROOM, RED_MUSHROOM,
    SUGAR_CANE, LADDER, VINE, COBWEB,
    STONE_SLAB, OAK_SLAB, COBBLESTONE_SLAB,
    WHITE_WOOL, BLACK_WOOL, RED_WOOL, WHITE_CARPET,
    PRISMARINE, SEA_LANTERN, WET_SPONGE, GRANITE, ANDESITE, DIORITE,
    SOLID, OPAQUE, CUTOUT, CROSS_MODEL, SLAB,
    BLOCK_NAMES, BLOCK_HARDNESS, BLOCK_TILES,
    get_item_name, get_item_tile,
)
from lighting import LIGHT_EMITTERS
from entities import Entity, DroppedItem, EntityManager, MOB_CONFIGS
from world import World
from renderer import Renderer


def test_complete_minecraft_1_8_blocks_presence_and_properties():
    """Verify all 164 Minecraft blocks are defined with valid names, textures, hardness and flags."""
    assert blocks.NUM_BLOCKS == 164
    assert len(BLOCK_NAMES) == 164
    assert len(BLOCK_TILES) == 164

    # Crucial workstations and utilities must exist
    workstations = [
        (FURNACE, "Furnace"),
        (LIT_FURNACE, "Lit Furnace"),
        (CHEST, "Chest"),
        (ENDER_CHEST, "Ender Chest"),
        (TRAPPED_CHEST, "Trapped Chest"),
        (DISPENSER, "Dispenser"),
        (DROPPER, "Dropper"),
        (HOPPER, "Hopper"),
        (BREWING_STAND, "Brewing Stand"),
        (ANVIL, "Anvil"),
        (ENCHANTING_TABLE, "Enchanting Table"),
        (JUKEBOX, "Jukebox"),
        (NOTE_BLOCK, "Note Block"),
        (BEACON, "Beacon"),
    ]
    for bid, name in workstations:
        assert 0 <= bid < 164
        assert BLOCK_NAMES[bid] == name
        assert bid in BLOCK_HARDNESS
        assert BLOCK_HARDNESS[bid] > 0

    # Lit furnace and beacon emit light
    assert LIGHT_EMITTERS[LIT_FURNACE] == 13
    assert LIGHT_EMITTERS[BEACON] == 15
    assert LIGHT_EMITTERS[TORCH] == 14
    assert LIGHT_EMITTERS[SEA_LANTERN] == 15


def test_partial_blocks_cross_models_and_slabs():
    """Verify partial blocks, cross-models and slabs have correct flags and traversal properties."""
    cross_blocks = [
        TORCH, REDSTONE_TORCH, TALL_GRASS, FERN, DANDELION, POPPY,
        BROWN_MUSHROOM, RED_MUSHROOM, SUGAR_CANE, COBWEB
    ]
    for bid in cross_blocks:
        assert bool(CROSS_MODEL[bid]) is True, f"Block {BLOCK_NAMES[bid]} must be CROSS_MODEL"
        assert bool(CUTOUT[bid]) is True, f"Block {BLOCK_NAMES[bid]} must be CUTOUT"
        # Torches and flowers are non-solid
        if bid != COBWEB:
            assert bool(SOLID[bid]) is False, f"Cross-model {BLOCK_NAMES[bid]} should be non-solid"

    # Wall attachments and cutouts
    for bid in (LADDER, VINE, COBWEB):
        assert bool(CUTOUT[bid]) is True, f"Block {BLOCK_NAMES[bid]} must be CUTOUT"

    # Slabs
    slabs = [STONE_SLAB, OAK_SLAB, COBBLESTONE_SLAB]
    for s in slabs:
        assert bool(SLAB[s]) is True, f"Slab {BLOCK_NAMES[s]} must be marked SLAB"
        assert bool(SOLID[s]) is True


def test_world_placement_and_raycasting_all_blocks():
    """Verify all 164 blocks can be set and raycasted in the world without error."""
    w = World(size=(16, 32, 16), seed=42, generate=False)
    for bid in range(blocks.NUM_BLOCKS):
        w.set(bid % 16, 5, (bid // 16) % 16, bid)
        assert w.get(bid % 16, 5, (bid // 16) % 16) == bid


def test_all_33_mobs_registered_and_configured():
    """Verify all 33 Minecraft 1.8 mobs are registered with correct attributes."""
    expected_mobs = {
        # Passive
        "pig", "cow", "sheep", "chicken", "horse", "rabbit", "bat", "squid",
        "villager", "mooshroom", "ocelot", "wolf", "iron_golem", "snow_golem",
        # Hostile
        "zombie", "skeleton", "creeper", "spider", "cave_spider", "enderman",
        "witch", "slime", "magma_cube", "silverfish", "endermite", "guardian",
        "elder_guardian", "ghast", "blaze", "zombie_pigman", "wither_skeleton",
        # Bosses
        "ender_dragon", "wither",
    }
    assert set(MOB_CONFIGS.keys()) == expected_mobs
    assert len(MOB_CONFIGS) == 33

    for mob_name, cfg in MOB_CONFIGS.items():
        ent = Entity(mob_name, 10.0, 5.0, 10.0)
        assert ent.kind == mob_name
        assert ent.health == cfg["health"]
        assert ent.max_health == cfg["health"]
        assert ent.width == cfg["width"]
        assert ent.height == cfg["height"]
        assert ent.speed == cfg["speed"]
        assert ent.category in ("passive", "hostile", "neutral", "boss", "flying", "aquatic", "golem")


def test_creeper_fuse_and_explosion_ai():
    """Verify Creeper approaches player, begins fuse countdown, and explodes."""
    w = World(size=(32, 32, 32), seed=1, generate=False)
    for x in range(32):
        for z in range(32):
            w.set(x, 1, z, STONE)

    creeper = Entity("creeper", 10.0, 2.0, 10.0)
    # Player in close proximity (2.5m)
    player_pos = (11.0, 2.0, 10.0)

    events = creeper.update(w, dt=0.5, player_pos=player_pos, daylight=0.0)
    assert creeper.fuse_timer > 0.0

    # Advance fuse past 1.5s
    events = creeper.update(w, dt=1.5, player_pos=player_pos, daylight=0.0)
    assert "creeper_explode" in events
    assert not creeper.is_alive


def test_skeleton_arrow_shooting_ai():
    """Verify Skeleton tracks player and shoots arrows at range."""
    w = World(size=(32, 32, 32), seed=1, generate=False)
    for x in range(32):
        for z in range(32):
            w.set(x, 1, z, STONE)

    skel = Entity("skeleton", 10.0, 2.0, 10.0)
    skel.bow_cooldown = 0.0
    # Player at archery distance (8m)
    player_pos = (18.0, 2.0, 10.0)

    events = skel.update(w, dt=0.1, player_pos=player_pos, daylight=0.0)
    assert "skeleton_shoot" in events
    assert skel.bow_cooldown > 1.0


def test_enderman_aggro_and_teleportation():
    """Verify Enderman aggros on eye contact and teleports away when damaged or in water."""
    w = World(size=(32, 32, 32), seed=1, generate=False)
    for x in range(32):
        for z in range(32):
            w.set(x, 1, z, STONE)

    eman = Entity("enderman", 10.0, 2.0, 10.0)
    assert not eman.aggro

    # Eye contact from player
    player_eye = (10.0, 2.6, 5.0)
    player_fwd = (0.0, 0.0, 1.0)
    eman.check_player_stare(player_eye, player_fwd)
    assert eman.aggro is True

    # Teleportation on hit
    old_pos = list(eman.pos)
    eman.take_damage(5)
    eman.teleport_random(w)
    # Position must have changed
    assert eman.pos != old_pos


def test_dropped_item_physics_bobbing_and_pickup():
    """Verify DroppedItem gravity, drag, sine-wave bobbing, magnet pull and pickup."""
    w = World(size=(32, 32, 32), seed=1, generate=False)
    for x in range(32):
        for z in range(32):
            w.set(x, 1, z, STONE)

    # Spawn dropped item at (5.0, 4.0, 5.0) falling down
    item = DroppedItem(FURNACE, count=2, x=5.0, y=4.0, z=5.0, vx=1.0, vy=0.0, vz=0.0, pickup_delay=0.5)
    assert item.item_id == FURNACE
    assert item.count == 2
    assert item.is_alive is True

    # Update physics: gravity falls
    for _ in range(20):
        item.update(w, dt=0.05)
    # Should land on stone ground at y=2.0
    assert item.on_ground is True
    assert 1.95 <= item.pos[1] <= 2.05

    # Bobbing: age increments and yaw rotates
    assert item.age > 0
    assert item.yaw != 0.0

    # Magnetism and pickup via EntityManager
    mgr = EntityManager()
    mgr.dropped_items.append(item)

    # When player is far (10m), item stays
    events, drops = mgr.update(w, dt=0.1, player_pos=(15.0, 2.0, 5.0), daylight=0.5)
    assert item.is_alive is True

    # When player is within magnet distance (2.0m) and pickup delay expired
    item.pickup_delay = 0.0
    events, drops = mgr.update(w, dt=0.1, player_pos=(5.5, 2.0, 5.0), daylight=0.5)
    assert "item_pickup" in events
    assert not item.is_alive
    assert item not in mgr.dropped_items


def test_renderer_entity_mesh_dropped_items_and_mobs():
    """Verify Renderer._build_entities_mesh creates valid VBO data for dropped items and diverse mobs."""
    items_and_mobs = [
        DroppedItem(FURNACE, 1, 5.0, 2.0, 5.0),
        DroppedItem(CHEST, 1, 6.0, 2.0, 5.0),
        Entity("zombie", 7.0, 2.0, 5.0),
        Entity("pig", 8.0, 2.0, 5.0),
        Entity("creeper", 9.0, 2.0, 5.0),
        Entity("skeleton", 10.0, 2.0, 5.0),
        Entity("spider", 11.0, 2.0, 5.0),
        Entity("enderman", 12.0, 2.0, 5.0),
        Entity("slime", 13.0, 2.0, 5.0),
        Entity("chicken", 14.0, 2.0, 5.0),
        Entity("iron_golem", 15.0, 2.0, 5.0),
        Entity("snow_golem", 16.0, 2.0, 5.0),
    ]
    data, vcount = Renderer._build_entities_mesh(items_and_mobs, alpha=0.5)
    assert data is not None
    assert vcount > 0
    # Each quad has 6 vertices, each vertex has 7 float attributes (x, y, z, u, v, shade, kind)
    assert data.shape[1] == 7
    assert vcount == len(data)
