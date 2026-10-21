import os
import sys
import tempfile
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import blocks
from world import World


def test_world_initialization():
    w = World(size=(16, 32, 16), seed=123, generate=False)
    assert w.size == (16, 32, 16)
    assert w.blocks.shape == (18, 34, 18)
    assert w.inner.shape == (16, 32, 16)
    assert np.all(w.inner == blocks.AIR)


def test_world_get_set():
    w = World(size=(16, 32, 16), seed=123, generate=False)
    assert w.get(5, 5, 5) == blocks.AIR
    w.set(5, 5, 5, blocks.STONE)
    assert w.get(5, 5, 5) == blocks.STONE
    assert w.is_solid(5, 5, 5)

    # Outside bounds
    assert not w.inside(-1, 0, 0)
    assert not w.inside(16, 0, 0)
    assert w.get(-1, 0, 0) == blocks.AIR
    assert w.is_solid(-1, 0, 0)  # boundary wall is solid


def test_world_raycast():
    w = World(size=(16, 32, 16), seed=123, generate=False)
    w.set(5, 5, 8, blocks.STONE)
    hit = w.raycast(origin=(5.5, 5.5, 2.0), direction=(0.0, 0.0, 1.0), reach=10.0)
    assert hit is not None
    target, previous = hit
    assert target == (5, 5, 8)
    assert previous == (5, 5, 7)


def test_world_save_and_load():
    w = World(size=(16, 32, 16), seed=42, generate=False)
    w.set(2, 3, 4, blocks.DIAMOND_ORE)
    w.set(7, 8, 9, blocks.GOLD_ORE)

    with tempfile.NamedTemporaryFile(suffix=".npz", delete=False) as tmp:
        path = tmp.name

    try:
        w.save(path, custom_field="hello")
        loaded_w, data = World.load(path)
        assert loaded_w.size == (16, 32, 16)
        assert loaded_w.seed == 42
        assert loaded_w.get(2, 3, 4) == blocks.DIAMOND_ORE
        assert loaded_w.get(7, 8, 9) == blocks.GOLD_ORE
        assert str(data["custom_field"]) == "hello"
    finally:
        if os.path.exists(path):
            os.remove(path)
