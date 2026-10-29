import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import pyxel
from main import App, GUI_SCALES, RESOLUTIONS, detect_screen_resolution


def test_fullscreen_toggle(headless_app):
    app = headless_app
    initial_fs = app.fullscreen_enabled

    app.toggle_fullscreen()
    assert app.fullscreen_enabled != initial_fs
    assert app.settings["fullscreen"] == app.fullscreen_enabled

    # Toggle back
    app.toggle_fullscreen()
    assert app.fullscreen_enabled == initial_fs
    assert app.settings["fullscreen"] == initial_fs


def test_ui_scale_calculation(headless_app):
    app = headless_app
    app.settings["gui_scale"] = "Auto"

    # Base 320x180 -> scale 1
    app.set_resolution(320, 180)
    assert app.get_ui_scale() == 1

    # 640x360 -> scale 2
    app.set_resolution(640, 360)
    assert app.get_ui_scale() == 2

    # 960x540 -> scale 3
    app.set_resolution(960, 540)
    assert app.get_ui_scale() == 3

    # 1280x720 -> scale 4
    app.set_resolution(1280, 720)
    assert app.get_ui_scale() == 4

    # Manual override preference
    app.settings["gui_scale"] = "1x"
    assert app.get_ui_scale() == 1
    app.settings["gui_scale"] = "3x"
    assert app.get_ui_scale() == 3

    # Reset
    app.settings["gui_scale"] = "Auto"
    app.set_resolution(320, 180)


def test_change_gui_scale(headless_app):
    app = headless_app
    app.settings["gui_scale"] = "Auto"

    app.change_gui_scale(1)
    assert app.settings["gui_scale"] == "1x"
    app.change_gui_scale(1)
    assert app.settings["gui_scale"] == "2x"
    app.change_gui_scale(-1)
    assert app.settings["gui_scale"] == "1x"

    app.settings["gui_scale"] = "Auto"


def test_button_rect_scaling(headless_app):
    app = headless_app
    for res in [(320, 180), (640, 360), (960, 540)]:
        app.set_resolution(*res)
        w, h = res
        s = app.get_ui_scale()
        # Button 0
        bx, by, bw, bh = app.button_rect(0)
        assert bw == 140 * s
        assert bh == 13 * s
        assert 0 <= bx < w
        assert bx + bw <= w
        assert 0 <= by < h

    app.set_resolution(320, 180)


def test_craft_layout_alignment(headless_app):
    app = headless_app
    for res in [(320, 180), (640, 360), (960, 540)]:
        app.set_resolution(*res)
        lay = app.craft_layout()
        s = lay["s"]
        assert lay["rx"] + lay["rw"] <= res[0]
        assert lay["ix0"] + 9 * lay["slot_s"] <= res[0]
        assert lay["iy0"] >= 0

    app.set_resolution(320, 180)


def test_scaled_text_drawing(headless_app):
    app = headless_app
    # Draw scaled text and shadow text across scales 1, 2, 3
    for s in [1, 2, 3]:
        app.draw_text(10, 10, "High DPI Scaling Test", 7, scale=s)
        app.shadow_text(10, 30, "Shadow Text Test", 10, scale=s)
        app.center_text(50, "Centered Text Test", 12, shadow=True, scale=s)


def test_2k_resolution_available_and_resize(headless_app):
    """2K (2560x1440) is in RESOLUTIONS and can be set successfully."""
    app = headless_app
    assert (2560, 1440) in RESOLUTIONS
    app.set_resolution(2560, 1440)
    assert pyxel.width == 2560
    assert pyxel.height == 1440
    assert app.get_ui_scale() >= 4

    # Restore base resolution
    app.set_resolution(320, 180)


def test_render_distance_settings(headless_app):
    """Render distance can be cycled in settings and is visible in menu items."""
    app = headless_app
    app.set_state("settings")

    initial_rd = app.settings["render_distance"]
    app.change_render_distance(1)
    assert app.settings["render_distance"] != initial_rd

    items = [label for label, _ in app.menu_items()]
    assert any("Render Distance:" in lbl and "Chunks" in lbl for lbl in items)

    # Restore default
    app.settings["render_distance"] = 4
    app.set_state("title")


def test_hotbar_with_tool_durability_draw_hud(headless_app):
    """Hotbar slots with 3 elements [item_id, count, durability] must not raise ValueError in draw_hud."""
    app = headless_app
    import blocks
    # Slot 0 has a damaged stone pickaxe [item_id, count, durability]
    app.hotbar[0] = [blocks.ITEM_STONE_PICKAXE, 1, 65]
    app.hotbar[1] = [blocks.ITEM_IRON_SWORD, 1, 10]
    app.set_state("playing")

    # Must draw without throwing ValueError: too many values to unpack
    app.draw_hud()

    # Reset
    app.hotbar[0] = [blocks.GRASS, 64]
    app.hotbar[1] = [blocks.DIRT, 64]
    app.set_state("title")


def test_detect_screen_resolution_returns_valid_dimensions():
    """detect_screen_resolution must return a positive (width, height) tuple."""
    w, h = detect_screen_resolution()
    assert isinstance(w, int) and w >= 640
    assert isinstance(h, int) and h >= 360


def test_fullscreen_switches_to_max_screen_resolution(headless_app, monkeypatch):
    """Entering fullscreen must automatically set resolution to MAX screen resolution and scale GUI."""
    app = headless_app
    app.set_resolution(640, 360)
    app.settings["resolution"] = (640, 360)
    app.fullscreen_enabled = False

    # Mock screen detection to a high-res display (e.g. 1512x982 MacBook or 1920x1080)
    monkeypatch.setattr(app, "detect_screen_resolution", lambda: (1920, 1080))

    # Toggle to fullscreen
    app.toggle_fullscreen()
    assert app.fullscreen_enabled is True
    assert app.settings["resolution"] == (1920, 1080)
    assert pyxel.width == 1920
    assert pyxel.height == 1080
    assert app.get_ui_scale() == 6

    # Toggle back to windowed
    app.toggle_fullscreen()
    assert app.fullscreen_enabled is False
    assert app.settings["resolution"] == (640, 360)
    assert pyxel.width == 640
    assert pyxel.height == 360
    assert app.get_ui_scale() == 2

    # Clean up
    app.set_resolution(320, 180)
    app.settings["resolution"] = (320, 180)


def test_settings_menu_shows_max_tag_for_display_resolution(headless_app, monkeypatch):
    """Settings menu must tag the display's maximum resolution with [MAX]."""
    app = headless_app
    monkeypatch.setattr(app, "detect_screen_resolution", lambda: (1920, 1080))

    app.set_state("settings")
    app.set_resolution(1920, 1080)
    app.settings["resolution"] = (1920, 1080)

    items = app.menu_items()
    labels = [lbl for lbl, _ in items]
    res_label = next(lbl for lbl in labels if "Resolution:" in lbl)
    assert "[MAX]" in res_label
    assert "1920 x 1080" in res_label

    # Other resolutions should not have [MAX]
    app.set_resolution(640, 360)
    app.settings["resolution"] = (640, 360)
    items = app.menu_items()
    labels = [lbl for lbl, _ in items]
    res_label = next(lbl for lbl in labels if "Resolution:" in lbl)
    assert "[MAX]" not in res_label

    # Clean up
    app.set_resolution(320, 180)
    app.settings["resolution"] = (320, 180)
    app.set_state("title")
