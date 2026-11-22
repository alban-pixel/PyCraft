"""Nothing in the game waits for the Earth's tiles: it only goes where they are."""
import numpy as np
import pytest

from pycraft.earth import Place
from pycraft.earth.tiles import TileStore, save_tile
from pycraft.lod import sample_step
from pycraft.play import Playing
from pycraft.player import FAST_FLY_SPEED, Player
from pycraft.render.chunks import Chunks
from pycraft.render.far import FarTerrain
from pycraft.world import World


class Store:
    """The tiles are the chunks themselves: those west of `edge` are there."""

    def __init__(self, edge=5):
        self.edge, self.asked, self.changes, self.looked = edge, [], 0, 0

    def missing(self, keys):
        self.looked += 1
        return [k for k in keys if k[0] > self.edge]

    def want(self, keys):
        self.asked.append(list(keys))


@pytest.fixture
def world():
    w = World(3)
    w.store = Store()
    w.gen.column_tiles = lambda cx, cz: [(cx, cz)]
    w.gen.level_tiles = lambda x0, z0, x1, z1, step: [(x1 // 16, 0)]
    return w


def test_procedural_always_ready():
    w = World(3)
    assert w.store is None and w.ready(10 ** 6, 5) and w.level_ready(0, 0, 10 ** 6, 10, 8)
    w.prefetch(0, 0)  # nothing to do


def test_ready_and_asks(world):
    assert world.ready(5, 0) and world.store.asked == []
    assert not world.ready(6, 0) and world.store.asked == [[(6, 0)]]


def test_not_ready_is_only_looked_at_again_when_a_tile_lands(world):
    world.ready(6, 0)
    looked = world.store.looked
    assert not world.ready(6, 0) and world.store.looked == looked
    world.store.edge, world.store.changes = 6, 1
    assert world.ready(6, 0)


def test_real_store_counts_what_lands(tmp_path):
    store = TileStore(tmp_path, start=False)
    before = store.changes
    store.landed((6, 1, 1), True)
    assert store.changes > before


def test_prefetch_wants_two_tiles_ahead(tmp_path):
    world = World(3, Place(45.0, 7.0, str(tmp_path)))
    world.store = TileStore(tmp_path, start=False)
    world.prefetch(0.0, 0.0)
    fine = {k for batch in world.store.sent for k in batch if k[0] == 14}
    assert len({tx for _, tx, _ in fine}) >= 5 and len({ty for _, _, ty in fine}) >= 5
    sent = len(world.store.sent)
    world.prefetch(1.0, 1.0)
    assert len(world.store.sent) == sent


class Builders:
    def __init__(self):
        self.columns, self.jobs = [], []

    def finished(self):
        return [], []

    def busy(self, key):
        return False

    def request_columns(self, keys):
        self.columns += keys

    def request(self, camera, jobs):
        self.jobs += [job[0] for job in jobs]


def chunks_of(world, radius=3):
    c = Chunks.__new__(Chunks)
    c.world, c.builders, c.radius = world, Builders(), radius
    c.meshes, c.built, c.pending, c.preparing, c.versions, c.asked_columns = {}, {}, {}, {}, {}, set()
    return c


def test_chunks_skip_unready(world):
    c = chunks_of(world)
    c.update((5 * 16 + 8.0, 600.0, 8.0), 0.01)
    assert c.builders.jobs and max(k[0] for k in c.builders.jobs) == 5
    assert c.builders.columns and max(k[0] for k in c.builders.columns) == 5
    world.store.edge, world.store.changes = 50, 1
    c.update((5 * 16 + 8.0, 600.0, 8.0), 0.01)
    assert max(k[0] for k in c.builders.columns) == 8


def test_far_level_keeps_its_grid_until_its_tiles_are_there(world):
    class Sampler:
        requests = []

        def finished(self):
            return []

        def request(self, batch, origins, edits):
            self.requests.append((batch, list(origins)))

    f = FarTerrain.__new__(FarTerrain)
    f.world, f.sampler, f.spacing, f.size, f.n_levels = world, Sampler(), 2, 64, 3
    f.origins, f.working, f.pending, f.edits, f.view_distance = [None] * 3, False, 0, set(), 10 ** 6
    world.store.edge = 4  # enough for the first level around (0, 0), not for the others
    f.update((0.0, 600.0, 0.0))
    batch, origins = f.sampler.requests[-1]
    assert {b[0] for b in batch} == {0} and origins[0] == (-32, -32) and origins[1:] == [None, None]
    f.working = False
    world.store.edge, world.store.changes = 10 ** 6, 1
    f.update((0.0, 600.0, 0.0))
    batch, origins = f.sampler.requests[-1]
    assert {1, 2} <= {b[0] for b in batch} and None not in origins


def test_sample_step():
    assert [sample_step(s) for s in (1, 2, 4, 512)] == [1, 1, 2, 256]


class Keys:
    def __init__(self, *held):
        self.keys = held

    def held(self, key):
        return key in self.keys

    def pressed(self, key):
        return False


class Game(Playing):
    def __init__(self, world, player):
        self.world, self.player, self.notes = world, player, []

    def notify(self, text):
        self.notes.append(text)


def fly(game, frames, dt=1 / 30):
    for _ in range(frames):
        before = list(game.player.pos)
        game.player.update(game.world, dt, Keys("forward", "sprint"))
        game.keep_to_ready_ground(before)


def flyer(yaw=90.0):
    p = Player(5 * 16 - 30.0, 3000.0, 8.0)
    p.yaw, p.flying = yaw, True
    return p


def test_player_is_held_at_the_edge(world):
    game = Game(world, flyer())
    fly(game, 200)
    assert 6 * 16 - FAST_FLY_SPEED / 30 - 1 < game.player.pos[0] < 6 * 16
    assert "Loading the terrain..." in game.notes
    world.store.edge, world.store.changes = 50, 1
    fly(game, 30)
    assert game.player.pos[0] > 6 * 16 + 20


def test_game_thread_never_generates_unready(world):
    columns = world.gen.columns

    def checked(keys):
        assert all(cx <= 5 + 3 for cx, _ in keys), keys  # (a ready chunk answers for those 3 around it)
        return columns(keys)

    world.gen.columns = checked
    game = Game(world, flyer())
    game.player.pos[1] = 700.0
    for _ in range(40):
        fly(game, 5)
        world.raycast(game.player.eye(), game.player.forward(), 6.0)
