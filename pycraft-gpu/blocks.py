"""Block types, items, tools, properties, and procedural 256x256 texture atlas (Minecraft 1.8 Bountiful Update)."""
import math
import numpy as np

TILE = 16
ATLAS_TILES = 16  # 16x16 tiles = 256x256 pixels

# Block IDs (0 to 47) - Canonical Minecraft 1.8 Catalog
(
    AIR, GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, SAND, BRICK,
    GLASS, WATER, COAL_ORE, IRON_ORE, BEDROCK, GOLD_ORE, DIAMOND_ORE, GLOWSTONE, SNOW, CRAFTING_TABLE,
    ICE, SLIME, OBSIDIAN, LAVA,
    # New Minecraft 1.8 Blocks
    GRANITE, POLISHED_GRANITE, DIORITE, POLISHED_DIORITE, ANDESITE, POLISHED_ANDESITE,
    PRISMARINE, PRISMARINE_BRICKS, DARK_PRISMARINE, SEA_LANTERN,
    RED_SAND, RED_SANDSTONE, CHISELED_RED_SANDSTONE, SMOOTH_RED_SANDSTONE,
    COARSE_DIRT, PODZOL, SPONGE, WET_SPONGE,
    SPRUCE_PLANKS, BIRCH_PLANKS, JUNGLE_PLANKS, ACACIA_PLANKS, DARK_OAK_PLANKS,
    IRON_TRAPDOOR
) = range(48)

BLOCK_NAMES = [
    "Air", "Grass", "Dirt", "Stone", "Cobblestone", "Planks", "Log", "Leaves", "Sand", "Brick",
    "Glass", "Water", "Coal ore", "Iron ore", "Bedrock", "Gold ore", "Diamond ore", "Glowstone", "Snow",
    "Crafting table", "Ice", "Slime", "Obsidian", "Lava",
    # 1.8 Stone types
    "Granite", "Polished Granite", "Diorite", "Polished Diorite", "Andesite", "Polished Andesite",
    # 1.8 Ocean Monument blocks
    "Prismarine", "Prismarine Bricks", "Dark Prismarine", "Sea Lantern",
    # 1.8 Red Sandstone / Desert blocks
    "Red Sand", "Red Sandstone", "Chiseled Red Sandstone", "Smooth Red Sandstone",
    # 1.8 Soils & Sponges
    "Coarse Dirt", "Podzol", "Sponge", "Wet Sponge",
    # 1.8 Wood Plank variants
    "Spruce Planks", "Birch Planks", "Jungle Planks", "Acacia Planks", "Dark Oak Planks",
    # 1.8 Redstone / Mechanism
    "Iron Trapdoor",
]
NUM_BLOCKS = len(BLOCK_NAMES)

# Item IDs (>= 100)
(
    ITEM_STICK, ITEM_WOOD_PICKAXE, ITEM_STONE_PICKAXE, ITEM_IRON_PICKAXE, ITEM_DIAMOND_PICKAXE,
    ITEM_WOOD_SWORD, ITEM_STONE_SWORD, ITEM_IRON_SWORD, ITEM_DIAMOND_SWORD,
    ITEM_RAW_PORK, ITEM_COOKED_PORK,
) = range(100, 111)

# Minecraft 1.8 Food & Material Items
(
    ITEM_RAW_MUTTON, ITEM_COOKED_MUTTON,
    ITEM_RAW_RABBIT, ITEM_COOKED_RABBIT, ITEM_RABBIT_STEW, ITEM_RABBIT_FOOT, ITEM_RABBIT_HIDE,
    ITEM_PRISMARINE_SHARD, ITEM_PRISMARINE_CRYSTALS,
    ITEM_ARMOR_STAND,
) = range(120, 130)

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
    # 1.8 Items
    ITEM_RAW_MUTTON: "Raw Mutton",
    ITEM_COOKED_MUTTON: "Cooked Mutton",
    ITEM_RAW_RABBIT: "Raw Rabbit",
    ITEM_COOKED_RABBIT: "Cooked Rabbit",
    ITEM_RABBIT_STEW: "Rabbit Stew",
    ITEM_RABBIT_FOOT: "Rabbit's Foot",
    ITEM_RABBIT_HIDE: "Rabbit Hide",
    ITEM_PRISMARINE_SHARD: "Prismarine Shard",
    ITEM_PRISMARINE_CRYSTALS: "Prismarine Crystals",
    ITEM_ARMOR_STAND: "Armor Stand",
}

# Blocks placeable directly in world
PLACEABLE = [
    GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, SAND, BRICK,
    GLASS, WATER, COAL_ORE, IRON_ORE, GOLD_ORE, DIAMOND_ORE, GLOWSTONE, SNOW, CRAFTING_TABLE,
    ICE, SLIME, OBSIDIAN, LAVA,
    GRANITE, POLISHED_GRANITE, DIORITE, POLISHED_DIORITE, ANDESITE, POLISHED_ANDESITE,
    PRISMARINE, PRISMARINE_BRICKS, DARK_PRISMARINE, SEA_LANTERN,
    RED_SAND, RED_SANDSTONE, CHISELED_RED_SANDSTONE, SMOOTH_RED_SANDSTONE,
    COARSE_DIRT, PODZOL, SPONGE, WET_SPONGE,
    SPRUCE_PLANKS, BIRCH_PLANKS, JUNGLE_PLANKS, ACACIA_PLANKS, DARK_OAK_PLANKS,
    IRON_TRAPDOOR,
]
DEFAULT_HOTBAR = [GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, GLASS, CRAFTING_TABLE]

# Full Creative Inventory catalog containing every placeable block and item in the game
CREATIVE_CATALOG = [
    # Basic Terrain & Building Blocks
    GRASS, DIRT, COARSE_DIRT, PODZOL, STONE, COBBLESTONE, BEDROCK,
    PLANKS, SPRUCE_PLANKS, BIRCH_PLANKS, JUNGLE_PLANKS, ACACIA_PLANKS, DARK_OAK_PLANKS,
    LOG, LEAVES, SAND, RED_SAND, BRICK,
    # 1.8 Stones
    GRANITE, POLISHED_GRANITE, DIORITE, POLISHED_DIORITE, ANDESITE, POLISHED_ANDESITE,
    # 1.8 Red Sandstone variants
    RED_SANDSTONE, CHISELED_RED_SANDSTONE, SMOOTH_RED_SANDSTONE,
    # Ocean Monument Blocks
    PRISMARINE, PRISMARINE_BRICKS, DARK_PRISMARINE, SEA_LANTERN, SPONGE, WET_SPONGE,
    # Transparent & Mechanics Blocks
    GLASS, ICE, SLIME, CRAFTING_TABLE, GLOWSTONE, OBSIDIAN, IRON_TRAPDOOR,
    WATER, LAVA,
    # Ores
    COAL_ORE, IRON_ORE, GOLD_ORE, DIAMOND_ORE, SNOW,
    # Tools & Weapons
    ITEM_WOOD_PICKAXE, ITEM_STONE_PICKAXE, ITEM_IRON_PICKAXE, ITEM_DIAMOND_PICKAXE,
    ITEM_WOOD_SWORD, ITEM_STONE_SWORD, ITEM_IRON_SWORD, ITEM_DIAMOND_SWORD,
    # Materials, Food & Armor Stand
    ITEM_STICK, ITEM_ARMOR_STAND,
    ITEM_RAW_PORK, ITEM_COOKED_PORK, ITEM_RAW_MUTTON, ITEM_COOKED_MUTTON,
    ITEM_RAW_RABBIT, ITEM_COOKED_RABBIT, ITEM_RABBIT_STEW,
    ITEM_RABBIT_FOOT, ITEM_RABBIT_HIDE, ITEM_PRISMARINE_SHARD, ITEM_PRISMARINE_CRYSTALS,
]

# Non-stackable tools & weapons (max stack size 1)
NON_STACKABLE = {
    ITEM_WOOD_PICKAXE, ITEM_STONE_PICKAXE, ITEM_IRON_PICKAXE, ITEM_DIAMOND_PICKAXE,
    ITEM_WOOD_SWORD, ITEM_STONE_SWORD, ITEM_IRON_SWORD, ITEM_DIAMOND_SWORD,
    ITEM_ARMOR_STAND,
}


def _flags(*blocks):
    table = np.zeros(NUM_BLOCKS, dtype=bool)
    table[list(blocks)] = True
    return table


OPAQUE = ~_flags(AIR, LEAVES, GLASS, WATER, ICE, SLIME, LAVA, IRON_TRAPDOOR)
SOLID = ~_flags(AIR, WATER, LAVA)
CUTOUT = _flags(LEAVES, GLASS, ICE, SLIME, IRON_TRAPDOOR)
SELF_CULL = _flags(GLASS, WATER, ICE, LAVA)
TARGETABLE = ~_flags(AIR, WATER, LAVA)
UNBREAKABLE = _flags(BEDROCK)

# Atlas tile indices (0 to 255)
# Row 0: Standard terrain
(
    T_GRASS_TOP, T_GRASS_SIDE, T_DIRT, T_STONE, T_COBBLE, T_PLANKS, T_LOG_SIDE, T_LOG_TOP, T_LEAVES,
    T_SAND, T_BRICK, T_GLASS, T_WATER, T_COAL, T_IRON, T_BEDROCK,
) = range(16)

# Row 1: Ores, utilities, and 1.8 stones
(
    T_GOLD, T_DIAMOND, T_GLOWSTONE, T_SNOW, T_SNOW_SIDE,
    T_CRAFT_TOP, T_CRAFT_SIDE, T_ICE, T_SLIME, T_OBSIDIAN, T_LAVA,
    T_GRANITE, T_POLISHED_GRANITE, T_DIORITE, T_POLISHED_DIORITE, T_ANDESITE,
) = range(16, 32)

# Row 2: 1.8 Ocean & Red Sandstone
(
    T_POLISHED_ANDESITE, T_PRISMARINE, T_PRISMARINE_BRICKS, T_DARK_PRISMARINE, T_SEA_LANTERN,
    T_RED_SAND, T_RED_SANDSTONE_SIDE, T_RED_SANDSTONE_TOP, T_RED_SANDSTONE_BOTTOM,
    T_CHISELED_RED_SANDSTONE, T_SMOOTH_RED_SANDSTONE,
    T_COARSE_DIRT, T_PODZOL_TOP, T_PODZOL_SIDE, T_SPONGE, T_WET_SPONGE,
) = range(32, 48)

# Row 3: 1.8 Wood planks & mechanics
(
    T_SPRUCE_PLANKS, T_BIRCH_PLANKS, T_JUNGLE_PLANKS, T_ACACIA_PLANKS, T_DARK_OAK_PLANKS,
    T_IRON_TRAPDOOR,
    T_CRACK_0, T_CRACK_1, T_CRACK_2, T_CRACK_3,
    T_ZOMBIE_FACE, T_ZOMBIE_BODY, T_PIG_FACE, T_PIG_BODY,
    T_STICK, T_ARMOR_STAND,
) = range(48, 64)

# Row 4: Tools & Food
(
    T_WOOD_PICKAXE, T_STONE_PICKAXE, T_IRON_PICKAXE, T_DIAMOND_PICKAXE,
    T_WOOD_SWORD, T_STONE_SWORD, ITEM_IRON_SWORD_TILE, T_DIAMOND_SWORD,
    T_RAW_PORK, T_COOKED_PORK, T_RAW_MUTTON, T_COOKED_MUTTON,
    T_RAW_RABBIT, T_COOKED_RABBIT, T_RABBIT_STEW, T_RABBIT_FOOT,
) = range(64, 80)
T_IRON_SWORD = ITEM_IRON_SWORD_TILE

# Row 5: 1.8 Materials & Shards
(
    T_RABBIT_HIDE, T_PRISMARINE_SHARD, T_PRISMARINE_CRYSTALS,
) = range(80, 83)


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
    _faces(T_ICE),
    _faces(T_SLIME),
    _faces(T_OBSIDIAN),
    _faces(T_LAVA),
    # 1.8 Stones
    _faces(T_GRANITE),
    _faces(T_POLISHED_GRANITE),
    _faces(T_DIORITE),
    _faces(T_POLISHED_DIORITE),
    _faces(T_ANDESITE),
    _faces(T_POLISHED_ANDESITE),
    # 1.8 Ocean Monument
    _faces(T_PRISMARINE),
    _faces(T_PRISMARINE_BRICKS),
    _faces(T_DARK_PRISMARINE),
    _faces(T_SEA_LANTERN),
    # 1.8 Red Sandstone / Desert
    _faces(T_RED_SAND),
    _faces(T_RED_SANDSTONE_SIDE, T_RED_SANDSTONE_TOP, T_RED_SANDSTONE_BOTTOM),
    _faces(T_CHISELED_RED_SANDSTONE, T_RED_SANDSTONE_TOP, T_RED_SANDSTONE_BOTTOM),
    _faces(T_SMOOTH_RED_SANDSTONE, T_RED_SANDSTONE_TOP, T_RED_SANDSTONE_BOTTOM),
    # 1.8 Soils & Sponges
    _faces(T_COARSE_DIRT),
    _faces(T_PODZOL_SIDE, T_PODZOL_TOP, T_DIRT),
    _faces(T_SPONGE),
    _faces(T_WET_SPONGE),
    # 1.8 Planks
    _faces(T_SPRUCE_PLANKS),
    _faces(T_BIRCH_PLANKS),
    _faces(T_JUNGLE_PLANKS),
    _faces(T_ACACIA_PLANKS),
    _faces(T_DARK_OAK_PLANKS),
    # 1.8 Redstone
    _faces(T_IRON_TRAPDOOR),
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
    # 1.8 Items
    ITEM_RAW_MUTTON: T_RAW_MUTTON,
    ITEM_COOKED_MUTTON: T_COOKED_MUTTON,
    ITEM_RAW_RABBIT: T_RAW_RABBIT,
    ITEM_COOKED_RABBIT: T_COOKED_RABBIT,
    ITEM_RABBIT_STEW: T_RABBIT_STEW,
    ITEM_RABBIT_FOOT: T_RABBIT_FOOT,
    ITEM_RABBIT_HIDE: T_RABBIT_HIDE,
    ITEM_PRISMARINE_SHARD: T_PRISMARINE_SHARD,
    ITEM_PRISMARINE_CRYSTALS: T_PRISMARINE_CRYSTALS,
    ITEM_ARMOR_STAND: T_ARMOR_STAND,
}

BLOCK_COLORS = {
    GRASS: 3, DIRT: 4, STONE: 6, COBBLESTONE: 13, PLANKS: 4, LOG: 4, LEAVES: 11,
    SAND: 10, BRICK: 2, GLASS: 7, WATER: 12, COAL_ORE: 0, IRON_ORE: 15,
    BEDROCK: 0, GOLD_ORE: 10, DIAMOND_ORE: 12, GLOWSTONE: 9, SNOW: 7, CRAFTING_TABLE: 4,
    ICE: 12, SLIME: 3, OBSIDIAN: 0, LAVA: 9,
    # 1.8 Stones
    GRANITE: 14, POLISHED_GRANITE: 14, DIORITE: 7, POLISHED_DIORITE: 7, ANDESITE: 6, POLISHED_ANDESITE: 6,
    # 1.8 Ocean
    PRISMARINE: 11, PRISMARINE_BRICKS: 11, DARK_PRISMARINE: 5, SEA_LANTERN: 12,
    # 1.8 Red Sandstone
    RED_SAND: 9, RED_SANDSTONE: 9, CHISELED_RED_SANDSTONE: 9, SMOOTH_RED_SANDSTONE: 9,
    # 1.8 Soils & Sponges
    COARSE_DIRT: 4, PODZOL: 4, SPONGE: 10, WET_SPONGE: 10,
    # 1.8 Planks
    SPRUCE_PLANKS: 4, BIRCH_PLANKS: 15, JUNGLE_PLANKS: 14, ACACIA_PLANKS: 9, DARK_OAK_PLANKS: 0,
    # 1.8 Trapdoor
    IRON_TRAPDOOR: 7,
}

# Mining hardness in seconds with bare hand
BLOCK_HARDNESS = {
    LEAVES: 0.25, GLASS: 0.3, SNOW: 0.35, SAND: 0.45, DIRT: 0.5, GRASS: 0.55,
    GLOWSTONE: 0.4, PLANKS: 1.2, LOG: 1.4, CRAFTING_TABLE: 1.2,
    STONE: 2.2, COBBLESTONE: 2.2, BRICK: 2.2,
    COAL_ORE: 2.8, IRON_ORE: 3.2, GOLD_ORE: 3.5, DIAMOND_ORE: 4.0,
    ICE: 0.5, SLIME: 0.2, OBSIDIAN: 50.0, LAVA: 100.0,
    # 1.8 Stones
    GRANITE: 2.2, POLISHED_GRANITE: 2.2, DIORITE: 2.2, POLISHED_DIORITE: 2.2,
    ANDESITE: 2.2, POLISHED_ANDESITE: 2.2,
    # 1.8 Ocean Monument
    PRISMARINE: 2.2, PRISMARINE_BRICKS: 2.2, DARK_PRISMARINE: 2.2, SEA_LANTERN: 0.45,
    # 1.8 Red Sandstone
    RED_SAND: 0.45, RED_SANDSTONE: 1.2, CHISELED_RED_SANDSTONE: 1.2, SMOOTH_RED_SANDSTONE: 1.2,
    # 1.8 Soils & Sponges
    COARSE_DIRT: 0.5, PODZOL: 0.5, SPONGE: 0.6, WET_SPONGE: 0.6,
    # 1.8 Planks
    SPRUCE_PLANKS: 1.2, BIRCH_PLANKS: 1.2, JUNGLE_PLANKS: 1.2, ACACIA_PLANKS: 1.2, DARK_OAK_PLANKS: 1.2,
    # 1.8 Redstone / Mechanism
    IRON_TRAPDOOR: 5.0,
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
    ITEM_RAW_MUTTON: 2,
    ITEM_COOKED_MUTTON: 6,
    ITEM_RAW_RABBIT: 3,
    ITEM_COOKED_RABBIT: 5,
    ITEM_RABBIT_STEW: 10,
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


def _polished_border(img, border_color):
    res = img.copy()
    res[0, :] = res[-1, :] = res[:, 0] = res[:, -1] = border_color
    return res


def _ore(rng, stone, color, count):
    img = stone.copy()
    for _ in range(count):
        y, x = rng.integers(1, TILE - 2, 2)
        img[y:y + 2, x:x + 2] = _noisy(rng, color, 0.15)[:2, :2]
    return img


def _draw_pickaxe(handle_col, head_col):
    img = np.zeros((TILE, TILE, 3), dtype=float)
    alpha = np.zeros((TILE, TILE), dtype=bool)
    for i in range(2, 13):
        x, y = i, 15 - i
        img[y:y + 2, x:x + 2] = handle_col
        alpha[y:y + 2, x:x + 2] = True
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
    for i in range(12, 15):
        img[i, 16 - i] = handle_col
        alpha[i, 16 - i] = True
    for gx, gy in [(3, 12), (4, 11), (5, 10)]:
        img[gy, gx] = (140, 110, 60)
        alpha[gy, gx] = True
    for b in range(2, 11):
        x, y = b, b
        img[y, x] = blade_col
        img[y + 1, x] = np.array(blade_col) * 0.85
        alpha[y, x] = True
        alpha[y + 1, x] = True
    return img, alpha


def build_atlas(seed=7, tiles_per_row=ATLAS_TILES):
    """Return the texture atlas as a (TILE * tiles_per_row, TILE * tiles_per_row, 4) uint8 RGBA array."""
    rng = np.random.default_rng(seed)
    tiles = {}
    alpha = {}

    # Standard terrain
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

    def _make_planks(col, var=0.06):
        pl = _noisy(rng, col, var)
        for row in range(4):
            pl[row * 4 + 3, :] *= 0.65
            joint = rng.integers(0, TILE)
            pl[row * 4:row * 4 + 3, joint] *= 0.75
            pl[row * 4 + rng.integers(0, 3), rng.integers(0, TILE, 5)] *= 0.85
        return pl

    tiles[T_PLANKS] = _make_planks((162, 130, 78))
    tiles[T_SPRUCE_PLANKS] = _make_planks((105, 78, 48))
    tiles[T_BIRCH_PLANKS] = _make_planks((205, 192, 145))
    tiles[T_JUNGLE_PLANKS] = _make_planks((160, 115, 82))
    tiles[T_ACACIA_PLANKS] = _make_planks((175, 92, 50))
    tiles[T_DARK_OAK_PLANKS] = _make_planks((66, 43, 20))

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
    tiles[T_RED_SAND] = _noisy(rng, (192, 102, 45), 0.06)

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
    tiles[T_ICE] = _noisy(rng, (140, 185, 245), 0.08)
    tiles[T_SLIME] = _noisy(rng, (110, 205, 90), 0.12)
    tiles[T_OBSIDIAN] = _noisy(rng, (25, 20, 40), 0.18)
    tiles[T_LAVA] = _noisy(rng, (235, 95, 20), 0.15)

    # 1.8 Stones: Granite, Diorite, Andesite & Polished variants
    granite = _noisy(rng, (154, 108, 92), 0.12)
    granite[rng.random((TILE, TILE)) < 0.18] = (185, 175, 170)
    tiles[T_GRANITE] = granite
    tiles[T_POLISHED_GRANITE] = _polished_border(granite * 1.05, (120, 80, 68))

    diorite = _noisy(rng, (195, 195, 200), 0.08)
    diorite[rng.random((TILE, TILE)) < 0.22] = (115, 115, 120)
    tiles[T_DIORITE] = diorite
    tiles[T_POLISHED_DIORITE] = _polished_border(diorite * 1.05, (140, 140, 145))

    andesite = _noisy(rng, (132, 134, 135), 0.08)
    andesite[rng.random((TILE, TILE)) < 0.15] = (100, 102, 105)
    tiles[T_ANDESITE] = andesite
    tiles[T_POLISHED_ANDESITE] = _polished_border(andesite * 1.05, (95, 97, 100))

    # 1.8 Ocean Monument: Prismarine, Prismarine Bricks, Dark Prismarine, Sea Lantern
    tiles[T_PRISMARINE] = _masonry(rng, (99, 158, 143), (65, 120, 110), 4, 4, 0.1)
    tiles[T_PRISMARINE_BRICKS] = _masonry(rng, (95, 168, 155), (60, 120, 110), 4, 8, 0.06)
    tiles[T_DARK_PRISMARINE] = _masonry(rng, (50, 85, 75), (30, 50, 45), 4, 4, 0.1, random_offsets=True)

    sea_lantern = _noisy(rng, (210, 245, 240), 0.05)
    sea_lantern[0, :] = sea_lantern[-1, :] = sea_lantern[:, 0] = sea_lantern[:, -1] = (110, 180, 175)
    sea_lantern[1:15, 1:15] *= rng.uniform(0.95, 1.05, (14, 14, 1))
    tiles[T_SEA_LANTERN] = sea_lantern

    # 1.8 Red Sandstone variants
    rs_side = _noisy(rng, (182, 96, 40), 0.06)
    for row in range(4):
        rs_side[row * 4 + 3, :] *= 0.78
    tiles[T_RED_SANDSTONE_SIDE] = rs_side
    tiles[T_RED_SANDSTONE_TOP] = _noisy(rng, (190, 105, 45), 0.04)
    tiles[T_RED_SANDSTONE_BOTTOM] = _noisy(rng, (160, 80, 32), 0.06)
    chiseled_rs = rs_side.copy()
    chiseled_rs[4:12, 4:12] = (140, 68, 25)
    tiles[T_CHISELED_RED_SANDSTONE] = chiseled_rs
    tiles[T_SMOOTH_RED_SANDSTONE] = _polished_border(tiles[T_RED_SANDSTONE_TOP], (140, 70, 28))

    # 1.8 Soils: Coarse dirt, Podzol
    coarse = dirt.copy()
    coarse[rng.random((TILE, TILE)) < 0.25] = (110, 78, 52)
    tiles[T_COARSE_DIRT] = coarse

    podzol_top = _noisy(rng, (92, 63, 34), 0.12)
    podzol_top[rng.random((TILE, TILE)) < 0.15] = (65, 95, 40)
    tiles[T_PODZOL_TOP] = podzol_top
    podzol_side = dirt.copy()
    podzol_side[:4, :] = podzol_top[:4, :]
    tiles[T_PODZOL_SIDE] = podzol_side

    # 1.8 Sponges
    sponge = _noisy(rng, (195, 190, 70), 0.08)
    for _ in range(12):
        py, px = rng.integers(1, TILE - 2, 2)
        sponge[py:py + 2, px:px + 2] = (140, 135, 40)
    tiles[T_SPONGE] = sponge

    wet_sponge = _noisy(rng, (155, 165, 55), 0.08)
    for _ in range(12):
        py, px = rng.integers(1, TILE - 2, 2)
        wet_sponge[py:py + 2, px:px + 2] = (90, 110, 45)
    tiles[T_WET_SPONGE] = wet_sponge

    # 1.8 Iron Trapdoor (with cutouts)
    iron_td = np.full((TILE, TILE, 3), (200, 200, 205), dtype=float)
    td_alpha = np.ones((TILE, TILE), dtype=bool)
    for cy in [2, 9]:
        for cx in [2, 9]:
            td_alpha[cy:cy + 5, cx:cx + 5] = False
    tiles[T_IRON_TRAPDOOR], alpha[T_IRON_TRAPDOOR] = iron_td, td_alpha

    # Crafting table
    craft_top = tiles[T_PLANKS].copy()
    craft_top[2:14, 2:14] *= 0.85
    craft_top[2, 2:14] = craft_top[13, 2:14] = (60, 40, 20)
    craft_top[2:14, 2] = craft_top[2:14, 13] = (60, 40, 20)
    craft_top[5, 3:13] = craft_top[9, 3:13] = (80, 55, 30)
    craft_top[3:13, 5] = craft_top[3:13, 9] = (80, 55, 30)
    tiles[T_CRAFT_TOP] = craft_top

    craft_side = tiles[T_PLANKS].copy()
    craft_side[3:12, 3:6] = (180, 180, 190)
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

    # Meats & Foods
    def _draw_meat(base_col, marbling_col):
        meat = np.zeros((TILE, TILE, 3), dtype=float)
        m_alpha = np.zeros((TILE, TILE), dtype=bool)
        for y in range(4, 12):
            for x in range(3, 13):
                if math.hypot(x - 7.5, y - 7.5) < 4.2:
                    meat[y, x] = base_col
                    m_alpha[y, x] = True
        meat[5:7, 5:8] = marbling_col
        return meat, m_alpha

    tiles[T_RAW_PORK], alpha[T_RAW_PORK] = _draw_meat((225, 120, 125), (245, 230, 230))
    cooked_pork = tiles[T_RAW_PORK].copy() * 0.65
    cooked_pork[alpha[T_RAW_PORK]] = np.clip(cooked_pork[alpha[T_RAW_PORK]] + np.array([80, 40, 10]), 0, 255)
    tiles[T_COOKED_PORK], alpha[T_COOKED_PORK] = cooked_pork, alpha[T_RAW_PORK]

    # 1.8 Mutton
    tiles[T_RAW_MUTTON], alpha[T_RAW_MUTTON] = _draw_meat((195, 80, 85), (240, 220, 220))
    cooked_mutton = tiles[T_RAW_MUTTON].copy() * 0.6
    cooked_mutton[alpha[T_RAW_MUTTON]] = np.clip(cooked_mutton[alpha[T_RAW_MUTTON]] + np.array([90, 45, 15]), 0, 255)
    tiles[T_COOKED_MUTTON], alpha[T_COOKED_MUTTON] = cooked_mutton, alpha[T_RAW_MUTTON]

    # 1.8 Rabbit
    tiles[T_RAW_RABBIT], alpha[T_RAW_RABBIT] = _draw_meat((215, 140, 130), (240, 235, 235))
    cooked_rabbit = tiles[T_RAW_RABBIT].copy() * 0.65
    cooked_rabbit[alpha[T_RAW_RABBIT]] = np.clip(cooked_rabbit[alpha[T_RAW_RABBIT]] + np.array([95, 50, 15]), 0, 255)
    tiles[T_COOKED_RABBIT], alpha[T_COOKED_RABBIT] = cooked_rabbit, alpha[T_RAW_RABBIT]

    # 1.8 Rabbit Stew (bowl filled with stew)
    stew = np.zeros((TILE, TILE, 3), dtype=float)
    s_alpha = np.zeros((TILE, TILE), dtype=bool)
    for y in range(7, 14):
        for x in range(3, 13):
            if math.hypot(x - 7.5, y - 8.0) < 4.8:
                stew[y, x] = (145, 95, 50)
                s_alpha[y, x] = True
    stew[6:9, 4:12] = (165, 75, 30)
    stew[7, 6:8] = (210, 160, 50)
    tiles[T_RABBIT_STEW], alpha[T_RABBIT_STEW] = stew, s_alpha

    # 1.8 Rabbit's Foot
    foot = np.zeros((TILE, TILE, 3), dtype=float)
    f_alpha = np.zeros((TILE, TILE), dtype=bool)
    for y in range(5, 13):
        foot[y, 7:10] = (195, 175, 150)
        f_alpha[y, 7:10] = True
    foot[11:13, 5:8] = (195, 175, 150)
    f_alpha[11:13, 5:8] = True
    tiles[T_RABBIT_FOOT], alpha[T_RABBIT_FOOT] = foot, f_alpha

    # 1.8 Rabbit Hide
    hide = np.zeros((TILE, TILE, 3), dtype=float)
    h_alpha = np.zeros((TILE, TILE), dtype=bool)
    for y in range(4, 12):
        for x in range(4, 12):
            hide[y, x] = (165, 125, 85)
            h_alpha[y, x] = True
    tiles[T_RABBIT_HIDE], alpha[T_RABBIT_HIDE] = hide, h_alpha

    # 1.8 Prismarine Shard & Crystals
    shard = np.zeros((TILE, TILE, 3), dtype=float)
    sh_alpha = np.zeros((TILE, TILE), dtype=bool)
    for i in range(3, 13):
        shard[i, i] = shard[i, 15 - i] = (120, 205, 185)
        sh_alpha[i, i] = sh_alpha[i, 15 - i] = True
    tiles[T_PRISMARINE_SHARD], alpha[T_PRISMARINE_SHARD] = shard, sh_alpha

    crystals = np.zeros((TILE, TILE, 3), dtype=float)
    crys_alpha = np.zeros((TILE, TILE), dtype=bool)
    crystals[5:11, 7:9] = (180, 240, 230)
    crystals[7:9, 5:11] = (180, 240, 230)
    crys_alpha[5:11, 7:9] = crys_alpha[7:9, 5:11] = True
    tiles[T_PRISMARINE_CRYSTALS], alpha[T_PRISMARINE_CRYSTALS] = crystals, crys_alpha

    # 1.8 Armor Stand
    stand = np.zeros((TILE, TILE, 3), dtype=float)
    st_alpha = np.zeros((TILE, TILE), dtype=bool)
    stand[13:15, 3:13] = (130, 130, 130)
    st_alpha[13:15, 3:13] = True
    stand[3:13, 7:9] = (150, 110, 60)
    st_alpha[3:13, 7:9] = True
    stand[4:6, 4:12] = (150, 110, 60)
    st_alpha[4:6, 4:12] = True
    tiles[T_ARMOR_STAND], alpha[T_ARMOR_STAND] = stand, st_alpha

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

    # Mob textures
    zombie_face = _noisy(rng, (45, 135, 55), 0.1)
    zombie_face[6:8, 3:5] = (15, 15, 20)
    zombie_face[6:8, 11:13] = (15, 15, 20)
    zombie_face[10:12, 6:10] = (25, 80, 30)
    tiles[T_ZOMBIE_FACE] = zombie_face
    tiles[T_ZOMBIE_BODY] = _noisy(rng, (40, 150, 160), 0.08)

    pig_face = _noisy(rng, (245, 165, 165), 0.08)
    pig_face[6:8, 2:4] = (20, 20, 20)
    pig_face[6:8, 12:14] = (20, 20, 20)
    pig_face[8:12, 5:11] = (225, 120, 130)
    pig_face[9:11, 6] = pig_face[9:11, 9] = (120, 50, 60)
    tiles[T_PIG_FACE] = pig_face
    tiles[T_PIG_BODY] = _noisy(rng, (240, 160, 160), 0.08)

    atlas = np.zeros((TILE * tiles_per_row, TILE * tiles_per_row, 4))
    for t, img in tiles.items():
        ty, tx = divmod(t, tiles_per_row)
        cell = (slice(ty * TILE, (ty + 1) * TILE), slice(tx * TILE, (tx + 1) * TILE))
        atlas[cell + (slice(0, 3),)] = img
        atlas[cell + (3,)] = 255 * alpha.get(t, np.ones((TILE, TILE), dtype=bool))
    return np.clip(atlas, 0, 255).astype(np.uint8)
