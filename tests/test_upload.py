import numpy as np
import pytest

from pycraft import blocks as B
from pycraft.blocks import TINT_ALPHA
from pycraft.tiles import build_tiles, resize_tile
from pycraft.render import make_tile_textures, split_tiles


def test_split_tiles():
    tiles = np.zeros((256, 4, 4, 4), np.uint8)
    glass, leaves = B.T_GLASS, B.T_LEAVES
    for t in (glass, leaves):
        tiles[t, ..., :3] = 0
        tiles[t, 0, :] = (100, 50, 20, 255)
        tiles[t, 1, :] = (60, 70, 80, TINT_ALPHA)
        tiles[t, 2:, :] = (0, 0, 0, 0)  # holes
    rgba, mask = split_tiles(tiles)
    assert set(np.unique(rgba[glass, ..., 3])) == {0, 255}
    assert (rgba[glass, 1, :, 3] == 255).all() and (rgba[glass, 2:, :, 3] == 0).all()
    assert (mask[glass, 1] == 255).all() and (mask[glass, 0] == 0).all()
    assert (mask[glass, 2:] == 128).all()  # holes: the share of tinted texels around (4 of 8)
    assert (rgba[glass, 2:, :, :3] == (80, 60, 50)).all()  # a glass hole: the average seen color
    assert (rgba[leaves, 2:, :, :3] == 0).all()  # a leaf hole keeps its color (it is drawn)


@pytest.fixture(scope="module")
def ctx():
    moderngl = pytest.importorskip("moderngl")
    try:
        ctx = moderngl.create_standalone_context()
    except Exception as e:  # no graphics card driver here
        pytest.skip(f"no OpenGL context: {e}")
    yield ctx
    ctx.release()


def test_upload_headless(ctx):
    atlas, tint = make_tile_textures(ctx, build_tiles())
    assert atlas.size == (16, 16, 256) and atlas.layers == 256 and atlas.components == 4
    assert tint.size == (16, 16, 256) and tint.layers == 256 and tint.components == 1
    big = np.stack([resize_tile(t, 64) for t in build_tiles()])
    atlas, _ = make_tile_textures(ctx, big)
    assert atlas.size == (64, 64, 256)


def test_palette_set_fixed(ctx):
    from pycraft.render import FIXED_COLORS, Palette
    palette = Palette(ctx, np.zeros((FIXED_COLORS, 3)))  # (0-255 RGB, as the Renderer gives it)
    palette.apply()
    version = palette.version
    palette.set_fixed([0xFF0000] * (FIXED_COLORS - 16))
    palette.apply()
    assert palette.colors[16] == 0xFF0000 and palette.colors[FIXED_COLORS - 1] == 0xFF0000
    assert palette.colors[15] == 0x000000  # Pyxel's own 16 stay
    assert palette.version > version
