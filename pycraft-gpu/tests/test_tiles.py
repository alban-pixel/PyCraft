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


def _as_tiles(atlas):
    return atlas.reshape(16, 16, 16, 16, 4).transpose(0, 2, 1, 3, 4).reshape(256, 16, 16, 4)


def test_tiles_match_atlas(tiles, reference):
    # The tiles that existed when the reference was made are unchanged (newer tiles come after)
    old = blocks.T_LEVER
    assert np.array_equal(_as_tiles(tiles_to_atlas(tiles))[:old], _as_tiles(reference["atlas"])[:old])
    assert np.array_equal(_as_tiles(blocks.build_atlas())[:old], _as_tiles(reference["atlas"])[:old])


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
    n = len(reference["block_colors"])  # (the blocks and tiles added since come after)
    assert np.allclose(blocks.block_colors(tiles)[:n], reference["block_colors"])
    assert np.allclose(renderer.tile_averages(tiles)[:blocks.T_LEVER], reference["tile_averages"][:blocks.T_LEVER])


def test_block_colors_size_free(tiles):
    big = np.stack([resize_tile(t, 64) for t in tiles])
    assert np.allclose(blocks.block_colors(big), blocks.block_colors(tiles))
    assert np.allclose(renderer.tile_averages(big), renderer.tile_averages(tiles))
