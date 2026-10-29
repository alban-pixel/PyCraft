"""Exhaustive tests for All Menus, Settings, Resolutions, Framerates, Audio, Hotkeys, and UI States."""
import json
import math
import os
import pyxel
import pytest
import numpy as np

from main import (
    BASE_WIDTH, BASE_HEIGHT, RESOLUTIONS, FRAME_RATES, FOVS,
    RENDER_DISTANCES, GUI_SCALES, SENSITIVITIES
)
from generator import WorldPreset
from renderer import Renderer
from world import World
from world_manager import WorldManager


def test_settings_all_fields_and_persistence(headless_app, tmp_path):
    """Test loading, modifying, and saving all settings options in JSON."""
    app = headless_app
    app.settings_path = str(tmp_path / "settings.json")

    # Verify default structure
    assert "resolution" in app.settings
    assert "fps" in app.settings
    assert "fov" in app.settings
    assert "gui_scale" in app.settings
    assert "render_distance" in app.settings
    assert "music" in app.settings
    assert "sensitivity" in app.settings
    assert "fullscreen" in app.settings

    # Modify all settings
    app.settings["fps"] = 144
    app.settings["fov"] = 90
    app.settings["render_distance"] = 12
    app.settings["gui_scale"] = "3x"
    app.settings["music"] = False
    app.settings["sensitivity"] = 0.35
    app.settings["resolution"] = (1920, 1080)
    app.save_settings()

    assert os.path.exists(app.settings_path)
    loaded = app.load_settings()
    assert loaded["fps"] == 144
    assert loaded["fov"] == 90
    assert loaded["render_distance"] == 12
    assert loaded["gui_scale"] == "3x"
    assert loaded["music"] is False
    assert loaded["sensitivity"] == 0.35
    assert loaded["resolution"] == (1920, 1080)


def test_settings_resolution_cycling_including_2k(headless_app):
    """Test resolution cycling forward and backward across all resolutions up to 2K (2560x1440)."""
    app = headless_app
    assert (2560, 1440) in RESOLUTIONS
    assert (1920, 1080) in RESOLUTIONS

    app.settings["resolution"] = RESOLUTIONS[0]
    app.change_resolution(1)
    assert app.settings["resolution"] == RESOLUTIONS[1]

    # Cycle all the way to 2K and wrap around
    for _ in range(len(RESOLUTIONS)):
        app.change_resolution(1)

    assert app.settings["resolution"] == RESOLUTIONS[1]

    # Reverse cycle
    app.change_resolution(-1)
    assert app.settings["resolution"] == RESOLUTIONS[0]


def test_settings_fps_and_render_distance_cycling(headless_app):
    """Test framerate (FPS) and render distance cycling with clamping/wrapping."""
    app = headless_app
    assert 60 in FRAME_RATES and 144 in FRAME_RATES and 240 in FRAME_RATES

    app.settings["fps"] = 60
    app.change_fps(1)
    assert app.settings["fps"] == FRAME_RATES[(FRAME_RATES.index(60) + 1) % len(FRAME_RATES)]

    # Render distance cycling: 2, 4, 6, 8, 12, 16
    app.settings["render_distance"] = 4
    app.change_render_distance(1)
    assert app.settings["render_distance"] == 6
    app.change_render_distance(-1)
    assert app.settings["render_distance"] == 4


def test_settings_fov_and_gui_scale_cycling(headless_app):
    """Test FOV and GUI scale step changes."""
    app = headless_app

    # FOV cycling
    app.settings["fov"] = 70
    app.change_fov(1)
    assert app.settings["fov"] == 80
    app.change_fov(-1)
    assert app.settings["fov"] == 70

    # GUI scale: Auto, 1x, 2x, 3x, 4x
    app.settings["gui_scale"] = "Auto"
    app.change_gui_scale(1)
    assert app.settings["gui_scale"] == "1x"
    app.change_gui_scale(1)
    assert app.settings["gui_scale"] == "2x"
    app.change_gui_scale(-1)
    assert app.settings["gui_scale"] == "1x"


def test_settings_audio_mouse_and_fullscreen_toggles(headless_app):
    """Test toggling audio, mouse sensitivity, and fullscreen."""
    app = headless_app

    # Music toggle
    init_mus = app.settings["music"]
    app.toggle_music()
    assert app.settings["music"] != init_mus
    app.toggle_music()
    assert app.settings["music"] == init_mus

    # Mouse sensitivity cycling
    app.settings["sensitivity"] = 0.25
    app.change_sensitivity(1)
    assert app.settings["sensitivity"] == SENSITIVITIES[(SENSITIVITIES.index(0.25) + 1) % len(SENSITIVITIES)]
    app.change_sensitivity(-1)
    assert app.settings["sensitivity"] == 0.25

    # Fullscreen toggle
    init_fs = app.fullscreen_enabled
    app.toggle_fullscreen()
    assert app.fullscreen_enabled != init_fs
    app.toggle_fullscreen()
    assert app.fullscreen_enabled == init_fs


def test_all_game_states_menu_items(headless_app, tmp_path):
    """Verify menu_items returns valid non-empty items for every single game menu state."""
    app = headless_app
    app.world_manager = WorldManager(str(tmp_path / "saves"))

    # 1. Title
    app.set_state("title")
    items = app.menu_items()
    labels = [lbl for lbl, _ in items]
    assert "Singleplayer" in labels
    assert "Settings" in labels

    # 2. Select World (empty)
    app.set_state("select_world")
    items = app.menu_items()
    labels = [lbl for lbl, _ in items]
    assert "Create New World" in labels
    assert "Cancel" in labels

    # Select World (with worlds)
    app.world_manager.create_world("Alpha Adventure", mode="survival")
    app.world_manager.create_world("Beta Creative", mode="creative")
    items = app.menu_items()
    labels = [lbl for lbl, _ in items]
    assert "Play Selected World" in labels
    assert "Delete World" in labels

    # 3. Create World
    app.set_state("create_world")
    items = app.menu_items()
    labels = [lbl for lbl, _ in items]
    assert any("World Name" in l for l in labels)
    assert any("Game Mode" in l for l in labels)
    assert any("World Type" in l for l in labels)
    assert any("Seed" in l for l in labels)
    assert "Create New World" in labels

    # 4. Multiplayer Placeholder
    app.set_state("multiplayer")
    items = app.menu_items()
    labels = [lbl for lbl, _ in items]
    assert "Back" in labels

    # 5. Settings
    app.set_state("settings")
    items = app.menu_items()
    assert len(items) >= 8
    labels = [lbl for lbl, _ in items]
    assert any("Resolution" in l for l in labels)
    assert any("Frame rate" in l for l in labels)
    assert any("Render Distance" in l for l in labels)
    assert any("Field of view" in l for l in labels)
    assert any("GUI Scale" in l for l in labels)
    assert any("Done" in l for l in labels)

    # 6. Paused
    app.set_state("paused")
    items = app.menu_items()
    labels = [lbl for lbl, _ in items]
    assert "Resume" in labels
    assert "Settings" in labels
    assert "Save and go to title" in labels


def test_pause_menu_workflow(headless_app, tmp_path):
    """Test pause menu actions: resuming, opening settings, and saving/quitting to title."""
    app = headless_app
    app.world_manager = WorldManager(str(tmp_path / "saves"))
    w_id, w_dir = app.world_manager.create_world("Pause Test", mode="survival")
    app.save_path = os.path.join(w_dir, "world.npz")
    app.current_world_info = app.world_manager.get_world_metadata(w_id)
    app.start_game(new_world=True, mode="survival", preset="standard", seed=101)

    assert app.state == "playing"
    assert app.mouse_captured is True

    # Pause the game
    app.set_state("paused")
    assert app.state == "paused"
    assert app.mouse_captured is False

    # Action 1: Resume
    app.set_state("playing")
    assert app.state == "playing"
    assert app.mouse_captured is True

    # Pause again and open settings
    app.set_state("paused")
    app.open_settings()
    assert app.state == "settings"
    assert app.settings_parent == "paused"
    app.close_settings()
    assert app.state == "paused"

    # Action 3: Save and Quit to Title
    app.save_and_title()
    assert app.state == "title"
    assert os.path.exists(app.save_path)


def test_game_over_and_respawn_workflow(headless_app, tmp_path):
    """Test dying in survival mode, entering game_over, and respawning at spawn."""
    app = headless_app
    app.world_manager = WorldManager(str(tmp_path / "saves"))
    app.start_game(new_world=True, mode="survival", preset="standard", seed=202)

    spawn_pos = list(app.player.pos)
    app.player.pos = [spawn_pos[0] + 50, spawn_pos[1], spawn_pos[2] + 50]

    # Deal fatal damage
    app.player.take_damage(100)
    assert app.player.health == 0

    # Trigger game over
    app.update()
    assert app.state == "game_over"

    # Respawn
    app.respawn_player()
    assert app.state == "playing"
    assert app.player.health == app.player.max_health
    assert app.player.pos[0] == pytest.approx(spawn_pos[0], abs=1.0)
    assert app.player.pos[2] == pytest.approx(spawn_pos[2], abs=1.0)


def test_button_rect_and_button_at_hit_testing(headless_app):
    """Test UI button bounds calculation and mouse hit testing."""
    app = headless_app
    app.set_state("title")
    items = app.menu_items()

    for i in range(len(items)):
        x, y, w, h = app.button_rect(i)
        assert w > 0 and h > 0
        # Button center must hit button i
        hit = app.button_at(x + w / 2, y + h / 2, len(items))
        assert hit == i

    # Point outside all buttons must return None
    assert app.button_at(-100, -100, len(items)) is None
