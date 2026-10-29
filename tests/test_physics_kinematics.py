"""Unit tests for the Swept AABB Physics Engine, Euler kinematics, and 3D DDA Raycasting."""
import math
import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from physics import (
    SweptAABBPhysics, DDARaycast, aabb_intersects,
    GRAVITY_PER_TICK, PASSIVE_DRAG_Y, TERMINAL_VELOCITY_Y,
    SLIPPERINESS_STANDARD, SLIPPERINESS_ICE, SLIPPERINESS_SLIME, SLIPPERINESS_AIR,
    REACH_MINE, REACH_PLACE, get_block_slipperiness,
)
from blocks import AIR, STONE, ICE, SLIME, WATER


class MockWorld:
    def __init__(self, solids=None):
        self.solids = set(solids or [])
        self.blocks = {}
        for s in self.solids:
            self.blocks[s] = STONE

    def is_solid(self, x, y, z):
        return (x, y, z) in self.solids

    def get(self, x, y, z):
        return self.blocks.get((x, y, z), AIR)

    def set(self, x, y, z, block):
        self.blocks[(x, y, z)] = block
        if block != AIR:
            self.solids.add((x, y, z))
        else:
            self.solids.discard((x, y, z))


def test_slipperiness_factors():
    assert get_block_slipperiness(STONE) == SLIPPERINESS_STANDARD
    assert get_block_slipperiness(ICE) == SLIPPERINESS_ICE
    assert get_block_slipperiness(SLIME) == SLIPPERINESS_SLIME
    assert get_block_slipperiness(AIR) == SLIPPERINESS_AIR


def test_vertical_gravity_and_terminal_velocity():
    # 1 tick of gravity from 0
    v1 = SweptAABBPhysics.step_vertical_kinematics(0.0)
    expected_v1 = -GRAVITY_PER_TICK * PASSIVE_DRAG_Y  # -0.08 * 0.98 = -0.0784
    assert math.isclose(v1, expected_v1, rel_tol=1e-5)

    # Free-fall towards asymptotic terminal velocity
    v = 0.0
    for _ in range(500):
        v = SweptAABBPhysics.step_vertical_kinematics(v)
    assert math.isclose(v, TERMINAL_VELOCITY_Y, rel_tol=1e-4)

    # Clamped when exceeding terminal velocity
    clamped = SweptAABBPhysics.step_vertical_kinematics(-10.0)
    assert math.isclose(clamped, TERMINAL_VELOCITY_Y, abs_tol=1e-5)


def test_floor_collision_and_ground_detection():
    # Solid block at (5, 0, 5) -> top is y = 1.0
    world = MockWorld([(5, 0, 5)])
    pos = [5.5, 1.2, 5.5]
    vel = [0.0, -0.4, 0.0]  # moving downward into the block

    on_ground, against_wall, slip = SweptAABBPhysics.resolve_movement(
        world, pos, vel, half_width=0.3, height=1.8
    )
    assert on_ground is True
    assert math.isclose(pos[1], 1.0, abs_tol=1e-5)
    assert vel[1] == 0.0
    assert slip == SLIPPERINESS_STANDARD


def test_auto_step_over_half_block():
    # Floor at y=0, step obstacle of 1m at (6, 1, 5)
    # Player at (5.5, 1.0, 5.5), moves toward +X (+0.4)
    # The obstacle is a solid block at (6, 1, 5).
    world = MockWorld([
        (5, 0, 5), (6, 0, 5),  # Floor
        (6, 1, 5),             # Step block
    ])
    pos = [5.5, 1.0, 5.5]
    vel = [0.4, 0.0, 0.0]  # Walking horizontally into the step block

    on_ground, against_wall, _ = SweptAABBPhysics.resolve_movement(
        world, pos, vel, half_width=0.3, height=1.8, step_height=0.60
    )
    # Since step block at (6,1,5) has height 1.0 > 0.6m, auto-step cannot clear a full 1m block
    assert against_wall is True
    assert pos[0] < 5.8  # Blocked

    # When step_height is 1.1m (enough for a full 1m block), it steps up and moves forward:
    pos_step = [5.5, 1.0, 5.5]
    vel_step = [0.4, 0.0, 0.0]
    on_ground, against_wall, _ = SweptAABBPhysics.resolve_movement(
        world, pos_step, vel_step, half_width=0.3, height=1.8, step_height=1.1
    )
    assert on_ground is True
    assert math.isclose(pos_step[1], 2.0, abs_tol=1e-5)
    assert pos_step[0] > 5.5


def test_tangent_wall_sliding():
    # Wall at x = 6 (blocks from x=6, y=1..2, z=0..10)
    world = MockWorld([(6, 1, z) for z in range(10)])
    # Player at x=5.6, walking diagonally forward (+X) and sideways (+Z)
    pos = [5.6, 1.0, 5.0]
    vel = [0.2, 0.0, 0.3]

    on_ground, against_wall, _ = SweptAABBPhysics.resolve_movement(
        world, pos, vel, half_width=0.3, height=1.8
    )
    # X motion is stopped by the wall, but Z motion proceeds freely!
    assert against_wall is True
    assert math.isclose(pos[0], 6.0 - 0.3 - 1e-5, abs_tol=1e-4)
    assert math.isclose(pos[2], 5.3, abs_tol=1e-5)
    assert vel[0] == 0.0  # Stopped along normal
    assert vel[2] == 0.3  # Preserved along tangent


def test_dda_raycast_mining_and_placement():
    world = MockWorld([(10, 5, 5)])
    origin = (7.0, 5.5, 5.5)  # 3m away from block (10, 5, 5)
    direction = (1.0, 0.0, 0.0)

    # Within mining reach (4.5m)
    res = DDARaycast.raycast(world, origin, direction, max_reach=REACH_MINE)
    assert res is not None
    target_pos, place_pos, normal = res
    assert target_pos == (10, 5, 5)
    assert place_pos == (9, 5, 5)
    assert normal == (-1, 0, 0)

    # Exceeding reach
    far_origin = (2.0, 5.5, 5.5)  # 8m away
    res_far = DDARaycast.raycast(world, far_origin, direction, max_reach=REACH_MINE)
    assert res_far is None


def test_placement_validation_against_entity_aabb():
    world = MockWorld([(10, 5, 5)])
    place_pos = (9, 5, 5)

    # Entity sitting right at (9.2, 5.0, 5.2), width 0.6, height 1.8
    entity_aabb = (9.2 - 0.3, 5.0, 5.2 - 0.3, 9.2 + 0.3, 5.0 + 1.8, 5.2 + 0.3)
    assert not DDARaycast.can_place_block(world, place_pos, [entity_aabb])

    # Entity positioned safely away at (15.0, 5.0, 15.0)
    safe_entity_aabb = (15.0 - 0.3, 5.0, 15.0 - 0.3, 15.0 + 0.3, 5.0 + 1.8, 15.0 + 0.3)
    assert DDARaycast.can_place_block(world, place_pos, [safe_entity_aabb])
