"""Items (what the inventory holds besides blocks), tools, and the rules of mining: how long a block
takes to break, whether a tool can harvest it, and what it drops. Item numbers start at 256, above
every block number, so one number names either kind of thing in an inventory."""
import math
from dataclasses import dataclass

import blocks as B

FIRST_ITEM = 256
(STICK, COAL, CHARCOAL, IRON_INGOT, GOLD_INGOT, DIAMOND, EMERALD, LAPIS, QUARTZ, FLINT, APPLE, CLAY_BALL,
 BRICK) = range(FIRST_ITEM, FIRST_ITEM + 13)
(WOODEN_PICKAXE, WOODEN_AXE, WOODEN_SHOVEL, STONE_PICKAXE, STONE_AXE, STONE_SHOVEL, IRON_PICKAXE, IRON_AXE,
 IRON_SHOVEL, GOLDEN_PICKAXE, GOLDEN_AXE, GOLDEN_SHOVEL, DIAMOND_PICKAXE, DIAMOND_AXE,
 DIAMOND_SHOVEL) = range(BRICK + 1, BRICK + 16)

ITEM_NAMES = {
    STICK: "Stick", COAL: "Coal", CHARCOAL: "Charcoal", IRON_INGOT: "Iron ingot", GOLD_INGOT: "Gold ingot",
    DIAMOND: "Diamond", EMERALD: "Emerald", LAPIS: "Lapis lazuli", QUARTZ: "Nether quartz", FLINT: "Flint",
    APPLE: "Apple", CLAY_BALL: "Clay ball", BRICK: "Brick",
}


@dataclass(frozen=True)
class Tool:
    kind: str  # "pickaxe", "axe" or "shovel"
    speed: float
    durability: int
    level: int


TOOLS = {}
_MATERIALS = [("Wooden", WOODEN_PICKAXE, 2, 59, 0), ("Stone", STONE_PICKAXE, 4, 131, 1),
              ("Iron", IRON_PICKAXE, 6, 250, 2), ("Golden", GOLDEN_PICKAXE, 12, 32, 0),
              ("Diamond", DIAMOND_PICKAXE, 8, 1561, 3)]
for _material, _first, _speed, _durability, _level in _MATERIALS:
    for _i, _kind in enumerate(("pickaxe", "axe", "shovel")):
        TOOLS[_first + _i] = Tool(_kind, _speed, _durability, _level)
        ITEM_NAMES[_first + _i] = f"{_material} {_kind}"
NUM_ITEMS = len(ITEM_NAMES)


def is_block(item):
    return 0 < item < FIRST_ITEM


def name(item):
    if item == 0:
        return ""  # the empty slot
    return B.BLOCK_NAMES[item] if is_block(item) else ITEM_NAMES[item]


def max_stack(item):
    return 1 if item in TOOLS else 64


# ---------------------------------------------------------------------------------------- hardness
_ALL_LOGS = (B.LOG, B.SPRUCE_LOG, B.BIRCH_LOG, B.JUNGLE_LOG, B.ACACIA_LOG, B.DARK_OAK_LOG)
_ALL_PLANKS = (B.PLANKS, B.SPRUCE_PLANKS, B.BIRCH_PLANKS, B.JUNGLE_PLANKS, B.ACACIA_PLANKS, B.DARK_OAK_PLANKS)
_WOOLS = tuple(range(B.WHITE_WOOL, B.BLACK_WOOL + 1))
_TERRACOTTAS = (B.TERRACOTTA, B.ORANGE_TERRACOTTA, B.WHITE_TERRACOTTA, B.YELLOW_TERRACOTTA, B.RED_TERRACOTTA,
                B.BROWN_TERRACOTTA, B.LIGHT_GRAY_TERRACOTTA, B.MAGENTA_TERRACOTTA, B.LIGHT_BLUE_TERRACOTTA,
                B.LIME_TERRACOTTA, B.PINK_TERRACOTTA, B.GRAY_TERRACOTTA, B.CYAN_TERRACOTTA,
                B.PURPLE_TERRACOTTA, B.BLUE_TERRACOTTA, B.GREEN_TERRACOTTA, B.BLACK_TERRACOTTA)


_HARDNESS_GROUPS = [
    (0.0, [B.TALL_GRASS, B.FERN, B.DEAD_BUSH, B.POPPY, B.DANDELION, B.BLUE_ORCHID, B.CORNFLOWER, B.OXEYE_DAISY,
           B.ALLIUM, B.OAK_SAPLING, B.REDSTONE_WIRE, B.REDSTONE_TORCH, B.REPEATER, B.TNT, B.SLIME_BLOCK]),
    (0.1, [B.MOSS]),
    (0.2, [*B.ALL_LEAVES, B.SNOW, B.BROWN_MUSHROOM_BLOCK, B.RED_MUSHROOM_BLOCK, B.MUSHROOM_STEM]),
    (0.3, [B.GLASS, *B.ALL_STAINED_GLASS, B.GLOWSTONE, B.SEA_LANTERN, B.REDSTONE_LAMP, B.REDSTONE_LAMP_OFF]),
    (0.4, [B.CACTUS, B.NETHERRACK]),
    (0.5, [B.DIRT, B.COARSE_DIRT, B.SAND, B.RED_SAND, B.ICE, B.PACKED_ICE, B.FARMLAND, B.MUD, B.HAY_BALE,
           B.LEVER, B.STONE_BUTTON, B.STONE_PRESSURE_PLATE, B.PISTON, B.STICKY_PISTON, B.PISTON_HEAD]),
    (0.6, [B.GRASS, B.MYCELIUM, B.PODZOL, B.GRAVEL, B.CLAY, B.SPONGE, B.WET_SPONGE, B.SOUL_SAND]),
    (0.8, [B.SANDSTONE, B.CUT_SANDSTONE, B.CHISELED_SANDSTONE, B.RED_SANDSTONE, B.CUT_RED_SANDSTONE,
           B.CHISELED_RED_SANDSTONE, B.QUARTZ_BLOCK, B.CHISELED_QUARTZ_BLOCK, B.QUARTZ_PILLAR, B.NOTE_BLOCK,
           *_WOOLS]),
    (1.0, [B.PUMPKIN, B.MELON, *B.FACING[B.JACK_O_LANTERN]]),
    (1.25, list(_TERRACOTTAS)),
    (1.5, [B.STONE, B.STONE_BRICKS, B.MOSSY_STONE_BRICKS, B.CRACKED_STONE_BRICKS, B.CHISELED_STONE_BRICKS,
           B.SMOOTH_STONE, B.GRANITE, B.POLISHED_GRANITE, B.DIORITE, B.POLISHED_DIORITE, B.ANDESITE,
           B.POLISHED_ANDESITE, B.PRISMARINE, B.PRISMARINE_BRICKS, B.DARK_PRISMARINE, B.BOOKSHELF]),
    (2.0, [B.COBBLESTONE, B.MOSSY_COBBLESTONE, B.BRICK, B.NETHER_BRICKS, B.MUD_BRICKS, B.JUKEBOX,
           *_ALL_LOGS, *_ALL_PLANKS]),
    (2.5, [B.CRAFTING_TABLE]),
    (3.0, [B.COAL_ORE, B.IRON_ORE, B.GOLD_ORE, B.DIAMOND_ORE, B.EMERALD_ORE, B.LAPIS_ORE, B.REDSTONE_ORE,
           B.NETHER_QUARTZ_ORE, B.DEEPSLATE, B.DEEPSLATE_BRICKS, B.POLISHED_DEEPSLATE, B.END_STONE]),
    (3.5, [*B.FACING[B.FURNACE], *B.FACING[B.FURNACE_ON], *B.FACING[B.DISPENSER], *B.FACING[B.DROPPER]]),
    (5.0, [B.COAL_BLOCK, B.IRON_BLOCK, B.GOLD_BLOCK, B.DIAMOND_BLOCK, B.EMERALD_BLOCK, B.LAPIS_BLOCK,
           B.REDSTONE_BLOCK, B.MONSTER_SPAWNER]),
    (50.0, [B.OBSIDIAN]),
    (-1.0, [B.BEDROCK, B.COMMAND_BLOCK, B.WATER, B.AIR]),
]
_HARDNESS = {}
for _h, _group in _HARDNESS_GROUPS:
    for _b in _group:
        _HARDNESS[_b] = _h


def hardness(block):
    return _HARDNESS.get(block, 0.5)


# -------------------------------------------------------------------------------------------- tools
_AXE_BLOCKS = {*_ALL_LOGS, *_ALL_PLANKS, B.CRAFTING_TABLE, B.BOOKSHELF, B.PUMPKIN, B.MELON,
               *B.FACING[B.JACK_O_LANTERN], B.JUKEBOX, B.NOTE_BLOCK}
_SHOVEL_BLOCKS = {B.DIRT, B.GRASS, B.SAND, B.RED_SAND, B.GRAVEL, B.CLAY, B.SNOW, B.MYCELIUM, B.PODZOL,
                  B.FARMLAND, B.MUD, B.SOUL_SAND, B.COARSE_DIRT}
_PICKAXE_BLOCKS = {b for b, h in _HARDNESS.items()
                   if h in (0.8, 1.25, 1.5, 2.0, 3.0, 3.5, 5.0, 50.0) and b not in _AXE_BLOCKS
                   and b not in _WOOLS} | {B.NETHERRACK, B.ICE, B.PACKED_ICE}
_PICKAXE_OPTIONAL = {B.ICE, B.PACKED_ICE}
_LEVELS = {1: (B.IRON_ORE, B.LAPIS_ORE, B.IRON_BLOCK, B.LAPIS_BLOCK),
           2: (B.GOLD_ORE, B.DIAMOND_ORE, B.EMERALD_ORE, B.REDSTONE_ORE, B.GOLD_BLOCK, B.DIAMOND_BLOCK,
               B.EMERALD_BLOCK),
           3: (B.OBSIDIAN,)}
_LEVEL = {b: level for level, group in _LEVELS.items() for b in group}


def best_tool(block):
    if block in _PICKAXE_BLOCKS:
        return "pickaxe"
    if block in _AXE_BLOCKS:
        return "axe"
    if block in _SHOVEL_BLOCKS:
        return "shovel"
    return None


def needed_level(block):
    """The pickaxe level a block needs to be harvested; None when no pickaxe is needed."""
    if block in _PICKAXE_BLOCKS and block not in _PICKAXE_OPTIONAL:
        return _LEVEL.get(block, 0)
    return None


def can_harvest(block, tool_item):
    if hardness(block) < 0:
        return False
    level = needed_level(block)
    if level is None:
        return True
    tool = TOOLS.get(tool_item)
    return tool is not None and tool.kind == "pickaxe" and tool.level >= level


def break_seconds(block, tool_item):
    """How long holding the button takes to break the block: 0.0 at once, math.inf if it never breaks."""
    h = hardness(block)
    if h < 0:
        return math.inf
    if h == 0:
        return 0.0
    tool = TOOLS.get(tool_item)
    speed = tool.speed if tool is not None and tool.kind == best_tool(block) else 1
    damage_per_tick = speed / h / (30 if can_harvest(block, tool_item) else 100)
    return 1 / (damage_per_tick * 20)


# ------------------------------------------------------------------------------------------- drops
_BASE = {}
for _base, _versions in B.FACING.items():
    for _v in _versions:
        _BASE[_v] = _base
for _v in B.FACING[B.FURNACE_ON]:
    _BASE[_v] = B.FURNACE
_BASE[B.REDSTONE_LAMP] = B.REDSTONE_LAMP_OFF


def base_item(block):
    """The inventory item a block stands for (a turned or lit block gives its plain version)."""
    return _BASE.get(block, block)


_SIMPLE_DROPS = {B.STONE: B.COBBLESTONE, B.GRASS: B.DIRT, B.MYCELIUM: B.DIRT, B.PODZOL: B.DIRT,
                 B.FARMLAND: B.DIRT, B.COAL_ORE: COAL, B.DIAMOND_ORE: DIAMOND, B.EMERALD_ORE: EMERALD,
                 B.NETHER_QUARTZ_ORE: QUARTZ}
_NO_DROPS = {B.GLASS, *B.ALL_STAINED_GLASS, B.ICE, B.PACKED_ICE, B.TALL_GRASS, B.FERN, B.DEAD_BUSH,
             B.MONSTER_SPAWNER, B.PISTON_HEAD}


def drops(block, tool_item, rng):
    """What breaking the block with this tool leaves, as (item, count) pairs."""
    if not can_harvest(block, tool_item) or block in _NO_DROPS:
        return []
    if block in _SIMPLE_DROPS:
        return [(_SIMPLE_DROPS[block], 1)]
    if block == B.LAPIS_ORE:
        return [(LAPIS, rng.randint(4, 8))]
    if block == B.REDSTONE_ORE:
        return [(B.REDSTONE_WIRE, rng.randint(4, 5))]
    if block == B.GRAVEL:
        return [(FLINT if rng.random() < 0.1 else B.GRAVEL, 1)]
    if block == B.CLAY:
        return [(CLAY_BALL, 4)]
    if block in B.ALL_LEAVES:
        out = []
        if rng.random() < 0.05:
            out.append((B.OAK_SAPLING, 1))
        if block in (B.LEAVES, B.DARK_OAK_LEAVES) and rng.random() < 0.005:
            out.append((APPLE, 1))
        return out
    return [(base_item(block), 1)]
