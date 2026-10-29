"""Deterministic 3D Dual-Channel Lighting Engine (SkyLight & BlockLight).

Implements canonical Minecraft lighting propagation:
- Dual uint8 channels in [0, 15]: SkyLight (sun/moon) and BlockLight (artificial).
- Vertical skylight ray attenuation under open sky.
- 3D BFS flood-fill diffusion across 6 orthogonal neighbors with material opacity.
- Circadian solar modulation: I_sun(t) = max(0, cos(t * 2 * pi / 24000)).
- Composite gamma curve for realistic cavern and night rendering.
"""
import math
from collections import deque
from typing import Dict, List, Optional, Set, Tuple
import numpy as np

from blocks import (
    AIR, GLASS, GLOWSTONE, ICE, LAVA, LEAVES, OPAQUE, WATER,
    LIT_FURNACE, SEA_LANTERN, BEACON, REDSTONE_TORCH, LIT_REDSTONE_LAMP, TORCH as BLOCKS_TORCH,
)

TORCH = BLOCKS_TORCH

# Light emission by block ID [0, 15]
LIGHT_EMITTERS: Dict[int, int] = {
    GLOWSTONE: 15,
    LAVA: 15,
    TORCH: 14,
    LIT_FURNACE: 13,
    SEA_LANTERN: 15,
    BEACON: 15,
    REDSTONE_TORCH: 7,
    LIT_REDSTONE_LAMP: 15,
}

# Opacity / attenuation by block ID
OPACITY_MAP: Dict[int, int] = {
    AIR: 0,
    GLASS: 0,
    LEAVES: 1,
    WATER: 2,
    ICE: 2,
}


def get_block_opacity(block_id: int) -> int:
    """Return opacity [0, 15] for a block. Opaque blocks attenuate by 15."""
    if block_id in OPACITY_MAP:
        return OPACITY_MAP[block_id]
    if block_id < len(OPAQUE) and OPAQUE[block_id]:
        return 15
    return 15


class LightingEngine:
    """Manages dual-channel lighting arrays and 3D BFS light propagation."""

    def __init__(self, size: Tuple[int, int, int]):
        self.sx, self.sy, self.sz = size
        # 3D arrays: (sx, sy, sz) uint8 in [0, 15]
        self.skylight = np.zeros((self.sx, self.sy, self.sz), dtype=np.uint8)
        self.blocklight = np.zeros((self.sx, self.sy, self.sz), dtype=np.uint8)

    def compute_skylight_column(self, world, x: int, z: int) -> None:
        """Propagate direct vertical skylight downwards from the top of a column."""
        if not (0 <= x < self.sx and 0 <= z < self.sz):
            return
        light = 15
        for y in range(self.sy - 1, -1, -1):
            block = world.get(x, y, z)
            opacity = get_block_opacity(block)
            if opacity >= 15:
                light = 0
            elif opacity > 0:
                light = max(0, light - opacity)
            self.skylight[x, y, z] = light

    def compute_initial_lighting(self, world) -> None:
        """Calculate complete initial skylight and blocklight for the world."""
        self.skylight.fill(0)
        self.blocklight.fill(0)

        # 1. Cast direct skylight columns
        for x in range(self.sx):
            for z in range(self.sz):
                self.compute_skylight_column(world, x, z)

        # 2. Collect skylight sources for horizontal spread
        sky_queue = deque()
        for x in range(self.sx):
            for y in range(self.sy):
                for z in range(self.sz):
                    if self.skylight[x, y, z] > 1:
                        sky_queue.append((x, y, z))

        # BFS diffuse skylight into overhangs
        self._diffuse_bfs(world, self.skylight, sky_queue)

        # 3. Collect blocklight emitters
        block_queue = deque()
        for x in range(self.sx):
            for y in range(self.sy):
                for z in range(self.sz):
                    b = world.get(x, y, z)
                    if b in LIGHT_EMITTERS:
                        emit = LIGHT_EMITTERS[b]
                        self.blocklight[x, y, z] = emit
                        block_queue.append((x, y, z))

        # BFS diffuse blocklight
        self._diffuse_bfs(world, self.blocklight, block_queue)

    def _diffuse_bfs(self, world, light_arr: np.ndarray, queue: deque) -> None:
        """3D BFS propagation of light across 6 orthogonal neighbors."""
        neighbors = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
        sx, sy, sz = self.sx, self.sy, self.sz

        while queue:
            x, y, z = queue.popleft()
            val = light_arr[x, y, z]
            if val <= 1:
                continue

            for dx, dy, dz in neighbors:
                nx, ny, nz = x + dx, y + dy, z + dz
                if 0 <= nx < sx and 0 <= ny < sy and 0 <= nz < sz:
                    b = world.get(nx, ny, nz)
                    opacity = get_block_opacity(b)
                    if opacity < 15:
                        step_loss = max(1, opacity)
                        target_val = max(0, val - step_loss)
                        if target_val > light_arr[nx, ny, nz]:
                            light_arr[nx, ny, nz] = target_val
                            queue.append((nx, ny, nz))

    def update_block(self, world, x: int, y: int, z: int) -> None:
        """Locally recompute lighting around a changed block."""
        if not (0 <= x < self.sx and 0 <= y < self.sy and 0 <= z < self.sz):
            return
        # Column skylight update
        self.compute_skylight_column(world, x, z)

        # Queue neighbors in radius 4 for BFS refresh
        sky_q = deque()
        block_q = deque()
        r = 4
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    nx, ny, nz = x + dx, y + dy, z + dz
                    if 0 <= nx < self.sx and 0 <= ny < self.sy and 0 <= nz < self.sz:
                        if self.skylight[nx, ny, nz] > 1:
                            sky_q.append((nx, ny, nz))
                        b = world.get(nx, ny, nz)
                        if b in LIGHT_EMITTERS:
                            self.blocklight[nx, ny, nz] = LIGHT_EMITTERS[b]
                            block_q.append((nx, ny, nz))
        self._diffuse_bfs(world, self.skylight, sky_q)
        self._diffuse_bfs(world, self.blocklight, block_q)

    def get_light(self, x: int, y: int, z: int, time_of_day: float = 0.0) -> float:
        """Compute the composite perceived light multiplier [0.05, 1.0].

        Applies circadian solar modulation on skylight and gamma curve.
        """
        if not (0 <= x < self.sx and 0 <= y < self.sy and 0 <= z < self.sz):
            return 1.0

        # Circadian solar factor: daytime = 1.0, midnight = 0.0
        # time_of_day in [0.0, 1.0) where 0.0 is sunrise (~6:00), 0.25 is noon (12:00), 0.75 is midnight
        angle = time_of_day * 2.0 * math.pi
        sun_intensity = max(0.0, math.sin(angle))  # 1.0 at zenith, 0.0 at night

        sky = float(self.skylight[x, y, z]) * (0.08 + 0.92 * sun_intensity)
        blk = float(self.blocklight[x, y, z])
        combined_level = max(sky, blk)  # [0.0, 15.0]

        # Non-linear gamma curve matching Minecraft visual perception
        ratio = combined_level / 15.0
        return 0.05 + 0.95 * (ratio ** 1.3)
