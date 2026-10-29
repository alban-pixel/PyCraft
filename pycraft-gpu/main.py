"""PyCraft GPU: a complete Minecraft-like game with survival, crafting, mobs, and GPU rendering."""
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

from blocks import (
    ATLAS_TILES, ATTACK_DAMAGE, BLOCK_COLORS, BLOCK_HARDNESS, BLOCK_NAMES,
    BLOCK_TILES, CRAFTING_TABLE, DEFAULT_HOTBAR, FOOD_HEAL, ITEM_COOKED_PORK,
    ITEM_DIAMOND_PICKAXE, ITEM_DIAMOND_SWORD, ITEM_IRON_PICKAXE, ITEM_IRON_SWORD,
    ITEM_RAW_PORK, ITEM_STICK, ITEM_STONE_PICKAXE, ITEM_STONE_SWORD, ITEM_WOOD_PICKAXE,
    ITEM_WOOD_SWORD, LOG, PICKAXES, PLACEABLE, PLANKS, TILE, UNBREAKABLE, WATER,
    build_atlas, get_item_name, get_item_tile,
)
import crafting
from clock import GameClock, TICK_DURATION, interpolate_position
from combat import CombatEngine, InvulnerabilityTracker
from entities import EntityManager
from generator import WorldPreset, parse_seed
from mining import MiningEngine
from physics import DDARaycast, SweptAABBPhysics, REACH_MINE, REACH_PLACE
from player import Player
from renderer import Renderer, look_at
from world import World

BASE_WIDTH, BASE_HEIGHT = 320, 180
RESOLUTIONS = [(320, 180), (384, 216), (480, 270), (640, 360), (800, 450), (960, 540), (1280, 720)]
FRAME_RATES = [30, 60, 75, 120, 144, 165, 240]
FOVS = [60, 70, 80, 90]
SENSITIVITIES = [0.12, 0.18, 0.25, 0.35, 0.50]
SENS_NAMES = {0.12: "Low", 0.18: "Medium", 0.25: "Normal", 0.35: "High", 0.50: "Very High"}
GUI_SCALES = ["Auto", "1x", "2x", "3x", "4x"]
DEFAULT_SETTINGS = {
    "resolution": (320, 180),
    "fps": 60,
    "fov": 70,
    "sensitivity": 0.25,
    "music": True,
    "fullscreen": False,
    "gui_scale": "Auto",
}
MAX_DT = 1 / 30
REACH = 5.5
KEY_LOOK_SPEED = 120.0
DAY_SECONDS = 8 * 60
AUTOSAVE_SECONDS = 120
HELP_SECONDS = 15

# Sky colors
DAY_ZENITH, DAY_HORIZON = (0.38, 0.6, 1.0), (0.68, 0.84, 1.0)
NIGHT_ZENITH, NIGHT_HORIZON = (0.01, 0.01, 0.06), (0.06, 0.08, 0.18)
SUNSET = (1.0, 0.55, 0.3)
UNDERWATER_FOG = (0.08, 0.2, 0.5)

# Sounds
(SND_BREAK, SND_PLACE, SND_JUMP, SND_STEP, SND_SPLASH,
 SND_CLICK, SND_HURT, SND_EAT, SND_SWORD) = range(9)
SFX_CHANNEL = 3

HELP = [
    "WASD/ZQSD move  SPACE jump/swim  CTRL sprint  F fly (Creative)",
    "F4 toggle Survival/Creative  F11 Fullscreen  Left click mine/attack",
    "Right click place/eat/craft  1-9/wheel slot  E inventory  ESC menu",
]


class Particle:
    __slots__ = ("x", "y", "z", "vx", "vy", "vz", "color", "age", "max_age")

    def __init__(self, x, y, z, color):
        self.x, self.y, self.z = x, y, z
        self.vx = random.uniform(-1.5, 1.5)
        self.vy = random.uniform(1.2, 3.2)
        self.vz = random.uniform(-1.5, 1.5)
        self.color = color
        self.age = 0.0
        self.max_age = random.uniform(0.3, 0.55)

    def update(self, dt):
        self.age += dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.z += self.vz * dt
        self.vy -= 18.0 * dt
        return self.age < self.max_age


class MouseGrabber:
    def __init__(self):
        self.is_mac = sys.platform == "darwin"
        self._cg = None
        self._dx = None
        self._dy = None
        if self.is_mac:
            try:
                self._cg = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
                self._cg.CGAssociateMouseAndMouseCursorPosition.argtypes = [ctypes.c_bool]
                self._cg.CGAssociateMouseAndMouseCursorPosition.restype = ctypes.c_int32
                self._dx = ctypes.c_int32()
                self._dy = ctypes.c_int32()
                self._cg.CGGetLastMouseDelta.argtypes = [ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32)]
                self._cg.CGGetLastMouseDelta.restype = None
            except Exception:
                self._cg = None
        self.captured = False
        self.last_pos = None

    def capture(self, x=None, y=None):
        self.captured = True
        if self._cg:
            self._cg.CGAssociateMouseAndMouseCursorPosition(False)
            self._cg.CGGetLastMouseDelta(ctypes.byref(self._dx), ctypes.byref(self._dy))
        if x is not None and y is not None:
            self.last_pos = (x, y)

    def release(self):
        self.captured = False
        if self._cg:
            self._cg.CGAssociateMouseAndMouseCursorPosition(True)
        self.last_pos = None

    def get_delta(self, mx, my, cx, cy):
        if not self.captured:
            return 0.0, 0.0
        if self._cg:
            self._cg.CGGetLastMouseDelta(ctypes.byref(self._dx), ctypes.byref(self._dy))
            return float(self._dx.value), float(self._dy.value)
        if self.last_pos is None:
            self.last_pos = (mx, my)
            return 0.0, 0.0
        dx = mx - self.last_pos[0]
        dy = my - self.last_pos[1]
        self.last_pos = (mx, my)
        if abs(dx) > cx or abs(dy) > cy:
            return 0.0, 0.0
        return float(dx), float(dy)


def make_palette():
    cube = [(r * 51) << 16 | (g * 51) << 8 | (b * 51) for r in range(6) for g in range(6) for b in range(6)]
    greys = [v << 16 | v << 8 | v for v in np.linspace(10, 245, 24).astype(int)]
    return list(pyxel.colors)[:16] + cube + greys


def atlas_to_indices(atlas):
    levels = np.rint(atlas[..., :3] / 51).astype(np.uint8)
    indices = 16 + levels[..., 0] * 36 + levels[..., 1] * 6 + levels[..., 2]
    indices[atlas[..., 3] < 128] = 0
    return indices


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def smoothstep(lo, hi, x):
    t = min(max((x - lo) / (hi - lo), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def sky_at(time_of_day):
    angle = time_of_day * 2 * math.pi
    sun_height = math.sin(angle)
    day = smoothstep(-0.2, 0.25, sun_height)
    zenith = mix(NIGHT_ZENITH, DAY_ZENITH, day)
    horizon = mix(NIGHT_HORIZON, DAY_HORIZON, day)
    horizon = mix(horizon, SUNSET, 0.8 * math.exp(-(sun_height / 0.18) ** 2))
    sun = np.array([math.cos(angle), sun_height, 0.25])
    sun_dir = tuple(float(c) for c in sun / np.linalg.norm(sun))
    return 0.38 + 0.62 * day, zenith, horizon, sun_dir


class App:
    def __init__(self, headless=False):
        ctx = moderngl.create_standalone_context()
        pyxel.init(BASE_WIDTH, BASE_HEIGHT, title="PyCraft", fps=1000, quit_key=pyxel.KEY_NONE,
                   headless=headless, capture_sec=0)
        pyxel.colors[:] = make_palette()
        self.headless = headless

        atlas = build_atlas()
        icons = atlas_to_indices(atlas)
        bank = np.frombuffer(pyxel.images[0].data_ptr(), dtype=np.uint8, count=256 * 256).reshape(256, 256)
        bank[:icons.shape[0], :icons.shape[1]] = icons
        pyxel.images[1].cls(0)
        pyxel.images[1].text(0, 0, "PYCRAFT", 7)
        self.text_scratch = pyxel.Image(1024, 64)
        self.init_sounds()

        data_dir = pyxel.user_data_dir("PyCraft", "PyCraft GPU")
        self.save_path = os.path.join(data_dir, "world.npz")
        self.settings_path = os.path.join(data_dir, "settings.json")
        self.settings = self.load_settings()

        self.fullscreen_enabled = bool(self.settings.get("fullscreen", False))
        if self.fullscreen_enabled and not headless:
            try:
                pyxel.fullscreen(True)
            except Exception:
                pass

        self.save_data = None
        self.world = None
        if os.path.exists(self.save_path):
            try:
                self.world, self.save_data = World.load(self.save_path)
            except (OSError, ValueError, KeyError):
                self.world = None
        self.world_is_fresh = self.world is None
        if self.world is None:
            self.world = World(seed=random.randrange(1 << 30))

        self.player = Player(*self.world.find_spawn(), mode="survival")
        self.renderer = Renderer(ctx, self.world, atlas, BASE_WIDTH, BASE_HEIGHT, fov=self.settings["fov"])
        self.screen = None
        self.set_resolution(*self.settings["resolution"])

        self.mouse_grabber = MouseGrabber()
        self.state = "title"
        self.settings_parent = "title"
        self.menu_index = 0
        self.warp_to_button = False

        # Inventory: 9 hotbar slots + 27 main inventory slots [item_id, count]
        self.hotbar = [[b, 64] for b in DEFAULT_HOTBAR]
        self.inventory = [[0, 0] for _ in range(27)]
        self.selected = 0
        self.target = None
        self.mining_target = None
        self.mining_time = 0.0

        # Crafting
        self.craft_grid = [[0, 0] for _ in range(9)]
        self.craft_size = 2  # 2x2 in inventory, 3x3 on table

        # Deterministic 20 Hz Clock, Presets & Combat
        self.clock = GameClock()
        self.current_preset = WorldPreset.STANDARD
        self.invulnerability = InvulnerabilityTracker()

        # Mobs & Fluids
        self.entity_mgr = EntityManager()
        self.fluid_timer = 0.0

        self.particles = []
        self.time_of_day = 0.05
        self.mouse_captured = False
        self.last_mouse = (pyxel.width // 2, pyxel.height // 2)
        self.show_help = True
        self.show_debug = False
        self.play_time = 0.0
        self.last_save = 0.0
        self.message = ""
        self.message_time = 0.0
        self.dt = 1 / self.settings["fps"]
        self.fps = 0.0
        self.last_draw = time.perf_counter()
        pyxel.mouse(True)
        self.start_music()

    def run(self):
        next_frame = last_update = time.perf_counter()
        try:
            while True:
                now = time.perf_counter()
                self.dt = min(now - last_update, MAX_DT)
                last_update = now
                self.update()
                self.draw()
                next_frame += 1 / self.settings["fps"]
                now = time.perf_counter()
                if now > next_frame + MAX_DT:
                    next_frame = now
                elif next_frame - now > 0.002:
                    time.sleep(next_frame - now - 0.0015)
                while time.perf_counter() < next_frame:
                    pass
                pyxel.flip()
        finally:
            self.release_mouse()

    # --- Settings ------------------------------------------------------------------------------

    def load_settings(self):
        settings = dict(DEFAULT_SETTINGS)
        try:
            with open(self.settings_path, encoding="utf-8") as f:
                saved = json.load(f)
        except (OSError, ValueError):
            saved = {}
        if isinstance(saved, dict):
            resolution = saved.get("resolution")
            if isinstance(resolution, list) and tuple(resolution) in RESOLUTIONS:
                settings["resolution"] = tuple(resolution)
            if saved.get("fps") in FRAME_RATES:
                settings["fps"] = saved["fps"]
            if saved.get("fov") in FOVS:
                settings["fov"] = saved["fov"]
            if saved.get("sensitivity") in SENSITIVITIES:
                settings["sensitivity"] = saved["sensitivity"]
            if isinstance(saved.get("music"), bool):
                settings["music"] = saved["music"]
            if isinstance(saved.get("fullscreen"), bool):
                settings["fullscreen"] = saved["fullscreen"]
            if saved.get("gui_scale") in GUI_SCALES:
                settings["gui_scale"] = saved["gui_scale"]
        return settings

    def save_settings(self):
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f)
        except OSError:
            pass

    def get_ui_scale(self):
        pref = self.settings.get("gui_scale", "Auto")
        if pref == "1x":
            return 1
        elif pref == "2x":
            return 2
        elif pref == "3x":
            return 3
        elif pref == "4x":
            return 4
        # "Auto" mode: scales proportionally to resolution
        return max(1, min(pyxel.width // 280, pyxel.height // 160))

    def toggle_fullscreen(self):
        self.fullscreen_enabled = not self.fullscreen_enabled
        self.settings["fullscreen"] = self.fullscreen_enabled
        self.save_settings()
        if not self.headless:
            try:
                pyxel.fullscreen(self.fullscreen_enabled)
            except Exception:
                pass
        self.notify("Fullscreen: " + ("ON" if self.fullscreen_enabled else "OFF"))

    def change_gui_scale(self, step):
        cur = self.settings.get("gui_scale", "Auto")
        if cur not in GUI_SCALES:
            cur = "Auto"
        i = GUI_SCALES.index(cur)
        self.settings["gui_scale"] = GUI_SCALES[(i + step) % len(GUI_SCALES)]
        self.save_settings()
        self.notify(f"GUI Scale: {self.settings['gui_scale']} ({self.get_ui_scale()}x)")

    def set_resolution(self, width, height):
        if (pyxel.width, pyxel.height) != (width, height):
            pyxel.resize(width, height)
        self.renderer.resize(width, height)
        self.screen = np.frombuffer(pyxel.screen.data_ptr(), dtype=np.uint8, count=width * height)
        self.screen = self.screen.reshape(height, width)
        self.last_mouse = (pyxel.mouse_x, pyxel.mouse_y)
        if hasattr(self, "text_scratch"):
            self.text_scratch = pyxel.Image(max(1024, width), 64)

    def change_resolution(self, step):
        on_button = self.button_at(pyxel.mouse_x, pyxel.mouse_y, len(self.menu_items())) == self.menu_index
        i = RESOLUTIONS.index(self.settings["resolution"])
        self.settings["resolution"] = RESOLUTIONS[(i + step) % len(RESOLUTIONS)]
        self.save_settings()
        self.set_resolution(*self.settings["resolution"])
        self.warp_to_button = on_button

    def change_fps(self, step):
        i = FRAME_RATES.index(self.settings["fps"])
        self.settings["fps"] = FRAME_RATES[(i + step) % len(FRAME_RATES)]
        self.save_settings()

    def change_fov(self, step):
        i = FOVS.index(self.settings["fov"])
        self.settings["fov"] = FOVS[(i + step) % len(FOVS)]
        self.save_settings()
        self.renderer.set_fov(self.settings["fov"])

    def change_sensitivity(self, step):
        sens = self.settings.get("sensitivity", 0.25)
        if sens not in SENSITIVITIES:
            sens = 0.25
        i = SENSITIVITIES.index(sens)
        self.settings["sensitivity"] = SENSITIVITIES[(i + step) % len(SENSITIVITIES)]
        self.save_settings()

    def frames(self, seconds):
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
        pyxel.sounds[SND_HURT].set("e2c2", "p", "75", "f", 5)
        pyxel.sounds[SND_EAT].set("f1a1c2", "n", "432", "f", 4)
        pyxel.sounds[SND_SWORD].set("g3d2", "n", "73", "f", 3)
        self.music = pyxel.gen_bgm(2, 0, 0, 1234)

    def sfx(self, sound):
        pyxel.play(SFX_CHANNEL, sound)

    def start_music(self):
        if self.settings["music"]:
            for ch, mml in enumerate(self.music[:3]):
                pyxel.channels[ch].gain = 0.07
                pyxel.play(ch, mml, loop=True)

    def toggle_music(self):
        self.settings["music"] = not self.settings["music"]
        self.save_settings()
        if self.settings["music"]:
            self.start_music()
        else:
            for ch in range(3):
                pyxel.stop(ch)

    # --- Inventory & Saving --------------------------------------------------------------------

    def add_to_inventory(self, item_id, count=1):
        if item_id == 0 or count <= 0:
            return
        # 1. Stack into hotbar
        for slot in self.hotbar:
            if slot[0] == item_id and slot[1] < 64:
                add = min(64 - slot[1], count)
                slot[1] += add
                count -= add
                if count <= 0:
                    return
        # 2. Stack into inventory
        for slot in self.inventory:
            if slot[0] == item_id and slot[1] < 64:
                add = min(64 - slot[1], count)
                slot[1] += add
                count -= add
                if count <= 0:
                    return
        # 3. First empty hotbar slot
        for slot in self.hotbar:
            if slot[0] == 0 or slot[1] <= 0:
                slot[0] = item_id
                slot[1] = min(64, count)
                count -= slot[1]
                if count <= 0:
                    return
        # 4. First empty inventory slot
        for slot in self.inventory:
            if slot[0] == 0 or slot[1] <= 0:
                slot[0] = item_id
                slot[1] = min(64, count)
                count -= slot[1]
                if count <= 0:
                    return

    def snapshot(self):
        p = self.player
        return {
            "player": np.array(p.pos + [p.yaw, p.pitch, float(p.flying), float(p.health)]),
            "time_of_day": self.time_of_day,
            "hotbar": np.array(self.hotbar),
            "selected": self.selected,
            "mode": self.player.mode,
        }

    def save(self):
        tmp = self.save_path + ".tmp.npz"
        self.world.save(tmp, **self.snapshot())
        os.replace(tmp, self.save_path)
        self.last_save = self.play_time
        self.world_is_fresh = False

    def start_game(self, new_world, mode="survival", preset=None, seed=None):
        if new_world:
            preset = preset or self.current_preset
            seed_val = random.randrange(1 << 30) if seed is None else seed
            self.world = World(seed=seed_val, preset=preset)
            self.renderer.set_world(self.world)
            self.player = Player(*self.world.find_spawn(), mode=mode)
            self.hotbar = [[b, 64] for b in DEFAULT_HOTBAR]
            self.inventory = [[0, 0] for _ in range(27)]
            self.selected, self.time_of_day = 0, 0.05
            self.clock.reset()
            self.save()
        elif self.save_data is not None:
            data = self.save_data
            p_arr = data["player"].tolist()
            x, y, z, yaw, pitch, flying = p_arr[:6]
            hp = p_arr[6] if len(p_arr) > 6 else 20.0
            saved_mode = str(data.get("mode", "survival"))
            self.player = Player(x, y, z, mode=saved_mode)
            self.player.yaw, self.player.pitch, self.player.flying = yaw, pitch, bool(flying)
            self.player.health = int(hp)
            self.time_of_day = float(data["time_of_day"])
            if "hotbar" in data:
                hb = data["hotbar"]
                if hb.ndim == 2:
                    self.hotbar = [[int(s[0]), int(s[1])] for s in hb]
                else:
                    self.hotbar = [[int(b), 64] for b in hb]
            self.selected = int(data.get("selected", 0))
        self.save_data = None
        self.play_time = self.last_save = 0.0
        self.show_help = True
        self.particles = []
        self.entity_mgr = EntityManager()
        self.set_state("playing")

    # --- States & Menus ------------------------------------------------------------------------

    def set_state(self, state):
        self.state = state
        self.menu_index = 0
        if state == "playing":
            self.capture_mouse()
        else:
            self.release_mouse()

    def capture_mouse(self):
        self.mouse_captured = True
        if not self.headless:
            pyxel.mouse(False)
            self.mouse_grabber.capture(pyxel.mouse_x, pyxel.mouse_y)
        self.last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

    def release_mouse(self):
        self.mouse_captured = False
        if not self.headless:
            self.mouse_grabber.release()
            pyxel.mouse(True)

    def on_title(self):
        return self.state == "title" or (self.state == "settings" and self.settings_parent == "title")

    def change_preset(self, step=1):
        i = WorldPreset.ALL.index(self.current_preset)
        self.current_preset = WorldPreset.ALL[(i + step) % len(WorldPreset.ALL)]

    def menu_items(self):
        if self.state == "title":
            items = []
            if not self.world_is_fresh:
                items.append(("Continue", lambda: self.start_game(new_world=False)))
            items.append(("New World (Survival)", lambda: self.start_game(new_world=True, mode="survival")))
            items.append(("New World (Creative)", lambda: self.start_game(new_world=True, mode="creative")))
            preset_name = self.current_preset.capitalize().replace("_", " ")
            items.append((f"Preset: {preset_name}", self.change_preset))
            items.append(("Settings", self.open_settings))
            items.append(("Quit", pyxel.quit))
            return items
        if self.state == "paused":
            return [
                ("Resume", lambda: self.set_state("playing")),
                (f"Mode: {self.player.mode.capitalize()}", self.toggle_player_mode),
                ("Settings", self.open_settings),
                ("Save and go to title", self.save_and_title),
                ("Save and quit", self.save_and_quit),
            ]
        if self.state == "settings":
            w, h = self.settings["resolution"]
            sens = self.settings.get("sensitivity", 0.25)
            sens_label = SENS_NAMES.get(sens, "Normal")
            fs_label = "ON" if self.fullscreen_enabled else "OFF"
            gui_label = self.settings.get("gui_scale", "Auto")
            return [
                (f"Resolution: {w} x {h}", self.change_resolution),
                (f"Fullscreen: {fs_label}", lambda step: self.toggle_fullscreen()),
                (f"GUI Scale: {gui_label}", self.change_gui_scale),
                (f"Frame rate: {self.settings['fps']} FPS", self.change_fps),
                (f"Field of view: {self.settings['fov']} deg", self.change_fov),
                (f"Mouse speed: {sens_label}", self.change_sensitivity),
                ("Music: " + ("on" if self.settings["music"] else "off"), lambda step: self.toggle_music()),
                ("Done", lambda step: self.close_settings()),
            ]
        return []

    def toggle_player_mode(self):
        self.player.toggle_mode()
        self.notify(f"Mode set to {self.player.mode.upper()}")

    def save_and_title(self):
        self.save()
        self.save_data = self.snapshot()
        self.set_state("title")

    def save_and_quit(self):
        self.release_mouse()
        self.save()
        pyxel.quit()

    # --- Update --------------------------------------------------------------------------------

    def update(self):
        if pyxel.btnp(pyxel.KEY_F11) or (pyxel.btn(pyxel.KEY_ALT) and pyxel.btnp(pyxel.KEY_RETURN)):
            self.toggle_fullscreen()

        if self.player.health <= 0 and self.state not in ("title", "game_over"):
            self.sfx(SND_HURT)
            self.set_state("game_over")
            return

        if self.state in ("title", "paused", "settings"):
            if self.state == "paused" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.set_state("playing")
            elif self.state == "settings" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.close_settings()
            else:
                self.update_menu()
        elif self.state in ("inventory", "crafting_table"):
            self.update_crafting_ui()
        elif self.state == "game_over":
            self.update_game_over()
        else:
            self.update_playing()

    def update_menu(self):
        items = self.menu_items()
        if self.warp_to_button:
            self.warp_to_button = False
            if not self.headless:
                x, y, w, h = self.button_rect(self.menu_index)
                pyxel.set_mouse_pos(x + w / 2, y + h / 2)
        hovered = self.button_at(pyxel.mouse_x, pyxel.mouse_y, len(items))
        if hovered is not None and (pyxel.mouse_x, pyxel.mouse_y) != self.last_mouse:
            self.menu_index = hovered
        self.last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            self.menu_index = (self.menu_index + 1) % len(items)
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W) or pyxel.btnp(pyxel.KEY_Z):
            self.menu_index = (self.menu_index - 1) % len(items)

        chosen, step = None, 1
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
            chosen = self.menu_index
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and hovered is not None:
            chosen = hovered

        if self.state in ("settings", "title"):
            has_steps = (self.state == "settings" and self.menu_index < len(items) - 1) or (
                self.state == "title" and "Preset:" in items[self.menu_index][0]
            )
            if has_steps and (pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D)):
                chosen = self.menu_index
            if has_steps and (pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A) or pyxel.btnp(pyxel.KEY_Q)):
                chosen, step = self.menu_index, -1
            if pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT) and hovered is not None:
                hovered_has_steps = (self.state == "settings" and hovered < len(items) - 1) or (
                    self.state == "title" and "Preset:" in items[hovered][0]
                )
                if hovered_has_steps:
                    chosen, step = hovered, -1

        if chosen is not None:
            self.sfx(SND_CLICK)
            self.menu_index = chosen
            cb = items[chosen][1]
            try:
                cb(step)
            except TypeError:
                cb()

    def button_rect(self, i):
        s = self.get_ui_scale()
        w, h = 140 * s, 13 * s
        items = self.menu_items()
        spacing = 3 * s
        total_h = len(items) * (h + spacing) - spacing
        y0 = (pyxel.height - total_h) // 2 + 8 * s
        return (pyxel.width - w) // 2, y0 + i * (h + spacing), w, h

    def button_at(self, mx, my, count):
        for i in range(count):
            x, y, w, h = self.button_rect(i)
            if x <= mx < x + w and y <= my < y + h:
                return i
        return None

    def respawn_player(self):
        self.player.respawn(self.world.find_spawn())
        self.set_state("playing")

    def game_over_button_rect(self):
        s = self.get_ui_scale()
        rw, rh = 100 * s, 16 * s
        rx, ry = (pyxel.width - rw) // 2, pyxel.height // 2 + 10 * s
        return rx, ry, rw, rh

    def update_game_over(self):
        rx, ry, rw, rh = self.game_over_button_rect()
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and rx <= pyxel.mouse_x < rx + rw and ry <= pyxel.mouse_y < ry + rh:
            self.sfx(SND_CLICK)
            self.respawn_player()
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and rx <= pyxel.mouse_x < rx + rw and ry <= pyxel.mouse_y < ry + rh:
            self.sfx(SND_CLICK)
            self.respawn_player()

    def update_playing(self):
        dt = self.dt
        self.play_time += dt
        self.time_of_day = (self.time_of_day + dt / DAY_SECONDS) % 1.0

        if self.play_time - dt < HELP_SECONDS <= self.play_time:
            self.show_help = False
        if self.play_time - self.last_save > AUTOSAVE_SECONDS:
            self.save()
            self.notify("Game saved")

        # Shortcuts
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.set_state("paused")
            return
        if pyxel.btnp(pyxel.KEY_E):
            self.craft_size = 2
            self.set_state("inventory")
            return
        if pyxel.btnp(pyxel.KEY_F4):
            self.toggle_player_mode()
        if pyxel.btnp(pyxel.KEY_TAB):
            if self.mouse_captured:
                self.release_mouse()
            else:
                self.capture_mouse()
        if pyxel.btnp(pyxel.KEY_H):
            self.show_help = not self.show_help
        if pyxel.btnp(pyxel.KEY_F3):
            self.show_debug = not self.show_debug

        self.update_look()
        self.update_hotbar_keys()

        # Deterministic 20 Hz fixed clock advancement
        def tick_logic(world_tick):
            self.time_of_day = self.clock.time_of_day
            self.invulnerability.tick()

            events = self.player.update(self.world, TICK_DURATION)
            for event in events:
                if event == "jump":
                    self.sfx(SND_JUMP)
                elif event == "step":
                    self.sfx(SND_STEP)
                elif event == "splash":
                    self.sfx(SND_SPLASH)
                elif event == "hurt":
                    self.sfx(SND_HURT)

            # Mobs update
            daylight = (math.sin(self.time_of_day * 2 * math.pi) + 1.0) * 0.5
            mob_events, mob_drops = self.entity_mgr.update(self.world, TICK_DURATION, self.player.pos, daylight)
            for me in mob_events:
                if me == "zombie_attack":
                    net_dmg = CombatEngine.compute_total_mitigated_damage(3.0, armor=0.0)
                    actual_dmg = self.invulnerability.attempt_damage(net_dmg)
                    if actual_dmg > 0 and self.player.take_damage(int(round(actual_dmg))):
                        self.sfx(SND_HURT)
                        self.notify("Zombie attacked you!")
            for drop_item, drop_pos in mob_drops:
                self.add_to_inventory(drop_item, 1)
                self.notify(f"Collected {get_item_name(drop_item)}")

        self.clock.advance(dt, tick_logic)

        # Update fluids & particles
        self.fluid_timer += dt
        if self.fluid_timer >= 0.15:
            self.fluid_timer = 0.0
            updated_chunks = self.world.tick_fluids()
            for cx, cz in updated_chunks:
                self.renderer.block_changed(cx * 16, cz * 16)

        if self.player.health <= 0:
            self.sfx(SND_HURT)
            self.set_state("game_over")
            return

        if self.particles:
            self.particles = [p for p in self.particles if p.update(dt)]

        # Interaction & Mining / Attack
        ray_res = DDARaycast.raycast(self.world, self.player.eye(), self.player.forward(), max_reach=REACH_MINE)
        self.target = (ray_res[0], ray_res[1]) if ray_res else None

        if not self.mouse_captured:
            if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
                self.capture_mouse()
            return

        # Check entity hit first
        hit_entity_info = self.entity_mgr.hit_target(self.player.eye(), self.player.forward(), reach=3.5)

        # Left Click: Attack mob OR Mine block
        if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT):
            self.player.swing()
            if hit_entity_info and pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT, hold=12, repeat=12):
                mob, _ = hit_entity_info
                held_item = self.hotbar[self.selected][0]
                dmg = ATTACK_DAMAGE.get(held_item, 1)
                mob.take_damage(dmg, knockback_src=self.player.pos)
                self.player.metabolism.add_exhaustion(0.10)
                self.sfx(SND_SWORD if held_item in ATTACK_DAMAGE else SND_HURT)
                return

            if self.target:
                target_pos = self.target[0]
                if self.mining_target != target_pos:
                    self.mining_target = target_pos
                    self.mining_time = 0.0

                block_id = self.world.get(*target_pos)
                if not UNBREAKABLE[block_id]:
                    if self.player.mode == "creative":
                        self.break_target_block(target_pos, block_id)
                    else:
                        slot = self.hotbar[self.selected]
                        held_item = slot[0]
                        p_tick = MiningEngine.compute_damage_per_tick(
                            held_item, block_id,
                            in_water=self.player.in_water,
                            on_ground=self.player.on_ground
                        )
                        self.mining_time += p_tick * (dt / TICK_DURATION)
                        if self.mining_time >= 1.0 or p_tick >= 1.0:
                            self.break_target_block(target_pos, block_id)
                            MiningEngine.apply_tool_wear(slot, block_id)
                            self.player.metabolism.add_exhaustion(0.005)
                            self.mining_target = None
                            self.mining_time = 0.0
            else:
                self.mining_target = None
                self.mining_time = 0.0
        else:
            self.mining_target = None
            self.mining_time = 0.0

        # Right Click: Eat food OR Interact with Crafting Table OR Place block
        if pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT, hold=15, repeat=10):
            slot = self.hotbar[self.selected]
            item_id = slot[0]

            # 1. Eat food
            if item_id in FOOD_HEAL and self.player.mode == "survival":
                if self.player.metabolism.eat(item_id):
                    self.player.health = self.player.metabolism.health
                    self.sfx(SND_EAT)
                    slot[1] -= 1
                    if slot[1] <= 0:
                        slot[0] = 0
                    self.notify(f"Ate {get_item_name(item_id)}")
                    return

            # 2. Right click on Crafting Table in world
            if self.target:
                tx, ty, tz = self.target[0]
                if self.world.get(tx, ty, tz) == CRAFTING_TABLE:
                    self.craft_size = 3
                    self.set_state("crafting_table")
                    return

            # 3. Place block
            if self.target and item_id in PLACEABLE and item_id != 0:
                if self.player.mode == "creative" or slot[1] > 0:
                    x, y, z = self.target[1]
                    free = self.world.inside(x, y, z) and self.world.get(x, y, z) in (0, WATER)
                    living_aabbs = [self.player_aabb()] + [e.aabb for e in self.entity_mgr.entities]
                    can_place = DDARaycast.can_place_block(self.world, (x, y, z), living_aabbs)
                    if free and (item_id == WATER or can_place):
                        self.world.set(x, y, z, item_id)
                        self.world.trigger_water(x, y, z)
                        self.renderer.block_changed(x, z)
                        self.sfx(SND_PLACE)
                        self.player.swing()
                        if self.player.mode == "survival":
                            slot[1] -= 1
                            if slot[1] <= 0:
                                slot[0] = 0

    def break_target_block(self, target_pos, block_id):
        x, y, z = target_pos
        self.world.set(x, y, z, 0)
        self.world.trigger_water(x, y, z)
        self.renderer.block_changed(x, z)
        self.sfx(SND_BREAK)
        col = BLOCK_COLORS.get(block_id, 7)
        for _ in range(12):
            self.particles.append(Particle(x + 0.5, y + 0.5, z + 0.5, col))
        if self.player.mode == "survival":
            self.add_to_inventory(block_id, 1)

    def update_look(self):
        keys_yaw = pyxel.btn(pyxel.KEY_LEFT) - pyxel.btn(pyxel.KEY_RIGHT)
        keys_pitch = pyxel.btn(pyxel.KEY_UP) - pyxel.btn(pyxel.KEY_DOWN)
        self.player.look(keys_yaw * KEY_LOOK_SPEED * self.dt, keys_pitch * KEY_LOOK_SPEED * self.dt)
        if not self.mouse_captured:
            return
        dx, dy = self.mouse_grabber.get_delta(
            pyxel.mouse_x, pyxel.mouse_y, pyxel.width // 2, pyxel.height // 2
        )
        if dx != 0.0 or dy != 0.0:
            sens = self.settings.get("sensitivity", 0.25)
            self.player.look(-dx * sens, -dy * sens)

    def update_hotbar_keys(self):
        for i in range(len(self.hotbar)):
            if pyxel.btnp(pyxel.KEY_1 + i):
                self.selected = i
        if pyxel.mouse_wheel:
            self.selected = (self.selected - pyxel.mouse_wheel) % len(self.hotbar)

    def notify(self, text):
        self.message, self.message_time = text, self.play_time

    # --- Crafting UI ---------------------------------------------------------------------------

    def craft_layout(self):
        s = self.get_ui_scale()
        w, h = pyxel.width, pyxel.height
        size = self.craft_size
        slot_s = 20 * s

        # Quick recipes on left
        qw, qh = 82 * s, 14 * s
        qx = 8 * s
        qy0 = 36 * s

        # Main Inventory (3 rows of 9) + Hotbar (1 row of 9) at bottom
        ix0 = (w - 9 * slot_s) // 2
        iy0 = h - 5 * slot_s - 8 * s

        # Crafting Grid in center above inventory
        gx0 = w // 2 - (size * slot_s) // 2 - 15 * s
        gy0 = max(qy0, (iy0 - size * slot_s) // 2)

        # Result slot
        rx = gx0 + size * slot_s + 20 * s
        ry = gy0 + (size * slot_s) // 2 - 10 * s
        rw, rh = slot_s + 2 * s, slot_s + 2 * s

        return {
            "s": s, "slot_s": slot_s,
            "gx0": gx0, "gy0": gy0,
            "rx": rx, "ry": ry, "rw": rw, "rh": rh,
            "ix0": ix0, "iy0": iy0,
            "qx": qx, "qy0": qy0, "qw": qw, "qh": qh,
        }

    def update_crafting_ui(self):
        if pyxel.btnp(pyxel.KEY_E) or pyxel.btnp(pyxel.KEY_ESCAPE):
            self.set_state("playing")
            return

        size = self.craft_size
        # Check recipe match
        res = crafting.check_craft(self.craft_grid, size, size)
        self.craft_result = list(res) if res else [0, 0]

        lay = self.craft_layout()
        rx, ry, rw, rh = lay["rx"], lay["ry"], lay["rw"], lay["rh"]

        # Click on result slot to craft
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            if rx <= pyxel.mouse_x < rx + rw and ry <= pyxel.mouse_y < ry + rh:
                if self.craft_result[0] != 0:
                    crafted = crafting.execute_craft(self.craft_grid, size, size)
                    if crafted:
                        self.add_to_inventory(crafted[0], crafted[1])
                        self.sfx(SND_CLICK)
                        self.notify(f"Crafted {get_item_name(crafted[0])} x{crafted[1]}")
                        return

            # Click quick recipe shortcuts on left side
            qx, qy0, qw, qh = lay["qx"], lay["qy0"], lay["qw"], lay["qh"]
            for q_idx, (r_name, r_ingr, r_out) in enumerate(self.quick_recipes()):
                qy = qy0 + q_idx * (qh + 2 * lay["s"])
                if qx <= pyxel.mouse_x < qx + qw and qy <= pyxel.mouse_y < qy + qh:
                    if self.has_ingredients(r_ingr):
                        self.consume_ingredients(r_ingr)
                        self.add_to_inventory(r_out[0], r_out[1])
                        self.sfx(SND_CLICK)
                        self.notify(f"Crafted {r_name}")
                        return

    def quick_recipes(self):
        recipes = [
            ("Planks x4", {LOG: 1}, (PLANKS, 4)),
            ("Sticks x4", {PLANKS: 2}, (ITEM_STICK, 4)),
            ("Crafting Table", {PLANKS: 4}, (CRAFTING_TABLE, 1)),
            ("Cooked Pork", {ITEM_RAW_PORK: 1}, (ITEM_COOKED_PORK, 1)),
        ]
        if self.craft_size == 3:
            recipes.extend([
                ("Wood Sword", {PLANKS: 2, ITEM_STICK: 1}, (ITEM_WOOD_SWORD, 1)),
                ("Wood Pickaxe", {PLANKS: 3, ITEM_STICK: 2}, (ITEM_WOOD_PICKAXE, 1)),
                ("Stone Sword", {3: 2, ITEM_STICK: 1}, (ITEM_STONE_SWORD, 1)),
                ("Stone Pickaxe", {3: 3, ITEM_STICK: 2}, (ITEM_STONE_PICKAXE, 1)),
                ("Iron Sword", {13: 2, ITEM_STICK: 1}, (ITEM_IRON_SWORD, 1)),
                ("Iron Pickaxe", {13: 3, ITEM_STICK: 2}, (ITEM_IRON_PICKAXE, 1)),
                ("Diamond Sword", {16: 2, ITEM_STICK: 1}, (ITEM_DIAMOND_SWORD, 1)),
                ("Diamond Pickaxe", {16: 3, ITEM_STICK: 2}, (ITEM_DIAMOND_PICKAXE, 1)),
            ])
        return recipes

    def has_ingredients(self, req_dict):
        all_slots = self.hotbar + self.inventory
        for item_id, needed in req_dict.items():
            avail = sum(s[1] for s in all_slots if s[0] == item_id)
            if avail < needed:
                return False
        return True

    def consume_ingredients(self, req_dict):
        all_slots = self.hotbar + self.inventory
        for item_id, needed in req_dict.items():
            for s in all_slots:
                if s[0] == item_id:
                    take = min(s[1], needed)
                    s[1] -= take
                    needed -= take
                    if s[1] <= 0:
                        s[0] = 0
                    if needed <= 0:
                        break

    # --- Draw ----------------------------------------------------------------------------------

    def draw(self):
        now = time.perf_counter()
        self.fps = self.fps * 0.9 + 0.1 / max(now - self.last_draw, 1e-6)
        self.last_draw = now

        self.draw_world()
        s = self.get_ui_scale()
        if self.state == "title":
            self.draw_title()
        elif self.state in ("paused", "settings"):
            self.dim_screen()
            title = "Settings" if self.state == "settings" else "Game paused"
            self.center_text(pyxel.height // 2 - 28 * s, title, 7, scale=s)
            self.draw_menu()
        elif self.state == "game_over":
            self.draw_game_over()
        elif self.state in ("inventory", "crafting_table"):
            self.draw_crafting_screen()
        else:
            self.draw_hud()

    def draw_world(self):
        if self.on_title():
            sx, _, sz = self.world.size
            angle = pyxel.frame_count * 0.002
            eye = (sx / 2 + math.cos(angle) * sx * 0.45, 52.0, sz / 2 + math.sin(angle) * sz * 0.45)
            forward = (sx / 2 - eye[0], 24 - eye[1], sz / 2 - eye[2])
            light, zenith, horizon, sun_dir = sky_at(0.12)
            target = None
        else:
            eye, forward = self.player.eye(), self.player.forward()
            light, zenith, horizon, sun_dir = sky_at(self.time_of_day)
            target = self.target[0] if self.target and self.state == "playing" else None

        if not self.on_title() and self.player.head_in_water(self.world):
            fog = (tuple(c * light for c in UNDERWATER_FOG), 0.0, 9.0)
        else:
            fog = (horizon, 40.0, 90.0)

        crack_stage = -1
        if self.mining_target and self.player.mode == "survival":
            block_id = self.world.get(*self.mining_target)
            hardness = BLOCK_HARDNESS.get(block_id, 1.0)
            crack_stage = min(3, max(0, int((self.mining_time / hardness) * 4)))

        self.renderer.set_environment(light, zenith, horizon, sun_dir, *fog)
        self.renderer.render(
            self.screen, eye, forward, target,
            entities=self.entity_mgr.entities if not self.on_title() else None,
            mining_target=self.mining_target if self.state == "playing" else None,
            crack_stage=crack_stage,
        )

        # 3D Break particles
        if self.particles and not self.on_title():
            vp = self.renderer.projection @ look_at(eye, forward)
            w, h = pyxel.width, pyxel.height
            for p in self.particles:
                pos = np.array([p.x, p.y, p.z, 1.0], dtype=np.float32)
                clip = vp @ pos
                cw = clip[3]
                if cw > 0.05:
                    ndc_x = clip[0] / cw
                    ndc_y = clip[1] / cw
                    if -1.0 <= ndc_x <= 1.0 and -1.0 <= ndc_y <= 1.0:
                        sx = int((ndc_x + 1.0) * 0.5 * w)
                        sy = int((1.0 - ndc_y) * 0.5 * h)
                        pyxel.rect(sx, sy, 2, 2, p.color)

    def draw_title(self):
        cx = pyxel.width // 2
        cy = pyxel.height // 2
        s = self.get_ui_scale()
        logo_scale = 5 * s
        pyxel.pal(7, 0)
        pyxel.blt(cx, cy - 50 * s + 3 * s, 1, 0, 0, 28, 6, colkey=0, scale=logo_scale)
        pyxel.pal()
        pyxel.blt(cx, cy - 50 * s, 1, 0, 0, 28, 6, colkey=0, scale=logo_scale)
        self.center_text(cy - 28 * s, "Voxel Sandbox & Survival", 7, shadow=True, scale=s)
        self.draw_menu()
        self.shadow_text(2 * s, pyxel.height - 8 * s, f"Seed {self.world.seed}", 13, scale=s)

    def draw_menu(self):
        s = self.get_ui_scale()
        items = self.menu_items()
        for i, (label, _) in enumerate(items):
            x, y, w, h = self.button_rect(i)
            selected = i == self.menu_index
            pyxel.dither(0.75)
            pyxel.rect(x, y, w, h, 5 if selected else 1)
            pyxel.dither(1.0)
            pyxel.rectb(x, y, w, h, 7 if selected else 13)
            if self.state == "settings" and selected and i < len(items) - 1:
                self.draw_text(x + 4 * s, y + (h - 6 * s) // 2, "<", 10, scale=s)
                self.draw_text(x + w - 7 * s, y + (h - 6 * s) // 2, ">", 10, scale=s)
            self.center_text(y + (h - 6 * s) // 2, label, 10 if selected else 7, scale=s)

    @staticmethod
    def dim_screen():
        pyxel.dither(0.5)
        pyxel.rect(0, 0, pyxel.width, pyxel.height, 0)
        pyxel.dither(1.0)

    def draw_game_over(self):
        w, h = pyxel.width, pyxel.height
        s = self.get_ui_scale()
        pyxel.dither(0.4)
        pyxel.rect(0, 0, w, h, 8)
        pyxel.dither(1.0)
        self.center_text(h // 2 - 22 * s, "YOU DIED!", 7, shadow=True, scale=max(1, s * 2))

        rx, ry, rw, rh = self.game_over_button_rect()
        hover = rx <= pyxel.mouse_x < rx + rw and ry <= pyxel.mouse_y < ry + rh
        pyxel.rect(rx, ry, rw, rh, 5 if hover else 1)
        pyxel.rectb(rx, ry, rw, rh, 7 if hover else 13)
        self.center_text(ry + (rh - 6 * s) // 2, "Respawn", 10 if hover else 7, scale=s)

    def draw_hud(self):
        w, h = pyxel.width, pyxel.height
        s = self.get_ui_scale()

        # Underwater screen tint
        if self.player.head_in_water(self.world):
            pyxel.dither(0.3)
            pyxel.rect(0, 0, w, h, 5)
            pyxel.dither(1.0)

        # Red damage vignette
        if self.player.hurt_timer > 0 and self.player.mode == "survival":
            pyxel.dither(0.25)
            pyxel.rect(0, 0, w, h, 8)
            pyxel.dither(1.0)

        # First-person swinging hand / tool
        self.draw_first_person_hand()

        # Crosshair
        cx, cy = w // 2, h // 2
        arm = 4 * s
        thick = max(1, s)
        pyxel.rect(cx - arm, cy - thick // 2, arm * 2 + 1, thick, 7)
        pyxel.rect(cx - thick // 2, cy - arm, thick, arm * 2 + 1, 7)

        # Hotbar
        slot = 20 * s
        x0 = (w - slot * len(self.hotbar)) // 2
        y0 = h - slot - 3 * s
        pyxel.dither(0.5)
        pyxel.rect(x0 - s, y0 - s, slot * len(self.hotbar) + 2 * s, slot + 2 * s, 0)
        pyxel.dither(1.0)
        for i, (b_id, cnt) in enumerate(self.hotbar):
            bx, by = x0 + i * slot, y0
            pyxel.rectb(bx, by, slot, slot, 7 if i == self.selected else 13)
            if b_id > 0 and cnt > 0:
                self.draw_icon(bx + 2 * s, by + 2 * s, b_id, scale=s)
                if cnt > 1:
                    cs = str(cnt)
                    self.draw_text(bx + slot - len(cs) * 4 * s - s, by + slot - 6 * s - s, cs, 7, scale=s)

        cur_item = self.hotbar[self.selected][0]
        cur_cnt = self.hotbar[self.selected][1]
        cur_name = get_item_name(cur_item) if cur_cnt > 0 else "Empty"
        self.center_text(y0 - (20 * s if self.player.mode == "survival" else 10 * s), cur_name, 7, shadow=True, scale=s)

        if self.message and self.play_time - self.message_time < 2.5:
            self.center_text(y0 - 28 * s, self.message, 10, shadow=True, scale=s)

        # Status bars: Hearts & Bubbles in Survival
        if self.player.mode == "survival":
            self.draw_status_bars(x0, y0 - 10 * s)

        # Debug & Help overlays
        y = 2 * s
        if self.show_debug:
            px, py, pz = self.player.pos
            hours = int((self.time_of_day * 24 + 6) % 24)
            fs_text = "  [FULLSCREEN]" if self.fullscreen_enabled else ""
            lines = [
                f"FPS {self.fps:4.0f} / {self.settings['fps']}  {w}x{h} (UI {s}x)  FOV {self.settings['fov']}{fs_text}",
                f"XYZ {px:5.1f} {py:5.1f} {pz:5.1f}  MODE: {self.player.mode.upper()}",
                f"Time {hours:02d}:00  Seed {self.world.seed}" + ("  FLY" if self.player.flying else ""),
            ]
            if self.target:
                tx, ty, tz = self.target[0]
                t_name = get_item_name(self.world.get(tx, ty, tz))
                lines.append(f"Target: {t_name} [{tx}, {ty}, {tz}]")
            for line in lines:
                self.shadow_text(2 * s, y, line, 7, scale=s)
                y += 7 * s
        if self.show_help:
            for line in HELP:
                self.shadow_text(2 * s, y, line, 6, scale=s)
                y += 7 * s
        if not self.mouse_captured and self.state == "playing":
            self.center_text(cy + 12 * s, "Click to capture the mouse", 10, shadow=True, scale=s)

    def player_aabb(self):
        px, py, pz = self.player.pos
        hw, h = 0.3, 1.8
        return (px - hw, py, pz - hw, px + hw, py + h, pz + hw)

    def draw_status_bars(self, x0, y0):
        s = self.get_ui_scale()
        slot = 20 * s
        total_w = slot * len(self.hotbar)

        # 10 Hearts on the left (2 HP per heart)
        for i in range(10):
            hx = x0 + i * 8 * s
            hy = y0
            hp = (i + 1) * 2
            # Heart outline
            pyxel.rect(hx + s, hy, 5 * s, 6 * s, 0)
            pyxel.rect(hx, hy + s, 7 * s, 4 * s, 0)
            pyxel.rect(hx + 3 * s, hy + 6 * s, s, s, 0)
            if self.player.health >= hp:
                # Full red heart
                pyxel.rect(hx + s, hy + s, 5 * s, 4 * s, 8)
                pyxel.rect(hx + 2 * s, hy, s, s, 8)
                pyxel.rect(hx + 4 * s, hy, s, s, 8)
                pyxel.rect(hx + 3 * s, hy + 5 * s, s, s, 8)
                pyxel.rect(hx + s, hy + s, s, s, 7)
            elif self.player.health == hp - 1:
                # Half red heart
                pyxel.rect(hx + s, hy + s, 2 * s, 4 * s, 8)
                pyxel.rect(hx + 2 * s, hy, s, s, 8)
                pyxel.rect(hx + 2 * s, hy + 5 * s, s, s, 8)
                pyxel.rect(hx + s, hy + s, s, s, 7)
            else:
                # Empty heart
                pyxel.rect(hx + s, hy + s, 5 * s, 4 * s, 13)

        # 10 Hunger drumsticks on the right (2 food units per drumstick)
        food = self.player.metabolism.food
        for i in range(10):
            fx = x0 + total_w - (10 - i) * 8 * s
            fy = y0
            f_val = (i + 1) * 2
            # Drumstick outline
            pyxel.rect(fx + s, fy, 5 * s, 6 * s, 0)
            pyxel.rect(fx, fy + s, 7 * s, 4 * s, 0)
            if food >= f_val:
                # Full drumstick (brown/orange)
                pyxel.rect(fx + s, fy + s, 5 * s, 4 * s, 9)
                pyxel.rect(fx + 2 * s, fy + 2 * s, 3 * s, 2 * s, 4)
                pyxel.rect(fx + 5 * s, fy + 4 * s, s, s, 7)
            elif food == f_val - 1:
                # Half drumstick
                pyxel.rect(fx + 3 * s, fy + s, 3 * s, 4 * s, 9)
                pyxel.rect(fx + 5 * s, fy + 4 * s, s, s, 7)
            else:
                # Empty drumstick
                pyxel.rect(fx + s, fy + s, 5 * s, 4 * s, 13)

        # Experience bar & Level
        xp_y = y0 + 8 * s
        pyxel.rect(x0, xp_y, total_w, 2 * s, 0)
        progress = self.player.metabolism.level_progress
        fill_w = int(total_w * progress)
        if fill_w > 0:
            pyxel.rect(x0, xp_y, fill_w, 2 * s, 11)

        lvl = self.player.metabolism.level
        if lvl > 0:
            self.center_text(xp_y - 6 * s, str(lvl), 11, shadow=True, scale=s)

        # 10 Air bubbles above hunger bar
        if self.player.air < self.player.max_air:
            bubbles = int(math.ceil(self.player.air))
            for i in range(bubbles):
                bx = x0 + total_w - (10 - i) * 8 * s
                by = y0 - 8 * s
                pyxel.circb(bx + 3 * s, by + 3 * s, 3 * s, 12)
                pyxel.rect(bx + 2 * s, by + 2 * s, s, s, 7)

    def draw_first_person_hand(self):
        w, h = pyxel.width, pyxel.height
        s = self.get_ui_scale()
        hx, hy = w - 44 * s, h - 36 * s
        bob_x = (math.cos(self.player.walked * 3.5) * 3 * s) if self.player.on_ground else 0
        bob_y = (abs(math.sin(self.player.walked * 3.5)) * 3 * s) if self.player.on_ground else 0
        swing_val = math.sin(self.player.swing_progress * math.pi)
        swing_x = swing_val * 8 * s
        swing_y = swing_val * 10 * s

        x = int(hx - swing_x + bob_x)
        y = int(hy + swing_y - bob_y)

        slot = self.hotbar[self.selected]
        item_id = slot[0] if slot[1] > 0 else 0

        if item_id == 0:
            # Arm box
            pyxel.rect(x + 10 * s, y + 8 * s, 22 * s, 34 * s, 15)
            pyxel.rect(x + 8 * s, y + 26 * s, 26 * s, 20 * s, 12)
            pyxel.rectb(x + 10 * s, y + 8 * s, 22 * s, 34 * s, 4)
        else:
            self.draw_icon(x + 8 * s, y - 2 * s, item_id, scale=2 * s)

    def draw_crafting_screen(self):
        self.dim_screen()
        lay = self.craft_layout()
        s, slot_s = lay["s"], lay["slot_s"]

        title = "Crafting Table (3x3)" if self.craft_size == 3 else "Crafting & Inventory (2x2)"
        self.center_text(12 * s, title, 7, shadow=True, scale=s)

        # Quick recipes on left
        self.draw_text(lay["qx"], lay["qy0"] - 10 * s, "Quick Recipes:", 10, scale=s)
        for q_idx, (r_name, r_ingr, r_out) in enumerate(self.quick_recipes()):
            qy = lay["qy0"] + q_idx * (lay["qh"] + 2 * s)
            can_craft = self.has_ingredients(r_ingr)
            hover = lay["qx"] <= pyxel.mouse_x < lay["qx"] + lay["qw"] and qy <= pyxel.mouse_y < qy + lay["qh"]
            pyxel.rect(lay["qx"], qy, lay["qw"], lay["qh"], 5 if hover else (1 if can_craft else 0))
            pyxel.rectb(lay["qx"], qy, lay["qw"], lay["qh"], 7 if hover else (13 if can_craft else 1))
            self.draw_icon(lay["qx"] + 2 * s, qy + s, r_out[0], scale=s)
            self.draw_text(lay["qx"] + 18 * s, qy + 3 * s, r_name, 10 if can_craft else 6, scale=s)

        # Crafting Grid in center
        size = self.craft_size
        gx0, gy0 = lay["gx0"], lay["gy0"]
        for r in range(size):
            for c in range(size):
                idx = r * size + c
                sx, sy = gx0 + c * slot_s, gy0 + r * slot_s
                slot = self.craft_grid[idx]
                pyxel.rect(sx, sy, slot_s, slot_s, 1)
                pyxel.rectb(sx, sy, slot_s, slot_s, 13)
                if slot[0] != 0 and slot[1] > 0:
                    self.draw_icon(sx + 2 * s, sy + 2 * s, slot[0], scale=s)
                    if slot[1] > 1:
                        self.draw_text(sx + 10 * s, sy + 12 * s, str(slot[1]), 7, scale=s)

        # Arrow ->
        self.draw_text(gx0 + size * slot_s + 5 * s, gy0 + (size * slot_s) // 2 - 3 * s, "->", 7, scale=s)

        # Result slot
        rx, ry, rw, rh = lay["rx"], lay["ry"], lay["rw"], lay["rh"]
        has_res = self.craft_result[0] != 0
        pyxel.rect(rx, ry, rw, rh, 5 if has_res else 1)
        pyxel.rectb(rx, ry, rw, rh, 10 if has_res else 13)
        if has_res:
            self.draw_icon(rx + 2 * s, ry + 2 * s, self.craft_result[0], scale=s)
            if self.craft_result[1] > 1:
                self.draw_text(rx + 10 * s, ry + 12 * s, str(self.craft_result[1]), 10, scale=s)

        # Main Inventory (3 rows of 9) + Hotbar (1 row of 9)
        ix0, iy0 = lay["ix0"], lay["iy0"]
        self.draw_text(ix0, iy0 - 8 * s, "Inventory:", 7, scale=s)
        for row in range(3):
            for col in range(9):
                idx = row * 9 + col
                sx, sy = ix0 + col * slot_s, iy0 + row * slot_s
                slot = self.inventory[idx]
                pyxel.rect(sx, sy, slot_s, slot_s, 1)
                pyxel.rectb(sx, sy, slot_s, slot_s, 13)
                if slot[0] != 0 and slot[1] > 0:
                    self.draw_icon(sx + 2 * s, sy + 2 * s, slot[0], scale=s)
                    if slot[1] > 1:
                        self.draw_text(sx + 10 * s, sy + 12 * s, str(slot[1]), 7, scale=s)

        # Hotbar row
        hy0 = iy0 + 3 * slot_s + 4 * s
        for col in range(9):
            sx, sy = ix0 + col * slot_s, hy0
            slot = self.hotbar[col]
            pyxel.rect(sx, sy, slot_s, slot_s, 1)
            pyxel.rectb(sx, sy, slot_s, slot_s, 7 if col == self.selected else 13)
            if slot[0] != 0 and slot[1] > 0:
                self.draw_icon(sx + 2 * s, sy + 2 * s, slot[0], scale=s)
                if slot[1] > 1:
                    self.draw_text(sx + 10 * s, sy + 12 * s, str(slot[1]), 7, scale=s)

    @staticmethod
    def draw_icon(x, y, item_id, scale=1):
        tile = get_item_tile(item_id)
        u, v = (tile % ATLAS_TILES) * TILE, (tile // ATLAS_TILES) * TILE
        if scale <= 1:
            pyxel.blt(int(x), int(y), 0, u, v, TILE, TILE, colkey=0)
        else:
            bx = int(x + (scale - 1) * (TILE / 2))
            by = int(y + (scale - 1) * (TILE / 2))
            pyxel.blt(bx, by, 0, u, v, TILE, TILE, colkey=0, scale=scale)

    def draw_text(self, x, y, s, col, scale=1):
        if not s:
            return
        if "\n" in s:
            for idx, line in enumerate(s.split("\n")):
                self.draw_text(x, y + idx * 7 * scale, line, col, scale=scale)
            return
        if scale <= 1:
            pyxel.text(int(x), int(y), s, col)
            return
        w = min(self.text_scratch.width, max(1, len(s) * 4))
        h = 6
        self.text_scratch.cls(255)
        self.text_scratch.text(0, 0, s, col)
        bx = int(x + (scale - 1) * (w / 2))
        by = int(y + (scale - 1) * (h / 2))
        pyxel.blt(bx, by, self.text_scratch, 0, 0, w, h, colkey=255, scale=scale)

    def shadow_text(self, x, y, s, col, scale=1):
        self.draw_text(x + scale, y + scale, s, 0, scale=scale)
        self.draw_text(x, y, s, col, scale=scale)

    def center_text(self, y, s, col, shadow=False, scale=1):
        w = len(s) * 4 * scale
        x = (pyxel.width - w) // 2
        if shadow:
            self.shadow_text(x, y, s, col, scale=scale)
        else:
            self.draw_text(x, y, s, col, scale=scale)


if __name__ == "__main__":
    App().run()
