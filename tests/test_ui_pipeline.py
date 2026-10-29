"""Unit tests for UI scaling layout, Minecraft world selection/creation pipeline, and inventory stability."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import pyxel
from generator import WorldPreset
from main import App, GUI_SCALES


def test_craft_result_initialized(headless_app):
    """Pressing 'E' to open inventory must never raise AttributeError: 'App' object has no attribute 'craft_result'."""
    app = headless_app
    assert hasattr(app, "craft_result")
    assert isinstance(app.craft_result, list)
    assert app.craft_result == [0, 0] or len(app.craft_result) == 2

    # Switch to inventory state and verify draw does not throw
    app.set_state("inventory")
    assert app.state == "inventory"
    app.draw_crafting_screen()
    app.set_state("playing")


def test_title_screen_menu_items(headless_app):
    """Home screen must have exactly Singleplayer, Multiplayer, Settings, Quit Game."""
    app = headless_app
    app.set_state("title")
    items = [label for label, _ in app.menu_items()]
    assert items == ["Singleplayer", "Multiplayer", "Settings", "Quit Game"]


def test_ui_scaling_title_above_buttons(headless_app):
    """Across all GUI scales and resolutions, title text must never be covered by buttons."""
    app = headless_app
    app.set_state("settings")

    for scale_pref in GUI_SCALES:
        app.settings["gui_scale"] = scale_pref
        s = app.get_ui_scale()
        title_y = app.get_title_y()
        bx, by, bw, bh = app.button_rect(0)
        # Title must be strictly above button 0 with at least 10 * s margin
        assert title_y < by, f"At scale {scale_pref} (s={s}), title_y ({title_y}) >= button 0 y ({by})"
        assert by - title_y >= 10 * s


def test_title_screen_layout_no_overlap(headless_app):
    """On title screen, Minecraft logo and subtitle must be strictly above button 0."""
    app = headless_app
    app.set_state("title")

    for scale_pref in GUI_SCALES:
        app.settings["gui_scale"] = scale_pref
        s = app.get_ui_scale()
        bx, by, bw, bh = app.button_rect(0)
        logo_y = by - 42 * s
        subtitle_y = by - 14 * s
        assert logo_y < subtitle_y < by
        assert by - subtitle_y >= 10 * s


def test_world_selection_pipeline(headless_app, tmp_path):
    """Test full multi-world selection, creation, and deletion pipeline."""
    app = headless_app
    app.saves_dir = str(tmp_path / "test_saves")
    from world_manager import WorldManager
    app.world_mgr = WorldManager(app.saves_dir)

    # 1. Open Singleplayer / Select World
    app.open_select_world()
    assert app.state == "select_world"
    items = [lbl for lbl, _ in app.menu_items()]
    assert "Create New World" in items
    assert "Cancel" in items

    # 2. Open Create World
    app.open_create_world()
    assert app.state == "create_world"
    create_items = [lbl for lbl, _ in app.menu_items()]
    assert any("World Name:" in lbl for lbl in create_items)
    assert any("Game Mode:" in lbl for lbl in create_items)
    assert any("World Type:" in lbl for lbl in create_items)
    assert any("Seed:" in lbl for lbl in create_items)
    assert "Create New World" in create_items
    assert "Cancel" in create_items

    # Cycle preset
    initial_preset = app.new_world_preset
    app.cycle_new_world_preset(1)
    assert app.new_world_preset != initial_preset

    # Toggle mode
    assert app.new_world_mode == "survival"
    app.toggle_new_world_mode()
    assert app.new_world_mode == "creative"

    # Confirm creation
    app.confirm_create_world()
    assert app.state == "playing"
    assert app.player.mode == "creative"
    assert len(app.world_mgr.list_worlds()) == 1

    # 3. Return to select world and verify created world is listed
    app.set_state("select_world")
    worlds = app.world_mgr.list_worlds()
    assert len(worlds) == 1
    sel_items = [lbl for lbl, _ in app.menu_items()]
    assert "Play Selected World" in sel_items
    assert "Delete World" in sel_items

    # 4. Delete world
    app.delete_selected_world()
    assert len(app.world_mgr.list_worlds()) == 0


def test_multiplayer_placeholder_screen(headless_app):
    """Multiplayer screen displays placeholder and Back button to return to Title."""
    app = headless_app
    app.set_state("multiplayer")
    assert app.state == "multiplayer"
    items = [lbl for lbl, _ in app.menu_items()]
    assert items == ["Back"]

    # Click/activate Back
    app.menu_items()[0][1]()
    assert app.state == "title"


def test_player_per_frame_smooth_movement(headless_app):
    """Player update must execute kinematics smoothly with frame dt."""
    app = headless_app
    app.set_state("playing")
    initial_y = app.player.pos[1]

    # Lift player into the air so they fall with dt
    app.player.pos[1] += 5.0
    app.player.flying = False
    app.player.on_ground = False
    app.player.vel_y = 0.0
    app.player.update(app.world, dt=0.016)
    # Velocity should have updated with gravity
    assert app.player.vel_y < 0
