"""Tests du monde voxel."""

import time

import pytest

from pycraft import config
from pycraft.world import World


def petit_monde(seed: int = 1) -> World:
    return World(sx=32, sy=32, sz=16, seed=seed)


def test_hors_bornes_horizontales_est_de_l_air():
    w = petit_monde()
    assert w.get(-1, 0, 0) is config.Block.AIR
    assert w.get(0, -1, 0) is config.Block.AIR
    assert w.get(w.sx, 0, 0) is config.Block.AIR
    assert w.get(0, w.sy, 0) is config.Block.AIR


def test_sous_le_monde_est_solide():
    w = petit_monde()
    assert w.get(3, 3, -1) is config.Block.STONE
    assert w.is_solid(3, 3, -1)


def test_au_dessus_du_monde_est_de_l_air():
    w = petit_monde()
    assert w.get(3, 3, w.sz) is config.Block.AIR


def test_set_puis_get_renvoie_la_nouvelle_valeur():
    w = petit_monde()
    w.set(4, 5, 10, config.Block.WOOD)
    assert w.get(4, 5, 10) is config.Block.WOOD
    w.set(4, 5, 10, config.Block.AIR)
    assert w.get(4, 5, 10) is config.Block.AIR


def test_is_solid_faux_pour_air_et_eau():
    w = petit_monde()
    w.set(2, 2, 12, config.Block.AIR)
    w.set(2, 2, 13, config.Block.WATER)
    assert not w.is_solid(2, 2, 12)
    assert not w.is_solid(2, 2, 13)
    w.set(2, 2, 14, config.Block.STONE)
    assert w.is_solid(2, 2, 14)


def test_generation_deterministe():
    a = petit_monde(seed=42)
    b = petit_monde(seed=42)
    assert bytes(a.data) == bytes(b.data)


def test_seeds_differentes_donnent_des_mondes_differents():
    a = petit_monde(seed=1)
    b = petit_monde(seed=2)
    assert bytes(a.data) != bytes(b.data)


def test_le_monde_contient_de_l_herbe_et_de_l_eau():
    w = petit_monde(seed=7)
    types = set(w.data)
    assert config.Block.GRASS in types
    assert config.Block.WATER in types


def test_spawn_jamais_dans_un_bloc_solide():
    for seed in (0, 1, 2, 3):
        w = petit_monde(seed=seed)
        x, y, z = w.spawn_point()
        assert not w.is_solid(int(x), int(y), int(z))
        assert 0 <= x < w.sx and 0 <= y < w.sy


def test_generation_du_monde_complet_rapide():
    t0 = time.perf_counter()
    w = World(seed=0)
    dt = time.perf_counter() - t0
    assert (w.sx, w.sy, w.sz) == (config.WORLD_X, config.WORLD_Y, config.WORLD_Z)
    assert dt < 1.5, f"génération trop lente : {dt:.2f} s"


def test_hauteur_de_surface():
    w = petit_monde()
    h = w.surface_height(5, 5)
    assert 0 <= h <= w.sz
    # le bloc juste en dessous est solide (ou de l'eau), celui au-dessus est vide
    assert not w.is_solid(5, 5, h)
