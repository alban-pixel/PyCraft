"""T4 : premier rendu 3D GPU (terrain + quantification)."""

import numpy as np
import pytest

pytestmark = pytest.mark.gpu

from pycraft.camera import Camera
from pycraft.config import Block
from pycraft.mesher import ChunkMeshes
from pycraft.world import World


def monde_de_test(sx=32, sy=32, sz=16):
    monde = World(sx=sx, sy=sy, sz=sz, seed=0)
    monde.data = bytearray(len(monde.data))
    for y in range(sy):
        for x in range(sx):
            for z in range(4):
                monde.set(x, y, z, Block.STONE)
    for x, y in [(18, 16), (20, 18), (22, 20)]:
        for z in range(4, 7):
            monde.set(x, y, z, Block.GRASS)
    return monde


def test_rendu_terrain_et_ciel(pyxel_headless):
    from pycraft.gl.context import GlContext
    from pycraft.gl.renderer_gl import GlRenderer

    monde = monde_de_test()
    meshes = ChunkMeshes(monde)
    gl = GlContext(320, 200)
    renderer = GlRenderer(monde, meshes, 320, 200, view_distance=40, detail_radius=16, gl=gl)
    try:
        camera = Camera(16, 16, 8, yaw=0.6, pitch=-0.25, width=320, height=200)
        renderer.draw(camera)
        data = gl.read_indices()
        assert len(data) == 320 * 200
        assert len(set(data)) >= 3, "l'image devrait contenir ciel, sol et ombrage"
        haut = set(data[: 320 * 20])
        bas = set(data[-320 * 20 :])
        assert haut != bas, "le ciel et le sol doivent différer"
        assert renderer.quads > 0
    finally:
        renderer.close()


def test_rendu_apres_modification_de_bloc(pyxel_headless):
    from pycraft.gl.context import GlContext
    from pycraft.gl.renderer_gl import GlRenderer

    monde = monde_de_test()
    meshes = ChunkMeshes(monde)
    gl = GlContext(320, 200)
    renderer = GlRenderer(monde, meshes, 320, 200, view_distance=40, detail_radius=16, gl=gl)
    try:
        camera = Camera(16, 16, 8, yaw=0.6, pitch=-0.25, width=320, height=200)
        renderer.draw(camera)
        avant = gl.read_indices()
        # pilier ajouté juste devant la caméra
        for z in range(0, 12):
            monde.set(18, 17, z, Block.GRASS)
        meshes.invalidate(18, 17)
        renderer.invalidate(18, 17)
        renderer.draw(camera)
        apres = gl.read_indices()
        assert avant != apres
    finally:
        renderer.close()
