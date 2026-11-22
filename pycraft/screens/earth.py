"""The real Earth: choosing a place, waiting for its tiles, and what to do without internet."""
import math
import os
import random
from dataclasses import dataclass

import pyxel

from pycraft.earth import Place, places
from pycraft.earth.tiles import TileStore
from pycraft.lod import sample_step
from pycraft.ui import AMBER, TEXT, TEXT_DIM
from pycraft.world import World

SPAWN_REACH = 480  # blocks around a place where the spawn is looked for, and what building it needs
ROWS = 6  # places in a column of the list
PANEL_W, PANEL_H = 312, 166  # the list's panel
CREDITS = "Data: Terrain Tiles (Mapzen, AWS), CHELSA. See docs/CREDITS.md"


@dataclass
class Arriving:
    """A world whose tiles are on their way; the one before stays until they are there."""
    world: World
    data: object  # of its save, or None for a new world
    look: object  # (lat, lon) a new player looks at, or None
    slot: str
    store: object
    near: list  # the tiles the player's surroundings need
    keys: list  # all the view's
    back: str  # the state to go back to


class EarthScreens:
    """The App's screens for the real Earth."""

    def init_earth(self):
        self.arriving = None
        self.chosen_place = None  # the Spot that waits for its game mode
        self.earth_note = ""  # shown under the list of places

    def earth_dir(self):
        """Where the Earth's worlds are saved, and the tiles kept."""
        return os.path.join(os.path.dirname(self.save_path), "earth")

    def earth_path(self, slot):
        return os.path.join(self.earth_dir(), slot + ".npz")

    def make_store(self, root):
        return TileStore(root)

    # --- Choosing a place ------------------------------------------------------------------------

    def open_places(self):
        self.earth_note, self.chosen_place = "", None
        self.set_state("places")

    def place_items(self):
        items = []
        for spot in places.PLACES:
            saved = os.path.exists(self.earth_path(places.slot(spot.lat, spot.lon)))
            items.append((spot.name + (" (saved)" if saved else ""), lambda spot=spot: self.choose_place(spot)))
        return items + [("Back", lambda: self.set_state("title"))]

    def choose_place(self, spot):
        if os.path.exists(self.earth_path(places.slot(spot.lat, spot.lon))):
            self.begin_earth(spot.lat, spot.lon)
        else:
            self.chosen_place = spot
            self.set_state("newmode")

    def place_rect(self, i):
        ui, top = self.ui, self.places_top()
        if i >= len(places.PLACES):  # Back, under the two columns
            return (ui.width - 80) // 2, top + 26 + ROWS * 18 + 2, 80, 15
        return (ui.width - 288) // 2 + i // ROWS * 148, top + 26 + i % ROWS * 18, 140, 15

    def places_top(self):
        return (self.ui.height - PANEL_H) // 2

    # --- Going there -----------------------------------------------------------------------------

    def begin_earth(self, lat, lon, look=None):
        """Get the tiles of a place, then go there: where the player left it, or as a new world."""
        slot = places.slot(lat, lon)
        path = self.earth_path(slot)
        data = None
        if os.path.exists(path):
            try:
                world, data = World.load(path, root=self.earth_dir())
                if world.earth is None:
                    raise ValueError("not a world on Earth")
                x, _, z = (float(v) for v in data["player"][:3])
            except Exception:  # noqa: BLE001 - whatever is wrong with the file, it is left as it is
                self.earth_note = "This save can't be read"
                self.notify(self.earth_note)
                return
            near = world.gen.column_tiles(math.floor(x) >> 4, math.floor(z) >> 4)
        else:
            world = World(random.randrange(1 << 30), Place(lat, lon, self.earth_dir()))
            x = z = 0.0
            near = world.gen.area_tiles(-SPAWN_REACH, -SPAWN_REACH, SPAWN_REACH, SPAWN_REACH)
        keys = near + world.gen.tiles_ahead(x, z) + world.gen.sky_tiles() + self.view_tiles(world, x, z)
        back = "playing" if self.state == "playing" else "title"
        self.arriving = Arriving(world, data, look, slot, self.make_store(self.earth_dir()), list(dict.fromkeys(near)),
                                 list(dict.fromkeys(keys)), back)
        self.arriving.store.want(self.arriving.keys)
        self.set_state("earth_loading")

    def view_tiles(self, world, x, z):
        """The tiles of every level of the distant terrain around a block."""
        far, keys = self.renderer.far, []
        for level in range(far.levels()):
            spacing = far.spacing << level
            half = (far.size // 2 + 1) * spacing
            keys += world.gen.level_tiles(x - half, z - half, x + half, z + half, sample_step(spacing))
        return keys

    def update_earth_loading(self):
        p = self.arriving
        p.store.poll()
        if p.store.complete(p.keys):
            self.enter_earth()
        elif p.store.ready(p.keys):  # all tried, and some won't come
            self.set_state("earth_offline")

    def enter_earth(self):
        p, self.arriving = self.arriving, None
        p.world.store = p.store
        self.use_world(p.world, p.slot)
        if p.data is not None:
            self.resume(p.data)
        else:
            self.spawn = p.world.find_spawn()
            self.begin_new()
            if p.look is not None:
                self.player.yaw = places.yaw_to(p.world.gen.grid, *p.look, self.spawn[0], self.spawn[2])
        self.started()

    def leave_earth_loading(self):
        p, self.arriving = self.arriving, None
        p.store.close()
        self.set_state(p.back)

    # --- Without internet --------------------------------------------------------------------------

    def offline_items(self):
        p = self.arriving
        items = [("Retry", self.retry_earth)]
        if p.store.complete(p.near):
            items.append(("Play anyway", self.enter_earth))
        return items + [("Play a generated world", self.play_generated), ("Back", self.leave_earth_loading)]

    def retry_earth(self):
        p = self.arriving
        p.store.retry()
        p.store.want(p.keys)
        self.set_state("earth_loading")

    def play_generated(self):
        """A usual world, in a save of its own: the same one each time."""
        p, self.arriving = self.arriving, None
        p.store.close()
        path, data = self.earth_path("generated"), None
        if os.path.exists(path):
            try:
                world, data = World.load(path)
            except Exception:  # noqa: BLE001 - whatever is wrong with the file, it is left as it is
                self.notify("This save can't be read")
                self.set_state(p.back)
                return
        else:
            world = World(random.randrange(1 << 30))
        self.use_world(world, "generated")
        if data is not None:
            self.resume(data)
        else:
            self.spawn = world.find_spawn()
            self.begin_new()
        self.started()

    # --- The command ---------------------------------------------------------------------------------

    def earth_command(self, words):
        """/earth lat lon"""
        try:
            lat, lon = (float(v) for v in words)
            if not (abs(lat) <= 84 and abs(lon) <= 180):
                raise ValueError
        except ValueError:
            self.notify("Usage: /earth lat lon")
            return
        if not self.has_pillow:
            self.notify("The Earth needs Pillow")
            return
        self.save()
        self.new_mode = self.mode
        self.begin_earth(lat, lon)

    # --- Drawing ---------------------------------------------------------------------------------------

    def draw_places(self):
        ui = self.ui
        top = self.places_top()
        ui.panel((ui.width - PANEL_W) // 2, top, PANEL_W, PANEL_H)
        ui.center_text(top + 6, "The real Earth", TEXT, shadow=True)
        ui.center_text(top + 15, "One block is one metre. Anywhere else: /earth lat lon", TEXT_DIM)
        self.draw_menu()
        if self.earth_note:
            ui.center_text(top + PANEL_H - 11, self.earth_note, AMBER)
        else:
            ui.center_text(top + PANEL_H - 11, CREDITS, TEXT_DIM)

    def draw_earth_loading(self):
        p = self.arriving
        done = p.store.progress(p.keys)
        self.draw_message_box(f"Downloading the Earth... {done * 100:.0f}%", done)
        self.ui.center_text(self.ui.height // 2 + 28, "ESC to go back", TEXT, shadow=True)

    def draw_offline(self):
        ui = self.ui
        top = self.menu_top() - 34
        ui.panel((ui.width - 200) // 2, top, 200, 34 + len(self.menu_items()) * 19 + 4)
        ui.center_text(top + 9, "No internet", TEXT, shadow=True)
        ui.center_text(top + 20, "Some of this place is not on this computer", TEXT_DIM)
        self.draw_menu()

    def earth_keys(self):
        """Escape, and the arrows between the two columns of places."""
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            if self.arriving is not None:
                self.leave_earth_loading()
            else:
                self.set_state("title")
            return True
        if self.state == "places" and self.menu_index < len(places.PLACES):
            if pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_LEFT):
                self.menu_index = (self.menu_index + ROWS) % len(places.PLACES)
        return False
