"""The real climate: known places have their known temperature and rain."""
import os

import numpy as np
import pytest

from pycraft.earth import climate
from pycraft.earth.climate import Climate


@pytest.fixture(scope="module")
def earth():
    return Climate()


@pytest.mark.parametrize("name, lat, lon, t0, rain", [
    ("Paris", 48.86, 2.35, (9, 13), (500, 800)), ("Tamanrasset", 22.79, 5.52, (27, 35), (20, 90)),
    ("In Salah", 27.2, 2.47, (24, 32), (0, 40)), ("Singapore", 1.35, 103.82, (25, 29), (1800, 3500)), ("Yakutsk", 62.03, 129.73, (-20, -5), (150, 400)),
    ("Chamonix", 45.9237, 6.8694, (8, 15), (700, 2500))])
def test_known_places(earth, name, lat, lon, t0, rain):
    t, p = earth.at(np.array([lat]), np.array([lon]))
    assert t0[0] <= t[0] <= t0[1], f"{name}: {t[0]} degrees"
    assert rain[0] <= p[0] <= rain[1], f"{name}: {p[0]} mm"


def test_the_date_line_is_not_a_border(earth):
    t, p = earth.at(np.array([10.0, 10.0]), np.array([179.99, -179.99]))
    assert abs(t[0] - t[1]) < 0.2 and abs(p[0] - p[1]) < 50


def test_poles(earth):
    t, p = earth.at(np.array([84.9, -84.9]), np.array([0.0, 0.0]))
    assert np.isfinite(t).all() and (t < 0).all() and (p > 0).all()


def test_any_shape(earth):
    t, p = earth.at(np.zeros((2, 3)), np.zeros((2, 3)))
    assert t.shape == p.shape == (2, 3)


def test_small_file():
    assert os.path.getsize(os.path.join(os.path.dirname(climate.__file__), "climate.npz")) < 3_000_000
