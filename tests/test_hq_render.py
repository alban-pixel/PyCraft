"""The screenshot's drawing on the graphics card: the high-quality switch of the shaders, its
bigger shadow maps, and the accumulator that averages its passes. Skipped without OpenGL."""
import math

import numpy as np
import pytest

from pycraft.render import shaders
from pycraft.render.constants import SCREENSHOT_SHADOW_SIZE, SHADOW_SIZE
from pycraft.tiles import build_tiles


@pytest.fixture(scope="module")
def ctx():
    moderngl = pytest.importorskip("moderngl")
    try:
        ctx = moderngl.create_standalone_context()
    except Exception as e:  # no graphics card driver here
        pytest.skip(f"no OpenGL context: {e}")
    yield ctx
    ctx.release()


def scene(ctx, rgb, size=(8, 4)):
    """A scene texture of one color (or an (h, w, 3) array, bottom row first), as the renderer draws it."""
    w, h = size
    data = np.empty((h, w, 4), np.float16)
    data[..., :3] = rgb
    data[..., 3] = 1.0
    return ctx.texture((w, h), 4, data.tobytes(), dtype="f2")


def finish(c):
    return min(c, 0.8) + 0.2 * (1 - math.exp(-5 * max(c - 0.8, 0)))


def test_shaders_compile_with_hq(ctx):
    for vertex, fragment in ((shaders.BLOCK_VERTEX_SHADER, shaders.BLOCK_FRAGMENT_SHADER),
                             (shaders.LOD_VERTEX_SHADER, shaders.LOD_FRAGMENT_SHADER),
                             (shaders.CLOUD_VERTEX_SHADER, shaders.CLOUD_FRAGMENT_SHADER)):
        program = ctx.program(vertex_shader=vertex, fragment_shader=fragment)
        assert program.get("hq", None) is not None
        program.release()


def test_shadow_size(ctx):
    from pycraft.render import make_tile_textures
    from pycraft.render.shadows import Shadows
    atlas, tint = make_tile_textures(ctx, build_tiles())
    big = Shadows(ctx, atlas, tint, size=SCREENSHOT_SHADOW_SIZE)
    assert big.size == 4096 and big.textures[0].size == (4096, 4096)
    big.release()
    assert Shadows(ctx, atlas, tint).size == SHADOW_SIZE


def test_accumulator_average(ctx):
    from pycraft.render.accumulate import Accumulator
    acc = Accumulator(ctx, (8, 4))
    for grey in (0.1, 0.2, 0.3, 0.4):
        acc.add(scene(ctx, grey))
    rgb = acc.resolve(1.0, (1.0, 1.0, 1.0))
    assert rgb.shape == (4, 8, 3) and rgb.dtype == np.uint8
    assert np.abs(rgb.astype(int) - round(0.25 * 255)).max() <= 1
    acc.release()


def test_accumulator_rows(ctx):
    from pycraft.render.accumulate import Accumulator
    image = np.zeros((4, 8, 3))
    image[0] = (1.0, 0.0, 0.0)  # OpenGL's row 0: the bottom of the picture
    acc = Accumulator(ctx, (8, 4))
    acc.add(scene(ctx, image))
    rgb = acc.resolve(1.0, (1.0, 1.0, 1.0))
    assert (rgb[-1, :, 0] > 200).all() and (rgb[-1, :, 1:] == 0).all()
    assert (rgb[0] == 0).all()
    acc.release()


def test_accumulator_finish(ctx):
    from pycraft.render.accumulate import Accumulator
    acc = Accumulator(ctx, (8, 4))
    acc.add(scene(ctx, 2.0))
    assert set(np.unique(acc.resolve(1.0, (1.0, 1.0, 1.0)))) <= {254, 255}
    dimmed = acc.resolve(0.5, (1.0, 1.0, 1.0)).astype(int)
    assert np.abs(dimmed - round(0.5 * finish(2.0) * 255)).max() <= 1
    acc.release()
