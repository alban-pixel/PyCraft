"""PyCraft GPU: a Minecraft-like game. OpenGL draws the 3D world, Pyxel shows it and runs everything else."""
import json
import math
import os
import random
import time

import moderngl
import numpy as np
import pyxel

from blocks import (ATLAS_TILES, BLOCK_NAMES, BLOCK_TILES, DEFAULT_HOTBAR, PLACEABLE, TILE, UNBREAKABLE, WATER,
                    build_atlas)
from player import Player
from renderer import Renderer
from world import World

BASE_WIDTH, BASE_HEIGHT = 320, 180  # the menus and the mouse speed are designed for this size
RESOLUTIONS = [(320, 180), (384, 216), (480, 270), (640, 360), (800, 450), (960, 540)]
FRAME_RATES = [30, 60, 75, 120, 144, 165, 240]
DEFAULT_SETTINGS = {"resolution": (320, 180), "fps": 60, "music": True}
MAX_DT = 1 / 30  # longest time step: slower frames slow the game down instead of making the player skip
REACH = 6.0
MOUSE_SENSITIVITY = 0.45  # degrees per pixel at 320x180
KEY_LOOK_SPEED = 120.0  # degrees per second with the arrow keys
DAY_SECONDS = 8 * 60  # one full day and night
AUTOSAVE_SECONDS = 120
HELP_SECONDS = 15

# Sky colors (RGB 0-1)
DAY_ZENITH, DAY_HORIZON = (0.38, 0.6, 1.0), (0.68, 0.84, 1.0)
NIGHT_ZENITH, NIGHT_HORIZON = (0.01, 0.01, 0.06), (0.06, 0.08, 0.18)
SUNSET = (1.0, 0.55, 0.3)
UNDERWATER_FOG = (0.08, 0.2, 0.5)

# Sound numbers; sound effects play on channel 3, music on channels 0-2
SND_BREAK, SND_PLACE, SND_JUMP, SND_STEP, SND_SPLASH, SND_CLICK = range(6)
SFX_CHANNEL = 3

HELP = [
    "WASD move  SPACE jump/swim  CTRL sprint  F fly (SPACE/SHIFT up/down)",
    "Left click break  Right click place  1-9/wheel choose  E all blocks",
    "ESC menu and settings  F3 info  H hide help",
]


def make_palette():
    """Pyxel's 16 default colors, then a 6x6x6 RGB cube (used by the 3D view), then 24 greys."""
    cube = [(r * 51) << 16 | (g * 51) << 8 | (b * 51) for r in range(6) for g in range(6) for b in range(6)]
    greys = [v << 16 | v << 8 | v for v in np.linspace(10, 245, 24).astype(int)]
    return list(pyxel.colors)[:16] + cube + greys


def atlas_to_indices(atlas):
    """Nearest color-cube index for every pixel (0 where transparent), for pyxel.blt icons."""
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
    """Light level, sky colors and sun direction. 0 = sunrise, 0.25 = noon, 0.5 = sunset, 0.75 = midnight."""
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
        # Create our OpenGL context before Pyxel's, so Pyxel's context stays the current one.
        # The renderer switches to ours only while it draws.
        ctx = moderngl.create_standalone_context()
        # Pyxel's frame rate can't change once its window is open, so it is set very high and run()
        # paces the frames itself: a new frame rate setting then applies right away.
        # (capture_sec=0: no screen recording, whose buffer would be sized for 1000 frames per second)
        pyxel.init(BASE_WIDTH, BASE_HEIGHT, title="PyCraft", fps=1000, quit_key=pyxel.KEY_NONE,
                   capture_sec=0, headless=headless)
        pyxel.colors[:] = make_palette()
        self.headless = headless

        atlas = build_atlas()
        icons = atlas_to_indices(atlas)
        bank = np.frombuffer(pyxel.images[0].data_ptr(), dtype=np.uint8, count=256 * 256).reshape(256, 256)
        bank[:icons.shape[0], :icons.shape[1]] = icons
        pyxel.images[1].cls(0)
        pyxel.images[1].text(0, 0, "PYCRAFT", 7)  # drawn scaled up on the title screen
        self.init_sounds()

        data_dir = pyxel.user_data_dir("PyCraft", "PyCraft GPU")
        self.save_path = os.path.join(data_dir, "world.npz")
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

        self.player = Player(*self.world.find_spawn())
        self.renderer = Renderer(ctx, self.world, atlas, BASE_WIDTH, BASE_HEIGHT)
        self.set_resolution(*self.settings["resolution"])

        self.state = "title"
        self.settings_parent = "title"  # the menu the settings screen goes back to
        self.menu_index = 0
        self.warp_to_button = False
        self.hotbar = list(DEFAULT_HOTBAR)
        self.selected = 0
        self.target = None  # (block looked at, empty block in front of it)
        self.time_of_day = 0.05
        self.mouse_captured = False
        self.last_mouse = (pyxel.width // 2, pyxel.height // 2)
        self.show_help = True
        self.show_debug = False
        self.play_time = 0.0
        self.last_save = 0.0
        self.message = ""  # short notice shown above the hotbar
        self.message_time = 0.0
        self.dt = 1 / self.settings["fps"]  # seconds since the last frame, measured by run()
        self.fps = 0.0
        self.start_time = self.last_draw = time.perf_counter()
        pyxel.mouse(True)
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
        if isinstance(saved.get("music"), bool):
            settings["music"] = saved["music"]
        return settings

    def save_settings(self):
        with open(self.settings_path, "w", encoding="utf-8") as f:
            json.dump(self.settings, f)

    def set_resolution(self, width, height):
        if (pyxel.width, pyxel.height) != (width, height):
            pyxel.resize(width, height)
        self.renderer.resize(width, height)
        # The screen's pixels move to a new buffer when its size changes
        self.screen = np.frombuffer(pyxel.screen.data_ptr(), dtype=np.uint8, count=width * height)
        self.screen = self.screen.reshape(height, width)
        self.last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

    def change_resolution(self, step):
        on_button = self.button_at(pyxel.mouse_x, pyxel.mouse_y, len(self.menu_items())) == self.menu_index
        i = RESOLUTIONS.index(self.settings["resolution"])
        self.settings["resolution"] = RESOLUTIONS[(i + step) % len(RESOLUTIONS)]
        self.save_settings()
        self.set_resolution(*self.settings["resolution"])
        self.warp_to_button = on_button  # the button moved: put the cursor back on it next frame

    def change_fps(self, step):
        i = FRAME_RATES.index(self.settings["fps"])
        self.settings["fps"] = FRAME_RATES[(i + step) % len(FRAME_RATES)]
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
            self.player = Player(*self.world.find_spawn())
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
        self.set_state("playing")

    # --- States --------------------------------------------------------------------------------

    def set_state(self, state):
        self.state = state
        self.menu_index = 0
        if state == "playing":
            self.capture_mouse()
        else:
            self.mouse_captured = False
            pyxel.mouse(True)

    def capture_mouse(self):
        self.mouse_captured = True
        if not self.headless:
            pyxel.mouse(False)
            pyxel.set_mouse_pos(pyxel.width / 2, pyxel.height / 2)
        self.last_mouse = (pyxel.mouse_x, pyxel.mouse_y)

    def on_title(self):
        """True on the title screen and on the settings screen opened from it."""
        return self.state == "title" or (self.state == "settings" and self.settings_parent == "title")

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
        self.set_state("title")

    def save_and_quit(self):
        self.save()
        pyxel.quit()

    # --- Update --------------------------------------------------------------------------------

    def update(self):
        if self.state == "generating":
            self.world_is_fresh = False
            self.start_game(new_world=True)
        elif self.state in ("title", "paused", "settings"):
            if self.state == "paused" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.set_state("playing")
            elif self.state == "settings" and pyxel.btnp(pyxel.KEY_ESCAPE):
                self.close_settings()
            else:
                self.update_menu()
        elif self.state == "inventory":
            self.update_inventory()
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

    @staticmethod
    def button_rect(i):
        w, h = 120, 13
        return (pyxel.width - w) // 2, pyxel.height // 2 + 2 + i * 17, w, h

    def button_at(self, mx, my, count):
        for i in range(count):
            x, y, w, h = self.button_rect(i)
            if x <= mx < x + w and y <= my < y + h:
                return i
        return None

    @staticmethod
    def inventory_slot(i):
        cols, size = 7, TILE + 6
        x0 = (pyxel.width - cols * size) // 2
        return x0 + (i % cols) * size, pyxel.height // 2 - 40 + (i // cols) * size, size

    def update_inventory(self):
        if pyxel.btnp(pyxel.KEY_E) or pyxel.btnp(pyxel.KEY_ESCAPE):
            self.set_state("playing")
            return
        self.update_hotbar_keys()
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            for i, block in enumerate(PLACEABLE):
                x, y, size = self.inventory_slot(i)
                if x <= pyxel.mouse_x < x + size and y <= pyxel.mouse_y < y + size:
                    self.hotbar[self.selected] = block
                    self.sfx(SND_CLICK)

    def update_hotbar_keys(self):
        for i in range(len(self.hotbar)):
            if pyxel.btnp(pyxel.KEY_1 + i):
                self.selected = i
        if pyxel.mouse_wheel:
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
                pyxel.mouse(True)
            else:
                self.capture_mouse()
        if pyxel.btnp(pyxel.KEY_H):
            self.show_help = not self.show_help
        if pyxel.btnp(pyxel.KEY_F3):
            self.show_debug = not self.show_debug

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
                self.renderer.block_changed(x, z)
                self.sfx(SND_BREAK)
        elif self.target and pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT, hold=hold, repeat=repeat):
            x, y, z = self.target[1]
            block = self.hotbar[self.selected]
            free = self.world.inside(x, y, z) and self.world.get(x, y, z) in (0, WATER)
            if free and (block == WATER or not self.player.overlaps(x, y, z)):
                self.world.set(x, y, z, block)
                self.renderer.block_changed(x, z)
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

    def notify(self, text):
        self.message, self.message_time = text, self.play_time

    # --- Draw ----------------------------------------------------------------------------------

    def draw(self):
        now = time.perf_counter()
        self.fps = self.fps * 0.9 + 0.1 / max(now - self.last_draw, 1e-6)
        self.last_draw = now

        if self.state == "generating":
            pyxel.cls(0)
            self.center_text(pyxel.height // 2 - 3, "Generating world...", 7)
            return

        self.draw_world()
        if self.state == "title":
            self.draw_title()
        elif self.state in ("paused", "settings"):
            self.dim_screen()
            self.center_text(pyxel.height // 2 - 24, "Game paused" if self.state == "paused" else "Settings", 7)
            self.draw_menu()
            if self.state == "settings":
                self.center_text(pyxel.height - 10, "Click or LEFT/RIGHT to change, ESC to go back", 13)
        else:
            self.draw_hud()
            if self.state == "inventory":
                self.draw_inventory()

    def draw_world(self):
        if self.on_title():
            # Slowly circle above the world
            sx, _, sz = self.world.size
            angle = (time.perf_counter() - self.start_time) * 0.12
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
        self.renderer.set_environment(light, zenith, horizon, sun_dir, *fog)
        self.renderer.render(self.screen, eye, forward, target)

    def draw_title(self):
        cx, h = pyxel.width // 2, pyxel.height
        scale = 5 * h // BASE_HEIGHT  # the logo grows with the resolution
        y = h * 48 // BASE_HEIGHT - 3  # blt scales the 28x6 logo around its center
        shadow = scale * 3 // 5
        pyxel.pal(7, 0)
        pyxel.blt(cx - 14 + shadow, y + shadow, 1, 0, 0, 28, 6, colkey=0, scale=scale)
        pyxel.pal()
        pyxel.blt(cx - 14, y, 1, 0, 0, 28, 6, colkey=0, scale=scale)
        self.center_text(h // 2 - 24, "A Minecraft-like game made with Pyxel", 7, shadow=True)
        self.draw_menu()
        self.shadow_text(2, h - 8, f"Seed {self.world.seed}", 13)

    def draw_menu(self):
        items = self.menu_items()
        for i, (label, _) in enumerate(items):
            x, y, w, h = self.button_rect(i)
            selected = i == self.menu_index
            pyxel.dither(0.75)
            pyxel.rect(x, y, w, h, 5 if selected else 1)
            pyxel.dither(1.0)
            pyxel.rectb(x, y, w, h, 7 if selected else 13)
            if self.state == "settings" and selected and i < len(items) - 1:  # arrows on a setting
                pyxel.text(x + 4, y + 4, "<", 10)
                pyxel.text(x + w - 7, y + 4, ">", 10)
            self.center_text(y + 4, label, 10 if selected else 7)

    @staticmethod
    def dim_screen():
        pyxel.dither(0.5)
        pyxel.rect(0, 0, pyxel.width, pyxel.height, 0)
        pyxel.dither(1.0)

    def draw_hud(self):
        w, h = pyxel.width, pyxel.height
        if self.player.head_in_water(self.world):
            pyxel.dither(0.3)
            pyxel.rect(0, 0, w, h, 5)
            pyxel.dither(1.0)

        cx, cy = w // 2, h // 2
        pyxel.line(cx - 4, cy, cx + 4, cy, 7)
        pyxel.line(cx, cy - 4, cx, cy + 4, 7)

        # Hotbar
        slot = TILE + 4
        x0 = (w - slot * len(self.hotbar)) // 2
        y0 = h - slot - 3
        pyxel.dither(0.5)
        pyxel.rect(x0 - 1, y0 - 1, slot * len(self.hotbar) + 2, slot + 2, 0)
        pyxel.dither(1.0)
        for i, block in enumerate(self.hotbar):
            self.draw_icon(x0 + i * slot + 2, y0 + 2, block)
            pyxel.rectb(x0 + i * slot, y0, slot, slot, 7 if i == self.selected else 13)
        self.center_text(y0 - 8, BLOCK_NAMES[self.hotbar[self.selected]], 7, shadow=True)
        if self.message and self.play_time - self.message_time < 2.5:
            self.center_text(y0 - 16, self.message, 10, shadow=True)

        y = 2
        if self.show_debug:
            px, py, pz = self.player.pos
            hours = int((self.time_of_day * 24 + 6) % 24)
            lines = [f"FPS {self.fps:4.0f} / {self.settings['fps']}  {w}x{h}",
                     f"XYZ {px:5.1f} {py:5.1f} {pz:5.1f}",
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
        self.dim_screen()
        size = TILE + 6
        rows = math.ceil(len(PLACEABLE) / 7)
        x, y, _ = self.inventory_slot(0)
        pyxel.rect(x - 4, y - 14, 7 * size + 8, rows * size + 18, 1)
        pyxel.rectb(x - 4, y - 14, 7 * size + 8, rows * size + 18, 13)
        self.center_text(y - 10, "Click a block to put it in the selected slot", 7)
        hovered = None
        for i, block in enumerate(PLACEABLE):
            x, y, size = self.inventory_slot(i)
            over = x <= pyxel.mouse_x < x + size and y <= pyxel.mouse_y < y + size
            if over:
                hovered = block
            pyxel.rectb(x, y, size, size, 7 if over else 5)
            self.draw_icon(x + 3, y + 3, block)
        if hovered is not None:
            self.center_text(y + size + 8, BLOCK_NAMES[hovered], 10, shadow=True)

    @staticmethod
    def draw_icon(x, y, block):
        tile = BLOCK_TILES[block][0]
        u, v = (tile % ATLAS_TILES) * TILE, (tile // ATLAS_TILES) * TILE
        pyxel.blt(x, y, 0, u, v, TILE, TILE, colkey=0)

    def center_text(self, y, s, col, shadow=False):
        x = (pyxel.width - len(s) * 4) // 2
        if shadow:
            self.shadow_text(x, y, s, col)
        else:
            pyxel.text(x, y, s, col)

    @staticmethod
    def shadow_text(x, y, s, col):
        pyxel.text(x + 1, y + 1, s, 0)
        pyxel.text(x, y, s, col)


if __name__ == "__main__":
    App().run()
