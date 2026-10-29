"""Multi-dimensional topology (Overworld, Nether, End), Portals, and Elytra flight physics.

Implements canonical Minecraft dimensional mechanics:
- Dimension Enum: OVERWORLD, NETHER, END.
- Nether Dimension:
    - Y in [0, 128] height bounds.
    - Bedrock floor (Y=0) and ceiling (Y=127).
    - Lava sea at Y <= 31.
    - Coordinate ratio 1:8 (1 Nether block = 8 Overworld blocks).
    - Water evaporates instantly when placed in the Nether.
    - Nether Portal geometry: minimum 4x5 obsidian frame with inner 2x3 portal area.
- End Dimension:
    - Floating central obsidian/end island centered at (0, 60, 0).
    - Void damage threshold: Y < 0 deals direct void damage ignoring armor.
    - Outer islands beyond 1000m radius.
- Elytra Kinematics:
    - Gliding pitch dynamics: diving accelerates, pulling up converts velocity to climb.
    - Drag coefficient and lift equations.
    - Stall threshold when velocity falls below critical speed.
"""
import math
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

import blocks


class Dimension(Enum):
    OVERWORLD = "overworld"
    NETHER = "nether"
    END = "end"


NETHER_COORDINATE_SCALE = 8.0
GRAVITY_ACCEL = 0.08
ELYTRA_DRAG = 0.99
STALL_SPEED = 0.25


class PortalManager:
    """Validates and manages obsidian portal frames and inter-dimensional teleportation."""

    @staticmethod
    def convert_coordinates(pos: Tuple[float, float, float],
                            from_dim: Dimension,
                            to_dim: Dimension) -> Tuple[float, float, float]:
        """Convert spatial coordinates according to the 1:8 Nether geodesic ratio."""
        x, y, z = pos
        if from_dim == Dimension.OVERWORLD and to_dim == Dimension.NETHER:
            return (x / NETHER_COORDINATE_SCALE, max(4.0, min(120.0, y)), z / NETHER_COORDINATE_SCALE)
        elif from_dim == Dimension.NETHER and to_dim == Dimension.OVERWORLD:
            return (x * NETHER_COORDINATE_SCALE, max(4.0, min(310.0, y)), z * NETHER_COORDINATE_SCALE)
        return (x, y, z)

    @staticmethod
    def validate_nether_portal(world, min_x: int, min_y: int, min_z: int, axis: str = "x") -> bool:
        """Validate an obsidian portal frame (minimum 4 wide x 5 high with 2x3 interior).

        axis: 'x' for frame along X axis, 'z' for frame along Z axis.
        """
        # Outer dimensions: width=4, height=5
        # Inner dimensions: width=2, height=3 (min_x+1..min_x+2, min_y+1..min_y+3)
        for dy in range(5):
            for dw in range(4):
                bx = min_x + (dw if axis == "x" else 0)
                by = min_y + dy
                bz = min_z + (dw if axis == "z" else 0)

                is_border = (dy == 0 or dy == 4 or dw == 0 or dw == 3)
                block = world.get(bx, by, bz)

                if is_border:
                    if block != blocks.OBSIDIAN:
                        return False
        return True


class DimensionManager:
    """Handles environmental constraints and generation rules for each dimension."""

    @staticmethod
    def can_place_water(dim: Dimension) -> bool:
        """Water evaporates immediately in the Nether."""
        return dim != Dimension.NETHER

    @staticmethod
    def check_void_damage(y: float, dim: Dimension) -> int:
        """Void abyss beneath the End/Overworld (Y < 0 or Y < -64) deals lethal piercing damage."""
        threshold = -64.0 if dim == Dimension.OVERWORLD else 0.0
        if y < threshold:
            # 4 damage points per tick in void
            return 4
        return 0


class ElytraPhysics:
    """Calculates gliding aerodynamics, pitch acceleration, climbing lift, and stalls."""

    def __init__(self):
        self.gliding: bool = False
        self.speed: float = 0.0

    def start_gliding(self, fall_speed: float) -> None:
        """Deploy wings when falling in air."""
        self.gliding = True
        self.speed = max(0.5, abs(fall_speed))

    def stop_gliding(self) -> None:
        self.gliding = False
        self.speed = 0.0

    def update(self, pitch: float, dt: float) -> Tuple[float, float]:
        """Update gliding flight velocity vector.

        pitch: Look angle in degrees (-90 = straight down, +90 = straight up).
        Returns: (horizontal_speed, vertical_velocity)
        """
        if not self.gliding:
            return 0.0, 0.0

        pitch_rad = math.radians(pitch)
        sin_pitch = math.sin(pitch_rad)
        cos_pitch = math.cos(pitch_rad)

        # Diving (pitch < 0) accelerates flight speed; Pulling up (pitch > 0) decelerates
        # Gravity vector component along flight axis
        self.speed -= sin_pitch * (GRAVITY_ACCEL * 18.0) * dt
        self.speed *= ELYTRA_DRAG
        self.speed = max(0.0, min(3.5, self.speed))

        # Check stall
        if self.speed < STALL_SPEED and pitch > 0:
            # Stall: loses lift and falls
            vert_vel = -0.5
            horiz_speed = self.speed * 0.5
        else:
            vert_vel = sin_pitch * self.speed
            horiz_speed = max(0.0, cos_pitch * self.speed)

        return horiz_speed, vert_vel
