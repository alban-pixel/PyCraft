"""Choosing a place on Earth, loading it, playing without internet, and the saves: no window, no
graphics card, no network."""
import hashlib
import os

import numpy as np
import pytest

from pycraft.app import App
from pycraft.earth import places
from pycraft.earth.grid import EarthGrid
from pycraft.earth.tiles import TileStore
from pycraft.survival import CREATIVE, SURVIVAL, BreakProgress, Health, creative_inventory
from pycraft.player import Player
from pycraft.terrain import SEA_LEVEL
from pycraft.ui import Ui
from pycraft.world import World
from tests.earthtiles import write_ground


class Far:
    spacing, size, n_levels = 2, 64, 3

    def levels(self):
        return self.n_levels


class Renderer:
    def __init__(self):
        self.far, self.worlds = Far(), []

    def set_world(self, world):
        self.worlds.append(world)


class Screen(Ui):
    """The interface at a size of its own (the real one asks Pyxel's window)."""
    size = (640, 360)
    width = property(lambda self: self.size[0] // self.scale)
    height = property(lambda self: self.size[1] // self.scale)


class Game(App):
    """The App without its window: what choosing, loading and saving worlds need."""

    def __init__(self, folder):
        self.save_path = os.path.join(folder, "world2.npz")
        self.settings = {"show_help": True, "fps": 60}
        self.renderer, self.ui, self.has_pillow, self.headless = Renderer(), Screen(), True, True
        self.ui.set_screen_size(640, 360)
        self.world, self.slot, self.save_data, self.world_is_fresh = World(5), "normal", None, True
        self.spawn = (0.5, 900.0, 0.5)
        self.player, self.health, self.breaking = Player(*self.spawn), Health(), BreakProgress()
        self.mode = self.new_mode = CREATIVE
        self.inv, self.selected, self.time_of_day = creative_inventory(), 0, 0.05
        self.state, self.menu_index, self.play_time, self.last_save = "title", 0, 0.0, 0.0
        self.title_spot, self.messages, self.last_mouse = [0, 900, 0], [], (0, 0)
        self.init_earth()
        self.new_simulation()

    def make_store(self, root):
        return TileStore(root, start=False)

    def set_state(self, state):
        self.state, self.menu_index = state, 0

    def notify(self, text):
        self.messages.append(text)

    def labels(self):
        return [label for label, _ in self.menu_items()]

    def choose(self, label):
        dict(self.menu_items())[label]()

    def arrive(self, metres=1000.0):
        """The tiles being loaded come."""
        p = self.arriving
        write_ground(p.store.root, p.world.earth, lambda x, z: metres, keys=p.keys)
        for key in p.keys:
            p.store.landed(key, True)
        self.update_earth_loading()

    def fail(self):
        for key in self.arriving.keys:
            if not self.arriving.store.complete([key]):
                self.arriving.store.landed(key, False, offline=True)
        self.update_earth_loading()


@pytest.fixture
def game(tmp_path):
    return Game(str(tmp_path))


def digest(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def test_slot():
    assert places.slot(45.9237, 6.8694) == "+45.9237+006.8694"
    assert places.slot(-21.13, 55.47) == "-21.1300+055.4700"


def test_yaw():
    grid = EarthGrid(45.0, 7.0)
    assert abs(places.yaw_to(grid, 44.0, 7.0)) < 0.01
    assert abs(places.yaw_to(grid, 45.0, 7.1) - 90) < 0.5
    assert abs(places.yaw_to(grid, 45.0, 6.9) - 270) < 0.5
    assert abs(places.yaw_to(grid, 46.0, 7.0) - 180) < 0.01


def test_places():
    assert len(places.PLACES) == 12 and places.PLACES[0].name == "Mont Blanc"
    for p in places.PLACES:
        x, z = EarthGrid(p.lat, p.lon).block(p.look_lat, p.look_lon)
        assert 1000 < np.hypot(x, z) < 30000, p.name  # the view is at a walk or a flight from there
    assert len({places.slot(p.lat, p.lon) for p in places.PLACES}) == 12


def enter(game, label="Mont Blanc", mode="Creative"):
    game.choose("Earth")
    game.choose(label)
    if game.state == "newmode":
        game.choose(mode)
    assert game.state == "earth_loading"


def test_new_place(game):
    enter(game, mode="Survival")
    old = game.world
    assert game.world is old and not game.renderer.worlds  # nothing changes until the tiles are there
    assert 0 <= game.arriving.store.progress(game.arriving.keys) < 1
    game.arrive()
    assert game.state == "loading" and game.mode == SURVIVAL and game.world.earth.lat == 45.9237
    assert game.renderer.worlds == [game.world] and game.world.store is not None
    assert abs(game.player.pos[1] - (SEA_LEVEL + 1001)) < 3
    assert min(game.player.yaw, 360 - game.player.yaw) < 5  # Mont Blanc is to the south
    assert os.path.exists(os.path.join(os.path.dirname(game.save_path), "earth", "+45.9237+006.8694.npz"))


def test_the_finest_and_the_far_tiles_are_waited_for(game):
    enter(game)
    zooms = {z for z, _, _ in game.arriving.keys}
    assert 14 in zooms and min(zooms) <= 10
    ready = set(game.arriving.keys)
    assert set(game.arriving.world.gen.column_tiles(0, 0)) <= ready
    assert set(game.arriving.world.gen.sky_tiles()) <= ready


def test_normal_save_untouched(game):
    game.save()
    game.save_data = game.snapshot()
    before = digest(game.save_path)
    enter(game)
    game.arrive()
    game.world.set(3, 2000, 3, 1)
    game.save()
    game.save_and_title()
    assert digest(game.save_path) == before


def test_back_to_the_normal_world(game):
    game.world.set(3, 2000, 3, 1)
    game.save()
    game.save_data = game.snapshot()
    enter(game)
    game.arrive()
    game.save_and_title()
    assert "Continue" not in game.labels() and "Normal world" in game.labels()
    game.choose("Normal world")
    assert game.slot == "normal" and game.world.earth is None and game.world.get(3, 2000, 3) == 1
    assert game.renderer.worlds[-1] is game.world and game.state == "loading"
    assert game.save_data is None


def test_a_new_normal_world_after_earth(game):
    enter(game)
    game.arrive()
    game.save_and_title()
    assert "Normal world" not in game.labels()  # there is none
    earth_save = os.path.join(os.path.dirname(game.save_path), "earth", "+45.9237+006.8694.npz")
    before = digest(earth_save)
    game.choose("New world")
    game.choose("Creative")
    game.start_game(new_world=True)
    assert game.slot == "normal" and game.world.earth is None and os.path.exists(game.save_path)
    assert digest(earth_save) == before


def test_a_place_already_played_goes_on(game):
    enter(game)
    game.arrive()
    game.player.pos = [40.5, 1600.0, -60.5]
    game.world.set(3, 2000, 3, 1)
    game.save_and_title()
    game.choose("Earth")
    assert "Mont Blanc (saved)" in game.labels() and "Everest" in game.labels()
    game.choose("Mont Blanc (saved)")
    assert game.state == "earth_loading"
    game.update_earth_loading()  # its tiles are on disk: nothing to wait for
    assert game.state == "loading" and game.player.pos == [40.5, 1600.0, -60.5]
    assert game.world.get(3, 2000, 3) == 1 and game.slot == "+45.9237+006.8694"


def test_visited_place_needs_no_network(game, tmp_path):
    enter(game)
    game.arrive()
    game.save_and_title()
    game.choose("Earth")
    game.choose("Mont Blanc (saved)")
    assert game.arriving.store.sent == []  # nothing asked of the network
    game.update_earth_loading()
    assert game.state == "loading"


def test_offline_screen(game):
    enter(game)
    game.fail()
    assert game.state == "earth_offline"
    assert game.labels() == ["Retry", "Play a generated world", "Back"]
    game.choose("Retry")
    assert game.state == "earth_loading"
    game.fail()
    game.choose("Back")
    assert game.state == "title" and game.world.earth is None and game.arriving is None


def test_play_a_generated_world(game):
    enter(game)
    game.fail()
    game.choose("Play a generated world")
    assert game.state == "loading" and game.world.earth is None and game.slot == "generated"
    path = os.path.join(os.path.dirname(game.save_path), "earth", "generated.npz")
    assert os.path.exists(path) and not os.path.exists(game.save_path)
    seed = game.world.seed
    game.save_and_title()
    enter(game)
    game.fail()
    game.choose("Play a generated world")
    assert game.world.seed == seed  # the same one goes on


def test_offline_with_the_ground_there(game):
    """The ground around the player is on disk but not the far view: it can be played."""
    enter(game)
    p = game.arriving
    near = p.near
    write_ground(p.store.root, p.world.earth, lambda x, z: 1000.0, keys=near)
    for key in near:
        p.store.landed(key, True)
    game.fail()
    assert game.labels() == ["Retry", "Play anyway", "Play a generated world", "Back"]
    game.choose("Play anyway")
    assert game.state == "loading" and game.world.earth is not None


def test_broken_earth_save_is_not_overwritten(game):
    folder = os.path.join(os.path.dirname(game.save_path), "earth")
    os.makedirs(folder)
    path = os.path.join(folder, "+45.9237+006.8694.npz")
    with open(path, "wb") as f:
        f.write(b"not a save")
    game.choose("Earth")
    game.choose("Mont Blanc (saved)")
    assert game.state == "places" and game.earth_note
    assert open(path, "rb").read() == b"not a save"


def test_earth_save_without_a_player(game):
    """A save that loads but lacks what a game needs is left alone too."""
    path = os.path.join(os.path.dirname(game.save_path), "earth", "+45.9237+006.8694.npz")
    os.makedirs(os.path.dirname(path))
    from pycraft.earth import Place
    World(5, Place(45.9237, 6.8694, "")).save(path)
    before = digest(path)
    game.choose("Earth")
    game.choose("Mont Blanc (saved)")
    assert game.state == "places" and game.earth_note and digest(path) == before


def test_earth_command(game):
    game.set_state("playing")
    for wrong in ("/earth 85 0", "/earth a b", "/earth 10", "/earth 0 181", "/earth nan 0"):
        game.run_command(wrong)
        assert game.messages[-1] == "Usage: /earth lat lon" and game.state == "playing"
    game.run_command("/earth -16.5 179.99")
    assert game.state == "earth_loading" and game.slot == "normal" and os.path.exists(game.save_path)
    for z, x, y in game.arriving.keys:
        assert 0 <= x < 2 ** z and 0 <= y < 2 ** z
    game.leave_earth_loading()
    assert game.state == "playing" and game.world.earth is None


def test_earth_command_from_one_place_to_another(game):
    enter(game)
    game.arrive()
    first = game.world.store
    game.set_state("playing")
    game.run_command("/earth 27.9957 86.8285")
    game.arrive(5000.0)
    assert game.slot == "+27.9957+086.8285" and game.world.store is not first
    assert len(os.listdir(os.path.join(os.path.dirname(game.save_path), "earth"))) >= 2


def test_without_pillow(game):
    game.has_pillow = False
    assert "Earth (needs Pillow)" in game.labels()
    game.choose("Earth (needs Pillow)")
    assert game.state == "title"


def test_buttons_fit_the_screen(game):
    enter(game)  # (the offline screen at its longest: the ground around is there, the far view isn't)
    for key in game.arriving.near:
        game.arriving.store.landed(key, True)
    game.fail()
    assert len(game.menu_items()) == 4
    for width, height in ((320, 180), (640, 360), (1280, 720)):
        game.ui.size = (width, height)
        game.ui.set_screen_size(width, height)
        for state in ("title", "places", "newmode", "earth_offline"):
            game.state = state
            rects = [game.button_rect(i) for i in range(len(game.menu_items()))]
            for x, y, w, h in rects:
                assert 0 <= x and x + w <= game.ui.width and 0 <= y and y + h <= game.ui.height - 9, (state, height)
            for i, a in enumerate(rects):
                for b in rects[i + 1:]:
                    assert a[0] + a[2] <= b[0] or b[0] + b[2] <= a[0] or a[1] + a[3] <= b[1] or b[1] + b[3] <= a[1]
