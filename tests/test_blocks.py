import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import blocks


def test_block_constants():
    assert blocks.AIR == 0
    assert blocks.GRASS == 1
    assert blocks.NUM_BLOCKS == len(blocks.BLOCK_NAMES)
    assert blocks.NUM_BLOCKS >= 15
    assert "Diamond ore" in blocks.BLOCK_NAMES
    assert "Gold ore" in blocks.BLOCK_NAMES
    assert "Snow" in blocks.BLOCK_NAMES


def test_block_flags():
    assert not blocks.SOLID[blocks.AIR]
    assert not blocks.SOLID[blocks.WATER]
    assert blocks.SOLID[blocks.STONE]
    assert blocks.SOLID[blocks.GRASS]
    assert blocks.SOLID[blocks.DIAMOND_ORE]

    assert not blocks.OPAQUE[blocks.AIR]
    assert not blocks.OPAQUE[blocks.GLASS]
    assert not blocks.OPAQUE[blocks.WATER]
    assert not blocks.OPAQUE[blocks.LEAVES]
    assert blocks.OPAQUE[blocks.STONE]

    assert blocks.CUTOUT[blocks.GLASS]
    assert blocks.CUTOUT[blocks.LEAVES]


def test_texture_atlas_generation():
    atlas = blocks.build_atlas(seed=42)
    assert atlas.ndim == 3
    assert atlas.shape in [(128, 128, 4), (256, 256, 4)]
    assert atlas.dtype == np.uint8
    assert blocks.BLOCK_TILES.shape == (blocks.NUM_BLOCKS, 6)
