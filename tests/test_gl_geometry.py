"""T3 : packing des maillages en buffers GPU."""

import numpy as np
import pytest

from pycraft.gl.geometry import STRIDE, GpuMeshes, pack_mesh


def quad_haut() -> np.ndarray:
    return np.array(
        [[[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]]], dtype=np.float32
    )


class FauxBuffer:
    def __init__(self, data):
        self.data = data
        self.released = False

    def release(self):
        self.released = True


class FauxCtx:
    def __init__(self):
        self.creations = 0

    def buffer(self, data):
        self.creations += 1
        return FauxBuffer(data)


def test_pack_un_quad_produit_six_sommets():
    data = pack_mesh(quad_haut(), np.array([11], dtype=np.uint8))
    assert data.shape == (6, STRIDE)
    assert data.dtype == np.float32


def test_normale_du_dessus():
    data = pack_mesh(quad_haut(), np.array([11], dtype=np.uint8))
    assert np.allclose(data[:, 3:6], [0.0, 0.0, 1.0])


def test_couleur_et_ao_par_sommet():
    data = pack_mesh(quad_haut(), np.array([7], dtype=np.uint8))
    assert np.all(data[:, 6] == 7)
    assert np.all(data[:, 7] == 1.0)


def test_positions_des_deux_triangles():
    data = pack_mesh(quad_haut(), np.array([1], dtype=np.uint8))
    # triangle 1 : (0,1,2), triangle 2 : (0,2,3)
    assert np.allclose(data[0, 0:3], [0, 0, 1])
    assert np.allclose(data[2, 0:3], [1, 1, 1])
    assert np.allclose(data[3, 0:3], [0, 0, 1])
    assert np.allclose(data[5, 0:3], [0, 1, 1])


def test_cache_reutilise_et_invalide():
    ctx = FauxCtx()
    gpu = GpuMeshes(ctx)
    verts = quad_haut()
    colors = np.array([11], dtype=np.uint8)

    buf1, count1 = gpu.get(0, 0, verts, colors)
    assert count1 == 6
    assert ctx.creations == 1
    buf2, _ = gpu.get(0, 0, verts, colors)
    assert buf2 is buf1
    assert ctx.creations == 1

    gpu.invalidate(0, 0)
    buf3, _ = gpu.get(0, 0, verts, colors)
    assert buf3 is not buf1
    assert ctx.creations == 2


def test_release_libere_les_buffers():
    ctx = FauxCtx()
    gpu = GpuMeshes(ctx)
    buf, _ = gpu.get(0, 0, quad_haut(), np.array([11], dtype=np.uint8))
    gpu.release()
    assert buf.released
