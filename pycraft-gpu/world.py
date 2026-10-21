"""The voxel world: a 3D NumPy array of block ids, terrain generation, saving, and block ray casting."""
import math

import numpy as np
import pyxel

from blocks import (AIR, BEDROCK, COAL_ORE, DIAMOND_ORE, DIRT, GLOWSTONE, GOLD_ORE, GRASS,
                    IRON_ORE, LEAVES, LOG, SAND, SNOW, SOLID, STONE, TARGETABLE, WATER)

SEA_LEVEL = 22  # water fills every empty block below this height that is open to the sky


class World:
    def __init__(self, size=(128, 64, 128), seed=1, generate=True):
        self.size = tuple(int(s) for s in size)
        self.seed = int(seed)
        sx, sy, sz = self.size
        # One block of air padding on every side, so meshing never goes out of bounds.
        # World block (x, y, z) is stored at blocks[x + 1, y + 1, z + 1].
        self.blocks = np.zeros((sx + 2, sy + 2, sz + 2), dtype=np.uint8)
        if generate:
            self.generate()

    @property
    def inner(self):
        """The world without its padding: inner[x, y, z] is block (x, y, z)."""
        return self.blocks[1:-1, 1:-1, 1:-1]

    def inside(self, x, y, z):
        sx, sy, sz = self.size
        return 0 <= x < sx and 0 <= y < sy and 0 <= z < sz

    def get(self, x, y, z):
        return int(self.blocks[x + 1, y + 1, z + 1]) if self.inside(x, y, z) else AIR

    def set(self, x, y, z, block):
        if self.inside(x, y, z):
            self.blocks[x + 1, y + 1, z + 1] = block

    def is_solid(self, x, y, z):
        # Invisible walls around the world and a solid floor, so the player can't fall out
        sx, sy, sz = self.size
        if x < 0 or z < 0 or x >= sx or z >= sz or y < 0:
            return True
        return y < sy and SOLID[self.blocks[x + 1, y + 1, z + 1]]

    # --- Generation ----------------------------------------------------------------------------

    def generate(self):
        sx, sy, sz = self.size
        pyxel.nseed(self.seed)
        rng = np.random.default_rng(self.seed)
        inner = self.inner

        heights = np.zeros((sx, sz), dtype=int)
        for x in range(sx):
            for z in range(sz):
                n = pyxel.noise(x * 0.022, z * 0.022) + 0.5 * pyxel.noise(x * 0.07 + 100, z * 0.07 + 100)
                heights[x, z] = min(max(int(SEA_LEVEL + 3 + n * 14), 4), sy - 12)

        # Layers: stone, then 3-4 blocks of dirt, then grass (or sand near and under water)
        ys = np.arange(sy)[None, :, None]
        h = heights[:, None, :]
        dirt_depth = rng.integers(3, 5, (sx, 1, sz))
        inner[ys < h] = STONE
        inner[(ys >= h - dirt_depth) & (ys < h)] = DIRT
        top = (ys == h - 1)
        beach = (h <= SEA_LEVEL + 1)
        inner[top & ~beach] = GRASS
        inner[(ys >= h - 3) & (ys < h) & beach] = SAND

        # Ores scattered in the stone
        roll = rng.random(inner.shape)
        stone = inner == STONE
        inner[stone & (roll < 0.014)] = COAL_ORE
        inner[stone & (roll > 0.991) & (ys < 28)] = IRON_ORE
        inner[stone & (roll > 0.996) & (ys < 18)] = GOLD_ORE
        inner[stone & (roll > 0.9982) & (ys < 12)] = DIAMOND_ORE

        # Snow caps on higher terrain
        snow_caps = top & (h > 33)
        inner[snow_caps] = SNOW

        # Caves: tunnels where two smooth noise fields both cross their middle value
        n1 = _value_noise(rng, inner.shape, 14)
        n2 = _value_noise(rng, inner.shape, 14)
        tunnel = (abs(n1 - 0.5) < 0.045) & (abs(n2 - 0.5) < 0.045) & (ys >= 1)
        # Under lakes and beaches, keep caves below the surface so the water stays sealed
        tunnel &= (ys < h - 4) | (h > SEA_LEVEL + 3)
        inner[tunnel] = AIR

        inner[:, 0, :] = BEDROCK
        inner[(ys >= h) & (ys < SEA_LEVEL)] = WATER

        self._plant_trees(rng, heights)

    def _plant_trees(self, rng, heights):
        sx, _, sz = self.size
        for _ in range(sx * sz // 120):
            x, z = int(rng.integers(3, sx - 3)), int(rng.integers(3, sz - 3))
            h = int(heights[x, z])
            if self.get(x, h - 1, z) != GRASS or self.get(x, h, z) != AIR:
                continue
            trunk = int(rng.integers(4, 6))
            for dy in range(-2, 2):
                radius = 2 if dy < 0 else 1
                for dx in range(-radius, radius + 1):
                    for dz in range(-radius, radius + 1):
                        corner = abs(dx) == radius and abs(dz) == radius
                        if corner and rng.random() < 0.6:
                            continue
                        if self.get(x + dx, h + trunk + dy, z + dz) == AIR:
                            self.set(x + dx, h + trunk + dy, z + dz, LEAVES)
            for y in range(h, h + trunk):
                self.set(x, y, z, LOG)
            self.set(x, h - 1, z, DIRT)

    def find_spawn(self):
        """Feet position on the grass block closest to the world's center."""
        sx, sy, sz = self.size
        inner = self.inner
        top_y = sy - 1 - np.argmax(inner[:, ::-1, :] != AIR, axis=1)  # highest block of each column
        top_block = np.take_along_axis(inner, top_y[:, None, :], axis=1)[:, 0, :]
        xs, zs = np.meshgrid(np.arange(sx), np.arange(sz), indexing="ij")
        dist = (xs - sx // 2) ** 2 + (zs - sz // 2) ** 2.0
        dist[top_block != GRASS] = np.inf
        x, z = np.unravel_index(np.argmin(dist), dist.shape)
        return [float(x) + 0.5, float(top_y[x, z] + 1), float(z) + 0.5]

    # --- Saving --------------------------------------------------------------------------------

    def save(self, path, **extra):
        np.savez_compressed(path, blocks=self.inner, seed=self.seed, **extra)

    @classmethod
    def load(cls, path):
        """Return (world, data) where data holds the extra values given to save()."""
        with np.load(path) as f:
            data = {key: f[key] for key in f.files}
        blocks = data.pop("blocks")
        world = cls(blocks.shape, int(data.pop("seed")), generate=False)
        world.inner[...] = blocks
        return world, data

    # --- Aiming --------------------------------------------------------------------------------

    def raycast(self, origin, direction, reach):
        """Walk the grid along a ray (DDA). Returns (hit_block, previous_block) or None.

        Air and water are passed through, so you can aim at blocks under water."""
        pos = [math.floor(c) for c in origin]
        if TARGETABLE[self.get(*pos)]:  # the ray starts inside a block (e.g. flying through leaves)
            return tuple(pos), tuple(pos)
        step, t_delta, t_max = [0] * 3, [math.inf] * 3, [math.inf] * 3
        for i in range(3):
            d = direction[i]
            if d > 0:
                step[i], t_delta[i] = 1, 1 / d
                t_max[i] = (pos[i] + 1 - origin[i]) * t_delta[i]
            elif d < 0:
                step[i], t_delta[i] = -1, -1 / d
                t_max[i] = (origin[i] - pos[i]) * t_delta[i]
        while True:
            axis = t_max.index(min(t_max))
            if t_max[axis] > reach:
                return None
            previous = tuple(pos)
            pos[axis] += step[axis]
            t_max[axis] += t_delta[axis]
            if TARGETABLE[self.get(*pos)]:
                return tuple(pos), previous


def _value_noise(rng, shape, cell):
    """Smooth 3D noise in [0, 1]: random values on a coarse grid, blended between grid points."""
    grid = rng.random([s // cell + 2 for s in shape])
    idx, frac = [], []
    for axis, s in enumerate(shape):
        c = np.arange(s) / cell
        view = [None, None, None]
        view[axis] = slice(None)
        idx.append(c.astype(int)[tuple(view)])
        t = (c - c.astype(int))[tuple(view)]
        frac.append(t * t * (3 - 2 * t))
    (x, y, z), (fx, fy, fz) = idx, frac

    def lerp(a, b, t):
        return a + (b - a) * t

    def corner(dx, dy, dz):
        return grid[x + dx, y + dy, z + dz]

    return lerp(
        lerp(lerp(corner(0, 0, 0), corner(1, 0, 0), fx), lerp(corner(0, 1, 0), corner(1, 1, 0), fx), fy),
        lerp(lerp(corner(0, 0, 1), corner(1, 0, 1), fx), lerp(corner(0, 1, 1), corner(1, 1, 1), fx), fy),
        fz,
    )
