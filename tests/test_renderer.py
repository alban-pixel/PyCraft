"""Tests des fonctions pures du rendu (sans fenêtre)."""

import pytest

from pycraft import config
from pycraft.renderer import fog_color_index, fog_factor, nearest_palette, sky_color_at


def test_pas_de_brouillard_pres_de_la_camera():
    assert fog_factor(0.0, 96) == 0.0
    assert fog_factor(48.0, 96) == 0.0


def test_brouillard_complet_a_la_distance_de_vue():
    assert fog_factor(96.0, 96) == pytest.approx(1.0)
    assert fog_factor(500.0, 96) == 1.0


def test_brouillard_monotone():
    valeurs = [fog_factor(d, 96) for d in range(0, 100, 4)]
    assert valeurs == sorted(valeurs)


def test_distance_de_vue_nulle_ne_divise_pas_par_zero():
    assert fog_factor(10.0, 0) == 0.0


def test_couleur_sans_brouillard_inchangee():
    assert fog_color_index(11, 0.0) == 11


def test_couleur_avec_brouillard_complet_est_celle_du_ciel():
    assert fog_color_index(11, 1.0) == config.FOG_COLOR
    assert fog_color_index(3, 1.0) == config.FOG_COLOR


def test_couleur_intermediaire_reste_dans_la_palette():
    for facteur in (0.2, 0.5, 0.8):
        assert 0 <= fog_color_index(11, facteur) < 16


def test_ciel_par_bandes():
    assert sky_color_at(0.0) == config.SKY_HORIZON
    assert sky_color_at(1.0) == config.SKY_TOP


def test_nearest_palette_retrouve_chaque_couleur():
    for i, rgb in enumerate(config.PALETTE):
        assert nearest_palette(rgb) == i
