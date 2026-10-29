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
    BLOCK_TILES, CRAFTING_TABLE, CREATIVE_CATALOG, DEFAULT_HOTBAR, FOOD_HEAL, ITEM_COOKED_PORK,
    ITEM_DIAMOND_PICKAXE, ITEM_DIAMOND_SWORD, ITEM_IRON_PICKAXE, ITEM_IRON_SWORD,
    ITEM_RAW_PORK, ITEM_STICK, ITEM_STONE_PICKAXE, ITEM_STONE_SWORD, ITEM_WOOD_PICKAXE,
    ITEM_WOOD_SWORD, LOG, NON_STACKABLE, PICKAXES, PLACEABLE, PLANKS, TILE, UNBREAKABLE, WATER,
    build_atlas, get_item_name, get_item_tile,
)
import crafting
from clock import GameClock, TICK_DURATION, TICKS_PER_DAY, interpolate_position
from combat import CombatEngine, InvulnerabilityTracker
from entities import EntityManager
from generator import WorldPreset, parse_seed
from mining import MiningEngine, TOOL_DURABILITY_TABLE
from physics import DDARaycast, SweptAABBPhysics, REACH_MINE, REACH_PLACE
from player import Player
from renderer import Renderer, look_at
from world import World
from world_manager import WorldManager
from texture_pack import TexturePackManager

BASE_WIDTH, BASE_HEIGHT = 320, 180
RESOLUTIONS = [
    (320, 180),
    (384, 216),
    (480, 270),
    (640, 360),
    (800, 450),
    (960, 540),
    (1280, 720),
    (1600, 900),
    (1920, 1080),
    (2560, 1440),
]
FRAME_RATES = [30, 60, 75, 120, 144, 165, 240]
FOVS = [60, 70, 80, 90]
RENDER_DISTANCES = [2, 4, 6, 8, 10, 12, 16, 20, 24]
SENSITIVITIES = [0.12, 0.18, 0.25, 0.35, 0.50]
SENS_NAMES = {0.12: "Low", 0.18: "Medium", 0.25: "Normal", 0.35: "High", 0.50: "Very High"}
GUI_SCALES = ["Auto", "1x", "2x", "3x", "4x"]
DEFAULT_SETTINGS = {
    "resolution": (320, 180),
    "fps": 60,
    "fov": 70,
    "render_distance": 12,
    "sensitivity": 0.25,
    "music": True,
    "fullscreen": False,
    "gui_scale": "Auto",
    "active_resource_pack": "default",
}
MAX_DT = 0.1
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

        data_dir = pyxel.user_data_dir("PyCraft", "PyCraft GPU")
        self.saves_dir = os.path.join(data_dir, "saves")
        self.world_mgr = WorldManager(self.saves_dir)
        self.save_path = os.path.join(data_dir, "world.npz")
        self.world_mgr.migrate_legacy_save(self.save_path)
        self.settings_path = os.path.join(data_dir, "settings.json")
        self.settings = self.load_settings()

        self.resource_packs_dir = os.path.join(data_dir, "resourcepacks")
        self.texture_pack_mgr = TexturePackManager(self.resource_packs_dir)
        self.active_resource_pack = self.settings.get("active_resource_pack", "default")

        atlas = self.texture_pack_mgr.build_pack_atlas(self.active_resource_pack)
        self.atlas = atlas
        icons = atlas_to_indices(atlas)
        bank = np.frombuffer(pyxel.images[0].data_ptr(), dtype=np.uint8, count=256 * 256).reshape(256, 256)
        bank[:icons.shape[0], :icons.shape[1]] = icons
        pyxel.images[1].cls(0)
        pyxel.images[1].text(0, 0, "PYCRAFT", 7)
        self.text_scratch = pyxel.Image(1024, 64)
        self.init_sounds()

        self.fullscreen_enabled = bool(self.settings.get("fullscreen", False))
        if self.fullscreen_enabled and not headless:
            try:
                pyxel.fullscreen(True)
            except Exception:
                pass

        self.save_data = None
        self.world = None
        # Check active worlds or legacy save
        saved_worlds = self.world_mgr.list_worlds()
        if saved_worlds:
            first_w = saved_worlds[0]
            try:
                self.world, self.save_data = World.load(first_w["save_path"])
                self.save_path = first_w["save_path"]
                self.current_world_info = first_w
            except (OSError, ValueError, KeyError):
                self.world = None
        elif os.path.exists(self.save_path):
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
        self.craft_result = [0, 0]
        self.cursor_item = [0, 0]  # [item_id, count] held on mouse cursor
        self.creative_tab = "catalog"  # "catalog" or "survival" in Creative mode

        # Multi-world selection & creation
        self.selected_world_idx = 0
        self.world_name_suggestions = [
            "New World", "Survival Island", "Voxel Adventure",
            "Alpine Peaks", "Mining Kingdom", "Infinite Plains"
        ]
        self.world_name_idx = 0
        self.new_world_name = self.world_name_suggestions[0]
        self.new_world_mode = "survival"
        self.new_world_preset = WorldPreset.STANDARD
        self.new_world_seed = ""
        self.active_text_field = None  # None, "world_name", or "seed"
        self.current_world_info = None
        self.world_list_cache = None

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

    @property
    def world_manager(self):
        return self.world_mgr

    @world_manager.setter
    def world_manager(self, mgr):
        self.world_mgr = mgr

    @property
    def create_world_focus(self):
        if self.active_text_field == "world_name":
            return "name"
        elif self.active_text_field == "seed":
            return "seed"
        return "name"

    @create_world_focus.setter
    def create_world_focus(self, val):
        if val == "name":
            self.active_text_field = "world_name"
        elif val == "seed":
            self.active_text_field = "seed"
        else:
            self.active_text_field = None

    @property
    def create_world_name(self):
        return self.new_world_name

    @create_world_name.setter
    def create_world_name(self, val):
        self.new_world_name = str(val)

    @property
    def create_world_seed(self):
        return self.new_world_seed

    @create_world_seed.setter
    def create_world_seed(self, val):
        self.new_world_seed = str(val)

    @property
    def create_world_mode(self):
        return self.new_world_mode

    @create_world_mode.setter
    def create_world_mode(self, val):
        self.new_world_mode = str(val)

    @property
    def create_world_preset_idx(self):
        try:
            return WorldPreset.ALL.index(self.new_world_preset)
        except ValueError:
            return 0

    @create_world_preset_idx.setter
    def create_world_preset_idx(self, idx):
        presets = WorldPreset.ALL
        self.new_world_preset = presets[idx % len(presets)]

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
            if saved.get("render_distance") in RENDER_DISTANCES:
                settings["render_distance"] = saved["render_distance"]
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
            if isinstance(saved.get("active_resource_pack"), str):
                settings["active_resource_pack"] = saved["active_resource_pack"]
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

    def change_render_distance(self, step):
        rd = self.settings.get("render_distance", 4)
        if rd not in RENDER_DISTANCES:
            rd = 4
        i = RENDER_DISTANCES.index(rd)
        self.settings["render_distance"] = RENDER_DISTANCES[(i + step) % len(RENDER_DISTANCES)]
        self.save_settings()
        self.notify(f"Render Distance: {self.settings['render_distance']} Chunks")

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

    def open_resource_packs(self, step=1):
        self.set_state("resource_packs")

    def set_resource_pack(self, pack_id):
        self.active_resource_pack = pack_id
        self.settings["active_resource_pack"] = pack_id
        self.save_settings()
        new_atlas = self.texture_pack_mgr.build_pack_atlas(pack_id)
        self.atlas = new_atlas
        icons = atlas_to_indices(new_atlas)
        bank = np.frombuffer(pyxel.images[0].data_ptr(), dtype=np.uint8, count=256 * 256).reshape(256, 256)
        bank[:icons.shape[0], :icons.shape[1]] = icons
        if hasattr(self, "renderer") and self.renderer and hasattr(self.renderer, "texture") and self.renderer.texture:
            self.renderer.texture.write(new_atlas.tobytes())
        self.notify(f"Pack Loaded: {pack_id.capitalize()}")

    def open_packs_folder(self, step=1):
        self.notify(f"Resource packs: {self.texture_pack_mgr.packs_dir}")
        try:
            import subprocess
            if sys.platform == "darwin":
                subprocess.Popen(["open", self.texture_pack_mgr.packs_dir])
            elif sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", self.texture_pack_mgr.packs_dir])
        except Exception:
            pass

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

    def add_to_container(self, container, item_id, count):
        """Add items to a container list (hotbar or inventory). Returns amount added."""
        max_stack = 1 if item_id in NON_STACKABLE else 64
        added = 0
        for slot in container:
            if slot[0] == item_id and slot[1] < max_stack:
                take = min(max_stack - slot[1], count)
                slot[1] += take
                count -= take
                added += take
                if count <= 0:
                    return added
        for slot in container:
            if slot[0] == 0 or slot[1] <= 0:
                slot[0] = item_id
                take = min(max_stack, count)
                slot[1] = take
                count -= take
                added += take
                if count <= 0:
                    return added
        return added

    def pick_block(self, block_id):
        if block_id == 0:
            return
        # 1. Hotbar check
        for i in range(len(self.hotbar)):
            if self.hotbar[i][0] == block_id and self.hotbar[i][1] > 0:
                self.selected = i
                return
        # 2. Main inventory check -> swap into current hotbar slot
        for i in range(len(self.inventory)):
            if self.inventory[i][0] == block_id and self.inventory[i][1] > 0:
                self.inventory[i], self.hotbar[self.selected] = self.hotbar[self.selected], self.inventory[i]
                return
        # 3. Creative mode -> clone stack of 64
        if self.player.mode == "creative":
            self.hotbar[self.selected] = [block_id, 64]

    def drop_item(self):
        slot = self.hotbar[self.selected]
        if slot[0] != 0 and slot[1] > 0:
            cnt = slot[1] if pyxel.btn(pyxel.KEY_LCTRL) else 1
            slot[1] -= cnt
            dropped_id = slot[0]
            if slot[1] <= 0:
                slot[0] = 0
            self.notify(f"Dropped {get_item_name(dropped_id)} x{cnt}")
            self.sfx(SND_CLICK)

    def close_inventory(self):
        # Refund cursor item
        if self.cursor_item[0] != 0 and self.cursor_item[1] > 0:
            if getattr(self.player, "mode", "survival") == "creative":
                self.cursor_item = [0, 0]
            else:
                self.add_to_inventory(self.cursor_item[0], self.cursor_item[1])
                self.cursor_item = [0, 0]
        # Refund crafting grid items
        for slot in self.craft_grid:
            if slot[0] != 0 and slot[1] > 0:
                self.add_to_inventory(slot[0], slot[1])
                slot[0], slot[1] = 0, 0
        self.set_state("playing")

    def snapshot(self):
        p = self.player
        return {
            "player": np.array(p.pos + [p.yaw, p.pitch, float(p.flying), float(p.health)], dtype=np.float64),
            "time_of_day": self.time_of_day,
            "hotbar": np.array([[int(s[0]), int(s[1]), int(s[2]) if len(s) > 2 else 0] for s in self.hotbar], dtype=np.int32),
            "inventory": np.array([[int(s[0]), int(s[1]), int(s[2]) if len(s) > 2 else 0] for s in self.inventory], dtype=np.int32),
            "armor": np.array([[int(s[0]), int(s[1]), int(s[2]) if len(s) > 2 else 0] for s in getattr(p, "armor_slots", [[0, 0]] * 4)], dtype=np.int32),
            "offhand": np.array([int(s) for s in getattr(p, "offhand_slot", [0, 0])[:2]], dtype=np.int32),
            "selected": self.selected,
            "mode": self.player.mode,
        }

    def save(self):
        tmp = self.save_path + ".tmp.npz"
        self.world.save(tmp, **self.snapshot())
        os.replace(tmp, self.save_path)
        self.last_save = self.play_time
        self.world_is_fresh = False
        if self.current_world_info and "folder" in self.current_world_info:
            self.current_world_info["last_played"] = time.time()
            self.world_mgr.save_metadata(self.current_world_info["folder"], self.current_world_info)

    def start_game(self, new_world, mode="survival", preset=None, seed=None):
        if new_world:
            preset = preset or self.current_preset
            seed_val = random.randrange(1 << 30) if seed is None else seed
            self.world = World(seed=seed_val, preset=preset)
            spawn_pos = self.world.find_spawn()
            self.player = Player(*spawn_pos, mode=mode)
            self.renderer.set_world(self.world, spawn_pos=spawn_pos, render_dist=self.settings.get("render_distance", 4))
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
            self.time_of_day = float(data.get("time_of_day", 0.05))
            if "hotbar" in data:
                hb = data["hotbar"]
                self.hotbar = []
                for s in hb:
                    if hasattr(s, "__len__") and len(s) >= 2:
                        slot_item = [int(s[0]), int(s[1])]
                        if len(s) >= 3:
                            slot_item.append(int(s[2]))
                        self.hotbar.append(slot_item)
                    else:
                        self.hotbar.append([int(s), 64])
                while len(self.hotbar) < 9:
                    self.hotbar.append([0, 0])
            if "inventory" in data:
                inv = data["inventory"]
                self.inventory = []
                for s in inv:
                    if hasattr(s, "__len__") and len(s) >= 2:
                        slot_item = [int(s[0]), int(s[1])]
                        if len(s) >= 3 and int(s[2]) > 0:
                            slot_item.append(int(s[2]))
                        self.inventory.append(slot_item)
                    else:
                        self.inventory.append([int(s), 64])
                while len(self.inventory) < 27:
                    self.inventory.append([0, 0])
            if "armor" in data:
                self.player.armor_slots = [list(map(int, s)) for s in data["armor"]]
            if "offhand" in data:
                self.player.offhand_slot = list(map(int, data["offhand"]))
            self.selected = int(data.get("selected", 0))
            self.clock.reset(int(self.time_of_day * TICKS_PER_DAY))
            self.renderer.set_world(self.world, spawn_pos=self.player.pos, render_dist=self.settings.get("render_distance", 4))
        self.save_data = None
        self.play_time = self.last_save = 0.0
        self.show_help = True
        self.particles = []
        self.entity_mgr = EntityManager()
        self.set_state("playing")

    # --- Multi-world Management ----------------------------------------------------------------

    def open_select_world(self):
        self.selected_world_idx = 0
        self.set_state("select_world")

    def play_selected_world(self):
        worlds = self.world_mgr.list_worlds()
        if not worlds:
            self.open_create_world()
            return
        idx = max(0, min(self.selected_world_idx, len(worlds) - 1))
        w_info = worlds[idx]
        self.load_and_play_world(w_info)

    def load_and_play_world(self, w_info):
        save_path = w_info["save_path"]
        if not os.path.exists(save_path):
            self.save_path = save_path
            self.current_world_info = dict(w_info)
            self.current_preset = w_info.get("preset", WorldPreset.STANDARD)
            self.world_is_fresh = True
            self.start_game(
                new_world=True,
                mode=w_info.get("mode", "survival"),
                preset=self.current_preset,
                seed=w_info.get("seed", 1),
            )
            self.notify(f"Created & Loaded {w_info['name']}")
            return

        try:
            self.world, self.save_data = World.load(save_path)
            self.save_path = save_path
            self.current_world_info = dict(w_info)
            self.current_preset = w_info.get("preset", WorldPreset.STANDARD)
            self.world_is_fresh = False
            self.start_game(new_world=False)
            self.notify(f"Loaded {w_info['name']}")
        except Exception as e:
            self.notify(f"Error loading world: {e}")

    def delete_selected_world(self):
        worlds = self.world_mgr.list_worlds()
        if not worlds:
            return
        idx = max(0, min(self.selected_world_idx, len(worlds) - 1))
        target = worlds[idx]
        self.world_mgr.delete_world(target["folder"])
        self.notify(f"Deleted {target['name']}")
        self.selected_world_idx = max(0, idx - 1)

    def cycle_selected_world(self, step=1):
        worlds = self.world_mgr.list_worlds()
        if worlds:
            self.selected_world_idx = (self.selected_world_idx + step) % len(worlds)

    def open_create_world(self):
        worlds = self.world_mgr.list_worlds()
        existing = {w["name"] for w in worlds}
        for name in self.world_name_suggestions:
            if name not in existing:
                self.new_world_name = name
                break
        else:
            self.new_world_name = f"World {len(worlds) + 1}"
        self.set_state("create_world")

    def cycle_new_world_name(self, step=1):
        self.world_name_idx = (self.world_name_idx + step) % len(self.world_name_suggestions)
        self.new_world_name = self.world_name_suggestions[self.world_name_idx]

    def focus_world_name(self, step=1):
        if self.active_text_field == "world_name":
            self.cycle_new_world_name(step)
        else:
            self.active_text_field = "world_name"

    def toggle_new_world_mode(self, step=1):
        self.new_world_mode = "creative" if self.new_world_mode == "survival" else "survival"

    def cycle_new_world_preset(self, step=1):
        i = WorldPreset.ALL.index(self.new_world_preset)
        self.new_world_preset = WorldPreset.ALL[(i + step) % len(WorldPreset.ALL)]

    def cycle_new_world_seed(self, step=1):
        seeds = ["", "12345", "42", "888888", "1337", "9999999"]
        cur = self.new_world_seed
        i = seeds.index(cur) if cur in seeds else 0
        self.new_world_seed = seeds[(i + step) % len(seeds)]

    def focus_world_seed(self, step=1):
        if self.active_text_field == "seed":
            self.cycle_new_world_seed(step)
        else:
            self.active_text_field = "seed"

    def confirm_create_world(self):
        if self.new_world_seed:
            try:
                seed_val = int(self.new_world_seed)
            except ValueError:
                seed_val = hash(self.new_world_seed) & 0x7FFFFFFF
        else:
            seed_val = random.randrange(1 << 30)

        name = self.new_world_name.strip() or "New World"
        mode = self.new_world_mode
        preset = self.new_world_preset

        meta = self.world_mgr.create_world_entry(name, mode, preset, seed_val)
        self.save_path = meta["save_path"]
        self.current_world_info = meta
        self.current_preset = preset
        self.start_game(new_world=True, mode=mode, preset=preset, seed=seed_val)
        self.notify(f"Created {name}")

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
        return self.state in ("title", "select_world", "create_world", "multiplayer", "resource_packs") or (
            self.state == "settings" and self.settings_parent == "title"
        )

    def change_preset(self, step=1):
        i = WorldPreset.ALL.index(self.current_preset)
        self.current_preset = WorldPreset.ALL[(i + step) % len(WorldPreset.ALL)]

    def menu_items(self):
        if self.state == "title":
            return [
                ("Singleplayer", self.open_select_world),
                ("Multiplayer", lambda: self.set_state("multiplayer")),
                ("Settings", self.open_settings),
                ("Quit Game", pyxel.quit),
            ]
        if self.state == "select_world":
            worlds = self.world_mgr.list_worlds()
            items = []
            if worlds:
                items.append(("Play Selected World", self.play_selected_world))
                if len(worlds) > 1:
                    items.append(("Switch World (< / >)", self.cycle_selected_world))
            items.append(("Create New World", self.open_create_world))
            if worlds:
                items.append(("Delete World", self.delete_selected_world))
            items.append(("Cancel", lambda: self.set_state("title")))
            return items
        if self.state == "create_world":
            preset_name = self.new_world_preset.capitalize().replace("_", " ")
            seed_disp = self.new_world_seed if self.new_world_seed else "Random"
            cursor_name = "_" if self.active_text_field == "world_name" and (pyxel.frame_count // 15) % 2 == 0 else ""
            cursor_seed = "_" if self.active_text_field == "seed" and (pyxel.frame_count // 15) % 2 == 0 else ""
            return [
                (f"World Name: {self.new_world_name}{cursor_name}", self.focus_world_name),
                (f"Game Mode: {self.new_world_mode.capitalize()}", self.toggle_new_world_mode),
                (f"World Type: {preset_name}", self.cycle_new_world_preset),
                (f"Seed: {seed_disp}{cursor_seed}", self.focus_world_seed),
                ("Create New World", self.confirm_create_world),
                ("Cancel", lambda: self.set_state("select_world")),
            ]
        if self.state == "multiplayer":
            return [
                ("Back", lambda: self.set_state("title")),
            ]
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
            rd = self.settings.get("render_distance", 4)
            return [
                (f"Resolution: {w} x {h}", self.change_resolution),
                (f"Fullscreen: {fs_label}", lambda step: self.toggle_fullscreen()),
                (f"Render Distance: {rd} Chunks", self.change_render_distance),
                (f"GUI Scale: {gui_label}", self.change_gui_scale),
                (f"Frame rate: {self.settings['fps']} FPS", self.change_fps),
                (f"Field of view: {self.settings['fov']} deg", self.change_fov),
                (f"Mouse speed: {sens_label}", self.change_sensitivity),
                ("Music: " + ("on" if self.settings["music"] else "off"), lambda step: self.toggle_music()),
                ("Resource Packs...", self.open_resource_packs),
                ("Done", lambda step: self.close_settings()),
            ]
        if self.state == "resource_packs":
            packs = self.texture_pack_mgr.list_packs()
            items = []
            for p in packs:
                status = " [ACTIVE]" if p.pack_id == self.active_resource_pack else ""
                items.append((f"{p.name}{status}", (lambda pid: lambda step: self.set_resource_pack(pid))(p.pack_id)))
            items.append(("Open Resource Pack Folder", self.open_packs_folder))
            items.append(("Done", lambda step: self.set_state("settings")))
            return items
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

        if self.state in ("title", "paused", "settings", "select_world", "create_world", "multiplayer", "resource_packs"):
            if self.state == "paused" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.set_state("playing")
            elif self.state == "settings" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.close_settings()
            elif self.state == "resource_packs" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.set_state("settings")
            elif self.state == "select_world" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.set_state("title")
            elif self.state == "create_world" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.set_state("select_world")
            elif self.state == "multiplayer" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.set_state("title")
            else:
                self.update_menu()
        elif self.state in ("inventory", "crafting_table"):
            self.update_crafting_ui()
        elif self.state == "game_over":
            self.update_game_over()
        else:
            self.update_playing()

    def update_menu(self):
        # Handle free text typing when an input field is active in create_world
        if self.state == "create_world" and self.active_text_field:
            txt = getattr(pyxel, "input_text", "")
            if txt:
                filtered = "".join(ch for ch in txt if ch.isprintable() and ch not in "\r\n")
                if filtered:
                    if self.active_text_field == "world_name":
                        if len(self.new_world_name) < 24:
                            self.new_world_name += filtered
                    elif self.active_text_field == "seed":
                        if len(self.new_world_seed) < 20:
                            self.new_world_seed += filtered

            backspace_pressed = False
            try:
                backspace_pressed = pyxel.btnp(pyxel.KEY_BACKSPACE, hold=10, period=2)
            except Exception:
                backspace_pressed = pyxel.btnp(pyxel.KEY_BACKSPACE)

            if backspace_pressed:
                if self.active_text_field == "world_name" and self.new_world_name:
                    self.new_world_name = self.new_world_name[:-1]
                elif self.active_text_field == "seed" and self.new_world_seed:
                    self.new_world_seed = self.new_world_seed[:-1]

        items = self.menu_items()
        if not items:
            return
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
        space_triggers = not (self.state == "create_world" and self.active_text_field)
        if pyxel.btnp(pyxel.KEY_RETURN) or (space_triggers and pyxel.btnp(pyxel.KEY_SPACE)):
            chosen = self.menu_index
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and hovered is not None:
            chosen = hovered

        label = items[self.menu_index][0] if 0 <= self.menu_index < len(items) else ""
        has_steps = (
            (self.state == "settings" and self.menu_index < len(items) - 1)
            or (self.state == "create_world" and (":" in label or "Mode" in label))
            or (self.state == "select_world" and ("< / >" in label or "Switch" in label))
        )
        if has_steps and (pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D)):
            chosen = self.menu_index
        if has_steps and (pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A) or pyxel.btnp(pyxel.KEY_Q)):
            chosen, step = self.menu_index, -1
        if pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT) and hovered is not None:
            hover_label = items[hovered][0] if 0 <= hovered < len(items) else ""
            hovered_has_steps = (
                (self.state == "settings" and hovered < len(items) - 1)
                or (self.state == "create_world" and (":" in hover_label or "Mode" in hover_label))
                or (self.state == "select_world" and ("< / >" in hover_label or "Switch" in hover_label))
            )
            if hovered_has_steps:
                chosen, step = hovered, -1

        if chosen is not None:
            self.sfx(SND_CLICK)
            self.menu_index = chosen
            cb = items[chosen][1]
            if self.state == "create_world":
                if chosen != 0 and self.active_text_field == "world_name":
                    self.active_text_field = None
                if chosen != 3 and self.active_text_field == "seed":
                    self.active_text_field = None
            try:
                cb(step)
            except TypeError:
                cb()

    def get_title_y(self):
        s = self.get_ui_scale()
        items = self.menu_items()
        h, spacing = 13 * s, 3 * s
        total_buttons_h = len(items) * (h + spacing) - spacing
        title_h = 16 * s
        return max(6 * s, (pyxel.height - (total_buttons_h + title_h)) // 2)

    def button_rect(self, i):
        s = self.get_ui_scale()
        w, h = min(140 * s, pyxel.width - 24 * s), 13 * s
        items = self.menu_items()
        spacing = 3 * s
        if self.state == "title":
            y0 = max(44 * s, pyxel.height // 2 + 4 * s)
        elif self.state == "select_world":
            y0 = max(55 * s, pyxel.height // 2 + 6 * s)
        elif self.state == "multiplayer":
            title_y = max(8 * s, pyxel.height // 2 - 36 * s)
            y0 = title_y + 48 * s
        else:
            title_y = self.get_title_y()
            y0 = title_y + 16 * s
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
            if getattr(self.player, "mode", "survival") == "creative":
                self.creative_tab = "catalog"
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

        # Pick Block with Middle Mouse Button (scroll wheel click)
        if pyxel.btnp(pyxel.MOUSE_BUTTON_MIDDLE) and self.target:
            tx, ty, tz = self.target[0]
            tb = self.world.get(tx, ty, tz)
            if tb != 0:
                self.pick_block(tb)

        # Drop item from active hotbar slot (Q on QWERTY, A on AZERTY)
        is_azerty = pyxel.btn(pyxel.KEY_Z)
        if (pyxel.btnp(pyxel.KEY_A) if is_azerty else pyxel.btnp(pyxel.KEY_Q)):
            self.drop_item()

        # 1. Update player physics every frame at the full display framerate (smooth at ~180 FPS)
        events = self.player.update(self.world, dt)
        for event in events:
            if event == "jump":
                self.sfx(SND_JUMP)
            elif event == "step":
                self.sfx(SND_STEP)
            elif event == "splash":
                self.sfx(SND_SPLASH)
            elif event == "hurt":
                self.sfx(SND_HURT)

        # 2. Deterministic 20 Hz fixed clock advancement for world simulation & metabolism
        def tick_logic(world_tick):
            self.time_of_day = self.clock.time_of_day
            self.invulnerability.tick()

            metab_events = self.player.tick_metabolism()
            if "hurt" in metab_events:
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
            if updated_chunks:
                self.renderer.rebuild_chunks(updated_chunks)

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

            # 2. Right click on Crafting Table in world (only if not sneaking)
            if self.target and not self.player.sneaking:
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
        slot_s = 18 * s
        size = self.craft_size

        pw, ph = 176 * s, 166 * s
        px0 = (pyxel.width - pw) // 2
        py0 = max(12 * s, (pyxel.height - ph) // 2) if (getattr(self.player, "mode", "survival") == "creative" and size == 2) else (pyxel.height - ph) // 2

        ix0 = px0 + 8 * s
        iy0 = py0 + 84 * s
        hx0 = px0 + 8 * s
        hy0 = py0 + 142 * s

        tab_cat = (px0 + 8 * s, py0 - 11 * s, 48 * s, 12 * s)
        tab_surv = (px0 + 60 * s, py0 - 11 * s, 54 * s, 12 * s)

        if size == 3:
            gx0 = px0 + 30 * s
            gy0 = py0 + 17 * s
            ax = px0 + 90 * s
            ay = py0 + 35 * s
            rx = px0 + 120 * s
            ry = py0 + 31 * s
            rw, rh = 26 * s, 26 * s
            return {
                "s": s, "slot_s": slot_s, "size": size,
                "pw": pw, "ph": ph, "px0": px0, "py0": py0,
                "gx0": gx0, "gy0": gy0,
                "ax": ax, "ay": ay,
                "rx": rx, "ry": ry, "rw": rw, "rh": rh,
                "ix0": ix0, "iy0": iy0,
                "hx0": hx0, "hy0": hy0,
            }
        else:
            is_creative = getattr(self.player, "mode", "survival") == "creative"
            if is_creative and getattr(self, "creative_tab", "catalog") == "catalog":
                cat_x0 = px0 + 8 * s
                cat_y0 = py0 + 18 * s
                trash_x = px0 + 150 * s
                trash_y = py0 + 114 * s
                hy0_cat = py0 + 138 * s
                return {
                    "type": "creative_catalog",
                    "s": s, "slot_s": slot_s, "size": size,
                    "pw": pw, "ph": ph, "px0": px0, "py0": py0,
                    "cat_x0": cat_x0, "cat_y0": cat_y0, "cat_rows": 5, "cat_cols": 9,
                    "trash_x": trash_x, "trash_y": trash_y, "trash_w": slot_s, "trash_h": slot_s,
                    "tab_cat": tab_cat, "tab_surv": tab_surv,
                    "hx0": hx0, "hy0": hy0_cat,
                    "ix0": cat_x0, "iy0": cat_y0,
                    "rx": trash_x, "ry": trash_y, "rw": slot_s, "rh": slot_s,
                }

            pvx = px0 + 26 * s
            pvy = py0 + 8 * s
            pvw = 48 * s
            pvh = 70 * s
            arm_x0 = px0 + 8 * s
            arm_y0 = py0 + 8 * s
            off_x0 = px0 + 77 * s
            off_y0 = py0 + 60 * s
            gx0 = px0 + 88 * s
            gy0 = py0 + 18 * s
            ax = px0 + 130 * s
            ay = py0 + 28 * s
            rx = px0 + 146 * s
            ry = py0 + 23 * s
            rw, rh = 24 * s, 24 * s
            res = {
                "s": s, "slot_s": slot_s, "size": size,
                "pw": pw, "ph": ph, "px0": px0, "py0": py0,
                "pvx": pvx, "pvy": pvy, "pvw": pvw, "pvh": pvh,
                "arm_x0": arm_x0, "arm_y0": arm_y0,
                "off_x0": off_x0, "off_y0": off_y0,
                "gx0": gx0, "gy0": gy0,
                "ax": ax, "ay": ay,
                "rx": rx, "ry": ry, "rw": rw, "rh": rh,
                "ix0": ix0, "iy0": iy0,
                "hx0": hx0, "hy0": hy0,
            }
            if is_creative:
                res["tab_cat"] = tab_cat
                res["tab_surv"] = tab_surv
            return res

    def get_slot_under_mouse(self, mx, my):
        lay = self.craft_layout()
        s, slot_s = lay["s"], lay["slot_s"]
        size = lay["size"]

        # Check tabs if present
        if "tab_cat" in lay:
            tx, ty, tw, th = lay["tab_cat"]
            if tx <= mx < tx + tw and ty <= my < ty + th:
                return ("tab", "catalog", tx, ty, tw, th)
        if "tab_surv" in lay:
            tx, ty, tw, th = lay["tab_surv"]
            if tx <= mx < tx + tw and ty <= my < ty + th:
                return ("tab", "survival", tx, ty, tw, th)

        # Creative catalog screen
        if lay.get("type") == "creative_catalog":
            # Trash slot
            tx, ty, tw, th = lay["trash_x"], lay["trash_y"], lay["trash_w"], lay["trash_h"]
            if tx <= mx < tx + tw and ty <= my < ty + th:
                return ("trash", 0, tx, ty, tw, th)

            # Catalog grid (5 rows x 9 cols)
            cat_x0, cat_y0 = lay["cat_x0"], lay["cat_y0"]
            for r in range(lay["cat_rows"]):
                for c in range(lay["cat_cols"]):
                    sx = cat_x0 + c * slot_s
                    sy = cat_y0 + r * slot_s
                    if sx <= mx < sx + slot_s and sy <= my < sy + slot_s:
                        idx = r * lay["cat_cols"] + c
                        return ("creative_catalog", idx, sx, sy, slot_s, slot_s)

            # Hotbar (1 row of 9)
            hx0, hy0 = lay["hx0"], lay["hy0"]
            for c in range(9):
                sx, sy = hx0 + c * slot_s, hy0
                if sx <= mx < sx + slot_s and sy <= my < sy + slot_s:
                    return ("hotbar", c, sx, sy, slot_s, slot_s)

            return None

        # 1. Result slot
        rx, ry, rw, rh = lay["rx"], lay["ry"], lay["rw"], lay["rh"]
        if rx <= mx < rx + rw and ry <= my < ry + rh:
            return ("result", 0, rx, ry, rw, rh)

        # 2. Craft grid
        gx0, gy0 = lay["gx0"], lay["gy0"]
        for r in range(size):
            for c in range(size):
                sx, sy = gx0 + c * slot_s, gy0 + r * slot_s
                if sx <= mx < sx + slot_s and sy <= my < sy + slot_s:
                    return ("grid", r * size + c, sx, sy, slot_s, slot_s)

        # 3. Main inventory (3 rows of 9)
        ix0, iy0 = lay["ix0"], lay["iy0"]
        for r in range(3):
            for c in range(9):
                sx, sy = ix0 + c * slot_s, iy0 + r * slot_s
                if sx <= mx < sx + slot_s and sy <= my < sy + slot_s:
                    return ("inventory", r * 9 + c, sx, sy, slot_s, slot_s)

        # 4. Hotbar (1 row of 9)
        hx0, hy0 = lay["hx0"], lay["hy0"]
        for c in range(9):
            sx, sy = hx0 + c * slot_s, hy0
            if sx <= mx < sx + slot_s and sy <= my < sy + slot_s:
                return ("hotbar", c, sx, sy, slot_s, slot_s)

        # 5. Armor slots & Off-hand in 2x2 player inventory
        if size == 2 and "arm_x0" in lay:
            arm_x0, arm_y0 = lay["arm_x0"], lay["arm_y0"]
            for i in range(4):
                sx, sy = arm_x0, arm_y0 + i * slot_s
                if sx <= mx < sx + slot_s and sy <= my < sy + slot_s:
                    return ("armor", i, sx, sy, slot_s, slot_s)
            off_x0, off_y0 = lay["off_x0"], lay["off_y0"]
            if off_x0 <= mx < off_x0 + slot_s and off_y0 <= my < off_y0 + slot_s:
                return ("offhand", 0, off_x0, off_y0, slot_s, slot_s)

        return None

    def handle_slot_click(self, slot_type, idx, is_right_click, is_shift_click):
        if slot_type == "tab":
            self.creative_tab = idx
            self.sfx(SND_CLICK)
            return

        if slot_type == "trash":
            if is_shift_click:
                for s in self.hotbar:
                    s[0], s[1] = 0, 0
                for s in self.inventory:
                    s[0], s[1] = 0, 0
                self.cursor_item = [0, 0]
                self.sfx(SND_CLICK)
            else:
                if self.cursor_item[0] != 0:
                    self.cursor_item = [0, 0]
                    self.sfx(SND_CLICK)
            return

        if slot_type == "creative_catalog":
            if idx < len(CREATIVE_CATALOG):
                item_id = CREATIVE_CATALOG[idx]
                is_tool = item_id in NON_STACKABLE
                count = 1 if is_tool else 64
                if is_shift_click:
                    self.add_to_container(self.hotbar, item_id, count)
                    self.sfx(SND_CLICK)
                elif is_right_click:
                    if self.cursor_item[0] == 0:
                        self.cursor_item = [item_id, 1]
                        self.sfx(SND_CLICK)
                    elif self.cursor_item[0] == item_id and not is_tool and self.cursor_item[1] < 64:
                        self.cursor_item[1] += 1
                        self.sfx(SND_CLICK)
                    else:
                        self.cursor_item = [item_id, 1]
                        self.sfx(SND_CLICK)
                else:
                    self.cursor_item = [item_id, count]
                    self.sfx(SND_CLICK)
            return

        if slot_type == "result":
            if self.craft_result[0] != 0:
                res_id, res_cnt = self.craft_result[0], self.craft_result[1]
                if self.cursor_item[0] == 0:
                    self.cursor_item = [res_id, res_cnt]
                    crafting.execute_craft(self.craft_grid, self.craft_size, self.craft_size)
                    self.sfx(SND_CLICK)
                elif self.cursor_item[0] == res_id and self.cursor_item[1] + res_cnt <= 64:
                    self.cursor_item[1] += res_cnt
                    crafting.execute_craft(self.craft_grid, self.craft_size, self.craft_size)
                    self.sfx(SND_CLICK)
            return

        # Target slot
        if slot_type == "grid":
            target = self.craft_grid[idx]
        elif slot_type == "inventory":
            target = self.inventory[idx]
        elif slot_type == "hotbar":
            target = self.hotbar[idx]
        elif slot_type == "armor":
            target = self.player.armor_slots[idx]
        elif slot_type == "offhand":
            target = self.player.offhand_slot
        else:
            return

        # Shift + Left click: quick move or clear
        if is_shift_click and not is_right_click:
            if target[0] != 0 and target[1] > 0:
                lay = self.craft_layout()
                if lay.get("type") == "creative_catalog" and slot_type == "hotbar":
                    # In creative catalog, shift-clicking a hotbar slot clears it
                    target[0], target[1] = 0, 0
                    self.sfx(SND_CLICK)
                    return
                item_id, count = target[0], target[1]
                if slot_type == "hotbar":
                    moved = self.add_to_container(self.inventory, item_id, count)
                    target[1] -= moved
                    if target[1] <= 0: target[0] = 0
                elif slot_type == "inventory":
                    moved = self.add_to_container(self.hotbar, item_id, count)
                    target[1] -= moved
                    if target[1] <= 0: target[0] = 0
                elif slot_type == "grid":
                    moved = self.add_to_container(self.hotbar, item_id, count)
                    leftover = count - moved
                    if leftover > 0:
                        leftover -= self.add_to_container(self.inventory, item_id, leftover)
                    target[1] = leftover
                    if target[1] <= 0: target[0] = 0
                self.sfx(SND_CLICK)
            return

        # Right click: split stack or place single item
        if is_right_click:
            if self.cursor_item[0] == 0:
                if target[0] != 0 and target[1] > 0:
                    take = (target[1] + 1) // 2
                    self.cursor_item = [target[0], take]
                    target[1] -= take
                    if target[1] <= 0: target[0] = 0
                    self.sfx(SND_CLICK)
            else:
                max_stack = 1 if self.cursor_item[0] in NON_STACKABLE else 64
                if target[0] == 0:
                    target[0] = self.cursor_item[0]
                    target[1] = 1
                    self.cursor_item[1] -= 1
                    if self.cursor_item[1] <= 0: self.cursor_item = [0, 0]
                    self.sfx(SND_CLICK)
                elif target[0] == self.cursor_item[0] and target[1] < max_stack:
                    target[1] += 1
                    self.cursor_item[1] -= 1
                    if self.cursor_item[1] <= 0: self.cursor_item = [0, 0]
                    self.sfx(SND_CLICK)
            return

        # Left click: pick up all, place all, or swap
        if self.cursor_item[0] == 0:
            if target[0] != 0 and target[1] > 0:
                self.cursor_item = list(target)
                target[0], target[1] = 0, 0
                self.sfx(SND_CLICK)
        else:
            max_stack = 1 if self.cursor_item[0] in NON_STACKABLE else 64
            if target[0] == 0:
                target[0], target[1] = self.cursor_item[0], self.cursor_item[1]
                self.cursor_item = [0, 0]
                self.sfx(SND_CLICK)
            elif target[0] == self.cursor_item[0]:
                space = max_stack - target[1]
                add = min(space, self.cursor_item[1])
                target[1] += add
                self.cursor_item[1] -= add
                if self.cursor_item[1] <= 0: self.cursor_item = [0, 0]
                self.sfx(SND_CLICK)
            else:
                self.cursor_item, target[0], target[1] = [target[0], target[1]], self.cursor_item[0], self.cursor_item[1]
                self.sfx(SND_CLICK)

    def update_crafting_ui(self):
        if pyxel.btnp(pyxel.KEY_E) or pyxel.btnp(pyxel.KEY_ESCAPE):
            self.close_inventory()
            return

        size = self.craft_size
        res = crafting.check_craft(self.craft_grid, size, size)
        self.craft_result = list(res) if res else [0, 0]

        is_left = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
        is_right = pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT)
        is_shift = pyxel.btn(pyxel.KEY_LSHIFT) or pyxel.btn(pyxel.KEY_RSHIFT)

        if is_left or is_right:
            slot_info = self.get_slot_under_mouse(pyxel.mouse_x, pyxel.mouse_y)
            if slot_info:
                slot_type, idx = slot_info[0], slot_info[1]
                self.handle_slot_click(slot_type, idx, is_right, is_shift)
                res = crafting.check_craft(self.craft_grid, size, size)
                self.craft_result = list(res) if res else [0, 0]

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
        elif self.state == "select_world":
            self.draw_select_world()
        elif self.state == "create_world":
            self.draw_create_world()
        elif self.state == "multiplayer":
            self.draw_multiplayer()
        elif self.state in ("paused", "settings", "resource_packs"):
            self.dim_screen()
            if self.state == "resource_packs":
                title = "Resource Packs"
            elif self.state == "settings":
                title = "Settings"
            else:
                title = "Game paused"
            title_y = self.get_title_y()
            self.center_text(title_y, title, 7, shadow=True, scale=s)
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
            angle = pyxel.frame_count * 0.0015
            # Smooth panorama rotating in place: eliminates 2-second chunk streaming stutter
            eye = (sx / 2, 48.0, sz / 2)
            forward = (math.cos(angle), -0.15, math.sin(angle))
            light, zenith, horizon, sun_dir = sky_at(0.12)
            target = None
        else:
            eye, forward = self.player.eye(), self.player.forward()
            light, zenith, horizon, sun_dir = sky_at(self.time_of_day)
            target = self.target[0] if self.target and self.state == "playing" else None

        rd = self.settings.get("render_distance", 12)
        max_dist = rd * 16.0
        # LOD extends several hundred blocks into the distance (700m to 1000m+)
        lod_max_dist = max(720.0, (rd + 36) * 16.0)
        fog_end = lod_max_dist
        fog_start = max(max_dist, lod_max_dist - 160.0)

        if not self.on_title() and self.player.head_in_water(self.world):
            fog = (tuple(c * light for c in UNDERWATER_FOG), 0.0, 9.0)
        else:
            fog = (horizon, fog_start, fog_end)

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
            render_dist=rd,
            alpha=self.clock.sub_frame_alpha,
            is_title=self.on_title(),
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
        s = self.get_ui_scale()
        logo_scale = 5 * s
        y0 = max(44 * s, pyxel.height // 2 + 4 * s)
        logo_y = y0 - 42 * s
        subtitle_y = y0 - 14 * s
        pyxel.pal(7, 0)
        pyxel.blt(cx, logo_y + 3 * s, 1, 0, 0, 28, 6, colkey=0, scale=logo_scale)
        pyxel.pal()
        pyxel.blt(cx, logo_y, 1, 0, 0, 28, 6, colkey=0, scale=logo_scale)
        self.center_text(subtitle_y, "Voxel Sandbox & Survival", 7, shadow=True, scale=s)
        self.draw_menu()
        self.shadow_text(2 * s, pyxel.height - 8 * s, "PyCraft GPU Edition", 13, scale=s)

    def draw_select_world(self):
        self.dim_screen()
        s = self.get_ui_scale()
        title_y = max(8 * s, pyxel.height // 2 - 70 * s)
        self.center_text(title_y, "Select World", 7, shadow=True, scale=s)

        worlds = self.world_mgr.list_worlds()
        card_w = min(180 * s, pyxel.width - 24 * s)
        card_h = 36 * s
        card_x = (pyxel.width - card_w) // 2
        card_y = title_y + 14 * s

        if worlds:
            idx = max(0, min(self.selected_world_idx, len(worlds) - 1))
            w = worlds[idx]
            pyxel.dither(0.85)
            pyxel.rect(card_x, card_y, card_w, card_h, 1)
            pyxel.dither(1.0)
            pyxel.rectb(card_x, card_y, card_w, card_h, 10)

            name_str = f"[{idx + 1}/{len(worlds)}] {w['name']}"
            self.draw_text(card_x + 6 * s, card_y + 4 * s, name_str, 10, scale=s)

            mode_str = w.get("mode", "survival").capitalize()
            preset_str = w.get("preset", "standard").capitalize().replace("_", " ")
            details = f"Mode: {mode_str} | Preset: {preset_str}"
            self.draw_text(card_x + 6 * s, card_y + 15 * s, details, 7, scale=s)

            seed_str = f"Seed: {w.get('seed', 0)}"
            self.draw_text(card_x + 6 * s, card_y + 25 * s, seed_str, 13, scale=s)
        else:
            pyxel.dither(0.85)
            pyxel.rect(card_x, card_y, card_w, card_h, 1)
            pyxel.dither(1.0)
            pyxel.rectb(card_x, card_y, card_w, card_h, 13)
            self.center_text(card_y + 14 * s, "No saved worlds found.", 7, scale=s)

        self.draw_menu()

    def draw_create_world(self):
        self.dim_screen()
        s = self.get_ui_scale()
        title_y = self.get_title_y()
        self.center_text(title_y, "Create New World", 7, shadow=True, scale=s)
        self.draw_menu()

    def draw_multiplayer(self):
        self.dim_screen()
        s = self.get_ui_scale()
        title_y = max(8 * s, pyxel.height // 2 - 36 * s)
        self.center_text(title_y, "Play Multiplayer", 7, shadow=True, scale=s)
        self.center_text(title_y + 18 * s, "Multiplayer is coming soon!", 10, scale=s)
        self.center_text(title_y + 30 * s, "LAN & Dedicated Servers in development.", 13, scale=s)
        self.draw_menu()

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
        for i, slot_data in enumerate(self.hotbar):
            b_id, cnt = slot_data[0], slot_data[1]
            bx, by = x0 + i * slot, y0
            pyxel.rectb(bx, by, slot, slot, 7 if i == self.selected else 13)
            if b_id > 0 and cnt > 0:
                self.draw_icon(bx + 2 * s, by + 2 * s, b_id, scale=s)
                if cnt > 1:
                    cs = str(cnt)
                    self.draw_text(bx + slot - len(cs) * 4 * s - s, by + slot - 6 * s - s, cs, 7, scale=s)
                max_dur = TOOL_DURABILITY_TABLE.get(b_id)
                if max_dur and len(slot_data) > 2 and slot_data[2] < max_dur:
                    dur = max(0, slot_data[2])
                    ratio = dur / max_dur
                    bar_w = int((slot - 4 * s) * ratio)
                    bar_y = by + slot - 3 * s
                    bar_col = 11 if ratio > 0.5 else (10 if ratio > 0.2 else 8)
                    pyxel.rect(bx + 2 * s, bar_y, slot - 4 * s, s, 0)
                    if bar_w > 0:
                        pyxel.rect(bx + 2 * s, bar_y, bar_w, s, bar_col)

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

        # 10 Armor icons above health bar if armor > 0 (2 armor points per icon)
        armor_pts = getattr(self.player, "armor_points", 0)
        if armor_pts > 0:
            for i in range(10):
                ax = x0 + i * 8 * s
                ay = y0 - 8 * s
                a_val = (i + 1) * 2
                # Armor icon outline
                pyxel.rect(ax + s, ay, 5 * s, 6 * s, 0)
                pyxel.rect(ax, ay + s, 7 * s, 4 * s, 0)
                if armor_pts >= a_val:
                    # Full armor chestplate (metallic gray & highlight)
                    pyxel.rect(ax + s, ay + s, 5 * s, 4 * s, 6)
                    pyxel.rect(ax + 2 * s, ay + s, 3 * s, 2 * s, 7)
                elif armor_pts == a_val - 1:
                    # Half armor icon
                    pyxel.rect(ax + s, ay + s, 2 * s, 4 * s, 6)
                    pyxel.rect(ax + 2 * s, ay + s, s, 2 * s, 7)

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

    def draw_minecraft_panel(self, x, y, w, h):
        s = self.get_ui_scale()
        pyxel.rectb(x, y, w, h, 0)
        pyxel.rect(x + s, y + s, w - 2 * s, h - 2 * s, 6)
        pyxel.rect(x + s, y + s, w - 2 * s, s, 7)
        pyxel.rect(x + s, y + s, s, h - 2 * s, 7)
        pyxel.rect(x + s, y + h - 2 * s, w - 2 * s, s, 5)
        pyxel.rect(x + w - 2 * s, y + s, s, h - 2 * s, 5)

    def draw_slot(self, x, y, size, item_id, count, is_selected=False, is_hovered=False):
        s = self.get_ui_scale()
        pyxel.rect(x, y, size, size, 5)
        pyxel.rect(x, y, size - s, s, 0)
        pyxel.rect(x, y, s, size - s, 0)
        pyxel.rect(x + s, y + size - s, size - s, s, 7)
        pyxel.rect(x + size - s, y + s, s, size - s, 7)
        pyxel.rect(x + s, y + s, size - 2 * s, size - 2 * s, 13)

        if is_hovered:
            pyxel.dither(0.35)
            pyxel.rect(x + s, y + s, size - 2 * s, size - 2 * s, 7)
            pyxel.dither(1.0)
        elif is_selected:
            pyxel.rectb(x, y, size, size, 10)

        if item_id != 0 and count > 0:
            offset = (size - 16 * s) // 2
            self.draw_icon(x + offset, y + offset, item_id, scale=s)
            if count > 1:
                cs = str(count)
                tx = x + size - len(cs) * 4 * s - 2 * s
                ty = y + size - 6 * s - s
                self.draw_text(tx + s, ty + s, cs, 0, scale=s)
                self.draw_text(tx, ty, cs, 7, scale=s)

    def draw_steve_preview(self, x, y, w, h):
        s = self.get_ui_scale()
        pyxel.rect(x, y, w, h, 0)
        pyxel.rect(x + s, y + s, w - 2 * s, h - 2 * s, 1)
        pyxel.rect(x + s, y + h - s, w - 2 * s, s, 7)
        pyxel.rect(x + w - s, y + s, s, h - 2 * s, 7)

        cx = x + w // 2
        cy = y + h // 2
        pyxel.rect(cx - 5 * s, cy - 22 * s, 10 * s, 10 * s, 15)
        pyxel.rect(cx - 5 * s, cy - 22 * s, 10 * s, 3 * s, 4)
        pyxel.pset(cx - 3 * s, cy - 17 * s, 7)
        pyxel.pset(cx + 2 * s, cy - 17 * s, 7)
        pyxel.rect(cx - 6 * s, cy - 12 * s, 12 * s, 14 * s, 12)
        pyxel.rect(cx - 10 * s, cy - 12 * s, 4 * s, 10 * s, 12)
        pyxel.rect(cx - 10 * s, cy - 2 * s, 4 * s, 4 * s, 15)
        pyxel.rect(cx + 6 * s, cy - 12 * s, 4 * s, 10 * s, 12)
        pyxel.rect(cx + 6 * s, cy - 2 * s, 4 * s, 4 * s, 15)
        pyxel.rect(cx - 5 * s, cy + 2 * s, 4 * s, 14 * s, 1)
        pyxel.rect(cx + s, cy + 2 * s, 4 * s, 14 * s, 1)
        pyxel.rect(cx - 5 * s, cy + 14 * s, 4 * s, 2 * s, 5)
        pyxel.rect(cx + s, cy + 14 * s, 4 * s, 2 * s, 5)

    def draw_crafting_arrow(self, x, y):
        s = self.get_ui_scale()
        pyxel.rect(x, y + 3 * s, 14 * s, 6 * s, 5)
        pyxel.rect(x + s, y + 4 * s, 12 * s, 4 * s, 6)
        pyxel.tri(x + 14 * s, y, x + 22 * s, y + 6 * s, x + 14 * s, y + 12 * s, 5)
        pyxel.tri(x + 14 * s, y + s, x + 20 * s, y + 6 * s, x + 14 * s, y + 11 * s, 6)

    def draw_tooltip(self, x, y, text):
        if not text:
            return
        s = self.get_ui_scale()
        tw = len(text) * 4 * s + 6 * s
        th = 10 * s
        tx = min(x + 8 * s, pyxel.width - tw - 2 * s)
        ty = max(2 * s, y - 12 * s)
        pyxel.rect(tx - s, ty - s, tw + 2 * s, th + 2 * s, 0)
        pyxel.rectb(tx, ty, tw, th, 2)
        pyxel.rect(tx + s, ty + s, tw - 2 * s, th - 2 * s, 1)
        self.draw_text(tx + 3 * s, ty + 2 * s, text, 7, scale=s)

    def draw_tab(self, x, y, w, h, text, is_active, is_hovered=False):
        s = self.get_ui_scale()
        tab_h = h + (2 * s if is_active else 0)
        pyxel.rectb(x, y, w, tab_h, 0)
        bg_col = 6 if is_active else (7 if is_hovered else 5)
        pyxel.rect(x + s, y + s, w - 2 * s, tab_h - (s if is_active else 2 * s), bg_col)
        pyxel.rect(x + s, y + s, w - 2 * s, s, 7 if is_active else 6)
        pyxel.rect(x + s, y + s, s, tab_h - 2 * s, 7 if is_active else 6)
        pyxel.rect(x + w - 2 * s, y + s, s, tab_h - 2 * s, 5 if is_active else 0)
        txt_col = 0 if is_active else (7 if is_hovered else 13)
        tx = x + (w - len(text) * 4 * s) // 2
        ty = y + (h - 6 * s) // 2
        self.draw_text(tx, ty, text, txt_col, scale=s)

    def draw_crafting_screen(self):
        self.dim_screen()
        lay = self.craft_layout()
        s, slot_s = lay["s"], lay["slot_s"]
        size = lay["size"]

        slot_under_mouse = self.get_slot_under_mouse(pyxel.mouse_x, pyxel.mouse_y)
        hovered_slot_type = slot_under_mouse[0] if slot_under_mouse else None
        hovered_slot_idx = slot_under_mouse[1] if slot_under_mouse else None

        # Draw tabs if present (in Creative mode)
        if "tab_cat" in lay and "tab_surv" in lay:
            cat_x, cat_y, cat_w, cat_h = lay["tab_cat"]
            surv_x, surv_y, surv_w, surv_h = lay["tab_surv"]
            is_cat_active = (getattr(self, "creative_tab", "catalog") == "catalog")
            self.draw_tab(cat_x, cat_y, cat_w, cat_h, "Items", is_cat_active,
                          is_hovered=(hovered_slot_type == "tab" and hovered_slot_idx == "catalog"))
            self.draw_tab(surv_x, surv_y, surv_w, surv_h, "Survival", not is_cat_active,
                          is_hovered=(hovered_slot_type == "tab" and hovered_slot_idx == "survival"))

        # Main panel
        self.draw_minecraft_panel(lay["px0"], lay["py0"], lay["pw"], lay["ph"])

        if lay.get("type") == "creative_catalog":
            # 1. Creative Catalog Screen
            self.draw_text(lay["px0"] + 8 * s, lay["py0"] + 6 * s, "Item Catalog", 5, scale=s)

            # 5x9 catalog slots
            cat_x0, cat_y0 = lay["cat_x0"], lay["cat_y0"]
            for r in range(lay["cat_rows"]):
                for c in range(lay["cat_cols"]):
                    idx = r * lay["cat_cols"] + c
                    sx, sy = cat_x0 + c * slot_s, cat_y0 + r * slot_s
                    item_id = CREATIVE_CATALOG[idx] if idx < len(CREATIVE_CATALOG) else 0
                    is_hovered = (hovered_slot_type == "creative_catalog" and hovered_slot_idx == idx)
                    self.draw_slot(sx, sy, slot_s, item_id, 1 if item_id else 0, is_hovered=is_hovered)

            # Trash / Destroy slot
            tx, ty = lay["trash_x"], lay["trash_y"]
            is_trash_hovered = (hovered_slot_type == "trash")
            self.draw_slot(tx, ty, slot_s, 0, 0, is_hovered=is_trash_hovered)
            cx, cy = tx + slot_s // 2, ty + slot_s // 2
            for d in range(-3 * s, 4 * s, s):
                pyxel.rect(cx + d, cy + d, s, s, 8)
                pyxel.rect(cx + d, cy - d, s, s, 8)
            self.draw_text(tx - 38 * s, ty + 6 * s, "Destroy", 5, scale=s)

            # Hotbar
            hx0, hy0 = lay["hx0"], lay["hy0"]
            self.draw_text(hx0, hy0 - 9 * s, "Hotbar", 5, scale=s)
            for c in range(9):
                sx, sy = hx0 + c * slot_s, hy0
                slot = self.hotbar[c]
                is_hovered = (hovered_slot_type == "hotbar" and hovered_slot_idx == c)
                self.draw_slot(sx, sy, slot_s, slot[0], slot[1], is_selected=(c == self.selected), is_hovered=is_hovered)

        else:
            # 2. Standard Crafting / Survival Screen
            if size == 3:
                self.draw_text(lay["px0"] + 30 * s, lay["py0"] + 6 * s, "Crafting", 5, scale=s)
            else:
                self.draw_text(lay["px0"] + 88 * s, lay["py0"] + 6 * s, "Crafting", 5, scale=s)
                self.draw_steve_preview(lay["pvx"], lay["pvy"], lay["pvw"], lay["pvh"])
            self.draw_text(lay["ix0"], lay["iy0"] - 10 * s, "Inventory", 5, scale=s)

            gx0, gy0 = lay["gx0"], lay["gy0"]
            for r in range(size):
                for c in range(size):
                    idx = r * size + c
                    sx, sy = gx0 + c * slot_s, gy0 + r * slot_s
                    slot = self.craft_grid[idx]
                    is_hovered = (hovered_slot_type == "grid" and hovered_slot_idx == idx)
                    self.draw_slot(sx, sy, slot_s, slot[0], slot[1], is_hovered=is_hovered)

            self.draw_crafting_arrow(lay["ax"], lay["ay"])

            rx, ry, rw, rh = lay["rx"], lay["ry"], lay["rw"], lay["rh"]
            is_res_hovered = (hovered_slot_type == "result")
            self.draw_slot(rx, ry, rw, self.craft_result[0], self.craft_result[1], is_hovered=is_res_hovered)

            ix0, iy0 = lay["ix0"], lay["iy0"]
            for r in range(3):
                for c in range(9):
                    idx = r * 9 + c
                    sx, sy = ix0 + c * slot_s, iy0 + r * slot_s
                    slot = self.inventory[idx]
                    is_hovered = (hovered_slot_type == "inventory" and hovered_slot_idx == idx)
                    self.draw_slot(sx, sy, slot_s, slot[0], slot[1], is_hovered=is_hovered)

            hx0, hy0 = lay["hx0"], lay["hy0"]
            for c in range(9):
                sx, sy = hx0 + c * slot_s, hy0
                slot = self.hotbar[c]
                is_hovered = (hovered_slot_type == "hotbar" and hovered_slot_idx == c)
                self.draw_slot(sx, sy, slot_s, slot[0], slot[1], is_selected=(c == self.selected), is_hovered=is_hovered)

            if size == 2 and "arm_x0" in lay:
                arm_x0, arm_y0 = lay["arm_x0"], lay["arm_y0"]
                for i in range(4):
                    sx, sy = arm_x0, arm_y0 + i * slot_s
                    slot = self.player.armor_slots[i]
                    is_hovered = (hovered_slot_type == "armor" and hovered_slot_idx == i)
                    self.draw_slot(sx, sy, slot_s, slot[0], slot[1], is_hovered=is_hovered)
                off_x0, off_y0 = lay["off_x0"], lay["off_y0"]
                slot = self.player.offhand_slot
                is_hovered = (hovered_slot_type == "offhand")
                self.draw_slot(off_x0, off_y0, slot_s, slot[0], slot[1], is_hovered=is_hovered)

        # Cursor item & tooltips
        if self.cursor_item[0] != 0 and self.cursor_item[1] > 0:
            mx, my = pyxel.mouse_x, pyxel.mouse_y
            self.draw_icon(mx - 8 * s, my - 8 * s, self.cursor_item[0], scale=s)
            if self.cursor_item[1] > 1:
                cs = str(self.cursor_item[1])
                tx = mx + 4 * s
                ty = my + 2 * s
                self.draw_text(tx + s, ty + s, cs, 0, scale=s)
                self.draw_text(tx, ty, cs, 7, scale=s)
        elif slot_under_mouse:
            if hovered_slot_type == "tab":
                name = "Creative Item Catalog" if hovered_slot_idx == "catalog" else "Survival Inventory"
                self.draw_tooltip(pyxel.mouse_x, pyxel.mouse_y, name)
            elif hovered_slot_type == "trash":
                self.draw_tooltip(pyxel.mouse_x, pyxel.mouse_y, "Destroy Item (Shift: Clear All)")
            elif hovered_slot_type == "creative_catalog":
                if hovered_slot_idx < len(CREATIVE_CATALOG):
                    item_id = CREATIVE_CATALOG[hovered_slot_idx]
                    self.draw_tooltip(pyxel.mouse_x, pyxel.mouse_y, get_item_name(item_id))
            else:
                item_id = 0
                if hovered_slot_type == "grid":
                    item_id = self.craft_grid[hovered_slot_idx][0]
                elif hovered_slot_type == "result":
                    item_id = self.craft_result[0]
                elif hovered_slot_type == "inventory":
                    item_id = self.inventory[hovered_slot_idx][0]
                elif hovered_slot_type == "hotbar":
                    item_id = self.hotbar[hovered_slot_idx][0]
                elif hovered_slot_type == "armor":
                    item_id = self.player.armor_slots[hovered_slot_idx][0]
                elif hovered_slot_type == "offhand":
                    item_id = self.player.offhand_slot[0]

                if item_id > 0:
                    name = get_item_name(item_id)
                    self.draw_tooltip(pyxel.mouse_x, pyxel.mouse_y, name)

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
