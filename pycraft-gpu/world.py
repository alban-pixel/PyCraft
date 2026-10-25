"""The voxel world: endless in x and z, 4096 blocks high, stored in 16x16x16 sections that are
generated the first time they are needed. Saving keeps only the sections the player changed: the
rest comes back the same from the seed."""
import math

import numpy as np

from blocks import AIR, SOLID, TARGETABLE
from terrain import (BIRCH_FOREST, BIOME_NAMES, CHUNK, FOREST, PLAINS, SAVANNA, SEA_LEVEL, TAIGA, WORLD_HEIGHT,
                     TerrainGenerator)

SAVE_VERSION = 2


class World:
    def __init__(self, seed):
        self.seed = int(seed)
        self.gen = TerrainGenerator(self.seed)
        self.columns = {}  # (cx, cz) -> terrain.Column
        self.sections = {}  # (cx, cy, cz) -> (16, 16, 16) uint8 array [x, y, z], or one block id
        self.edited = set()  # sections the player changed: saved, and never forgotten
        self.edited_columns = {}  # (cx, cz) -> set of cy of its edited sections

    # --- Columns and sections ------------------------------------------------------------------

    # The renderer's background thread generates terrain while the game reads and changes blocks.
    # Each thread works on its own objects and stores them with setdefault, so when both make the
    # same column or section, the first one stored wins (they are identical anyway).

    def load_columns(self, keys):
        """Make sure these columns exist, generating the missing ones in batches."""
        missing = list(dict.fromkeys(k for k in keys if k not in self.columns))
        for i in range(0, len(missing), 64):
            for col in self.gen.columns(missing[i:i + 64]):
                self.columns.setdefault((col.cx, col.cz), col)

    def column(self, cx, cz):
        col = self.columns.get((cx, cz))
        if col is None:
            col = self.columns.setdefault((cx, cz), self.gen.columns([(cx, cz)])[0])
        return col

    def _nearby(self, cx, cz):
        """The 3x3 columns around (cx, cz), generating the missing ones together."""
        cols = {(cx + dx, cz + dz): self.columns.get((cx + dx, cz + dz)) for dx in (-1, 0, 1) for dz in (-1, 0, 1)}
        missing = [k for k, col in cols.items() if col is None]
        if missing:
            for col in self.gen.columns(missing):
                cols[(col.cx, col.cz)] = self.columns.setdefault((col.cx, col.cz), col)
        return cols

    def section(self, cx, cy, cz):
        key = (cx, cy, cz)
        s = self.sections.get(key)
        if s is None:
            if not 0 <= cy < WORLD_HEIGHT // CHUNK:
                return AIR
            s = self.sections.setdefault(key, self.gen.section(self._nearby(cx, cz), cx, cy, cz))
        return s

    def forget(self, cx, cz, radius):
        """Drop columns and sections farther than radius chunks from (cx, cz), unless edited."""
        for k in [k for k in list(self.columns) if max(abs(k[0] - cx), abs(k[1] - cz)) > radius]:
            self.columns.pop(k, None)
        for k in [k for k in list(self.sections) if max(abs(k[0] - cx), abs(k[2] - cz)) > radius]:
            if k not in self.edited:
                self.sections.pop(k, None)

    # --- Blocks --------------------------------------------------------------------------------

    def inside(self, x, y, z):
        return 0 <= y < WORLD_HEIGHT

    def get(self, x, y, z):
        if not 0 <= y < WORLD_HEIGHT:
            return AIR
        s = self.section(x >> 4, y >> 4, z >> 4)
        return s if isinstance(s, int) else int(s[x & 15, y & 15, z & 15])

    def set(self, x, y, z, block):
        if not 0 <= y < WORLD_HEIGHT:
            return
        key = (x >> 4, y >> 4, z >> 4)
        s = self.section(*key)
        self.edited.add(key)  # first, so forget() never drops it
        self.edited_columns.setdefault((key[0], key[2]), set()).add(key[1])
        if isinstance(s, int):
            s = np.full((CHUNK, CHUNK, CHUNK), s, dtype=np.uint8)
            self.sections[key] = s
        s[x & 15, y & 15, z & 15] = block

    def is_solid(self, x, y, z):
        if y < 0:
            return True  # a floor under the bedrock, so nobody falls out of the world
        return bool(SOLID[self.get(x, y, z)])

    def biome_at(self, x, z):
        """Name of the biome at block (x, z), or "River" in a river."""
        col = self.column(x >> 4, z >> 4)
        if col.river[x & 15, z & 15]:
            return "River"
        return BIOME_NAMES[col.biome[x & 15, z & 15]]

    def surface_y(self, x, z):
        return int(self.column(x >> 4, z >> 4).height[x & 15, z & 15])

    def find_spawn(self):
        """Feet position on dry, fairly flat land near (0, 0), in a mild biome, with high mountains
        in view if possible."""
        gen = self.gen
        for reach in (2000, 6000, 20000):
            step = reach / 40
            g = np.arange(-40, 41) * step
            x, z = np.meshgrid(g, g, indexing="ij")
            s = gen.sample(x, z)
            h = s["height"]
            flat = np.abs(gen.sample(x + 3, z + 3)["height"] - h) < 3
            mild = np.isin(s["biome"], (PLAINS, FOREST, BIRCH_FOREST, TAIGA, SAVANNA))
            ok = (s["water"] < 0) & (h > SEA_LEVEL + 3) & flat & mild
            if not ok.any():
                continue
            # The highest ground within about 1.5 km of each spot, from a coarser look around
            wide = np.arange(-24, 25) * (reach + 1500) / 24
            wx, wz = np.meshgrid(wide, wide, indexing="ij")
            peaks = gen.sample(wx, wz)["height"].ravel()
            px, pz = x[ok], z[ok]
            nearest = np.argsort(np.hypot(px, pz))[:800]  # enough spots to choose from
            px, pz = px[nearest], pz[nearest]
            near = np.hypot(px[:, None] - wx.ravel()[None], pz[:, None] - wz.ravel()[None]) < 1500
            view = np.max(np.where(near, peaks[None], 0), axis=1) - SEA_LEVEL
            altitude = gen.sample(px, pz)["height"] - SEA_LEVEL  # lowlands, looking up at the mountains
            score = np.minimum(view, 2500) / 1000 - np.hypot(px, pz) / reach - altitude / 300
            best = int(np.argmax(score))
            bx, bz = int(px[best]), int(pz[best])
            return [bx + 0.5, float(self.surface_y(bx, bz) + 1), bz + 0.5]
        return [0.5, float(max(self.surface_y(0, 0), SEA_LEVEL) + 1), 0.5]

    # --- Saving --------------------------------------------------------------------------------

    def save(self, path, **extra):
        keys = sorted(self.edited)
        blocks = [self.sections[k] for k in keys]
        blocks = [np.full((CHUNK,) * 3, b, np.uint8) if isinstance(b, int) else b for b in blocks]
        np.savez_compressed(path, version=SAVE_VERSION, seed=self.seed,
                            keys=np.array(keys, dtype=np.int64).reshape(-1, 3),
                            sections=np.array(blocks, dtype=np.uint8).reshape(-1, CHUNK, CHUNK, CHUNK), **extra)

    @classmethod
    def load(cls, path):
        """Return (world, data) where data holds the extra values given to save()."""
        with np.load(path) as f:
            data = {key: f[key] for key in f.files}
        if int(data.pop("version", 1)) != SAVE_VERSION:
            raise ValueError("this save is from an older version of the game")
        world = cls(int(data.pop("seed")))
        for key, blocks in zip(data.pop("keys"), data.pop("sections")):
            key = tuple(int(v) for v in key)
            world.sections[key] = blocks.copy()
            world.edited.add(key)
            world.edited_columns.setdefault((key[0], key[2]), set()).add(key[1])
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
