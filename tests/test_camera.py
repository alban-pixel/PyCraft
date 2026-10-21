"""Tests de la caméra : projection, horizon et clipping du plan proche."""

import math

import numpy as np
import pytest

from pycraft import config
from pycraft.camera import Camera, clip_near


def camera(w=1280, h=800, **kw) -> Camera:
    return Camera(width=w, height=h, **kw)


# ----------------------------------------------------------------------
# Projection
# ----------------------------------------------------------------------
def test_point_droit_devant_se_projette_au_centre():
    cam = camera()
    sx, sy, z, visible = cam.project(np.array([[10.0, 0.0, 0.0]]))
    assert visible[0]
    assert sx[0] == pytest.approx(cam.width / 2, abs=0.5)
    assert sy[0] == pytest.approx(cam.height / 2, abs=0.5)
    assert z[0] == pytest.approx(10.0)


def test_point_a_droite_a_un_x_superieur_au_centre():
    cam = camera()  # yaw = 0 → on regarde vers +X, la droite est -Y
    sx, sy, z, visible = cam.project(np.array([[10.0, -5.0, 0.0]]))
    assert visible[0]
    assert sx[0] > cam.width / 2


def test_point_a_gauche_a_un_x_inferieur_au_centre():
    cam = camera()
    sx, _, _, visible = cam.project(np.array([[10.0, 5.0, 0.0]]))
    assert visible[0]
    assert sx[0] < cam.width / 2


def test_point_au_dessus_a_un_y_inferieur_au_centre():
    cam = camera()
    _, sy, _, visible = cam.project(np.array([[10.0, 0.0, 5.0]]))
    assert visible[0]
    assert sy[0] < cam.height / 2


def test_point_derriere_la_camera_est_invisible():
    cam = camera()
    _, _, _, visible = cam.project(np.array([[-10.0, 0.0, 0.0]]))
    assert not visible[0]


def test_point_sur_le_plan_proche_est_invisible():
    cam = camera()
    _, _, _, visible = cam.project(np.array([[config.NEAR_PLANE - 0.01, 0.0, 0.0]]))
    assert not visible[0]


def test_la_camera_suit_sa_position():
    cam = camera(x=100.0, y=50.0, z=10.0)
    sx, sy, _, visible = cam.project(np.array([[110.0, 50.0, 10.0]]))
    assert visible[0]
    assert sx[0] == pytest.approx(cam.width / 2, abs=0.5)
    assert sy[0] == pytest.approx(cam.height / 2, abs=0.5)


def test_yaw_de_90_degres_regarde_vers_plus_y():
    cam = camera(yaw=math.pi / 2)
    sx, sy, _, visible = cam.project(np.array([[0.0, 10.0, 0.0]]))
    assert visible[0]
    assert sx[0] == pytest.approx(cam.width / 2, abs=0.5)


def test_horizon_a_la_hauteur_du_milieu_quand_pitch_est_nul():
    cam = camera()
    assert cam.horizon_y() == pytest.approx(cam.height / 2, abs=0.5)


def test_horizon_descend_quand_on_regarde_vers_le_haut():
    cam = camera(pitch=math.radians(20))
    assert cam.horizon_y() > cam.height / 2


def test_project_point_renvoie_none_derriere():
    cam = camera()
    assert cam.project_point((-5.0, 0.0, 0.0)) is None
    p = cam.project_point((10.0, 0.0, 0.0))
    assert p is not None and p[2] == pytest.approx(10.0)


def test_project_sur_tableau_vide():
    cam = camera()
    sx, sy, z, visible = cam.project(np.zeros((0, 3)))
    assert len(sx) == len(sy) == len(z) == len(visible) == 0


# ----------------------------------------------------------------------
# Clipping du plan proche
# ----------------------------------------------------------------------
def test_clip_polygone_entierement_devant_est_inchange():
    poly = [(0.0, 0.0, 5.0), (1.0, 0.0, 5.0), (1.0, 1.0, 5.0), (0.0, 1.0, 5.0)]
    assert clip_near(poly, 0.2) == poly


def test_clip_polygone_entierement_derriere_est_vide():
    poly = [(0.0, 0.0, -5.0), (1.0, 0.0, -5.0), (1.0, 1.0, -5.0)]
    assert clip_near(poly, 0.2) == []


def test_clip_polygone_a_cheval_est_decoupe():
    # Un quad dont deux sommets sont derrière le plan proche
    poly = [(-1.0, 0.0, -1.0), (1.0, 0.0, 1.0), (1.0, 1.0, 1.0), (-1.0, 1.0, -1.0)]
    out = clip_near(poly, 0.2)
    assert len(out) >= 4
    assert all(p[2] >= 0.2 - 1e-9 for p in out)
    # les sommets initiaux conservés sont bien présents
    assert (1.0, 0.0, 1.0) in out


def test_clip_ne_produit_jamais_de_triangle_geant():
    """Régression : un sommet derrière la caméra ne doit pas être projeté."""
    cam = camera()
    poly = [(-2.0, 0.0, -2.0), (6.0, -2.0, 1.0), (6.0, 2.0, 1.0)]
    out = clip_near(poly, config.NEAR_PLANE)
    for x, y, z in out:
        sx, sy, _, visible = cam.project(np.array([[x, y, z]]))
        if visible[0]:
            assert abs(sx[0]) < cam.width * 10
