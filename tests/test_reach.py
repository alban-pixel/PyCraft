"""How far the renderer sees: as the settings say in play, 60 km for a screenshot."""
import pytest

from pycraft.render.constants import (FAR_LIMIT, LOD_QUALITIES, READY_SIZE, SCREENSHOT_REACH,
                                      SCREENSHOT_SIM_DISTANCE)
from pycraft.render.far import levels_for
from pycraft.render.renderer import far_planes, sim_distance, view_distance
from pycraft.sky import HAZE, haze


def test_levels_for():
    counts = [levels_for(*LOD_QUALITIES[q][:2], SCREENSHOT_REACH) for q in ("low", "medium", "high", "ultra")]
    assert counts == [10, 9, 10, 9]
    assert levels_for(2, 128, 7680) == 7


def test_distances():
    assert view_distance(512, None) == FAR_LIMIT == 8000
    assert view_distance(64, None) == 1024
    assert view_distance(64, SCREENSHOT_REACH) == SCREENSHOT_REACH
    assert sim_distance(256, None) == 12
    assert sim_distance(32, SCREENSHOT_REACH) == SCREENSHOT_SIM_DISTANCE == 24


def test_far_planes():
    assert far_planes(8000) == (1.0, 30000.0)
    assert far_planes(61440) == (16.0, 122880.0)


def test_haze():
    assert haze(4096) == haze(8000) == HAZE
    assert haze(61440) == pytest.approx(1.78 / 61440)


def test_sim_distance_fits_ready_map():
    assert SCREENSHOT_SIM_DISTANCE + 2 <= READY_SIZE // 2
