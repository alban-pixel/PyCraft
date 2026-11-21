"""Block types and their properties: numbers and names, which way a block with a front faces, what is
solid, see-through or a plant, and which tile of the textures each face of each block shows. The
tiles themselves are drawn by textures.py (or read from a texture pack, packs.py)."""
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
# Plants, numbered after the building blocks
(TALL_GRASS, FERN, DEAD_BUSH, POPPY, DANDELION, BLUE_ORCHID, CORNFLOWER, OXEYE_DAISY, ALLIUM,
 OAK_SAPLING) = range(LIGHT_GRAY_TERRACOTTA + 1, LIGHT_GRAY_TERRACOTTA + 11)
# The other full blocks of the classic block set, then the turned versions of the blocks with a front
(COARSE_DIRT, MYCELIUM, FARMLAND, PACKED_ICE, SPONGE, WET_SPONGE, EMERALD_ORE, LAPIS_ORE, REDSTONE_ORE,
 NETHER_QUARTZ_ORE, NETHERRACK, SOUL_SAND, NETHER_BRICKS, END_STONE, PRISMARINE, PRISMARINE_BRICKS, DARK_PRISMARINE,
 BROWN_MUSHROOM_BLOCK, RED_MUSHROOM_BLOCK, MUSHROOM_STEM, SLIME_BLOCK, CHISELED_STONE_BRICKS, CHISELED_QUARTZ_BLOCK,
 QUARTZ_PILLAR, CHISELED_RED_SANDSTONE, LAPIS_BLOCK, EMERALD_BLOCK, REDSTONE_BLOCK, DARK_OAK_LOG, DARK_OAK_PLANKS,
 DARK_OAK_LEAVES, MAGENTA_TERRACOTTA, LIGHT_BLUE_TERRACOTTA, LIME_TERRACOTTA, PINK_TERRACOTTA, GRAY_TERRACOTTA,
 CYAN_TERRACOTTA, PURPLE_TERRACOTTA, BLUE_TERRACOTTA, GREEN_TERRACOTTA, BLACK_TERRACOTTA, WHITE_STAINED_GLASS,
 ORANGE_STAINED_GLASS, MAGENTA_STAINED_GLASS, LIGHT_BLUE_STAINED_GLASS, YELLOW_STAINED_GLASS, LIME_STAINED_GLASS,
 PINK_STAINED_GLASS, GRAY_STAINED_GLASS, LIGHT_GRAY_STAINED_GLASS, CYAN_STAINED_GLASS, PURPLE_STAINED_GLASS,
 BLUE_STAINED_GLASS, BROWN_STAINED_GLASS, GREEN_STAINED_GLASS, RED_STAINED_GLASS, BLACK_STAINED_GLASS, CRAFTING_TABLE,
 FURNACE, DISPENSER, DROPPER, NOTE_BLOCK, JUKEBOX, TNT, PISTON, STICKY_PISTON, COMMAND_BLOCK, GLOWSTONE, SEA_LANTERN,
 REDSTONE_LAMP, JACK_O_LANTERN, MONSTER_SPAWNER, FURNACE_WEST, FURNACE_SOUTH, FURNACE_NORTH, DISPENSER_WEST,
 DISPENSER_SOUTH, DISPENSER_NORTH, DROPPER_WEST, DROPPER_SOUTH, DROPPER_NORTH, JACK_O_LANTERN_WEST,
 JACK_O_LANTERN_SOUTH, JACK_O_LANTERN_NORTH) = range(OAK_SAPLING + 1, OAK_SAPLING + 85)
# Redstone: blocks with a state and a shape of their own (see shapes.py, redstone.py)
(LEVER, STONE_BUTTON, STONE_PRESSURE_PLATE, REDSTONE_WIRE, REDSTONE_TORCH, REPEATER, REDSTONE_LAMP_OFF,
 PISTON_HEAD) = range(JACK_O_LANTERN_NORTH + 1, JACK_O_LANTERN_NORTH + 9)
# The furnace while it burns, with its three turned versions (see FACING)
FURNACE_ON, FURNACE_ON_WEST, FURNACE_ON_SOUTH, FURNACE_ON_NORTH = range(PISTON_HEAD + 1, PISTON_HEAD + 5)
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
               "Red terracotta", "Brown terracotta", "Light gray terracotta",
               "Tall grass", "Fern", "Dead bush", "Poppy", "Dandelion", "Blue orchid", "Cornflower", "Oxeye daisy",
               "Allium", "Oak sapling",
               "Coarse dirt", "Mycelium", "Farmland", "Packed ice", "Sponge", "Wet sponge", "Emerald ore",
               "Lapis lazuli ore", "Redstone ore", "Nether quartz ore", "Netherrack", "Soul sand", "Nether bricks",
               "End stone", "Prismarine", "Prismarine bricks", "Dark prismarine", "Brown mushroom block",
               "Red mushroom block", "Mushroom stem", "Slime block", "Chiseled stone bricks", "Chiseled quartz block",
               "Quartz pillar", "Chiseled red sandstone", "Lapis lazuli block", "Block of emerald",
               "Block of redstone", "Dark oak log", "Dark oak planks", "Dark oak leaves", "Magenta terracotta",
               "Light blue terracotta", "Lime terracotta", "Pink terracotta", "Gray terracotta", "Cyan terracotta",
               "Purple terracotta", "Blue terracotta", "Green terracotta", "Black terracotta", "White stained glass",
               "Orange stained glass", "Magenta stained glass", "Light blue stained glass", "Yellow stained glass",
               "Lime stained glass", "Pink stained glass", "Gray stained glass", "Light gray stained glass",
               "Cyan stained glass", "Purple stained glass", "Blue stained glass", "Brown stained glass",
               "Green stained glass", "Red stained glass", "Black stained glass", "Crafting table", "Furnace",
               "Dispenser", "Dropper", "Note block", "Jukebox", "TNT", "Piston", "Sticky piston", "Command block",
               "Glowstone", "Sea lantern", "Redstone lamp", "Jack o'lantern", "Monster spawner", "Furnace", "Furnace",
               "Furnace", "Dispenser", "Dispenser", "Dispenser", "Dropper", "Dropper", "Dropper", "Jack o'lantern",
               "Jack o'lantern", "Jack o'lantern",
               "Lever", "Stone button", "Pressure plate", "Redstone dust", "Redstone torch", "Repeater",
               "Redstone lamp", "Piston head", "Furnace", "Furnace", "Furnace", "Furnace"]
NUM_BLOCKS = len(BLOCK_NAMES)

# Directions a block with a state can face, in the order its state numbers them: 0 is up, so a
# block saved before states existed (state 0) faces up, as it was drawn
FACING_VECTORS = [(0, 1, 0), (0, -1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]
UP, DOWN, EAST, WEST, SOUTH, NORTH = range(6)
OPPOSITE = [DOWN, UP, WEST, EAST, NORTH, SOUTH]

# Blocks with a front, which faces the player who places them: the block in the inventory has its front
# toward +x, and three more numbers turn it toward -x, +z and -z
FACING = {block: (block, west, south, north) for block, west, south, north in [
    (FURNACE, FURNACE_WEST, FURNACE_SOUTH, FURNACE_NORTH),
    (DISPENSER, DISPENSER_WEST, DISPENSER_SOUTH, DISPENSER_NORTH),
    (DROPPER, DROPPER_WEST, DROPPER_SOUTH, DROPPER_NORTH),
    (JACK_O_LANTERN, JACK_O_LANTERN_WEST, JACK_O_LANTERN_SOUTH, JACK_O_LANTERN_NORTH),
    (FURNACE_ON, FURNACE_ON_WEST, FURNACE_ON_SOUTH, FURNACE_ON_NORTH)]}
TURNED = {b for versions in FACING.values() for b in versions[1:]}

# A furnace and its lit twin, version for version
LIT_FURNACE = dict(zip(FACING[FURNACE], FACING[FURNACE_ON]))
UNLIT_FURNACE = {lit: unlit for unlit, lit in LIT_FURNACE.items()}

# Blocks the player can pick in the inventory (E)
PLACEABLE = [b for b in range(1, NUM_BLOCKS)
             if b not in (BEDROCK, PISTON_HEAD, REDSTONE_LAMP, FURNACE_ON) and b not in TURNED]
DEFAULT_HOTBAR = [GRASS, DIRT, STONE, COBBLESTONE, PLANKS, LOG, LEAVES, GLASS, BRICK]


def _flags(*blocks):
    table = np.zeros(NUM_BLOCKS, dtype=bool)
    table[list(blocks)] = True
    return table


ALL_LEAVES = (LEAVES, SPRUCE_LEAVES, BIRCH_LEAVES, JUNGLE_LEAVES, ACACIA_LEAVES, DARK_OAK_LEAVES)
ALL_STAINED_GLASS = tuple(range(WHITE_STAINED_GLASS, BLACK_STAINED_GLASS + 1))
# Small plants, drawn as two crossed quads instead of a cube (see builder.py)
FLOWERS = (POPPY, DANDELION, BLUE_ORCHID, CORNFLOWER, OXEYE_DAISY, ALLIUM)
PLANTS = (TALL_GRASS, FERN, DEAD_BUSH, *FLOWERS, OAK_SAPLING)

# Properties, as lookup tables indexed by block id (they also work on whole NumPy arrays of blocks)
# Hides the faces of the blocks next to it
# Small redstone parts: drawn from boxes (shapes.py), walked through, seen through
THIN = (LEVER, STONE_BUTTON, STONE_PRESSURE_PLATE, REDSTONE_WIRE, REDSTONE_TORCH, REPEATER)
OPAQUE = ~_flags(AIR, GLASS, WATER, MONSTER_SPAWNER, *ALL_LEAVES, *ALL_STAINED_GLASS, *PLANTS, *THIN, PISTON_HEAD)
SOLID = ~_flags(AIR, WATER, *PLANTS, *THIN)  # the player collides with it
CUTOUT = _flags(GLASS, MONSTER_SPAWNER, *ALL_LEAVES, *ALL_STAINED_GLASS, *PLANTS)  # see-through where the texture is
PLANT = _flags(*PLANTS)  # drawn as two crossed quads
SELF_CULL = _flags(GLASS, WATER, *ALL_LEAVES, *ALL_STAINED_GLASS)  # no faces between two blocks of this same type
TARGETABLE = ~_flags(AIR, WATER)  # can be aimed at and broken
UNBREAKABLE = _flags(BEDROCK)
# Lamps: drawn at full brightness, day and night (they light nothing around them)
GLOWING = _flags(GLOWSTONE, SEA_LANTERN, REDSTONE_LAMP, *FACING[JACK_O_LANTERN])
# Drawn from boxes, turned by their state (shapes.py): the redstone parts, and the pistons (a cube
# facing its way, or a short base once its head is out)
SHAPED = _flags(*THIN, PISTON_HEAD, PISTON, STICKY_PISTON)
FLAT = _flags(*THIN)  # left out of the distant terrain's ground, like plants
# The ground each plant grows on: GROWS_ON[plant, block under it]
GROWS_ON = np.zeros((NUM_BLOCKS, NUM_BLOCKS), dtype=bool)
GROWS_ON[np.ix_(PLANTS, (GRASS, DIRT, PODZOL))] = True
GROWS_ON[DEAD_BUSH] = _flags(SAND, RED_SAND)

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
(T_TALL_GRASS, T_FERN, T_DEAD_BUSH, T_POPPY, T_DANDELION, T_BLUE_ORCHID, T_CORNFLOWER, T_OXEYE_DAISY, T_ALLIUM,
 T_OAK_SAPLING) = range(T_LIGHT_GRAY_TERRACOTTA + 1, T_LIGHT_GRAY_TERRACOTTA + 11)
(T_COARSE_DIRT, T_MYCELIUM_TOP, T_MYCELIUM_SIDE, T_FARMLAND, T_PACKED_ICE, T_SPONGE, T_WET_SPONGE, T_EMERALD_ORE,
 T_LAPIS_ORE, T_REDSTONE_ORE, T_NETHER_QUARTZ_ORE, T_NETHERRACK, T_SOUL_SAND, T_NETHER_BRICKS, T_END_STONE,
 T_PRISMARINE, T_PRISMARINE_BRICKS, T_DARK_PRISMARINE, T_BROWN_MUSHROOM, T_RED_MUSHROOM, T_MUSHROOM_STEM, T_SLIME,
 T_CHISELED_STONE_BRICKS, T_CHISELED_QUARTZ, T_QUARTZ_PILLAR_SIDE, T_QUARTZ_PILLAR_TOP, T_CHISELED_RED_SANDSTONE,
 T_LAPIS_BLOCK, T_EMERALD_BLOCK, T_REDSTONE_BLOCK, T_DARK_OAK_LOG_SIDE, T_DARK_OAK_LOG_TOP, T_DARK_OAK_PLANKS,
 T_DARK_OAK_LEAVES, T_MAGENTA_TERRACOTTA, T_LIGHT_BLUE_TERRACOTTA, T_LIME_TERRACOTTA, T_PINK_TERRACOTTA,
 T_GRAY_TERRACOTTA, T_CYAN_TERRACOTTA, T_PURPLE_TERRACOTTA, T_BLUE_TERRACOTTA, T_GREEN_TERRACOTTA, T_BLACK_TERRACOTTA,
 T_WHITE_STAINED_GLASS, T_ORANGE_STAINED_GLASS, T_MAGENTA_STAINED_GLASS, T_LIGHT_BLUE_STAINED_GLASS,
 T_YELLOW_STAINED_GLASS, T_LIME_STAINED_GLASS, T_PINK_STAINED_GLASS, T_GRAY_STAINED_GLASS, T_LIGHT_GRAY_STAINED_GLASS,
 T_CYAN_STAINED_GLASS, T_PURPLE_STAINED_GLASS, T_BLUE_STAINED_GLASS, T_BROWN_STAINED_GLASS, T_GREEN_STAINED_GLASS,
 T_RED_STAINED_GLASS, T_BLACK_STAINED_GLASS, T_CRAFTING_TABLE_TOP, T_CRAFTING_TABLE_SIDE, T_CRAFTING_TABLE_FRONT,
 T_FURNACE_SIDE, T_FURNACE_TOP, T_FURNACE_FRONT, T_DISPENSER_FRONT, T_DROPPER_FRONT, T_NOTE_BLOCK, T_JUKEBOX_SIDE,
 T_JUKEBOX_TOP, T_TNT_SIDE, T_TNT_TOP, T_PISTON_SIDE, T_PISTON_TOP, T_PISTON_BOTTOM, T_STICKY_PISTON_TOP,
 T_COMMAND_BLOCK, T_GLOWSTONE, T_SEA_LANTERN, T_REDSTONE_LAMP, T_JACK_O_LANTERN,
 T_SPAWNER) = range(T_OAK_SAPLING + 1, T_OAK_SAPLING + 84)
(T_LEVER, T_REDSTONE_DUST, T_REDSTONE_TORCH_ON, T_REDSTONE_TORCH_OFF, T_REPEATER_OFF, T_REPEATER_ON,
 T_REDSTONE_LAMP_OFF, T_PISTON_INNER, T_FURNACE_FRONT_ON) = range(T_SPAWNER + 1, T_SPAWNER + 10)


def _faces(side, top=None, bottom=None):
    # Face order used everywhere: +x, -x, +y (top), -y (bottom), +z, -z
    top = side if top is None else top
    bottom = top if bottom is None else bottom
    return [side, side, top, bottom, side, side]


def _fronts(front, side, top, bottom=None):
    """The faces of a block with a front, turned toward +x, -x, +z and -z (see FACING)."""
    versions = []
    for toward in (0, 1, 4, 5):
        faces = _faces(side, top, bottom)
        faces[toward] = front
        versions.append(faces)
    return versions


def turned(block, look):
    """The version of a block that faces someone looking along 'look' (x, y, z): its front toward them."""
    if block not in FACING:
        return block
    x, _, z = look
    if abs(x) > abs(z):
        return FACING[block][1 if x > 0 else 0]
    return FACING[block][3 if z > 0 else 2]


FURNACE_FACES = _fronts(T_FURNACE_FRONT, T_FURNACE_SIDE, T_FURNACE_TOP)
DISPENSER_FACES = _fronts(T_DISPENSER_FRONT, T_FURNACE_SIDE, T_FURNACE_TOP)
DROPPER_FACES = _fronts(T_DROPPER_FRONT, T_FURNACE_SIDE, T_FURNACE_TOP)
JACK_O_LANTERN_FACES = _fronts(T_JACK_O_LANTERN, T_PUMPKIN_SIDE, T_PUMPKIN_TOP)
FURNACE_ON_FACES = _fronts(T_FURNACE_FRONT_ON, T_FURNACE_SIDE, T_FURNACE_TOP)

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
    # Plants: one tile for both crossed quads
    _faces(T_TALL_GRASS),
    _faces(T_FERN),
    _faces(T_DEAD_BUSH),
    _faces(T_POPPY),
    _faces(T_DANDELION),
    _faces(T_BLUE_ORCHID),
    _faces(T_CORNFLOWER),
    _faces(T_OXEYE_DAISY),
    _faces(T_ALLIUM),
    _faces(T_OAK_SAPLING),
    _faces(T_COARSE_DIRT),
    _faces(T_MYCELIUM_SIDE, T_MYCELIUM_TOP, T_DIRT),
    _faces(T_DIRT, T_FARMLAND, T_DIRT),
    _faces(T_PACKED_ICE),
    _faces(T_SPONGE),
    _faces(T_WET_SPONGE),
    _faces(T_EMERALD_ORE),
    _faces(T_LAPIS_ORE),
    _faces(T_REDSTONE_ORE),
    _faces(T_NETHER_QUARTZ_ORE),
    _faces(T_NETHERRACK),
    _faces(T_SOUL_SAND),
    _faces(T_NETHER_BRICKS),
    _faces(T_END_STONE),
    _faces(T_PRISMARINE),
    _faces(T_PRISMARINE_BRICKS),
    _faces(T_DARK_PRISMARINE),
    _faces(T_BROWN_MUSHROOM),
    _faces(T_RED_MUSHROOM),
    _faces(T_MUSHROOM_STEM),
    _faces(T_SLIME),
    _faces(T_CHISELED_STONE_BRICKS),
    _faces(T_CHISELED_QUARTZ, T_QUARTZ),
    _faces(T_QUARTZ_PILLAR_SIDE, T_QUARTZ_PILLAR_TOP),
    _faces(T_CHISELED_RED_SANDSTONE, T_RED_SANDSTONE_TOP),
    _faces(T_LAPIS_BLOCK),
    _faces(T_EMERALD_BLOCK),
    _faces(T_REDSTONE_BLOCK),
    _faces(T_DARK_OAK_LOG_SIDE, T_DARK_OAK_LOG_TOP),
    _faces(T_DARK_OAK_PLANKS),
    _faces(T_DARK_OAK_LEAVES),
    _faces(T_MAGENTA_TERRACOTTA),
    _faces(T_LIGHT_BLUE_TERRACOTTA),
    _faces(T_LIME_TERRACOTTA),
    _faces(T_PINK_TERRACOTTA),
    _faces(T_GRAY_TERRACOTTA),
    _faces(T_CYAN_TERRACOTTA),
    _faces(T_PURPLE_TERRACOTTA),
    _faces(T_BLUE_TERRACOTTA),
    _faces(T_GREEN_TERRACOTTA),
    _faces(T_BLACK_TERRACOTTA),
    _faces(T_WHITE_STAINED_GLASS),
    _faces(T_ORANGE_STAINED_GLASS),
    _faces(T_MAGENTA_STAINED_GLASS),
    _faces(T_LIGHT_BLUE_STAINED_GLASS),
    _faces(T_YELLOW_STAINED_GLASS),
    _faces(T_LIME_STAINED_GLASS),
    _faces(T_PINK_STAINED_GLASS),
    _faces(T_GRAY_STAINED_GLASS),
    _faces(T_LIGHT_GRAY_STAINED_GLASS),
    _faces(T_CYAN_STAINED_GLASS),
    _faces(T_PURPLE_STAINED_GLASS),
    _faces(T_BLUE_STAINED_GLASS),
    _faces(T_BROWN_STAINED_GLASS),
    _faces(T_GREEN_STAINED_GLASS),
    _faces(T_RED_STAINED_GLASS),
    _faces(T_BLACK_STAINED_GLASS),
    [T_CRAFTING_TABLE_FRONT, T_CRAFTING_TABLE_FRONT, T_CRAFTING_TABLE_TOP, T_PLANKS, T_CRAFTING_TABLE_SIDE,
     T_CRAFTING_TABLE_SIDE],
    FURNACE_FACES[0],
    DISPENSER_FACES[0],
    DROPPER_FACES[0],
    _faces(T_NOTE_BLOCK),
    _faces(T_JUKEBOX_SIDE, T_JUKEBOX_TOP, T_JUKEBOX_SIDE),
    _faces(T_TNT_SIDE, T_TNT_TOP),
    _faces(T_PISTON_SIDE, T_PISTON_TOP, T_PISTON_BOTTOM),
    _faces(T_PISTON_SIDE, T_STICKY_PISTON_TOP, T_PISTON_BOTTOM),
    _faces(T_COMMAND_BLOCK),
    _faces(T_GLOWSTONE),
    _faces(T_SEA_LANTERN),
    _faces(T_REDSTONE_LAMP),
    JACK_O_LANTERN_FACES[0],
    _faces(T_SPAWNER),
    FURNACE_FACES[1],
    FURNACE_FACES[2],
    FURNACE_FACES[3],
    DISPENSER_FACES[1],
    DISPENSER_FACES[2],
    DISPENSER_FACES[3],
    DROPPER_FACES[1],
    DROPPER_FACES[2],
    DROPPER_FACES[3],
    JACK_O_LANTERN_FACES[1],
    JACK_O_LANTERN_FACES[2],
    JACK_O_LANTERN_FACES[3],
    # The redstone blocks with a shape: their tiles come from shapes.py; these are their icons
    # (face 0) and their color from afar (face 2)
    _faces(T_LEVER),
    _faces(T_STONE),
    _faces(T_STONE),
    _faces(T_REDSTONE_DUST),
    _faces(T_REDSTONE_TORCH_ON),
    _faces(T_REPEATER_OFF),
    _faces(T_REDSTONE_LAMP_OFF),
    _faces(T_PISTON_SIDE, T_PISTON_TOP),
    FURNACE_ON_FACES[0],
    FURNACE_ON_FACES[1],
    FURNACE_ON_FACES[2],
    FURNACE_ON_FACES[3],
], dtype=np.int32)
