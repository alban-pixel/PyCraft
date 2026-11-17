"""Texture packs in Minecraft's format: finding them, and loading their block textures into the
game's tiles.

A pack is a folder, a .zip, or the .jar of a Minecraft version installed on this computer. Its
block textures are in assets/minecraft/textures/blocks/ (up to 1.12) or .../block/ (1.13 on,
renamed). The files are read where they are: nothing is extracted or copied, and the game ships
no pack of its own. The generated textures stay the default, and fill in whatever a pack lacks."""
import io
import json
import os
import re
import sys
import zipfile
import zlib
from dataclasses import dataclass

import numpy as np

from pycraft import blocks as B
from pycraft.blocks import TINT_ALPHA
from pycraft.tiles import resize_tile

TEXTURE_DIRS = {"1.8": "assets/minecraft/textures/blocks/", "1.13": "assets/minecraft/textures/block/"}


@dataclass(frozen=True)
class PackInfo:
    name: str  # as shown in the settings
    path: str  # folder, .zip or .jar
    description: str
    layout: str  # "1.8" or "1.13": which texture folder and names it uses


def clean_name(text):
    """Text for the 3x5 font: without Minecraft's formatting codes (§ and a letter), printable
    ASCII only."""
    text = re.sub("§.", "", str(text))
    return " ".join("".join(c for c in text if " " <= c <= "~").split())


def _component_text(value):
    """The text of a pack description: a string, or a JSON text component (object or list)."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_component_text(v) for v in value)
    if isinstance(value, dict):
        return _component_text(value.get("text", "")) + "".join(_component_text(v) for v in value.get("extra", []))
    return ""


def minecraft_dir():
    """The folder of the Minecraft installed on this computer, or None."""
    if sys.platform == "darwin":
        path = os.path.expanduser("~/Library/Application Support/minecraft")
    elif sys.platform == "win32":
        path = os.path.join(os.environ.get("APPDATA", ""), ".minecraft")
    else:
        path = os.path.expanduser("~/.minecraft")
    return path if os.path.isdir(path) else None


def pack_dirs(data_dir):
    """The folders where packs are looked for: the game's own resourcepacks folder (made if
    missing), then the installed Minecraft's."""
    own = os.path.join(data_dir, "resourcepacks")
    try:
        os.makedirs(own, exist_ok=True)
    except OSError:
        pass
    dirs = [own]
    mc = minecraft_dir()
    if mc and os.path.isdir(os.path.join(mc, "resourcepacks")):
        dirs.append(os.path.join(mc, "resourcepacks"))
    return dirs


def minecraft_jars():
    """The .jar of every Minecraft version installed on this computer."""
    mc = minecraft_dir()
    if not mc:
        return []
    versions = os.path.join(mc, "versions")
    try:
        names = sorted(os.listdir(versions))
    except OSError:
        return []
    return [os.path.join(versions, v, v + ".jar") for v in names if os.path.isfile(os.path.join(versions, v, v + ".jar"))]


class PackFiles:
    """The block textures of a pack, read by name (without .png)."""

    def __init__(self, path, layout):
        self.prefix = TEXTURE_DIRS[layout]
        self.zip = None
        if os.path.isdir(path):
            self.root = os.path.join(path, *self.prefix.split("/"))
        else:
            self.zip = zipfile.ZipFile(path)
            self.members = {n[len(self.prefix):-4]: n for n in self.zip.namelist()
                            if n.startswith(self.prefix) and n.endswith(".png")}

    def names(self):
        if self.zip is not None:
            return set(self.members)
        out = set()
        for folder, _, files in os.walk(self.root):
            rel = os.path.relpath(folder, self.root)
            for f in files:
                if f.endswith(".png"):
                    out.add(f[:-4] if rel == "." else f"{rel}/{f[:-4]}".replace(os.sep, "/"))
        return out

    def read(self, name):
        """The PNG's bytes, or None if the pack doesn't have it (or it can't be read)."""
        try:
            if self.zip is not None:
                member = self.members.get(name)
                return None if member is None else self.zip.read(member)
            with open(os.path.join(self.root, *name.split("/")) + ".png", "rb") as f:
                return f.read()
        except (OSError, KeyError, zipfile.BadZipFile, RuntimeError, ValueError, EOFError, zlib.error):
            return None  # (a damaged member of a zip: zlib.error or EOFError)

    def close(self):
        if self.zip is not None:
            self.zip.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def open_pack(info):
    return PackFiles(info.path, info.layout)


def _inspect(path, name):
    """A PackInfo for this folder, zip or jar, or None if it holds no block textures."""
    try:
        if os.path.isdir(path):
            def count(prefix):
                folder = os.path.join(path, *prefix.split("/"))
                return sum(f.endswith(".png") for _, _, fs in os.walk(folder) for f in fs)
            meta_path = os.path.join(path, "pack.mcmeta")
            meta = open(meta_path, "rb").read() if os.path.isfile(meta_path) else None
        else:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                try:  # a damaged description doesn't hide the pack
                    meta = z.read("pack.mcmeta") if "pack.mcmeta" in names else None
                except (OSError, zipfile.BadZipFile, RuntimeError, ValueError, EOFError, zlib.error):
                    meta = None

            def count(prefix):
                return sum(n.startswith(prefix) and n.endswith(".png") for n in names)
        counts = {layout: count(prefix) for layout, prefix in TEXTURE_DIRS.items()}
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError, EOFError, zlib.error):
        return None
    layout = max(counts, key=counts.get)
    if counts[layout] == 0:
        return None
    description = ""
    if meta is not None:
        try:
            description = clean_name(_component_text(json.loads(meta.decode("utf-8-sig"))["pack"]["description"]))
        except (ValueError, KeyError, TypeError, UnicodeDecodeError, RecursionError):
            description = ""
    return PackInfo(clean_name(name) or "Pack", path, description, layout)


def find_packs(dirs, jars):
    """Every pack in these folders (subfolders and .zip files), and these Minecraft .jar files,
    sorted by name."""
    found, seen = [], set()
    candidates = []
    for d in dirs:
        try:
            entries = sorted(os.listdir(d))
        except OSError:
            continue
        for e in entries:
            path = os.path.join(d, e)
            if os.path.isdir(path):
                candidates.append((path, e))
            elif e.lower().endswith(".zip"):
                candidates.append((path, e[:-4]))
    for jar in jars:
        candidates.append((jar, "Minecraft " + os.path.basename(jar)[:-4]))
    for path, name in candidates:
        key = os.path.realpath(path)
        if key in seen:
            continue
        seen.add(key)
        info = _inspect(path, name)
        if info is not None:
            found.append(info)
    # A folder and a .zip of the same pack: the zip says so
    names = [p.name for p in found]
    found = [PackInfo(p.name + " (zip)", p.path, p.description, p.layout)
             if names.count(p.name) > 1 and p.path.lower().endswith(".zip") else p for p in found]
    return sorted(found, key=lambda p: (p.name.lower(), p.path))


# --- Loading a pack into the tiles ----------------------------------------------------------------

class PackError(Exception):
    """A pack that can't be used at all."""


def _n(*names):
    return tuple(n for n in names if n)


# For each tile: the names of its texture in 1.8 (textures/blocks) and in 1.13 and later
# (textures/block), each a tuple of names to try in order. An empty tuple: Minecraft has no such
# texture in that version; the generated tile stays.
_TABLE = [
    (B.T_GRASS_TOP, _n("grass_top"), _n("grass_block_top")),
    (B.T_GRASS_SIDE, _n("grass_side"), _n("grass_block_side")),  # + its overlay, see GRASS_OVERLAY
    (B.T_DIRT, _n("dirt"), _n("dirt")),
    (B.T_STONE, _n("stone"), _n("stone")),
    (B.T_COBBLE, _n("cobblestone"), _n("cobblestone")),
    (B.T_PLANKS, _n("planks_oak"), _n("oak_planks")),
    (B.T_LOG_SIDE, _n("log_oak"), _n("oak_log")),
    (B.T_LOG_TOP, _n("log_oak_top"), _n("oak_log_top")),
    (B.T_LEAVES, _n("leaves_oak"), _n("oak_leaves")),
    (B.T_SAND, _n("sand"), _n("sand")),
    (B.T_BRICK, _n("brick"), _n("bricks")),
    (B.T_GLASS, _n("glass"), _n("glass")),
    (B.T_WATER, _n("water_still"), _n("water_still")),
    (B.T_COAL, _n("coal_ore"), _n("coal_ore")),
    (B.T_IRON, _n("iron_ore"), _n("iron_ore")),
    (B.T_BEDROCK, _n("bedrock"), _n("bedrock")),
    (B.T_SNOW, _n("snow"), _n("snow")),
    (B.T_ICE, _n("ice"), _n("ice")),
    (B.T_GRAVEL, _n("gravel"), _n("gravel")),
    (B.T_SANDSTONE_TOP, _n("sandstone_top"), _n("sandstone_top")),
    (B.T_SANDSTONE_SIDE, _n("sandstone_normal"), _n("sandstone")),
    (B.T_RED_SAND, _n("red_sand"), _n("red_sand")),
    (B.T_TERRACOTTA, _n("hardened_clay"), _n("terracotta")),
    (B.T_PODZOL_TOP, _n("dirt_podzol_top"), _n("podzol_top")),
    (B.T_PODZOL_SIDE, _n("dirt_podzol_side"), _n("podzol_side")),
    (B.T_SPRUCE_LOG_SIDE, _n("log_spruce"), _n("spruce_log")),
    (B.T_SPRUCE_LOG_TOP, _n("log_spruce_top"), _n("spruce_log_top")),
    (B.T_SPRUCE_LEAVES, _n("leaves_spruce"), _n("spruce_leaves")),
    (B.T_BIRCH_LOG_SIDE, _n("log_birch"), _n("birch_log")),
    (B.T_BIRCH_LOG_TOP, _n("log_birch_top"), _n("birch_log_top")),
    (B.T_BIRCH_LEAVES, _n("leaves_birch"), _n("birch_leaves")),
    (B.T_JUNGLE_LOG_SIDE, _n("log_jungle"), _n("jungle_log")),
    (B.T_JUNGLE_LOG_TOP, _n("log_jungle_top"), _n("jungle_log_top")),
    (B.T_JUNGLE_LEAVES, _n("leaves_jungle"), _n("jungle_leaves")),
    (B.T_ACACIA_LOG_SIDE, _n("log_acacia"), _n("acacia_log")),
    (B.T_ACACIA_LOG_TOP, _n("log_acacia_top"), _n("acacia_log_top")),
    (B.T_ACACIA_LEAVES, _n("leaves_acacia"), _n("acacia_leaves")),
    (B.T_CACTUS_SIDE, _n("cactus_side"), _n("cactus_side")),
    (B.T_CACTUS_TOP, _n("cactus_top"), _n("cactus_top")),
    (B.T_GOLD, _n("gold_ore"), _n("gold_ore")),
    (B.T_DIAMOND, _n("diamond_ore"), _n("diamond_ore")),
    (B.T_DEEPSLATE, (), _n("deepslate")),
    (B.T_CLAY, _n("clay"), _n("clay")),
    (B.T_MUD, (), _n("mud")),
    (B.T_MOSS, (), _n("moss_block")),
    (B.T_SPRUCE_PLANKS, _n("planks_spruce"), _n("spruce_planks")),
    (B.T_BIRCH_PLANKS, _n("planks_birch"), _n("birch_planks")),
    (B.T_JUNGLE_PLANKS, _n("planks_jungle"), _n("jungle_planks")),
    (B.T_ACACIA_PLANKS, _n("planks_acacia"), _n("acacia_planks")),
    (B.T_STONE_BRICKS, _n("stonebrick"), _n("stone_bricks")),
    (B.T_MOSSY_STONE_BRICKS, _n("stonebrick_mossy"), _n("mossy_stone_bricks")),
    (B.T_CRACKED_STONE_BRICKS, _n("stonebrick_cracked"), _n("cracked_stone_bricks")),
    (B.T_MOSSY_COBBLE, _n("cobblestone_mossy"), _n("mossy_cobblestone")),
    (B.T_SMOOTH_STONE, _n("stone_slab_top"), _n("smooth_stone")),
    (B.T_GRANITE, _n("stone_granite"), _n("granite")),
    (B.T_POLISHED_GRANITE, _n("stone_granite_smooth"), _n("polished_granite")),
    (B.T_DIORITE, _n("stone_diorite"), _n("diorite")),
    (B.T_POLISHED_DIORITE, _n("stone_diorite_smooth"), _n("polished_diorite")),
    (B.T_ANDESITE, _n("stone_andesite"), _n("andesite")),
    (B.T_POLISHED_ANDESITE, _n("stone_andesite_smooth"), _n("polished_andesite")),
    (B.T_CUT_SANDSTONE, _n("sandstone_smooth"), _n("cut_sandstone")),
    (B.T_CHISELED_SANDSTONE, _n("sandstone_carved"), _n("chiseled_sandstone")),
    (B.T_RED_SANDSTONE_TOP, _n("red_sandstone_top"), _n("red_sandstone_top")),
    (B.T_RED_SANDSTONE_SIDE, _n("red_sandstone_normal"), _n("red_sandstone")),
    (B.T_CUT_RED_SANDSTONE, _n("red_sandstone_smooth"), _n("cut_red_sandstone")),
    (B.T_COAL_BLOCK, _n("coal_block"), _n("coal_block")),
    (B.T_IRON_BLOCK, _n("iron_block"), _n("iron_block")),
    (B.T_GOLD_BLOCK, _n("gold_block"), _n("gold_block")),
    (B.T_DIAMOND_BLOCK, _n("diamond_block"), _n("diamond_block")),
    (B.T_OBSIDIAN, _n("obsidian"), _n("obsidian")),
    (B.T_BOOKSHELF, _n("bookshelf"), _n("bookshelf")),
    (B.T_HAY_SIDE, _n("hay_block_side"), _n("hay_block_side")),
    (B.T_HAY_TOP, _n("hay_block_top"), _n("hay_block_top")),
    (B.T_PUMPKIN_SIDE, _n("pumpkin_side"), _n("pumpkin_side")),
    (B.T_PUMPKIN_TOP, _n("pumpkin_top"), _n("pumpkin_top")),
    (B.T_MELON_SIDE, _n("melon_side"), _n("melon_side")),
    (B.T_MELON_TOP, _n("melon_top"), _n("melon_top")),
    (B.T_DEEPSLATE_BRICKS, (), _n("deepslate_bricks")),
    (B.T_POLISHED_DEEPSLATE, (), _n("polished_deepslate")),
    (B.T_MUD_BRICKS, (), _n("mud_bricks")),
    (B.T_QUARTZ, _n("quartz_block_side"), _n("quartz_block_side")),
    (B.T_TALL_GRASS, _n("tallgrass"), _n("short_grass", "grass")),
    (B.T_FERN, _n("fern"), _n("fern")),
    (B.T_DEAD_BUSH, _n("deadbush"), _n("dead_bush")),
    (B.T_POPPY, _n("flower_rose"), _n("poppy")),
    (B.T_DANDELION, _n("flower_dandelion"), _n("dandelion")),
    (B.T_BLUE_ORCHID, _n("flower_blue_orchid"), _n("blue_orchid")),
    (B.T_CORNFLOWER, (), _n("cornflower")),
    (B.T_OXEYE_DAISY, _n("flower_oxeye_daisy"), _n("oxeye_daisy")),
    (B.T_ALLIUM, _n("flower_allium"), _n("allium")),
    (B.T_OAK_SAPLING, _n("sapling_oak"), _n("oak_sapling")),
    (B.T_COARSE_DIRT, _n("coarse_dirt"), _n("coarse_dirt")),
    (B.T_MYCELIUM_TOP, _n("mycelium_top"), _n("mycelium_top")),
    (B.T_MYCELIUM_SIDE, _n("mycelium_side"), _n("mycelium_side")),
    (B.T_FARMLAND, _n("farmland_dry"), _n("farmland")),
    (B.T_PACKED_ICE, _n("ice_packed"), _n("packed_ice")),
    (B.T_SPONGE, _n("sponge"), _n("sponge")),
    (B.T_WET_SPONGE, _n("sponge_wet"), _n("wet_sponge")),
    (B.T_EMERALD_ORE, _n("emerald_ore"), _n("emerald_ore")),
    (B.T_LAPIS_ORE, _n("lapis_ore"), _n("lapis_ore")),
    (B.T_REDSTONE_ORE, _n("redstone_ore"), _n("redstone_ore")),
    (B.T_NETHER_QUARTZ_ORE, _n("quartz_ore"), _n("nether_quartz_ore")),
    (B.T_NETHERRACK, _n("netherrack"), _n("netherrack")),
    (B.T_SOUL_SAND, _n("soul_sand"), _n("soul_sand")),
    (B.T_NETHER_BRICKS, _n("nether_brick"), _n("nether_bricks")),
    (B.T_END_STONE, _n("end_stone"), _n("end_stone")),
    (B.T_PRISMARINE, _n("prismarine_rough"), _n("prismarine")),
    (B.T_PRISMARINE_BRICKS, _n("prismarine_bricks"), _n("prismarine_bricks")),
    (B.T_DARK_PRISMARINE, _n("prismarine_dark"), _n("dark_prismarine")),
    (B.T_BROWN_MUSHROOM, _n("mushroom_block_skin_brown"), _n("brown_mushroom_block")),
    (B.T_RED_MUSHROOM, _n("mushroom_block_skin_red"), _n("red_mushroom_block")),
    (B.T_MUSHROOM_STEM, _n("mushroom_block_skin_stem"), _n("mushroom_stem")),
    (B.T_SLIME, _n("slime"), _n("slime_block")),
    (B.T_CHISELED_STONE_BRICKS, _n("stonebrick_carved"), _n("chiseled_stone_bricks")),
    (B.T_CHISELED_QUARTZ, _n("quartz_block_chiseled"), _n("chiseled_quartz_block")),
    (B.T_QUARTZ_PILLAR_SIDE, _n("quartz_block_lines"), _n("quartz_pillar")),
    (B.T_QUARTZ_PILLAR_TOP, _n("quartz_block_lines_top"), _n("quartz_pillar_top")),
    (B.T_CHISELED_RED_SANDSTONE, _n("red_sandstone_carved"), _n("chiseled_red_sandstone")),
    (B.T_LAPIS_BLOCK, _n("lapis_block"), _n("lapis_block")),
    (B.T_EMERALD_BLOCK, _n("emerald_block"), _n("emerald_block")),
    (B.T_REDSTONE_BLOCK, _n("redstone_block"), _n("redstone_block")),
    (B.T_DARK_OAK_LOG_SIDE, _n("log_big_oak"), _n("dark_oak_log")),
    (B.T_DARK_OAK_LOG_TOP, _n("log_big_oak_top"), _n("dark_oak_log_top")),
    (B.T_DARK_OAK_PLANKS, _n("planks_big_oak"), _n("dark_oak_planks")),
    (B.T_DARK_OAK_LEAVES, _n("leaves_big_oak"), _n("dark_oak_leaves")),
    (B.T_CRAFTING_TABLE_TOP, _n("crafting_table_top"), _n("crafting_table_top")),
    (B.T_CRAFTING_TABLE_SIDE, _n("crafting_table_side"), _n("crafting_table_side")),
    (B.T_CRAFTING_TABLE_FRONT, _n("crafting_table_front"), _n("crafting_table_front")),
    (B.T_FURNACE_SIDE, _n("furnace_side"), _n("furnace_side")),
    (B.T_FURNACE_TOP, _n("furnace_top"), _n("furnace_top")),
    (B.T_FURNACE_FRONT, _n("furnace_front_off"), _n("furnace_front")),
    (B.T_DISPENSER_FRONT, _n("dispenser_front_horizontal"), _n("dispenser_front")),
    (B.T_DROPPER_FRONT, _n("dropper_front_horizontal"), _n("dropper_front")),
    (B.T_NOTE_BLOCK, _n("noteblock"), _n("note_block")),
    (B.T_JUKEBOX_SIDE, _n("jukebox_side"), _n("jukebox_side")),
    (B.T_JUKEBOX_TOP, _n("jukebox_top"), _n("jukebox_top")),
    (B.T_TNT_SIDE, _n("tnt_side"), _n("tnt_side")),
    (B.T_TNT_TOP, _n("tnt_top"), _n("tnt_top")),
    (B.T_PISTON_SIDE, _n("piston_side"), _n("piston_side")),
    (B.T_PISTON_TOP, _n("piston_top_normal"), _n("piston_top")),
    (B.T_PISTON_BOTTOM, _n("piston_bottom"), _n("piston_bottom")),
    (B.T_STICKY_PISTON_TOP, _n("piston_top_sticky"), _n("piston_top_sticky")),
    (B.T_COMMAND_BLOCK, _n("command_block"), _n("command_block_side")),
    (B.T_GLOWSTONE, _n("glowstone"), _n("glowstone")),
    (B.T_SEA_LANTERN, _n("sea_lantern"), _n("sea_lantern")),
    (B.T_REDSTONE_LAMP, _n("redstone_lamp_on"), _n("redstone_lamp_on")),
    (B.T_JACK_O_LANTERN, _n("pumpkin_face_on"), _n("jack_o_lantern")),
    (B.T_SPAWNER, _n("mob_spawner"), _n("spawner")),
    (B.T_LEVER, _n("lever"), _n("lever")),
    (B.T_REDSTONE_DUST, _n("redstone_dust_cross"), _n("redstone_dust_dot")),
    (B.T_REDSTONE_TORCH_ON, _n("redstone_torch_on"), _n("redstone_torch")),
    (B.T_REDSTONE_TORCH_OFF, _n("redstone_torch_off"), _n("redstone_torch_off")),
    (B.T_REPEATER_OFF, _n("repeater_off"), _n("repeater")),
    (B.T_REPEATER_ON, _n("repeater_on"), _n("repeater_on")),
    (B.T_REDSTONE_LAMP_OFF, _n("redstone_lamp_off"), _n("redstone_lamp")),
    (B.T_PISTON_INNER, _n("piston_inner"), _n("piston_inner")),
]
# The 16 colors: 1.8 calls light gray "silver"
_COLORS = ["white", "orange", "magenta", "light_blue", "yellow", "lime", "pink", "gray", "light_gray", "cyan",
           "purple", "blue", "brown", "green", "red", "black"]
for _c in _COLORS:
    _old = "silver" if _c == "light_gray" else _c
    _table_name = _c.upper()
    _TABLE.append((getattr(B, f"T_{_table_name}_WOOL"), _n(f"wool_colored_{_old}"), _n(f"{_c}_wool")))
    _TABLE.append((getattr(B, f"T_{_table_name}_STAINED_GLASS"), _n(f"glass_{_old}"), _n(f"{_c}_stained_glass")))
    _TABLE.append((getattr(B, f"T_{_table_name}_TERRACOTTA"), _n(f"hardened_clay_stained_{_old}"),
                   _n(f"{_c}_terracotta")))

TILE_FILES = {t: (n18, n113) for t, n18, n113 in _TABLE}
GRASS_OVERLAY = {"1.8": "grass_side_overlay", "1.13": "grass_block_side_overlay"}

BIOME_TINTED = {B.T_GRASS_TOP, B.T_TALL_GRASS, B.T_FERN, B.T_LEAVES, B.T_JUNGLE_LEAVES, B.T_ACACIA_LEAVES, B.T_WATER,
                B.T_REDSTONE_DUST}  # (dust: colored by its power, through the same tint)
LEAF_TILES = {B.T_LEAVES, B.T_SPRUCE_LEAVES, B.T_BIRCH_LEAVES, B.T_JUNGLE_LEAVES, B.T_ACACIA_LEAVES,
              B.T_DARK_OAK_LEAVES}
# Leaves the game doesn't color by the biome: Minecraft's own fixed colors for spruce and birch;
# dark oak takes the color of the game's generated dark oak leaves (load_pack)
FIXED_LEAF = {B.T_SPRUCE_LEAVES: (0x61, 0x99, 0x61), B.T_BIRCH_LEAVES: (0x80, 0xA7, 0x55)}
GREY_SATURATION = 0.15  # below this average saturation, a texture is grey: made to take a color
TINT_GREY = 204  # average brightness of the game's grey textures, which its biome colors suit


def _decode(data):
    """An (n, n, 4) uint8 array from PNG bytes: RGBA, the first frame of an animation (frames are
    stacked downward), alpha made 0 or 255. None if it can't be read."""
    if data is None:
        return None
    from PIL import Image  # only needed here, so the game runs without Pillow
    try:
        with Image.open(io.BytesIO(data)) as img:
            pixels = np.asarray(img.convert("RGBA"), np.uint8).copy()
    except Exception:  # Pillow raises many kinds of errors for a broken file
        return None
    h, w = pixels.shape[:2]
    side = min(h, w)
    if side == 0:
        return None
    pixels = pixels[:side, :side]
    pixels[..., 3] = np.where(pixels[..., 3] >= 128, 255, 0)
    return pixels


def _tile_size(sizes):
    """The size of every tile: the most common texture size (the larger on a tie), rounded to the
    nearest power of 2, from 16 to 256."""
    values, counts = np.unique(sizes, return_counts=True)
    common = int(values[np.flatnonzero(counts == counts.max())[-1]])
    return int(min(max(2 ** round(np.log2(common)), 16), 256))


def _is_grey(tile):
    seen = tile[..., 3] > 0
    if not seen.any():
        return False
    rgb = tile[seen][:, :3].astype(float)
    return (rgb.max(axis=1) - rgb.min(axis=1)).mean() / 255 < GREY_SATURATION


def _tint(tile, where, reference=None):
    """Mark these texels as colored by the biome, scaled so that their brightness averages
    TINT_GREY (or that of the reference texels)."""
    ref = tile[where if reference is None else reference][:, :3].astype(float)
    mean = ref.mean() if ref.size else TINT_GREY
    scale = TINT_GREY / max(mean, 1.0)
    tile[where, :3] = np.clip(np.rint(tile[where, :3] * scale), 0, 255)
    tile[where, 3] = TINT_ALPHA


def load_pack(info, base):
    """The tiles of a pack: (256, N, N, 4) uint8 at the pack's size, the generated tiles base
    filling in what it lacks. Returns (tiles, names of the textures it lacks). Raises PackError if
    the pack has none of the textures the game uses."""
    other = "1.13" if info.layout == "1.8" else "1.8"
    images, missing = {}, []
    with open_pack(info) as files:
        def find(names_mine, names_other):
            for name in names_mine + names_other:
                img = _decode(files.read(name))
                if img is not None:
                    return img
            return None

        for t, names in TILE_FILES.items():
            mine, theirs = (names[0], names[1]) if info.layout == "1.8" else (names[1], names[0])
            img = find(mine, theirs)
            if img is not None:
                images[t] = img
            elif mine:
                missing.append(mine[0])
        overlay = find((GRASS_OVERLAY[info.layout],), (GRASS_OVERLAY[other],))
    if not images:
        raise PackError("no block textures this game uses")
    n = _tile_size([img.shape[0] for img in images.values()])
    tiles = np.stack([resize_tile(base[t], n) for t in range(base.shape[0])])
    for t, img in images.items():
        tile = resize_tile(img, n)
        if t == B.T_WATER:
            tile[..., 3] = 255  # the game makes water see-through itself: a pack's clear water stays water
        seen = tile[..., 3] > 0
        if t in BIOME_TINTED and _is_grey(tile):
            _tint(tile, seen)
        elif t == B.T_GRASS_SIDE and overlay is not None:
            over = resize_tile(overlay, n)
            top = over[..., 3] > 0
            if top.any() and _is_grey(over):
                tile[top, :3] = over[top, :3]
                _tint(tile, top)
        if t in LEAF_TILES and t not in BIOME_TINTED and _is_grey(tile):
            if t in FIXED_LEAF:
                color = np.array(FIXED_LEAF[t], float)
            else:  # dark oak: the color of the generated leaves
                gen = base[t]
                color = gen[gen[..., 3] > 0][:, :3].astype(float).mean(axis=0)
            tile[seen, :3] = np.clip(np.rint(tile[seen, :3].astype(float) * color / 255), 0, 255)
            tile[seen, 3] = 255
        if t in LEAF_TILES and seen.any() and not seen.all():
            # The holes are drawn too (the shaded leaves inside a crown): their color, the leaves'
            tile[~seen, :3] = np.rint(tile[seen][:, :3].astype(float).mean(axis=0))
        tiles[t] = tile
    return tiles, missing
