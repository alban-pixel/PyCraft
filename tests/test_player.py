"""Tests du joueur : déplacement, collisions et glissement."""

import math

import pytest

from pycraft import config
from pycraft.config import Block
from pycraft.player import Player
from pycraft.world import World


def monde_plat(sx=32, sy=32, sz=16, hauteur=4) -> World:
    """Un sol plein, vide au-dessus."""
    w = World(sx=sx, sy=sy, sz=sz, seed=0)
    w.data = bytearray(len(w.data))
    for y in range(sy):
        for x in range(sx):
            for z in range(hauteur):
                w.set(x, y, z, Block.STONE)
    return w


def joueur(x=10.5, y=10.5, z=4.0) -> Player:
    return Player(x, y, z)


def test_deplacement_simple():
    w = monde_plat()
    p = joueur()
    p.move(w, 1.0, 0.0)
    assert p.x == pytest.approx(11.5)
    assert p.y == pytest.approx(10.5)


def test_un_mur_stoppe_le_joueur():
    w = monde_plat()
    for y in range(32):
        for z in range(8):
            w.set(15, y, z, Block.STONE)
    p = joueur()
    p.move(w, 20.0, 0.0)  # traverserait le mur sans collisions
    assert p.x < 15.0
    assert p.x == pytest.approx(15 - p.radius, abs=0.15)


def test_glissement_le_long_d_un_mur():
    w = monde_plat()
    for y in range(32):
        for z in range(8):
            w.set(15, y, z, Block.STONE)
    p = joueur()
    depart_y = p.y
    p.move(w, 2.0, 2.0)
    assert p.x < 15.0          # bloqué en x
    assert p.y > depart_y + 1  # mais avance en y


def test_la_camera_reste_dans_les_bornes():
    w = monde_plat(sx=8, sy=8)
    p = joueur(x=4.0, y=4.0)
    p.move(w, -100.0, -100.0)
    assert p.x >= p.radius
    assert p.y >= p.radius
    p.move(w, 200.0, 200.0)
    assert p.x <= 8 - p.radius
    assert p.y <= 8 - p.radius


def test_collision_avec_un_bloc_solide():
    w = monde_plat()
    w.set(10, 10, 4, Block.STONE)
    p = joueur()
    assert p.collides(w, 10.5, 10.5, 4.0)
    assert not p.collides(w, 12.5, 10.5, 4.0)


def test_l_eau_ne_bloque_pas():
    w = monde_plat()
    w.set(12, 10, 4, Block.WATER)
    p = joueur()
    assert not p.collides(w, 12.5, 10.5, 4.0)


def test_update_avance_dans_la_direction_du_regard():
    w = monde_plat()
    p = joueur()
    p.set_angles(0.0, 0.0)  # regarde vers +X
    p.update(w, dt=0.1, avant=1.0)
    assert p.x > 10.5
    assert p.y == pytest.approx(10.5, abs=1e-6)


def test_update_tourne_la_camera():
    w = monde_plat()
    p = joueur()
    p.update(w, dt=1.0, tourner=math.pi / 2)
    assert p.yaw == pytest.approx(math.pi / 2)


# ----------------------------------------------------------------------
# Raycast (T9)
# ----------------------------------------------------------------------
def mur_en_x(w, x=15, zmax=8):
    for y in range(w.sy):
        for z in range(zmax):
            w.set(x, y, z, Block.STONE)


def test_raycast_touche_le_bloc_devant():
    w = monde_plat()
    mur_en_x(w)
    p = joueur()
    p.set_angles(0.0, 0.0)
    resultat = p.raycast(w, 6.0)
    assert resultat == ((15, 10, 5), (-1, 0, 0))


def test_raycast_portee_limitee():
    w = monde_plat()
    mur_en_x(w)
    p = joueur()
    p.set_angles(0.0, 0.0)
    assert p.raycast(w, 2.0) is None


def test_raycast_ignore_l_eau():
    w = monde_plat()
    w.set(12, 10, 5, Block.WATER)
    p = joueur()
    p.set_angles(0.0, 0.0)
    assert p.raycast(w, 6.0) is None


def test_raycast_vers_le_haut():
    w = monde_plat()
    w.set(10, 10, 7, Block.STONE)
    p = joueur()
    p.set_angles(0.0, math.pi / 2 - 0.01)
    resultat = p.raycast(w, 5.0)
    assert resultat is not None
    bloc, normale = resultat
    assert bloc == (10, 10, 7)
    assert normale == (0, 0, -1)


def test_raycast_portee_par_defaut_cinq_blocs():
    w = monde_plat()
    mur_en_x(w, x=17)  # 6,5 blocs devant l'œil
    p = joueur()
    p.set_angles(0.0, 0.0)
    assert p.raycast(w) is None


# ----------------------------------------------------------------------
# Casser / poser (T10)
# ----------------------------------------------------------------------
from pycraft.mesher import ChunkMeshes


def test_casser_supprime_le_bloc_vise():
    w = monde_plat()
    mur_en_x(w)
    p = joueur()
    p.set_angles(0.0, 0.0)
    cache = ChunkMeshes(w)
    assert p.break_block(w, cache) is True
    assert w.get(15, 10, 5) is Block.AIR


def test_casser_sans_cible_echoue():
    w = monde_plat()
    p = joueur()
    p.set_angles(0.0, math.pi / 2 - 0.01)  # vers le ciel
    cache = ChunkMeshes(w)
    assert p.break_block(w, cache) is False


def test_poser_sur_la_face_visée():
    w = monde_plat()
    mur_en_x(w)
    p = joueur()
    p.set_angles(0.0, 0.0)
    cache = ChunkMeshes(w)
    assert p.place_block(w, cache, Block.GRASS) is True
    assert w.get(14, 10, 5) is Block.GRASS


def test_poser_dans_le_joueur_est_refuse():
    w = monde_plat()
    p = joueur()
    p.set_angles(0.0, -math.pi / 2 + 0.01)  # vers ses pieds
    cache = ChunkMeshes(w)
    assert p.place_block(w, cache, Block.STONE) is False
    assert w.get(10, 10, 4) is Block.AIR


def test_poser_hors_des_bornes_est_refuse():
    w = monde_plat(sx=8, sy=8)
    w.set(0, 0, 4, Block.STONE)
    p = joueur(x=1.5, y=1.5, z=4.0)
    p.set_angles(math.pi, 0.0)  # regarde vers -X, vers le bord
    cache = ChunkMeshes(w)
    ok = p.place_block(w, cache, Block.STONE)
    assert ok is False
