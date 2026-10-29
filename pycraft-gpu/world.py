"""The voxel world: a 3D NumPy array of block ids, terrain generation, saving, and block ray casting."""
import math

import numpy as np
import pyxel

from blocks import (AIR, BEDROCK, COAL_ORE, DIAMOND_ORE, DIRT, GLOWSTONE, GOLD_ORE, GRASS,
                    IRON_ORE, LEAVES, LOG, SAND, SNOW, SOLID, STONE, TARGETABLE, WATER, LAVA, OBSIDIAN, COBBLESTONE)
from generator import ProceduralGenerator, WorldPreset, parse_seed
from fluids import FluidAutomata

SEA_LEVEL = 22  # water fills every empty block below this height that is open to the sky


class World:
    def __init__(self, size=(128, 64, 128), seed=1, generate=True, preset=WorldPreset.STANDARD, infinite=None):
        self.size = tuple(int(s) for s in size)
        self.seed = parse_seed(seed)
        self.preset = preset
        sx, sy, sz = self.size
        self.sy = sy
        if infinite is None:
            self.infinite = (self.size == (128, 64, 128))
        else:
            self.infinite = bool(infinite)

        self.generator = ProceduralGenerator(seed=self.seed, preset=self.preset)
        self.chunks = {}
        # One block of air padding on every side, so meshing never goes out of bounds.
        # World block (x, y, z) is stored at blocks[x + 1, y + 1, z + 1].
        self.blocks = np.zeros((sx + 2, sy + 2, sz + 2), dtype=np.uint8)
        self.active_water = set()
        self.fluid_automata = FluidAutomata(self)
        if generate:
            self.generate()

    @property
    def inner(self):
        """The world without its padding: inner[x, y, z] is block (x, y, z)."""
        return self.blocks[1:-1, 1:-1, 1:-1]

    def inside(self, x, y, z):
        if self.infinite:
            return 0 <= y < self.sy
        sx, sy, sz = self.size
        return 0 <= x < sx and 0 <= y < sy and 0 <= z < sz

    def get(self, x, y, z):
        if not self.inside(x, y, z):
            return AIR
        sx, sy, sz = self.size
        if 0 <= x < sx and 0 <= z < sz:
            return int(self.blocks[x + 1, y + 1, z + 1])
        cx, cz = x // 16, z // 16
        chunk = self.get_chunk(cx, cz)
        return int(chunk[x % 16, y, z % 16])

    def set(self, x, y, z, block):
        if not self.inside(x, y, z):
            return
        old_b = self.get(x, y, z)
        sx, sy, sz = self.size
        if 0 <= x < sx and 0 <= z < sz:
            self.blocks[x + 1, y + 1, z + 1] = block
        cx, cz = x // 16, z // 16
        if (cx, cz) in self.chunks:
            self.chunks[(cx, cz)][x % 16, y, z % 16] = block
        elif not (0 <= x < sx and 0 <= z < sz):
            chunk = self.get_chunk(cx, cz)
            chunk[x % 16, y, z % 16] = block

        if old_b != block:
            if block in (WATER, LAVA):
                self.fluid_automata.add_fluid(x, y, z, block, level=0)
            elif old_b in (WATER, LAVA):
                self.fluid_automata.remove_fluid(x, y, z)

    def trigger_water(self, x, y, z):
        """Wake up fluid simulation around position (x, y, z)."""
        for dx, dy, dz in [(0, 0, 0), (0, 1, 0), (0, -1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]:
            nx, ny, nz = x + dx, y + dy, z + dz
            if self.inside(nx, ny, nz) and self.get(nx, ny, nz) in (WATER, LAVA):
                self.active_water.add((nx, ny, nz))
                self.fluid_automata.trigger_cell(nx, ny, nz)

    def tick_fluids(self):
        """Step dynamic fluid flow using deterministic cellular automata. Returns a set of (cx, cz) chunk indices that were updated."""
        for cell in self.active_water:
            self.fluid_automata.active_cells.add(cell)
        modified = self.fluid_automata.tick()
        self.active_water = set(self.fluid_automata.active_cells)
        return modified

    def get_chunk(self, cx, cz):
        key = (int(cx), int(cz))
        if key in self.chunks:
            return self.chunks[key]

        sx, sy, sz = self.size
        if 0 <= cx < sx // 16 and 0 <= cz < sz // 16:
            chunk = self.inner[cx * 16:(cx + 1) * 16, :, cz * 16:(cz + 1) * 16]
            self.chunks[key] = chunk
            return chunk

        chunk = self._generate_chunk(cx, cz)
        self.chunks[key] = chunk
        return chunk

    def _generate_chunk(self, cx, cz):
        sy = self.sy
        if self.preset == WorldPreset.SUPERFLAT:
            chunk = np.zeros((16, sy, 16), dtype=np.uint8)
            chunk[:, 0, :] = BEDROCK
            chunk[:, 1:3, :] = DIRT
            chunk[:, 3, :] = GRASS
            return chunk

        if self.preset != WorldPreset.STANDARD:
            return self.generator.generate_column_blocks(cx, cz, height=sy)

        chunk = np.zeros((16, sy, 16), dtype=np.uint8)
        rng = np.random.default_rng(hash((self.seed, cx, cz)) & 0x7FFFFFFF)

        heights = np.zeros((16, 16), dtype=int)
        for lx in range(16):
            x = cx * 16 + lx
            for lz in range(16):
                z = cz * 16 + lz
                n = pyxel.noise(x * 0.022, z * 0.022) + 0.5 * pyxel.noise(x * 0.07 + 100, z * 0.07 + 100)
                heights[lx, lz] = min(max(int(SEA_LEVEL + 3 + n * 14), 4), sy - 12)

        ys = np.arange(sy)[None, :, None]
        h = heights[:, None, :]
        dirt_depth = rng.integers(3, 5, (16, 1, 16))
        chunk[ys < h] = STONE
        chunk[(ys >= h - dirt_depth) & (ys < h)] = DIRT
        top = (ys == h - 1)
        beach = (h <= SEA_LEVEL + 1)
        chunk[top & ~beach] = GRASS
        chunk[(ys >= h - 3) & (ys < h) & beach] = SAND

        roll = rng.random(chunk.shape)
        stone = chunk == STONE
        chunk[stone & (roll < 0.014)] = COAL_ORE
        chunk[stone & (roll > 0.991) & (ys < 28)] = IRON_ORE
        chunk[stone & (roll > 0.996) & (ys < 18)] = GOLD_ORE
        chunk[stone & (roll > 0.9982) & (ys < 12)] = DIAMOND_ORE

        snow_caps = top & (h > 33)
        chunk[snow_caps] = SNOW

        chunk[:, 0, :] = BEDROCK
        chunk[(ys >= h) & (ys < SEA_LEVEL)] = WATER

        for _ in range(rng.integers(0, 3)):
            tx, tz = int(rng.integers(2, 14)), int(rng.integers(2, 14))
            th = heights[tx, tz]
            if chunk[tx, th - 1, tz] == GRASS and chunk[tx, th, tz] == AIR:
                trunk = int(rng.integers(4, 6))
                for dy in range(-2, 2):
                    rad = 2 if dy < 0 else 1
                    for dx in range(-rad, rad + 1):
                        for dz in range(-rad, rad + 1):
                            if abs(dx) == rad and abs(dz) == rad and rng.random() < 0.6:
                                continue
                            ly = th + trunk + dy
                            if 0 <= tx + dx < 16 and 0 <= tz + dz < 16 and 0 <= ly < sy:
                                if chunk[tx + dx, ly, tz + dz] == AIR:
                                    chunk[tx + dx, ly, tz + dz] = LEAVES
                for y in range(th, min(sy, th + trunk)):
                    chunk[tx, y, tz] = LOG
                chunk[tx, th - 1, tz] = DIRT

        return chunk

    def get_mesh_region(self, cx, cz):
        sx, sy, sz = self.size
        x0, z0 = cx * 16, cz * 16
        if not self.infinite and 0 <= cx < sx // 16 and 0 <= cz < sz // 16:
            return self.blocks[x0:x0 + 18, :, z0:z0 + 18]

        region = np.zeros((18, sy + 2, 18), dtype=np.uint8)
        center = self.get_chunk(cx, cz)
        region[1:17, 1:sy + 1, 1:17] = center

        left = self.get_chunk(cx - 1, cz)
        region[0, 1:sy + 1, 1:17] = left[15, :, :]

        right = self.get_chunk(cx + 1, cz)
        region[17, 1:sy + 1, 1:17] = right[0, :, :]

        back = self.get_chunk(cx, cz - 1)
        region[1:17, 1:sy + 1, 0] = back[:, :, 15]

        front = self.get_chunk(cx, cz + 1)
        region[1:17, 1:sy + 1, 17] = front[:, :, 0]

        region[:, 0, :] = BEDROCK
        return region

    def is_solid(self, x, y, z):
        if not self.infinite:
            sx, sy, sz = self.size
            if x < 0 or z < 0 or x >= sx or z >= sz or y < 0:
                return True
            return bool(y < sy and SOLID[self.blocks[x + 1, y + 1, z + 1]])
        else:
            if y < 0:
                return True
            if y >= self.sy:
                return False
            return bool(SOLID[self.get(x, y, z)])

    def get_column_height(self, x, z) -> int:
        """Return the top solid block Y coordinate + 1 in column (x, z), or sea level if water/air."""
        if not self.infinite:
            sx, sy, sz = self.size
            if 0 <= x < sx and 0 <= z < sz:
                col = self.blocks[x + 1, 1:sy + 1, z + 1]
                solid_ys = np.nonzero(col != 0)[0]
                if solid_ys.size > 0:
                    return int(solid_ys[-1]) + 1
            return SEA_LEVEL

        cx, cz = x // 16, z // 16
        chunk = self.chunks.get((cx, cz))
        if chunk is not None:
            col = chunk[x % 16, :, z % 16]
            solid_ys = np.nonzero(col != 0)[0]
            if solid_ys.size > 0:
                return int(solid_ys[-1]) + 1

        if self.preset == WorldPreset.SUPERFLAT:
            return 4

        if self.preset != WorldPreset.STANDARD:
            col = self.get_chunk(cx, cz)
            solid_ys = np.nonzero(col[x % 16, :, z % 16] != 0)[0]
            return int(solid_ys[-1]) + 1 if solid_ys.size > 0 else SEA_LEVEL

        # Standard preset: compute height with the EXACT SAME formula as _generate_chunk
        n = pyxel.noise(x * 0.022, z * 0.022) + 0.5 * pyxel.noise(x * 0.07 + 100, z * 0.07 + 100)
        return min(max(int(SEA_LEVEL + 3 + n * 14), 4), self.sy - 12)

    def get_surface_block_type(self, x, h, z) -> int:
        """Return dominant surface block type at column (x, z) with ground height h."""
        b = self.get(x, max(0, h - 1), z)
        if b != AIR:
            return b
        if h <= SEA_LEVEL:
            return WATER
        if h <= SEA_LEVEL + 1:
            return SAND
        if h > 33:
            return SNOW
        return GRASS

    # --- Generation ----------------------------------------------------------------------------

    def generate(self):
        sx, sy, sz = self.size
        inner = self.inner

        if self.preset == WorldPreset.SUPERFLAT:
            inner[:, 0, :] = BEDROCK
            inner[:, 1:3, :] = DIRT
            inner[:, 3, :] = GRASS
            return

        if self.preset != WorldPreset.STANDARD:
            gen = ProceduralGenerator(seed=self.seed, preset=self.preset)
            col = gen.generate_column_blocks(0, 0, height=min(sy, 128))
            # Tile or fit into world dimensions
            for cx in range(0, sx, 16):
                for cz in range(0, sz, 16):
                    c = gen.generate_column_blocks(cx // 16, cz // 16, height=min(sy, 128))
                    inner[cx:cx + 16, :min(sy, 128), cz:cz + 16] = c[:min(16, sx - cx), :, :min(16, sz - cz)]
            return

        pyxel.nseed(self.seed)
        rng = np.random.default_rng(self.seed)

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
        if np.all(np.isinf(dist)):
            dist = (xs - sx // 2) ** 2 + (zs - sz // 2) ** 2.0
            dist[top_block == AIR] = np.inf
        x, z = np.unravel_index(np.argmin(dist), dist.shape)
        return [float(x) + 0.5, float(top_y[x, z] + 1), float(z) + 0.5]

    # --- Saving --------------------------------------------------------------------------------

    def save(self, path, **extra):
        extra_chunks = {}
        sx, sy, sz = self.size
        for (cx, cz), cdata in self.chunks.items():
            if not (0 <= cx < sx // 16 and 0 <= cz < sz // 16):
                extra_chunks[f"chunk_{cx}_{cz}"] = cdata
        np.savez_compressed(
            path,
            blocks=self.inner,
            seed=self.seed,
            preset=self.preset,
            infinite=self.infinite,
            **extra_chunks,
            **extra
        )

    @classmethod
    def load(cls, path):
        """Return (world, data) where data holds the extra values given to save()."""
        with np.load(path) as f:
            data = {key: f[key] for key in f.files}
        blocks = data.pop("blocks")
        preset = str(data.pop("preset", WorldPreset.STANDARD))
        infinite = bool(data.pop("infinite", True)) if "infinite" in data else None
        world = cls(blocks.shape, int(data.pop("seed")), generate=False, preset=preset, infinite=infinite)
        world.inner[...] = blocks
        for key in list(data.keys()):
            if key.startswith("chunk_"):
                parts = key.split("_")
                cx, cz = int(parts[1]), int(parts[2])
                world.chunks[(cx, cz)] = data.pop(key)
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
