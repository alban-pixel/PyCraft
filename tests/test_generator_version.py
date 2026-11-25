"""A world keeps the generator's version it was made with (terrain.GENERATOR_VERSION): the land a
player hasn't changed must not come back different around what they built."""
import os

import numpy as np

from pycraft import terrain as T
from pycraft.blocks import STONE
from pycraft.world import World

DATA = os.path.join(os.path.dirname(__file__), "data")


def test_new_worlds_use_the_current_version(tmp_path):
    world = World(5)
    assert world.version == world.gen.version == T.GENERATOR_VERSION == 2
    world.set(3, 900, 3, STONE)
    world.save(tmp_path / "a.npz")
    back, _ = World.load(tmp_path / "a.npz")
    assert back.version == back.gen.version == 2 and back.get(3, 900, 3) == STONE


def test_saves_from_before_the_versions_keep_version_1(tmp_path):
    World(5).save(tmp_path / "a.npz")
    with np.load(tmp_path / "a.npz") as f:
        data = {k: f[k] for k in f.files if k != "generator"}
    np.savez_compressed(tmp_path / "old.npz", **data)
    back, extra = World.load(tmp_path / "old.npz")
    assert back.version == back.gen.version == 1 and "generator" not in extra
    back.save(tmp_path / "again.npz")
    assert World.load(tmp_path / "again.npz")[0].version == 1


def test_version_1_is_the_generator_of_before():
    """tests/data/generator_v1.npz was sampled with the generator of main 2e9d45b (seed 7)."""
    with np.load(os.path.join(DATA, "generator_v1.npz")) as f:
        biome, top = f["biome"], f["top"]
    xs = (np.arange(64) - 32) * 160.0
    x, z = np.meshgrid(xs, xs, indexing="ij")
    s = T.TerrainGenerator(7, version=1).sample(x, z)
    # (another processor may round a column the other way)
    assert np.mean(s["biome"] == biome) > 0.995
    assert np.mean(np.floor(s["height"]) == top) > 0.995
    assert "shore" not in s and "ice" not in s  # (the blocks then use the old shores and ice)
    assert np.mean(T.TerrainGenerator(7).sample(x, z)["biome"] == biome) < 0.9  # (and version 2 differs)


def test_the_processes_learn_the_version():
    """The builders and the distant terrain's sampler must make the same world as the game."""
    from pycraft import builder, lod
    world = World(5, version=1)
    sent = []

    class Tasks:
        def put(self, msg):
            sent.append(msg)

    b = builder.Builders.__new__(builder.Builders)
    b.generation, b.tasks, b.in_flight = 0, [Tasks()], [set()]
    b.set_world(world)
    assert sent[-1][:5] == ("world", 1, 5, None, 1)
    s = lod.SamplerProcess.__new__(lod.SamplerProcess)
    s.number, s.tasks = 0, Tasks()
    s.current = type("Value", (), {"value": 0})()
    s.configure(world, 2, 128, 7, None)
    assert sent[-1][:5] == ("config", 1, 5, None, 1)
