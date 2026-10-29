"""Unit tests for the WorldManager multi-world save system."""
import os
import shutil
import tempfile
import pytest

from world_manager import WorldManager


@pytest.fixture
def temp_saves_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_world_manager_creation_and_listing(temp_saves_dir):
    mgr = WorldManager(temp_saves_dir)
    assert mgr.list_worlds() == []

    # Create world 1
    w1 = mgr.create_world_entry("Alpha World", "survival", "standard", 123)
    assert os.path.exists(os.path.dirname(w1["save_path"]))
    # Put a dummy file to emulate world.npz existing
    with open(w1["save_path"], "wb") as f:
        f.write(b"dummy")

    # Create world 2
    w2 = mgr.create_world_entry("Creative Build", "creative", "superflat", 456)
    with open(w2["save_path"], "wb") as f:
        f.write(b"dummy")

    worlds = mgr.list_worlds()
    assert len(worlds) == 2
    names = [w["name"] for w in worlds]
    assert "Alpha World" in names
    assert "Creative Build" in names


def test_world_deletion(temp_saves_dir):
    mgr = WorldManager(temp_saves_dir)
    w = mgr.create_world_entry("To Delete", "survival", "standard", 789)
    with open(w["save_path"], "wb") as f:
        f.write(b"dummy")

    assert len(mgr.list_worlds()) == 1
    deleted = mgr.delete_world(w["folder"])
    assert deleted is True
    assert len(mgr.list_worlds()) == 0
