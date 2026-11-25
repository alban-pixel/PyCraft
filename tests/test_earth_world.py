"""A world that knows its place on Earth; a normal world stays what it was."""
import hashlib
import pickle
import platform
import sys

import numpy as np
import pytest

from pycraft import terrain as T
from pycraft.blocks import COAL_ORE, GRAVEL, STONE
from pycraft.earth import Place
from pycraft.world import World


@pytest.mark.skipif((sys.platform, platform.machine()) != ("darwin", "arm64"),
                    reason="the last bit of a noise may differ on another computer")
@pytest.mark.parametrize("seed, digest", [
    (7, "5579937ad70abf24ffd885f18dd76b23e6a060b4cf91c23267e7f34eaa35766c"),
    (424242, "014e3338d747aaaa497e9b18cefb48fa7f3a5945455e76a89db1b3de53169fc8")])
def test_procedural_unchanged(seed, digest):
    """The blocks of four whole columns, as they were before worlds could be on Earth."""
    world, h = World(seed), hashlib.sha256()
    for cx, cz in ((0, 0), (5, -3), (-40, 12), (300, 300)):
        for cy in range(4096 // 16):
            s = world.section(cx, cy, cz)
            h.update(bytes([s]) if isinstance(s, int) else s.tobytes())
    assert h.hexdigest() == digest


def test_place_travels_between_processes(tmp_path):
    place = Place(45.9, 6.9, str(tmp_path))
    assert pickle.loads(pickle.dumps(place)) == place


def test_save_load_earth(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "make_generator", lambda seed, earth, version=None: T.TerrainGenerator(seed))
    world = World(5, Place(45.9, 6.9, str(tmp_path)))
    world.set(3, 900, 3, STONE)
    world.save(tmp_path / "a.npz", mode=1)
    back, data = World.load(tmp_path / "a.npz", root="somewhere")
    assert back.earth == Place(45.9, 6.9, "somewhere") and back.seed == 5
    assert back.get(3, 900, 3) == STONE and "earth" not in data and int(data["mode"]) == 1


def test_save_load_normal(tmp_path):
    world = World(5)
    world.save(tmp_path / "a.npz")
    with np.load(tmp_path / "a.npz") as f:
        assert "earth" not in f.files
    assert World.load(tmp_path / "a.npz")[0].earth is None


def test_height():
    assert T.WORLD_HEIGHT == 10240
    world = World(5)
    world.set(0, 9400, 0, STONE)
    assert world.get(0, 9400, 0) == STONE
    assert world.inside(0, 10239, 0) and not world.inside(0, 10240, 0)


class Raised(T.TerrainGenerator):
    """Flat stone country at 5000 blocks, its ores moved up by `by`."""
    by = 4000

    def sample(self, x, z, clim=None, spacing=1):
        s = super().sample(x, z, clim)
        s["height"] = np.full_like(s["height"], 5000.0)
        s["water"] = np.full_like(s["water"], -1)
        return s

    def shift(self, heights):
        return self.by


def count_coal(by):
    gen = Raised(3)
    gen.by = by
    cols = {(c.cx, c.cz): c for c in gen.columns([(x, z) for x in (-1, 0, 1) for z in (-1, 0, 1)])}
    sections = [gen.section(cols, 0, cy, 0) for cy in range(4500 // 16, 4800 // 16)]
    return sum(int((s == COAL_ORE).sum()) for s in sections if not isinstance(s, int))


def test_shift_moves_ores():
    assert count_coal(4000) > 0
    assert count_coal(0) == 0


def test_rocky_slopes_are_stone_and_gravel():
    n = np.array([[0.0, 0.5]])
    s = {"biome": np.full((1, 2), T.ROCKY), "water": np.full((1, 2), -1), "temperature": np.full((1, 2), -0.4),
         "humidity": np.zeros((1, 2))}
    s["moss"] = np.zeros((1, 2), bool)
    surface, filler, _ = T._surface(s, np.full((1, 2), 3000), np.zeros((1, 2)), n)
    assert surface.tolist() == [[STONE, GRAVEL]]
    assert T.BIOME_NAMES[T.ROCKY] == "Rocky slopes" and T.CANOPY[T.ROCKY] == 0


def test_moss_needs_the_place_to_have_it():
    s = {"biome": np.full((1, 1), T.PLAINS), "water": np.full((1, 1), -1), "temperature": np.zeros((1, 1)),
         "humidity": np.zeros((1, 1))}
    args = np.full((1, 1), 900), np.zeros((1, 1)), np.full((1, 1), 0.2)
    mossy = T._surface(dict(s), *args)[0]
    assert (T._surface(dict(s, moss=np.ones((1, 1), bool)), *args)[0] == mossy).all()
    assert (T._surface(dict(s, moss=np.zeros((1, 1), bool)), *args)[0] != mossy).all()


def test_the_processes_learn_the_place(tmp_path):
    """The builders and the distant terrain's sampler must make the same world as the game."""
    from pycraft import builder, lod
    world = World(5)
    world.earth = Place(1.0, 2.0, "r")
    sent = []

    class Tasks:
        def put(self, msg):
            sent.append(msg)

    b = builder.Builders.__new__(builder.Builders)
    b.generation, b.tasks, b.in_flight = 0, [Tasks()], [set()]
    b.set_world(world)
    assert sent[-1][:4] == ("world", 1, 5, Place(1.0, 2.0, "r"))
    s = lod.SamplerProcess.__new__(lod.SamplerProcess)
    s.number, s.tasks = 0, Tasks()
    s.current = type("Value", (), {"value": 0})()
    s.configure(world, 2, 128, 7, None)
    assert sent[-1][:4] == ("config", 1, 5, Place(1.0, 2.0, "r"))
