"""Caméra perspective et clipping du plan proche.

Convention : `yaw` tourne autour de Z (0 = regarde vers +X), `pitch` incline la
vue (positif = vers le haut). La projection est une projection en trou d'épingle
(« pinhole ») : `focal = (largeur / 2) / tan(fov / 2)`.
"""

from __future__ import annotations

import math

import numpy as np

from pycraft import config

_MAX_PITCH = math.pi / 2 - 0.01


class Camera:
    """Position + orientation + projection écran."""

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        yaw: float = 0.0,
        pitch: float = 0.0,
        fov_deg: float = config.FOV_DEG,
        width: int = config.DEFAULT_WIDTH,
        height: int = config.DEFAULT_HEIGHT,
    ) -> None:
        self.pos = np.array([x, y, z], dtype=np.float64)
        self.yaw = float(yaw)
        self.pitch = float(pitch)
        self.fov_deg = float(fov_deg)
        self.width = int(width)
        self.height = int(height)
        self._recompute()

    # ------------------------------------------------------------------
    # État
    # ------------------------------------------------------------------
    def _recompute(self) -> None:
        self.yaw %= 2 * math.pi
        self.pitch = max(-_MAX_PITCH, min(_MAX_PITCH, self.pitch))
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        self.fwd = np.array([cp * cy, cp * sy, sp], dtype=np.float64)
        self.right = np.array([sy, -cy, 0.0], dtype=np.float64)
        self.up = np.array([-sp * cy, -sp * sy, cp], dtype=np.float64)
        self.focal = (self.width / 2) / math.tan(math.radians(self.fov_deg) / 2)

    def set_position(self, x: float, y: float, z: float) -> None:
        self.pos[:] = (x, y, z)

    def set_angles(self, yaw: float, pitch: float) -> None:
        self.yaw = float(yaw)
        self.pitch = float(pitch)
        self._recompute()

    def rotate(self, dyaw: float, dpitch: float) -> None:
        self.set_angles(self.yaw + dyaw, self.pitch + dpitch)

    def set_size(self, width: int, height: int) -> None:
        self.width, self.height = int(width), int(height)
        self._recompute()

    def basis(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        return self.right, self.up, self.fwd

    # ------------------------------------------------------------------
    # Projection
    # ------------------------------------------------------------------
    def to_camera(self, points: np.ndarray) -> np.ndarray:
        """Transforme des points monde (N, 3) en coordonnées caméra (N, 3)."""
        pts = np.asarray(points, dtype=np.float64)
        if pts.size == 0:
            return np.zeros((0, 3), dtype=np.float64)
        rel = pts - self.pos
        return np.stack((rel @ self.right, rel @ self.up, rel @ self.fwd), axis=-1)

    def project(
        self, points: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Projette (N, 3) monde → (sx, sy, profondeur, visible)."""
        pts = np.asarray(points, dtype=np.float64)
        if pts.size == 0:
            empty = np.zeros(0, dtype=np.float64)
            return empty, empty, empty, np.zeros(0, dtype=bool)
        rel = pts - self.pos
        xc = rel @ self.right
        yc = rel @ self.up
        zc = rel @ self.fwd
        visible = zc > config.NEAR_PLANE
        safe = np.where(visible, zc, 1.0)
        sx = self.width / 2 + self.focal * xc / safe
        sy = self.height / 2 - self.focal * yc / safe
        return sx, sy, zc, visible

    def project_point(self, point: tuple[float, float, float]) -> tuple[float, float, float] | None:
        """Projette un seul point ; `None` s'il est derrière la caméra."""
        sx, sy, z, visible = self.project(np.array([point], dtype=np.float64))
        if not visible[0]:
            return None
        return float(sx[0]), float(sy[0]), float(z[0])

    def horizon_y(self) -> float:
        """Ligne d'horizon à l'écran (y), en tenant compte du pitch."""
        return self.height / 2 + self.focal * math.tan(self.pitch)


def clip_near(
    poly: list[tuple[float, float, float]],
    near: float = config.NEAR_PLANE,
) -> list[tuple[float, float, float]]:
    """Découpe un polygone (coordonnées caméra) contre le plan z = near.

    Utilise l'algorithme de Sutherland–Hodgman. Un polygone entièrement derrière
    la caméra renvoie une liste vide ; un polygone entièrement devant est
    renvoyé tel quel.
    """
    if not poly:
        return []
    if all(p[2] >= near for p in poly):
        return poly
    if all(p[2] < near for p in poly):
        return []

    out: list[tuple[float, float, float]] = []
    n = len(poly)
    for i in range(n):
        a = poly[i]
        b = poly[(i + 1) % n]
        a_in = a[2] >= near
        b_in = b[2] >= near
        if a_in:
            out.append(a)
        if a_in != b_in:
            t = (near - a[2]) / (b[2] - a[2])
            out.append(
                (
                    a[0] + t * (b[0] - a[0]),
                    a[1] + t * (b[1] - a[1]),
                    near,
                )
            )
    return out
