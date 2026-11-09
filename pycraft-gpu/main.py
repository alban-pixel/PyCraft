"""PyCraft GPU: a Minecraft-like game. OpenGL draws the 3D world, Pyxel shows it and runs everything else."""
import ctypes
import json
import math
import os
import random
import sys
import time

import moderngl
import numpy as np
import pyxel

from autoscale import AutoScale
from blocks import (ATLAS_TILES, BLOCK_NAMES, BLOCK_TILES, DEFAULT_HOTBAR, GROWS_ON, PLACEABLE, PLANT, SOLID, T_WATER,
                    TILE, TINT_ALPHA, UNBREAKABLE, WATER, build_atlas, turned)
from player import Player
from renderer import FIXED_COLORS, LOD_QUALITY_NAMES, Renderer, oklab_to_srgb, srgb_to_oklab
from terrain import SEA_LEVEL
from ui import BLACK, BLUE, GREY, LIGHT_BLUE, NAVY, TEXT, TEXT_DIM, TEXT_HOT, WHITE, Ui, text_width
from world import World

BASE_WIDTH, BASE_HEIGHT = 320, 180  # the menus and the mouse speed are designed for this size
RESOLUTIONS = [(320, 180), (384, 216), (480, 270), (640, 360), (800, 450), (960, 540), (1280, 720), (1600, 900),
               (1920, 1080), (2560, 1440)]
FRAME_RATES = [30, 60, 75, 120, 144, 165, 240]
RENDER_DISTANCES = [32, 64, 128, 256, 512]  # how far the world is seen, in chunks of 16 blocks
RENDER_SCALES = ["auto", 1.0, 0.75, 0.5]  # share of the resolution the 3D view is drawn at ("auto": follows the FPS)
DEFAULT_SETTINGS = {"resolution": (1280, 720), "fps": 60, "render_distance": 256, "lod_quality": "low",
                    "fancy": True, "music": True, "ui_scale": "auto", "render_scale": "auto"}
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
SETTINGS_W, ROW_H, ROW_PITCH = 232, 12, 13  # the settings panel and its rows
NAME_SECONDS = 3.0  # the chosen block's name shows this long above the hotbar
MOUSE_SENSITIVITY = 0.45  # degrees per pixel at 320x180
KEY_LOOK_SPEED = 120.0  # degrees per second with the arrow keys
DAY_SECONDS = 20 * 60  # one full day and night
AUTOSAVE_SECONDS = 120
HELP_SECONDS = 15

# Sky colors (RGB 0-1)
DAY_ZENITH, DAY_HORIZON = (0.38, 0.6, 1.0), (0.68, 0.84, 1.0)
NIGHT_ZENITH, NIGHT_HORIZON = (0.01, 0.01, 0.06), (0.06, 0.08, 0.18)
SUNSET = (1.0, 0.55, 0.3)
UNDERWATER_FOG = (0.08, 0.2, 0.5)
ICON_GREEN, ICON_BLUE = (0.5, 0.72, 0.33), (0.25, 0.45, 0.95)  # grass/leaves and water in the inventory
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

HELP = [  # (keys, what they do), in two columns
    [("WASD", "Move"), ("SPACE", "Jump, swim, fly up"), ("SHIFT", "Fly down"), ("CTRL", "Sprint, fly fast"),
     ("F", "Fly on/off"), ("E", "All the blocks"), ("T", "Chat, commands")],
    [("Left click", "Break"), ("Right click", "Place"), ("1-9, wheel", "Choose a block"), ("TAB", "Free the mouse"),
     ("F3", "Info"), ("H", "Hide this help"), ("ESC", "Menu")],
]

# The inventory's tabs. Plants and colored blocks are found by their names, the others listed here.
NATURE = {"Grass", "Dirt", "Stone", "Sand", "Water", "Snow", "Ice", "Gravel", "Red sand", "Podzol", "Cactus",
          "Deepslate", "Clay", "Mud", "Moss", "Granite", "Diorite", "Andesite", "Obsidian", "Coarse dirt", "Mycelium",
          "Farmland", "Packed ice", "Netherrack", "Soul sand", "End stone", "Brown mushroom block",
          "Red mushroom block", "Mushroom stem", "Pumpkin", "Melon"}
SPECIAL = {"Crafting table", "Furnace", "Dispenser", "Dropper", "Note block", "Jukebox", "TNT", "Piston",
           "Sticky piston", "Command block", "Glowstone", "Sea lantern", "Redstone lamp", "Jack o'lantern",
           "Monster spawner", "Slime block", "Sponge", "Wet sponge", "Bookshelf"}


def block_category(block):
    name = BLOCK_NAMES[block]
    if PLANT[block]:
        return "Plants"
    if name.lower().endswith(("wool", "terracotta", "stained glass")):
        return "Colors"
    if name in SPECIAL:
        return "Special"
    if name in NATURE or name.endswith((" ore", " log", " leaves")):
        return "Nature"
    return "Building"


CATEGORIES = [(tab, [b for b in PLACEABLE if tab == "All" or block_category(b) == tab])
              for tab in ("All", "Nature", "Building", "Colors", "Plants", "Special")]


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
    rgb = np.where((atlas[..., 3] == TINT_ALPHA)[..., None], rgb * tint, rgb)
    seen = atlas[..., 3] >= 128
    lab = srgb_to_oklab(rgb.reshape(-1, 3)).reshape(rgb.shape)
    points, weight = [], []
    for t in sorted({int(BLOCK_TILES[b][0]) for b in PLACEABLE}):  # the tiles drawn as icons
        ty, tx = divmod(t, ATLAS_TILES)
        cell = (slice(ty * TILE, (ty + 1) * TILE), slice(tx * TILE, (tx + 1) * TILE))
        texels = lab[cell][seen[cell]]
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

        atlas = build_atlas()
        icon_colors, icons = icon_palette(atlas)
        bank = np.frombuffer(pyxel.images[0].data_ptr(), dtype=np.uint8, count=256 * 256).reshape(256, 256)
        bank[:icons.shape[0], :icons.shape[1]] = icons
        pyxel.images[1].cls(0)
        pyxel.images[1].text(0, 0, "PYCRAFT", 7)  # drawn scaled up on the title screen
        self.init_sounds()

        data_dir = pyxel.user_data_dir("PyCraft", "PyCraft GPU")
        self.save_path = os.path.join(data_dir, SAVE_FILE)
        self.settings_path = os.path.join(data_dir, "settings.json")
        self.settings = self.load_settings()
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
        # Palette: Pyxel's 16 colors (HUD), 48 for the icons, and 192 that adapt to the 3D view
        self.renderer = Renderer(ctx, self.world, atlas, BASE_WIDTH, BASE_HEIGHT,
                                 list(pyxel.colors)[:16] + icon_colors)
        self.palette_version = None
        self.use_palette()
        self.renderer.render_distance = self.settings["render_distance"]
        self.renderer.set_lod_quality(self.settings["lod_quality"])
        self.renderer.set_fancy(self.settings["fancy"])
        self.scaler = AutoScale()  # picks the 3D view's render scale with the "auto" setting
        self.set_resolution(*self.settings["resolution"])
        self.apply_render_scale()

        self.state = "title"
        self.settings_parent = "title"  # the menu the settings screen goes back to
        self.menu_index = 0
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
        self.start_music()

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
        settings = dict(DEFAULT_SETTINGS)
        try:
            with open(self.settings_path, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            saved = {}
        if not isinstance(saved, dict):
            saved = {}
        resolution = saved.get("resolution")
        if isinstance(resolution, list) and tuple(resolution) in RESOLUTIONS:
            settings["resolution"] = tuple(resolution)
        if saved.get("fps") in FRAME_RATES:
            settings["fps"] = saved["fps"]
        if saved.get("render_distance") in RENDER_DISTANCES:
            settings["render_distance"] = saved["render_distance"]
        if saved.get("lod_quality") in LOD_QUALITY_NAMES:
            settings["lod_quality"] = saved["lod_quality"]
        for key in ("fancy", "music"):
            if isinstance(saved.get(key), bool):
                settings[key] = saved[key]
        ui_scale = saved.get("ui_scale")
        if ui_scale == "auto" or (type(ui_scale) is int and 1 <= ui_scale <= 8):
            settings["ui_scale"] = ui_scale
        if saved.get("render_scale") in RENDER_SCALES:
            settings["render_scale"] = saved["render_scale"]
        return settings

    def save_settings(self):
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f)

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

    def change_resolution(self, step):
        on_button = self.button_at(self.ui.mouse_x, self.ui.mouse_y, len(self.menu_items())) == self.menu_index
        i = RESOLUTIONS.index(self.settings["resolution"])
        self.settings["resolution"] = RESOLUTIONS[(i + step) % len(RESOLUTIONS)]
        self.save_settings()
        self.set_resolution(*self.settings["resolution"])
        self.warp_to_button = on_button  # the button moved: put the cursor back on it next frame

    def change_ui_scale(self, step):
        """Auto, then every scale that leaves the menus room at this resolution."""
        on_button = self.button_at(self.ui.mouse_x, self.ui.mouse_y, len(self.menu_items())) == self.menu_index
        choices = ["auto"] + list(range(1, Ui.max_scale(pyxel.height) + 1))
        current = self.settings["ui_scale"]
        i = choices.index(current) if current in choices else 0
        self.settings["ui_scale"] = choices[(i + step) % len(choices)]
        self.save_settings()
        self.ui.set_screen_size(pyxel.width, pyxel.height, self.settings["ui_scale"])
        self.warp_to_button = on_button

    def change_render_scale(self, step):
        i = RENDER_SCALES.index(self.settings["render_scale"])
        self.settings["render_scale"] = RENDER_SCALES[(i + step) % len(RENDER_SCALES)]
        self.save_settings()
        self.apply_render_scale()

    def change_fps(self, step):
        i = FRAME_RATES.index(self.settings["fps"])
        self.settings["fps"] = FRAME_RATES[(i + step) % len(FRAME_RATES)]
        self.save_settings()
        self.apply_render_scale()  # a new aim: the automatic scale starts again from full size

    def change_render_distance(self, step):
        i = RENDER_DISTANCES.index(self.settings["render_distance"])
        self.settings["render_distance"] = RENDER_DISTANCES[(i + step) % len(RENDER_DISTANCES)]
        self.renderer.render_distance = self.settings["render_distance"]
        self.save_settings()

    def change_lod_quality(self, step):
        i = LOD_QUALITY_NAMES.index(self.settings["lod_quality"])
        self.settings["lod_quality"] = LOD_QUALITY_NAMES[(i + step) % len(LOD_QUALITY_NAMES)]
        self.renderer.set_lod_quality(self.settings["lod_quality"])
        self.save_settings()

    def toggle_graphics(self):
        self.settings["fancy"] = not self.settings["fancy"]
        self.renderer.set_fancy(self.settings["fancy"])
        self.save_settings()

    def frames(self, seconds):
        """Number of frames lasting about this long at the current frame rate (for pyxel.btnp)."""
        return max(1, round(seconds * self.settings["fps"]))

    def open_settings(self):
        self.settings_parent = self.state
        self.set_state("settings")

    def close_settings(self):
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

    def start_music(self):
        if self.settings["music"]:
            for ch, mml in enumerate(self.music[:3]):  # the 4th part is empty for this instrumentation
                pyxel.channels[ch].gain = 0.07  # quieter than the sound effects (default 0.125)
                pyxel.play(ch, mml, loop=True)

    def toggle_music(self):
        self.settings["music"] = not self.settings["music"]
        self.save_settings()
        if self.settings["music"]:
            self.start_music()
        else:
            for ch in range(3):
                pyxel.stop(ch)

    # --- Saving --------------------------------------------------------------------------------

    def snapshot(self):
        """Everything besides the blocks needed to continue the game later."""
        p = self.player
        return {
            "player": np.array(p.pos + [p.yaw, p.pitch, float(p.flying)]),
            "time_of_day": self.time_of_day,
            "hotbar": np.array(self.hotbar),
            "selected": self.selected,
        }

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
            self.save()
        elif self.save_data is not None:
            data = self.save_data
            x, y, z, yaw, pitch, flying = data["player"].tolist()
            self.player = Player(x, y, z)
            self.player.yaw, self.player.pitch, self.player.flying = yaw, pitch, bool(flying)
            self.time_of_day = float(data["time_of_day"])
            self.hotbar = [int(b) for b in data["hotbar"]]
            self.selected = int(data["selected"])
        self.save_data = None
        self.play_time = self.last_save = self.selected_time = 0.0
        self.show_help = True
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
        """(label, action) pairs for the menu of the current state.

        On the settings screen, every action but "Done" changes a setting and takes a step:
        1 for the next value, -1 for the previous one.
        """
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
        if self.state == "settings":
            rows = [(f"{name}: {value}", change) for name, value, change, _ in self.setting_rows()]
            return rows + [("Done", lambda step: self.close_settings())]
        return []

    def setting_rows(self):
        """(name, value, change, explanation) of each setting; change takes a step: 1 for the next
        value, -1 for the previous one."""
        s = self.settings
        width, height = s["resolution"]
        ui_size = f"{self.ui.scale}x"
        render = f"{self.renderer.render_scale:.0%}"
        return [
            ("Resolution", f"{width} x {height}", self.change_resolution,
             "Pixels in the picture: fewer is faster"),
            ("Interface size", f"Auto ({ui_size})" if s["ui_scale"] == "auto" else ui_size, self.change_ui_scale,
             "Size of the menus, the text and the hotbar"),
            ("3D resolution", f"Auto ({render})" if s["render_scale"] == "auto" else render, self.change_render_scale,
             "Auto: the world is drawn smaller when it's slow"),
            ("Frame rate", f"{s['fps']} FPS", self.change_fps, "Frames per second the game aims for"),
            ("Render distance", f"{s['render_distance']} chunks", self.change_render_distance,
             "How far you can see: shorter is faster"),
            ("LOD quality", s["lod_quality"].capitalize(), self.change_lod_quality,
             "Detail of the faraway terrain"),
            ("Graphics", "Fancy" if s["fancy"] else "Fast", lambda step: self.toggle_graphics(),
             "Fancy: shadows and smooth edges"),
            ("Music", "On" if s["music"] else "Off", lambda step: self.toggle_music(), "Background music"),
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
        elif self.state in ("title", "paused", "settings"):
            if self.state == "paused" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.set_state("playing")
            elif self.state == "settings" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.close_settings()
            else:
                self.update_menu()
        elif self.state == "inventory":
            self.update_inventory()
        elif self.state == "chat":
            self.update_chat()
        else:
            self.update_playing()

    def update_menu(self):
        items = self.menu_items()
        ui = self.ui
        if self.warp_to_button:
            self.warp_to_button = False
            if not self.headless:
                x, y, w, h = self.button_rect(self.menu_index)
                pyxel.set_mouse_pos(*ui.to_screen(x + w // 2, y + h // 2))
        hovered = self.button_at(ui.mouse_x, ui.mouse_y, len(items))
        if hovered is not None and (ui.mouse_x, ui.mouse_y) != self.last_mouse:
            self.menu_index = hovered
        self.last_mouse = (ui.mouse_x, ui.mouse_y)
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            self.menu_index = (self.menu_index + 1) % len(items)
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W):
            self.menu_index = (self.menu_index - 1) % len(items)
        chosen, step = None, 1
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
            chosen = self.menu_index
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and hovered is not None:
            chosen = hovered
            if self.state == "settings" and hovered < len(items) - 1:
                x, _, w, _ = self.button_rect(hovered)
                vx, _ = Ui.value_box(x, w)
                if vx - 3 <= ui.mouse_x < vx + 8:  # on the "<" of the value: the previous one
                    step = -1
        if self.state == "settings":
            # Right / Left (or a right click) go to the next / previous value of a setting
            is_setting = self.menu_index < len(items) - 1  # all but "Done"
            if is_setting and (pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D)):
                chosen = self.menu_index
            if is_setting and (pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A)):
                chosen, step = self.menu_index, -1
            if pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT) and hovered is not None and hovered < len(items) - 1:
                chosen, step = hovered, -1
        if chosen is not None:
            self.sfx(SND_CLICK)
            if self.state == "settings":
                self.menu_index = chosen
                items[chosen][1](step)
            else:
                items[chosen][1]()

    def menu_top(self):
        """UI y of the first button of the title screen and the pause menu: below the middle."""
        return self.ui.height // 2 + 2

    def settings_panel(self):
        """(x, y, w, h) of the settings panel: a title, a row per setting, the explanation of the
        chosen one, and "Done"."""
        h = 23 + len(self.setting_rows()) * ROW_PITCH + 40
        return (self.ui.width - SETTINGS_W) // 2, max(1, (self.ui.height - h) // 2), SETTINGS_W, h

    def button_rect(self, i):
        if self.state == "settings":
            x, y, w, h = self.settings_panel()
            if i < len(self.setting_rows()):
                return x + 6, y + 23 + i * ROW_PITCH, w - 12, ROW_H
            return x + (w - 80) // 2, y + h - 21, 80, BUTTON_H  # "Done"
        return (self.ui.width - BUTTON_W) // 2, self.menu_top() + i * BUTTON_PITCH, BUTTON_W, BUTTON_H

    def button_at(self, mx, my, count):
        for i in range(count):
            x, y, w, h = self.button_rect(i)
            if x <= mx < x + w and y <= my < y + h:
                return i
        return None

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
        if pyxel.btnp(pyxel.KEY_E) or pyxel.btnp(pyxel.KEY_ESCAPE):
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
        self.play_time += dt
        self.time_of_day = (self.time_of_day + dt / DAY_SECONDS) % 1.0
        if self.play_time - dt < HELP_SECONDS <= self.play_time:
            self.show_help = False  # hide the help once, after the first seconds of play
        if self.play_time - self.last_save > AUTOSAVE_SECONDS:
            self.save()
            self.notify("Game saved")

        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.set_state("paused")
            return
        if pyxel.btnp(pyxel.KEY_E):
            self.set_state("inventory")
            return
        if pyxel.btnp(pyxel.KEY_TAB):
            if self.mouse_captured:
                self.mouse_captured = False
            else:
                self.capture_mouse()
        if pyxel.btnp(pyxel.KEY_H):
            self.show_help = not self.show_help
        if pyxel.btnp(pyxel.KEY_F3):
            self.show_debug = not self.show_debug
        if pyxel.btnp(pyxel.KEY_T) or pyxel.btnp(pyxel.KEY_SLASH):
            self.chat_text = "/" if pyxel.btnp(pyxel.KEY_SLASH) else ""
            self.set_state("chat")
            return

        self.update_look()
        events = self.player.update(self.world, dt)
        for event, sound in (("jump", SND_JUMP), ("step", SND_STEP), ("splash", SND_SPLASH)):
            if event in events:
                self.sfx(sound)
        self.update_hotbar_keys()

        # Break and place blocks (hold the button to repeat)
        self.target = self.world.raycast(self.player.eye(), self.player.forward(), REACH)
        if not self.mouse_captured:
            if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                self.capture_mouse()
            return
        hold, repeat = self.frames(0.25), self.frames(0.13)
        if self.target and pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT, hold=hold, repeat=repeat):
            x, y, z = self.target[0]
            if UNBREAKABLE[self.world.get(x, y, z)]:
                self.notify("Bedrock can't be broken")
            else:
                self.world.set(x, y, z, 0)
                self.renderer.block_changed(x, y, z)
                if PLANT[self.world.get(x, y + 1, z)]:  # the plant on it goes too
                    self.world.set(x, y + 1, z, 0)
                    self.renderer.block_changed(x, y + 1, z)
                self.sfx(SND_BREAK)
        elif self.target and pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT, hold=hold, repeat=repeat):
            # Aiming at a plant puts the block in its place, like on the ground under it
            x, y, z = self.target[0] if PLANT[self.world.get(*self.target[0])] else self.target[1]
            block = turned(self.hotbar[self.selected], self.player.forward())  # a front faces the player
            here = self.world.get(x, y, z)
            free = self.world.inside(x, y, z) and (here in (0, WATER) or PLANT[here])
            if free and PLANT[block] and (here == WATER or not GROWS_ON[block, self.world.get(x, y - 1, z)]):
                grounds = [BLOCK_NAMES[g].lower() for g in np.flatnonzero(GROWS_ON[block])]
                self.notify("%s grows only on %s or %s" % (BLOCK_NAMES[block], ", ".join(grounds[:-1]), grounds[-1]))
            elif free and (not SOLID[block] or not self.player.overlaps(x, y, z)):  # plants and water: walk-through
                self.world.set(x, y, z, block)
                self.renderer.block_changed(x, y, z)
                self.sfx(SND_PLACE)

    def update_look(self):
        keys_yaw = pyxel.btn(pyxel.KEY_LEFT) - pyxel.btn(pyxel.KEY_RIGHT)
        keys_pitch = pyxel.btn(pyxel.KEY_UP) - pyxel.btn(pyxel.KEY_DOWN)
        self.player.look(keys_yaw * KEY_LOOK_SPEED * self.dt, keys_pitch * KEY_LOOK_SPEED * self.dt)
        if not self.mouse_captured:
            return
        w, h = pyxel.width, pyxel.height
        mx, my = pyxel.mouse_x, pyxel.mouse_y
        dx, dy = mx - self.last_mouse[0], my - self.last_mouse[1]
        sensitivity = MOUSE_SENSITIVITY * BASE_WIDTH / w  # same turn for the same hand movement at any resolution
        self.player.look(-dx * sensitivity, -dy * sensitivity)
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
        self.time_of_day = (self.time_of_day + self.dt / DAY_SECONDS) % 1.0
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
        y = self.hotbar_rects()[0][1] - 18
        ui.text(4, y - 9, "ENTER run   ESC cancel   /tp x y z   /time set day|noon|night", TEXT_DIM, shadow=True)
        ui.shade(2, y - 1, ui.width - 4, 12, 0.75)
        ui.rectb(2, y - 1, ui.width - 4, 12, BLUE)
        cursor = "_" if self.play_time % 1.0 < 0.6 else ""
        ui.text(6, y + 2, "> " + self.chat_text + cursor, TEXT)

    def notify(self, text):
        self.message, self.message_time = text, self.play_time

    # --- Draw ----------------------------------------------------------------------------------

    def draw(self):
        now = time.perf_counter()
        self.fps = self.fps * 0.9 + 0.1 / max(now - self.last_draw, 1e-6)
        self.last_draw = now
        ui = self.ui

        if self.state == "generating":
            pyxel.cls(0)
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
        w, h = max(text_width(text) + 24, 160), 22 if progress is None else 36
        x, y = (ui.width - w) // 2, (ui.height - h) // 2
        ui.panel(x, y, w, h)
        ui.center_text(y + 8, text, TEXT, shadow=True)
        if progress is not None:
            ui.bar(x + 10, y + 20, w - 20, 8, progress)

    def draw_world(self):
        eye, forward = self.camera()
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
        shadow = logo * 3 // 5
        pyxel.pal(7, 0)
        ui.blt(x + shadow, y + shadow, 1, 0, 0, 28, 6, 0, scale=logo)
        pyxel.pal()
        ui.blt(x, y, 1, 0, 0, 28, 6, 0, scale=logo)
        ui.center_text(h // 2 - 22, "A Minecraft-like game made with Pyxel", TEXT, shadow=True)
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
        ui.panel(x, y, w, h, "Settings")
        rows = self.setting_rows()
        for i, (name, value, _, _) in enumerate(rows):
            ui.setting_row(*self.button_rect(i), name, value, hot=i == self.menu_index)
        explain = rows[self.menu_index][3] if self.menu_index < len(rows) else "Back to the menu"
        ui.center_text(y + 27 + len(rows) * ROW_PITCH, explain, TEXT_DIM, cx=x + w // 2)
        ui.button(*self.button_rect(len(rows)), "Done", hot=self.menu_index == len(rows))
        if y + h + 12 <= ui.height:
            ui.center_text(y + h + 5, "Click or LEFT/RIGHT to change, ESC to go back", TEXT_DIM, shadow=True)

    def draw_hud(self):
        ui = self.ui
        self.draw_hotbar()
        if self.state == "inventory":
            return  # (the rest would show through the inventory's see-through panel)
        cx, cy = ui.width // 2, ui.height // 2
        # Crosshair, outlined so it shows on bright blocks and on the sky too
        ui.shade(cx - 5, cy - 1, 11, 3, 0.5)
        ui.shade(cx - 1, cy - 5, 3, 4, 0.5)
        ui.shade(cx - 1, cy + 2, 3, 4, 0.5)
        ui.hline(cx - 4, cx + 4, cy, WHITE)
        ui.vline(cx, cy - 4, cy + 4, WHITE)

        y0 = self.hotbar_rects()[0][1]
        if self.state == "playing":  # (the chat line would cover them)
            if self.play_time - self.selected_time < NAME_SECONDS:
                ui.center_text(y0 - 13, BLOCK_NAMES[self.hotbar[self.selected]], TEXT, shadow=True)
            if self.message and self.play_time - self.message_time < 2.5:
                ui.toast(y0 - 29, self.message)

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
        x0, y0, s, _ = rects[0]
        ui.shade(x0 - 2, y0 - 2, s * len(rects) + 4, s + 4, 0.7)
        ui.rectb(x0 - 2, y0 - 2, s * len(rects) + 4, s + 4, BLACK)
        for i, (block, (x, y, w, h)) in enumerate(zip(self.hotbar, rects)):
            ui.rectb(x + 1, y + 1, w - 2, h - 2, NAVY)
            self.draw_icon(x + 3, y + 3, block)
            ui.text(x + 2, y + 2, str(i + 1), TEXT_HOT if i == self.selected else GREY, shadow=True)
        x, y, w, h = rects[self.selected]  # the chosen slot: a thick white frame
        ui.rectb(x - 1, y - 1, w + 2, h + 2, BLACK)
        ui.rectb(x, y, w, h, WHITE)
        ui.rectb(x + 1, y + 1, w - 2, h - 2, WHITE)

    def draw_text_panel(self, y, lines):
        """(text, color) lines on a see-through panel at the left of the screen. Returns its bottom."""
        ui = self.ui
        w, h = max(text_width(s) for s, _ in lines) + 9, len(lines) * 8 + 5
        ui.shade(2, y, w, h, 0.65)
        for i, (s, col) in enumerate(lines):
            ui.text(6, y + 3 + i * 8, s, col, shadow=True)
        return y + h

    def draw_debug(self, y):
        px, py, pz = self.player.pos
        hours = int((self.time_of_day * 24 + 6) % 24)
        biome = self.world.biome_at(math.floor(px), math.floor(pz))
        r = self.renderer
        sw, sh = r.scene_size
        gpu = "" if r.gpu_time is None else f"  GPU {r.gpu_time * 1000:.1f} ms"
        auto = ", auto" if self.settings["render_scale"] == "auto" else ""
        lines = [f"FPS {self.fps:4.0f} / {self.settings['fps']}  {pyxel.width}x{pyxel.height}"
                 + ("" if self.settings["fancy"] else "  fast graphics"),
                 f"3D drawn at {sw}x{sh} ({r.render_scale:.0%}{auto}){gpu}",
                 f"XYZ {px:7.1f} {py:6.1f} {pz:7.1f}  Altitude {py - SEA_LEVEL - 1:5.0f}",
                 f"Biome {biome}",
                 f"Chunks {r.drawn} drawn / {len(r.chunks.meshes)} built",
                 f"Time {hours:02d}:00  Seed {self.world.seed}" + ("  FLY" if self.player.flying else "")]
        return self.draw_text_panel(y, [(line, TEXT) for line in lines])

    def draw_help(self, y):
        """The controls in two columns: the keys in blue, what they do in white."""
        ui = self.ui
        columns = [(column, max(text_width(k) for k, _ in column) + 6, max(text_width(a) for _, a in column))
                   for column in HELP]
        w = sum(kw + aw for _, kw, aw in columns) + 12 * (len(columns) - 1) + 9
        h = max(len(column) for column in HELP) * 8 + 15
        ui.shade(2, y, w, h, 0.65)
        ui.text(6, y + 3, "Controls", TEXT_HOT, shadow=True)
        x = 6
        for column, kw, aw in columns:
            for i, (keys, action) in enumerate(column):
                ui.text(x, y + 13 + i * 8, keys, LIGHT_BLUE, shadow=True)
                ui.text(x + kw, y + 13 + i * 8, action, TEXT, shadow=True)
            x += kw + aw + 12

    def draw_inventory(self):
        ui = self.ui
        size = INVENTORY_SLOT
        x0, top, rows, pages, page = self.inventory_layout()
        w = INVENTORY_COLUMNS * size + 10
        ui.panel(x0 - 5, top - INVENTORY_HEADER, w, INVENTORY_HEADER + rows * size + INVENTORY_FOOTER)
        for i, ((name, _), (x, y, tw, th)) in enumerate(zip(CATEGORIES, self.inventory_tabs())):
            active = i == self.inventory_tab
            ui.rect(x, y, tw, th, BLUE if active else NAVY)
            ui.rectb(x, y, tw, th, WHITE if active else LIGHT_BLUE if ui.mouse_in(x, y, tw, th) else BLACK)
            ui.text(x + 5, y + 4, name, TEXT_HOT if active else TEXT, shadow=True)
        hovered = None
        chosen = self.hotbar[self.selected]
        for block, x, y in self.inventory_slots():
            over = ui.mouse_in(x, y, size, size)
            if over:
                hovered = block
                ui.rect(x + 1, y + 1, size - 2, size - 2, BLUE)
            else:
                ui.shade(x + 1, y + 1, size - 2, size - 2, 0.5)
            # The block in the chosen hotbar slot is framed in yellow
            ui.rectb(x + 1, y + 1, size - 2, size - 2, WHITE if over else TEXT_HOT if block == chosen else NAVY)
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


if __name__ == "__main__":
    App().run()
