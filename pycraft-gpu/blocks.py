"""Block types, their properties, and a procedurally generated texture atlas (16x16 pixels per tile)."""
import numpy as np

TILE = 16
ATLAS_TILES = 8  # the atlas is 8x8 tiles = 128x128 pixels

(AIR, GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, SAND, BRICK,
 GLASS, WATER, COAL_ORE, IRON_ORE, BEDROCK) = range(15)
BLOCK_NAMES = ["Air", "Grass", "Dirt", "Stone", "Cobblestone", "Planks", "Log", "Leaves", "Sand", "Brick",
               "Glass", "Water", "Coal ore", "Iron ore", "Bedrock"]
NUM_BLOCKS = len(BLOCK_NAMES)

# Blocks the player can pick in the inventory (E)
PLACEABLE = [GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, SAND, BRICK, GLASS, WATER, COAL_ORE, IRON_ORE]
DEFAULT_HOTBAR = [GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, GLASS, BRICK]


def _flags(*blocks):
    table = np.zeros(NUM_BLOCKS, dtype=bool)
    table[list(blocks)] = True
    return table


# Properties, as lookup tables indexed by block id (they also work on whole NumPy arrays of blocks)
OPAQUE = ~_flags(AIR, LEAVES, GLASS, WATER)  # hides the faces of the blocks next to it
SOLID = ~_flags(AIR, WATER)  # the player collides with it
CUTOUT = _flags(LEAVES, GLASS)  # see-through where the texture is transparent
SELF_CULL = _flags(GLASS, WATER)  # no faces between two blocks of this same type
TARGETABLE = ~_flags(AIR, WATER)  # can be aimed at and broken
UNBREAKABLE = _flags(BEDROCK)

# Tile numbers inside the atlas
(T_GRASS_TOP, T_GRASS_SIDE, T_DIRT, T_STONE, T_COBBLE, T_PLANKS, T_LOG_SIDE, T_LOG_TOP, T_LEAVES,
 T_SAND, T_BRICK, T_GLASS, T_WATER, T_COAL, T_IRON, T_BEDROCK) = range(16)


def _faces(side, top=None, bottom=None):
    # Face order used everywhere: +x, -x, +y (top), -y (bottom), +z, -z
    top = side if top is None else top
    bottom = top if bottom is None else bottom
    return [side, side, top, bottom, side, side]


# BLOCK_TILES[block][face] -> atlas tile number
BLOCK_TILES = np.array([
    _faces(0),  # air, never drawn
    _faces(T_GRASS_SIDE, T_GRASS_TOP, T_DIRT),
    _faces(T_DIRT),
    _faces(T_STONE),
    _faces(T_COBBLE),
    _faces(T_PLANKS),
    _faces(T_LOG_SIDE, T_LOG_TOP),
    _faces(T_LEAVES),
    _faces(T_SAND),
    _faces(T_BRICK),
    _faces(T_GLASS),
    _faces(T_WATER),
    _faces(T_COAL),
    _faces(T_IRON),
    _faces(T_BEDROCK),
], dtype=np.int32)


def _noisy(rng, base, var):
    shade = 1 + rng.uniform(-var, var, (TILE, TILE, 1))
    return np.array(base, dtype=float) * shade


def _masonry(rng, base, mortar, row_h, brick_w, var, random_offsets=False):
    img = _noisy(rng, base, var)
    for row in range(TILE // row_h):
        offset = rng.integers(0, brick_w) if random_offsets else (row % 2) * brick_w // 2
        ys = slice(row * row_h, (row + 1) * row_h)
        # Each brick/stone gets its own brightness
        for start in range(-brick_w, TILE, brick_w):
            xs = slice(max(0, start + offset), max(0, start + offset + brick_w))
            img[ys, xs] *= rng.uniform(0.85, 1.1)
        img[row * row_h + row_h - 1, :] = mortar
        for x in range(TILE):
            if (x + offset) % brick_w == brick_w - 1:
                img[ys, x] = mortar
    return img


def _ore(rng, stone, color, count):
    img = stone.copy()
    for _ in range(count):
        y, x = rng.integers(1, TILE - 2, 2)
        img[y:y + 2, x:x + 2] = _noisy(rng, color, 0.15)[:2, :2]
    return img


def build_atlas(seed=7):
    """Return the texture atlas as a (128, 128, 4) uint8 RGBA array (alpha 0 = see-through)."""
    rng = np.random.default_rng(seed)
    tiles = {}
    alpha = {}

    tiles[T_GRASS_TOP] = _noisy(rng, (95, 159, 53), 0.18)

    dirt = _noisy(rng, (134, 96, 67), 0.12)
    dirt[rng.random((TILE, TILE)) < 0.12] *= 0.72
    tiles[T_DIRT] = dirt

    side = dirt.copy()
    for x in range(TILE):
        depth = rng.integers(2, 6)
        side[:depth, x] = tiles[T_GRASS_TOP][:depth, x]
    tiles[T_GRASS_SIDE] = side

    stone = _noisy(rng, (125, 125, 125), 0.08)
    for _ in range(10):
        y, x = rng.integers(0, TILE - 1, 2)
        stone[y, x:x + 2] *= 0.75
    tiles[T_STONE] = stone
    tiles[T_COAL] = _ore(rng, stone, (30, 30, 30), 6)
    tiles[T_IRON] = _ore(rng, stone, (216, 175, 147), 6)
    tiles[T_BEDROCK] = _noisy(rng, (70, 70, 70), 0.6)

    tiles[T_COBBLE] = _masonry(rng, (122, 122, 122), (72, 72, 72), 4, 5, 0.12, random_offsets=True)
    tiles[T_BRICK] = _masonry(rng, (150, 74, 58), (178, 170, 160), 4, 8, 0.08)

    planks = _noisy(rng, (162, 130, 78), 0.06)
    for row in range(4):
        planks[row * 4 + 3, :] *= 0.65  # gap between boards
        joint = rng.integers(0, TILE)
        planks[row * 4:row * 4 + 3, joint] *= 0.75
        planks[row * 4 + rng.integers(0, 3), rng.integers(0, TILE, 5)] *= 0.85  # grain
    tiles[T_PLANKS] = planks

    tiles[T_LOG_SIDE] = _noisy(rng, (102, 81, 51), 0.05) * rng.uniform(0.72, 1.12, (1, TILE, 1))

    ys, xs = np.mgrid[0:TILE, 0:TILE]
    ring = np.maximum(abs(xs - 7.5), abs(ys - 7.5))
    top = _noisy(rng, (176, 143, 90), 0.05)
    top[(ring.astype(int) % 3) == 0] *= 0.8
    top[ring > 6.5] = tiles[T_LOG_SIDE][ring > 6.5]
    tiles[T_LOG_TOP] = top

    tiles[T_LEAVES] = _noisy(rng, (58, 122, 40), 0.25)
    alpha[T_LEAVES] = rng.random((TILE, TILE)) >= 0.18

    tiles[T_SAND] = _noisy(rng, (219, 207, 163), 0.05)

    glass = np.full((TILE, TILE, 3), (215, 235, 240), dtype=float)
    glass_alpha = (ring > 6.5)  # frame
    for i in range(3):  # a few diagonal shine streaks
        glass_alpha |= (xs - ys == 4 + i) & (xs < 10)
    tiles[T_GLASS], alpha[T_GLASS] = glass, glass_alpha

    tiles[T_WATER] = _noisy(rng, (45, 90, 200), 0.1)

    atlas = np.zeros((TILE * ATLAS_TILES, TILE * ATLAS_TILES, 4))
    for t, img in tiles.items():
        ty, tx = divmod(t, ATLAS_TILES)
        cell = (slice(ty * TILE, (ty + 1) * TILE), slice(tx * TILE, (tx + 1) * TILE))
        atlas[cell + (slice(0, 3),)] = img
        atlas[cell + (3,)] = 255 * alpha.get(t, np.ones((TILE, TILE), dtype=bool))
    return np.clip(atlas, 0, 255).astype(np.uint8)
