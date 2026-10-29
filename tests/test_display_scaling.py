import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import pyxel
from main import App, GUI_SCALES, RESOLUTIONS


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
