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

from blocks import (ATLAS_TILES, BLOCK_NAMES, BLOCK_TILES, DEFAULT_HOTBAR, PLACEABLE, T_WATER, TILE, TINT_ALPHA,
                    UNBREAKABLE, WATER, build_atlas)
from player import Player
from renderer import FIXED_COLORS, LOD_QUALITY_NAMES, Renderer, oklab_to_srgb, srgb_to_oklab
from terrain import SEA_LEVEL
from ui import Ui
from world import World

BASE_WIDTH, BASE_HEIGHT = 320, 180  # the menus and the mouse speed are designed for this size
RESOLUTIONS = [(320, 180), (384, 216), (480, 270), (640, 360), (800, 450), (960, 540), (1280, 720), (1600, 900),
               (1920, 1080), (2560, 1440)]
FRAME_RATES = [30, 60, 75, 120, 144, 165, 240]
RENDER_DISTANCES = [32, 64, 128, 256, 512]  # how far the world is seen, in chunks of 16 blocks
DEFAULT_SETTINGS = {"resolution": (1280, 720), "fps": 60, "render_distance": 256, "lod_quality": "low",
                    "fancy": True, "music": True}
SAVE_FILE = "world2.npz"  # "world.npz" holds a world of the older, smaller version: left alone
LOADING_RADIUS = 2  # chunks around the player that must be ready before playing
HAZE = 1 / 4500  # share of light lost per block of distance: far mountains fade into the sky
FOG_START = 0.75  # the fog that hides the end of the world starts at this share of the view distance
MAX_DT = 1 / 30  # longest time step: slower frames slow the game down instead of making the player skip
REACH = 6.0
INVENTORY_COLUMNS = 13
INVENTORY_SLOT = TILE + 6  # side of a slot of the inventory, in UI pixels
INVENTORY_HEADER, INVENTORY_FOOTER = 14, 15  # room above the slots (instructions) and below (pages, name)
INVENTORY_BELOW = 34  # UI pixels kept free at the bottom of the screen: the hotbar and its block's name
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

HELP = [
    "WASD move  SPACE jump/swim  CTRL sprint  F fly (SPACE/SHIFT up/down)",
    "CTRL while flying: fly fast   E all blocks   1-9/wheel choose",
    "Left click break  Right click place  ESC menu  F3 info  H hide help  T chat",
]


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
        self.set_resolution(*self.settings["resolution"])

        self.state = "title"
        self.settings_parent = "title"  # the menu the settings screen goes back to
        self.menu_index = 0
        self.warp_to_button = False
        self.hotbar = list(DEFAULT_HOTBAR)
        self.selected = 0
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
        return settings

    def save_settings(self):
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f)

    def set_resolution(self, width, height):
        if (pyxel.width, pyxel.height) != (width, height):
            pyxel.resize(width, height)
        self.renderer.resize(width, height)
        self.ui.set_screen_size(width, height)
        # The screen's pixels move to a new buffer when its size changes
        self.screen = np.frombuffer(pyxel.screen.data_ptr(), dtype=np.uint8, count=width * height)
        self.screen = self.screen.reshape(height, width)
        self.last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

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

    def change_fps(self, step):
        i = FRAME_RATES.index(self.settings["fps"])
        self.settings["fps"] = FRAME_RATES[(i + step) % len(FRAME_RATES)]
        self.save_settings()

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
        self.play_time = self.last_save = 0.0
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
            width, height = self.settings["resolution"]
            return [
                (f"Resolution: {width} x {height}", self.change_resolution),
                (f"Frame rate: {self.settings['fps']} FPS", self.change_fps),
                (f"Render distance: {self.settings['render_distance']} chunks", self.change_render_distance),
                (f"LOD quality: {self.settings['lod_quality']}", self.change_lod_quality),
                ("Graphics: " + ("fancy" if self.settings["fancy"] else "fast"), lambda step: self.toggle_graphics()),
                ("Music: " + ("on" if self.settings["music"] else "off"), lambda step: self.toggle_music()),
                ("Done", lambda step: self.close_settings()),
            ]
        return []

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
        """UI y of the first button: below the middle, or higher up for a long menu."""
        count = len(self.menu_items())
        return self.ui.height // 2 + 2 if count <= 4 else (self.ui.height - count * 16) // 2 + 12

    def button_rect(self, i):
        w, h = 120, 13
        return (self.ui.width - w) // 2, self.menu_top() + i * 16, w, h

    def button_at(self, mx, my, count):
        for i in range(count):
            x, y, w, h = self.button_rect(i)
            if x <= mx < x + w and y <= my < y + h:
                return i
        return None

    def inventory_layout(self):
        """The inventory shows as many rows of slots as fit above the hotbar, and puts the other
        blocks on more pages. Returns the left and top of the slots, the rows per page, the number
        of pages and the page shown."""
        needed = math.ceil(len(PLACEABLE) / INVENTORY_COLUMNS)
        room = self.ui.height - INVENTORY_BELOW - 2
        rows = max(1, min(needed, (room - INVENTORY_HEADER - INVENTORY_FOOTER) // INVENTORY_SLOT))
        pages = math.ceil(needed / rows)
        x0 = (self.ui.width - INVENTORY_COLUMNS * INVENTORY_SLOT) // 2
        panel = INVENTORY_HEADER + rows * INVENTORY_SLOT + INVENTORY_FOOTER
        top = 2 + (room - panel) // 2 + INVENTORY_HEADER
        return x0, top, rows, pages, min(self.inventory_page, pages - 1)

    def inventory_slots(self):
        """(block, x, y) of each slot on the page shown."""
        x0, top, rows, pages, page = self.inventory_layout()
        per_page = rows * INVENTORY_COLUMNS
        for i, block in enumerate(PLACEABLE[page * per_page:(page + 1) * per_page]):
            yield block, x0 + (i % INVENTORY_COLUMNS) * INVENTORY_SLOT, top + (i // INVENTORY_COLUMNS) * INVENTORY_SLOT

    def inventory_arrows(self):
        """(x, y, w, h) of the buttons that show the previous and the next page."""
        x0, top, rows, _, _ = self.inventory_layout()
        y = top + rows * INVENTORY_SLOT + 3
        return (x0, y, 9, 9), (x0 + 33, y, 9, 9)

    def update_inventory(self):
        if pyxel.btnp(pyxel.KEY_E) or pyxel.btnp(pyxel.KEY_ESCAPE):
            self.set_state("playing")
            return
        _, _, _, pages, page = self.inventory_layout()
        # With several pages, the wheel turns them (1-9 still choose the hotbar slot)
        self.update_hotbar_keys(wheel=pages == 1)
        forward = pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_PAGEDOWN)
        back = pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_PAGEUP)
        turn = int(forward) - int(back)
        if pages > 1:
            turn -= pyxel.mouse_wheel
        mx, my = self.ui.mouse_x, self.ui.mouse_y
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            for step, (x, y, w, h) in zip((-1, 1), self.inventory_arrows()):
                if pages > 1 and x <= mx < x + w and y <= my < y + h:
                    turn = step
            for block, x, y in self.inventory_slots():
                if x <= mx < x + INVENTORY_SLOT and y <= my < y + INVENTORY_SLOT:
                    self.hotbar[self.selected] = block
                    self.sfx(SND_CLICK)
        new_page = min(max(page + turn, 0), pages - 1)
        if new_page != page:
            self.sfx(SND_CLICK)
        self.inventory_page = new_page

    def update_hotbar_keys(self, wheel=True):
        for i in range(len(self.hotbar)):
            if pyxel.btnp(pyxel.KEY_1 + i):
                self.selected = i
        if wheel and pyxel.mouse_wheel:
            self.selected = (self.selected - pyxel.mouse_wheel) % len(self.hotbar)

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
                self.sfx(SND_BREAK)
        elif self.target and pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT, hold=hold, repeat=repeat):
            x, y, z = self.target[1]
            block = self.hotbar[self.selected]
            free = self.world.inside(x, y, z) and self.world.get(x, y, z) in (0, WATER)
            if free and (block == WATER or not self.player.overlaps(x, y, z)):
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
        y = ui.height - TILE - 3 - 12
        pyxel.dither(0.5)
        ui.rect(0, y - 2, ui.width, 11, 0)
        pyxel.dither(1.0)
        cursor = "_" if self.play_time % 1.0 < 0.6 else ""
        ui.text(3, y, "> " + self.chat_text + cursor, 7)

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
            self.center_text(ui.height // 2 - 3, "Finding a place to start...", 7)
            return

        self.draw_world()
        if self.state == "title":
            self.draw_title()
        elif self.state == "loading":
            done = self.renderer.progress(self.player.eye(), LOADING_RADIUS)
            self.center_text(ui.height // 2 - 3, f"Generating terrain... {done * 100:.0f}%", 7)
        elif self.state in ("paused", "settings"):
            top = self.menu_top()
            self.center_text(top - 24, "Game paused" if self.state == "paused" else "Settings", 7)
            self.draw_menu()
            if self.state == "settings":
                self.center_text(top - 13, "Click or LEFT/RIGHT to change, ESC to go back", 13)
        else:
            self.draw_hud()
            if self.state == "inventory":
                self.draw_inventory()
            elif self.state == "chat":
                self.draw_chat()
        if not self.mouse_captured and self.state != "loading":
            ui.cursor()

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
        logo = 5 * h // BASE_HEIGHT  # the logo grows with the resolution
        y = h * 48 // BASE_HEIGHT - 3 - 3 * (logo - 1)  # top of the scaled 28x6 logo
        x = cx - 14 * logo
        shadow = logo * 3 // 5
        pyxel.pal(7, 0)
        ui.blt(x + shadow, y + shadow, 1, 0, 0, 28, 6, 0, scale=logo)
        pyxel.pal()
        ui.blt(x, y, 1, 0, 0, 28, 6, 0, scale=logo)
        self.center_text(h // 2 - 24, "A Minecraft-like game made with Pyxel", 7, shadow=True)
        self.draw_menu()
        self.shadow_text(2, h - 8, f"Seed {self.world.seed}", 13)

    def draw_menu(self):
        ui = self.ui
        items = self.menu_items()
        for i, (label, _) in enumerate(items):
            x, y, w, h = self.button_rect(i)
            selected = i == self.menu_index
            pyxel.dither(0.75)
            ui.rect(x, y, w, h, 5 if selected else 1)
            pyxel.dither(1.0)
            ui.rectb(x, y, w, h, 7 if selected else 13)
            if self.state == "settings" and selected and i < len(items) - 1:  # arrows on a setting
                ui.text(x + 4, y + 4, "<", 10)
                ui.text(x + w - 7, y + 4, ">", 10)
            self.center_text(y + 4, label, 10 if selected else 7)

    def draw_hud(self):
        ui = self.ui
        w, h = ui.width, ui.height
        cx, cy = w // 2, h // 2
        ui.hline(cx - 4, cx + 4, cy, 7)
        ui.vline(cx, cy - 4, cy + 4, 7)

        # Hotbar
        slot = TILE + 4
        x0 = (w - slot * len(self.hotbar)) // 2
        y0 = h - slot - 3
        pyxel.dither(0.5)
        ui.rect(x0 - 1, y0 - 1, slot * len(self.hotbar) + 2, slot + 2, 0)
        pyxel.dither(1.0)
        for i, block in enumerate(self.hotbar):
            self.draw_icon(x0 + i * slot + 2, y0 + 2, block)
            ui.rectb(x0 + i * slot, y0, slot, slot, 7 if i == self.selected else 13)
        self.center_text(y0 - 8, BLOCK_NAMES[self.hotbar[self.selected]], 7, shadow=True)
        if self.message and self.play_time - self.message_time < 2.5:
            self.center_text(y0 - 16, self.message, 10, shadow=True)

        y = 2
        if self.show_debug:
            px, py, pz = self.player.pos
            hours = int((self.time_of_day * 24 + 6) % 24)
            biome = self.world.biome_at(math.floor(px), math.floor(pz))
            chunks = self.renderer.chunks
            lines = [f"FPS {self.fps:4.0f} / {self.settings['fps']}  {pyxel.width}x{pyxel.height}"
                     + ("" if self.settings["fancy"] else "  fast graphics"),
                     f"XYZ {px:7.1f} {py:6.1f} {pz:7.1f}  Altitude {py - SEA_LEVEL - 1:5.0f}",
                     f"Biome {biome}",
                     f"Chunks {self.renderer.drawn} drawn / {len(chunks.meshes)} built",
                     f"Time {hours:02d}:00  Seed {self.world.seed}" + ("  FLY" if self.player.flying else "")]
            for line in lines:
                self.shadow_text(2, y, line, 7)
                y += 7
        if self.show_help:
            for line in HELP:
                self.shadow_text(2, y, line, 6)
                y += 7
        if not self.mouse_captured and self.state == "playing":
            self.center_text(cy + 10, "Click to capture the mouse", 10, shadow=True)

    def draw_inventory(self):
        ui = self.ui
        size = INVENTORY_SLOT
        x0, top, rows, pages, page = self.inventory_layout()
        w, h = INVENTORY_COLUMNS * size + 8, INVENTORY_HEADER + rows * size + INVENTORY_FOOTER
        ui.rect(x0 - 4, top - INVENTORY_HEADER, w, h, 1)
        ui.rectb(x0 - 4, top - INVENTORY_HEADER, w, h, 13)
        self.center_text(top - 10, "Click a block to put it in the selected slot", 7)
        hovered = None
        for block, x, y in self.inventory_slots():
            over = x <= ui.mouse_x < x + size and y <= ui.mouse_y < y + size
            if over:
                hovered = block
            ui.rectb(x, y, size, size, 7 if over else 5)
            self.draw_icon(x + 3, y + 3, block)
        bottom = top + rows * size
        if pages > 1:  # the page buttons, dimmed on the first and the last page
            for (x, y, bw, bh), label, usable in zip(self.inventory_arrows(), "<>", (page > 0, page < pages - 1)):
                over = usable and x <= ui.mouse_x < x + bw and y <= ui.mouse_y < y + bh
                ui.rectb(x, y, bw, bh, 7 if over else 13 if usable else 5)
                ui.text(x + 3, y + 2, label, 7 if usable else 5)
            number = f"{page + 1}/{pages}"
            ui.text(x0 + 9 + (24 - len(number) * 4) // 2 + 1, bottom + 5, number, 7)
        if hovered is not None:
            self.center_text(bottom + 5, BLOCK_NAMES[hovered], 10, shadow=True)

    def draw_icon(self, x, y, block):
        tile = BLOCK_TILES[block][0]
        u, v = (tile % ATLAS_TILES) * TILE, (tile // ATLAS_TILES) * TILE
        self.ui.blt(x, y, 0, u, v, TILE, TILE, 0)

    def center_text(self, y, s, col, shadow=False):
        x = (self.ui.width - len(s) * 4) // 2
        if shadow:
            self.shadow_text(x, y, s, col)
        else:
            self.ui.text(x, y, s, col)

    def shadow_text(self, x, y, s, col):
        self.ui.text(x + 1, y + 1, s, 0)
        self.ui.text(x, y, s, col)


if __name__ == "__main__":
    App().run()
