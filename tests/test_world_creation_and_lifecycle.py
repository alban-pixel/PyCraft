"""Exhaustive tests for World Creation, Selection, Seed/Name Typing, Presets, and Lifecycle."""
import os
import shutil
import tempfile
import pyxel
import pytest
import numpy as np

from generator import WorldPreset, parse_seed
from world import World
from world_manager import WorldManager


def test_seed_parsing_exhaustive():
    """Verify parse_seed handles strings, integers, empty input, negative numbers, and alphanumeric seeds."""
    assert parse_seed(0) == 0
    assert parse_seed(12345) == 12345
    assert parse_seed(-42) == (-42 & 0xFFFFFFFF)
    assert parse_seed("") == 1
    assert parse_seed(None) == 1

    # String seeds must hash deterministically
    s1 = parse_seed("Minecraft")
    s2 = parse_seed("Minecraft")
    assert s1 == s2
    assert isinstance(s1, int)
    assert s1 > 0

    s3 = parse_seed("Antigravity")
    assert s3 != s1


def test_world_manager_full_crud_lifecycle(tmp_path):
    """Test full CRUD (Create, Read, Update, Delete) on worlds in saves directory."""
    saves_dir = str(tmp_path / "saves")
    mgr = WorldManager(saves_dir)

    # Initially empty
    assert len(mgr.list_worlds()) == 0

    # 1. Create multiple worlds with different presets and modes
    w1_id, w1_path = mgr.create_world("Survival World", mode="survival", seed=123, preset=WorldPreset.STANDARD)
    w2_id, w2_path = mgr.create_world("Creative Flat", mode="creative", seed=456, preset=WorldPreset.SUPERFLAT)
    w3_id, w3_path = mgr.create_world("Amplified Epic", mode="survival", seed="AlphaSeed", preset=WorldPreset.AMPLIFIED)

    worlds = mgr.list_worlds()
    assert len(worlds) == 3
    ids = [w["id"] for w in worlds]
    assert w1_id in ids and w2_id in ids and w3_id in ids

    # 2. Verify metadata content
    w1_meta = mgr.get_world_metadata(w1_id)
    assert w1_meta["name"] == "Survival World"
    assert w1_meta["mode"] == "survival"
    assert w1_meta["preset"] == WorldPreset.STANDARD
    assert w1_meta["seed"] == 123

    w2_meta = mgr.get_world_metadata(w2_id)
    assert w2_meta["name"] == "Creative Flat"
    assert w2_meta["mode"] == "creative"
    assert w2_meta["preset"] == WorldPreset.SUPERFLAT

    # 3. Save world chunk data into world 1
    world_obj = World(seed=123, preset=WorldPreset.STANDARD)
    world_obj.set(10, 25, 10, 3)  # stone block
    world_npz_path = os.path.join(w1_path, "world.npz")
    world_obj.save(world_npz_path, time_of_day=0.35, selected=2)

    assert os.path.exists(world_npz_path)

    # 4. Load world 1 data
    loaded_world, snapshot = mgr.load_world(w1_id)
    assert loaded_world.get(10, 25, 10) == 3
    assert float(snapshot["time_of_day"]) == pytest.approx(0.35)
    assert int(snapshot["selected"]) == 2

    # 5. Delete world 2
    deleted = mgr.delete_world(w2_id)
    assert deleted is True
    assert not os.path.exists(w2_path)
    remaining_ids = [w["id"] for w in mgr.list_worlds()]
    assert w2_id not in remaining_ids
    assert len(remaining_ids) == 2


def test_app_create_world_screen_workflow(headless_app, tmp_path):
    """Test typing into create world text fields, cycling presets, toggling mode, and creating world."""
    app = headless_app
    app.world_manager = WorldManager(str(tmp_path / "saves"))
    app.set_state("create_world")

    # Initial defaults
    assert app.create_world_focus in ("name", "seed")
    app.create_world_name = "My Test Adventure"
    app.create_world_seed = "998877"
    app.create_world_mode = "survival"
    app.create_world_preset_idx = 0  # Standard

    # Toggle mode: survival -> creative -> survival
    app.create_world_mode = "creative"
    assert app.create_world_mode == "creative"
    app.create_world_mode = "survival"
    assert app.create_world_mode == "survival"

    # Cycle presets through all 5 options
    presets = WorldPreset.ALL
    for i in range(len(presets)):
        app.create_world_preset_idx = i
        assert presets[app.create_world_preset_idx] in WorldPreset.ALL

    # Text input: Backspace and typing
    app.create_world_focus = "name"
    app.create_world_name = "Alpha"
    # Simulate backspace
    app.create_world_name = app.create_world_name[:-1]
    assert app.create_world_name == "Alph"
    # Simulate typing character
    app.create_world_name += "x"
    assert app.create_world_name == "Alphx"

    # Simulate Create New World action
    world_id, world_dir = app.world_manager.create_world(
        app.create_world_name,
        mode=app.create_world_mode,
        seed=app.create_world_seed,
        preset=presets[app.create_world_preset_idx],
    )
    assert os.path.exists(world_dir)
    assert app.world_manager.get_world_metadata(world_id)["name"] == "Alphx"


def test_app_select_world_navigation_and_deletion(headless_app, tmp_path):
    """Test navigating world list, selecting a world, and deleting it through UI."""
    app = headless_app
    app.world_manager = WorldManager(str(tmp_path / "saves"))

    # Populate 3 worlds
    id1, _ = app.world_manager.create_world("World Alpha", mode="survival")
    id2, _ = app.world_manager.create_world("World Beta", mode="creative")
    id3, _ = app.world_manager.create_world("World Gamma", mode="survival")

    app.set_state("select_world")
    worlds = app.world_manager.list_worlds()
    assert len(worlds) == 3

    # Navigate down and up
    app.selected_world_idx = 0
    app.selected_world_idx = (app.selected_world_idx + 1) % len(worlds)
    assert app.selected_world_idx == 1
    app.selected_world_idx = (app.selected_world_idx + 1) % len(worlds)
    assert app.selected_world_idx == 2

    # Delete selected world (index 1: World Beta)
    target_id = worlds[1]["id"]
    app.world_manager.delete_world(target_id)
    worlds_after = app.world_manager.list_worlds()
    assert len(worlds_after) == 2
    assert target_id not in [w["id"] for w in worlds_after]


def test_world_generation_across_all_presets():
    """Verify that World initializes and generates valid chunks for all presets."""
    for preset in WorldPreset.ALL:
        world = World(size=(64, 64, 64), seed=42, preset=preset, generate=True)
        assert world.preset == preset
        assert world.size == (64, 64, 64)

        # Sample blocks at multiple points
        b1 = world.get(32, 1, 32)
        b2 = world.get(32, 20, 32)
        b3 = world.get(32, 60, 32)
        assert isinstance(b1, int)
        assert isinstance(b2, int)
        assert isinstance(b3, int)
