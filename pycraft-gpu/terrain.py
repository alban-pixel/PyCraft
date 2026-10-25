"""Terrain generator: continents and oceans, mountain ranges thousands of blocks high, river valleys,
lakes and 18 biomes. Everything is a function of (x, z) computed on NumPy arrays, so the same code
builds the blocks near the player and the distant scenery (at any spacing)."""
import numpy as np

from blocks import (ACACIA_LEAVES, ACACIA_LOG, AIR, BEDROCK, BIRCH_LEAVES, BIRCH_LOG, CACTUS, CLAY, COAL_ORE,
                    DEEPSLATE, DIAMOND_ORE, DIRT, GOLD_ORE, GRASS, GRAVEL, ICE, IRON_ORE, JUNGLE_LEAVES,
                    JUNGLE_LOG, LEAVES, LOG, MUD, ORANGE_TERRACOTTA, PODZOL, RED_SAND, SAND, SANDSTONE, SNOW,
                    SPRUCE_LEAVES, SPRUCE_LOG, STONE, TERRACOTTA, WATER, WHITE_TERRACOTTA)
from noise import Noise, smoothstep

CHUNK = 16  # columns and sections are 16 blocks wide
WORLD_HEIGHT = 4096
SEA_LEVEL = 512
LAPSE = 1 / 1500  # temperature drop per block of altitude: tree line, then snow, then glaciers

# Continentalness -> base height above sea level (oceans, coasts, lowlands, inland plateaus)
C_POINTS = [-1.2, -0.55, -0.25, -0.08, 0.0, 0.08, 0.3, 0.7, 1.2]
C_HEIGHTS = [-300, -220, -90, -20, -2, 5, 30, 85, 120]

(OCEAN, DEEP_OCEAN, FROZEN_OCEAN, BEACH, DESERT, BADLANDS, SAVANNA, JUNGLE, PLAINS, FOREST, BIRCH_FOREST,
 SWAMP, TAIGA, SNOWY_TAIGA, SNOWY_TUNDRA, ALPINE, SNOWY_PEAKS, GLACIER) = range(18)
BIOME_NAMES = ["Ocean", "Deep ocean", "Frozen ocean", "Beach", "Desert", "Badlands", "Savanna", "Jungle",
               "Plains", "Forest", "Birch forest", "Swamp", "Taiga", "Snowy taiga", "Snowy tundra",
               "Alpine meadow", "Snowy peaks", "Glacier"]

NOISES = ["warp_x", "warp_z", "continent", "mountain_mask", "ridges", "hilliness", "hills", "detail",
          "river", "river_warp_x", "river_warp_z", "river_width", "lake", "temperature", "humidity",
          "badlands", "surface", "caves_a", "caves_b", "caverns", "entrances", "ores"]


class TerrainGenerator:
    def __init__(self, seed):
        self.seed = int(seed)
        for i, name in enumerate(NOISES):
            setattr(self, name, Noise(np.random.SeedSequence([self.seed, i]).generate_state(1)[0]))

    def climate(self, x, z):
        """The large, smooth parts of the terrain at points (x, z): continents, climate, where the
        mountain ranges and rivers run. They change slowly, so for whole chunks they are computed
        every 8 blocks and blended in between (see _generate_columns)."""
        # Warp the coordinates of the large features, so continents and ranges get irregular shapes
        wx = x + 900 * self.warp_x.fbm2(x / 3000, z / 3000, 3)
        wz = z + 900 * self.warp_z.fbm2(x / 3000, z / 3000, 3)
        # Mountain ranges and rivers follow the zero lines of smooth noises: keep each noise and the
        # length of its gradient, their ratio is the distance to the line in blocks
        m = self.mountain_mask.fbm2(wx / 16000, wz / 16000, 3)
        m_grad = np.hypot(self.mountain_mask.fbm2((wx + 16) / 16000, wz / 16000, 3) - m,
                          self.mountain_mask.fbm2(wx / 16000, (wz + 16) / 16000, 3) - m) / 16
        rx = x + 400 * self.river_warp_x.fbm2(x / 1100, z / 1100, 2)
        rz = z + 400 * self.river_warp_z.fbm2(x / 1100, z / 1100, 2)
        r = self.river.fbm2(rx / 5200, rz / 5200, 3)
        r_grad = np.hypot(self.river.fbm2((rx + 4) / 5200, rz / 5200, 3) - r,
                          self.river.fbm2(rx / 5200, (rz + 4) / 5200, 3) - r) / 4
        return {
            "wx": wx, "wz": wz, "m": m, "m_grad": m_grad, "r": r, "r_grad": r_grad,
            "continent": self.continent.fbm2(wx / 6000, wz / 6000, 5) * 2.4 + 0.2,
            "temperature": self.temperature.fbm2(wx / 4500, wz / 4500, 3) * 2.3,
            "humidity": self.humidity.fbm2(wx / 4000, wz / 4000, 3) * 2.3,
            "hilliness": smoothstep(-0.3, 0.45, self.hilliness.fbm2(wx / 2500, wz / 2500, 2) * 2.3),
            "half_width": 2600 + 1200 * self.hilliness.noise2(wx / 7000 + 50, wz / 7000),
            "strength": smoothstep(-0.5, 0.15, self.mountain_mask.fbm2(wx / 9000 + 300, wz / 9000, 2) * 2.3),
            "badlands": self.badlands.fbm2(wx / 1800, wz / 1800, 2) * 2.3,
            "river_width": self.river_width.noise2(x / 400, z / 400),
            "lake": self.lake.fbm2(wx / 1200, wz / 1200, 3) * 2.3,
        }

    def sample(self, x, z, clim=None):
        """Terrain at points (x, z), given as float arrays of the same shape. clim: climate(x, z),
        when the caller already has it.

        Returns a dict of arrays: height (top of the ground, float), water (water surface height,
        or -1 where there is none), biome, temperature, humidity and a few values the surface uses."""
        k = self.climate(x, z) if clim is None else clim
        wx, wz, c, hilliness = k["wx"], k["wz"], k["continent"], k["hilliness"]
        base = np.interp(c, C_POINTS, C_HEIGHTS) + SEA_LEVEL  # smooth "ground level" without relief
        land = smoothstep(-0.02, 0.25, c)
        temperature = k["temperature"] + 0.05 * self.surface.noise2(x / 90, z / 90)
        humidity = k["humidity"] + 0.06 * self.surface.noise2(x / 70 + 500, z / 70)

        # Relief on top of the base level, always >= 0 on land: hills, mountains, small bumps
        hills = np.maximum(self.hills.fbm2(x / 600, z / 600, 5) * 2.2 + 0.45, 0) * (10 + 85 * hilliness)
        # Mountain ranges: long chains along the zero line of a very smooth noise. A spine rises
        # toward that line, and ridged noise adds the side ridges, peaks and valleys on top of it.
        spine = np.clip(1 - np.abs(k["m"]) / np.maximum(k["m_grad"], 1e-9) / k["half_width"], 0, 1)
        # Ranges may run a little into the sea: steep coasts and rocky islands
        mask = spine * k["strength"] * smoothstep(-0.3, 0.1, c)  # 0 outside ranges, 1 on the highest crests
        mountains = np.zeros_like(mask)
        ranges = mask > 0  # the ridged noise is the costliest part: only where it's needed
        ridges = self.ridges.ridged2(wx[ranges] / 3000, wz[ranges] / 3000, 8, gain=0.48)
        mountains[ranges] = 3800 * mask[ranges] ** 1.2 * (0.35 + 0.65 * ridges ** 1.6)
        detail = (self.detail.fbm2(x / 45, z / 45, 3) + 0.6) * (2.0 + 5 * hilliness + 9 * mask)
        relief = (hills * (0.4 + 0.6 * land) + np.maximum(detail, 0)) * land + mountains

        # Badlands: in hot and dry places, the relief turns into stepped mesas
        mesa = smoothstep(0.25, 0.45, temperature) * smoothstep(-0.25, -0.45, humidity) * smoothstep(
            -0.1, 0.25, k["badlands"])
        step = 9.0
        stepped = np.floor(relief / step) * step + step * smoothstep(0.7, 1.0, (relief / step) % 1.0)
        relief = relief + (stepped * 1.4 - relief) * mesa

        # Rivers carve a channel and a valley around the zero line of the river noise
        dist = np.abs(k["r"]) / np.maximum(k["r_grad"], 1e-9)
        lowland = 1 - smoothstep(0, 900, relief)
        width = (3 + 9 * lowland) * (1 + 0.35 * k["river_width"])
        valley = width + 40 + 0.9 * np.minimum(relief, 700)  # deeper relief, wider valley
        t = np.clip((dist - width) / (valley - width), 0, 1)
        carved = relief * t ** 1.3
        # Rivers start in the foothills: none in the mountain ranges, so the ranges stay whole
        strength = (1 - smoothstep(0.08, 0.35, mask)) * land
        river_level = np.floor(np.maximum(base, SEA_LEVEL + 1)) - 1
        depth = 1 + 0.35 * width * (1 - (dist / width) ** 2)
        in_bed = dist < width
        relief = relief + (carved - relief) * strength
        height = base + relief
        bed = river_level - depth
        height = np.where(in_bed & (strength > 0.5) & (base > SEA_LEVEL - 4), np.minimum(height, bed), height)

        # Lakes: round basins in fairly flat land, filled up to the base level
        lake = k["lake"] - 3 * mask - 0.4 * hilliness
        shore = smoothstep(0.7, 0.8, lake) * land * (1 - smoothstep(80, 300, relief))
        height = height + (np.maximum(base, SEA_LEVEL + 1) - height) * shore * (height > base)
        lake_bed = river_level - 1 - (lake - 0.8) * 60
        in_lake = (lake > 0.8) & (shore > 0.5) & (base > SEA_LEVEL - 4)
        height = np.where(in_lake, np.minimum(height, lake_bed), height)

        # Squeeze the highest peaks smoothly under the height limit instead of cutting them flat
        above = height - (SEA_LEVEL + 2700)
        height = np.where(above > 0, SEA_LEVEL + 2700 + 800 * np.tanh(above / 800), height)
        height = np.maximum(height, 8)
        top = np.floor(height)
        inland_water = (in_bed & (strength > 0.5) | in_lake) & (top < river_level) & (base > SEA_LEVEL - 4)
        water = np.where(top < SEA_LEVEL, SEA_LEVEL, np.where(inland_water, river_level, -1))

        altitude = np.maximum(top - SEA_LEVEL - 30, 0)
        temp_here = temperature - altitude * LAPSE
        biome = self._biome(top, water, c, temp_here, humidity, mesa, (mask > 0.12) | (top > SEA_LEVEL + 600))
        return {"height": height, "water": water, "biome": biome, "temperature": temp_here,
                "humidity": humidity, "continent": c, "mask": mask, "river": in_bed & (water > SEA_LEVEL)}

    @staticmethod
    def _biome(top, water, c, temp, humidity, mesa, high):
        """Biome from climate: temperature (lower with altitude) and humidity. The first rule that
        matches wins. high: in the mountains, where the cold comes from altitude, not climate."""
        underwater = top < water
        ocean = top < SEA_LEVEL - 1
        rules = [
            (ocean & (temp < -0.55), FROZEN_OCEAN),
            (ocean & (top < SEA_LEVEL - 60), DEEP_OCEAN),
            (ocean, OCEAN),
            ((top <= SEA_LEVEL + 2) & (c < 0.15) & ~underwater & (temp > -0.55), BEACH),
            (temp < -1.5, GLACIER),
            ((temp < -0.85) & high, SNOWY_PEAKS),
            ((temp < -0.5) & high, ALPINE),
            ((temp < -0.5) & (humidity < 0), SNOWY_TUNDRA),
            (temp < -0.5, SNOWY_TAIGA),
            ((temp < -0.3) & (humidity < -0.3), SNOWY_TUNDRA),
            (temp < -0.3, TAIGA),
            ((temp > 0.35) & (mesa > 0.3), BADLANDS),
            ((temp > 0.35) & (humidity < -0.3), DESERT),
            ((temp > 0.35) & (humidity < 0.15), SAVANNA),
            (temp > 0.35, JUNGLE),
            ((humidity > 0.38) & (top < SEA_LEVEL + 14), SWAMP),
            (humidity < -0.25, PLAINS),
            ((humidity > 0.1) & (temp < 0.1), BIRCH_FOREST),
        ]
        return np.select([r[0] for r in rules], [r[1] for r in rules], FOREST).astype(np.uint8)

    def columns(self, keys):
        """Build the Columns for a list of (cx, cz) chunk coordinates, with one batch of noise."""
        return _generate_columns(self, keys)

    def section(self, cols, cx, cy, cz):
        """Blocks of section (cx, cy, cz): a (16, 16, 16) uint8 array [x, y, z], or one block id when
        the whole section is that block. cols: dict of the 3x3 Columns around (cx, cz)."""
        return _generate_section(self, cols, cx, cy, cz)


# --- Blocks ------------------------------------------------------------------------------------

# Badlands rock layers, repeating with height
BANDS = np.array([TERRACOTTA, ORANGE_TERRACOTTA, TERRACOTTA, WHITE_TERRACOTTA, ORANGE_TERRACOTTA,
                  ORANGE_TERRACOTTA, TERRACOTTA, RED_SAND, TERRACOTTA, WHITE_TERRACOTTA, TERRACOTTA],
                 dtype=np.uint8)
# Ore veins: (block, veins per section, highest y, blocks per vein)
ORES = [(COAL_ORE, 5.0, SEA_LEVEL + 400, 7), (IRON_ORE, 3.0, SEA_LEVEL + 120, 5),
        (GOLD_ORE, 1.0, SEA_LEVEL - 150, 5), (DIAMOND_ORE, 0.6, SEA_LEVEL - 380, 4)]
LEAF_BLOCKS = (LEAVES, SPRUCE_LEAVES, BIRCH_LEAVES, JUNGLE_LEAVES, ACACIA_LEAVES)

OAK, BIRCH, SPRUCE, JUNGLE, ACACIA, SWAMP_OAK, CACTUS_PLANT = range(7)
# Trees per 16x16 column in each biome, as {tree kind: number of trees}
TREES = {FOREST: {OAK: 7.5, BIRCH: 1.5}, BIRCH_FOREST: {BIRCH: 8.0, OAK: 0.6}, PLAINS: {OAK: 0.3},
         SWAMP: {SWAMP_OAK: 2.5}, TAIGA: {SPRUCE: 9.0}, SNOWY_TAIGA: {SPRUCE: 6.0}, SNOWY_TUNDRA: {SPRUCE: 0.25},
         JUNGLE: {JUNGLE: 11.0, OAK: 2.0}, SAVANNA: {ACACIA: 1.0, OAK: 0.15}, DESERT: {CACTUS_PLANT: 0.9},
         BADLANDS: {CACTUS_PLANT: 0.15}, ALPINE: {SPRUCE: 0.5}}
TREE_HEIGHTS = {OAK: (4, 7), BIRCH: (5, 8), SPRUCE: (7, 14), JUNGLE: (9, 17), ACACIA: (5, 8),
                SWAMP_OAK: (4, 6), CACTUS_PLANT: (1, 4)}
TREE_GROUND = {CACTUS_PLANT: (SAND, RED_SAND)}  # the other trees grow on grass, podzol and snow
# How much the tree canopy hides the ground, seen from far away
CANOPY = np.zeros(len(BIOME_NAMES))
for _biome, _kinds in TREES.items():
    CANOPY[_biome] = min(sum(_kinds.values()) / 12, 0.85)
CANOPY[[DESERT, BADLANDS]] = 0


def _rng(seed, *coords):
    """A random generator that always gives the same numbers for the same world seed and place."""
    return np.random.default_rng([seed] + [int(c) & 0xFFFFFFFF for c in coords])


def _tree_blocks(kind, height, variant):
    """Blocks of one tree as (dx, dy, dz, block) rows; the trunk starts at (0, 0, 0), above the ground."""
    rng = np.random.default_rng([kind, height, variant])
    log, leaf = {OAK: (LOG, LEAVES), BIRCH: (BIRCH_LOG, BIRCH_LEAVES), SPRUCE: (SPRUCE_LOG, SPRUCE_LEAVES),
                 JUNGLE: (JUNGLE_LOG, JUNGLE_LEAVES), ACACIA: (ACACIA_LOG, ACACIA_LEAVES),
                 SWAMP_OAK: (LOG, LEAVES), CACTUS_PLANT: (CACTUS, CACTUS)}[kind]
    out = []

    def disc(x, y, z, radius, trim=0.5):
        """A flat layer of leaves. trim: chance to leave out each corner."""
        r = int(np.ceil(radius))
        for dx in range(-r, r + 1):
            for dz in range(-r, r + 1):
                d = max(abs(dx), abs(dz)) if radius == int(radius) else np.hypot(dx, dz)
                corner = abs(dx) == r and abs(dz) == r
                if d <= radius and not (corner and rng.random() < trim):
                    out.append((x + dx, y, z + dz, leaf))

    if kind == CACTUS_PLANT:
        return np.array([(0, dy, 0, CACTUS) for dy in range(height)], dtype=np.int32)
    trunk = height
    if kind in (OAK, BIRCH):
        disc(0, height - 3, 0, 2)
        disc(0, height - 2, 0, 2)
        disc(0, height - 1, 0, 1, 0.0)
        disc(0, height, 0, 1, 1.0)
    elif kind == SWAMP_OAK:
        disc(0, height - 2, 0, 3)
        disc(0, height - 1, 0, 3, 0.8)
        disc(0, height, 0, 2, 1.0)
    elif kind == SPRUCE:  # cone of layers, wide and narrow in turn
        for dy in range(2, height + 1):
            r = min(3.0, (height - dy) * 0.32 + 0.6)
            disc(0, dy, 0, max(0.0, r - (0.9 if (height - dy) % 2 else 0)), 0.0)
        out += [(0, height + 1, 0, leaf), (0, height + 2, 0, leaf)]
    elif kind == JUNGLE:
        disc(0, height - 2, 0, 2.5)
        disc(0, height - 1, 0, 3.3)
        disc(0, height, 0, 2.6)
        disc(0, height + 1, 0, 1.5)
        for _ in range(3):  # a few branches with leaves along the trunk
            dy = int(rng.integers(3, height - 3))
            dx, dz = [(1, 0), (-1, 0), (0, 1), (0, -1)][rng.integers(4)]
            disc(dx * 2, dy, dz * 2, 1.0, 1.0)
            out.append((dx, dy, dz, log))
    elif kind == ACACIA:  # the trunk leans over near the top, under a flat umbrella of leaves
        dx, dz = [(1, 0), (-1, 0), (0, 1), (0, -1)][rng.integers(4)]
        trunk = height - 2
        out += [(dx * i, trunk - 1 + i, dz * i, log) for i in (1, 2)]
        disc(dx * 2, height, dz * 2, 3.2)
        disc(dx * 2, height + 1, dz * 2, 1.6)
    out += [(0, dy, 0, log) for dy in range(trunk)]
    return np.array(out, dtype=np.int32)


_TREE_CACHE = {}


def tree_blocks(kind, height, variant):
    key = (kind, height, variant)
    if key not in _TREE_CACHE:
        _TREE_CACHE[key] = _tree_blocks(kind, height, variant)
    return _TREE_CACHE[key]


class Column:
    """One 16x16 column of the world: everything that doesn't depend on y. Arrays are indexed [x, z]."""

    def __init__(self, cx, cz):
        self.cx, self.cz = cx, cz


def tints(temperature, humidity, biome):
    """Biome colors (0-1) for grass, leaves and water, changing smoothly with the climate."""
    t = np.clip((temperature + 0.6) / 1.2, 0, 1)[..., None]
    h = np.clip((humidity + 0.8) / 1.3, 0, 1)[..., None]
    cold, hot_dry, hot_wet = np.array([0.45, 0.66, 0.47]), np.array([0.74, 0.7, 0.33]), np.array([0.3, 0.8, 0.14])
    grass = cold + (hot_dry + (hot_wet - hot_dry) * h - cold) * t
    foliage = grass * np.array([0.68, 0.78, 0.66])
    cold_water, warm_water = np.array([0.22, 0.36, 0.86]), np.array([0.2, 0.56, 0.95])
    water = cold_water + (warm_water - cold_water) * t
    swamp = (biome == SWAMP)[..., None]
    grass = np.where(swamp, [0.42, 0.5, 0.26], grass)
    foliage = np.where(swamp, [0.33, 0.44, 0.2], foliage)
    water = np.where(swamp, [0.3, 0.4, 0.3], water)
    return grass, foliage, water


def _surface(s, top, slope, noise):
    """Top block, the block under it and how deep that goes, for every column of a chunk.
    slope: biggest height difference with a neighbor column, in blocks."""
    biome, water = s["biome"], s["water"]
    surface = np.full(top.shape, GRASS, dtype=np.uint8)
    filler = np.full(top.shape, DIRT, dtype=np.uint8)
    depth = (3 + (noise > 0)).astype(np.int32)
    steep = slope >= 2  # 2 blocks of drop per block: bare rock instead of walls of dirt

    def put(where, top_block, fill_block=None, fill_depth=None):
        surface[where] = top_block
        if fill_block is not None:
            filler[where] = fill_block
        if fill_depth is not None:
            depth[where] = fill_depth

    put((biome == TAIGA) & (noise > 0.1), PODZOL)
    put((biome == JUNGLE) & (noise > 0.45), PODZOL)
    put((biome == SWAMP) & (noise > 0.25) & (top <= SEA_LEVEL + 3), MUD, MUD)
    put(np.isin(biome, (SNOWY_TAIGA, SNOWY_TUNDRA)), SNOW)
    put((biome == ALPINE) & (slope == 1) & (noise > 0.35), GRAVEL, GRAVEL, 2)
    put((biome == ALPINE) & steep, STONE, STONE)
    put(biome == SNOWY_PEAKS, SNOW, STONE, 1)
    put((biome == SNOWY_PEAKS) & (slope >= 4), STONE)
    put(biome == GLACIER, ICE, ICE, 8)
    put(steep & ~np.isin(biome, (DESERT, BADLANDS, BEACH, GLACIER, SNOWY_PEAKS, ALPINE)), STONE, STONE, 1)
    put(np.isin(biome, (BEACH, DESERT)), SAND, SANDSTONE, 5)
    put((biome == DESERT) & (slope >= 4), SANDSTONE)
    put(biome == BADLANDS, RED_SAND, TERRACOTTA, 12)
    # Under water: sand, gravel and clay
    under = top < water
    put(under, SAND, SAND, 3)
    put(under & (noise > 0.3), GRAVEL, GRAVEL)
    put(under & (noise < -0.35) & (water > SEA_LEVEL), CLAY, CLAY)
    put(under & (top < SEA_LEVEL - 30), GRAVEL, GRAVEL)
    put(under & (biome == SWAMP), MUD, MUD)
    return surface, filler, depth


_OFFSETS = np.arange(-1, CHUNK + 1)  # a column with a 1-block border, to know its neighbors' heights
_LATTICE = np.array([-8, 0, 8, 16])  # where the smooth climate is computed, for that same area
_I0 = np.minimum((_OFFSETS + 8) // 8, 2)
_F = (_OFFSETS + 8) / 8 - _I0


def _blend(v):
    """Bilinear blend of values on the 4x4 lattice of each column, to its 18x18 blocks."""
    v = v[:, _I0, :] * (1 - _F)[None, :, None] + v[:, _I0 + 1, :] * _F[None, :, None]
    return v[:, :, _I0] * (1 - _F)[None, None, :] + v[:, :, _I0 + 1] * _F[None, None, :]


def _generate_columns(gen, keys):
    n = len(keys)
    ks = np.array(keys, dtype=np.int64).reshape(n, 1, 1, 2)

    def grid(offsets):
        size = len(offsets)
        gx = (ks[..., 0] * CHUNK + offsets[None, :, None]).astype(float)
        gz = (ks[..., 1] * CHUNK + offsets[None, None, :]).astype(float)
        return np.broadcast_to(gx, (n, size, size)), np.broadcast_to(gz, (n, size, size))

    clim = {name: _blend(v) for name, v in gen.climate(*grid(_LATTICE)).items()}
    x, z = grid(_OFFSETS)
    s = gen.sample(x, z, clim)
    top_padded = np.floor(s["height"]).astype(np.int32)
    inner = (slice(None), slice(1, -1), slice(1, -1))
    s = {k: v[inner] for k, v in s.items()}
    top = top_padded[inner]
    slope = np.max([np.abs(top - top_padded[:, 1 + dx:17 + dx, 1 + dz:17 + dz])
                    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))], axis=0)
    xs, zs = x[inner], z[inner]
    noise = gen.surface.fbm2(xs / 9, zs / 9, 2) * 2
    surface, filler, depth = _surface(s, top, slope, noise)
    grass, foliage, water_tint = tints(s["temperature"], s["humidity"], s["biome"])
    deep = (SEA_LEVEL - 90 + 6 * gen.surface.noise2(xs / 23 + 90, zs / 23)).astype(np.int32)
    entrance = gen.entrances.noise2(xs / 380, zs / 380) > 0.55

    columns = []
    for i, (cx, cz) in enumerate(keys):
        col = Column(cx, cz)
        col.height, col.water = top[i], s["water"][i].astype(np.int32)
        col.surface, col.filler, col.depth = surface[i], filler[i], depth[i]
        col.biome, col.temperature, col.river = s["biome"][i], s["temperature"][i], s["river"][i]
        col.badlands = col.biome == BADLANDS
        col.ice = (col.water > col.height) & (col.temperature < -0.55)
        col.deep, col.entrance = deep[i], entrance[i]
        col.grass = (grass[i] * 255).astype(np.uint8)
        col.foliage = (foliage[i] * 255).astype(np.uint8)
        col.water_tint = (water_tint[i] * 255).astype(np.uint8)
        col.lowest = int(top_padded[i].min())  # lowest ground here and next door: faces start there
        col.highest = int(max(top[i].max(), col.water.max()))
        _plant_trees(gen, col, slope[i])
        columns.append(col)
    return columns


def _plant_trees(gen, col, slope):
    """Pick tree spots on a jittered 4x4 grid, by biome, and keep all their blocks in the column."""
    rng = _rng(gen.seed, col.cx, col.cz, 7)
    chance, pick, size = rng.random((3, 4, 4))
    jitter = rng.integers(0, 4, (4, 4, 2))
    variant = rng.integers(0, 4, (4, 4))
    positions, blocks = [], []
    for i in range(4):
        for j in range(4):
            lx, lz = i * 4 + jitter[i, j, 0], j * 4 + jitter[i, j, 1]
            kinds = TREES.get(int(col.biome[lx, lz]))
            if not kinds or col.water[lx, lz] >= col.height[lx, lz] or slope[lx, lz] > 1:
                continue
            counts = np.array(list(kinds.values()))
            if chance[i, j] >= counts.sum() / 16:
                continue
            kind = list(kinds)[np.searchsorted(np.cumsum(counts) / counts.sum(), pick[i, j])]
            if col.surface[lx, lz] not in TREE_GROUND.get(kind, (GRASS, PODZOL, SNOW)):
                continue
            lo, hi = TREE_HEIGHTS[kind]
            tree = tree_blocks(kind, lo + int(size[i, j] * (hi - lo)), int(variant[i, j]))
            base = np.array([col.cx * CHUNK + lx, col.height[lx, lz] + 1, col.cz * CHUNK + lz])
            positions.append(tree[:, :3] + base)
            blocks.append(tree[:, 3])
    if positions:
        col.tree_pos = np.concatenate(positions).astype(np.int32)
        col.tree_block = np.concatenate(blocks).astype(np.uint8)
        col.tree_top = int(col.tree_pos[:, 1].max())
    else:
        col.tree_pos, col.tree_block, col.tree_top = np.zeros((0, 3), np.int32), np.zeros(0, np.uint8), -1


def _generate_section(gen, cols, cx, cy, cz):
    col = cols[(cx, cz)]
    y0 = cy * CHUNK
    tree_top = max(c.tree_top for c in cols.values())
    if y0 < 0 or y0 > max(col.highest, tree_top):
        return AIR
    ys = (y0 + np.arange(CHUNK))[None, :, None]
    depth = col.height[:, None, :] - ys  # 0 at the surface block, > 0 below it
    stone = np.where(ys < col.deep[:, None, :], DEEPSLATE, STONE)
    blocks = np.where(depth > col.depth[:, None, :], stone, col.filler[:, None, :])
    blocks = np.where(depth == 0, col.surface[:, None, :], blocks)
    bands = BANDS[(ys + 7 * np.sign(col.cx)) % len(BANDS)]
    blocks = np.where(col.badlands[:, None, :] & (depth > 0) & (depth <= 40), bands, blocks)
    water = (depth < 0) & (ys <= col.water[:, None, :])
    blocks = np.where(depth < 0, AIR, blocks)
    blocks = np.where(water, WATER, blocks)
    blocks = np.where(water & (ys == col.water[:, None, :]) & col.ice[:, None, :], ICE, blocks)
    blocks = np.ascontiguousarray(np.broadcast_to(blocks, (CHUNK, CHUNK, CHUNK)), dtype=np.uint8)

    x0, z0 = cx * CHUNK, cz * CHUNK
    if y0 <= col.height.max() - 2:
        _carve_caves(gen, blocks, x0, y0, z0, col, depth)
        _add_ores(gen, blocks, cx, cy, cz, y0)
    if y0 == 0:  # bedrock floor, ragged on top
        rough = _rng(gen.seed, cx, cz, 3).random((CHUNK, 3, CHUNK)) < np.array([1.0, 0.5, 0.2])[None, :, None]
        blocks[:, :3, :][rough] = BEDROCK
    if tree_top >= y0:
        _stamp_trees(blocks, cols.values(), x0, y0, z0)
    first = blocks.flat[0]
    if (blocks == first).all():
        return int(first)
    return blocks


def _upsample(lattice):
    """Trilinear interpolation from a 5x5x5 lattice (one value every 4 blocks) to 16x16x16 blocks."""
    t = np.arange(CHUNK) / 4
    i0 = t.astype(int)
    for axis in range(3):
        shape = [1, 1, 1]
        shape[axis] = CHUNK
        w = (t - i0).reshape(shape)
        lattice = np.take(lattice, i0, axis=axis) * (1 - w) + np.take(lattice, i0 + 1, axis=axis) * w
    return lattice


def _carve_caves(gen, blocks, x0, y0, z0, col, depth):
    """Winding tunnels where two 3D noises are both near zero, and big caverns deeper down. The
    noise is computed every 4 blocks and blended in between, which is much faster."""
    g = np.arange(5) * 4.0
    gx, gy, gz = np.meshgrid(x0 + g, y0 + g, z0 + g, indexing="ij")
    a = gen.caves_a.noise3(gx / 72, gy / 44, gz / 72)
    b = gen.caves_b.noise3(gx / 72, gy / 44, gz / 72)
    tunnels = _upsample(a * a + b * b) < 0.011
    caverns = _upsample(gen.caverns.fbm3(gx / 160, gy / 70, gz / 160, 2)) > 0.42
    ys = (y0 + np.arange(CHUNK))[None, :, None]
    underwater = (col.water >= col.height)[:, None, :]
    # Keep a roof of 4 blocks (8 under water), except at cave entrances
    room = np.where(underwater, depth > 8, (depth > 4) | (col.entrance[:, None, :] & (depth >= 0)))
    blocks[(tunnels | (caverns & (depth > 30))) & room & (ys > 5)] = AIR


def _add_ores(gen, blocks, cx, cy, cz, y0):
    """Ore veins: short random walks through the stone."""
    rng = _rng(gen.seed, cx, cy, cz, 11)
    for block, per_section, top, size in ORES:
        count = rng.poisson(per_section) if y0 <= top else 0
        if not count:
            continue
        walk = rng.integers(0, 16, (count, 1, 3)) + np.cumsum(rng.integers(-1, 2, (count, size, 3)), axis=1)
        p = np.clip(walk, 0, 15).reshape(-1, 3)
        p = p[p[:, 1] + y0 <= top]
        here = blocks[p[:, 0], p[:, 1], p[:, 2]]
        p = p[(here == STONE) | (here == DEEPSLATE)]
        blocks[p[:, 0], p[:, 1], p[:, 2]] = block


def _stamp_trees(blocks, cols, x0, y0, z0):
    """Copy into the section the tree blocks (from this column and its neighbors) that fall inside."""
    cols = [c for c in cols if len(c.tree_pos)]
    if not cols:
        return
    pos = np.concatenate([c.tree_pos for c in cols]) - np.array([x0, y0, z0])
    kind = np.concatenate([c.tree_block for c in cols])
    inside = np.all((pos >= 0) & (pos < CHUNK), axis=1)
    pos, kind = pos[inside], kind[inside]
    leaf = np.isin(kind, LEAF_BLOCKS)
    p, k = pos[leaf], kind[leaf]
    free = blocks[p[:, 0], p[:, 1], p[:, 2]] == AIR  # leaves only grow into air
    blocks[p[free, 0], p[free, 1], p[free, 2]] = k[free]
    p, k = pos[~leaf], kind[~leaf]
    here = blocks[p[:, 0], p[:, 1], p[:, 2]]
    free = (here == AIR) | np.isin(here, LEAF_BLOCKS)  # trunks push leaves aside
    blocks[p[free, 0], p[free, 1], p[free, 2]] = k[free]
