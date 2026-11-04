"""Block types, their properties, and a procedurally generated texture atlas (16x16 pixels per tile)."""
import numpy as np

TILE = 16
ATLAS_TILES = 16  # the atlas is 16x16 tiles = 256x256 pixels
TINT_ALPHA = 200  # texels with this alpha take the biome color (grass, leaves, water)

(AIR, GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, SAND, BRICK, GLASS, WATER, COAL_ORE, IRON_ORE,
 BEDROCK, SNOW, ICE, GRAVEL, SANDSTONE, RED_SAND, TERRACOTTA, ORANGE_TERRACOTTA, WHITE_TERRACOTTA, PODZOL,
 SPRUCE_LOG, SPRUCE_LEAVES, BIRCH_LOG, BIRCH_LEAVES, JUNGLE_LOG, JUNGLE_LEAVES, ACACIA_LOG, ACACIA_LEAVES,
 CACTUS, GOLD_ORE, DIAMOND_ORE, DEEPSLATE, CLAY, MUD, MOSS) = range(39)
# Building blocks, numbered after the older ones: saved worlds keep the numbers of their blocks
(SPRUCE_PLANKS, BIRCH_PLANKS, JUNGLE_PLANKS, ACACIA_PLANKS, STONE_BRICKS, MOSSY_STONE_BRICKS, CRACKED_STONE_BRICKS,
 MOSSY_COBBLESTONE, SMOOTH_STONE, GRANITE, POLISHED_GRANITE, DIORITE, POLISHED_DIORITE, ANDESITE,
 POLISHED_ANDESITE, CUT_SANDSTONE, CHISELED_SANDSTONE, RED_SANDSTONE, CUT_RED_SANDSTONE, COAL_BLOCK, IRON_BLOCK,
 GOLD_BLOCK, DIAMOND_BLOCK, OBSIDIAN, BOOKSHELF, HAY_BALE, PUMPKIN, MELON, WHITE_WOOL, ORANGE_WOOL, MAGENTA_WOOL,
 LIGHT_BLUE_WOOL, YELLOW_WOOL, LIME_WOOL, PINK_WOOL, GRAY_WOOL, LIGHT_GRAY_WOOL, CYAN_WOOL, PURPLE_WOOL, BLUE_WOOL,
 BROWN_WOOL, GREEN_WOOL, RED_WOOL, BLACK_WOOL, DEEPSLATE_BRICKS, POLISHED_DEEPSLATE, MUD_BRICKS, QUARTZ_BLOCK,
 YELLOW_TERRACOTTA, RED_TERRACOTTA, BROWN_TERRACOTTA, LIGHT_GRAY_TERRACOTTA) = range(MOSS + 1, MOSS + 53)
BLOCK_NAMES = ["Air", "Grass", "Dirt", "Stone", "Cobblestone", "Oak planks", "Oak log", "Oak leaves", "Sand", "Brick",
               "Glass", "Water", "Coal ore", "Iron ore", "Bedrock", "Snow", "Ice", "Gravel", "Sandstone",
               "Red sand", "Terracotta", "Orange terracotta", "White terracotta", "Podzol", "Spruce log",
               "Spruce leaves", "Birch log", "Birch leaves", "Jungle log", "Jungle leaves", "Acacia log",
               "Acacia leaves", "Cactus", "Gold ore", "Diamond ore", "Deepslate", "Clay", "Mud",
               "Moss",
               "Spruce planks", "Birch planks", "Jungle planks", "Acacia planks", "Stone bricks",
               "Mossy stone bricks", "Cracked stone bricks", "Mossy cobblestone", "Smooth stone", "Granite",
               "Polished granite", "Diorite", "Polished diorite", "Andesite", "Polished andesite",
               "Cut sandstone", "Chiseled sandstone", "Red sandstone", "Cut red sandstone", "Block of coal",
               "Block of iron", "Block of gold", "Block of diamond", "Obsidian", "Bookshelf", "Hay bale",
               "Pumpkin", "Melon", "White wool", "Orange wool", "Magenta wool", "Light blue wool",
               "Yellow wool", "Lime wool", "Pink wool", "Gray wool", "Light gray wool", "Cyan wool",
               "Purple wool", "Blue wool", "Brown wool", "Green wool", "Red wool", "Black wool",
               "Deepslate bricks", "Polished deepslate", "Mud bricks", "Quartz block", "Yellow terracotta",
               "Red terracotta", "Brown terracotta", "Light gray terracotta"]
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
 T_ACACIA_LEAVES, T_CACTUS_SIDE, T_CACTUS_TOP, T_GOLD, T_DIAMOND, T_DEEPSLATE, T_CLAY, T_MUD,
 T_MOSS) = range(47)
(T_SPRUCE_PLANKS, T_BIRCH_PLANKS, T_JUNGLE_PLANKS, T_ACACIA_PLANKS, T_STONE_BRICKS, T_MOSSY_STONE_BRICKS,
 T_CRACKED_STONE_BRICKS, T_MOSSY_COBBLE, T_SMOOTH_STONE, T_GRANITE, T_POLISHED_GRANITE, T_DIORITE,
 T_POLISHED_DIORITE, T_ANDESITE, T_POLISHED_ANDESITE, T_CUT_SANDSTONE, T_CHISELED_SANDSTONE, T_RED_SANDSTONE_TOP,
 T_RED_SANDSTONE_SIDE, T_CUT_RED_SANDSTONE, T_COAL_BLOCK, T_IRON_BLOCK, T_GOLD_BLOCK, T_DIAMOND_BLOCK, T_OBSIDIAN,
 T_BOOKSHELF, T_HAY_SIDE, T_HAY_TOP, T_PUMPKIN_SIDE, T_PUMPKIN_TOP, T_MELON_SIDE, T_MELON_TOP, T_WHITE_WOOL,
 T_ORANGE_WOOL, T_MAGENTA_WOOL, T_LIGHT_BLUE_WOOL, T_YELLOW_WOOL, T_LIME_WOOL, T_PINK_WOOL, T_GRAY_WOOL,
 T_LIGHT_GRAY_WOOL, T_CYAN_WOOL, T_PURPLE_WOOL, T_BLUE_WOOL, T_BROWN_WOOL, T_GREEN_WOOL, T_RED_WOOL, T_BLACK_WOOL,
 T_DEEPSLATE_BRICKS, T_POLISHED_DEEPSLATE, T_MUD_BRICKS, T_QUARTZ, T_YELLOW_TERRACOTTA, T_RED_TERRACOTTA,
 T_BROWN_TERRACOTTA, T_LIGHT_GRAY_TERRACOTTA) = range(T_MOSS + 1, T_MOSS + 57)


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
    _faces(T_MOSS),
    _faces(T_SPRUCE_PLANKS),
    _faces(T_BIRCH_PLANKS),
    _faces(T_JUNGLE_PLANKS),
    _faces(T_ACACIA_PLANKS),
    _faces(T_STONE_BRICKS),
    _faces(T_MOSSY_STONE_BRICKS),
    _faces(T_CRACKED_STONE_BRICKS),
    _faces(T_MOSSY_COBBLE),
    _faces(T_SMOOTH_STONE),
    _faces(T_GRANITE),
    _faces(T_POLISHED_GRANITE),
    _faces(T_DIORITE),
    _faces(T_POLISHED_DIORITE),
    _faces(T_ANDESITE),
    _faces(T_POLISHED_ANDESITE),
    _faces(T_CUT_SANDSTONE, T_SANDSTONE_TOP),
    _faces(T_CHISELED_SANDSTONE, T_SANDSTONE_TOP),
    _faces(T_RED_SANDSTONE_SIDE, T_RED_SANDSTONE_TOP),
    _faces(T_CUT_RED_SANDSTONE, T_RED_SANDSTONE_TOP),
    _faces(T_COAL_BLOCK),
    _faces(T_IRON_BLOCK),
    _faces(T_GOLD_BLOCK),
    _faces(T_DIAMOND_BLOCK),
    _faces(T_OBSIDIAN),
    _faces(T_BOOKSHELF, T_PLANKS),
    _faces(T_HAY_SIDE, T_HAY_TOP),
    _faces(T_PUMPKIN_SIDE, T_PUMPKIN_TOP),
    _faces(T_MELON_SIDE, T_MELON_TOP),
    _faces(T_WHITE_WOOL),
    _faces(T_ORANGE_WOOL),
    _faces(T_MAGENTA_WOOL),
    _faces(T_LIGHT_BLUE_WOOL),
    _faces(T_YELLOW_WOOL),
    _faces(T_LIME_WOOL),
    _faces(T_PINK_WOOL),
    _faces(T_GRAY_WOOL),
    _faces(T_LIGHT_GRAY_WOOL),
    _faces(T_CYAN_WOOL),
    _faces(T_PURPLE_WOOL),
    _faces(T_BLUE_WOOL),
    _faces(T_BROWN_WOOL),
    _faces(T_GREEN_WOOL),
    _faces(T_RED_WOOL),
    _faces(T_BLACK_WOOL),
    _faces(T_DEEPSLATE_BRICKS),
    _faces(T_POLISHED_DEEPSLATE),
    _faces(T_MUD_BRICKS),
    _faces(T_QUARTZ),
    _faces(T_YELLOW_TERRACOTTA),
    _faces(T_RED_TERRACOTTA),
    _faces(T_BROWN_TERRACOTTA),
    _faces(T_LIGHT_GRAY_TERRACOTTA),
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


def _planks(rng, base):
    """Four boards, with gaps between them, a joint in each and some grain."""
    planks = _noisy(rng, base, 0.06)
    for row in range(4):
        planks[row * 4 + 3, :] *= 0.65  # gap between boards
        joint = rng.integers(0, TILE)
        planks[row * 4:row * 4 + 3, joint] *= 0.75
        planks[row * 4 + rng.integers(0, 3), rng.integers(0, TILE, 5)] *= 0.85  # grain
    return planks


def _blobs(rng, share, cells=4):
    """A mask of soft round patches covering about 'share' of the tile (moss, stains)."""
    coarse = rng.random((cells + 1, cells + 1))
    t = np.linspace(0, cells, TILE, endpoint=False)
    i, f = t.astype(int), t % 1
    f = f * f * (3 - 2 * f)
    rows = coarse[i] * (1 - f)[:, None] + coarse[i + 1] * f[:, None]  # blend the coarse grid in y...
    field = rows[:, i] * (1 - f) + rows[:, i + 1] * f  # ...then in x
    field += rng.uniform(-0.12, 0.12, (TILE, TILE))
    return field > np.quantile(field, 1 - share)


def _speckled(rng, base, var, specks):
    """A rock with grains of other colors: specks is a list of (color, share of the texels)."""
    img = _noisy(rng, base, var)
    for color, share in specks:
        grains = rng.random((TILE, TILE)) < share
        img[grains] = _noisy(rng, color, 0.08)[grains]
    return img


def _bevel(img, light=1.12, dark=0.78):
    """A raised square: lit along the top and left edges, shaded along the bottom and right ones."""
    img = img.copy()
    img[0, :] *= light
    img[:, 0] *= light
    img[-1, :] *= dark
    img[:, -1] *= dark
    return img


def _wool_weave(rng):
    """The pattern of woven threads shared by every color of wool, as brightness around 1."""
    ys, xs = np.mgrid[0:TILE, 0:TILE]
    across = (xs // 4 + ys // 4) % 2 == 0  # squares of 4x4 texels, threads across then down, in turn
    weave = np.where(np.where(across, ys, xs) % 2 == 0, 1.05, 0.93)
    return weave[..., None] * (1 + rng.uniform(-0.04, 0.04, (TILE, TILE, 1)))


def build_atlas(seed=7):
    """Return the texture atlas as a (256, 256, 4) uint8 RGBA array.

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

    tiles[T_PLANKS] = _planks(rng, (162, 130, 78))

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

    # Moss over dark lava rock: olive clumps, the rock showing through in gaps
    moss = _noisy(rng, (96, 120, 52), 0.14)
    for _ in range(26):  # the bumps of a thick carpet
        y, x = rng.integers(0, TILE - 2, 2)
        moss[y:y + 2, x:x + 2] *= rng.uniform(0.7, 1.3)
    moss[rng.random((TILE, TILE)) < 0.12] *= 0.45
    tiles[T_MOSS] = moss

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

    # --- Building blocks (made after the older tiles, which then stay exactly as they were) ---
    for planks_t, color in [(T_SPRUCE_PLANKS, (115, 85, 52)), (T_BIRCH_PLANKS, (196, 179, 123)),
                            (T_JUNGLE_PLANKS, (160, 115, 81)), (T_ACACIA_PLANKS, (169, 92, 51))]:
        tiles[planks_t] = _planks(rng, color)

    moss_green = (84, 108, 50)
    bricks = _masonry(rng, (124, 124, 124), (84, 84, 84), 8, 16, 0.05)
    tiles[T_STONE_BRICKS] = bricks
    mossy = bricks.copy()
    patches = _blobs(rng, 0.35)
    mossy[patches] = _noisy(rng, moss_green, 0.18)[patches]
    tiles[T_MOSSY_STONE_BRICKS] = mossy
    cracked = bricks.copy()
    for _ in range(3):  # cracks: short zigzags across the bricks
        y, x = rng.integers(1, TILE - 1), rng.integers(0, 6)
        for _ in range(rng.integers(6, 11)):
            cracked[y, x] *= 0.55
            y, x = int(np.clip(y + rng.integers(-1, 2), 0, TILE - 1)), x + 1
            if x >= TILE:
                break
    tiles[T_CRACKED_STONE_BRICKS] = cracked
    cobble = _masonry(rng, (122, 122, 122), (72, 72, 72), 4, 5, 0.12, random_offsets=True)
    patches = _blobs(rng, 0.3)
    cobble[patches] = _noisy(rng, moss_green, 0.2)[patches]
    tiles[T_MOSSY_COBBLE] = cobble
    smooth = _noisy(rng, (158, 158, 158), 0.03)
    smooth[ring > 6.5] *= 0.82  # a darker rim
    tiles[T_SMOOTH_STONE] = smooth

    # Rocks, raw and polished: the polished ones are smoother squares with a raised edge
    for raw_t, polished_t, base, specks in [
            (T_GRANITE, T_POLISHED_GRANITE, (152, 106, 88), [((184, 134, 112), 0.18), ((104, 70, 62), 0.12)]),
            (T_DIORITE, T_POLISHED_DIORITE, (190, 190, 192), [((120, 120, 122), 0.16), ((236, 236, 236), 0.12)]),
            (T_ANDESITE, T_POLISHED_ANDESITE, (136, 136, 137), [((108, 108, 110), 0.18), ((164, 164, 164), 0.12)])]:
        tiles[raw_t] = _speckled(rng, base, 0.06, specks)
        tiles[polished_t] = _bevel(_speckled(rng, base, 0.03, [(color, share / 3) for color, share in specks]))

    def cut(top_color, side_color):  # cut sandstone: two smooth slabs, one above the other
        img = _noisy(rng, side_color, 0.03)
        img[[0, 8]] = _noisy(rng, top_color, 0.03)[[0, 8]] * 1.06
        img[[7, 15]] *= 0.84
        return img

    tiles[T_CUT_SANDSTONE] = cut((216, 201, 150), (212, 197, 145))
    chiseled = _noisy(rng, (212, 197, 145), 0.03)
    chiseled[[2, 13]] *= 0.82  # a carved band in the middle, with a pattern of nested squares
    inside = (ys > 2) & (ys < 13)
    middle = np.maximum(abs(xs - 7.5), abs(ys - 7.5) * 1.6)
    chiseled[inside & (middle.astype(int) % 3 == 1)] *= 0.8
    chiseled[:2] = sandstone_top[:2]
    chiseled[14:] = sandstone_top[14:]
    tiles[T_CHISELED_SANDSTONE] = chiseled
    red_top = _noisy(rng, (181, 98, 33), 0.04)
    tiles[T_RED_SANDSTONE_TOP] = red_top
    red_side = _noisy(rng, (172, 90, 30), 0.04)
    red_side[[3, 4, 11]] *= 0.88  # horizontal layers
    red_side[:2] = red_top[:2]
    tiles[T_RED_SANDSTONE_SIDE] = red_side
    tiles[T_CUT_RED_SANDSTONE] = cut((181, 98, 33), (174, 92, 31))

    # Blocks of ore: metal plates, diamond facets, coal lumps
    for block_t, base in [(T_IRON_BLOCK, (216, 216, 216)), (T_GOLD_BLOCK, (246, 206, 58)),
                          (T_DIAMOND_BLOCK, (98, 219, 212))]:
        img = _noisy(rng, base, 0.03)
        img[(xs + ys) % 8 == 3] *= 1.1  # diagonal shine
        img[[7, 8], 1:-1] *= np.array([0.86, 1.08])[:, None, None]  # a seam between two plates
        tiles[block_t] = _bevel(img, 1.15, 0.7)
    coal = _noisy(rng, (30, 30, 32), 0.2)
    coal[rng.random((TILE, TILE)) < 0.12] = (58, 58, 62)  # glints
    tiles[T_COAL_BLOCK] = coal
    obsidian = _noisy(rng, (22, 16, 34), 0.25)
    obsidian[_blobs(rng, 0.15, cells=6)] = (60, 40, 94)  # purple streaks in the glass
    tiles[T_OBSIDIAN] = obsidian

    shelf = tiles[T_PLANKS].copy()  # two rows of books between the boards
    for y0 in (2, 9):
        x = 1
        while x < TILE - 1:
            width = min(rng.integers(1, 4), TILE - 1 - x)
            book = rng.choice([(120, 36, 30), (44, 70, 120), (52, 96, 46), (130, 98, 46), (92, 50, 90),
                               (150, 140, 120)])
            height = rng.integers(4, 6)
            shelf[y0 + 5 - height:y0 + 5, x:x + width] = _noisy(rng, book, 0.08)[:height, :width]
            shelf[y0 + 5 - height:y0 + 5, x] *= 0.8  # the spine's edge
            x += width
        shelf[y0:y0 + 5, [0, TILE - 1]] *= 0.6
    tiles[T_BOOKSHELF] = shelf

    hay = _bark(rng, (196, 162, 44), 0.1, 0.3)  # straw lying up and down
    hay[[3, 4, 11, 12]] = _noisy(rng, (128, 78, 30), 0.1)[[3, 4, 11, 12]]  # the bindings
    tiles[T_HAY_SIDE] = hay
    hay_top = _noisy(rng, (204, 172, 56), 0.16)  # the cut ends of the straw
    hay_top[ring > 6.5] *= 0.75
    tiles[T_HAY_TOP] = hay_top

    pumpkin = _bark(rng, (222, 132, 24), 0.05, 0.15)
    pumpkin[:, [0, 5, 10, 15]] *= 0.72  # the grooves between the ribs
    tiles[T_PUMPKIN_SIDE] = pumpkin
    pumpkin_top = _noisy(rng, (214, 126, 22), 0.05)
    pumpkin_top[(abs(xs - 7.5) + abs(ys - 7.5)).astype(int) % 4 == 0] *= 0.8
    pumpkin_top[6:10, 6:10] = _noisy(rng, (96, 82, 34), 0.1)[:4, :4]  # the stem
    tiles[T_PUMPKIN_TOP] = pumpkin_top

    melon = _noisy(rng, (106, 146, 30), 0.06)
    stripes = (xs + np.rint(1.2 * np.sin(ys * 0.8)).astype(int)) % 5 < 2  # wavy pale stripes
    melon[stripes] = _noisy(rng, (164, 186, 58), 0.06)[stripes]
    tiles[T_MELON_SIDE] = melon
    melon_top = _noisy(rng, (110, 150, 32), 0.06)
    pale = np.hypot(xs - 7.5, ys - 7.5).astype(int) % 4 < 2
    melon_top[pale] = _noisy(rng, (160, 182, 56), 0.06)[pale]
    melon_top[7:9, 7:9] = (86, 76, 30)
    tiles[T_MELON_TOP] = melon_top

    # Wool: one woven pattern, in 16 colors
    weave = _wool_weave(rng)
    for wool_t, color in [(T_WHITE_WOOL, (233, 236, 236)), (T_ORANGE_WOOL, (240, 118, 20)),
                          (T_MAGENTA_WOOL, (190, 68, 180)), (T_LIGHT_BLUE_WOOL, (58, 176, 218)),
                          (T_YELLOW_WOOL, (248, 198, 40)), (T_LIME_WOOL, (112, 186, 26)),
                          (T_PINK_WOOL, (238, 141, 172)), (T_GRAY_WOOL, (63, 68, 72)),
                          (T_LIGHT_GRAY_WOOL, (142, 142, 135)), (T_CYAN_WOOL, (21, 138, 145)),
                          (T_PURPLE_WOOL, (122, 42, 172)), (T_BLUE_WOOL, (53, 57, 158)),
                          (T_BROWN_WOOL, (114, 72, 41)), (T_GREEN_WOOL, (84, 110, 28)),
                          (T_RED_WOOL, (160, 39, 35)), (T_BLACK_WOOL, (22, 22, 27))]:
        tiles[wool_t] = np.array(color, dtype=float) * weave

    tiles[T_DEEPSLATE_BRICKS] = _masonry(rng, (72, 72, 78), (42, 42, 46), 4, 8, 0.08)
    tiles[T_POLISHED_DEEPSLATE] = _bevel(_noisy(rng, (74, 74, 78), 0.04), 1.2, 0.75)
    tiles[T_MUD_BRICKS] = _masonry(rng, (138, 106, 80), (100, 78, 62), 4, 8, 0.06)
    quartz = _noisy(rng, (236, 230, 222), 0.02)
    quartz[ring > 6.5] *= 0.92
    tiles[T_QUARTZ] = quartz
    for terracotta_t, color in [(T_YELLOW_TERRACOTTA, (186, 133, 35)), (T_RED_TERRACOTTA, (143, 61, 46)),
                                (T_BROWN_TERRACOTTA, (77, 51, 36)), (T_LIGHT_GRAY_TERRACOTTA, (135, 107, 98))]:
        tiles[terracotta_t] = _noisy(rng, color, 0.04)

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
