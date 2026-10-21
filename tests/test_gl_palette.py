"""T2 : palette 256, quantification et LUT."""

import numpy as np
import pytest

from pycraft.gl.palette import (
    PALETTE,
    build_lut,
    detect_palette_size,
    lut_lookup,
    nearest_index,
)


def test_palette_a_256_couleurs():
    assert PALETTE.shape == (256, 3)
    assert PALETTE.dtype == np.uint8


def test_couleurs_de_palette_retrouvent_leur_indice():
    indices = nearest_index(PALETTE.astype(np.int16))
    assert np.array_equal(indices, np.arange(256))


def test_quantification_d_un_rouge_pur():
    idx = nearest_index(np.array([[255, 0, 0]], dtype=np.int16))
    couleur = PALETTE[int(idx[0])]
    assert couleur[0] > 150 and couleur[0] > couleur[1] and couleur[0] > couleur[2]


def test_lut_32_proche_du_voisin_exact():
    lut = build_lut(PALETTE, bits=5)
    assert lut.shape == (32, 32, 32)
    rng = np.random.default_rng(0)
    couleurs = rng.integers(0, 256, size=(5000, 3), dtype=np.uint8)
    exact = nearest_index(couleurs.astype(np.int16))
    par_lut = lut_lookup(lut, couleurs, bits=5)
    err_exact = np.abs(PALETTE[exact].astype(int) - couleurs).sum(axis=1)
    err_lut = np.abs(PALETTE[par_lut].astype(int) - couleurs).sum(axis=1)
    assert (err_lut <= err_exact + 12).mean() >= 0.98


def test_lut_sur_les_couleurs_de_la_palette():
    lut = build_lut(PALETTE, bits=5)
    indices = lut_lookup(lut, PALETTE, bits=5)
    err = np.abs(PALETTE[indices].astype(int) - PALETTE.astype(int)).max()
    assert err <= 8


def test_detection_palette_256(pyxel_headless):
    assert detect_palette_size(pyxel_headless) == 256


def test_detection_repli_si_extensions_refusee():
    class Faux:
        colors = [0] * 16

        def pset(self, x, y, c):
            raise OverflowError

        def pget(self, x, y):
            return 0

    assert detect_palette_size(Faux()) == 16
