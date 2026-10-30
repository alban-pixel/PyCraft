"""Block types, items, tools, properties, and procedural 256x256 texture atlas (Minecraft 1.8 Bountiful Update)."""
import math
import numpy as np

TILE = 16
ATLAS_TILES = 16  # 16x16 tiles = 256x256 pixels

# Block IDs (0 to 163) - Complete Minecraft 1.8 Catalog
(
    # Core terrain (0..23)
    AIR, GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, SAND, BRICK,
    GLASS, WATER, COAL_ORE, IRON_ORE, BEDROCK, GOLD_ORE, DIAMOND_ORE, GLOWSTONE, SNOW, CRAFTING_TABLE,
    ICE, SLIME, OBSIDIAN, LAVA,
    # 1.8 Stone & Ocean & Red Sandstone (24..47)
    GRANITE, POLISHED_GRANITE, DIORITE, POLISHED_DIORITE, ANDESITE, POLISHED_ANDESITE,
    PRISMARINE, PRISMARINE_BRICKS, DARK_PRISMARINE, SEA_LANTERN,
    RED_SAND, RED_SANDSTONE, CHISELED_RED_SANDSTONE, SMOOTH_RED_SANDSTONE,
    COARSE_DIRT, PODZOL, SPONGE, WET_SPONGE,
    SPRUCE_PLANKS, BIRCH_PLANKS, JUNGLE_PLANKS, ACACIA_PLANKS, DARK_OAK_PLANKS,
    IRON_TRAPDOOR,
    # Workstations & Containers (48..61)
    FURNACE, LIT_FURNACE, CHEST, ENDER_CHEST, TRAPPED_CHEST,
    DISPENSER, DROPPER, HOPPER, BREWING_STAND, ANVIL,
    ENCHANTING_TABLE, JUKEBOX, NOTE_BLOCK, BEACON,
    # Cutout & Cross-model Flora / Utilities (62..84)
    TORCH, REDSTONE_TORCH,
    TALL_GRASS, FERN, DEAD_BUSH,
    DANDELION, POPPY, BLUE_ORCHID, ALLIUM, RED_TULIP, OXEYE_DAISY, SUNFLOWER,
    BROWN_MUSHROOM, RED_MUSHROOM,
    SUGAR_CANE, CACTUS,
    OAK_SAPLING, SPRUCE_SAPLING, BIRCH_SAPLING,
    LADDER, VINE, LILY_PAD, COBWEB,
    # Slabs, Stairs & Partials (85..102)
    STONE_SLAB, OAK_SLAB, COBBLESTONE_SLAB, BRICK_SLAB, STONE_BRICK_SLAB, SANDSTONE_SLAB,
    OAK_STAIRS, COBBLESTONE_STAIRS, BRICK_STAIRS, STONE_BRICK_STAIRS, NETHER_BRICK_STAIRS,
    OAK_FENCE, OAK_FENCE_GATE, IRON_BARS, GLASS_PANE,
    OAK_DOOR, IRON_DOOR, WOODEN_TRAPDOOR,
    # Redstone & Mechanisms (103..121)
    REDSTONE_WIRE, REDSTONE_REPEATER, REDSTONE_COMPARATOR,
    REDSTONE_LAMP, LIT_REDSTONE_LAMP,
    LEVER, STONE_BUTTON, WOODEN_BUTTON, STONE_PRESSURE_PLATE, WOODEN_PRESSURE_PLATE,
    RAIL, POWERED_RAIL, DETECTOR_RAIL, ACTIVATOR_RAIL,
    PISTON, STICKY_PISTON, DAYLIGHT_DETECTOR, TRIPWIRE_HOOK, TNT,
    # Minerals, Nether, End & Decor (122..163)
    COAL_BLOCK, IRON_BLOCK, GOLD_BLOCK, DIAMOND_BLOCK, EMERALD_BLOCK, REDSTONE_BLOCK, LAPIS_BLOCK,
    LAPIS_ORE, EMERALD_ORE, NETHER_QUARTZ_ORE, REDSTONE_ORE, LIT_REDSTONE_ORE,
    QUARTZ_BLOCK, CHISELED_QUARTZ, PILLAR_QUARTZ,
    STONE_BRICKS, MOSSY_STONE_BRICKS, CRACKED_STONE_BRICKS, CHISELED_STONE_BRICKS, MOSSY_COBBLESTONE,
    NETHERRACK, SOUL_SAND, NETHER_BRICKS, END_STONE,
    CLAY_BLOCK, HARDENED_CLAY, HAY_BALE, BOOKSHELF,
    PUMPKIN, JACK_O_LANTERN, MELON_BLOCK,
    MYCELIUM, FARMLAND, WHEAT_CROPS, BED_BLOCK,
    WHITE_WOOL, RED_WOOL, BLUE_WOOL, YELLOW_WOOL, GREEN_WOOL, BLACK_WOOL,
    WHITE_CARPET,
) = range(164)

BLOCK_NAMES = [
    # 0..23
    "Air", "Grass", "Dirt", "Stone", "Cobblestone", "Planks", "Log", "Leaves", "Sand", "Brick",
    "Glass", "Water", "Coal ore", "Iron ore", "Bedrock", "Gold ore", "Diamond ore", "Glowstone", "Snow",
    "Crafting table", "Ice", "Slime", "Obsidian", "Lava",
    # 24..47
    "Granite", "Polished Granite", "Diorite", "Polished Diorite", "Andesite", "Polished Andesite",
    "Prismarine", "Prismarine Bricks", "Dark Prismarine", "Sea Lantern",
    "Red Sand", "Red Sandstone", "Chiseled Red Sandstone", "Smooth Red Sandstone",
    "Coarse Dirt", "Podzol", "Sponge", "Wet Sponge",
    "Spruce Planks", "Birch Planks", "Jungle Planks", "Acacia Planks", "Dark Oak Planks",
    "Iron Trapdoor",
    # 48..61
    "Furnace", "Lit Furnace", "Chest", "Ender Chest", "Trapped Chest",
    "Dispenser", "Dropper", "Hopper", "Brewing Stand", "Anvil",
    "Enchanting Table", "Jukebox", "Note Block", "Beacon",
    # 62..84
    "Torch", "Redstone Torch",
    "Tall Grass", "Fern", "Dead Bush",
    "Dandelion", "Poppy", "Blue Orchid", "Allium", "Red Tulip", "Oxeye Daisy", "Sunflower",
    "Brown Mushroom", "Red Mushroom",
    "Sugar Cane", "Cactus",
    "Oak Sapling", "Spruce Sapling", "Birch Sapling",
    "Ladder", "Vines", "Lily Pad", "Cobweb",
    # 85..102
    "Stone Slab", "Oak Wood Slab", "Cobblestone Slab", "Brick Slab", "Stone Brick Slab", "Sandstone Slab",
    "Oak Wood Stairs", "Cobblestone Stairs", "Brick Stairs", "Stone Brick Stairs", "Nether Brick Stairs",
    "Oak Fence", "Oak Fence Gate", "Iron Bars", "Glass Pane",
    "Wooden Door", "Iron Door", "Wooden Trapdoor",
    # 103..121
    "Redstone Wire", "Redstone Repeater", "Redstone Comparator",
    "Redstone Lamp", "Lit Redstone Lamp",
    "Lever", "Stone Button", "Wooden Button", "Stone Pressure Plate", "Wooden Pressure Plate",
    "Rail", "Powered Rail", "Detector Rail", "Activator Rail",
    "Piston", "Sticky Piston", "Daylight Sensor", "Tripwire Hook", "TNT",
    # 122..163
    "Block of Coal", "Block of Iron", "Block of Gold", "Block of Diamond", "Block of Emerald", "Block of Redstone", "Lapis Lazuli Block",
    "Lapis Lazuli Ore", "Emerald Ore", "Nether Quartz Ore", "Redstone Ore", "Lit Redstone Ore",
    "Block of Quartz", "Chiseled Quartz Block", "Pillar Quartz Block",
    "Stone Bricks", "Mossy Stone Bricks", "Cracked Stone Bricks", "Chiseled Stone Bricks", "Mossy Cobblestone",
    "Netherrack", "Soul Sand", "Nether Bricks", "End Stone",
    "Clay", "Hardened Clay", "Hay Bale", "Bookshelf",
    "Pumpkin", "Jack o'Lantern", "Melon",
    "Mycelium", "Farmland", "Crops (Wheat)", "Bed",
    "White Wool", "Red Wool", "Blue Wool", "Yellow Wool", "Green Wool", "Black Wool",
    "White Carpet",
]
NUM_BLOCKS = len(BLOCK_NAMES)

# Item IDs (>= 256)
(
    ITEM_STICK, ITEM_WOOD_PICKAXE, ITEM_STONE_PICKAXE, ITEM_IRON_PICKAXE, ITEM_DIAMOND_PICKAXE,
    ITEM_WOOD_SWORD, ITEM_STONE_SWORD, ITEM_IRON_SWORD, ITEM_DIAMOND_SWORD,
    ITEM_RAW_PORK, ITEM_COOKED_PORK,
    # 1.8 Food & Material Items
    ITEM_RAW_MUTTON, ITEM_COOKED_MUTTON,
    ITEM_RAW_RABBIT, ITEM_COOKED_RABBIT, ITEM_RABBIT_STEW, ITEM_RABBIT_FOOT, ITEM_RABBIT_HIDE,
    ITEM_PRISMARINE_SHARD, ITEM_PRISMARINE_CRYSTALS,
    ITEM_ARMOR_STAND,
    # Extended 1.8 Items
    ITEM_COAL, ITEM_CHARCOAL, ITEM_IRON_INGOT, ITEM_GOLD_INGOT, ITEM_DIAMOND, ITEM_EMERALD,
    ITEM_REDSTONE, ITEM_LAPIS_LAZULI, ITEM_QUARTZ,
    ITEM_BREAD, ITEM_APPLE, ITEM_GOLDEN_APPLE, ITEM_CARROT, ITEM_POTATO, ITEM_BAKED_POTATO,
    ITEM_GOLDEN_CARROT, ITEM_RAW_BEEF, ITEM_STEAK, ITEM_RAW_CHICKEN, ITEM_COOKED_CHICKEN,
    ITEM_GUNPOWDER, ITEM_STRING, ITEM_FEATHER, ITEM_BONE, ITEM_ARROW, ITEM_BOW,
    ITEM_SNOWBALL, ITEM_SLIMEBALL, ITEM_CLAY_BALL, ITEM_BLAZE_ROD, ITEM_GHAST_TEAR,
    ITEM_NETHER_STAR, ITEM_ENDER_PEARL, ITEM_EYE_OF_ENDER, ITEM_LEATHER,
    ITEM_WHEAT, ITEM_WHEAT_SEEDS, ITEM_FLINT,
    ITEM_BUCKET, ITEM_WATER_BUCKET, ITEM_LAVA_BUCKET, ITEM_MILK_BUCKET,
    ITEM_FLINT_AND_STEEL, ITEM_SHEARS,
    ITEM_WOOD_AXE, ITEM_STONE_AXE, ITEM_IRON_AXE, ITEM_DIAMOND_AXE,
    ITEM_WOOD_SHOVEL, ITEM_STONE_SHOVEL, ITEM_IRON_SHOVEL, ITEM_DIAMOND_SHOVEL,
    ITEM_IRON_HELMET, ITEM_IRON_CHESTPLATE, ITEM_IRON_LEGGINGS, ITEM_IRON_BOOTS,
    ITEM_DIAMOND_HELMET, ITEM_DIAMOND_CHESTPLATE, ITEM_DIAMOND_LEGGINGS, ITEM_DIAMOND_BOOTS,
) = range(256, 256 + 81)

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
    # Extended 1.8 Items
    ITEM_COAL: "Coal",
    ITEM_CHARCOAL: "Charcoal",
    ITEM_IRON_INGOT: "Iron Ingot",
    ITEM_GOLD_INGOT: "Gold Ingot",
    ITEM_DIAMOND: "Diamond",
    ITEM_EMERALD: "Emerald",
    ITEM_REDSTONE: "Redstone",
    ITEM_LAPIS_LAZULI: "Lapis Lazuli",
    ITEM_QUARTZ: "Nether Quartz",
    ITEM_BREAD: "Bread",
    ITEM_APPLE: "Apple",
    ITEM_GOLDEN_APPLE: "Golden Apple",
    ITEM_CARROT: "Carrot",
    ITEM_POTATO: "Potato",
    ITEM_BAKED_POTATO: "Baked Potato",
    ITEM_GOLDEN_CARROT: "Golden Carrot",
    ITEM_RAW_BEEF: "Raw Beef",
    ITEM_STEAK: "Steak",
    ITEM_RAW_CHICKEN: "Raw Chicken",
    ITEM_COOKED_CHICKEN: "Cooked Chicken",
    ITEM_GUNPOWDER: "Gunpowder",
    ITEM_STRING: "String",
    ITEM_FEATHER: "Feather",
    ITEM_BONE: "Bone",
    ITEM_ARROW: "Arrow",
    ITEM_BOW: "Bow",
    ITEM_SNOWBALL: "Snowball",
    ITEM_SLIMEBALL: "Slimeball",
    ITEM_CLAY_BALL: "Clay Ball",
    ITEM_BLAZE_ROD: "Blaze Rod",
    ITEM_GHAST_TEAR: "Ghast Tear",
    ITEM_NETHER_STAR: "Nether Star",
    ITEM_ENDER_PEARL: "Ender Pearl",
    ITEM_EYE_OF_ENDER: "Eye of Ender",
    ITEM_LEATHER: "Leather",
    ITEM_WHEAT: "Wheat",
    ITEM_WHEAT_SEEDS: "Wheat Seeds",
    ITEM_FLINT: "Flint",
    ITEM_BUCKET: "Bucket",
    ITEM_WATER_BUCKET: "Water Bucket",
    ITEM_LAVA_BUCKET: "Lava Bucket",
    ITEM_MILK_BUCKET: "Milk Bucket",
    ITEM_FLINT_AND_STEEL: "Flint and Steel",
    ITEM_SHEARS: "Shears",
    ITEM_WOOD_AXE: "Wooden Axe",
    ITEM_STONE_AXE: "Stone Axe",
    ITEM_IRON_AXE: "Iron Axe",
    ITEM_DIAMOND_AXE: "Diamond Axe",
    ITEM_WOOD_SHOVEL: "Wooden Shovel",
    ITEM_STONE_SHOVEL: "Stone Shovel",
    ITEM_IRON_SHOVEL: "Iron Shovel",
    ITEM_DIAMOND_SHOVEL: "Diamond Shovel",
    ITEM_IRON_HELMET: "Iron Helmet",
    ITEM_IRON_CHESTPLATE: "Iron Chestplate",
    ITEM_IRON_LEGGINGS: "Iron Leggings",
    ITEM_IRON_BOOTS: "Iron Boots",
    ITEM_DIAMOND_HELMET: "Diamond Helmet",
    ITEM_DIAMOND_CHESTPLATE: "Diamond Chestplate",
    ITEM_DIAMOND_LEGGINGS: "Diamond Leggings",
    ITEM_DIAMOND_BOOTS: "Diamond Boots",
}

# Blocks placeable directly in world
PLACEABLE = [b for b in range(1, NUM_BLOCKS)]
DEFAULT_HOTBAR = [GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, TORCH, FURNACE, CRAFTING_TABLE]

# Creative Catalog
CREATIVE_CATALOG = list(range(1, NUM_BLOCKS)) + list(ITEM_NAMES.keys())

# Non-stackable tools & gear
NON_STACKABLE = {
    ITEM_WOOD_PICKAXE, ITEM_STONE_PICKAXE, ITEM_IRON_PICKAXE, ITEM_DIAMOND_PICKAXE,
    ITEM_WOOD_SWORD, ITEM_STONE_SWORD, ITEM_IRON_SWORD, ITEM_DIAMOND_SWORD,
    ITEM_WOOD_AXE, ITEM_STONE_AXE, ITEM_IRON_AXE, ITEM_DIAMOND_AXE,
    ITEM_WOOD_SHOVEL, ITEM_STONE_SHOVEL, ITEM_IRON_SHOVEL, ITEM_DIAMOND_SHOVEL,
    ITEM_BOW, ITEM_FLINT_AND_STEEL, ITEM_SHEARS, ITEM_ARMOR_STAND,
    ITEM_WATER_BUCKET, ITEM_LAVA_BUCKET, ITEM_MILK_BUCKET,
    ITEM_IRON_HELMET, ITEM_IRON_CHESTPLATE, ITEM_IRON_LEGGINGS, ITEM_IRON_BOOTS,
    ITEM_DIAMOND_HELMET, ITEM_DIAMOND_CHESTPLATE, ITEM_DIAMOND_LEGGINGS, ITEM_DIAMOND_BOOTS,
}

def _flags(*blocks):
    table = np.zeros(NUM_BLOCKS, dtype=bool)
    table[list(blocks)] = True
    return table

# Cutout & Cross Model definitions
CROSS_MODEL = _flags(
    TORCH, REDSTONE_TORCH,
    TALL_GRASS, FERN, DEAD_BUSH,
    DANDELION, POPPY, BLUE_ORCHID, ALLIUM, RED_TULIP, OXEYE_DAISY, SUNFLOWER,
    BROWN_MUSHROOM, RED_MUSHROOM,
    SUGAR_CANE, OAK_SAPLING, SPRUCE_SAPLING, BIRCH_SAPLING,
    COBWEB,
)

SLAB = _flags(
    STONE_SLAB, OAK_SLAB, COBBLESTONE_SLAB, BRICK_SLAB, STONE_BRICK_SLAB, SANDSTONE_SLAB,
)

NON_OPAQUE_BLOCKS = [
    AIR, LEAVES, GLASS, WATER, ICE, SLIME, LAVA, IRON_TRAPDOOR, WOODEN_TRAPDOOR,
    OAK_DOOR, IRON_DOOR, CHEST, ENDER_CHEST, TRAPPED_CHEST, ENCHANTING_TABLE, ANVIL,
    BREWING_STAND, HOPPER, BEACON, BED_BLOCK, WHITE_CARPET, OAK_FENCE, OAK_FENCE_GATE,
    IRON_BARS, GLASS_PANE, LADDER, VINE, LILY_PAD, COBWEB, CACTUS,
    STONE_SLAB, OAK_SLAB, COBBLESTONE_SLAB, BRICK_SLAB, STONE_BRICK_SLAB, SANDSTONE_SLAB,
    OAK_STAIRS, COBBLESTONE_STAIRS, BRICK_STAIRS, STONE_BRICK_STAIRS, NETHER_BRICK_STAIRS,
    REDSTONE_WIRE, LEVER, STONE_BUTTON, WOODEN_BUTTON, STONE_PRESSURE_PLATE, WOODEN_PRESSURE_PLATE,
    RAIL, POWERED_RAIL, DETECTOR_RAIL, ACTIVATOR_RAIL, TRIPWIRE_HOOK,
]

NON_SOLID_BLOCKS = [
    AIR, WATER, LAVA,
    TORCH, REDSTONE_TORCH,
    TALL_GRASS, FERN, DEAD_BUSH,
    DANDELION, POPPY, BLUE_ORCHID, ALLIUM, RED_TULIP, OXEYE_DAISY, SUNFLOWER,
    BROWN_MUSHROOM, RED_MUSHROOM,
    SUGAR_CANE, OAK_SAPLING, SPRUCE_SAPLING, BIRCH_SAPLING,
    LADDER, VINE, LILY_PAD, COBWEB,
    REDSTONE_WIRE, LEVER, STONE_BUTTON, WOODEN_BUTTON, STONE_PRESSURE_PLATE, WOODEN_PRESSURE_PLATE,
    RAIL, POWERED_RAIL, DETECTOR_RAIL, ACTIVATOR_RAIL, TRIPWIRE_HOOK,
]

CUTOUT_BLOCKS = [
    LEAVES, GLASS, ICE, SLIME, IRON_TRAPDOOR, WOODEN_TRAPDOOR,
    OAK_DOOR, IRON_DOOR, IRON_BARS, GLASS_PANE, LADDER, VINE, LILY_PAD, COBWEB,
    TORCH, REDSTONE_TORCH,
    TALL_GRASS, FERN, DEAD_BUSH,
    DANDELION, POPPY, BLUE_ORCHID, ALLIUM, RED_TULIP, OXEYE_DAISY, SUNFLOWER,
    BROWN_MUSHROOM, RED_MUSHROOM,
    SUGAR_CANE, OAK_SAPLING, SPRUCE_SAPLING, BIRCH_SAPLING,
    RAIL, POWERED_RAIL, DETECTOR_RAIL, ACTIVATOR_RAIL, REDSTONE_WIRE,
    CACTUS, BREWING_STAND, HOPPER, ANVIL, ENCHANTING_TABLE, LEVER, TRIPWIRE_HOOK,
]

OPAQUE = ~_flags(*NON_OPAQUE_BLOCKS) & ~CROSS_MODEL
SOLID = ~_flags(*NON_SOLID_BLOCKS)
CUTOUT = _flags(*CUTOUT_BLOCKS)
SELF_CULL = _flags(GLASS, WATER, ICE, LAVA, SLIME)
TARGETABLE = ~_flags(AIR, WATER, LAVA)
UNBREAKABLE = _flags(BEDROCK)

# Atlas tile indices (0 to 255)
# Row 0: Standard terrain (0..15)
(
    T_GRASS_TOP, T_GRASS_SIDE, T_DIRT, T_STONE, T_COBBLE, T_PLANKS, T_LOG_SIDE, T_LOG_TOP, T_LEAVES,
    T_SAND, T_BRICK, T_GLASS, T_WATER, T_COAL, T_IRON, T_BEDROCK,
) = range(16)

# Row 1: Ores, utilities, and 1.8 stones (16..31)
(
    T_GOLD, T_DIAMOND, T_GLOWSTONE, T_SNOW, T_SNOW_SIDE,
    T_CRAFT_TOP, T_CRAFT_SIDE, T_ICE, T_SLIME, T_OBSIDIAN, T_LAVA,
    T_GRANITE, T_POLISHED_GRANITE, T_DIORITE, T_POLISHED_DIORITE, T_ANDESITE,
) = range(16, 32)

# Row 2: 1.8 Ocean & Red Sandstone (32..47)
(
    T_POLISHED_ANDESITE, T_PRISMARINE, T_PRISMARINE_BRICKS, T_DARK_PRISMARINE, T_SEA_LANTERN,
    T_RED_SAND, T_RED_SANDSTONE_SIDE, T_RED_SANDSTONE_TOP, T_RED_SANDSTONE_BOTTOM,
    T_CHISELED_RED_SANDSTONE, T_SMOOTH_RED_SANDSTONE,
    T_COARSE_DIRT, T_PODZOL_TOP, T_PODZOL_SIDE, T_SPONGE, T_WET_SPONGE,
) = range(32, 48)

# Row 3: 1.8 Wood planks & mechanics (48..63)
(
    T_SPRUCE_PLANKS, T_BIRCH_PLANKS, T_JUNGLE_PLANKS, T_ACACIA_PLANKS, T_DARK_OAK_PLANKS,
    T_IRON_TRAPDOOR,
    T_CRACK_0, T_CRACK_1, T_CRACK_2, T_CRACK_3,
    T_ZOMBIE_FACE, T_ZOMBIE_BODY, T_PIG_FACE, T_PIG_BODY,
    T_STICK, T_ARMOR_STAND,
) = range(48, 64)

# Row 4: Tools & Food (64..79)
(
    T_WOOD_PICKAXE, T_STONE_PICKAXE, T_IRON_PICKAXE, T_DIAMOND_PICKAXE,
    T_WOOD_SWORD, T_STONE_SWORD, ITEM_IRON_SWORD_TILE, T_DIAMOND_SWORD,
    T_RAW_PORK, T_COOKED_PORK, T_RAW_MUTTON, T_COOKED_MUTTON,
    T_RAW_RABBIT, T_COOKED_RABBIT, T_RABBIT_STEW, T_RABBIT_FOOT,
) = range(64, 80)
T_IRON_SWORD = ITEM_IRON_SWORD_TILE

# Row 5: 1.8 Materials & Furnaces / Chests (80..95)
(
    T_RABBIT_HIDE, T_PRISMARINE_SHARD, T_PRISMARINE_CRYSTALS,
    T_FURNACE_FRONT, T_FURNACE_FRONT_LIT, T_FURNACE_SIDE, T_FURNACE_TOP,
    T_CHEST_FRONT, T_CHEST_SIDE, T_CHEST_TOP,
    T_DISPENSER_FRONT, T_HOPPER_TOP, T_HOPPER_SIDE,
    T_BREWING_STAND, T_ANVIL_TOP, T_ANVIL_SIDE,
) = range(80, 96)

# Row 6: Workstations, Torches & Flowers (96..111)
(
    T_ENCHANTING_TABLE_TOP, T_ENCHANTING_TABLE_SIDE,
    T_JUKEBOX_TOP, T_JUKEBOX_SIDE, T_NOTE_BLOCK, T_BEACON,
    T_TORCH, T_REDSTONE_TORCH,
    T_TALL_GRASS, T_FERN, T_DEAD_BUSH,
    T_DANDELION, T_POPPY, T_BLUE_ORCHID, T_ALLIUM, T_RED_TULIP,
) = range(96, 112)

# Row 7: Flora, Crops, Ladder, Doors (112..127)
(
    T_OXEYE_DAISY, T_SUNFLOWER,
    T_BROWN_MUSHROOM, T_RED_MUSHROOM,
    T_SUGAR_CANE, T_CACTUS_SIDE, T_CACTUS_TOP,
    T_OAK_SAPLING, T_SPRUCE_SAPLING, T_BIRCH_SAPLING,
    T_LADDER, T_VINE, T_LILY_PAD, T_COBWEB,
    T_WOODEN_DOOR_TOP, T_WOODEN_DOOR_BOTTOM,
) = range(112, 128)

# Row 8: Doors, Trapdoors, Redstone (128..143)
(
    T_IRON_DOOR_TOP, T_IRON_DOOR_BOTTOM,
    T_WOODEN_TRAPDOOR,
    T_REDSTONE_WIRE, T_REDSTONE_REPEATER, T_REDSTONE_COMPARATOR,
    T_REDSTONE_LAMP_OFF, T_REDSTONE_LAMP_ON,
    T_LEVER, T_STONE_BUTTON,
    T_RAIL, T_POWERED_RAIL,
    T_PISTON_TOP, T_PISTON_SIDE,
    T_DAYLIGHT_DETECTOR, T_TNT_SIDE,
) = range(128, 144)

# Row 9: TNT, Mineral Blocks, Ores (144..159)
(
    T_TNT_TOP, T_TNT_BOTTOM,
    T_COAL_BLOCK, T_IRON_BLOCK, T_GOLD_BLOCK, T_DIAMOND_BLOCK,
    T_EMERALD_BLOCK, T_REDSTONE_BLOCK, T_LAPIS_BLOCK,
    T_LAPIS_ORE, T_EMERALD_ORE, T_NETHER_QUARTZ_ORE, T_REDSTONE_ORE,
    T_QUARTZ_BLOCK_TOP, T_QUARTZ_BLOCK_SIDE, T_QUARTZ_PILLAR_SIDE,
) = range(144, 160)

# Row 10: Nether, End, Bricks, Hay, Books (160..175)
(
    T_STONE_BRICKS, T_MOSSY_STONE_BRICKS, T_CRACKED_STONE_BRICKS, T_CHISELED_STONE_BRICKS,
    T_MOSSY_COBBLE, T_NETHERRACK, T_SOUL_SAND, T_NETHER_BRICKS, T_END_STONE,
    T_CLAY_BLOCK, T_HARDENED_CLAY,
    T_HAY_SIDE, T_HAY_TOP, T_BOOKSHELF,
    T_PUMPKIN_SIDE, T_PUMPKIN_TOP,
) = range(160, 176)

# Row 11: Pumpkin, Melon, Farmland, Wool (176..191)
(
    T_PUMPKIN_FRONT, T_JACK_O_LANTERN_FRONT,
    T_MELON_SIDE, T_MELON_TOP,
    T_FARMLAND_TOP, T_WHEAT_STAGE_7,
    T_WHITE_WOOL, T_RED_WOOL, T_BLUE_WOOL, T_YELLOW_WOOL, T_GREEN_WOOL, T_BLACK_WOOL,
    T_IRON_BARS, T_GLASS_PANE, T_STONE_SLAB_SIDE, T_MYCELIUM_TOP,
) = range(176, 192)

# Row 12: Mob Faces & Parts (192..207)
(
    T_CREEPER_FACE, T_SKELETON_FACE, T_SPIDER_FACE, T_ENDERMAN_FACE,
    T_COW_FACE, T_SHEEP_FACE, T_CHICKEN_FACE, T_VILLAGER_FACE,
    T_SLIME_FACE, T_GHAST_FACE, T_BLAZE_FACE, T_WOLF_FACE,
    T_OCELOT_FACE, T_IRON_GOLEM_FACE, T_SNOW_GOLEM_FACE, T_WITCH_FACE,
) = range(192, 208)

# Row 13: Items & Foods (208..223)
(
    T_COAL_ITEM, T_IRON_INGOT, T_GOLD_INGOT, T_DIAMOND_ITEM,
    T_EMERALD_ITEM, T_REDSTONE_ITEM, T_LAPIS_ITEM, T_QUARTZ_ITEM,
    T_BREAD, T_APPLE, T_GOLDEN_APPLE, T_CARROT, T_POTATO,
    T_RAW_BEEF, T_STEAK, T_RAW_CHICKEN,
) = range(208, 224)

# Row 14: Mob drops & Gear (224..239)
(
    T_COOKED_CHICKEN, T_GUNPOWDER, T_STRING, T_FEATHER,
    T_BONE, T_ARROW, T_BOW, T_SNOWBALL, T_SLIMEBALL,
    T_BLAZE_ROD, T_GHAST_TEAR, T_NETHER_STAR, T_ENDER_PEARL,
    T_LEATHER, T_WHEAT_ITEM, T_FLINT,
) = range(224, 240)

# Row 15: Buckets, Tools, Armor & Special (240..255)
(
    T_BUCKET, T_WATER_BUCKET, T_LAVA_BUCKET, T_MILK_BUCKET,
    T_FLINT_AND_STEEL, T_SHEARS,
    T_IRON_HELMET, T_IRON_CHESTPLATE, T_IRON_LEGGINGS, T_IRON_BOOTS,
    T_DIAMOND_HELMET, T_DIAMOND_CHESTPLATE, T_DIAMOND_LEGGINGS, T_DIAMOND_BOOTS,
    T_BED_ITEM, T_DRAGON_EGG,
) = range(240, 256)

def _faces(side, top=None, bottom=None, front=None):
    top = side if top is None else top
    bottom = top if bottom is None else bottom
    front = side if front is None else front
    return [side, side, top, bottom, front, side]

# Construct BLOCK_TILES array of shape (NUM_BLOCKS, 6)
_tiles_list = [
    # 0..23 Core terrain
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
    # 24..47 1.8 Stones & Ocean
    _faces(T_GRANITE),
    _faces(T_POLISHED_GRANITE),
    _faces(T_DIORITE),
    _faces(T_POLISHED_DIORITE),
    _faces(T_ANDESITE),
    _faces(T_POLISHED_ANDESITE),
    _faces(T_PRISMARINE),
    _faces(T_PRISMARINE_BRICKS),
    _faces(T_DARK_PRISMARINE),
    _faces(T_SEA_LANTERN),
    _faces(T_RED_SAND),
    _faces(T_RED_SANDSTONE_SIDE, T_RED_SANDSTONE_TOP, T_RED_SANDSTONE_BOTTOM),
    _faces(T_CHISELED_RED_SANDSTONE, T_RED_SANDSTONE_TOP, T_RED_SANDSTONE_BOTTOM),
    _faces(T_SMOOTH_RED_SANDSTONE, T_RED_SANDSTONE_TOP, T_RED_SANDSTONE_BOTTOM),
    _faces(T_COARSE_DIRT),
    _faces(T_PODZOL_SIDE, T_PODZOL_TOP, T_DIRT),
    _faces(T_SPONGE),
    _faces(T_WET_SPONGE),
    _faces(T_SPRUCE_PLANKS),
    _faces(T_BIRCH_PLANKS),
    _faces(T_JUNGLE_PLANKS),
    _faces(T_ACACIA_PLANKS),
    _faces(T_DARK_OAK_PLANKS),
    _faces(T_IRON_TRAPDOOR),
    # 48..61 Workstations & Containers
    _faces(side=T_FURNACE_SIDE, top=T_FURNACE_TOP, bottom=T_FURNACE_TOP, front=T_FURNACE_FRONT),
    _faces(side=T_FURNACE_SIDE, top=T_FURNACE_TOP, bottom=T_FURNACE_TOP, front=T_FURNACE_FRONT_LIT),
    _faces(side=T_CHEST_SIDE, top=T_CHEST_TOP, bottom=T_CHEST_TOP, front=T_CHEST_FRONT),
    _faces(side=T_CHEST_SIDE, top=T_CHEST_TOP, bottom=T_CHEST_TOP, front=T_CHEST_FRONT),
    _faces(side=T_CHEST_SIDE, top=T_CHEST_TOP, bottom=T_CHEST_TOP, front=T_CHEST_FRONT),
    _faces(side=T_FURNACE_SIDE, top=T_FURNACE_TOP, bottom=T_FURNACE_TOP, front=T_DISPENSER_FRONT),
    _faces(side=T_FURNACE_SIDE, top=T_FURNACE_TOP, bottom=T_FURNACE_TOP, front=T_DISPENSER_FRONT),
    _faces(side=T_HOPPER_SIDE, top=T_HOPPER_TOP, bottom=T_HOPPER_SIDE, front=T_HOPPER_SIDE),
    _faces(T_BREWING_STAND),
    _faces(side=T_ANVIL_SIDE, top=T_ANVIL_TOP, bottom=T_ANVIL_SIDE, front=T_ANVIL_SIDE),
    _faces(side=T_ENCHANTING_TABLE_SIDE, top=T_ENCHANTING_TABLE_TOP, bottom=T_OBSIDIAN, front=T_ENCHANTING_TABLE_SIDE),
    _faces(side=T_JUKEBOX_SIDE, top=T_JUKEBOX_TOP, bottom=T_PLANKS, front=T_JUKEBOX_SIDE),
    _faces(T_NOTE_BLOCK),
    _faces(T_BEACON),
    # 62..84 Cutouts & Flora
    _faces(T_TORCH),
    _faces(T_REDSTONE_TORCH),
    _faces(T_TALL_GRASS),
    _faces(T_FERN),
    _faces(T_DEAD_BUSH),
    _faces(T_DANDELION),
    _faces(T_POPPY),
    _faces(T_BLUE_ORCHID),
    _faces(T_ALLIUM),
    _faces(T_RED_TULIP),
    _faces(T_OXEYE_DAISY),
    _faces(T_SUNFLOWER),
    _faces(T_BROWN_MUSHROOM),
    _faces(T_RED_MUSHROOM),
    _faces(T_SUGAR_CANE),
    _faces(side=T_CACTUS_SIDE, top=T_CACTUS_TOP, bottom=T_CACTUS_TOP),
    _faces(T_OAK_SAPLING),
    _faces(T_SPRUCE_SAPLING),
    _faces(T_BIRCH_SAPLING),
    _faces(T_LADDER),
    _faces(T_VINE),
    _faces(T_LILY_PAD),
    _faces(T_COBWEB),
    # 85..102 Slabs, Stairs & Partials
    _faces(side=T_STONE_SLAB_SIDE, top=T_STONE, bottom=T_STONE),
    _faces(side=T_PLANKS, top=T_PLANKS, bottom=T_PLANKS),
    _faces(side=T_COBBLE, top=T_COBBLE, bottom=T_COBBLE),
    _faces(side=T_BRICK, top=T_BRICK, bottom=T_BRICK),
    _faces(side=T_STONE_BRICKS, top=T_STONE_BRICKS, bottom=T_STONE_BRICKS),
    _faces(side=T_RED_SANDSTONE_SIDE, top=T_RED_SANDSTONE_TOP, bottom=T_RED_SANDSTONE_BOTTOM),
    _faces(T_PLANKS),
    _faces(T_COBBLE),
    _faces(T_BRICK),
    _faces(T_STONE_BRICKS),
    _faces(T_NETHER_BRICKS),
    _faces(T_PLANKS),
    _faces(T_PLANKS),
    _faces(T_IRON_BARS),
    _faces(T_GLASS_PANE),
    _faces(T_WOODEN_DOOR_TOP),
    _faces(T_IRON_DOOR_TOP),
    _faces(T_WOODEN_TRAPDOOR),
    # 103..121 Redstone & Mechanisms
    _faces(T_REDSTONE_WIRE),
    _faces(side=T_STONE, top=T_REDSTONE_REPEATER, bottom=T_STONE),
    _faces(side=T_STONE, top=T_REDSTONE_COMPARATOR, bottom=T_STONE),
    _faces(T_REDSTONE_LAMP_OFF),
    _faces(T_REDSTONE_LAMP_ON),
    _faces(T_LEVER),
    _faces(T_STONE_BUTTON),
    _faces(T_PLANKS),
    _faces(T_STONE),
    _faces(T_PLANKS),
    _faces(T_RAIL),
    _faces(T_POWERED_RAIL),
    _faces(T_RAIL),
    _faces(T_POWERED_RAIL),
    _faces(side=T_PISTON_SIDE, top=T_PISTON_TOP, bottom=T_COBBLE),
    _faces(side=T_PISTON_SIDE, top=T_SLIME, bottom=T_COBBLE),
    _faces(side=T_PLANKS, top=T_DAYLIGHT_DETECTOR, bottom=T_PLANKS),
    _faces(T_LEVER),
    _faces(side=T_TNT_SIDE, top=T_TNT_TOP, bottom=T_TNT_BOTTOM),
    # 122..163 Minerals, Nether, End & Decor
    _faces(T_COAL_BLOCK),
    _faces(T_IRON_BLOCK),
    _faces(T_GOLD_BLOCK),
    _faces(T_DIAMOND_BLOCK),
    _faces(T_EMERALD_BLOCK),
    _faces(T_REDSTONE_BLOCK),
    _faces(T_LAPIS_BLOCK),
    _faces(T_LAPIS_ORE),
    _faces(T_EMERALD_ORE),
    _faces(T_NETHER_QUARTZ_ORE),
    _faces(T_REDSTONE_ORE),
    _faces(T_REDSTONE_ORE),
    _faces(side=T_QUARTZ_BLOCK_SIDE, top=T_QUARTZ_BLOCK_TOP, bottom=T_QUARTZ_BLOCK_TOP),
    _faces(side=T_QUARTZ_BLOCK_SIDE, top=T_QUARTZ_BLOCK_TOP, bottom=T_QUARTZ_BLOCK_TOP),
    _faces(side=T_QUARTZ_PILLAR_SIDE, top=T_QUARTZ_BLOCK_TOP, bottom=T_QUARTZ_BLOCK_TOP),
    _faces(T_STONE_BRICKS),
    _faces(T_MOSSY_STONE_BRICKS),
    _faces(T_CRACKED_STONE_BRICKS),
    _faces(T_CHISELED_STONE_BRICKS),
    _faces(T_MOSSY_COBBLE),
    _faces(T_NETHERRACK),
    _faces(T_SOUL_SAND),
    _faces(T_NETHER_BRICKS),
    _faces(T_END_STONE),
    _faces(T_CLAY_BLOCK),
    _faces(T_HARDENED_CLAY),
    _faces(side=T_HAY_SIDE, top=T_HAY_TOP, bottom=T_HAY_TOP),
    _faces(side=T_BOOKSHELF, top=T_PLANKS, bottom=T_PLANKS),
    _faces(side=T_PUMPKIN_SIDE, top=T_PUMPKIN_TOP, bottom=T_PUMPKIN_TOP, front=T_PUMPKIN_FRONT),
    _faces(side=T_PUMPKIN_SIDE, top=T_PUMPKIN_TOP, bottom=T_PUMPKIN_TOP, front=T_JACK_O_LANTERN_FRONT),
    _faces(side=T_MELON_SIDE, top=T_MELON_TOP, bottom=T_MELON_TOP),
    _faces(side=T_GRASS_SIDE, top=T_MYCELIUM_TOP, bottom=T_DIRT),
    _faces(side=T_DIRT, top=T_FARMLAND_TOP, bottom=T_DIRT),
    _faces(T_WHEAT_STAGE_7),
    _faces(T_BED_ITEM),
    _faces(T_WHITE_WOOL),
    _faces(T_RED_WOOL),
    _faces(T_BLUE_WOOL),
    _faces(T_YELLOW_WOOL),
    _faces(T_GREEN_WOOL),
    _faces(T_BLACK_WOOL),
    _faces(T_WHITE_WOOL),
]

BLOCK_TILES = np.array(_tiles_list, dtype=np.int32)

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
    # Extended 1.8 Items
    ITEM_COAL: T_COAL_ITEM,
    ITEM_CHARCOAL: T_COAL_ITEM,
    ITEM_IRON_INGOT: T_IRON_INGOT,
    ITEM_GOLD_INGOT: T_GOLD_INGOT,
    ITEM_DIAMOND: T_DIAMOND_ITEM,
    ITEM_EMERALD: T_EMERALD_ITEM,
    ITEM_REDSTONE: T_REDSTONE_ITEM,
    ITEM_LAPIS_LAZULI: T_LAPIS_ITEM,
    ITEM_QUARTZ: T_QUARTZ_ITEM,
    ITEM_BREAD: T_BREAD,
    ITEM_APPLE: T_APPLE,
    ITEM_GOLDEN_APPLE: T_GOLDEN_APPLE,
    ITEM_CARROT: T_CARROT,
    ITEM_POTATO: T_POTATO,
    ITEM_BAKED_POTATO: T_POTATO,
    ITEM_GOLDEN_CARROT: T_CARROT,
    ITEM_RAW_BEEF: T_RAW_BEEF,
    ITEM_STEAK: T_STEAK,
    ITEM_RAW_CHICKEN: T_RAW_CHICKEN,
    ITEM_COOKED_CHICKEN: T_COOKED_CHICKEN,
    ITEM_GUNPOWDER: T_GUNPOWDER,
    ITEM_STRING: T_STRING,
    ITEM_FEATHER: T_FEATHER,
    ITEM_BONE: T_BONE,
    ITEM_ARROW: T_ARROW,
    ITEM_BOW: T_BOW,
    ITEM_SNOWBALL: T_SNOWBALL,
    ITEM_SLIMEBALL: T_SLIMEBALL,
    ITEM_CLAY_BALL: T_SNOWBALL,
    ITEM_BLAZE_ROD: T_BLAZE_ROD,
    ITEM_GHAST_TEAR: T_GHAST_TEAR,
    ITEM_NETHER_STAR: T_NETHER_STAR,
    ITEM_ENDER_PEARL: T_ENDER_PEARL,
    ITEM_EYE_OF_ENDER: T_ENDER_PEARL,
    ITEM_LEATHER: T_LEATHER,
    ITEM_WHEAT: T_WHEAT_ITEM,
    ITEM_WHEAT_SEEDS: T_WHEAT_ITEM,
    ITEM_FLINT: T_FLINT,
    ITEM_BUCKET: T_BUCKET,
    ITEM_WATER_BUCKET: T_WATER_BUCKET,
    ITEM_LAVA_BUCKET: T_LAVA_BUCKET,
    ITEM_MILK_BUCKET: T_MILK_BUCKET,
    ITEM_FLINT_AND_STEEL: T_FLINT_AND_STEEL,
    ITEM_SHEARS: T_SHEARS,
    ITEM_WOOD_AXE: T_WOOD_PICKAXE,
    ITEM_STONE_AXE: T_STONE_PICKAXE,
    ITEM_IRON_AXE: T_IRON_PICKAXE,
    ITEM_DIAMOND_AXE: T_DIAMOND_PICKAXE,
    ITEM_WOOD_SHOVEL: T_WOOD_PICKAXE,
    ITEM_STONE_SHOVEL: T_STONE_PICKAXE,
    ITEM_IRON_SHOVEL: T_IRON_PICKAXE,
    ITEM_DIAMOND_SHOVEL: T_DIAMOND_PICKAXE,
    ITEM_IRON_HELMET: T_IRON_HELMET,
    ITEM_IRON_CHESTPLATE: T_IRON_CHESTPLATE,
    ITEM_IRON_LEGGINGS: T_IRON_LEGGINGS,
    ITEM_IRON_BOOTS: T_IRON_BOOTS,
    ITEM_DIAMOND_HELMET: T_DIAMOND_HELMET,
    ITEM_DIAMOND_CHESTPLATE: T_DIAMOND_CHESTPLATE,
    ITEM_DIAMOND_LEGGINGS: T_DIAMOND_LEGGINGS,
    ITEM_DIAMOND_BOOTS: T_DIAMOND_BOOTS,
}

BLOCK_COLORS = {
    GRASS: 3, DIRT: 4, STONE: 6, COBBLESTONE: 13, PLANKS: 4, LOG: 4, LEAVES: 11,
    SAND: 10, BRICK: 2, GLASS: 7, WATER: 12, COAL_ORE: 0, IRON_ORE: 15,
    BEDROCK: 0, GOLD_ORE: 10, DIAMOND_ORE: 12, GLOWSTONE: 9, SNOW: 7, CRAFTING_TABLE: 4,
    ICE: 12, SLIME: 3, OBSIDIAN: 0, LAVA: 9,
    FURNACE: 6, LIT_FURNACE: 9, CHEST: 4, TORCH: 10, TNT: 8,
}
for b in range(NUM_BLOCKS):
    if b not in BLOCK_COLORS:
        BLOCK_COLORS[b] = 6

BLOCK_HARDNESS = {
    LEAVES: 0.25, GLASS: 0.3, SNOW: 0.35, SAND: 0.45, DIRT: 0.5, GRASS: 0.55,
    GLOWSTONE: 0.4, PLANKS: 1.2, LOG: 1.4, CRAFTING_TABLE: 1.2, FURNACE: 2.2, LIT_FURNACE: 2.2,
    CHEST: 1.5, TORCH: 0.05, TNT: 0.0,
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
for b in range(NUM_BLOCKS):
    if b not in BLOCK_HARDNESS:
        BLOCK_HARDNESS[b] = 1.5

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
    ITEM_WOOD_AXE: 3,
    ITEM_STONE_AXE: 4,
    ITEM_IRON_AXE: 5,
    ITEM_DIAMOND_AXE: 6,
    ITEM_WOOD_SHOVEL: 1,
    ITEM_STONE_SHOVEL: 2,
    ITEM_IRON_SHOVEL: 3,
    ITEM_DIAMOND_SHOVEL: 4,
}

FOOD_HEAL = {
    ITEM_RAW_PORK: 3,
    ITEM_COOKED_PORK: 8,
    ITEM_RAW_MUTTON: 2,
    ITEM_COOKED_MUTTON: 6,
    ITEM_RAW_RABBIT: 3,
    ITEM_COOKED_RABBIT: 5,
    ITEM_RABBIT_STEW: 10,
    ITEM_BREAD: 5,
    ITEM_APPLE: 4,
    ITEM_GOLDEN_APPLE: 4,
    ITEM_CARROT: 3,
    ITEM_POTATO: 1,
    ITEM_BAKED_POTATO: 5,
    ITEM_GOLDEN_CARROT: 6,
    ITEM_RAW_BEEF: 3,
    ITEM_STEAK: 8,
    ITEM_RAW_CHICKEN: 2,
    ITEM_COOKED_CHICKEN: 6,
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

    # Terrain
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

    tiles[T_COBBLE] = _masonry(rng, (120, 120, 120), (60, 60, 60), 4, 6, 0.25, random_offsets=True)
    tiles[T_PLANKS] = _masonry(rng, (162, 130, 78), (95, 67, 30), 4, 16, 0.12)

    log_s = _noisy(rng, (103, 82, 49), 0.1)
    for x in [3, 7, 11]:
        log_s[:, x:x + 2] *= 0.7
    tiles[T_LOG_SIDE] = log_s

    log_t = _noisy(rng, (162, 130, 78), 0.08)
    yy, xx = np.ogrid[:TILE, :TILE]
    r = np.sqrt((xx - 7.5)**2 + (yy - 7.5)**2)
    log_t[r > 7] = (103, 82, 49)
    for ring in [3, 5]:
        log_t[np.abs(r - ring) < 0.6] *= 0.8
    tiles[T_LOG_TOP] = log_t

    leaves = _noisy(rng, (56, 116, 32), 0.35)
    leaf_a = rng.random((TILE, TILE)) > 0.18
    tiles[T_LEAVES] = leaves
    alpha[T_LEAVES] = leaf_a

    tiles[T_SAND] = _noisy(rng, (219, 207, 153), 0.08)
    tiles[T_BRICK] = _masonry(rng, (150, 66, 50), (210, 200, 190), 4, 8, 0.15)

    glass = np.full((TILE, TILE, 3), 255.0)
    g_a = np.zeros((TILE, TILE), dtype=bool)
    g_a[0, :] = g_a[-1, :] = g_a[:, 0] = g_a[:, -1] = True
    g_a[3, 3:6] = g_a[4, 4:7] = True
    tiles[T_GLASS] = glass
    alpha[T_GLASS] = g_a

    water = _noisy(rng, (44, 96, 216), 0.12)
    for y in range(0, TILE, 2):
        water[y, :] *= 1.15
    tiles[T_WATER] = water

    tiles[T_COAL] = _ore(rng, stone, (35, 35, 35), 8)
    tiles[T_IRON] = _ore(rng, stone, (216, 175, 147), 7)
    tiles[T_BEDROCK] = _noisy(rng, (40, 40, 40), 0.6)
    tiles[T_GOLD] = _ore(rng, stone, (255, 235, 80), 7)
    tiles[T_DIAMOND] = _ore(rng, stone, (92, 235, 230), 6)
    tiles[T_GLOWSTONE] = _noisy(rng, (250, 190, 80), 0.25)
    tiles[T_SNOW] = _noisy(rng, (245, 250, 255), 0.04)

    snow_s = dirt.copy()
    snow_s[:4, :] = (245, 250, 255)
    tiles[T_SNOW_SIDE] = snow_s

    craft_s = tiles[T_PLANKS].copy()
    craft_s[3:13, 3:13] = _noisy(rng, (90, 60, 30), 0.15)[:10, :10]
    tiles[T_CRAFT_SIDE] = craft_s
    craft_t = tiles[T_PLANKS].copy()
    craft_t[2:14, 2:14:6] = (60, 40, 20)
    craft_t[2:14:6, 2:14] = (60, 40, 20)
    tiles[T_CRAFT_TOP] = craft_t

    tiles[T_ICE] = _noisy(rng, (160, 200, 250), 0.08)
    tiles[T_SLIME] = _noisy(rng, (110, 195, 85), 0.15)
    tiles[T_OBSIDIAN] = _noisy(rng, (20, 15, 35), 0.3)
    tiles[T_LAVA] = _noisy(rng, (230, 90, 15), 0.2)

    # 1.8 Stones
    tiles[T_GRANITE] = _noisy(rng, (155, 108, 92), 0.18)
    tiles[T_POLISHED_GRANITE] = _polished_border(tiles[T_GRANITE], (120, 80, 70))
    tiles[T_DIORITE] = _noisy(rng, (205, 205, 208), 0.25)
    tiles[T_POLISHED_DIORITE] = _polished_border(tiles[T_DIORITE], (170, 170, 175))
    tiles[T_ANDESITE] = _noisy(rng, (134, 134, 138), 0.12)
    tiles[T_POLISHED_ANDESITE] = _polished_border(tiles[T_ANDESITE], (100, 100, 105))

    # 1.8 Ocean
    tiles[T_PRISMARINE] = _masonry(rng, (102, 160, 152), (50, 95, 90), 4, 8, 0.2)
    tiles[T_PRISMARINE_BRICKS] = _masonry(rng, (95, 165, 155), (40, 85, 80), 4, 4, 0.15)
    tiles[T_DARK_PRISMARINE] = _masonry(rng, (45, 75, 65), (25, 45, 40), 4, 8, 0.12)
    tiles[T_SEA_LANTERN] = _polished_border(_noisy(rng, (215, 240, 235), 0.08), (140, 190, 185))

    # 1.8 Red Sandstone
    tiles[T_RED_SAND] = _noisy(rng, (190, 100, 35), 0.12)
    tiles[T_RED_SANDSTONE_TOP] = _noisy(rng, (195, 105, 40), 0.08)
    tiles[T_RED_SANDSTONE_SIDE] = _noisy(rng, (185, 95, 35), 0.1)
    tiles[T_RED_SANDSTONE_BOTTOM] = _noisy(rng, (175, 85, 30), 0.08)
    tiles[T_CHISELED_RED_SANDSTONE] = _polished_border(tiles[T_RED_SANDSTONE_SIDE], (140, 65, 20))
    tiles[T_SMOOTH_RED_SANDSTONE] = _noisy(rng, (195, 105, 40), 0.04)

    # Soils & Sponges
    tiles[T_COARSE_DIRT] = _noisy(rng, (120, 85, 55), 0.22)
    tiles[T_PODZOL_TOP] = _noisy(rng, (90, 60, 30), 0.2)
    podzol_s = dirt.copy()
    podzol_s[:3, :] = tiles[T_PODZOL_TOP][:3, :]
    tiles[T_PODZOL_SIDE] = podzol_s
    tiles[T_SPONGE] = _noisy(rng, (195, 195, 70), 0.3)
    tiles[T_WET_SPONGE] = _noisy(rng, (160, 160, 50), 0.3)

    # Planks
    tiles[T_SPRUCE_PLANKS] = _masonry(rng, (105, 78, 48), (60, 42, 22), 4, 16, 0.12)
    tiles[T_BIRCH_PLANKS] = _masonry(rng, (215, 205, 155), (160, 150, 105), 4, 16, 0.12)
    tiles[T_JUNGLE_PLANKS] = _masonry(rng, (160, 115, 85), (110, 75, 50), 4, 16, 0.12)
    tiles[T_ACACIA_PLANKS] = _masonry(rng, (175, 90, 50), (125, 60, 30), 4, 16, 0.12)
    tiles[T_DARK_OAK_PLANKS] = _masonry(rng, (66, 43, 20), (35, 22, 10), 4, 16, 0.12)

    # Furnaces, Chests, Workstations
    furn_s = stone.copy()
    furn_t = stone.copy()
    furn_f = stone.copy()
    furn_f[4:12, 4:12] = (30, 30, 30) # unlit mouth
    furn_fl = stone.copy()
    furn_fl[4:12, 4:12] = (240, 120, 20) # lit fire mouth
    tiles[T_FURNACE_SIDE] = furn_s
    tiles[T_FURNACE_TOP] = furn_t
    tiles[T_FURNACE_FRONT] = furn_f
    tiles[T_FURNACE_FRONT_LIT] = furn_fl

    chest_s = _noisy(rng, (150, 105, 45), 0.1)
    chest_t = _noisy(rng, (150, 105, 45), 0.1)
    chest_f = chest_s.copy()
    chest_f[6:9, 7:9] = (220, 220, 220) # metal latch
    tiles[T_CHEST_SIDE] = chest_s
    tiles[T_CHEST_TOP] = chest_t
    tiles[T_CHEST_FRONT] = chest_f
    disp_f = stone.copy()
    disp_f[6:10, 6:10] = (20, 20, 20)
    tiles[T_DISPENSER_FRONT] = disp_f

    # Torches & Flowers
    torch_img = np.zeros((TILE, TILE, 3), dtype=float)
    torch_a = np.zeros((TILE, TILE), dtype=bool)
    torch_img[4:14, 7:9] = (140, 100, 50)
    torch_img[1:4, 6:10] = (255, 200, 50)
    torch_a[4:14, 7:9] = True
    torch_a[1:4, 6:10] = True
    tiles[T_TORCH] = torch_img
    alpha[T_TORCH] = torch_a

    rtorch_img = np.zeros((TILE, TILE, 3), dtype=float)
    rtorch_a = np.zeros((TILE, TILE), dtype=bool)
    rtorch_img[4:14, 7:9] = (140, 100, 50)
    rtorch_img[1:4, 6:10] = (250, 40, 30)
    rtorch_a[4:14, 7:9] = True
    rtorch_a[1:4, 6:10] = True
    tiles[T_REDSTONE_TORCH] = rtorch_img
    alpha[T_REDSTONE_TORCH] = rtorch_a

    grass_img = np.zeros((TILE, TILE, 3), dtype=float)
    grass_a = np.zeros((TILE, TILE), dtype=bool)
    for bx in range(2, 14, 2):
        y_start = int(rng.integers(2, 6))
        grass_img[y_start:16, bx:bx + 2] = _noisy(rng, (70, 145, 40), 0.2)[:16 - y_start, :2]
        grass_a[y_start:16, bx:bx + 2] = True
    tiles[T_TALL_GRASS] = grass_img
    alpha[T_TALL_GRASS] = grass_a
    tiles[T_FERN] = grass_img.copy()
    alpha[T_FERN] = grass_a.copy()

    poppy_img = np.zeros((TILE, TILE, 3), dtype=float)
    poppy_a = np.zeros((TILE, TILE), dtype=bool)
    poppy_img[7:16, 7:9] = (50, 120, 30)
    poppy_img[3:7, 5:11] = (220, 35, 30)
    poppy_img[4:6, 7:9] = (20, 20, 20)
    poppy_a[7:16, 7:9] = True
    poppy_a[3:7, 5:11] = True
    tiles[T_POPPY] = poppy_img
    alpha[T_POPPY] = poppy_a

    dand_img = np.zeros((TILE, TILE, 3), dtype=float)
    dand_a = np.zeros((TILE, TILE), dtype=bool)
    dand_img[7:16, 7:9] = (50, 120, 30)
    dand_img[3:7, 5:11] = (255, 225, 40)
    dand_a[7:16, 7:9] = True
    dand_a[3:7, 5:11] = True
    tiles[T_DANDELION] = dand_img
    alpha[T_DANDELION] = dand_a

    # TNT
    tnt_s = _noisy(rng, (180, 45, 35), 0.1)
    tnt_s[5:11, :] = (245, 245, 245) # white label
    tnt_s[6:10, 3:13] = (20, 20, 20) # TNT text
    tnt_t = _noisy(rng, (170, 40, 30), 0.1)
    tiles[T_TNT_SIDE] = tnt_s
    tiles[T_TNT_TOP] = tnt_t
    tiles[T_TNT_BOTTOM] = tnt_t

    # Mineral Blocks
    tiles[T_COAL_BLOCK] = _noisy(rng, (25, 25, 25), 0.2)
    tiles[T_IRON_BLOCK] = _polished_border(_noisy(rng, (225, 225, 225), 0.05), (170, 170, 170))
    tiles[T_GOLD_BLOCK] = _polished_border(_noisy(rng, (250, 215, 60), 0.05), (200, 160, 40))
    tiles[T_DIAMOND_BLOCK] = _polished_border(_noisy(rng, (110, 240, 235), 0.05), (70, 190, 185))
    tiles[T_EMERALD_BLOCK] = _polished_border(_noisy(rng, (60, 220, 95), 0.05), (35, 165, 65))
    tiles[T_REDSTONE_BLOCK] = _polished_border(_noisy(rng, (215, 30, 20), 0.1), (150, 20, 15))
    tiles[T_LAPIS_BLOCK] = _noisy(rng, (35, 65, 155), 0.15)
    tiles[T_STONE_BRICKS] = _masonry(rng, (130, 130, 130), (70, 70, 70), 4, 8, 0.08)
    tiles[T_NETHERRACK] = _noisy(rng, (115, 40, 40), 0.25)
    tiles[T_SOUL_SAND] = _noisy(rng, (85, 65, 50), 0.2)
    tiles[T_NETHER_BRICKS] = _masonry(rng, (50, 25, 30), (25, 10, 15), 4, 8, 0.1)
    tiles[T_END_STONE] = _noisy(rng, (225, 230, 175), 0.15)
    tiles[T_BOOKSHELF] = tiles[T_PLANKS].copy()
    tiles[T_BOOKSHELF][2:6, 2:14] = (160, 50, 40)
    tiles[T_BOOKSHELF][8:12, 2:14] = (45, 110, 150)
    tiles[T_WHITE_WOOL] = _noisy(rng, (235, 235, 235), 0.06)
    tiles[T_RED_WOOL] = _noisy(rng, (180, 40, 40), 0.06)
    tiles[T_BLUE_WOOL] = _noisy(rng, (50, 70, 175), 0.06)
    tiles[T_YELLOW_WOOL] = _noisy(rng, (230, 200, 45), 0.06)
    tiles[T_GREEN_WOOL] = _noisy(rng, (60, 130, 40), 0.06)
    tiles[T_BLACK_WOOL] = _noisy(rng, (30, 30, 30), 0.06)

    # Mob faces
    creeper = _noisy(rng, (75, 180, 60), 0.15)
    creeper[4:7, 3:6] = creeper[4:7, 10:13] = (10, 10, 10)
    creeper[7:10, 6:10] = (10, 10, 10)
    creeper[10:13, 4:7] = creeper[10:13, 9:12] = (10, 10, 10)
    tiles[T_CREEPER_FACE] = creeper
    skel = _noisy(rng, (210, 210, 210), 0.08)
    skel[5:8, 3:6] = skel[5:8, 10:13] = (20, 20, 20)
    skel[10:12, 5:11] = (20, 20, 20)
    tiles[T_SKELETON_FACE] = skel

    # Tools
    for (t_pick, head_col) in [(T_WOOD_PICKAXE, (150, 115, 65)), (T_STONE_PICKAXE, (130, 130, 130)), (T_IRON_PICKAXE, (220, 220, 220)), (T_DIAMOND_PICKAXE, (90, 235, 230))]:
        img, a = _draw_pickaxe((115, 80, 40), head_col)
        tiles[t_pick], alpha[t_pick] = img, a
    for (t_swd, blade_col) in [(T_WOOD_SWORD, (150, 115, 65)), (T_STONE_SWORD, (130, 130, 130)), (T_IRON_SWORD, (220, 220, 220)), (T_DIAMOND_SWORD, (90, 235, 230))]:
        img, a = _draw_sword((115, 80, 40), blade_col)
        tiles[t_swd], alpha[t_swd] = img, a

    # Fill any unassigned tiles with default texture
    for t in range(256):
        if t not in tiles:
            tiles[t] = _noisy(rng, (140, 140, 140), 0.1)

    # Assemble into full atlas
    atlas = np.zeros((TILE * tiles_per_row, TILE * tiles_per_row, 4), dtype=np.uint8)
    for idx, img in tiles.items():
        row, col = divmod(idx, tiles_per_row)
        if row >= tiles_per_row:
            continue
        ys = slice(row * TILE, (row + 1) * TILE)
        xs = slice(col * TILE, (col + 1) * TILE)
        atlas[ys, xs, :3] = np.clip(img, 0, 255).astype(np.uint8)
        if idx in alpha:
            atlas[ys, xs, 3] = (alpha[idx] * 255).astype(np.uint8)
        else:
            atlas[ys, xs, 3] = 255

    return atlas
