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


def test_ciel_degrade_etoiles_et_soleil(pyxel_headless):
    from pycraft.gl.context import GlContext
    from pycraft.gl.renderer_gl import GlRenderer

    monde = World(sx=32, sy=32, sz=16, seed=0)
    monde.data = bytearray(len(monde.data))  # ciel seul
    meshes = ChunkMeshes(monde)
    gl = GlContext(320, 200)
    renderer = GlRenderer(monde, meshes, 320, 200, view_distance=16, detail_radius=8, gl=gl)
    try:
        camera = Camera(16, 16, 8, yaw=0.6, pitch=0.35, width=320, height=200)
        renderer.draw(camera, time=3.0)
        data = gl.read_indices()
        assert len(set(data)) >= 8, "le ciel doit produire un dégradé"
        haut = set(data[: 320 * 30])
        bas = set(data[-320 * 30 :])
        assert haut != bas, "zénith et horizon doivent différer"
    finally:
        renderer.close()


def test_ombres_portees_assombrissent_le_sol(pyxel_headless):
    from pycraft.gl.context import GlContext
    from pycraft.gl.palette import PALETTE
    from pycraft.gl.renderer_gl import GlRenderer

    monde = World(sx=32, sy=32, sz=16, seed=0)
    monde.data = bytearray(len(monde.data))
    for y in range(32):
        for x in range(32):
            for z in range(4):
                monde.set(x, y, z, Block.STONE)
    for z in range(4, 14):  # tour qui projette une ombre
        monde.set(18, 17, z, Block.STONE)

    gl = GlContext(320, 200)
    renderer = GlRenderer(monde, ChunkMeshes(monde), 320, 200, view_distance=40, detail_radius=16, gl=gl)
    try:
        camera = Camera(16, 16, 9, yaw=0.85, pitch=-0.35, width=320, height=200)
        renderer.shadows = True
        renderer.draw(camera)
        avec = np.frombuffer(gl.read_indices(), dtype=np.uint8).copy()
        renderer.shadows = False
        renderer.draw(camera)
        sans = np.frombuffer(gl.read_indices(), dtype=np.uint8).copy()

        diff = np.abs(avec.astype(int) - sans.astype(int))
        assert diff.sum() > 100, "les ombres doivent changer l'image"
        lum_avec = PALETTE[avec].astype(float).mean()
        lum_sans = PALETTE[sans].astype(float).mean()
        assert lum_avec < lum_sans, "les ombres doivent assombrir"
    finally:
        renderer.close()


def test_eau_animee(pyxel_headless):
    from pycraft.gl.context import GlContext
    from pycraft.gl.renderer_gl import GlRenderer

    monde = World(sx=32, sy=32, sz=16, seed=0)
    monde.data = bytearray(len(monde.data))
    for y in range(32):
        for x in range(32):
            for z in range(3):
                monde.set(x, y, z, Block.STONE)
    for y in range(10, 22):
        for x in range(10, 22):
            monde.set(x, y, 3, Block.WATER)

    gl = GlContext(320, 200)
    renderer = GlRenderer(monde, ChunkMeshes(monde), 320, 200, view_distance=40, detail_radius=16, gl=gl)
    try:
        camera = Camera(16, 14, 10, yaw=0.9, pitch=-0.35, width=320, height=200)
        renderer.draw(camera, time=0.0)
        t0 = np.frombuffer(gl.read_indices(), dtype=np.uint8).copy()
        renderer.draw(camera, time=1.3)
        t1 = np.frombuffer(gl.read_indices(), dtype=np.uint8).copy()
        assert (t0 != t1).sum() > 50, "l'eau doit onduler avec le temps"
    finally:
        renderer.close()


def test_textures_procedurales(pyxel_headless):
    from pycraft.gl.context import GlContext
    from pycraft.gl.renderer_gl import GlRenderer

    monde = World(sx=16, sy=16, sz=8, seed=0)
    monde.data = bytearray(len(monde.data))
    for y in range(16):
        for x in range(16):
            for z in range(4):
                monde.set(x, y, z, Block.STONE)
    gl = GlContext(320, 200)
    renderer = GlRenderer(monde, ChunkMeshes(monde), 320, 200, view_distance=20, detail_radius=8, gl=gl)
    try:
        camera = Camera(8, 8, 6, yaw=0.0, pitch=-0.6, width=320, height=200)
        renderer.draw(camera)
        data = gl.read_indices()
        assert len(set(data)) >= 4, "le sol doit être texturé, pas uni"
    finally:
        renderer.close()


def test_cycle_jour_nuit(pyxel_headless):
    from pycraft.gl.context import GlContext
    from pycraft.gl.palette import PALETTE
    from pycraft.gl.renderer_gl import GlRenderer

    monde = World(sx=32, sy=32, sz=16, seed=0)
    monde.data = bytearray(len(monde.data))
    for y in range(32):
        for x in range(32):
            for z in range(4):
                monde.set(x, y, z, Block.GRASS)
    gl = GlContext(320, 200)
    renderer = GlRenderer(monde, ChunkMeshes(monde), 320, 200, view_distance=40, detail_radius=16, gl=gl)
    try:
        camera = Camera(16, 16, 8, yaw=0.6, pitch=-0.2, width=320, height=200)
        renderer.draw(camera, time=30.0)  # plein jour
        jour = np.frombuffer(gl.read_indices(), dtype=np.uint8).copy()
        renderer.draw(camera, time=110.0)  # nuit
        nuit = np.frombuffer(gl.read_indices(), dtype=np.uint8).copy()
        assert (jour != nuit).sum() > 500
        assert PALETTE[nuit].astype(float).mean() < PALETTE[jour].astype(float).mean()
    finally:
        renderer.close()


def test_pluie_visible(pyxel_headless):
    from pycraft.gl.context import GlContext
    from pycraft.gl.renderer_gl import GlRenderer

    monde = World(sx=32, sy=32, sz=16, seed=0)
    monde.data = bytearray(len(monde.data))
    for y in range(32):
        for x in range(32):
            for z in range(4):
                monde.set(x, y, z, Block.GRASS)
    gl = GlContext(320, 200)
    renderer = GlRenderer(monde, ChunkMeshes(monde), 320, 200, view_distance=40, detail_radius=16, gl=gl)
    try:
        camera = Camera(16, 16, 8, yaw=0.6, pitch=-0.1, width=320, height=200)
        renderer.rain = 0.0
        renderer.draw(camera, time=10.0)
        sec = np.frombuffer(gl.read_indices(), dtype=np.uint8).copy()
        renderer.rain = 1.0
        renderer.draw(camera, time=10.0)
        pluie = np.frombuffer(gl.read_indices(), dtype=np.uint8).copy()
        assert (sec != pluie).sum() > 100
    finally:
        renderer.close()
