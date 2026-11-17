import numpy as np

from pycraft.blocks import FACING_VECTORS, PISTON, STONE
from pycraft.terrain import CHUNK
from pycraft.world import SAVE_VERSION, World

SEED = 1234


def test_facing_vectors():
    assert FACING_VECTORS[0] == (0, 1, 0) and FACING_VECTORS[5] == (0, 0, -1)
    assert len(FACING_VECTORS) == 6


def test_state_roundtrip():
    w = World(SEED)
    w.set(5, 600, 7, PISTON, 3)
    assert w.get(5, 600, 7) == PISTON and w.get_state(5, 600, 7) == 3
    assert w.get_state(6, 600, 7) == 0


def test_set_clears_state():
    w = World(SEED)
    w.set(5, 600, 7, PISTON, 3)
    w.set(5, 600, 7, STONE)
    assert w.get_state(5, 600, 7) == 0


def test_state_only_where_needed():
    w = World(SEED)
    w.set(5, 600, 7, STONE)
    assert w.states == {}
    assert w.state_section(0, 600 >> 4, 0) is None
    w.set(5, 600, 7, PISTON, 2)
    assert w.state_section(0, 600 >> 4, 0)[5, 600 & 15, 7] == 2


def test_save_v3_keeps_states(tmp_path):
    w = World(SEED)
    w.set(5, 600, 7, PISTON, 4)
    w.set(-20, 610, 33, STONE)
    path = str(tmp_path / "w.npz")
    w.save(path, extra=np.array([1, 2]))
    loaded, data = World.load(path)
    assert loaded.get(5, 600, 7) == PISTON and loaded.get_state(5, 600, 7) == 4
    assert loaded.get(-20, 610, 33) == STONE and loaded.get_state(-20, 610, 33) == 0
    assert list(data["extra"]) == [1, 2]
    assert SAVE_VERSION == 3


def test_load_v2_save(tmp_path):
    section = np.zeros((CHUNK,) * 3, np.uint8)
    section[1, 2, 3] = PISTON
    path = str(tmp_path / "old.npz")
    np.savez_compressed(path, version=2, seed=SEED, keys=np.array([[0, 40, 0]], np.int64),
                        sections=section[None], player=np.zeros(6))
    w, data = World.load(path)
    assert w.get(1, 40 * CHUNK + 2, 3) == PISTON and w.get_state(1, 40 * CHUNK + 2, 3) == 0
    assert "player" in data
