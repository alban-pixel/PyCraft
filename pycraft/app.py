"""PyCraft: a Minecraft-like game. OpenGL draws the 3D world, Pyxel shows it and runs everything else.

Run it with `python -m pycraft`."""
import ctypes
import importlib.util
import json
import math
import os
import random
import sys
import time

import moderngl
import numpy as np
import pyxel

from pycraft import packs
from pycraft import redstone
from pycraft.autoscale import AutoScale
from pycraft.blocks import (DOWN, EAST, FACING_VECTORS, LEVER, NORTH, OPAQUE, OPPOSITE, PISTON, REDSTONE_TORCH,
                            REDSTONE_WIRE, REPEATER, SOUTH, STICKY_PISTON, STONE_BUTTON, STONE_PRESSURE_PLATE, UP, WEST)
from pycraft.blocks import (ATLAS_TILES, BLOCK_NAMES, BLOCK_TILES, DEFAULT_HOTBAR, FACING, GROWS_ON, PLACEABLE,
                            PLANT, SOLID, T_REDSTONE_DUST, T_WATER, TILE, TINT_ALPHA, UNBREAKABLE, WATER, turned)
from pycraft.tiles import build_tiles, tiles_to_atlas
from pycraft.controls import ACTIONS, LABELS, Controls
from pycraft.player import Player
from pycraft.sim import Simulation
from pycraft.render import FIXED_COLORS, LOD_QUALITY_NAMES, Renderer, oklab_to_srgb, srgb_to_oklab
from pycraft.terrain import SEA_LEVEL
from pycraft.ui import (AMBER, ASH, BLACK, COAL, CREAM, GOLD, IRON, PALETTE, RUST, TEXT, TEXT_DIM, TEXT_HOT, WHITE, Ui,
                        text_width)
from pycraft.world import World

BASE_WIDTH, BASE_HEIGHT = 320, 180  # the menus and the mouse speed are designed for this size
RESOLUTIONS = [(320, 180), (384, 216), (480, 270), (640, 360), (800, 450), (960, 540), (1280, 720), (1600, 900),
               (1920, 1080), (2560, 1440)]
FRAME_RATES = [30, 60, 75, 120, 144, 165, 240]
RENDER_DISTANCES = [32, 64, 128, 256, 512]  # how far the world is seen, in chunks of 16 blocks
RENDER_SCALES = ["auto", 1.0, 0.75, 0.5]  # share of the resolution the 3D view is drawn at ("auto": follows the FPS)
AUTOSAVES = [0, 1, 2, 5, 10]  # minutes between two automatic saves (0: only when leaving through the menu)
DAY_LENGTHS = [10, 20, 40, 60]  # minutes a full day and night last
CROSSHAIRS = ["cross", "dot", "none"]
RANGES = {  # the settings on a scale: (lowest, highest, step)
    "fov": (50, 110, 5),  # field of view, degrees from the top of the screen to the bottom
    "sensitivity": (10, 300, 10),  # mouse speed, percent
    "look_speed": (30, 240, 10),  # looking around with the arrow keys, degrees per second
    "music_volume": (0, 100, 10),
    "sound_volume": (0, 100, 10),
}
DEFAULT_SETTINGS = {"resolution": (1280, 720), "fps": 60, "render_distance": 256, "lod_quality": "low",
                    "fancy": True, "ui_scale": "auto", "render_scale": "auto", "fov": 70,
                    "sensitivity": 100, "invert_y": False, "look_speed": 120,
                    "music_volume": 50, "sound_volume": 100,
                    "autosave": 2, "day_length": 20, "show_help": True, "crosshair": "cross", "keys": {},
                    "texture_pack": None}  # texture_pack: path of the pack, None for the game's own textures
SETTING_TABS = {  # the tabs of the settings screen and the settings each one holds
    "Video": ["resolution", "ui_scale", "fps", "fov", "render_scale", "render_distance", "lod_quality", "fancy",
              "texture_pack"],
    "Controls": ["sensitivity", "invert_y", "look_speed"],
    "Keys": ["keys"],
    "Sound": ["music_volume", "sound_volume"],
    "Game": ["autosave", "day_length", "show_help", "crosshair"],
}
TAB_NAMES = list(SETTING_TABS)
SAVE_FILE = "world2.npz"  # "world.npz" holds a world of the older, smaller version: left alone
LOADING_RADIUS = 2  # chunks around the player that must be ready before playing
HAZE = 1 / 4500  # share of light lost per block of distance: far mountains fade into the sky
FOG_START = 0.75  # the fog that hides the end of the world starts at this share of the view distance
MAX_DT = 1 / 30  # longest time step: slower frames slow the game down instead of making the player skip
REACH = 6.0
INVENTORY_COLUMNS = 13
INVENTORY_SLOT = TILE + 6  # side of a slot of the inventory, in UI pixels
INVENTORY_HEADER, INVENTORY_FOOTER = 19, 16  # room above the slots (the tabs) and below (pages, hints)
INVENTORY_BELOW = 32  # UI pixels kept free at the bottom of the screen: the hotbar
HOTBAR_SLOT = TILE + 6
BUTTON_W, BUTTON_H, BUTTON_PITCH = 128, 15, 19  # buttons of the title screen and the pause menu
SETTINGS_W, SETTINGS_H = 304, 172  # the settings panel
TAB_H, ROW_H, ROW_PITCH = 13, 12, 13  # its tabs and its rows
SETTING_ROWS = 9  # rows that fit under the tabs (the keys go in two columns of them)
NAME_SECONDS = 3.0  # the chosen block's name shows this long above the hotbar
MOUSE_SENSITIVITY = 0.45  # degrees per pixel at 320x180, with the mouse speed setting at 100%
ZOOM_FOV = 22.0  # field of view while the zoom key is held
MUSIC_GAIN, SOUND_GAIN = 0.14, 0.125  # the channels' gains at full volume
HELP_SECONDS = 15

# Sky colors (RGB 0-1)
DAY_ZENITH, DAY_HORIZON = (0.38, 0.6, 1.0), (0.68, 0.84, 1.0)
NIGHT_ZENITH, NIGHT_HORIZON = (0.01, 0.01, 0.06), (0.06, 0.08, 0.18)
SUNSET = (1.0, 0.55, 0.3)
UNDERWATER_FOG = (0.08, 0.2, 0.5)
ICON_GREEN, ICON_BLUE = (0.5, 0.72, 0.33), (0.25, 0.45, 0.95)  # grass/leaves and water in the inventory
ICON_RED = (0.9, 0.12, 0.08)  # redstone dust in the inventory
# Light (RGB): direct light from the sun or the moon, and the light of the whole sky
NOON_LIGHT, SUNSET_LIGHT, MOON_LIGHT = (0.56, 0.54, 0.48), (0.6, 0.36, 0.2), (0.1, 0.12, 0.17)
DAY_SKY_LIGHT, NIGHT_SKY_LIGHT, SUNSET_SKY_LIGHT = (0.52, 0.56, 0.63), (0.17, 0.19, 0.28), (0.58, 0.46, 0.44)
SUN_GLOW = (1.0, 0.7, 0.4)
SUN_TILT = 0.5  # the sun's path leans to one side (63 degrees up at most), so walls facing it get light
CLOUD_COVER = 0.56  # share of the sky without clouds (about)
DIM = 0.5  # brightness of the world behind the menus

# Sound numbers; sound effects play on channel 3, music on channels 0-2
SND_BREAK, SND_PLACE, SND_JUMP, SND_STEP, SND_SPLASH, SND_CLICK = range(6)
SFX_CHANNEL = 3

# The inventory's tabs. Plants and colored blocks are found by their names, the others listed here.
NATURE = {"Grass", "Dirt", "Stone", "Sand", "Water", "Snow", "Ice", "Gravel", "Red sand", "Podzol", "Cactus",
          "Deepslate", "Clay", "Mud", "Moss", "Granite", "Diorite", "Andesite", "Obsidian", "Coarse dirt", "Mycelium",
          "Farmland", "Packed ice", "Netherrack", "Soul sand", "End stone", "Brown mushroom block",
          "Red mushroom block", "Mushroom stem", "Pumpkin", "Melon"}
SPECIAL = {"Crafting table", "Furnace", "Dispenser", "Dropper", "Note block", "Jukebox", "Command block",
           "Glowstone", "Sea lantern", "Jack o'lantern", "Monster spawner", "Slime block", "Sponge", "Wet sponge",
           "Bookshelf"}
REDSTONE = {"Lever", "Stone button", "Pressure plate", "Redstone dust", "Redstone torch", "Repeater",
            "Redstone lamp", "Piston", "Sticky piston", "TNT", "Block of redstone"}
INTERACTIVE = {LEVER, STONE_BUTTON, REPEATER}  # a right click works them instead of placing a block


def block_category(block):
    name = BLOCK_NAMES[block]
    if PLANT[block]:
        return "Plants"
    if name.lower().endswith(("wool", "terracotta", "stained glass")):
        return "Colors"
    if name in REDSTONE:
        return "Redstone"
    if name in SPECIAL:
        return "Special"
    if name in NATURE or name.endswith((" ore", " log", " leaves")):
        return "Nature"
    return "Building"


CATEGORIES = [(tab, [b for b in PLACEABLE if tab == "All" or block_category(b) == tab])
              for tab in ("All", "Nature", "Building", "Colors", "Plants", "Redstone", "Special")]


def right_click(block, first_press):
    """What a right click on this block does: "act" (flip a lever...), "place" a block against it,
    or nothing. Held down, it repeats placing, but never flips a lever again or places on it."""
    if block in INTERACTIVE:
        return "act" if first_press else None
    return "place"


def _main_direction(v, horizontal=False):
    """The facing (blocks.FACING_VECTORS) a vector points along the most."""
    x, y, z = v
    if not horizontal and abs(y) > max(abs(x), abs(z)):
        return UP if y > 0 else DOWN
    if abs(x) > abs(z):
        return EAST if x > 0 else WEST
    return SOUTH if z > 0 else NORTH


def placement(block, hit, previous, look, world):
    """The (block, state) to put in the cell previous, aiming at the block hit while looking along
    look; None when it can't go there (a lever needs a full block to be fixed to...)."""
    face = tuple(p - h for p, h in zip(previous, hit))
    facing = FACING_VECTORS.index(face) if face in FACING_VECTORS else UP
    floor = OPAQUE[world.get(previous[0], previous[1] - 1, previous[2])]
    if block in (LEVER, STONE_BUTTON, REDSTONE_TORCH):
        if not OPAQUE[world.get(*hit)] or (block == REDSTONE_TORCH and facing == DOWN):
            return None
        state = facing
        if block == LEVER and facing in (UP, DOWN) and abs(look[0]) > abs(look[2]):
            state |= 16  # a lever on the floor turns with the player's look
        return block, state
    if block in (REDSTONE_WIRE, STONE_PRESSURE_PLATE, REPEATER):
        if not floor:
            return None
        return block, (_main_direction(look, horizontal=True) if block == REPEATER else 0)
    if block in (PISTON, STICKY_PISTON):
        return block, OPPOSITE[_main_direction(look)]  # its face looks back at the player
    return block, 0


# The block the "pick" key puts in the hotbar for each block of the world (a turned furnace: a furnace)
PICKS = {b: b for b in PLACEABLE}
PICKS.update({version: block for block, versions in FACING.items() for version in versions})


def _kmeans(points, weight, centers, rounds):
    """Move the centers to the weighted average of the points nearest to each, a few times."""
    for _ in range(rounds):
        nearest = np.argmin(((points[:, None] - centers[None]) ** 2).sum(-1), axis=1)
        for k in range(len(centers)):
            members = nearest == k
            if members.any():
                centers[k] = np.average(points[members], axis=0, weights=weight[members])
    return centers


def _spread(points, weight, count):
    """Starting centers far apart: each next one is the point worst served by those before it."""
    centers = [points[np.argmax(weight)]]
    gap = ((points - centers[0]) ** 2).sum(-1)
    for _ in range(count - 1):
        centers.append(points[np.argmax(gap * weight)])
        gap = np.minimum(gap, ((points - centers[-1]) ** 2).sum(-1))
    return np.array(centers)


def icon_palette(atlas):
    """The block icons for pyxel.blt: 48 colors that suit them and every pixel as the index of its
    nearest one, 16-63 (0 where transparent). Texels that take the biome color get a typical green
    (blue for water).
    Each icon is first summed up in 4 colors (its main color, darker and lighter texels, specks),
    and the 48 colors are a k-means of those, every icon counting the same: a tile of a rare color
    (a wool, a block of diamond) keeps its own color instead of the many greys and browns taking
    most of the palette."""
    rgb = atlas[..., :3].astype(float) / 255
    tint = np.broadcast_to(np.array(ICON_GREEN), rgb.shape).copy()
    ty, tx = divmod(T_WATER, ATLAS_TILES)
    tint[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE] = ICON_BLUE
    ty, tx = divmod(T_REDSTONE_DUST, ATLAS_TILES)
    tint[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE] = ICON_RED
    rgb = np.where((atlas[..., 3] == TINT_ALPHA)[..., None], rgb * tint, rgb)
    seen = atlas[..., 3] >= 128
    lab = srgb_to_oklab(rgb.reshape(-1, 3)).reshape(rgb.shape)
    points, weight = [], []
    for t in sorted({int(BLOCK_TILES[b][0]) for b in PLACEABLE}):  # the tiles drawn as icons
        ty, tx = divmod(t, ATLAS_TILES)
        cell = (slice(ty * TILE, (ty + 1) * TILE), slice(tx * TILE, (tx + 1) * TILE))
        texels = lab[cell][seen[cell]]
        if len(texels) == 0:
            continue  # nothing to see (a pack's clear glass): no colors to keep for it
        ones = np.ones(len(texels))
        summary = _kmeans(texels, ones, _spread(texels, ones, 4), 8)
        share = np.bincount(np.argmin(((texels[:, None] - summary[None]) ** 2).sum(-1), axis=1), minlength=4)
        points.append(summary[share > 0])
        weight.append(share[share > 0] / len(texels))
    points, weight = np.concatenate(points), np.concatenate(weight)
    centers = _kmeans(points, weight, _spread(points, weight, FIXED_COLORS - 16), 20)
    colors = np.rint(oklab_to_srgb(centers) * 255).astype(np.uint8)
    pixels = lab.reshape(-1, 3)
    nearest = np.argmin(((pixels[:, None] - srgb_to_oklab(colors / 255)[None]) ** 2).sum(-1), axis=1)
    indices = (16 + nearest).reshape(seen.shape).astype(np.uint8)
    indices[~seen] = 0
    return [int(r) << 16 | int(g) << 8 | int(b) for r, g, b in colors], indices


def parse_settings(saved):
    """The settings from settings.json's contents, with the default for any that is missing or
    not valid."""
    settings = dict(DEFAULT_SETTINGS)
    if not isinstance(saved, dict):
        return settings
    resolution = saved.get("resolution")
    if isinstance(resolution, list) and tuple(resolution) in RESOLUTIONS:
        settings["resolution"] = tuple(resolution)
    ui_scale = saved.get("ui_scale")
    if ui_scale == "auto" or (type(ui_scale) is int and 1 <= ui_scale <= 8):
        settings["ui_scale"] = ui_scale
    choices = {"fps": FRAME_RATES, "render_distance": RENDER_DISTANCES, "lod_quality": LOD_QUALITY_NAMES,
               "render_scale": RENDER_SCALES, "autosave": AUTOSAVES, "day_length": DAY_LENGTHS,
               "crosshair": CROSSHAIRS}
    for key, allowed in choices.items():
        if type(saved.get(key)) is not bool and saved.get(key) in allowed:
            settings[key] = saved[key]
    for key, (low, high, step) in RANGES.items():
        value = saved.get(key)
        if type(value) is int and low <= value <= high and (value - low) % step == 0:
            settings[key] = value
    for key in ("fancy", "invert_y", "show_help"):
        if isinstance(saved.get(key), bool):
            settings[key] = saved[key]
    if saved.get("music") is False and "music_volume" not in saved:
        settings["music_volume"] = 0  # (a file from before the volumes: the music was on or off)
    if isinstance(saved.get("keys"), dict):
        settings["keys"] = dict(saved["keys"])
    pack = saved.get("texture_pack")
    if isinstance(pack, str) and os.path.exists(pack):  # (a pack deleted since: the game's own textures)
        settings["texture_pack"] = pack
    return settings


def load_tiles(path, found, default_tiles):
    """The tiles of the texture pack at path (None: the game's own, default_tiles), looked up among
    the packs found. Returns (tiles, message, path): a pack that can't be read gives the game's own
    tiles, a message for the settings and None."""
    if path is None:
        return default_tiles, "", None
    info = next((p for p in found if p.path == path), None)
    try:
        if info is None:
            listed = packs.find_packs([os.path.dirname(path)], [path] if path.endswith(".jar") else [])
            info = next((p for p in listed if p.path == path), None)
        if info is None:
            raise packs.PackError("no block textures")
        tiles, missing = packs.load_pack(info, default_tiles)
    except Exception as e:  # whatever is in the file, the game goes on with its own textures
        print(f"Texture pack {path} unreadable: {e!r}", file=sys.stderr)
        return default_tiles, fit_text(f"Pack unreadable: {e}", 56, keep="start"), None
    if missing:
        print(f"Texture pack {info.name}: {len(missing)} textures missing, the game's own drawn instead: "
              + ", ".join(missing), file=sys.stderr)
    return tiles, "", path


def next_pack(current, found, step):
    """The texture pack after (step 1) or before (step -1) the current one: None (the game's own
    textures), then the packs found, round and round. Paths."""
    choices = [None] + [p.path for p in found]
    i = choices.index(current) if current in choices else 0
    return choices[(i + step) % len(choices)]


def fit_text(text, n, keep="end"):
    """The text cut to n characters at most, with "..." where it was cut: keeping its end (paths)
    or its start (names)."""
    if len(text) <= n:
        return text
    return "..." + text[len(text) - n + 3:] if keep == "end" else text[:n - 3] + "..."


def mix(a, b, t):
    return tuple(float(x + (y - x) * t) for x, y in zip(a, b))


def scale(color, k):
    return tuple(float(c * k) for c in color)


def smoothstep(lo, hi, x):
    t = min(max((x - lo) / (hi - lo), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def environment(time_of_day):
    """Light and sky for a time of day (0 = sunrise, 0.25 = noon, 0.5 = sunset, 0.75 = midnight),
    as values for Renderer.set_environment, and how much it is day (0-1)."""
    angle = time_of_day * 2 * math.pi
    sun_height = math.sin(angle)
    day = smoothstep(-0.2, 0.25, sun_height)
    low_sun = math.exp(-(sun_height / 0.18) ** 2)  # 1 at sunrise and sunset
    zenith = mix(NIGHT_ZENITH, DAY_ZENITH, day)
    horizon = mix(mix(NIGHT_HORIZON, DAY_HORIZON, day), SUNSET, 0.8 * low_sun)
    sun = np.array([math.cos(angle), sun_height, SUN_TILT])
    sun /= np.linalg.norm(sun)
    # Direct light from the sun by day, from the moon by night, and none while either is at the horizon
    if sun_height >= 0:
        light_dir = sun
        color = mix(SUNSET_LIGHT, NOON_LIGHT, smoothstep(0.0, 0.45, sun_height))
        light = scale(color, smoothstep(0.0, 0.1, sun_height))
    else:
        light_dir = -sun
        light = scale(MOON_LIGHT, smoothstep(0.0, 0.1, -sun_height))
    sky_light = mix(mix(NIGHT_SKY_LIGHT, DAY_SKY_LIGHT, day), SUNSET_SKY_LIGHT, 0.35 * low_sun * day)
    return {
        "light_dir": tuple(float(c) for c in light_dir), "light_color": light, "sky_light": sky_light,
        "zenith": zenith, "horizon": horizon, "sun_dir": tuple(float(c) for c in sun),
        "sun_glow": scale(SUN_GLOW, day * (0.35 + 0.65 * low_sun)),
        "night": 1.0 - smoothstep(-0.35, -0.05, sun_height), "cloud_cover": CLOUD_COVER,
    }, day


class App:
    def __init__(self, headless=False):
        # The terrain is built by a background thread: let Python switch between the threads often,
        # so the game's own frame never waits long for its turn
        sys.setswitchinterval(0.001)
        if sys.platform == "win32" and not headless:
            # Use the screen's real pixels: on a high-DPI screen, Windows would otherwise draw the
            # window at a lower resolution and stretch it, blurred. (Before any window is made.)
            try:
                ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))  # per monitor, v2
            except (AttributeError, OSError):
                pass
        # Create our OpenGL context before Pyxel's, so Pyxel's context stays the current one.
        # The renderer switches to ours only while it draws.
        ctx = moderngl.create_standalone_context()
        # Pyxel's frame rate can't change once its window is open, so it is set very high and run()
        # paces the frames itself: a new frame rate setting then applies right away.
        # (capture_sec=0: no screen recording, whose buffer would be sized for 1000 frames per second)
        pyxel.init(BASE_WIDTH, BASE_HEIGHT, title="PyCraft", fps=1000, quit_key=pyxel.KEY_NONE,
                   capture_sec=0, headless=headless)
        pyxel.mouse(False)  # the UI draws its own pointer, at its own scale
        self.headless = headless
        self.ui = Ui()

        self.default_tiles = tiles = build_tiles()
        icon_colors = self.set_icons(tiles)
        pyxel.images[1].cls(0)
        pyxel.images[1].text(0, 0, "PYCRAFT", 7)  # drawn scaled up on the title screen
        self.init_sounds()

        data_dir = pyxel.user_data_dir("PyCraft", "PyCraft GPU")
        self.pack_dirs = packs.pack_dirs(data_dir)
        self.has_pillow = importlib.util.find_spec("PIL") is not None
        self.packs = self.find_packs()
        self.pack_message = ""  # shown under the settings: a pack that couldn't be read
        self.pack_to_apply = False  # a pack chosen in the settings, applied on the next update
        self.save_path = os.path.join(data_dir, SAVE_FILE)
        self.settings_path = os.path.join(data_dir, "settings.json")
        self.settings = self.load_settings()
        self.controls = Controls(self.settings["keys"])
        self.settings["keys"] = self.controls.to_settings()
        self.save_data = None
        self.world = None
        if os.path.exists(self.save_path):
            try:
                self.world, self.save_data = World.load(self.save_path)
            except (OSError, ValueError, KeyError):
                self.world = None  # unreadable save: start a new world instead
        self.world_is_fresh = self.world is None
        if self.world is None:
            self.world = World(seed=random.randrange(1 << 30))

        self.spawn = self.world.find_spawn()
        self.player = Player(*self.spawn)
        # The title screen looks around from above the spawn, or where the saved game left off
        self.title_spot = self.save_data["player"][:3].tolist() if self.save_data else self.spawn
        # Palette: the interface's 16 colors, 48 for the icons, and 192 that adapt to the 3D view
        for i, color in enumerate(PALETTE):
            pyxel.colors[i] = color
        self.renderer = Renderer(ctx, self.world, tiles, BASE_WIDTH, BASE_HEIGHT,
                                 list(pyxel.colors)[:16] + icon_colors)
        self.new_simulation()
        self.palette_version = None
        self.use_palette()
        self.renderer.render_distance = self.settings["render_distance"]
        self.renderer.set_lod_quality(self.settings["lod_quality"])
        self.renderer.set_fancy(self.settings["fancy"])
        if self.settings["texture_pack"] is not None:
            self.pack_message = self.apply_pack(self.settings["texture_pack"])
        self.scaler = AutoScale()  # picks the 3D view's render scale with the "auto" setting
        self.set_resolution(*self.settings["resolution"])
        self.apply_render_scale()

        self.state = "title"
        self.settings_parent = "title"  # the menu the settings screen goes back to
        self.settings_tab = 0  # the tab of the settings screen that shows
        self.settings_note = ""  # what the last change did, shown in place of the explanation
        self.binding = None  # the action that waits for its new key
        self.dragging = None  # the row of the slider that follows the mouse
        self.menu_index = 0
        self.view_fov = float(self.settings["fov"])  # the field of view on screen (it glides to the zoom's)
        self.music_playing = False
        self.warp_to_button = False
        self.hotbar = list(DEFAULT_HOTBAR)
        self.selected = 0
        self.selected_time = 0.0  # play time when the chosen block last changed (its name shows a while)
        self.inventory_tab = 0
        self.inventory_page = 0
        self.target = None  # (block looked at, empty block in front of it)
        self.time_of_day = 0.05
        self.mouse_captured = False
        self.last_mouse = (pyxel.width // 2, pyxel.height // 2)
        self.show_help = True
        self.show_debug = False
        self.play_time = 0.0
        self.last_save = 0.0
        self.chat_text = ""  # the command line being typed
        self.message = ""  # short notice shown above the hotbar
        self.message_time = 0.0
        self.dt = 1 / self.settings["fps"]  # seconds since the last frame, measured by run()
        self.fps = 0.0
        self.start_time = self.last_draw = time.perf_counter()
        self.apply_sound()

    def run(self):
        """Like pyxel.run(update, draw), but with the frame rate from the settings."""
        next_frame = last_update = time.perf_counter()
        while True:
            now = time.perf_counter()
            self.dt = min(now - last_update, MAX_DT)
            last_update = now
            self.update()
            self.draw()
            self.frame_done(time.perf_counter() - now)
            next_frame += 1 / self.settings["fps"]
            now = time.perf_counter()
            if now > next_frame + MAX_DT:
                next_frame = now  # far behind (a slow frame): don't rush to catch up
            elif next_frame - now > 0.002:
                time.sleep(next_frame - now - 0.0015)  # sleep can wake up late: wait the last bit actively
            while time.perf_counter() < next_frame:
                pass
            pyxel.flip()

    # --- Settings ------------------------------------------------------------------------------

    def load_settings(self):
        """The saved settings, with the default for any that is missing or not valid."""
        try:
            with open(self.settings_path, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            saved = {}
        return parse_settings(saved)

    def save_settings(self):
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f)

    # --- Texture packs -------------------------------------------------------------------------

    def find_packs(self):
        """The texture packs on this computer (none without Pillow, which reads their PNGs)."""
        return packs.find_packs(self.pack_dirs, packs.minecraft_jars()) if self.has_pillow else []

    def set_icons(self, tiles):
        """Draw the block icons of these tiles into Pyxel's image bank 0; returns their 48 colors."""
        icon_colors, icons = icon_palette(tiles_to_atlas(tiles))
        bank = np.frombuffer(pyxel.images[0].data_ptr(), dtype=np.uint8, count=256 * 256).reshape(256, 256)
        bank[:icons.shape[0], :icons.shape[1]] = icons
        return icon_colors

    def apply_pack(self, path):
        """Draw the world and the icons with this texture pack (None: the game's own textures).
        Returns a message for the settings: "" when it went well. A pack that can't be read gives
        the game's own textures back, and its path is forgotten."""
        tiles, message, path = load_tiles(path, self.packs, self.default_tiles)
        self.renderer.set_tiles(tiles)
        self.renderer.palette.set_fixed(self.set_icons(tiles))
        self.settings["texture_pack"] = path
        return message

    def change_texture_pack(self, step):
        """Next / previous texture pack: applied on the next update, once "Loading textures..." shows."""
        if not self.packs and self.settings["texture_pack"] is None:
            return
        self.pack_to_apply = next_pack(self.settings["texture_pack"], self.packs, step)
        self.pack_message = "Loading textures..."

    def texture_pack_row(self):
        current = self.settings["texture_pack"]
        info = next((p for p in self.packs if p.path == current), None)
        name = "Default" if current is None else info.name if info else os.path.basename(current)
        if self.pack_message:
            explain = self.pack_message
        elif not self.has_pillow:
            explain = "Install Pillow to use texture packs"
        elif current is None:
            explain = "Packs go in " + fit_text(self.pack_dirs[0], 44)
        else:
            explain = info.description if info and info.description else "Minecraft-style texture pack"
        return ("Texture pack", fit_text(name, 19, keep="start"), self.change_texture_pack, fit_text(explain, 56))

    def set_resolution(self, width, height):
        if (pyxel.width, pyxel.height) != (width, height):
            pyxel.resize(width, height)
        self.renderer.resize(width, height)
        self.ui.set_screen_size(width, height, self.settings["ui_scale"])
        self.scaler.reset(height)  # the time a frame takes changes with its size
        # The screen's pixels move to a new buffer when its size changes
        self.screen = np.frombuffer(pyxel.screen.data_ptr(), dtype=np.uint8, count=width * height)
        self.screen = self.screen.reshape(height, width)
        self.last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

    def apply_render_scale(self):
        """The 3D view's size from the setting: a fixed share of the resolution, or the automatic one."""
        choice = self.settings["render_scale"]
        self.scaler.reset()
        self.renderer.set_render_scale(self.scaler.scale if choice == "auto" else choice)

    def frame_done(self, work):
        """A frame was made in `work` seconds (without the wait for the next one): with the automatic
        render scale, draw the 3D view smaller if frames are too slow, or bigger if they have time to spare."""
        if self.settings["render_scale"] != "auto" or self.state in ("loading", "generating"):
            return  # (while loading, the frames are slow building the world, not drawing it)
        scale = self.scaler.update(work, self.renderer.gpu_time, 1 / self.settings["fps"])
        self.renderer.set_render_scale(scale)

    def use_palette(self):
        """Give Pyxel the palette the renderer drew the last frame for (it adapts to the view)."""
        if self.renderer.palette.version != self.palette_version:
            pyxel.colors[:] = self.renderer.palette.colors
            self.palette_version = self.renderer.palette.version

    def mouse_on_chosen(self):
        """True if the mouse is on the chosen line of the settings (a change that moves the panel
        then puts the cursor back on it)."""
        x, y, w, h = self.setting_rects()[self.menu_index]
        return self.ui.mouse_in(x, y, w, h)

    def change_resolution(self, step):
        on_row = self.mouse_on_chosen()
        i = RESOLUTIONS.index(self.settings["resolution"])
        self.settings["resolution"] = RESOLUTIONS[(i + step) % len(RESOLUTIONS)]
        self.save_settings()
        self.set_resolution(*self.settings["resolution"])
        self.warp_to_button = on_row  # the row moved: put the cursor back on it next frame

    def change_ui_scale(self, step):
        """Auto, then every scale that leaves the menus room at this resolution."""
        on_row = self.mouse_on_chosen()
        choices = ["auto"] + list(range(1, Ui.max_scale(pyxel.height) + 1))
        current = self.settings["ui_scale"]
        i = choices.index(current) if current in choices else 0
        self.settings["ui_scale"] = choices[(i + step) % len(choices)]
        self.save_settings()
        self.ui.set_screen_size(pyxel.width, pyxel.height, self.settings["ui_scale"])
        self.warp_to_button = on_row

    def cycle(self, key, choices, step):
        """The next (or previous) of a setting's values."""
        i = choices.index(self.settings[key])
        self.settings[key] = choices[(i + step) % len(choices)]
        self.apply_setting(key)

    def nudge(self, key, step):
        """A setting on a scale, one step up or down."""
        low, high, by = RANGES[key]
        self.settings[key] = min(max(self.settings[key] + step * by, low), high)
        self.apply_setting(key)

    def slide(self, key, fraction):
        """A setting on a scale, put where the mouse holds its slider."""
        low, high, by = RANGES[key]
        value = low + round(min(max(fraction, 0.0), 1.0) * (high - low) / by) * by
        if value != self.settings[key]:
            self.settings[key] = value
            self.apply_setting(key)

    def apply_setting(self, key):
        """Make a setting that just changed take effect, and save the settings. (The field of view,
        the mouse and the game's own settings are read where they are used.)"""
        s = self.settings
        if key in ("render_scale", "fps"):  # (a new frame rate: the automatic scale starts again)
            self.apply_render_scale()
        elif key == "render_distance":
            self.renderer.render_distance = s[key]
        elif key == "lod_quality":
            self.renderer.set_lod_quality(s[key])
        elif key == "fancy":
            self.renderer.set_fancy(s[key])
        elif key in ("music_volume", "sound_volume"):
            self.apply_sound()
        self.save_settings()

    def reset_tab(self):
        """The settings of the tab shown go back to what they were at first."""
        keys = SETTING_TABS[TAB_NAMES[self.settings_tab]]
        if keys == ["keys"]:
            self.controls.reset()
            self.settings["keys"] = self.controls.to_settings()
            self.save_settings()
            return
        before = dict(self.settings)
        if "texture_pack" in keys and self.settings["texture_pack"] is not None:
            self.pack_to_apply, self.pack_message = None, "Loading textures..."  # (applied on the next update)
        keys = [key for key in keys if key != "texture_pack"]
        for key in keys:
            self.settings[key] = DEFAULT_SETTINGS[key]
        if (self.settings["resolution"], self.settings["ui_scale"]) != (before["resolution"], before["ui_scale"]):
            self.set_resolution(*self.settings["resolution"])
            self.warp_to_button = True
        for key in keys:
            if self.settings[key] != before[key]:
                self.apply_setting(key)

    def frames(self, seconds):
        """Number of frames lasting about this long at the current frame rate (for pyxel.btnp)."""
        return max(1, round(seconds * self.settings["fps"]))

    def open_settings(self):
        self.settings_parent = self.state
        self.settings_note = ""
        self.packs = self.find_packs()  # (a pack put in the folder while the game runs shows up)
        self.pack_message = ""
        self.set_state("settings")

    def close_settings(self):
        self.binding = self.dragging = None
        self.set_state(self.settings_parent)
        self.menu_index = [label for label, _ in self.menu_items()].index("Settings")

    # --- Sound ---------------------------------------------------------------------------------

    def init_sounds(self):
        pyxel.sounds[SND_BREAK].set("a1f1c1", "n", "654", "nnf", 4)
        pyxel.sounds[SND_PLACE].set("c2", "n", "5", "f", 6)
        pyxel.sounds[SND_JUMP].set("c2", "n", "2", "f", 3)
        pyxel.sounds[SND_STEP].set("f1", "n", "2", "f", 4)
        pyxel.sounds[SND_SPLASH].set("g2c2f1", "n", "543", "nnf", 7)
        pyxel.sounds[SND_CLICK].set("c3", "p", "4", "f", 6)
        self.music = pyxel.gen_bgm(2, 0, 0, 1234)

    def sfx(self, sound):
        pyxel.play(SFX_CHANNEL, sound)

    def apply_sound(self):
        """The volumes of the settings: the music's three channels and the sound effects' one.
        The music stops at volume 0 and starts again from the top above it."""
        music = self.settings["music_volume"] / 100
        for ch in range(3):
            pyxel.channels[ch].gain = MUSIC_GAIN * music
        pyxel.channels[SFX_CHANNEL].gain = SOUND_GAIN * self.settings["sound_volume"] / 100
        if music > 0 and not self.music_playing:
            for ch, mml in enumerate(self.music[:3]):  # the 4th part is empty for this instrumentation
                pyxel.play(ch, mml, loop=True)
        elif music == 0 and self.music_playing:
            for ch in range(3):
                pyxel.stop(ch)
        self.music_playing = music > 0

    # --- Saving --------------------------------------------------------------------------------

    def snapshot(self):
        """Everything besides the blocks needed to continue the game later."""
        p = self.player
        return {
            "player": np.array(p.pos + [p.yaw, p.pitch, float(p.flying)]),
            "time_of_day": self.time_of_day,
            "hotbar": np.array(self.hotbar),
            "selected": self.selected,
            "ticks": self.sim.pending(),  # the machines' updates still to come
        }

    def new_simulation(self, pending=None):
        """The clock of the world's machines (sim.py), for the current world."""
        self.changes = []  # blocks the machines changed this frame: meshed together, once per section
        self.sim = Simulation(self.world, lambda x, y, z: self.changes.append((x, y, z)))
        redstone.install(self.sim)
        self.sim.every_tick.append(self.feel_plates)
        if pending is not None:
            self.sim.load_pending(pending)

    def feel_plates(self, sim):
        """Tell the simulation where the player stands, for the pressure plates."""
        x, y, z = (math.floor(c) for c in self.player.pos)
        cell = (x, y, z)
        before, sim.occupied = sim.occupied, {cell}
        if cell not in before and self.world.get(*cell) == STONE_PRESSURE_PLATE:
            sim.notify(cell)

    def save(self):
        tmp = self.save_path + ".tmp.npz"
        self.world.save(tmp, **self.snapshot())
        os.replace(tmp, self.save_path)  # replace the old save only once the new one is complete
        self.last_save = self.play_time
        self.world_is_fresh = False

    def start_game(self, new_world):
        if new_world:
            if not self.world_is_fresh:
                self.world = World(seed=random.randrange(1 << 30))
                self.renderer.set_world(self.world)
                self.spawn = self.world.find_spawn()
            self.player = Player(*self.spawn)
            self.hotbar, self.selected, self.time_of_day = list(DEFAULT_HOTBAR), 0, 0.05
            self.new_simulation()
            self.save()
        elif self.save_data is not None:
            data = self.save_data
            x, y, z, yaw, pitch, flying = data["player"].tolist()
            self.player = Player(x, y, z)
            self.player.yaw, self.player.pitch, self.player.flying = yaw, pitch, bool(flying)
            self.time_of_day = float(data["time_of_day"])
            self.hotbar = [int(b) for b in data["hotbar"]]
            self.selected = int(data["selected"])
            self.new_simulation(data.get("ticks"))
        self.save_data = None
        self.play_time = self.last_save = self.selected_time = 0.0
        self.show_help = self.settings["show_help"]
        self.set_state("loading")  # until the blocks around the player are ready

    # --- States --------------------------------------------------------------------------------

    def set_state(self, state):
        self.state = state
        self.menu_index = 0
        if state == "playing":
            self.capture_mouse()
        else:
            self.mouse_captured = False

    def capture_mouse(self):
        self.mouse_captured = True
        if not self.headless:
            pyxel.set_mouse_pos(pyxel.width / 2, pyxel.height / 2)
        self.last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

    def on_title(self):
        """True on the title screen and on the settings screen opened from it."""
        return self.state == "title" or (self.state == "settings" and self.settings_parent == "title")

    def camera(self):
        """(eye, forward) of the view: the player's, or a slow look around on the title screen."""
        if self.on_title():
            x, _, z = self.title_spot
            ground = max(self.world.surface_y(math.floor(x), math.floor(z)), SEA_LEVEL)
            angle = (time.perf_counter() - self.start_time) * 0.05
            return (x, ground + 30.0, z), (math.sin(angle), -0.2, math.cos(angle))
        return self.player.eye(), self.player.forward()

    def menu_items(self):
        """(label, action) pairs for the buttons of the title screen or of the pause menu."""
        if self.state == "title":
            items = []
            if not self.world_is_fresh:
                items.append(("Continue", lambda: self.start_game(new_world=False)))
            items.append(("New world", self.new_world_clicked))
            items.append(("Settings", self.open_settings))
            items.append(("Quit", pyxel.quit))
            return items
        if self.state == "paused":
            return [
                ("Resume", lambda: self.set_state("playing")),
                ("Settings", self.open_settings),
                ("Save and go to title", self.save_and_title),
                ("Save and quit", self.save_and_quit),
            ]
        return []

    def setting_rows(self):
        """The lines of the tab of the settings that shows. Each is (kind, name, value, change,
        explanation, fraction, slide): a "choice" has a few values and change takes a step (1 for
        the next, -1 for the previous); a "slider" is on a scale, at `fraction` of it, and slide
        puts it at another fraction; a "key" is an action and its key, and change is the action."""
        s = self.settings

        def choice(name, value, change, explain):
            return ("choice", name, value, change, explain, None, None)

        def pick(name, value, key, choices, explain):
            return choice(name, value, lambda step: self.cycle(key, choices, step), explain)

        def slider(name, value, key, explain):
            low, high, _ = RANGES[key]
            return ("slider", name, value, lambda step: self.nudge(key, step), explain,
                    (s[key] - low) / (high - low), lambda fraction: self.slide(key, fraction))

        def volume(key):
            return f"{s[key]}%" if s[key] else "Off"

        tab = TAB_NAMES[self.settings_tab]
        if tab == "Video":
            width, height = s["resolution"]
            ui_size = f"{self.ui.scale}x"
            render = f"{self.renderer.render_scale:.0%}"
            return [
                choice("Resolution", f"{width} x {height}", self.change_resolution,
                       "Pixels in the picture: fewer is faster"),
                choice("Interface size", f"Auto ({ui_size})" if s["ui_scale"] == "auto" else ui_size,
                       self.change_ui_scale, "Size of the menus, the text and the hotbar"),
                pick("Frame rate", f"{s['fps']} FPS", "fps", FRAME_RATES, "Frames per second the game aims for"),
                slider("Field of view", f"{s['fov']}", "fov", "How wide you see, in degrees: wider shows more, smaller"),
                pick("3D resolution", f"Auto ({render})" if s["render_scale"] == "auto" else render, "render_scale",
                     RENDER_SCALES, "Auto: the world is drawn smaller when it's slow"),
                pick("Render distance", f"{s['render_distance']} chunks", "render_distance", RENDER_DISTANCES,
                     "How far you can see: shorter is faster"),
                pick("LOD quality", s["lod_quality"].capitalize(), "lod_quality", LOD_QUALITY_NAMES,
                     "Detail of the faraway terrain"),
                pick("Graphics", "Fancy" if s["fancy"] else "Fast", "fancy", [False, True],
                     "Fancy: shadows and smooth edges"),
                choice(*self.texture_pack_row()),
            ]
        if tab == "Controls":
            return [
                slider("Mouse speed", f"{s['sensitivity']}%", "sensitivity",
                       "How far the view turns when the mouse moves"),
                pick("Invert mouse", "On" if s["invert_y"] else "Off", "invert_y", [False, True],
                     "On: pushing the mouse forward looks down"),
                slider("Arrow keys speed", f"{s['look_speed']}", "look_speed",
                       "Looking around with the arrow keys, in degrees per second"),
            ]
        if tab == "Keys":
            return [("key", LABELS[action], self.controls.name(action), action,
                     "ENTER or a click, then the new key or mouse button", None, None) for action, _, _ in ACTIONS]
        if tab == "Sound":
            return [
                slider("Music", volume("music_volume"), "music_volume", "Volume of the background music"),
                slider("Sound effects", volume("sound_volume"), "sound_volume",
                       "Volume of the steps, the splashes and the blocks"),
            ]
        minutes = s["autosave"]
        return [
            pick("Autosave", f"Every {minutes} min" if minutes else "Off", "autosave", AUTOSAVES,
                 "The game is also saved when you leave through the menu"),
            pick("Day length", f"{s['day_length']} minutes", "day_length", DAY_LENGTHS,
                 "How long a day and its night last"),
            pick("Controls help", "At the start" if s["show_help"] else "Hidden", "show_help", [False, True],
                 "The list of keys shown when a game starts (the help key brings it back)"),
            pick("Crosshair", s["crosshair"].capitalize(), "crosshair", CROSSHAIRS,
                 "The mark in the middle of the screen"),
        ]

    def new_world_clicked(self):
        if self.world_is_fresh:
            self.start_game(new_world=True)
        else:
            self.state = "generating"  # draw a message first, generate on the next update

    def save_and_title(self):
        self.save()
        self.save_data = self.snapshot()  # for "Continue"
        self.title_spot = list(self.player.pos)
        self.set_state("title")

    def save_and_quit(self):
        self.save()
        pyxel.quit()

    # --- Update --------------------------------------------------------------------------------

    def update(self):
        if self.pack_to_apply is not False:  # a texture pack chosen last frame, with its message shown
            path, self.pack_to_apply = self.pack_to_apply, False
            self.pack_message = self.apply_pack(path)
            self.save_settings()
        # Build the world around the camera a little every frame (much more while loading)
        budget = 0.06 if self.state == "loading" else 0.3 / self.settings["fps"]
        if self.state != "generating":
            self.renderer.update(self.camera()[0], budget)
        if self.state == "generating":
            self.world_is_fresh = False
            self.start_game(new_world=True)
        elif self.state == "loading":
            if self.renderer.progress(self.player.eye(), LOADING_RADIUS) >= 1:
                self.set_state("playing")
        elif self.state == "settings":
            self.update_settings()
        elif self.state in ("title", "paused"):
            if self.state == "paused" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.set_state("playing")
            else:
                self.update_menu()
        elif self.state == "inventory":
            self.update_inventory()
        elif self.state == "chat":
            self.update_chat()
        else:
            self.update_playing()

    def update_menu(self):
        """The buttons of the title screen and of the pause menu: the mouse, or the arrows and Enter."""
        items = self.menu_items()
        ui = self.ui
        hovered = self.button_at(ui.mouse_x, ui.mouse_y, len(items))
        if hovered is not None and (ui.mouse_x, ui.mouse_y) != self.last_mouse:
            self.menu_index = hovered
        self.last_mouse = (ui.mouse_x, ui.mouse_y)
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            self.menu_index = (self.menu_index + 1) % len(items)
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W):
            self.menu_index = (self.menu_index - 1) % len(items)
        chosen = None
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
            chosen = self.menu_index
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and hovered is not None:
            chosen = hovered
        if chosen is not None:
            self.sfx(SND_CLICK)
            items[chosen][1]()

    def update_settings(self):
        """The settings screen: tabs, then the lines of the tab shown, then "Defaults" and "Done".
        The mouse or the keyboard: Up/Down choose a line, Left/Right change it, Tab changes tab."""
        ui = self.ui
        if self.binding is not None:  # an action waits for its new key: the next one pressed is it
            if pyxel.btnp(pyxel.KEY_ESCAPE):
                self.binding = None
                return
            key = Controls.key_pressed()
            if key is not None:
                other = self.controls.bind(self.binding, key)
                self.settings_note = f"{LABELS[other]}: now {self.controls.name(other)}" if other else ""
                self.binding = None
                self.settings["keys"] = self.controls.to_settings()
                self.save_settings()
                self.sfx(SND_CLICK)
            return
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.close_settings()
            return
        rows, rects = self.setting_rows(), self.setting_rects()
        n = len(rows)  # the lines, then "Defaults" (n) and "Done" (n + 1)
        if self.warp_to_button:
            self.warp_to_button = False
            if not self.headless:
                x, y, w, h = rects[self.menu_index]
                pyxel.set_mouse_pos(*ui.to_screen(x + w // 2, y + h // 2))
        mouse = (ui.mouse_x, ui.mouse_y)
        if self.dragging is not None:  # a slider follows the mouse for as long as its button is down
            if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT) and self.dragging < n and rows[self.dragging][0] == "slider":
                x, _, w, _ = rects[self.dragging]
                sx, sw = Ui.slider_box(x, w)
                rows[self.dragging][6]((mouse[0] - sx - 2) / max(sw - 5, 1))
            else:
                self.dragging = None
            self.last_mouse = mouse
            return
        clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
        back = pyxel.btn(pyxel.KEY_SHIFT)
        turn = int(pyxel.btnp(pyxel.KEY_PAGEDOWN) or (pyxel.btnp(pyxel.KEY_TAB) and not back)) \
            - int(pyxel.btnp(pyxel.KEY_PAGEUP) or (pyxel.btnp(pyxel.KEY_TAB) and back))
        for i, rect in enumerate(self.tab_rects()):
            if clicked and ui.mouse_in(*rect):
                turn = i - self.settings_tab
        if turn:
            self.settings_tab = (self.settings_tab + turn) % len(TAB_NAMES)
            self.menu_index, self.settings_note = 0, ""
            self.sfx(SND_CLICK)
            return
        hovered = next((i for i, rect in enumerate(rects) if ui.mouse_in(*rect)), None)
        index = self.menu_index
        if hovered is not None and mouse != self.last_mouse:
            index = hovered
        self.last_mouse = mouse
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            index = (index + 1) % (n + 2)
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W):
            index = (index - 1) % (n + 2)
        step = int(pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D)) \
            - int(pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A))
        if step and index >= n:  # between the two buttons
            index, step = n + (1 if step > 0 else 0), 0
        elif step and rows[index][0] == "key":  # between the two columns of keys
            if 0 <= index + step * SETTING_ROWS < n:
                index += step * SETTING_ROWS
            step = 0
        if index != self.menu_index:
            self.menu_index, self.settings_note = index, ""
        chosen = index if step else None
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
            chosen, step = index, 1
        if clicked and hovered is not None:
            chosen, step = hovered, 1
            if hovered < n and rows[hovered][0] == "choice":
                x, _, w, _ = rects[hovered]
                vx, _ = Ui.value_box(x, w)
                if vx - 3 <= mouse[0] < vx + 8:  # on the "<" of the value: the previous one
                    step = -1
            elif hovered < n and rows[hovered][0] == "slider":
                self.menu_index, self.dragging = hovered, hovered  # (it moves from the next frame on)
                return
        if pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT) and hovered is not None and hovered < n \
                and rows[hovered][0] == "choice":
            chosen, step = hovered, -1
        if chosen is None:
            return
        self.sfx(SND_CLICK)
        self.menu_index = chosen
        if chosen == n:
            self.reset_tab()
            self.settings_note = "Back to the defaults"
        elif chosen == n + 1:
            self.close_settings()
        elif rows[chosen][0] == "key":
            self.binding, self.settings_note = rows[chosen][3], ""
        else:
            rows[chosen][3](step)

    def menu_top(self):
        """UI y of the first button of the title screen and the pause menu: below the middle."""
        return self.ui.height // 2 + 2

    def button_rect(self, i):
        return (self.ui.width - BUTTON_W) // 2, self.menu_top() + i * BUTTON_PITCH, BUTTON_W, BUTTON_H

    def button_at(self, mx, my, count):
        for i in range(count):
            x, y, w, h = self.button_rect(i)
            if x <= mx < x + w and y <= my < y + h:
                return i
        return None

    def settings_panel(self):
        """(x, y, w, h) of the settings panel: the tabs, the lines of the tab shown, a line that
        explains the chosen one, and two buttons."""
        return ((self.ui.width - SETTINGS_W) // 2, max(1, (self.ui.height - SETTINGS_H) // 2), SETTINGS_W,
                SETTINGS_H)

    def tab_rects(self):
        x, y, w, _ = self.settings_panel()
        tw = (w - 8) // len(TAB_NAMES)
        return [(x + 4 + i * tw, y + 4, tw, TAB_H) for i in range(len(TAB_NAMES))]

    def setting_rects(self):
        """(x, y, w, h) of each line of the tab shown, then of "Defaults" and of "Done". The keys
        go in two columns."""
        x, y, w, h = self.settings_panel()
        top = y + 4 + TAB_H + 4
        count = len(self.setting_rows())
        if TAB_NAMES[self.settings_tab] == "Keys":
            cw = (w - 12) // 2
            rects = [(x + 6 + (i // SETTING_ROWS) * (cw + 2), top + (i % SETTING_ROWS) * ROW_PITCH, cw - 2, ROW_H)
                     for i in range(count)]
        else:
            rects = [(x + 6, top + i * ROW_PITCH, w - 12, ROW_H) for i in range(count)]
        return rects + [(x + 6, y + h - 20, 84, BUTTON_H), (x + w - 90, y + h - 20, 84, BUTTON_H)]

    def inventory_layout(self):
        """The inventory shows as many rows of slots as fit above the hotbar, and puts the other
        blocks of the tab on more pages. Every tab has the same size, the one "All" needs. Returns
        the left and top of the slots, the rows per page, the number of pages and the page shown."""
        needed = math.ceil(len(PLACEABLE) / INVENTORY_COLUMNS)
        room = self.ui.height - INVENTORY_BELOW - 2
        rows = max(1, min(needed, (room - INVENTORY_HEADER - INVENTORY_FOOTER) // INVENTORY_SLOT))
        pages = max(1, math.ceil(math.ceil(len(self.inventory_blocks()) / INVENTORY_COLUMNS) / rows))
        x0 = (self.ui.width - INVENTORY_COLUMNS * INVENTORY_SLOT) // 2
        panel = INVENTORY_HEADER + rows * INVENTORY_SLOT + INVENTORY_FOOTER
        top = 2 + (room - panel) // 2 + INVENTORY_HEADER
        return x0, top, rows, pages, min(self.inventory_page, pages - 1)

    def inventory_blocks(self):
        return CATEGORIES[self.inventory_tab][1]

    def inventory_slots(self):
        """(block, x, y) of each slot on the page shown."""
        x0, top, rows, pages, page = self.inventory_layout()
        per_page = rows * INVENTORY_COLUMNS
        for i, block in enumerate(self.inventory_blocks()[page * per_page:(page + 1) * per_page]):
            yield block, x0 + (i % INVENTORY_COLUMNS) * INVENTORY_SLOT, top + (i // INVENTORY_COLUMNS) * INVENTORY_SLOT

    def inventory_tabs(self):
        """(x, y, w, h) of each tab, along the top of the inventory."""
        x0, top, _, _, _ = self.inventory_layout()
        x, rects = x0, []
        for name, _ in CATEGORIES:
            w = text_width(name) + 10
            rects.append((x, top - INVENTORY_HEADER + 4, w, 12))
            x += w + 2
        return rects

    def inventory_arrows(self):
        """(x, y, w, h) of the buttons that show the previous and the next page."""
        x0, top, rows, _, _ = self.inventory_layout()
        y = top + rows * INVENTORY_SLOT + 4
        return (x0, y, 11, 11), (x0 + 37, y, 11, 11)

    def hotbar_rects(self):
        """(x, y, w, h) of each slot of the hotbar, at the bottom of the screen."""
        n = len(self.hotbar)
        x0 = (self.ui.width - HOTBAR_SLOT * n) // 2
        y0 = self.ui.height - HOTBAR_SLOT - 4
        return [(x0 + i * HOTBAR_SLOT, y0, HOTBAR_SLOT, HOTBAR_SLOT) for i in range(n)]

    def update_inventory(self):
        if self.controls.pressed("inventory") or pyxel.btnp(pyxel.KEY_ESCAPE):
            self.set_state("playing")
            return
        ui = self.ui
        tab = self.inventory_tab
        if pyxel.btnp(pyxel.KEY_TAB):  # the next tab (SHIFT+TAB: the previous one)
            back = pyxel.btn(pyxel.KEY_SHIFT)
            tab = (tab + (-1 if back else 1)) % len(CATEGORIES)
        _, _, _, pages, page = self.inventory_layout()
        # With several pages, the wheel turns them (1-9 still choose the hotbar slot)
        self.update_hotbar_keys(wheel=pages == 1)
        forward = pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_PAGEDOWN)
        back = pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_PAGEUP)
        turn = int(forward) - int(back)
        if pages > 1:
            turn -= pyxel.mouse_wheel
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            for step, rect in zip((-1, 1), self.inventory_arrows()):
                if pages > 1 and ui.mouse_in(*rect):
                    turn = step
            for i, rect in enumerate(self.inventory_tabs()):
                if ui.mouse_in(*rect):
                    tab = i
            for i, rect in enumerate(self.hotbar_rects()):  # choose the slot the next block goes in
                if ui.mouse_in(*rect) and i != self.selected:
                    self.selected, self.selected_time = i, self.play_time
                    self.sfx(SND_CLICK)
            for block, x, y in self.inventory_slots():
                if ui.mouse_in(x, y, INVENTORY_SLOT, INVENTORY_SLOT):
                    self.hotbar[self.selected] = block
                    self.selected_time = self.play_time
                    self.sfx(SND_CLICK)
        if tab != self.inventory_tab:
            self.inventory_tab, self.inventory_page = tab, 0
            self.sfx(SND_CLICK)
            return
        new_page = min(max(page + turn, 0), pages - 1)
        if new_page != page:
            self.sfx(SND_CLICK)
        self.inventory_page = new_page

    def update_hotbar_keys(self, wheel=True):
        before = self.selected
        for i in range(len(self.hotbar)):
            if pyxel.btnp(pyxel.KEY_1 + i):
                self.selected = i
        if wheel and pyxel.mouse_wheel:
            self.selected = (self.selected - pyxel.mouse_wheel) % len(self.hotbar)
        if self.selected != before:
            self.selected_time = self.play_time

    def update_playing(self):
        dt = self.dt
        keys = self.controls
        self.play_time += dt
        self.time_of_day = (self.time_of_day + dt / (self.settings["day_length"] * 60)) % 1.0
        self.sim.update(dt)  # the machines: 20 ticks a second
        if self.sim.events:
            for event, pos in self.sim.events:
                if event == "explode":
                    self.sfx(SND_BREAK)
            self.sim.events.clear()
        if self.play_time - dt < HELP_SECONDS <= self.play_time:
            self.show_help = False  # hide the help once, after the first seconds of play
        autosave = self.settings["autosave"] * 60
        if autosave and self.play_time - self.last_save > autosave:
            self.save()
            self.notify("Game saved")

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.set_state("paused")
            return
        if keys.pressed("inventory"):
            self.set_state("inventory")
            return
        if keys.pressed("mouse"):
            if self.mouse_captured:
                self.mouse_captured = False
            else:
                self.capture_mouse()
        if keys.pressed("help"):
            self.show_help = not self.show_help
        if keys.pressed("info"):
            self.show_debug = not self.show_debug
        if keys.pressed("chat") or pyxel.btnp(pyxel.KEY_SLASH):
            self.chat_text = "/" if pyxel.btnp(pyxel.KEY_SLASH) else ""
            self.set_state("chat")
            return

        self.update_look()
        events = self.player.update(self.world, dt, keys)
        for event, sound in (("jump", SND_JUMP), ("step", SND_STEP), ("splash", SND_SPLASH)):
            if event in events:
                self.sfx(sound)
        self.update_hotbar_keys()

        # Break, place and pick blocks (hold the key to repeat)
        self.target = self.world.raycast(self.player.eye(), self.player.forward(), REACH)
        if not self.mouse_captured:
            if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                self.capture_mouse()
            return
        hold, repeat = self.frames(0.25), self.frames(0.13)
        if self.target and keys.pressed("pick"):
            self.pick_block(self.world.get(*self.target[0]))
        elif self.target and keys.pressed("break", hold=hold, repeat=repeat):
            x, y, z = self.target[0]
            if UNBREAKABLE[self.world.get(x, y, z)]:
                self.notify("Bedrock can't be broken")
            else:
                broken, state = self.world.get(x, y, z), self.world.get_state(x, y, z)
                self.sim.set_block(x, y, z, 0)
                if broken in redstone.SOURCES:  # what it powered goes dark
                    redstone.spread(self.sim, (x, y, z))
                    support = redstone.support_of(broken, state, (x, y, z))
                    if support is not None:
                        redstone.spread(self.sim, support)
                if PLANT[self.world.get(x, y + 1, z)]:  # the plant on it goes too
                    self.sim.set_block(x, y + 1, z, 0)
                self.sfx(SND_BREAK)
        elif self.target and keys.pressed("place", hold=hold, repeat=repeat) and right_click(
                self.world.get(*self.target[0]), keys.pressed("place")) == "act":
            x, y, z = self.target[0]
            act = {LEVER: redstone.toggle_lever, STONE_BUTTON: redstone.press_button,
                   REPEATER: redstone.cycle_repeater}[self.world.get(x, y, z)]
            act(self.sim, x, y, z)
            self.sfx(SND_CLICK)
        elif self.target and keys.pressed("place", hold=hold, repeat=repeat) and right_click(
                self.world.get(*self.target[0]), keys.pressed("place")) == "place":
            # Aiming at a plant puts the block in its place, like on the ground under it
            x, y, z = self.target[0] if PLANT[self.world.get(*self.target[0])] else self.target[1]
            block = turned(self.hotbar[self.selected], self.player.forward())  # a front faces the player
            here = self.world.get(x, y, z)
            free = self.world.inside(x, y, z) and (here in (0, WATER) or PLANT[here])
            if free and PLANT[block] and (here == WATER or not GROWS_ON[block, self.world.get(x, y - 1, z)]):
                grounds = [BLOCK_NAMES[g].lower() for g in np.flatnonzero(GROWS_ON[block])]
                self.notify("%s grows only on %s or %s" % (BLOCK_NAMES[block], ", ".join(grounds[:-1]), grounds[-1]))
            elif free and (not SOLID[block] or not self.player.overlaps(x, y, z)):  # plants and water: walk-through
                placed = placement(block, self.target[0], (x, y, z), self.player.forward(), self.world)
                if placed is None:
                    self.notify("%s needs a full block to go on" % BLOCK_NAMES[block])
                else:
                    self.sim.set_block(x, y, z, *placed)
                    self.sfx(SND_PLACE)

    def pick_block(self, block):
        """The block looked at becomes the chosen one: its hotbar slot if it has one, else it
        takes the chosen slot's place."""
        block = PICKS.get(int(block))
        if block is None:
            return
        if block in self.hotbar:
            self.selected = self.hotbar.index(block)
        else:
            self.hotbar[self.selected] = block
        self.selected_time = self.play_time
        self.sfx(SND_CLICK)

    def zooming(self):
        return self.state == "playing" and self.mouse_captured and self.controls.held("zoom")

    def update_look(self):
        s = self.settings
        keys_yaw = pyxel.btn(pyxel.KEY_LEFT) - pyxel.btn(pyxel.KEY_RIGHT)
        keys_pitch = pyxel.btn(pyxel.KEY_UP) - pyxel.btn(pyxel.KEY_DOWN)
        zoom = self.view_fov / s["fov"]  # zoomed in, the view turns as much slower as it is narrower
        self.player.look(keys_yaw * s["look_speed"] * zoom * self.dt, keys_pitch * s["look_speed"] * zoom * self.dt)
        if not self.mouse_captured:
            return
        w, h = pyxel.width, pyxel.height
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        dx, dy = mx - self.last_mouse[0], my - self.last_mouse[1]
        # (the same turn for the same hand movement at any resolution)
        sensitivity = MOUSE_SENSITIVITY * s["sensitivity"] / 100 * BASE_WIDTH / w * zoom
        self.player.look(-dx * sensitivity, (dy if s["invert_y"] else -dy) * sensitivity)
        # Only move the cursor back to the center when it gets near the edge: re-centering every
        # frame would throw away slow movements smaller than one Pyxel pixel.
        if not self.headless and (abs(mx - w / 2) > w / 4 or abs(my - h / 2) > h / 4):
            pyxel.set_mouse_pos(w / 2, h / 2)
            self.last_mouse = (w // 2, h // 2)
        else:
            self.last_mouse = (mx, my)

    # --- Chat ----------------------------------------------------------------------------------

    def update_chat(self):
        """The command line is open: the world and the clock go on, the player stands still."""
        self.play_time += self.dt
        self.time_of_day = (self.time_of_day + self.dt / (self.settings["day_length"] * 60)) % 1.0
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.set_state("playing")
            return
        if pyxel.btnp(pyxel.KEY_RETURN):
            text, self.chat_text = self.chat_text, ""
            self.set_state("playing")
            self.run_command(text)
            return
        hold, repeat = self.frames(0.4), self.frames(0.05)
        if pyxel.btnp(pyxel.KEY_BACKSPACE, hold=hold, repeat=repeat):
            self.chat_text = self.chat_text[:-1]
        for i in range(26):
            if pyxel.btnp(pyxel.KEY_A + i, hold=hold, repeat=repeat):
                self.chat_text += chr(ord("a") + i)
        for i in range(10):
            if pyxel.btnp(pyxel.KEY_0 + i, hold=hold, repeat=repeat):
                self.chat_text += str(i)
        for key, char in ((pyxel.KEY_SPACE, " "), (pyxel.KEY_MINUS, "-"), (pyxel.KEY_SLASH, "/"),
                          (pyxel.KEY_PERIOD, ".")):
            if pyxel.btnp(key, hold=hold, repeat=repeat):
                self.chat_text += char
        self.chat_text = self.chat_text[:64]

    def run_command(self, text):
        parts = text.strip().split()
        if not parts:
            return
        cmd = parts[0].lstrip("/").lower()
        if cmd == "tp":
            try:
                if len(parts) != 4:
                    raise ValueError
                coords = [float(v) if v != "~" else self.player.pos[i] for i, v in enumerate(parts[1:])]
            except ValueError:
                self.notify("Usage: /tp x y z")
                return
            self.player.pos = coords
            self.player.vel_y = 0.0
            self.notify(f"Teleported to {coords[0]:.0f} {coords[1]:.0f} {coords[2]:.0f}")
        elif cmd == "time" and len(parts) == 3 and parts[1] == "set":
            named = {"sunrise": 0.0, "day": 0.05, "noon": 0.25, "sunset": 0.5, "night": 0.6,
                     "midnight": 0.75}
            v = parts[2].lower()
            try:
                t = named[v] if v in named else float(v)
            except (KeyError, ValueError):
                self.notify("Usage: /time set day|noon|sunset|night|<0-1>")
                return
            self.time_of_day = (t / 24000 if t > 1 else t) % 1.0
            self.notify(f"Time set to {self.time_of_day * 24 % 24:.0f}:00")
        else:
            self.notify(f"Unknown command: {parts[0]}  (/tp x y z, /time set ...)")

    def draw_chat(self):
        ui = self.ui
        y = self.hotbar_rects()[0][1] - 19
        ui.text(4, y - 9, "ENTER run   ESC cancel   /tp x y z   /time set day|noon|night", TEXT_DIM, shadow=True)
        ui.glass(2, y - 1, ui.width - 4, 12, 0.85)
        ui.rect(2, y - 1, 2, 12, AMBER)
        cursor = "_" if self.play_time % 1.0 < 0.6 else ""
        ui.text(8, y + 2, "> " + self.chat_text + cursor, TEXT)

    def notify(self, text):
        self.message, self.message_time = text, self.play_time

    # --- Draw ----------------------------------------------------------------------------------

    def draw(self):
        if self.changes:  # what the machines and the player changed this frame: meshed once per section
            changes, self.changes = self.changes, []
            self.renderer.blocks_changed(list(dict.fromkeys(changes)))
        now = time.perf_counter()
        self.fps = self.fps * 0.9 + 0.1 / max(now - self.last_draw, 1e-6)
        self.last_draw = now
        ui = self.ui

        if self.state == "generating":
            pyxel.cls(BLACK)
            self.draw_message_box("Finding a place to start...")
            return

        self.draw_world()
        if self.state == "title":
            self.draw_title()
        elif self.state == "loading":
            done = self.renderer.progress(self.player.eye(), LOADING_RADIUS)
            self.draw_message_box(f"Generating terrain... {done * 100:.0f}%", done)
        elif self.state == "paused":
            ui.center_text(self.menu_top() - 26, "Game paused", TEXT, shadow=True, size=2)
            self.draw_menu()
        elif self.state == "settings":
            self.draw_settings()
        else:
            self.draw_hud()
            if self.state == "inventory":
                self.draw_inventory()
            elif self.state == "chat":
                self.draw_chat()
        if not self.mouse_captured and self.state != "loading":
            ui.cursor()

    def draw_message_box(self, text, progress=None):
        """A small panel in the middle of the screen with a line of text (and a progress bar)."""
        ui = self.ui
        w, h = max(text_width(text) + 28, 170), 24 if progress is None else 40
        x, y = (ui.width - w) // 2, (ui.height - h) // 2
        ui.panel(x, y, w, h)
        ui.center_text(y + 9, text, TEXT, shadow=True)
        if progress is not None:
            ui.bar(x + 10, y + 22, w - 20, 9, progress)

    def draw_world(self):
        eye, forward = self.camera()
        # The field of view of the settings; it glides to the zoom's while that key is held
        fov = ZOOM_FOV if self.zooming() else float(self.settings["fov"])
        glide = min(1.0, self.dt * 14) if self.state == "playing" and self.dt > 0 else 1.0
        self.view_fov += (fov - self.view_fov) * glide
        self.renderer.fov = self.view_fov
        if self.on_title():
            env, day = environment(0.12)
            target = None
        else:
            env, day = environment(self.time_of_day)
            target = self.target[0] if self.target and self.state == "playing" else None
        underwater = not self.on_title() and self.player.head_in_water(self.world)
        if underwater:
            fog = (scale(UNDERWATER_FOG, 0.38 + 0.62 * day), 0.0, 0.0, 9.0)
        else:
            end = self.renderer.view_distance
            fog = (env["horizon"], HAZE, FOG_START * end, end)
        self.renderer.set_environment(**env, fog_color=fog[0], fog_density=fog[1], fog_start=fog[2], fog_end=fog[3])
        self.renderer.underwater = underwater
        self.renderer.dim = DIM if self.state in ("loading", "paused", "settings", "inventory") else 1.0
        self.renderer.render(self.screen, eye, forward, target)
        self.use_palette()

    def draw_title(self):
        ui = self.ui
        cx, h = ui.width // 2, ui.height
        logo = 5 * h // BASE_HEIGHT  # the logo grows with the interface
        y = h * 48 // BASE_HEIGHT - 3 - 3 * (logo - 1)  # top of the scaled 28x6 logo
        x = cx - 14 * logo
        depth = max(1, logo // 4)  # the letters stand out of the screen: gold on top, amber then rust below
        for dx, dy, col in ((2 * depth, 3 * depth, BLACK), (0, 2 * depth, RUST), (0, depth, AMBER), (0, 0, GOLD)):
            pyxel.pal(7, col)
            ui.blt(x + dx, y + dy, 1, 0, 0, 28, 6, 0, scale=logo)
        pyxel.pal()
        ui.center_text(h // 2 - 22, "A Minecraft-like game made with Pyxel", CREAM, shadow=True)
        self.draw_menu()
        ui.text(3, h - 9, f"Seed {self.world.seed}", TEXT_DIM, shadow=True)
        hint = "Mouse or arrows to choose, ENTER to pick"
        ui.text(ui.width - text_width(hint) - 3, h - 9, hint, TEXT_DIM, shadow=True)

    def draw_menu(self):
        """The buttons of the title screen and the pause menu."""
        for i, (label, _) in enumerate(self.menu_items()):
            self.ui.button(*self.button_rect(i), label, hot=i == self.menu_index)

    def draw_settings(self):
        ui = self.ui
        x, y, w, h = self.settings_panel()
        ui.panel(x, y, w, h)
        ui.hline(x + 2, x + w - 3, y + 4 + TAB_H, IRON)  # the tabs stand on this line
        for i, (name, rect) in enumerate(zip(TAB_NAMES, self.tab_rects())):
            ui.tab(*rect, name, active=i == self.settings_tab, hot=ui.mouse_in(*rect))
        rows, rects = self.setting_rows(), self.setting_rects()
        n = len(rows)
        for i, (row, rect) in enumerate(zip(rows, rects)):
            kind, name, value = row[:3]
            hot = i == self.menu_index
            if kind == "slider":
                ui.slider_row(*rect, name, value, row[5], hot=hot or self.dragging == i)
            elif kind == "key":
                ui.key_row(*rect, name, value, hot=hot, listening=self.binding == row[3])
            else:
                ui.setting_row(*rect, name, value, hot=hot)
        # One line under the settings: what the last change did, or what the chosen line is for
        if self.binding is not None:
            note, col = "Press the new key or mouse button (ESC: keep the old one)", TEXT_HOT
        elif self.settings_note:
            note, col = self.settings_note, TEXT_HOT
        elif self.menu_index < n:
            note, col = rows[self.menu_index][4], TEXT_DIM
        elif self.menu_index == n:
            note, col = "This tab's settings as they were at first", TEXT_DIM
        else:
            note, col = "Back to the menu", TEXT_DIM
        ui.center_text(y + h - 30, note, col, cx=x + w // 2)
        ui.button(*rects[n], "Defaults", hot=self.menu_index == n)
        ui.button(*rects[n + 1], "Done", hot=self.menu_index == n + 1)
        if y + h + 12 <= ui.height:
            ui.center_text(y + h + 5, "TAB: next tab   LEFT/RIGHT or a click: change   ESC: back", TEXT_DIM,
                           shadow=True)

    def draw_hud(self):
        ui = self.ui
        self.draw_hotbar()
        if self.state == "inventory":
            return  # (the rest would show through the inventory)
        cx, cy = ui.width // 2, ui.height // 2
        # The crosshair, with a dark rim so it shows on bright blocks and on the sky too
        if self.settings["crosshair"] == "cross":
            ui.shade(cx - 5, cy - 1, 11, 3, 0.5)
            ui.shade(cx - 1, cy - 5, 3, 4, 0.5)
            ui.shade(cx - 1, cy + 2, 3, 4, 0.5)
            ui.hline(cx - 4, cx + 4, cy, WHITE)
            ui.vline(cx, cy - 4, cy + 4, WHITE)
        elif self.settings["crosshair"] == "dot":
            ui.shade(cx - 2, cy - 2, 4, 4, 0.5)
            ui.rect(cx - 1, cy - 1, 2, 2, WHITE)

        y0 = self.hotbar_rects()[0][1]
        if self.state == "playing":  # (the chat line would cover them)
            if self.play_time - self.selected_time < NAME_SECONDS:
                ui.center_text(y0 - 14, BLOCK_NAMES[self.hotbar[self.selected]], TEXT, shadow=True)
            if self.message and self.play_time - self.message_time < 2.5:
                ui.toast(y0 - 30, self.message)

        y = 2
        if self.show_debug:
            y = self.draw_debug(y) + 3
        if self.show_help:
            self.draw_help(y)
        if not self.mouse_captured and self.state == "playing":
            ui.toast(cy + 10, "Click to capture the mouse")

    def draw_hotbar(self):
        ui = self.ui
        rects = self.hotbar_rects()
        x0, y0, size, _ = rects[0]
        ui.rect(x0 - 3, y0 - 3, size * len(rects) + 6, size + 6, BLACK)
        ui.rect(x0 - 2, y0 - 2, size * len(rects) + 4, size + 4, COAL)
        ui.rectb(x0 - 2, y0 - 2, size * len(rects) + 4, size + 4, IRON)
        for i, (block, (x, y, w, h)) in enumerate(zip(self.hotbar, rects)):
            ui.slot(x, y, w)
            self.draw_icon(x + 3, y + 3, block)
            ui.text(x + 2, y + 2, str(i + 1), TEXT_HOT if i == self.selected else ASH, shadow=True)
        x, y, w, h = rects[self.selected]  # the chosen slot: a thick amber frame
        ui.rectb(x - 1, y - 1, w + 2, h + 2, GOLD)
        ui.rectb(x, y, w, h, AMBER)

    def draw_text_panel(self, y, lines):
        """(text, color) lines on a see-through panel at the left of the screen. Returns its bottom."""
        ui = self.ui
        w, h = max(text_width(s) for s, _ in lines) + 10, len(lines) * 8 + 5
        ui.glass(2, y, w, h)
        for i, (s, col) in enumerate(lines):
            ui.text(7, y + 3 + i * 8, s, col, shadow=True)
        return y + h

    def draw_debug(self, y):
        px, py, pz = self.player.pos
        hours = int((self.time_of_day * 24 + 6) % 24)
        biome = self.world.biome_at(math.floor(px), math.floor(pz))
        r = self.renderer
        sw, sh = r.scene_size
        gpu = "" if r.gpu_time is None else f"  GPU {r.gpu_time * 1000:.1f} ms"
        auto = ", auto" if self.settings["render_scale"] == "auto" else ""
        first, last = r.far.shown
        far = f"levels {first + 1}-{last + 1} of {r.far.levels()}" if last >= first else "not ready yet"
        lines = [f"FPS {self.fps:4.0f} / {self.settings['fps']}  {pyxel.width}x{pyxel.height}"
                 + ("" if self.settings["fancy"] else "  fast graphics"),
                 f"3D drawn at {sw}x{sh} ({r.render_scale:.0%}{auto}){gpu}",
                 f"XYZ {px:7.1f} {py:6.1f} {pz:7.1f}  Altitude {py - SEA_LEVEL - 1:5.0f}",
                 f"Biome {biome}",
                 f"Chunks {r.drawn} drawn / {len(r.chunks.meshes)} built",
                 f"Distant terrain: {far}",
                 f"Time {hours:02d}:00  Seed {self.world.seed}" + ("  FLY" if self.player.flying else "")]
        return self.draw_text_panel(y, [(line, TEXT) for line in lines])

    def help_lines(self):
        """The controls, with the keys they have now: (keys, what they do), in two columns."""
        key = self.controls.name
        move = [key(action) for action in ("forward", "left", "back", "right")]
        return [
            [("".join(move) if all(len(k) == 1 for k in move) else " ".join(move), "Move"),
             (key("jump"), "Jump, swim, fly up"), (key("down"), "Fly down"), (key("sprint"), "Sprint, fly fast"),
             (key("fly"), "Fly on/off"), (key("zoom"), "Zoom"), (key("inventory"), "All the blocks"),
             (key("chat"), "Chat, commands")],
            [(key("break"), "Break"), (key("place"), "Place, use"), (key("pick"), "Pick the block"),
             ("1-9, WHEEL", "Choose a block"), (key("mouse"), "Free the mouse"), (key("info"), "Info"),
             (key("help"), "Hide this help"), ("ESC", "Menu, settings")],
        ]

    def draw_help(self, y):
        """The controls in two columns: the keys in amber, what they do in white."""
        ui = self.ui
        lines = self.help_lines()
        columns = [(column, max(text_width(k) for k, _ in column) + 6, max(text_width(a) for _, a in column))
                   for column in lines]
        w = sum(kw + aw for _, kw, aw in columns) + 12 * (len(columns) - 1) + 10
        h = max(len(column) for column in lines) * 8 + 15
        ui.glass(2, y, w, h)
        ui.text(7, y + 3, "Controls", TEXT_HOT, shadow=True)
        x = 7
        for column, kw, aw in columns:
            for i, (keys, action) in enumerate(column):
                ui.text(x, y + 13 + i * 8, keys, AMBER, shadow=True)
                ui.text(x + kw, y + 13 + i * 8, action, TEXT, shadow=True)
            x += kw + aw + 12

    def draw_inventory(self):
        ui = self.ui
        size = INVENTORY_SLOT
        x0, top, rows, pages, page = self.inventory_layout()
        w = INVENTORY_COLUMNS * size + 10
        ui.panel(x0 - 5, top - INVENTORY_HEADER, w, INVENTORY_HEADER + rows * size + INVENTORY_FOOTER)
        ui.hline(x0 - 3, x0 + w - 8, top - 3, IRON)  # the tabs stand on this line
        for i, ((name, _), (x, y, tw, th)) in enumerate(zip(CATEGORIES, self.inventory_tabs())):
            ui.tab(x, y, tw, th, name, active=i == self.inventory_tab, hot=ui.mouse_in(x, y, tw, th))
        hovered = None
        chosen = self.hotbar[self.selected]
        for block, x, y in self.inventory_slots():
            over = ui.mouse_in(x, y, size, size)
            if over:
                hovered = block
            ui.slot(x, y, size, hot=over, chosen=block == chosen)  # (the chosen slot's block: framed in amber)
            self.draw_icon(x + 3, y + 3, block)
        bottom = top + rows * size
        if pages > 1:  # the page buttons, dimmed on the first and the last page
            for (x, y, bw, bh), label, usable in zip(self.inventory_arrows(), "<>", (page > 0, page < pages - 1)):
                ui.button(x, y, bw, bh, label, hot=usable and ui.mouse_in(x, y, bw, bh), enabled=usable)
            ui.center_text(bottom + 7, f"{page + 1}/{pages}", TEXT, cx=x0 + 24)
        hint = "Click: put in the chosen slot   TAB: next tab"
        ui.text(x0 + w - 10 - text_width(hint), bottom + 7, hint, TEXT_DIM)
        if hovered is not None:
            ui.tooltip(ui.mouse_x, ui.mouse_y, BLOCK_NAMES[hovered])

    def draw_icon(self, x, y, block):
        tile = BLOCK_TILES[block][0]
        u, v = (tile % ATLAS_TILES) * TILE, (tile // ATLAS_TILES) * TILE
        self.ui.blt(x, y, 0, u, v, TILE, TILE, 0)


def main():
    App().run()


if __name__ == "__main__":
    main()
