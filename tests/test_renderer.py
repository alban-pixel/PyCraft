import math
import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

from renderer import perspective, look_at, Renderer


def test_perspective_matrix():
    mat = perspective(70.0, 16 / 9, 0.05, 300.0)
    assert mat.shape == (4, 4)
    assert mat[3, 2] == -1.0


def test_look_at_matrix():
    eye = (0.0, 0.0, 0.0)
    fw = (0.0, 0.0, 1.0)
    mat = look_at(eye, fw)
    assert mat.shape == (4, 4)
    # Origin should stay at origin
    transformed_origin = mat @ np.array([0.0, 0.0, 0.0, 1.0], dtype=np.float32)
    assert np.allclose(transformed_origin[:3], [0.0, 0.0, 0.0])


def test_frustum_planes_culling():
    p = perspective(70.0, 16 / 9, 0.05, 300.0)
    v = look_at((64.0, 30.0, 64.0), (0.0, 0.0, 1.0))
    vp = p @ v

    planes = Renderer._frustum_planes(vp)
    assert len(planes) == 6

    # Test chunk center straight ahead
    cx_ahead, cy_ahead, cz_ahead = 64.0, 30.0, 100.0
    r = 20.0
    inside_ahead = all(pl[0] * cx_ahead + pl[1] * cy_ahead + pl[2] * cz_ahead + pl[3] >= -r for pl in planes)
    assert inside_ahead is True

    # Test chunk center completely behind camera
    cx_behind, cy_behind, cz_behind = 64.0, 30.0, 20.0
    inside_behind = all(pl[0] * cx_behind + pl[1] * cy_behind + pl[2] * cz_behind + pl[3] >= -r for pl in planes)
    assert inside_behind is False
