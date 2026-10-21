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
