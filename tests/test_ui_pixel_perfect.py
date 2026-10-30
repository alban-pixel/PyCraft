"""Exhaustive tests for Pixel-Perfect Minecraft 1.8 User Interfaces, Containers, and Scaling."""
import pytest
from ui_renderer import (
    CONTAINER_DIMENSIONS, CREATIVE_METRICS, FURNACE_METRICS,
    HUD_DIMENSIONS, PLAYER_PREVIEW_DIMS, TOOLTIP_COLORS,
    UIRenderer, WIDGET_METRICS, calculate_durability_bar
)


def test_gui_scale_integer_calculations():
    renderer = UIRenderer()
    # 320x180 minimum window size
    assert renderer.calculate_gui_scale(320, 180) == 1
    # 854x480 standard default window size
    assert renderer.calculate_gui_scale(854, 480) == 2
    # Full HD (1920x1080)
    assert renderer.calculate_gui_scale(1920, 1080) in (3, 4)
    # 4K UHD (3840x2160)
    assert renderer.calculate_gui_scale(3840, 2160) >= 4


def test_container_pixel_dimensions():
    assert CONTAINER_DIMENSIONS["INVENTORY"] == (176, 166)
    assert CONTAINER_DIMENSIONS["CRAFTING_TABLE"] == (176, 166)
    assert CONTAINER_DIMENSIONS["FURNACE"] == (176, 166)
    assert CONTAINER_DIMENSIONS["CHEST_SINGLE"] == (176, 166)
    assert CONTAINER_DIMENSIONS["CHEST_DOUBLE"] == (176, 222)
    assert CONTAINER_DIMENSIONS["CREATIVE"] == (195, 136)


def test_hud_and_preview_metrics():
    assert HUD_DIMENSIONS["HOTBAR_WIDTH"] == 182
    assert HUD_DIMENSIONS["HOTBAR_HEIGHT"] == 22
    assert HUD_DIMENSIONS["CROSSHAIR_SIZE"] == 15
    assert PLAYER_PREVIEW_DIMS == (51, 72)
    assert FURNACE_METRICS["FLAME_HEIGHT"] == 14
    assert FURNACE_METRICS["ARROW_WIDTH"] == 24
    assert CREATIVE_METRICS["TAB_COUNT"] == 12
    assert CREATIVE_METRICS["SCROLLBAR_THUMB"] == (12, 15)


def test_tooltip_and_widget_metrics():
    assert TOOLTIP_COLORS["BACKGROUND"] == "#100010"
    assert TOOLTIP_COLORS["OUTER_BORDER"] == "#5000FF"
    assert TOOLTIP_COLORS["INNER_BORDER"] == "#28007F"
    assert WIDGET_METRICS["SLOT_HIGHLIGHT_SIZE"] == (16, 16)
    assert WIDGET_METRICS["DURABILITY_BAR_SIZE"] == (13, 2)


def test_durability_bar_calculations():
    # 100% durability
    w_max, col_max = calculate_durability_bar(150, 150)
    assert w_max == 13
    assert col_max == (0, 255, 0)

    # 50% durability
    w_mid, col_mid = calculate_durability_bar(75, 150)
    assert w_mid == 6

    # 0% durability
    w_zero, col_zero = calculate_durability_bar(0, 150)
    assert w_zero == 0
    assert col_zero == (255, 0, 0)

    # Negative durability
    w_neg, _ = calculate_durability_bar(-10, 150)
    assert w_neg == 0


def test_container_centering():
    renderer = UIRenderer()
    # 176x166 in 854x480 at scale 2 -> (176*2=352, 166*2=332)
    # cx = (854 - 352) // 2 = 251
    # cy = (480 - 332) // 2 = 74
    cx, cy = renderer.get_container_centered_pos(176, 166, 854, 480, scale=2)
    assert cx == 251
    assert cy == 74
