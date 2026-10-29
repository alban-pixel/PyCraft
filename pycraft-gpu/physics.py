"""Voxel physics engine: Swept AABB collision, modified Euler kinematics, and 3D DDA raycasting.

Implements the deterministic specifications:
- Decoupled axis resolution: Y first (ground/ceiling lock), then X and Z for tangent wall sliding.
- Automatic stepping for vertical obstacles <= 0.6 m without jump impulse.
- Slipperiness St: standard 0.60, ice 0.98, blue ice 0.989, slime 0.80 (elastic bounce), air 1.00.
- Vertical gravity: -0.08 blocks/tick with 0.98 drag, terminal velocity -3.92 blocks/tick.
- 3D DDA Raycasting (Amanatides & Woo) with extraction (4.5m) and placement (5.0m) reaches.
- Placement non-intersection validation against entity AABBs.
"""
import math
from typing import List, Optional, Tuple

from blocks import (
    AIR, ICE, SLIME, WATER,
)

# Kinematic constants (per-tick, at 20 Hz)
GRAVITY_PER_TICK = 0.08  # -32 m/s^2 equivalent
PASSIVE_DRAG_Y = 0.98
TERMINAL_VELOCITY_Y = -3.92  # -78.4 m/s equivalent
HORIZONTAL_MOMENTUM_RETENTION = 0.91

# Slipperiness constants
SLIPPERINESS_STANDARD = 0.60
SLIPPERINESS_ICE = 0.98
SLIPPERINESS_BLUE_ICE = 0.989
SLIPPERINESS_SLIME = 0.80
SLIPPERINESS_AIR = 1.00

# Kinematics reaches & steps
STEP_HEIGHT_MAX = 0.60  # Maximum auto-step height in meters
REACH_MINE = 4.5  # meters
REACH_PLACE = 5.0  # meters
EPSILON = 1e-5


def get_block_slipperiness(block_id: int) -> float:
    """Return the physical slipperiness factor S_t for the given block ID."""
    if block_id == ICE:
        return SLIPPERINESS_ICE
    if block_id == SLIME:
        return SLIPPERINESS_SLIME
    if block_id == AIR:
        return SLIPPERINESS_AIR
    return SLIPPERINESS_STANDARD


def aabb_intersects(box1: Tuple[float, float, float, float, float, float],
                    box2: Tuple[float, float, float, float, float, float]) -> bool:
    """True if two 3D AABBs (min_x, min_y, min_z, max_x, max_y, max_z) overlap."""
    return (box1[0] < box2[3] and box1[3] > box2[0] and
            box1[1] < box2[4] and box1[4] > box2[1] and
            box1[2] < box2[5] and box1[5] > box2[2])


class SweptAABBPhysics:
    """Physical controller handling swept AABB collisions, auto-step, and Euler updates."""

    @staticmethod
    def step_vertical_kinematics(vel_y: float, in_water: bool = False) -> float:
        """Apply gravity and passive drag per tick.

        V_{y, t} = (V_{y, t-1} - 0.08) * 0.98
        Clamped to terminal velocity -3.92 blocks/tick.
        """
        if in_water:
            # Water buoyancy / terminal sink speed (-0.15 blocks/tick = 3 m/s)
            vel_y = max(vel_y - 0.04, -0.15)
        else:
            vel_y = (vel_y - GRAVITY_PER_TICK) * PASSIVE_DRAG_Y
            vel_y = max(vel_y, TERMINAL_VELOCITY_Y)
        return vel_y

    @staticmethod
    def step_horizontal_kinematics(vel_h: Tuple[float, float],
                                   accel: Tuple[float, float],
                                   slipperiness: float) -> Tuple[float, float]:
        """Apply modified Euler horizontal momentum:

        V_{H, t} = (V_{H, t-1} * S_t * 0.91) + A_input
        """
        decay = slipperiness * HORIZONTAL_MOMENTUM_RETENTION
        vx = vel_h[0] * decay + accel[0]
        vz = vel_h[1] * decay + accel[1]
        return vx, vz

    @classmethod
    def resolve_movement(cls,
                         world,
                         pos: List[float],
                         vel: List[float],
                         half_width: float,
                         height: float,
                         step_height: float = STEP_HEIGHT_MAX) -> Tuple[bool, bool, float]:
        """Resolve swept AABB movement across Y (first), then X and Z (with auto-stepping).

        Returns:
            (on_ground, against_wall, slipperiness_substrate)
        """
        px, py, pz = pos
        vx, vy, vz = vel

        # ---------------------------------------------------------------------
        # 1. Y-axis Translation & Collision Resolution
        # ---------------------------------------------------------------------
        on_ground = False
        slipperiness = SLIPPERINESS_AIR

        if vy != 0:
            target_y = py + vy
            lo_x, hi_x = px - half_width, px + half_width
            lo_z, hi_z = pz - half_width, pz + half_width

            if vy < 0:
                # Falling: check floor collisions
                min_bx = math.floor(lo_x)
                max_bx = math.floor(hi_x - EPSILON)
                min_bz = math.floor(lo_z)
                max_bz = math.floor(hi_z - EPSILON)

                start_by = math.floor(py)
                end_by = math.floor(target_y)

                floor_y = None
                floor_block = AIR
                for by in range(start_by, end_by - 1, -1):
                    for bx in range(min_bx, max_bx + 1):
                        for bz in range(min_bz, max_bz + 1):
                            if world.is_solid(bx, by, bz):
                                top = by + 1.0
                                if top <= py + EPSILON and top >= target_y:
                                    if floor_y is None or top > floor_y:
                                        floor_y = top
                                        floor_block = world.get(bx, by, bz)
                    if floor_y is not None:
                        break

                if floor_y is not None:
                    pos[1] = floor_y
                    on_ground = True
                    slipperiness = get_block_slipperiness(floor_block)
                    if floor_block == SLIME and abs(vy) > 0.1:
                        # Elastic rebound
                        vel[1] = -vy * 0.8
                    else:
                        vel[1] = 0.0
                else:
                    pos[1] = target_y
            else:
                # Jumping: check ceiling collisions
                min_bx = math.floor(lo_x)
                max_bx = math.floor(hi_x - EPSILON)
                min_bz = math.floor(lo_z)
                max_bz = math.floor(hi_z - EPSILON)

                start_by = math.floor(py + height)
                end_by = math.floor(target_y + height)

                ceil_y = None
                for by in range(start_by, end_by + 1):
                    for bx in range(min_bx, max_bx + 1):
                        for bz in range(min_bz, max_bz + 1):
                            if world.is_solid(bx, by, bz):
                                bottom = float(by)
                                if bottom >= py + height - EPSILON and bottom <= target_y + height:
                                    if ceil_y is None or bottom < ceil_y:
                                        ceil_y = bottom
                    if ceil_y is not None:
                        break

                if ceil_y is not None:
                    pos[1] = ceil_y - height - EPSILON
                    vel[1] = 0.0
                else:
                    pos[1] = target_y
        else:
            # Stationary vertically: check if standing on a solid block
            lo_x, hi_x = px - half_width, px + half_width
            lo_z, hi_z = pz - half_width, pz + half_width
            check_y = math.floor(pos[1] - 0.01)
            for bx in range(math.floor(lo_x), math.floor(hi_x - EPSILON) + 1):
                for bz in range(math.floor(lo_z), math.floor(hi_z - EPSILON) + 1):
                    if world.is_solid(bx, check_y, bz):
                        on_ground = True
                        slipperiness = get_block_slipperiness(world.get(bx, check_y, bz))
                        break
                if on_ground:
                    break

        # ---------------------------------------------------------------------
        # 2. X and Z axes Translations with Auto-Step (up to 0.6m)
        # ---------------------------------------------------------------------
        hit_x = False
        hit_z = False

        # Attempt move with auto-step if on_ground
        if on_ground and (vx != 0 or vz != 0):
            # Try normal move first
            pos_x_try, hit_x = cls._test_move_axis(world, pos, 0, vx, half_width, height)
            pos_z_try, hit_z = cls._test_move_axis(world, [pos_x_try, pos[1], pos[2]], 2, vz, half_width, height)

            if hit_x or hit_z:
                # Test stepping up
                step_up_pos = [pos[0], pos[1] + step_height, pos[2]]
                # Verify step-up space is clear of solid blocks
                if not cls._collides_with_world(world, step_up_pos, half_width, height):
                    # Move horizontally from stepped-up position
                    up_x, up_hit_x = cls._test_move_axis(world, step_up_pos, 0, vx, half_width, height)
                    up_z, up_hit_z = cls._test_move_axis(world, [up_x, step_up_pos[1], step_up_pos[2]], 2, vz, half_width, height)
                    # Step back down to ground
                    stepped_down_y = cls._step_down(world, [up_x, step_up_pos[1], up_z], half_width, height, step_height + EPSILON)
                    # Successful step-up must actually land higher than the original pos[1]
                    if stepped_down_y is not None and stepped_down_y > pos[1] + EPSILON:
                        pos[0] = up_x
                        pos[1] = stepped_down_y
                        pos[2] = up_z
                        on_ground = True
                        return on_ground, False, slipperiness

        # Normal sequential resolution (tangent slide along walls)
        if vx != 0:
            pos[0], hit_x = cls._test_move_axis(world, pos, 0, vx, half_width, height)
            if hit_x:
                vel[0] = 0.0

        if vz != 0:
            pos[2], hit_z = cls._test_move_axis(world, pos, 2, vz, half_width, height)
            if hit_z:
                vel[2] = 0.0

        against_wall = hit_x or hit_z
        return on_ground, against_wall, slipperiness

    @classmethod
    def _collides_with_world(cls, world, pos: List[float], half_width: float, height: float) -> bool:
        """Check if an AABB at pos intersects any solid blocks in world."""
        px, py, pz = pos
        min_x = math.floor(px - half_width)
        max_x = math.floor(px + half_width - EPSILON)
        min_y = math.floor(py)
        max_y = math.floor(py + height - EPSILON)
        min_z = math.floor(pz - half_width)
        max_z = math.floor(pz + half_width - EPSILON)

        for bx in range(min_x, max_x + 1):
            for by in range(min_y, max_y + 1):
                for bz in range(min_z, max_z + 1):
                    if world.is_solid(bx, by, bz):
                        return True
        return False

    @classmethod
    def _step_down(cls, world, pos: List[float], half_width: float, height: float, max_drop: float) -> Optional[float]:
        """Step downward to settle onto the top of the stepped block."""
        px, py, pz = pos
        min_bx = math.floor(px - half_width)
        max_bx = math.floor(px + half_width - EPSILON)
        min_bz = math.floor(pz - half_width)
        max_bz = math.floor(pz + half_width - EPSILON)

        floor_y = None
        for by in range(math.floor(py), math.floor(py - max_drop) - 1, -1):
            for bx in range(min_bx, max_bx + 1):
                for bz in range(min_bz, max_bz + 1):
                    if world.is_solid(bx, by, bz):
                        top = by + 1.0
                        if top <= py + EPSILON and top >= py - max_drop:
                            if floor_y is None or top > floor_y:
                                floor_y = top
            if floor_y is not None:
                break
        return floor_y

    @classmethod
    def _test_move_axis(cls, world, pos: List[float], axis: int, dist: float,
                        half_width: float, height: float) -> Tuple[float, bool]:
        """Move along a single axis (0: X, 2: Z), stopping before any solid voxel."""
        if dist == 0:
            return pos[axis], False

        new_val = pos[axis] + dist
        test_pos = list(pos)
        test_pos[axis] = new_val

        px, py, pz = test_pos
        lo = (px - half_width, py, pz - half_width)
        hi = (px + half_width, py + height, pz + half_width)

        hit = None
        for bx in range(math.floor(lo[0]), math.floor(hi[0] - EPSILON) + 1):
            for by in range(math.floor(lo[1]), math.floor(hi[1] - EPSILON) + 1):
                for bz in range(math.floor(lo[2]), math.floor(hi[2] - EPSILON) + 1):
                    if world.is_solid(bx, by, bz):
                        c = (bx, by, bz)[axis]
                        if hit is None or (c < hit if dist > 0 else c > hit):
                            hit = c

        if hit is None:
            return new_val, False

        # Snap to face of block
        if dist > 0:
            return hit - (height if axis == 1 else half_width) - EPSILON, True
        else:
            return hit + 1.0 + (0 if axis == 1 else half_width) + EPSILON, True


class DDARaycast:
    """3D Digital Differential Analyzer (Amanatides & Woo)."""

    @staticmethod
    def raycast(world, origin: Tuple[float, float, float],
                direction: Tuple[float, float, float],
                max_reach: float = REACH_MINE,
                targetable_predicate=None) -> Optional[Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]]:
        """Perform 3D voxel grid traversal along ray.

        Returns:
            (target_block_pos, previous_block_pos, face_normal) or None.
            face_normal is (nx, ny, nz) matching target_pos + normal == previous_pos.
        """
        pos = [math.floor(c) for c in origin]

        def is_targetable(x, y, z):
            b = world.get(x, y, z)
            if targetable_predicate is not None:
                return targetable_predicate(b)
            return b != AIR and b != WATER

        if is_targetable(*pos):
            return tuple(pos), tuple(pos), (0, 0, 0)

        step = [0, 0, 0]
        t_delta = [math.inf, math.inf, math.inf]
        t_max = [math.inf, math.inf, math.inf]

        for i in range(3):
            d = direction[i]
            if d > 0:
                step[i] = 1
                t_delta[i] = 1.0 / d
                t_max[i] = (pos[i] + 1 - origin[i]) * t_delta[i]
            elif d < 0:
                step[i] = -1
                t_delta[i] = -1.0 / d
                t_max[i] = (origin[i] - pos[i]) * t_delta[i]

        while True:
            axis = t_max.index(min(t_max))
            if t_max[axis] > max_reach:
                return None

            previous = tuple(pos)
            pos[axis] += step[axis]
            t_max[axis] += t_delta[axis]

            if is_targetable(*pos):
                normal = [0, 0, 0]
                normal[axis] = -step[axis]
                return tuple(pos), previous, tuple(normal)

    @staticmethod
    def can_place_block(world, place_pos: Tuple[int, int, int],
                        entities_aabbs: List[Tuple[float, float, float, float, float, float]]) -> bool:
        """Validate that a block placement at place_pos does not collide with entity AABBs."""
        bx, by, bz = place_pos
        block_box = (float(bx), float(by), float(bz), float(bx + 1), float(by + 1), float(bz + 1))
        for ent_box in entities_aabbs:
            if aabb_intersects(block_box, ent_box):
                return False
        return True
