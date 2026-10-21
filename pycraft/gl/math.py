"""Matrices de vue et de projection pour le renderer GPU.

Convention : vecteurs colonnes (le point est multiplié à droite). Les matrices
sont en numpy (row-major) ; `as_uniform()` les transpose pour OpenGL, qui attend
du column-major.
"""

from __future__ import annotations

import numpy as np

from pycraft import config
from pycraft.camera import Camera


def view_matrix(camera: Camera) -> np.ndarray:
    """Monde → espace caméra."""
    r, u, f = camera.right, camera.up, camera.fwd
    m = np.eye(4, dtype=np.float64)
    m[0, :3] = r
    m[1, :3] = u
    m[2, :3] = f
    m[:3, 3] = (-r @ camera.pos, -u @ camera.pos, -f @ camera.pos)
    return m


def projection_matrix(
    camera: Camera, near: float = config.NEAR_PLANE, far: float | None = None
) -> np.ndarray:
    """Caméra → NDC (OpenGL, z dans [-1, 1])."""
    if far is None:
        far = max(100.0, camera.focal * 4.0)
    a = camera.focal / (camera.width / 2)
    b = camera.focal / (camera.height / 2)
    m = np.zeros((4, 4), dtype=np.float64)
    m[0, 0] = a
    m[1, 1] = b
    m[2, 2] = (far + near) / (far - near)
    m[2, 3] = -2.0 * far * near / (far - near)
    m[3, 2] = 1.0
    return m


def mvp_matrix(camera: Camera, near: float = config.NEAR_PLANE, far: float | None = None) -> np.ndarray:
    return projection_matrix(camera, near, far) @ view_matrix(camera)


def as_uniform(matrice: np.ndarray) -> bytes:
    """Sérialise une matrice pour un uniform mat4 (column-major)."""
    return np.ascontiguousarray(matrice.T, dtype=np.float32).tobytes()


def project_with_matrix(camera: Camera, point: tuple[float, float, float]) -> tuple[float, float, float] | None:
    """Projette un point via la matrice MVP ; `None` s'il est derrière."""
    m = mvp_matrix(camera)
    p = np.array([point[0], point[1], point[2], 1.0], dtype=np.float64)
    clip = m @ p
    if clip[3] <= 1e-6:
        return None
    ndc = clip[:3] / clip[3]
    sx = (ndc[0] + 1.0) / 2.0 * camera.width
    sy = (1.0 - (ndc[1] + 1.0) / 2.0) * camera.height
    return float(sx), float(sy), float(clip[3])
