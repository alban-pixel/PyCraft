"""Block types, items, tools, properties, and procedural 128x128 texture atlas."""
import math
import numpy as np

TILE = 16
ATLAS_TILES = 8  # 8x8 tiles = 128x128 pixels

# Block IDs (0 to 23)
(AIR, GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, SAND, BRICK,
 GLASS, WATER, COAL_ORE, IRON_ORE, BEDROCK, GOLD_ORE, DIAMOND_ORE, GLOWSTONE, SNOW, CRAFTING_TABLE,
 ICE, SLIME, OBSIDIAN, LAVA) = range(24)

BLOCK_NAMES = [
    "Air", "Grass", "Dirt", "Stone", "Cobblestone", "Planks", "Log", "Leaves", "Sand", "Brick",
    "Glass", "Water", "Coal ore", "Iron ore", "Bedrock", "Gold ore", "Diamond ore", "Glowstone", "Snow",
    "Crafting table", "Ice", "Slime", "Obsidian", "Lava",
]
NUM_BLOCKS = len(BLOCK_NAMES)

# Item IDs (>= 100)
(ITEM_STICK, ITEM_WOOD_PICKAXE, ITEM_STONE_PICKAXE, ITEM_IRON_PICKAXE, ITEM_DIAMOND_PICKAXE,
 ITEM_WOOD_SWORD, ITEM_STONE_SWORD, ITEM_IRON_SWORD, ITEM_DIAMOND_SWORD,
 ITEM_RAW_PORK, ITEM_COOKED_PORK) = range(100, 111)

ITEM_NAMES = {
    ITEM_STICK: "Stick",
    ITEM_WOOD_PICKAXE: "Wooden Pickaxe",
    ITEM_STONE_PICKAXE: "Stone Pickaxe",
    ITEM_IRON_PICKAXE: "Iron Pickaxe",
    ITEM_DIAMOND_PICKAXE: "Diamond Pickaxe",
    ITEM_WOOD_SWORD: "Wooden Sword",
    ITEM_STONE_SWORD: "Stone Sword",
    ITEM_IRON_SWORD: "Iron Sword",
    ITEM_DIAMOND_SWORD: "Diamond Sword",
    ITEM_RAW_PORK: "Raw Porkchop",
    ITEM_COOKED_PORK: "Cooked Porkchop",
}

# Blocks placeable directly in world
PLACEABLE = [
    GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, SAND, BRICK,
    GLASS, WATER, COAL_ORE, IRON_ORE, GOLD_ORE, DIAMOND_ORE, GLOWSTONE, SNOW, CRAFTING_TABLE,
    ICE, SLIME, OBSIDIAN, LAVA,
]
DEFAULT_HOTBAR = [GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, GLASS, CRAFTING_TABLE]

# Full Creative Inventory catalog containing every placeable block and item in the game
CREATIVE_CATALOG = [
    GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, SAND, BRICK,
    GLASS, WATER, LAVA, COAL_ORE, IRON_ORE, GOLD_ORE, DIAMOND_ORE,
    GLOWSTONE, SNOW, CRAFTING_TABLE, ICE, SLIME, OBSIDIAN, BEDROCK,
    ITEM_WOOD_PICKAXE, ITEM_STONE_PICKAXE, ITEM_IRON_PICKAXE, ITEM_DIAMOND_PICKAXE,
    ITEM_WOOD_SWORD, ITEM_STONE_SWORD, ITEM_IRON_SWORD, ITEM_DIAMOND_SWORD,
    ITEM_STICK, ITEM_RAW_PORK, ITEM_COOKED_PORK,
]

# Non-stackable tools & weapons (max stack size 1)
NON_STACKABLE = {
    ITEM_WOOD_PICKAXE, ITEM_STONE_PICKAXE, ITEM_IRON_PICKAXE, ITEM_DIAMOND_PICKAXE,
    ITEM_WOOD_SWORD, ITEM_STONE_SWORD, ITEM_IRON_SWORD, ITEM_DIAMOND_SWORD,
}


def _flags(*blocks):
    table = np.zeros(NUM_BLOCKS, dtype=bool)
    table[list(blocks)] = True
    return table


OPAQUE = ~_flags(AIR, LEAVES, GLASS, WATER, ICE, SLIME, LAVA)
SOLID = ~_flags(AIR, WATER, LAVA)
CUTOUT = _flags(LEAVES, GLASS, ICE, SLIME)
SELF_CULL = _flags(GLASS, WATER, ICE, LAVA)
TARGETABLE = ~_flags(AIR, WATER, LAVA)
UNBREAKABLE = _flags(BEDROCK)

# Atlas tile indices
(T_GRASS_TOP, T_GRASS_SIDE, T_DIRT, T_STONE, T_COBBLE, T_PLANKS, T_LOG_SIDE, T_LOG_TOP, T_LEAVES,
 T_SAND, T_BRICK, T_GLASS, T_WATER, T_COAL, T_IRON, T_BEDROCK,
 T_GOLD, T_DIAMOND, T_GLOWSTONE, T_SNOW, T_SNOW_SIDE,
 T_CRAFT_TOP, T_CRAFT_SIDE, T_STICK,
 T_WOOD_PICKAXE, T_STONE_PICKAXE, T_IRON_PICKAXE, T_DIAMOND_PICKAXE,
 T_WOOD_SWORD, T_STONE_SWORD, T_IRON_SWORD, T_DIAMOND_SWORD,
 T_RAW_PORK, T_COOKED_PORK,
 T_CRACK_0, T_CRACK_1, T_CRACK_2, T_CRACK_3,
 T_ZOMBIE_FACE, T_ZOMBIE_BODY, T_PIG_FACE, T_PIG_BODY) = range(42)


def _faces(side, top=None, bottom=None, front=None):
    top = side if top is None else top
    bottom = top if bottom is None else bottom
    front = side if front is None else front
    return [side, side, top, bottom, front, side]


BLOCK_TILES = np.array([
    _faces(0),  # AIR
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
    _faces(T_GOLD),
    _faces(T_DIAMOND),
    _faces(T_GLOWSTONE),
    _faces(T_SNOW_SIDE, T_SNOW, T_DIRT),
    _faces(T_CRAFT_SIDE, T_CRAFT_TOP, T_PLANKS),
    _faces(T_GLASS),   # ICE
    _faces(T_LEAVES),  # SLIME
    _faces(T_BEDROCK), # OBSIDIAN
    _faces(T_GOLD),    # LAVA
], dtype=np.int32)

ITEM_TILES = {
    ITEM_STICK: T_STICK,
    ITEM_WOOD_PICKAXE: T_WOOD_PICKAXE,
    ITEM_STONE_PICKAXE: T_STONE_PICKAXE,
    ITEM_IRON_PICKAXE: T_IRON_PICKAXE,
    ITEM_DIAMOND_PICKAXE: T_DIAMOND_PICKAXE,
    ITEM_WOOD_SWORD: T_WOOD_SWORD,
    ITEM_STONE_SWORD: T_STONE_SWORD,
    ITEM_IRON_SWORD: T_IRON_SWORD,
    ITEM_DIAMOND_SWORD: T_DIAMOND_SWORD,
    ITEM_RAW_PORK: T_RAW_PORK,
    ITEM_COOKED_PORK: T_COOKED_PORK,
}

BLOCK_COLORS = {
    GRASS: 3, DIRT: 4, STONE: 6, COBBLESTONE: 13, PLANKS: 4, LOG: 4, LEAVES: 11,
    SAND: 10, BRICK: 2, GLASS: 7, WATER: 12, COAL_ORE: 0, IRON_ORE: 15,
    BEDROCK: 0, GOLD_ORE: 10, DIAMOND_ORE: 12, GLOWSTONE: 9, SNOW: 7, CRAFTING_TABLE: 4,
    ICE: 12, SLIME: 3, OBSIDIAN: 0, LAVA: 9,
}

# Mining hardness in seconds with bare hand
BLOCK_HARDNESS = {
    LEAVES: 0.25, GLASS: 0.3, SNOW: 0.35, SAND: 0.45, DIRT: 0.5, GRASS: 0.55,
    GLOWSTONE: 0.4, PLANKS: 1.2, LOG: 1.4, CRAFTING_TABLE: 1.2,
    STONE: 2.2, COBBLESTONE: 2.2, BRICK: 2.2,
    COAL_ORE: 2.8, IRON_ORE: 3.2, GOLD_ORE: 3.5, DIAMOND_ORE: 4.0,
    ICE: 0.5, SLIME: 0.2, OBSIDIAN: 50.0, LAVA: 100.0,
}

PICKAXES = {
    ITEM_WOOD_PICKAXE: 2.0,
    ITEM_STONE_PICKAXE: 3.5,
    ITEM_IRON_PICKAXE: 5.5,
    ITEM_DIAMOND_PICKAXE: 8.0,
}

ATTACK_DAMAGE = {
    ITEM_WOOD_SWORD: 4,
    ITEM_STONE_SWORD: 5,
    ITEM_IRON_SWORD: 6,
    ITEM_DIAMOND_SWORD: 7,
    ITEM_WOOD_PICKAXE: 2,
    ITEM_STONE_PICKAXE: 3,
    ITEM_IRON_PICKAXE: 4,
    ITEM_DIAMOND_PICKAXE: 5,
}

FOOD_HEAL = {
    ITEM_RAW_PORK: 3,
    ITEM_COOKED_PORK: 8,
}


def get_item_name(item_id):
    if item_id < NUM_BLOCKS:
        return BLOCK_NAMES[item_id]
    return ITEM_NAMES.get(item_id, "Item")


def get_item_tile(item_id):
    if item_id < NUM_BLOCKS:
        return int(BLOCK_TILES[item_id][0])
    return ITEM_TILES.get(item_id, 0)


def _noisy(rng, base, var):
    shade = 1 + rng.uniform(-var, var, (TILE, TILE, 1))
    return np.array(base, dtype=float) * shade


def _masonry(rng, base, mortar, row_h, brick_w, var, random_offsets=False):
    img = _noisy(rng, base, var)
    for row in range(TILE // row_h):
        offset = rng.integers(0, brick_w) if random_offsets else (row % 2) * brick_w // 2
        ys = slice(row * row_h, (row + 1) * row_h)
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


def _draw_pickaxe(handle_col, head_col):
    img = np.zeros((TILE, TILE, 3), dtype=float)
    alpha = np.zeros((TILE, TILE), dtype=bool)
    # Handle diagonal
    for i in range(2, 13):
        x, y = i, 15 - i
        img[y:y + 2, x:x + 2] = handle_col
        alpha[y:y + 2, x:x + 2] = True
    # Pickaxe head curve
    head_coords = [(1, 14), (2, 13), (3, 12), (4, 11), (5, 11), (6, 12), (7, 13), (8, 14)]
    for hx, hy in [(2, 2), (3, 2), (4, 3), (2, 3), (3, 4), (4, 4), (5, 4), (5, 3), (6, 2), (7, 2), (8, 3)]:
        img[hy, hx] = head_col
        alpha[hy, hx] = True
    for hx, hy in [(1, 3), (2, 1), (8, 2), (9, 3), (10, 4), (11, 5)]:
        img[hy, hx] = head_col
        alpha[hy, hx] = True
    return img, alpha


def _draw_sword(handle_col, blade_col):
    img = np.zeros((TILE, TILE, 3), dtype=float)
    alpha = np.zeros((TILE, TILE), dtype=bool)
    # Handle
    for i in range(12, 15):
        img[i, 16 - i] = handle_col
        alpha[i, 16 - i] = True
    # Guard
    for gx, gy in [(3, 12), (4, 11), (5, 10)]:
        img[gy, gx] = (140, 110, 60)
        alpha[gy, gx] = True
    # Blade
    for b in range(2, 11):
        x, y = b, b
        img[y, x] = blade_col
        img[y + 1, x] = np.array(blade_col) * 0.85
        alpha[y, x] = True
        alpha[y + 1, x] = True
    return img, alpha


def build_atlas(seed=7):
    """Return the texture atlas as a (128, 128, 4) uint8 RGBA array."""
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
    tiles[T_GOLD] = _ore(rng, stone, (245, 215, 60), 6)
    tiles[T_DIAMOND] = _ore(rng, stone, (75, 235, 235), 6)
    tiles[T_BEDROCK] = _noisy(rng, (70, 70, 70), 0.6)

    tiles[T_COBBLE] = _masonry(rng, (122, 122, 122), (72, 72, 72), 4, 5, 0.12, random_offsets=True)
    tiles[T_BRICK] = _masonry(rng, (150, 74, 58), (178, 170, 160), 4, 8, 0.08)
    tiles[T_GLOWSTONE] = _masonry(rng, (230, 190, 80), (190, 140, 50), 4, 4, 0.18, random_offsets=True)

    planks = _noisy(rng, (162, 130, 78), 0.06)
    for row in range(4):
        planks[row * 4 + 3, :] *= 0.65
        joint = rng.integers(0, TILE)
        planks[row * 4:row * 4 + 3, joint] *= 0.75
        planks[row * 4 + rng.integers(0, 3), rng.integers(0, TILE, 5)] *= 0.85
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

    snow = _noisy(rng, (242, 245, 255), 0.04)
    tiles[T_SNOW] = snow
    snow_side = dirt.copy()
    for x in range(TILE):
        depth = rng.integers(3, 6)
        snow_side[:depth, x] = snow[:depth, x]
    tiles[T_SNOW_SIDE] = snow_side

    glass = np.full((TILE, TILE, 3), (215, 235, 240), dtype=float)
    glass_alpha = (ring > 6.5)
    for i in range(3):
        glass_alpha |= (xs - ys == 4 + i) & (xs < 10)
    tiles[T_GLASS], alpha[T_GLASS] = glass, glass_alpha

    tiles[T_WATER] = _noisy(rng, (45, 90, 200), 0.1)

    # Crafting table
    craft_top = planks.copy()
    craft_top[2:14, 2:14] *= 0.85
    craft_top[2, 2:14] = craft_top[13, 2:14] = (60, 40, 20)
    craft_top[2:14, 2] = craft_top[2:14, 13] = (60, 40, 20)
    craft_top[5, 3:13] = craft_top[9, 3:13] = (80, 55, 30)
    craft_top[3:13, 5] = craft_top[3:13, 9] = (80, 55, 30)
    tiles[T_CRAFT_TOP] = craft_top

    craft_side = planks.copy()
    craft_side[3:12, 3:6] = (180, 180, 190)  # tool silhouette
    craft_side[8:13, 8:14] = (140, 80, 40)
    tiles[T_CRAFT_SIDE] = craft_side

    # Stick
    stick_img = np.zeros((TILE, TILE, 3), dtype=float)
    stick_alpha = np.zeros((TILE, TILE), dtype=bool)
    for i in range(3, 13):
        stick_img[15 - i, i] = (120, 85, 45)
        stick_alpha[15 - i, i] = True
    tiles[T_STICK], alpha[T_STICK] = stick_img, stick_alpha

    # Tools
    tiles[T_WOOD_PICKAXE], alpha[T_WOOD_PICKAXE] = _draw_pickaxe((120, 85, 45), (160, 125, 75))
    tiles[T_STONE_PICKAXE], alpha[T_STONE_PICKAXE] = _draw_pickaxe((120, 85, 45), (140, 140, 140))
    tiles[T_IRON_PICKAXE], alpha[T_IRON_PICKAXE] = _draw_pickaxe((120, 85, 45), (220, 220, 230))
    tiles[T_DIAMOND_PICKAXE], alpha[T_DIAMOND_PICKAXE] = _draw_pickaxe((120, 85, 45), (80, 235, 230))

    tiles[T_WOOD_SWORD], alpha[T_WOOD_SWORD] = _draw_sword((120, 85, 45), (160, 125, 75))
    tiles[T_STONE_SWORD], alpha[T_STONE_SWORD] = _draw_sword((120, 85, 45), (140, 140, 140))
    tiles[T_IRON_SWORD], alpha[T_IRON_SWORD] = _draw_sword((120, 85, 45), (220, 220, 230))
    tiles[T_DIAMOND_SWORD], alpha[T_DIAMOND_SWORD] = _draw_sword((120, 85, 45), (80, 235, 230))

    # Pork
    raw_pork = np.zeros((TILE, TILE, 3), dtype=float)
    raw_alpha = np.zeros((TILE, TILE), dtype=bool)
    for y in range(4, 12):
        for x in range(3, 13):
            if math.hypot(x - 7.5, y - 7.5) < 4.2:
                raw_pork[y, x] = (225, 120, 125)
                raw_alpha[y, x] = True
    raw_pork[5:7, 5:8] = (245, 230, 230)  # fat/bone marbling
    tiles[T_RAW_PORK], alpha[T_RAW_PORK] = raw_pork, raw_alpha

    cooked_pork = raw_pork.copy() * 0.65
    cooked_pork[raw_alpha] = np.clip(cooked_pork[raw_alpha] + np.array([80, 40, 10]), 0, 255)
    tiles[T_COOKED_PORK], alpha[T_COOKED_PORK] = cooked_pork, raw_alpha

    # Cracks 0..3
    for c_idx in range(4):
        c_img = np.zeros((TILE, TILE, 3), dtype=float)
        c_alpha = np.zeros((TILE, TILE), dtype=bool)
        rng_c = np.random.default_rng(c_idx * 17)
        points = [(8, 8)]
        for _ in range(4 + c_idx * 5):
            px, py = points[rng_c.integers(0, len(points))]
            nx = min(max(px + rng_c.integers(-2, 3), 0), TILE - 1)
            ny = min(max(py + rng_c.integers(-2, 3), 0), TILE - 1)
            points.append((nx, ny))
            c_alpha[ny, nx] = True
            c_img[ny, nx] = (10, 10, 10)
        tiles[T_CRACK_0 + c_idx] = c_img
        alpha[T_CRACK_0 + c_idx] = c_alpha

    # Mob textures: Zombie & Pig faces and skins
    zombie_face = _noisy(rng, (45, 135, 55), 0.1)
    zombie_face[6:8, 3:5] = (15, 15, 20)  # eyes
    zombie_face[6:8, 11:13] = (15, 15, 20)
    zombie_face[10:12, 6:10] = (25, 80, 30)  # mouth
    tiles[T_ZOMBIE_FACE] = zombie_face
    tiles[T_ZOMBIE_BODY] = _noisy(rng, (40, 150, 160), 0.08)  # cyan shirt

    pig_face = _noisy(rng, (245, 165, 165), 0.08)
    pig_face[6:8, 2:4] = (20, 20, 20)  # eyes
    pig_face[6:8, 12:14] = (20, 20, 20)
    pig_face[8:12, 5:11] = (225, 120, 130)  # snout
    pig_face[9:11, 6] = pig_face[9:11, 9] = (120, 50, 60)  # nostrils
    tiles[T_PIG_FACE] = pig_face
    tiles[T_PIG_BODY] = _noisy(rng, (240, 160, 160), 0.08)

    atlas = np.zeros((TILE * ATLAS_TILES, TILE * ATLAS_TILES, 4))
    for t, img in tiles.items():
        ty, tx = divmod(t, ATLAS_TILES)
        cell = (slice(ty * TILE, (ty + 1) * TILE), slice(tx * TILE, (tx + 1) * TILE))
        atlas[cell + (slice(0, 3),)] = img
        atlas[cell + (3,)] = 255 * alpha.get(t, np.ones((TILE, TILE), dtype=bool))
    return np.clip(atlas, 0, 255).astype(np.uint8)
