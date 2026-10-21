"""T4 : premier rendu 3D GPU (terrain + quantification)."""

import math

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


def test_contour_du_bloc_vise(pyxel_headless):
    """Le bloc sous le réticule doit être entouré d'un contour (comme en CPU)."""
    from pycraft.gl.context import GlContext
    from pycraft.gl.renderer_gl import GlRenderer

    monde = World(sx=32, sy=32, sz=16, seed=0)
    monde.data = bytearray(len(monde.data))
    monde.set(16, 16, 8, Block.GRASS)

    gl = GlContext(320, 200)
    renderer = GlRenderer(
        monde, ChunkMeshes(monde), 320, 200, view_distance=40, detail_radius=16, gl=gl
    )
    try:
        # Caméra pile en face de la face -Y du bloc : il occupe le centre de l'écran.
        camera = Camera(16.5, 14.0, 8.5, yaw=math.pi / 2, pitch=0.0, width=320, height=200)

        renderer.draw(camera)
        sans = np.frombuffer(gl.read_indices(), dtype=np.uint8).copy()

        renderer.draw(camera, selection=(16, 16, 8))
        avec = np.frombuffer(gl.read_indices(), dtype=np.uint8).copy()

        masque = (avec != sans).reshape(200, 320)
        diff = np.argwhere(masque)
        assert len(diff) > 600, "le bloc visé doit être entouré d'un contour"
        # Un contour, pas un aplat : le centre de la face ne change pas.
        assert avec[100 * 320 + 160] == sans[100 * 320 + 160]
        # Le changement reste confiné à la boîte projetée du bloc (±55 px ici).
        ys, xs = diff[:, 0], diff[:, 1]
        assert xs.min() >= 160 - 70 and xs.max() <= 160 + 70
        assert ys.min() >= 100 - 70 and ys.max() <= 100 + 70
        # Trait de 2 px d'épaisseur (glLineWidth n'est pas garanti > 1).
        rangees = np.flatnonzero(masque[:, 160])
        assert rangees[1] == rangees[0] + 1, "le contour doit faire 2 px d'épaisseur"
        assert len(rangees) == 4
    finally:
        renderer.close()


def test_pas_de_contour_sans_selection(pyxel_headless):
    """Sans sélection, aucune ligne parasite ne doit apparaître."""
    from pycraft.gl.context import GlContext
    from pycraft.gl.renderer_gl import GlRenderer

    monde = World(sx=32, sy=32, sz=16, seed=0)
    monde.data = bytearray(len(monde.data))
    monde.set(16, 16, 8, Block.GRASS)

    gl = GlContext(320, 200)
    renderer = GlRenderer(
        monde, ChunkMeshes(monde), 320, 200, view_distance=40, detail_radius=16, gl=gl
    )
    try:
        camera = Camera(16.5, 14.0, 8.5, yaw=math.pi / 2, pitch=0.0, width=320, height=200)
        renderer.draw(camera)
        a = np.frombuffer(gl.read_indices(), dtype=np.uint8).copy()
        renderer.draw(camera, selection=None)
        b = np.frombuffer(gl.read_indices(), dtype=np.uint8).copy()
        assert (a != b).sum() == 0
    finally:
        renderer.close()


def _rendu_motif(bloc, mur=False, largeur=320, hauteur=200):
    """Image d'un sol (dessus) ou d'un mur (côtés) uniforme de `bloc`."""
    from pycraft.gl.context import GlContext
    from pycraft.gl.renderer_gl import GlRenderer

    monde = World(sx=32, sy=32, sz=16, seed=0)
    monde.data = bytearray(len(monde.data))
    if mur:
        for y in range(32):
            for x in range(32):
                for z in range(10):
                    monde.set(x, y, 8, bloc)
        camera = Camera(16, 6, 5.0, yaw=math.pi / 2, pitch=0.0, width=largeur, height=hauteur)
    else:
        for y in range(32):
            for x in range(32):
                for z in range(6):
                    monde.set(x, y, z, bloc)
        camera = Camera(16, 16, 22, yaw=0.0, pitch=-1.45, width=largeur, height=hauteur)

    gl = GlContext(largeur, hauteur)
    renderer = GlRenderer(
        monde, ChunkMeshes(monde), largeur, hauteur,
        view_distance=40, detail_radius=16, gl=gl,
    )
    try:
        renderer.draw(camera, time=30.0)
        return np.frombuffer(gl.read_indices(), np.uint8).copy()
    finally:
        renderer.close()


def test_textures_par_materiau(pyxel_headless):
    """Le motif dépend du matériau : couper la table doit changer l'image."""
    import pycraft.config as cfg

    defaut = {
        "bois": _rendu_motif(Block.WOOD),
        "pierre": _rendu_motif(Block.STONE),
        "herbe_cote": _rendu_motif(Block.GRASS, mur=True),
    }
    assert len(set(defaut["herbe_cote"].tolist())) >= 4, "un mur d'herbe doit être texturé"

    sauvegarde = cfg.MATERIALS
    cfg.MATERIALS = (0,) * 16  # tous les blocs « unis » : plus aucun motif
    try:
        plat = {
            "bois": _rendu_motif(Block.WOOD),
            "pierre": _rendu_motif(Block.STONE),
            "herbe_cote": _rendu_motif(Block.GRASS, mur=True),
        }
    finally:
        cfg.MATERIALS = sauvegarde

    ecart = {nom: float((defaut[nom] != plat[nom]).mean()) for nom in defaut}
    assert ecart["herbe_cote"] > 0.02, "les brins doivent modifier les côtés de l'herbe"
    assert ecart["bois"] > 0.15, "les planches doivent modifier le dessus du bois"
    assert ecart["pierre"] > 0.15, "les éclats doivent modifier le dessus de la pierre"
    # Deux matériaux ne doivent pas réagir de la même façon au même changement.
    assert abs(ecart["bois"] - ecart["pierre"]) > 0.05, "bois et pierre partagent le même motif"


def test_ombre_d_un_casteur_hors_champ(pyxel_headless):
    """Une tour derrière la caméra doit projeter son ombre devant elle."""
    from pycraft.gl.context import GlContext
    from pycraft.gl.palette import PALETTE
    from pycraft.gl.renderer_gl import GlRenderer

    monde = World(sx=48, sy=48, sz=16, seed=0)
    monde.data = bytearray(len(monde.data))
    for y in range(48):
        for x in range(48):
            for z in range(2):
                monde.set(x, y, z, Block.STONE)
    # Tour derrière la caméra : jamais dans le frustum de la caméra.
    for z in range(2, 14):
        for dy in (0, 1):
            for dx in (0, 1):
                monde.set(33 + dx, 33 + dy, z, Block.STONE)

    gl = GlContext(320, 200)
    renderer = GlRenderer(
        monde, ChunkMeshes(monde), 320, 200, view_distance=48, detail_radius=100, gl=gl
    )
    try:
        # La caméra regarde vers -x,-y : la tour à (33,33) est derrière elle,
        # mais son ombre tombe vers (28,28), donc devant la caméra.
        camera = Camera(28, 28, 6, yaw=math.pi + 0.9, pitch=-0.45,
                        width=320, height=200)
        renderer.shadows = True
        renderer.draw(camera, time=30.0)
        avec = np.frombuffer(gl.read_indices(), np.uint8).copy()
        renderer.shadows = False
        renderer.draw(camera, time=30.0)
        sans = np.frombuffer(gl.read_indices(), np.uint8).copy()

        changes = int((avec != sans).sum())
        assert changes > 200, "l'ombre d'une tour hors champ doit être visible"
        assert PALETTE[avec].astype(float).mean() < PALETTE[sans].astype(float).mean()
    finally:
        renderer.close()


def test_resolution_interne_reduite(pyxel_headless):
    """À scale=0.5, la scène est rendue en 160×100 puis agrandie en nearest."""
    from pycraft.gl.context import GlContext
    from pycraft.gl.renderer_gl import GlRenderer

    monde = World(sx=32, sy=32, sz=16, seed=0)
    monde.data = bytearray(len(monde.data))
    for y in range(32):
        for x in range(32):
            for z in range(4):
                monde.set(x, y, z, Block.GRASS)

    gl = GlContext(320, 200)
    renderer = GlRenderer(
        monde, ChunkMeshes(monde), 320, 200,
        view_distance=40, detail_radius=16, gl=gl, scale=0.5,
    )
    try:
        assert renderer.scene_tex.size == (160, 100)
        camera = Camera(16, 16, 8, yaw=0.6, pitch=-0.25, width=320, height=200)
        renderer.draw(camera, time=30.0)
        img = np.frombuffer(gl.read_indices(), np.uint8).reshape(200, 320)
        # Agrandissement nearest : chaque bloc 2×2 vient d'un seul texel.
        blocs = img.reshape(100, 2, 160, 2).transpose(0, 2, 1, 3).reshape(-1, 4)
        uniformes = (blocs == blocs[:, :1]).all(axis=1).mean()
        # La vignette du post-traitement varie par pixel : quelques blocs
        # changent d'un cran de palette. On exige donc 90 %, pas 100 %.
        assert uniformes > 0.90, f"seulement {uniformes:.0%} de blocs 2×2 uniformes"
    finally:
        renderer.close()
