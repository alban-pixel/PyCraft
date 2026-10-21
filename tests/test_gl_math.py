"""T3 : matrices de vue/projection cohérentes avec la caméra CPU."""

import numpy as np
import pytest

from pycraft.camera import Camera
from pycraft.gl.math import mvp_matrix, projection_matrix, project_with_matrix, view_matrix


def camera() -> Camera:
    return Camera(10.0, 20.0, 5.0, yaw=0.6, pitch=-0.2, width=1280, height=800)


def test_mvp_projette_comme_la_camera():
    cam = camera()
    # Points construits devant la caméra : devant + décalages droite/haut.
    for avant, droite, haut in [(10, 0, 0), (20, 3, -2), (50, -5, 1), (5, 1, 1)]:
        point = tuple(cam.pos + cam.fwd * avant + cam.right * droite + cam.up * haut)
        attendu = cam.project_point(point)
        obtenu = project_with_matrix(cam, point)
        assert attendu is not None and obtenu is not None
        assert obtenu[0] == pytest.approx(attendu[0], abs=0.5)
        assert obtenu[1] == pytest.approx(attendu[1], abs=0.5)
        assert obtenu[2] == pytest.approx(attendu[2], abs=1e-3)


def test_point_derriere_la_camera_est_rejete():
    cam = camera()
    point_derriere = tuple(cam.pos - cam.fwd * 10.0)
    assert project_with_matrix(cam, point_derriere) is None


def test_matrice_de_vue_est_orthonormee():
    cam = camera()
    v = view_matrix(cam)
    assert v.shape == (4, 4)
    assert np.allclose(v[3], [0, 0, 0, 1])
    assert abs(np.linalg.det(v[:3, :3])) == pytest.approx(1.0, abs=1e-6)


def test_projection_place_l_horizon_au_centre_quand_pitch_nul():
    cam = Camera(0, 0, 0, yaw=0, pitch=0, width=800, height=600)
    point = (1000.0, 0.0, 0.0)  # à l'infini devant, à hauteur d'œil
    sx, sy, _ = project_with_matrix(cam, point)
    assert sx == pytest.approx(400, abs=1)
    assert sy == pytest.approx(300, abs=1)


def test_mvp_est_le_produit_projection_fois_vue():
    cam = camera()
    attendu = projection_matrix(cam) @ view_matrix(cam)
    assert np.allclose(mvp_matrix(cam), attendu)
