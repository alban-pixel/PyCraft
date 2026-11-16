import os

import numpy as np
import pytest

import blocks
import renderer
from blocks import TINT_ALPHA, build_tiles, resize_tile, tiles_to_atlas

REFERENCE = os.path.join(os.path.dirname(__file__), "data", "default_reference.npz")


@pytest.fixture(scope="module")
def reference():
    with np.load(REFERENCE) as f:
        return {k: f[k] for k in f.files}


@pytest.fixture(scope="module")
def tiles():
    return build_tiles()


def test_tiles_shape(tiles):
    assert tiles.shape == (256, 16, 16, 4) and tiles.dtype == np.uint8


def test_tiles_match_atlas(tiles, reference):
    assert np.array_equal(tiles_to_atlas(tiles), reference["atlas"])
    assert np.array_equal(blocks.build_atlas(), reference["atlas"])


def test_resize_roundtrip(tiles):
    for t in range(256):
        assert np.array_equal(resize_tile(resize_tile(tiles[t], 64), 16), tiles[t]), t


def test_resize_keeps_tint():
    tile = np.full((32, 32, 4), 120, np.uint8)
    tile[:, :16, 3] = TINT_ALPHA
    tile[:, 16:, 3] = 255
    small = resize_tile(tile, 16)
    assert (small[:, :8, 3] == TINT_ALPHA).all()
    assert (small[:, 8:, 3] == 255).all()


def test_resize_odd_sizes():
    tile = np.zeros((20, 20, 4), np.uint8)
    tile[..., 3] = 255
    assert resize_tile(tile, 16).shape == (16, 16, 4)
    assert resize_tile(tile, 64).shape == (64, 64, 4)


def test_block_colors_unchanged(tiles, reference):
    assert np.allclose(blocks.block_colors(tiles), reference["block_colors"])
    assert np.allclose(renderer.tile_averages(tiles), reference["tile_averages"])


def test_block_colors_size_free(tiles):
    big = np.stack([resize_tile(t, 64) for t in tiles])
    assert np.allclose(blocks.block_colors(big), blocks.block_colors(tiles))
    assert np.allclose(renderer.tile_averages(big), renderer.tile_averages(tiles))
