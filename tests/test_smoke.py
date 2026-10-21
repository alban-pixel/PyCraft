"""Tests de fumée : le paquet s'importe et la configuration est cohérente."""

import pytest

import pycraft
from pycraft import config


def test_package_version():
    assert pycraft.__version__ == "0.1.0"


def test_resolution_par_defaut():
    assert (config.DEFAULT_WIDTH, config.DEFAULT_HEIGHT) == (1280, 800)
    assert config.DEFAULT_WIDTH % 2 == 0


def test_blocs_et_couleurs():
    assert config.Block.AIR == 0
    # Chaque bloc non vide a une couleur pour ses 4 orientations
    for bloc in config.Block:
        if bloc is config.Block.AIR:
            continue
        assert len(config.BLOCK_COLORS[bloc]) == 4


def test_hotbar_non_vide():
    assert len(config.HOTBAR) == 3
    assert all(b is not config.Block.AIR for b in config.HOTBAR)
