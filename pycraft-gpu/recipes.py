"""Crafting recipes, smelting and fuel. Grids are lists of rows of item ids (0 is empty)."""
from dataclasses import dataclass

import blocks as B
import items as I

COOK_TICKS = 200

LOG_PLANKS = ((B.LOG, B.PLANKS), (B.SPRUCE_LOG, B.SPRUCE_PLANKS), (B.BIRCH_LOG, B.BIRCH_PLANKS),
              (B.JUNGLE_LOG, B.JUNGLE_PLANKS), (B.ACACIA_LOG, B.ACACIA_PLANKS),
              (B.DARK_OAK_LOG, B.DARK_OAK_PLANKS))
LOGS = frozenset(log for log, _ in LOG_PLANKS)
PLANKS_ANY = frozenset(planks for _, planks in LOG_PLANKS)


@dataclass(frozen=True)
class Shaped:
    pattern: tuple
    key: dict
    result: tuple


@dataclass(frozen=True)
class Shapeless:
    ingredients: tuple
    result: tuple


def _one(item):
    return frozenset((item,))


def _shaped(pattern, key, result):
    return Shaped(tuple(pattern.split("/")), {k: v if isinstance(v, frozenset) else _one(v) for k, v in key.items()},
                  result)


def _build():
    out = []
    P, S = PLANKS_ANY, _one(I.STICK)
    for log, planks in LOG_PLANKS:
        out.append(Shapeless((_one(log),), (planks, 4)))
    out.append(_shaped("P/P", {"P": P}, (I.STICK, 4)))
    out.append(_shaped("PP/PP", {"P": P}, (B.CRAFTING_TABLE, 1)))
    out.append(_shaped("CCC/C.C/CCC", {"C": B.COBBLESTONE}, (B.FURNACE, 1)))
    tools = ((P, I.WOODEN_PICKAXE), (B.COBBLESTONE, I.STONE_PICKAXE), (I.IRON_INGOT, I.IRON_PICKAXE),
             (I.GOLD_INGOT, I.GOLDEN_PICKAXE), (I.DIAMOND, I.DIAMOND_PICKAXE))
    for material, pick in tools:
        key = {"X": material, "S": S}
        out.append(_shaped("XXX/.S./.S.", key, (pick, 1)))
        out.append(_shaped("XX/XS/.S", key, (pick + 1, 1)))
        out.append(_shaped("X/S/S", key, (pick + 2, 1)))
    out.append(_shaped("R/S", {"R": B.REDSTONE_WIRE, "S": S}, (B.REDSTONE_TORCH, 1)))
    out.append(_shaped("S/C", {"S": S, "C": B.COBBLESTONE}, (B.LEVER, 1)))
    out.append(Shapeless((_one(B.STONE),), (B.STONE_BUTTON, 1)))
    out.append(_shaped("TT", {"T": B.STONE}, (B.STONE_PRESSURE_PLATE, 1)))
    out.append(_shaped("XRX/TTT", {"X": B.REDSTONE_TORCH, "R": B.REDSTONE_WIRE, "T": B.STONE}, (B.REPEATER, 1)))
    out.append(_shaped(".R./RGR/.R.", {"R": B.REDSTONE_WIRE, "G": B.GLOWSTONE}, (B.REDSTONE_LAMP_OFF, 1)))
    out.append(_shaped("PPP/CIC/CRC", {"P": P, "C": B.COBBLESTONE, "I": I.IRON_INGOT, "R": B.REDSTONE_WIRE},
                       (B.PISTON, 1)))
    out.append(_shaped("L/K", {"L": B.SLIME_BLOCK, "K": B.PISTON}, (B.STICKY_PISTON, 1)))
    for part, block in ((I.COAL, B.COAL_BLOCK), (I.IRON_INGOT, B.IRON_BLOCK), (I.GOLD_INGOT, B.GOLD_BLOCK),
                        (I.DIAMOND, B.DIAMOND_BLOCK), (I.EMERALD, B.EMERALD_BLOCK), (I.LAPIS, B.LAPIS_BLOCK),
                        (B.REDSTONE_WIRE, B.REDSTONE_BLOCK)):
        out.append(_shaped("XXX/XXX/XXX", {"X": part}, (block, 1)))
        out.append(Shapeless((_one(block),), (part, 9)))
    for src, dst, n in ((B.STONE, B.STONE_BRICKS, 4), (B.SANDSTONE, B.CUT_SANDSTONE, 4),
                        (B.RED_SANDSTONE, B.CUT_RED_SANDSTONE, 4), (B.GRANITE, B.POLISHED_GRANITE, 4),
                        (B.DIORITE, B.POLISHED_DIORITE, 4), (B.ANDESITE, B.POLISHED_ANDESITE, 4),
                        (B.DEEPSLATE, B.POLISHED_DEEPSLATE, 4), (B.POLISHED_DEEPSLATE, B.DEEPSLATE_BRICKS, 4),
                        (B.SAND, B.SANDSTONE, 1), (B.RED_SAND, B.RED_SANDSTONE, 1), (I.BRICK, B.BRICK, 1),
                        (I.CLAY_BALL, B.CLAY, 1), (I.QUARTZ, B.QUARTZ_BLOCK, 1)):
        out.append(_shaped("XX/XX", {"X": src}, (dst, n)))
    out.append(_shaped("PPP/PRP/PPP", {"P": P, "R": B.REDSTONE_WIRE}, (B.NOTE_BLOCK, 1)))
    out.append(_shaped("PPP/PDP/PPP", {"P": P, "D": I.DIAMOND}, (B.JUKEBOX, 1)))
    out.append(_shaped("CCC/C.C/CRC", {"C": B.COBBLESTONE, "R": B.REDSTONE_WIRE}, (B.DROPPER, 1)))
    return out


RECIPES = _build()


def _fits(recipe, grid, h, w, ox, oy, mirror):
    ph, pw = len(recipe.pattern), len(recipe.pattern[0])
    for y in range(h):
        for x in range(w):
            inside = oy <= y < oy + ph and ox <= x < ox + pw
            ch = "."
            if inside:
                px = x - ox
                ch = recipe.pattern[y - oy][pw - 1 - px if mirror else px]
            cell = grid[y][x]
            if ch in ". ":
                if cell:
                    return False
            elif cell not in recipe.key[ch]:
                return False
    return True


def _match_shaped(recipe, grid):
    h, w = len(grid), len(grid[0])
    ph, pw = len(recipe.pattern), len(recipe.pattern[0])
    for oy in range(h - ph + 1):
        for ox in range(w - pw + 1):
            if _fits(recipe, grid, h, w, ox, oy, False) or _fits(recipe, grid, h, w, ox, oy, True):
                return True
    return False


def _match_shapeless(recipe, grid):
    cells = [c for row in grid for c in row if c]
    if len(cells) != len(recipe.ingredients):
        return False
    used = [False] * len(cells)

    def assign(i):
        if i == len(recipe.ingredients):
            return True
        for j, c in enumerate(cells):
            if not used[j] and c in recipe.ingredients[i]:
                used[j] = True
                if assign(i + 1):
                    return True
                used[j] = False
        return False

    return assign(0)


def match(grid):
    if not grid or not any(c for row in grid for c in row):
        return None
    for recipe in RECIPES:
        if isinstance(recipe, Shaped):
            if _match_shaped(recipe, grid):
                return recipe.result
        elif _match_shapeless(recipe, grid):
            return recipe.result
    return None


SMELTING = {B.IRON_ORE: I.IRON_INGOT, B.GOLD_ORE: I.GOLD_INGOT, B.SAND: B.GLASS, B.RED_SAND: B.GLASS,
            B.COBBLESTONE: B.STONE, B.STONE: B.SMOOTH_STONE, I.CLAY_BALL: I.BRICK, B.CLAY: B.TERRACOTTA,
            B.WET_SPONGE: B.SPONGE, B.COAL_ORE: I.COAL, B.DIAMOND_ORE: I.DIAMOND, B.EMERALD_ORE: I.EMERALD,
            B.LAPIS_ORE: I.LAPIS, B.REDSTONE_ORE: B.REDSTONE_WIRE, B.NETHER_QUARTZ_ORE: I.QUARTZ}
for _log in LOGS:
    SMELTING[_log] = I.CHARCOAL

_FUEL = {I.COAL: 8.0, I.CHARCOAL: 8.0, B.COAL_BLOCK: 80.0, B.CRAFTING_TABLE: 1.5, B.BOOKSHELF: 1.5,
         I.WOODEN_PICKAXE: 1.0, I.WOODEN_AXE: 1.0, I.WOODEN_SHOVEL: 1.0, I.STICK: 0.5}
for _item in LOGS | PLANKS_ANY:
    _FUEL[_item] = 1.5


def smelt_result(item):
    return SMELTING.get(item)


def fuel_value(item):
    return _FUEL.get(item, 0.0)
