"""Packing des maillages CPU en buffers de sommets pour le GPU.

Format interleaved (8 floats par sommet) :
    position (3) · normale (3) · couleur (1) · occlusion ambiante (1)
"""

from __future__ import annotations

import numpy as np

from pycraft.mesher import CHUNK

STRIDE = 8


def derive_normals(verts: np.ndarray) -> np.ndarray:
    """Normale de chaque quad (N, 4, 3) à partir de ses trois premiers sommets."""
    p0 = verts[:, 0, :]
    p1 = verts[:, 1, :]
    p2 = verts[:, 2, :]
    n = np.cross(p1 - p0, p2 - p0)
    longueurs = np.linalg.norm(n, axis=1, keepdims=True)
    longueurs[longueurs == 0] = 1.0
    return n / longueurs


def pack_mesh(verts: np.ndarray, colors: np.ndarray) -> np.ndarray:
    """(N, 4, 3) quads + couleurs (N,) → triangles (6N, STRIDE) float32."""
    n = len(verts)
    if n == 0:
        return np.zeros((0, STRIDE), dtype=np.float32)
    normales = derive_normals(verts.astype(np.float64))
    data = np.zeros((n, 6, STRIDE), dtype=np.float32)
    # sommets 0-2 et 0-2-3
    data[:, 0, 0:3] = verts[:, 0]
    data[:, 1, 0:3] = verts[:, 1]
    data[:, 2, 0:3] = verts[:, 2]
    data[:, 3, 0:3] = verts[:, 0]
    data[:, 4, 0:3] = verts[:, 2]
    data[:, 5, 0:3] = verts[:, 3]
    data[:, :, 3:6] = normales[:, None, :]
    data[:, :, 6] = colors[:, None]
    data[:, :, 7] = 1.0
    return data.reshape(-1, STRIDE)


class GpuMeshes:
    """Cache de VBO par chunk (le contexte est fourni, jamais créé ici)."""

    def __init__(self, ctx) -> None:
        self.ctx = ctx
        self._gpu: dict[tuple[int, int], tuple[object, int]] = {}

    def get(self, cx: int, cy: int, verts: np.ndarray, colors: np.ndarray):
        cle = (cx, cy)
        mesh = self._gpu.get(cle)
        if mesh is None:
            data = pack_mesh(verts, colors)
            buffer = self.ctx.buffer(data.tobytes())
            mesh = (buffer, len(data))
            self._gpu[cle] = mesh
        return mesh

    def invalidate(self, x: int, y: int) -> None:
        cx, cy = x // CHUNK, y // CHUNK
        cles = {(cx, cy)}
        if x % CHUNK == 0:
            cles.add((cx - 1, cy))
        if x % CHUNK == CHUNK - 1:
            cles.add((cx + 1, cy))
        if y % CHUNK == 0:
            cles.add((cx, cy - 1))
        if y % CHUNK == CHUNK - 1:
            cles.add((cx, cy + 1))
        for cle in cles:
            mesh = self._gpu.pop(cle, None)
            if mesh is not None:
                mesh[0].release()

    def release(self) -> None:
        for buffer, _ in self._gpu.values():
            buffer.release()
        self._gpu.clear()
