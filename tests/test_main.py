"""Tests des arguments de la ligne de commande et du HUD."""

import pytest

import main
from pycraft import config
from pycraft.hud import slot_rect


def test_valeurs_par_defaut():
    args = main.parse_args([])
    assert args.res == (1280, 800)
    assert args.dist == config.DEFAULT_VIEW_DISTANCE
    assert args.detail == config.DEFAULT_DETAIL_RADIUS
    assert args.no_lod is False
    assert args.seed == 0


def test_resolution_personnalisee():
    assert main.parse_args(["--res", "1920x1200"]).res == (1920, 1200)


def test_resolution_invalide():
    with pytest.raises(SystemExit):
        main.parse_args(["--res", "abc"])


def test_resolution_trop_small():
    with pytest.raises(SystemExit):
        main.parse_args(["--res", "100x100"])


def test_options_lod_et_detail():
    args = main.parse_args(["--no-lod", "--detail", "8", "--dist", "64", "--seed", "42"])
    assert args.no_lod is True
    assert args.detail == 8
    assert args.dist == 64
    assert args.seed == 42


def test_hotbar_centree():
    x0, y0, w, h = slot_rect(1280, 800, 0, 3)
    x2, _, _, _ = slot_rect(1280, 800, 2, 3)
    assert x0 < x2
    assert 0 < y0 < 800
    centre = (x0 + x2 + w) / 2
    assert abs(centre - 640) < 4


def test_options_gpu():
    args = main.parse_args(["--cpu", "--no-shadows"])
    assert args.cpu is True
    assert args.no_shadows is True


def test_gpu_par_defaut():
    args = main.parse_args([])
    assert args.cpu is False
    assert args.no_shadows is False


def test_option_meteo():
    assert main.parse_args(["--weather"]).weather is True


def _etat_de_jeu(pyxel_headless):
    import main

    etat = main.construire(320, 200, 0, 32, 8)
    main._etat.update(etat)
    main._etat["ecran"] = "jeu"
    main._etat["souris"] = True
    main._etat["aide"] = False
    main._etat["stats"] = False
    return main


def test_la_meteo_ne_plante_pas_la_boucle(pyxel_headless):
    """La branche météo lisait `renderer` sans l'avoir défini (NameError)."""
    main = _etat_de_jeu(pyxel_headless)
    main._etat["weather"] = True
    main.update()  # ne doit pas lever


def test_casser_un_bloc_ne_plante_pas_la_boucle(pyxel_headless, monkeypatch):
    """Le clic gauche utilisait `renderer` hors de portée (NameError)."""
    import pyxel

    main = _etat_de_jeu(pyxel_headless)
    main._etat["weather"] = False
    joueur = main._etat["joueur"]
    joueur.pitch = -1.2  # regarde le sol, à portée
    monkeypatch.setattr(pyxel, "btnp", lambda touche: touche == pyxel.MOUSE_BUTTON_LEFT)
    main.update()  # ne doit pas lever
    assert main._etat["selection"] is not None, "le joueur doit viser un bloc"
