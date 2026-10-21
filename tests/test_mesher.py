"""Tests du maillage par chunk."""

import time

import numpy as np
import pytest

from pycraft import config
from pycraft.config import Block
from pycraft.mesher import CHUNK, ChunkMeshes, build_detail, build_greedy, select_mesh
from pycraft.world import World


def monde_vide(sx=32, sy=32, sz=16) -> World:
    """Monde généré puis vidé : la génération reste testée à part."""
    w = World(sx=sx, sy=sy, sz=sz, seed=0)
    w.data = bytearray(len(w.data))
    return w


def test_bloc_isole_produit_six_faces():
    w = monde_vide()
    w.set(5, 5, 5, Block.STONE)
    verts, colors = build_detail(w, 0, 0)
    assert len(verts) == 6
    assert len(colors) == 6


def test_deux_blocs_adjacents_produisent_dix_faces():
    w = monde_vide()
    w.set(5, 5, 5, Block.STONE)
    w.set(6, 5, 5, Block.STONE)
    verts, _ = build_detail(w, 0, 0)
    assert len(verts) == 10  # 12 - 2 faces partagées


def test_face_enterree_non_emise():
    w = monde_vide()
    w.set(5, 5, 0, Block.STONE)  # sous z=0 : considéré solide → face du dessous cachée
    verts, _ = build_detail(w, 0, 0)
    assert len(verts) == 5


def test_face_cote_eau_est_cachee():
    w = monde_vide()
    w.set(5, 5, 5, Block.STONE)
    w.set(5, 5, 6, Block.WATER)  # l'eau cache la face du dessus
    verts, _ = build_detail(w, 0, 0)
    # pierre : 5 faces (dessus caché) + eau : 5 faces (dessous caché par la pierre)
    assert len(verts) == 10


def test_couleur_du_dessus():
    w = monde_vide()
    w.set(5, 5, 5, Block.GRASS)
    verts, colors = build_detail(w, 0, 0)
    for quad, col in zip(verts, colors):
        if all(p[2] == 6 for p in quad):
            assert col == config.BLOCK_COLORS[Block.GRASS][0]
            break
    else:
        pytest.fail("aucune face du dessus trouvée")


def test_les_faces_restent_dans_les_bornes_du_chunk():
    w = monde_vide()
    w.set(17, 3, 5, Block.STONE)  # chunk (1, 0)
    verts, _ = build_detail(w, 1, 0)
    assert len(verts) == 6
    for quad in verts:
        for x, y, z in quad:
            assert CHUNK <= x <= 2 * CHUNK
            assert 0 <= y <= CHUNK
            assert 0 <= z <= 16


def test_cache_reutilise_le_maillage():
    w = monde_vide()
    w.set(5, 5, 5, Block.STONE)
    cache = ChunkMeshes(w)
    a = cache.detail(0, 0)
    b = cache.detail(0, 0)
    assert a is b


def test_invalidation_reconstruit_le_chunk():
    w = monde_vide()
    w.set(5, 5, 5, Block.STONE)
    cache = ChunkMeshes(w)
    a = cache.detail(0, 0)
    w.set(6, 5, 5, Block.STONE)
    cache.invalidate(6, 5)
    b = cache.detail(0, 0)
    assert a is not b
    assert len(b[0]) == 10


def test_invalidation_touche_le_chunk_voisin_sur_le_bord():
    w = monde_vide()
    w.set(15, 5, 5, Block.STONE)  # dernier bloc du chunk (0, 0) en x
    cache = ChunkMeshes(w)
    avant, _ = cache.detail(0, 0)
    assert len(avant) == 6
    w.set(16, 5, 5, Block.STONE)  # dans le chunk voisin : cache la face +x
    cache.invalidate(16, 5)
    apres, _ = cache.detail(0, 0)
    assert len(apres) == 5


def test_maillage_d_un_chunk_de_terrain_rapide():
    w = World(seed=0)  # monde réel
    t0 = time.perf_counter()
    verts, colors = build_detail(w, 8, 8)
    dt = (time.perf_counter() - t0) * 1000
    assert len(verts) > 0
    assert len(colors) == len(verts)
    assert dt < 8.0, f"maillage trop lent : {dt:.1f} ms"


# ----------------------------------------------------------------------
# Greedy meshing (T6)
# ----------------------------------------------------------------------
def chunk_plein(w, cx=0, cy=0, hauteur=5, bloc=Block.STONE):
    for y in range(cy * CHUNK, (cy + 1) * CHUNK):
        for x in range(cx * CHUNK, (cx + 1) * CHUNK):
            for z in range(hauteur):
                w.set(x, y, z, bloc)


def test_greedy_plaque_pleine_donne_un_seul_dessus():
    w = monde_vide()
    chunk_plein(w, hauteur=5)
    verts, cols = build_greedy(w, 0, 0)
    dessus = [q for q in verts if all(abs(p[2] - 5) < 1e-6 for p in q)]
    assert len(dessus) == 1
    xs = [p[0] for p in dessus[0]]
    ys = [p[1] for p in dessus[0]]
    # le quad couvre tout le chunk (avec le recouvrement EPS)
    assert min(xs) <= 0.001 and max(xs) >= 16.0
    assert min(ys) <= 0.001 and max(ys) >= 16.0


def test_greedy_reduit_fortement_le_nombre_de_quads_en_terrain_plat():
    w = monde_vide()
    chunk_plein(w, hauteur=5)
    detail, _ = build_detail(w, 0, 0)
    greedy, _ = build_greedy(w, 0, 0)
    assert len(greedy) * 10 <= len(detail)


def test_greedy_ne_depasse_jamais_le_detail_sur_du_terrain():
    w = World(seed=0)
    for cx, cy in [(8, 8), (0, 0), (5, 9)]:
        detail = len(build_detail(w, cx, cy)[0])
        greedy = len(build_greedy(w, cx, cy)[0])
        assert greedy < detail


def test_greedy_quads_sont_legerement_etendus():
    w = monde_vide()
    chunk_plein(w, hauteur=5)
    verts, _ = build_greedy(w, 0, 0)
    dessus = [q for q in verts if all(abs(p[2] - 5) < 1e-6 for p in q)][0]
    xs = [p[0] for p in dessus]
    assert min(xs) < 0.0  # déborde de EPS pour boucher les T-junctions
    assert max(xs) > 16.0


def test_greedy_cache_et_invalidation():
    w = monde_vide()
    w.set(5, 5, 5, Block.STONE)
    cache = ChunkMeshes(w)
    a = cache.greedy(0, 0)
    assert cache.greedy(0, 0) is a
    w.set(6, 5, 5, Block.STONE)
    cache.invalidate(6, 5)
    b = cache.greedy(0, 0)
    assert a is not b


def test_select_mesh_choisit_le_lod():
    w = monde_vide()
    w.set(5, 5, 5, Block.STONE)
    cache = ChunkMeshes(w)
    detail, _ = cache.detail(0, 0)
    greedy, _ = cache.greedy(0, 0)
    assert select_mesh(cache, 0, 0, distance=10, detail_radius=24)[0] is detail
    assert select_mesh(cache, 0, 0, distance=40, detail_radius=24)[0] is greedy
    assert select_mesh(cache, 0, 0, distance=10, detail_radius=24, use_detail=False)[0] is greedy


def test_greedy_conserve_les_types_de_blocs():
    w = monde_vide()
    w.set(0, 0, 0, Block.GRASS)
    w.set(1, 0, 0, Block.STONE)
    verts, cols = build_greedy(w, 0, 0)
    haut = [c for q, c in zip(verts, cols) if all(abs(p[2] - 1) < 1e-6 for p in q)]
    assert len(haut) == 2  # deux types différents ne fusionnent pas
    assert set(haut) == {config.BLOCK_COLORS[Block.GRASS][0], config.BLOCK_COLORS[Block.STONE][0]}
