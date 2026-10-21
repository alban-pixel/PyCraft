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
