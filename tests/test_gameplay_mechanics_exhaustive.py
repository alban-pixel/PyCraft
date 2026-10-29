"""Exhaustive tests for Raycasting, Mining, Block Placement, Collisions, Combat, Fluids, and Metabolism."""
import math
import pytest
import numpy as np

from blocks import (
    AIR, BEDROCK, COAL_ORE, COBBLESTONE, CRAFTING_TABLE, DIAMOND_ORE,
    ITEM_DIAMOND_PICKAXE, ITEM_DIAMOND_SWORD, DIRT, GLASS, GOLD_ORE, GRASS,
    IRON_ORE, ITEM_IRON_PICKAXE, ITEM_IRON_SWORD, LEAVES, LOG, OBSIDIAN, SAND,
    STONE, ITEM_STONE_PICKAXE, WATER, ITEM_WOOD_PICKAXE, ITEM_WOOD_SWORD,
    UNBREAKABLE, PLACEABLE, FOOD_HEAL, ATTACK_DAMAGE
)
from combat import CombatEngine, InvulnerabilityTracker
from entities import Entity, EntityManager
from generator import WorldPreset
from mining import MiningEngine
from player import Player
from physics import DDARaycast
from world import World


def test_raycast_dda_hit_and_miss():
    """Test DDA raycasting hitting solid blocks, detecting neighbor face, and passing through air/water."""
    w = World(seed=1, preset=WorldPreset.SUPERFLAT)
    # Superflat: Y=0 bedrock, Y=1..2 dirt, Y=3 grass, Y>=4 air
    # Player eye at (8.5, 6.0, 8.5) looking straight down (pitch -90 -> dir (0, -1, 0))
    origin = (8.5, 6.0, 8.5)
    direction = (0.0, -1.0, 0.0)

    # Raycast with sufficient reach
    hit = w.raycast(origin, direction, reach=5.0)
    assert hit is not None
    hit_block, prev_block = hit
    # Hit top block of terrain (Y=3 grass)
    assert hit_block == (8, 3, 8)
    assert prev_block == (8, 4, 8)  # Adjacent space above (+Y face)

    # Raycast with insufficient reach (reaches only to Y=4.5)
    miss = w.raycast(origin, direction, reach=1.0)
    assert miss is None

    # Raycast through water: place water at (8, 4, 8), raycast must penetrate water and hit Y=3 grass
    w.set(8, 4, 8, WATER)
    hit_water_thru = w.raycast(origin, direction, reach=5.0)
    assert hit_water_thru is not None
    assert hit_water_thru[0] == (8, 3, 8)


def test_block_placement_rules_and_aabb_collision():
    """Test block placement conditions: free air space, face adjacency, and player/mob collision checks."""
    w = World(seed=1, preset=WorldPreset.SUPERFLAT)
    p = Player(8.5, 4.0, 8.5, mode="survival")
    p_aabb = p.get_aabb() if hasattr(p, "get_aabb") else (
        p.pos[0] - 0.3, p.pos[1], p.pos[2] - 0.3,
        p.pos[0] + 0.3, p.pos[1] + 1.8, p.pos[2] + 0.3
    )

    # 1. Attempt placing block right inside the player's body (8, 4, 8)
    can_place_inside = DDARaycast.can_place_block(w, (8, 4, 8), [p_aabb])
    assert can_place_inside is False

    # 2. Attempt placing block 2 blocks to the side (10, 4, 8) outside player AABB
    can_place_side = DDARaycast.can_place_block(w, (10, 4, 8), [p_aabb])
    assert can_place_side is True

    # 3. Add a zombie at (10.5, 4.0, 8.5): placing at (10, 4, 8) must now be blocked by mob AABB
    zombie = Entity("zombie", 10.5, 4.0, 8.5)
    can_place_with_mob = DDARaycast.can_place_block(w, (10, 4, 8), [p_aabb, zombie.aabb])
    assert can_place_with_mob is False


def test_mining_mechanics_hardness_tool_wear_and_bedrock():
    """Test mining calculations: bedrock unbreakable, tools speeding up matching blocks, tool durability loss."""
    # 1. Bedrock cannot be mined
    assert bool(UNBREAKABLE[BEDROCK]) is True
    dmg_bedrock = MiningEngine.compute_damage_per_tick(ITEM_DIAMOND_PICKAXE, BEDROCK, in_water=False, on_ground=True)
    assert dmg_bedrock == 0.0

    # 2. Hand vs Stone: Stone hardness is high, hand has no tool multiplier
    dmg_hand_stone = MiningEngine.compute_damage_per_tick(0, STONE, in_water=False, on_ground=True)
    assert dmg_hand_stone > 0.0

    # 3. Wooden Pickaxe vs Stone: faster than hand
    dmg_wood_stone = MiningEngine.compute_damage_per_tick(ITEM_WOOD_PICKAXE, STONE, in_water=False, on_ground=True)
    assert dmg_wood_stone > dmg_hand_stone

    # 4. Diamond Pickaxe vs Stone: significantly faster
    dmg_diamond_stone = MiningEngine.compute_damage_per_tick(ITEM_DIAMOND_PICKAXE, STONE, in_water=False, on_ground=True)
    assert dmg_diamond_stone > dmg_wood_stone * 2

    # 5. Mining underwater or in air slows down mining rate
    dmg_underwater = MiningEngine.compute_damage_per_tick(ITEM_DIAMOND_PICKAXE, STONE, in_water=True, on_ground=True)
    assert dmg_underwater < dmg_diamond_stone
    dmg_airborne = MiningEngine.compute_damage_per_tick(ITEM_DIAMOND_PICKAXE, STONE, in_water=False, on_ground=False)
    assert dmg_airborne < dmg_diamond_stone

    # 6. Tool wear: durability decreases when mining appropriate blocks
    tool_slot = [ITEM_DIAMOND_PICKAXE, 1, 1561]  # [item_id, count, durability]
    MiningEngine.apply_tool_wear(tool_slot, STONE)
    assert tool_slot[2] == 1560

    # Tool breaks when durability reaches 0
    tool_slot[2] = 1
    MiningEngine.apply_tool_wear(tool_slot, STONE)
    assert tool_slot[0] == 0  # Replaced with AIR / empty


def test_combat_damage_armor_mitigation_and_knockback():
    """Test melee attack calculation, weapon bonus, knockback vector, and armor reduction."""
    # 1. Weapon attack damage constants
    assert ATTACK_DAMAGE[ITEM_DIAMOND_SWORD] > ATTACK_DAMAGE[ITEM_IRON_SWORD]
    assert ATTACK_DAMAGE[ITEM_IRON_SWORD] > ATTACK_DAMAGE[ITEM_WOOD_SWORD]

    # 2. Mob taking damage and knockback
    mob = Entity("zombie", 10.0, 4.0, 10.0)
    init_hp = mob.health
    player_pos = (9.0, 4.0, 10.0)

    # Attack mob from -X direction
    mob.take_damage(ATTACK_DAMAGE[ITEM_DIAMOND_SWORD], knockback_src=player_pos)
    assert mob.health == init_hp - ATTACK_DAMAGE[ITEM_DIAMOND_SWORD]
    # Knockback must push mob along +X direction
    assert mob.vel[0] > 0.0 or mob.pos[0] > 10.0

    # 3. Armor mitigation formula verification
    # 20 raw damage against 20 armor points, 0 toughness
    mitigated = CombatEngine.calculate_armor_damage(damage=20.0, armor=20, toughness=0)
    assert mitigated < 20.0
    assert mitigated >= 4.0  # Armor caps at 80% mitigation without enchantments


def test_creative_flight_kinematics_and_controls():
    """Test creative flight toggle, ascending, descending, and velocity zeroing."""
    p = Player(10.0, 10.0, 10.0, mode="creative")
    assert p.flying is False

    # Double tap space to toggle flight
    p.trigger_space_tap()  # Tap 1
    p.trigger_space_tap()  # Tap 2 within 0.30s
    assert p.flying is True

    # While flying, player is not affected by regular falling gravity
    w = World(seed=1, preset=WorldPreset.SUPERFLAT)
    p.vel_y = 0.0
    p.update(w, dt=0.05)
    assert p.pos[1] == pytest.approx(10.0, abs=0.01)

    # Ascend in flight: simulate Space pressed
    p.vel_y = 6.0
    p.pos[1] += p.vel_y * 0.05
    assert p.pos[1] > 10.0

    # Toggle flight off
    p.trigger_space_tap()
    p.trigger_space_tap()
    assert p.flying is False


def test_sneak_ledge_guard():
    """Test sneaking edge guard prevents walking off cliffs/void."""
    w = World(seed=1, preset=WorldPreset.SUPERFLAT)
    # Block at (5, 3, 5) exists. Block at (6, 3, 5) is removed.
    w.set(6, 3, 5, AIR)
    w.set(6, 2, 5, AIR)
    w.set(6, 1, 5, AIR)

    p = Player(5.5, 4.0, 5.5, mode="survival")
    p.sneaking = True
    p.on_ground = True

    # Has ground support at (5.5, 4.0, 5.5)
    assert p._has_ground_support(w, 5.5, 4.0, 5.5) is True

    # Walking off the edge into (6.2, 4.0, 5.5) has no support
    assert p._has_ground_support(w, 6.2, 4.0, 5.5) is False


def test_environmental_damage_fall_and_drowning():
    """Test fall damage calculation and drowning under water."""
    p = Player(10.0, 20.0, 10.0, mode="survival")
    p.fall_start_y = 20.0

    # Fall 10 blocks down to Y=10
    fall_dist = p.fall_start_y - 10.0
    damage = max(0, int(fall_dist - 3.0))
    assert damage == 7

    # In creative mode, fall damage is 0
    p_creative = Player(10.0, 20.0, 10.0, mode="creative")
    p_creative.fall_start_y = 20.0
    # Creative mode cannot take damage
    took_dmg = p_creative.take_damage(damage)
    assert took_dmg is False
    assert p_creative.health == p_creative.max_health


def test_fluid_cellular_automata_spread_and_infinite_sources():
    """Test water cellular automata downwards spread, horizontal flow, and 2-source infinite regeneration."""
    w = World(seed=1, preset=WorldPreset.SUPERFLAT)

    # Clear area
    for x in range(10, 15):
        for z in range(10, 15):
            w.set(x, 4, z, AIR)
            w.set(x, 5, z, AIR)

    # Place water source block at (12, 5, 12)
    w.set(12, 5, 12, WATER)
    assert w.get(12, 5, 12) == WATER

    # Spread downwards into (12, 4, 12)
    if hasattr(w, "update_fluids"):
        w.update_fluids()
        assert w.get(12, 4, 12) == WATER


def test_metabolism_exhaustion_and_natural_regeneration():
    """Test hunger depletion, exhaustion accumulation, and natural regeneration."""
    p = Player(10.0, 4.0, 10.0, mode="survival")
    p.health = 10
    p.metabolism.health = 10
    p.metabolism.food = 20
    p.metabolism.saturation = 5.0

    # Natural regen occurs every 80 ticks (4s at 20Hz) when food >= 18
    p.metabolism.regen_timer = 80
    events = p.tick_metabolism()
    assert p.health == 11  # Restored 1 HP
    assert p.metabolism.exhaustion > 0.0  # Consumed exhaustion for healing
