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

from pycraft import items, packs, redstone
from pycraft.autoscale import AutoScale
from pycraft.blocks import ATLAS_TILES, BLOCK_TILES, STONE_PRESSURE_PLATE, TILE
from pycraft.controls import Controls
from pycraft.icons import icon_palette, item_atlas
from pycraft.play import Playing
from pycraft.player import Player
from pycraft.render import Renderer
from pycraft.furnace import Furnaces
from pycraft.screens.chat import Chat
from pycraft.screens.earth import EarthScreens
from pycraft.screens.hud import Hud
from pycraft.screens.inventory import Inventory
from pycraft.screens.menus import Menus
from pycraft.screens.screenshot import Screenshots
from pycraft.screens.settings import SettingsScreen
from pycraft.settings import load_item_icons, load_tiles, parse_settings
from pycraft.sim import Simulation
from pycraft.survival import (CREATIVE, SURVIVAL, BreakProgress, Health, convert_old_save,
                              creative_inventory)
from pycraft.inventory import Inventory as Slots
from pycraft.sky import FOG_START, UNDERWATER_FOG, environment, haze, scale
from pycraft.sound import Sound
from pycraft.terrain import SEA_LEVEL
from pycraft.tiles import build_tiles, tiles_to_atlas
from pycraft.ui import BASE_HEIGHT, BASE_WIDTH, BLACK, BRICK, PALETTE, TEXT, Ui, text_width
from pycraft.world import World


SAVE_FILE = "world2.npz"  # "world.npz" holds a world of the older, smaller version: left alone
LOADING_RADIUS = 2  # chunks around the player that must be ready before playing
MAX_DT = 1 / 30  # longest time step: slower frames slow the game down instead of making the player skip
ZOOM_FOV = 22.0  # field of view while the zoom key is held
DIM = 0.5  # brightness of the world behind the menus


class App(Sound, Menus, EarthScreens, SettingsScreen, Inventory, Hud, Chat, Screenshots, Playing):
    """The game: its window, its screens (see the classes it inherits from), its world and renderer."""

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
        self.default_item_tiles = self.item_tiles = items.build_item_tiles()
        icon_colors = self.set_icons(tiles, self.item_tiles)
        pyxel.images[1].cls(0)
        pyxel.images[1].text(0, 0, "PYCRAFT", 7)  # drawn scaled up on the title screen
        self.init_sounds()

        data_dir = pyxel.user_data_dir("PyCraft", "PyCraft GPU")
        self.pack_dirs = packs.pack_dirs(data_dir)
        self.has_pillow = importlib.util.find_spec("PIL") is not None
        self.packs = self.find_packs()
        self.pack_message = ""  # shown under the settings: a pack that couldn't be read
        self.pack_to_apply = False  # a pack chosen in the settings, applied on the next update
        self.save_path = os.path.join(data_dir, SAVE_FILE)  # the normal world's (see slot_path)
        self.slot = "normal"  # the save of the world played: the normal one, or one of the Earth's
        self.init_earth()
        self.settings_path = os.path.join(data_dir, "settings.json")
        self.screenshot_dir = os.path.join(data_dir, "screenshots")
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
        self.mode = CREATIVE
        self.new_mode = CREATIVE  # the next new world's mode (the title menu asks for it)
        self.inv = creative_inventory()  # its slots 0 to 8 are the hotbar
        self.health = Health()
        self.breaking = BreakProgress()
        self.open_screen = None  # the Survival screen shown (inventory, crafting table, furnace), in "screen"
        self.hurt_time = -1.0  # play time the player was last hurt (the screen flashes red)
        self.rng = random.Random()
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
    def find_packs(self):
        """The texture packs on this computer (none without Pillow, which reads their PNGs)."""
        return packs.find_packs(self.pack_dirs, packs.minecraft_jars()) if self.has_pillow else []
    def set_icons(self, tiles, item_tiles):
        """Draw the block icons of these tiles into Pyxel's image bank 0, and the item icons into bank 2;
        returns their 48 colors."""
        icon_colors, icons, item_icons = icon_palette(tiles_to_atlas(tiles), item_atlas(item_tiles))
        for bank_number, image in ((0, icons), (2, item_icons)):
            bank = np.frombuffer(pyxel.images[bank_number].data_ptr(), dtype=np.uint8, count=256 * 256)
            bank.reshape(256, 256)[:image.shape[0], :image.shape[1]] = image
        return icon_colors
    def apply_pack(self, path):
        """Draw the world and the icons with this texture pack (None: the game's own textures).
        Returns a message for the settings: "" when it went well. A pack that can't be read gives
        the game's own textures back, and its path is forgotten."""
        tiles, message, path = load_tiles(path, self.packs, self.default_tiles)
        self.item_tiles = load_item_icons(path, self.packs, self.default_item_tiles)
        self.renderer.set_tiles(tiles)
        self.renderer.palette.set_fixed(self.set_icons(tiles, self.item_tiles))
        self.settings["texture_pack"] = path
        return message
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
        if self.settings["render_scale"] != "auto" or self.state in ("loading", "generating", "earth_loading"):
            return  # (while loading, the frames are slow building the world, not drawing it)
        scale = self.scaler.update(work, self.renderer.gpu_time, 1 / self.settings["fps"])
        self.renderer.set_render_scale(scale)
    def use_palette(self):
        """Give Pyxel the palette the renderer drew the last frame for (it adapts to the view)."""
        if self.renderer.palette.version != self.palette_version:
            pyxel.colors[:] = self.renderer.palette.colors
            self.palette_version = self.renderer.palette.version
    def frames(self, seconds):
        """Number of frames lasting about this long at the current frame rate (for pyxel.btnp)."""
        return max(1, round(seconds * self.settings["fps"]))
    @property
    def hotbar(self):
        """The items of the hotbar's 9 slots (0: empty); change them through self.inv."""
        return [stack[0] for stack in self.inv.slots[:9]]
    def snapshot(self):
        """Everything besides the blocks needed to continue the game later."""
        p = self.player
        return {
            "player": np.array(p.pos + [p.yaw, p.pitch, float(p.flying)]),
            "time_of_day": self.time_of_day,
            "selected": self.selected,
            "ticks": self.sim.pending(),  # the machines' updates still to come
            "mode": self.mode,
            "inventory": self.inv.to_array(),
            "health": self.health.hp,
            "air": self.health.air,
            "spawn": np.array(self.spawn, dtype=float),
            "furnaces": self.furnaces.to_array(),
        }
    def new_simulation(self, pending=None, furnaces=None):
        """The clock of the world's machines (sim.py), for the current world, and its furnaces."""
        self.changes = []  # blocks the machines changed this frame: meshed together, once per section
        self.sim = Simulation(self.world, lambda x, y, z: self.changes.append((x, y, z)))
        redstone.install(self.sim)
        self.sim.every_tick.append(self.feel_plates)
        self.furnaces = Furnaces() if furnaces is None else furnaces
        self.sim.every_tick.append(self.furnaces.tick)
        if pending is not None:
            self.sim.load_pending(pending)
    def feel_plates(self, sim):
        """Tell the simulation where the player stands, for the pressure plates."""
        x, y, z = (math.floor(c) for c in self.player.pos)
        cell = (x, y, z)
        before, sim.occupied = sim.occupied, {cell}
        if cell not in before and self.world.get(*cell) == STONE_PRESSURE_PLATE:
            sim.notify(cell)
    def slot_path(self):
        """The file of the world played."""
        return self.save_path if self.slot == "normal" else self.earth_path(self.slot)
    def save(self):
        path = self.slot_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp.npz"
        self.world.save(tmp, **self.snapshot())
        os.replace(tmp, path)  # replace the old save only once the new one is complete
        self.last_save = self.play_time
        if self.slot == "normal":
            self.world_is_fresh = False
    def use_world(self, world, slot):
        """Go to another world, saved in another file."""
        if self.world is not None and self.world is not world and self.world.store is not None:
            self.world.store.close()
        self.world, self.slot = world, slot
        self.renderer.set_world(world)
    def continue_normal(self):
        """Back to the normal world from one of the Earth's."""
        try:
            world, data = World.load(self.save_path)
        except (OSError, ValueError, KeyError):
            self.notify("This save can't be read")
            return
        self.use_world(world, "normal")
        self.save_data = data
        self.start_game(new_world=False)
    def start_game(self, new_world):
        if new_world:
            if not self.world_is_fresh or self.slot != "normal":
                self.use_world(World(seed=random.randrange(1 << 30)), "normal")
                self.spawn = self.world.find_spawn()
            self.begin_new()
        elif self.save_data is not None:
            self.resume(self.save_data)
        self.started()
    def begin_new(self):
        """A new player at the spawn of a new world."""
        self.player = Player(*self.spawn)
        self.selected, self.time_of_day = 0, 0.05
        self.mode = self.new_mode
        self.inv = Slots() if self.mode == SURVIVAL else creative_inventory()
        self.health.reset()
        self.new_simulation()
        self.save()
    def resume(self, data):
        """The player of a saved world, as they left it."""
        x, y, z, yaw, pitch, flying = data["player"].tolist()
        self.player = Player(x, y, z)
        self.player.yaw, self.player.pitch, self.player.flying = yaw, pitch, bool(flying)
        self.time_of_day = float(data["time_of_day"])
        self.mode, self.inv = convert_old_save(data)
        self.selected = int(data["selected"])
        self.health.reset()
        if "health" in data:  # (a save from before Survival: full health)
            self.health.hp = int(data["health"])
            self.health.air = float(data["air"])
        if "spawn" in data:
            self.spawn = tuple(float(v) for v in np.asarray(data["spawn"]).tolist())
        furnaces = Furnaces.from_array(data["furnaces"]) if "furnaces" in data else None
        self.new_simulation(data.get("ticks"), furnaces)
    def started(self):
        """The world and the player are there: wait for the blocks around, then play."""
        self.save_data = None
        self.player.can_fly = self.mode == CREATIVE
        self.breaking.reset()
        self.open_screen = None
        self.play_time = self.last_save = self.selected_time = 0.0
        self.hurt_time = -1.0
        self.show_help = self.settings["show_help"]
        self.set_state("loading")  # until the blocks around the player are ready
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
        if self.state in ("earth_loading", "earth_offline"):
            return self.arriving.back == "title"
        return self.state in ("title", "newmode", "places") or (
            self.state == "settings" and self.settings_parent == "title")
    def ground_ready(self):
        """Whether the terrain where the player is can be read (on Earth, its tiles may be on their way)."""
        x, _, z = self.player.pos
        return self.world.ready(math.floor(x) >> 4, math.floor(z) >> 4)
    def camera(self):
        """(eye, forward) of the view: the player's, or a slow look around on the title screen."""
        if self.on_title():
            x, _, z = self.title_spot
            ground = max(self.world.surface_y(math.floor(x), math.floor(z)), SEA_LEVEL)
            angle = (time.perf_counter() - self.start_time) * 0.05
            return (x, ground + 30.0, z), (math.sin(angle), -0.2, math.cos(angle))
        return self.player.eye(), self.player.forward()
    def update(self):
        if self.pack_to_apply is not False:  # a texture pack chosen last frame, with its message shown
            path, self.pack_to_apply = self.pack_to_apply, False
            self.pack_message = self.apply_pack(path)
            self.save_settings()
        # Build the world around the camera a little every frame (much more while loading)
        budget = 0.06 if self.state in ("loading", "screenshot") else 0.3 / self.settings["fps"]
        if self.world.store is not None:
            online = not self.world.store.offline
            self.world.store.poll()
            if online and self.world.store.offline and self.state == "playing":
                self.notify("No internet: less detail ahead")
            if not self.on_title():
                self.world.prefetch(self.player.pos[0], self.player.pos[2])
        if self.state != "generating":
            self.renderer.update(self.camera()[0], budget)
        if self.state == "generating":
            self.world_is_fresh = False
            self.start_game(new_world=True)
        elif self.state == "loading":
            if self.ground_ready() and self.renderer.progress(self.player.eye(), LOADING_RADIUS) >= 1:
                self.set_state("playing")
        elif self.state == "screenshot":
            self.update_screenshot(pyxel.btnp(pyxel.KEY_ESCAPE))
        elif self.state == "settings":
            self.update_settings()
        elif self.state == "earth_loading":
            if not self.earth_keys():
                self.update_earth_loading()
        elif self.state in ("places", "earth_offline"):
            if not self.earth_keys():
                self.update_menu()
        elif self.state in ("title", "paused", "newmode", "dead"):
            if self.state == "paused" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.set_state("playing")
            elif self.state == "newmode" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.set_state("title" if self.chosen_place is None else "places")
            else:
                self.update_menu()
        elif self.state == "inventory":
            self.update_inventory()
        elif self.state == "screen":
            self.update_screen()
        elif self.state == "chat":
            self.update_chat()
        else:
            self.update_playing()
    def notify(self, text):
        self.message, self.message_time = text, self.play_time
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
        if self.state in ("title", "newmode"):
            self.draw_title()
        elif self.state == "places":
            self.draw_places()
        elif self.state == "earth_loading":
            self.draw_earth_loading()
        elif self.state == "earth_offline":
            self.draw_offline()
        elif self.state == "loading":
            done = self.renderer.progress(self.player.eye(), LOADING_RADIUS)
            self.draw_message_box(f"Generating terrain... {done * 100:.0f}%", done)
        elif self.state == "paused":
            ui.center_text(self.menu_top() - 26, "Game paused", TEXT, shadow=True, size=2)
            self.draw_menu()
        elif self.state == "dead":
            ui.shade(0, 0, ui.width, ui.height, 0.35, col=BRICK)
            ui.center_text(self.menu_top() - 26, "You died!", TEXT, shadow=True, size=2)
            self.draw_menu()
        elif self.state == "screenshot":
            self.draw_screenshot()
        elif self.state == "settings":
            self.draw_settings()
        else:
            self.draw_hud()
            if self.state == "inventory":
                self.draw_inventory()
            elif self.state == "screen":
                self.open_screen.draw(ui, self.draw_icon, ui.mouse_x, ui.mouse_y, ui.width, ui.height)
            elif self.state == "chat":
                self.draw_chat()
        if not self.mouse_captured and self.state not in ("loading", "earth_loading", "screenshot"):
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
        underwater = not self.on_title() and self.ground_ready() and self.player.head_in_water(self.world)
        if underwater:
            fog = (scale(UNDERWATER_FOG, 0.38 + 0.62 * day), 0.0, 0.0, 9.0)
        else:
            end = self.renderer.view_distance
            fog = (env["horizon"], haze(end), FOG_START * end, end)
        self.renderer.set_environment(**env, fog_color=fog[0], fog_density=fog[1], fog_start=fog[2], fog_end=fog[3])
        self.renderer.underwater = underwater
        dimmed = ("loading", "paused", "settings", "inventory", "screen", "dead", "earth_loading", "earth_offline")
        self.renderer.dim = DIM if self.state in dimmed else 1.0
        self.renderer.render(self.screen, eye, forward, target)
        self.use_palette()
    def draw_icon(self, x, y, item):
        """Draw any item's icon: a block's from image bank 0, another item's from bank 2."""
        if items.is_block(item):
            tile, bank = BLOCK_TILES[item][0], 0
        elif item >= items.FIRST_ITEM:
            tile, bank = item - items.FIRST_ITEM, 2
        else:
            return  # the empty slot
        u, v = (tile % ATLAS_TILES) * TILE, (tile // ATLAS_TILES) * TILE
        self.ui.blt(x, y, bank, u, v, TILE, TILE, 0)


def main():
    App().run()


if __name__ == "__main__":
    main()
