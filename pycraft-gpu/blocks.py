"""Block types, their properties, and a procedurally generated texture atlas (16x16 pixels per tile)."""
import numpy as np

TILE = 16
ATLAS_TILES = 8  # the atlas is 8x8 tiles = 128x128 pixels
TINT_ALPHA = 200  # texels with this alpha take the biome color (grass, leaves, water)

(AIR, GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, SAND, BRICK, GLASS, WATER, COAL_ORE, IRON_ORE,
 BEDROCK, SNOW, ICE, GRAVEL, SANDSTONE, RED_SAND, TERRACOTTA, ORANGE_TERRACOTTA, WHITE_TERRACOTTA, PODZOL,
 SPRUCE_LOG, SPRUCE_LEAVES, BIRCH_LOG, BIRCH_LEAVES, JUNGLE_LOG, JUNGLE_LEAVES, ACACIA_LOG, ACACIA_LEAVES,
 CACTUS, GOLD_ORE, DIAMOND_ORE, DEEPSLATE, CLAY, MUD) = range(38)
BLOCK_NAMES = ["Air", "Grass", "Dirt", "Stone", "Cobblestone", "Planks", "Oak log", "Oak leaves", "Sand", "Brick",
               "Glass", "Water", "Coal ore", "Iron ore", "Bedrock", "Snow", "Ice", "Gravel", "Sandstone",
               "Red sand", "Terracotta", "Orange terracotta", "White terracotta", "Podzol", "Spruce log",
               "Spruce leaves", "Birch log", "Birch leaves", "Jungle log", "Jungle leaves", "Acacia log",
               "Acacia leaves", "Cactus", "Gold ore", "Diamond ore", "Deepslate", "Clay", "Mud"]
NUM_BLOCKS = len(BLOCK_NAMES)

# Blocks the player can pick in the inventory (E)
PLACEABLE = [b for b in range(1, NUM_BLOCKS) if b != BEDROCK]
DEFAULT_HOTBAR = [GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, GLASS, BRICK]


def _flags(*blocks):
    table = np.zeros(NUM_BLOCKS, dtype=bool)
    table[list(blocks)] = True
    return table


ALL_LEAVES = (LEAVES, SPRUCE_LEAVES, BIRCH_LEAVES, JUNGLE_LEAVES, ACACIA_LEAVES)

# Properties, as lookup tables indexed by block id (they also work on whole NumPy arrays of blocks)
OPAQUE = ~_flags(AIR, GLASS, WATER, *ALL_LEAVES)  # hides the faces of the blocks next to it
SOLID = ~_flags(AIR, WATER)  # the player collides with it
CUTOUT = _flags(GLASS, *ALL_LEAVES)  # see-through where the texture is transparent
SELF_CULL = _flags(GLASS, WATER, *ALL_LEAVES)  # no faces between two blocks of this same type
TARGETABLE = ~_flags(AIR, WATER)  # can be aimed at and broken
UNBREAKABLE = _flags(BEDROCK)

# Tile numbers inside the atlas
(T_GRASS_TOP, T_GRASS_SIDE, T_DIRT, T_STONE, T_COBBLE, T_PLANKS, T_LOG_SIDE, T_LOG_TOP, T_LEAVES,
 T_SAND, T_BRICK, T_GLASS, T_WATER, T_COAL, T_IRON, T_BEDROCK, T_SNOW, T_ICE, T_GRAVEL, T_SANDSTONE_TOP,
 T_SANDSTONE_SIDE, T_RED_SAND, T_TERRACOTTA, T_ORANGE_TERRACOTTA, T_WHITE_TERRACOTTA, T_PODZOL_TOP,
 T_PODZOL_SIDE, T_SPRUCE_LOG_SIDE, T_SPRUCE_LOG_TOP, T_SPRUCE_LEAVES, T_BIRCH_LOG_SIDE, T_BIRCH_LOG_TOP,
 T_BIRCH_LEAVES, T_JUNGLE_LOG_SIDE, T_JUNGLE_LOG_TOP, T_JUNGLE_LEAVES, T_ACACIA_LOG_SIDE, T_ACACIA_LOG_TOP,
 T_ACACIA_LEAVES, T_CACTUS_SIDE, T_CACTUS_TOP, T_GOLD, T_DIAMOND, T_DEEPSLATE, T_CLAY, T_MUD) = range(46)


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
    _faces(T_SNOW),
    _faces(T_ICE),
    _faces(T_GRAVEL),
    _faces(T_SANDSTONE_SIDE, T_SANDSTONE_TOP),
    _faces(T_RED_SAND),
    _faces(T_TERRACOTTA),
    _faces(T_ORANGE_TERRACOTTA),
    _faces(T_WHITE_TERRACOTTA),
    _faces(T_PODZOL_SIDE, T_PODZOL_TOP, T_DIRT),
    _faces(T_SPRUCE_LOG_SIDE, T_SPRUCE_LOG_TOP),
    _faces(T_SPRUCE_LEAVES),
    _faces(T_BIRCH_LOG_SIDE, T_BIRCH_LOG_TOP),
    _faces(T_BIRCH_LEAVES),
    _faces(T_JUNGLE_LOG_SIDE, T_JUNGLE_LOG_TOP),
    _faces(T_JUNGLE_LEAVES),
    _faces(T_ACACIA_LOG_SIDE, T_ACACIA_LOG_TOP),
    _faces(T_ACACIA_LEAVES),
    _faces(T_CACTUS_SIDE, T_CACTUS_TOP),
    _faces(T_GOLD),
    _faces(T_DIAMOND),
    _faces(T_DEEPSLATE),
    _faces(T_CLAY),
    _faces(T_MUD),
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


def _bark(rng, base, var, streak):
    """Log side: vertical streaks of darker and lighter bark."""
    return _noisy(rng, base, var) * rng.uniform(1 - streak, 1 + streak * 0.6, (1, TILE, 1))


def _rings(rng, inner, bark_side):
    """Log top: growth rings, with the bark around the edge."""
    ys, xs = np.mgrid[0:TILE, 0:TILE]
    ring = np.maximum(abs(xs - 7.5), abs(ys - 7.5))
    top = _noisy(rng, inner, 0.05)
    top[(ring.astype(int) % 3) == 0] *= 0.8
    top[ring > 6.5] = bark_side[ring > 6.5]
    return top


def _side_with_top(rng, below, top, lo=2, hi=6):
    """A side texture: the 'below' texture with a ragged strip of 'top' along the upper edge."""
    side = below.copy()
    strip = np.zeros((TILE, TILE), dtype=bool)
    for x in range(TILE):
        depth = rng.integers(lo, hi)
        side[:depth, x] = top[:depth, x]
        strip[:depth, x] = True
    return side, strip


def build_atlas(seed=7):
    """Return the texture atlas as a (128, 128, 4) uint8 RGBA array.

    Alpha 0 = see-through, TINT_ALPHA = colored by the biome (the texture itself is grey there)."""
    rng = np.random.default_rng(seed)
    tiles, alpha = {}, {}
    tint = {}  # tile -> mask of texels colored by the biome
    full = np.ones((TILE, TILE), dtype=bool)

    grey_grass = _noisy(rng, (204, 204, 204), 0.18)
    tiles[T_GRASS_TOP], tint[T_GRASS_TOP] = grey_grass, full

    dirt = _noisy(rng, (134, 96, 67), 0.12)
    dirt[rng.random((TILE, TILE)) < 0.12] *= 0.72
    tiles[T_DIRT] = dirt
    tiles[T_GRASS_SIDE], tint[T_GRASS_SIDE] = _side_with_top(rng, dirt, grey_grass)

    stone = _noisy(rng, (125, 125, 125), 0.08)
    for _ in range(10):
        y, x = rng.integers(0, TILE - 1, 2)
        stone[y, x:x + 2] *= 0.75
    tiles[T_STONE] = stone
    tiles[T_COAL] = _ore(rng, stone, (30, 30, 30), 6)
    tiles[T_IRON] = _ore(rng, stone, (216, 175, 147), 6)
    tiles[T_GOLD] = _ore(rng, stone, (250, 215, 60), 5)
    tiles[T_DIAMOND] = _ore(rng, stone, (95, 225, 215), 5)
    tiles[T_BEDROCK] = _noisy(rng, (70, 70, 70), 0.6)
    deepslate = _noisy(rng, (78, 78, 84), 0.1) * rng.uniform(0.85, 1.1, (TILE, 1, 1))  # layered
    tiles[T_DEEPSLATE] = deepslate

    tiles[T_COBBLE] = _masonry(rng, (122, 122, 122), (72, 72, 72), 4, 5, 0.12, random_offsets=True)
    tiles[T_BRICK] = _masonry(rng, (150, 74, 58), (178, 170, 160), 4, 8, 0.08)

    planks = _noisy(rng, (162, 130, 78), 0.06)
    for row in range(4):
        planks[row * 4 + 3, :] *= 0.65  # gap between boards
        joint = rng.integers(0, TILE)
        planks[row * 4:row * 4 + 3, joint] *= 0.75
        planks[row * 4 + rng.integers(0, 3), rng.integers(0, TILE, 5)] *= 0.85  # grain
    tiles[T_PLANKS] = planks

    # Logs and leaves of the five kinds of trees. Oak, jungle and acacia leaves take the biome color.
    for side_t, top_t, bark, inner, streak in [
            (T_LOG_SIDE, T_LOG_TOP, (102, 81, 51), (176, 143, 90), 0.28),
            (T_SPRUCE_LOG_SIDE, T_SPRUCE_LOG_TOP, (60, 42, 24), (120, 88, 52), 0.3),
            (T_JUNGLE_LOG_SIDE, T_JUNGLE_LOG_TOP, (88, 68, 28), (165, 118, 72), 0.25),
            (T_ACACIA_LOG_SIDE, T_ACACIA_LOG_TOP, (104, 98, 88), (175, 92, 50), 0.2)]:
        tiles[side_t] = _bark(rng, bark, 0.05, streak)
        tiles[top_t] = _rings(rng, inner, tiles[side_t])
    birch = _noisy(rng, (216, 214, 204), 0.04)
    for _ in range(9):  # black marks on the white bark
        y, x = rng.integers(0, TILE, 2)
        birch[y, x:x + rng.integers(2, 5)] = (40, 40, 36)
    tiles[T_BIRCH_LOG_SIDE] = birch
    tiles[T_BIRCH_LOG_TOP] = _rings(rng, (200, 180, 130), birch)

    for leaves_t, color, holes, tinted in [(T_LEAVES, (204, 204, 204), 0.18, True),
                                           (T_JUNGLE_LEAVES, (204, 204, 204), 0.12, True),
                                           (T_ACACIA_LEAVES, (204, 204, 204), 0.22, True),
                                           (T_SPRUCE_LEAVES, (46, 78, 46), 0.16, False),
                                           (T_BIRCH_LEAVES, (110, 150, 66), 0.18, False)]:
        tiles[leaves_t] = _noisy(rng, color, 0.25)
        alpha[leaves_t] = rng.random((TILE, TILE)) >= holes
        if tinted:
            tint[leaves_t] = full

    tiles[T_SAND] = _noisy(rng, (219, 207, 163), 0.05)
    tiles[T_RED_SAND] = _noisy(rng, (190, 102, 46), 0.06)
    sandstone_top = _noisy(rng, (216, 201, 150), 0.04)
    tiles[T_SANDSTONE_TOP] = sandstone_top
    side = _noisy(rng, (210, 193, 140), 0.04)
    side[[3, 4, 11]] *= 0.9  # horizontal layers
    side[:2] = sandstone_top[:2]
    tiles[T_SANDSTONE_SIDE] = side
    tiles[T_TERRACOTTA] = _noisy(rng, (152, 94, 67), 0.04)
    tiles[T_ORANGE_TERRACOTTA] = _noisy(rng, (162, 84, 38), 0.04)
    tiles[T_WHITE_TERRACOTTA] = _noisy(rng, (210, 178, 161), 0.04)
    tiles[T_CLAY] = _noisy(rng, (160, 166, 180), 0.04)
    tiles[T_MUD] = _noisy(rng, (62, 56, 56), 0.1)

    gravel = _noisy(rng, (128, 123, 118), 0.12)
    for _ in range(22):  # pebbles
        y, x = rng.integers(0, TILE - 1, 2)
        gravel[y:y + 2, x:x + 2] *= rng.uniform(0.6, 1.3)
    tiles[T_GRAVEL] = gravel

    tiles[T_SNOW] = _noisy(rng, (240, 245, 250), 0.04)
    ice = _noisy(rng, (160, 198, 245), 0.05)
    ys, xs = np.mgrid[0:TILE, 0:TILE]
    ice[(xs + 2 * ys) % 11 == 0] *= 1.12  # streaks
    tiles[T_ICE] = ice

    podzol = _noisy(rng, (110, 78, 38), 0.12)
    podzol[rng.random((TILE, TILE)) < 0.2] *= 0.65
    tiles[T_PODZOL_TOP] = podzol
    tiles[T_PODZOL_SIDE], _ = _side_with_top(rng, dirt, podzol, 2, 4)

    cactus = _noisy(rng, (78, 128, 40), 0.08)
    cactus[:, [0, 15]] *= 0.7
    cactus[:, [4, 11]] *= 0.82  # ridges
    cactus[rng.integers(0, TILE, 10), rng.choice([2, 7, 9, 13], 10)] = (220, 220, 180)  # spines
    tiles[T_CACTUS_SIDE] = cactus
    top = _noisy(rng, (100, 150, 52), 0.06)
    top[(np.maximum(abs(xs - 7.5), abs(ys - 7.5)) > 6.5)] *= 0.75
    tiles[T_CACTUS_TOP] = top

    ring = np.maximum(abs(xs - 7.5), abs(ys - 7.5))
    glass = np.full((TILE, TILE, 3), (215, 235, 240), dtype=float)
    glass_alpha = (ring > 6.5)  # frame
    for i in range(3):  # a few diagonal shine streaks
        glass_alpha |= (xs - ys == 4 + i) & (xs < 10)
    tiles[T_GLASS], alpha[T_GLASS] = glass, glass_alpha

    tiles[T_WATER], tint[T_WATER] = _noisy(rng, (204, 204, 204), 0.1), full

    atlas = np.zeros((TILE * ATLAS_TILES, TILE * ATLAS_TILES, 4))
    for t, img in tiles.items():
        ty, tx = divmod(t, ATLAS_TILES)
        cell = (slice(ty * TILE, (ty + 1) * TILE), slice(tx * TILE, (tx + 1) * TILE))
        a = np.where(alpha.get(t, full), 255.0, 0.0)
        a[(a > 0) & tint.get(t, ~full)] = TINT_ALPHA
        atlas[cell + (slice(0, 3),)] = img
        atlas[cell + (3,)] = a
    return np.clip(atlas, 0, 255).astype(np.uint8)


def block_colors(atlas):
    """Average color (0-1) of each block's top face, for the distant terrain. Tinted texels count as
    white: the distant terrain multiplies them by the biome color itself."""
    colors = np.zeros((NUM_BLOCKS, 3))
    for block in range(1, NUM_BLOCKS):
        t = BLOCK_TILES[block][2]
        ty, tx = divmod(int(t), ATLAS_TILES)
        cell = atlas[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE].astype(float)
        seen = cell[..., 3] > 0
        rgb = cell[..., :3][seen] / 255
        if (cell[..., 3][seen] == TINT_ALPHA).all():
            rgb = rgb / 0.8  # grey texels, about 204/255
        colors[block] = rgb.mean(axis=0)
    return colors
