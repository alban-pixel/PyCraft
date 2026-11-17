import os

import numpy as np
import pytest

from pycraft import blocks as B
from pycraft.blocks import TINT_ALPHA
from pycraft.tiles import build_tiles, resize_tile
from pycraft.packs import TILE_FILES, PackError, find_packs, load_pack
from tests.packfactory import make_pack, solid

JAR_18 = os.path.expanduser("~/Library/Application Support/minecraft/versions/1.8/1.8.jar")


@pytest.fixture(scope="module")
def base():
    return build_tiles()


def load(tmp_path, layout, textures, raw=None, zip=False):
    root = str(tmp_path / "packs")
    make_pack(root, "P", layout, textures, raw=raw, zip=zip)
    (info,) = find_packs([root], [])
    return load_pack(info, build_tiles())


def test_every_used_tile_mapped():
    used = {int(t) for row in B.BLOCK_TILES for t in row}
    assert used <= set(TILE_FILES)


def test_size_is_most_common(tmp_path, base):
    tex = {"stone": solid((10, 20, 30), 64), "dirt": solid((1, 2, 3), 64), "sand": solid((4, 5, 6), 64),
           "gravel": solid((7, 8, 9), 16)}
    tiles, _ = load(tmp_path, "1.8", tex)
    assert tiles.shape == (256, 64, 64, 4)
    assert (tiles[B.T_GRAVEL][..., :3] == (7, 8, 9)).all()
    assert np.array_equal(tiles[B.T_BRICK], resize_tile(base[B.T_BRICK], 64))


def test_size_rounded_and_clamped(tmp_path):
    tiles, _ = load(tmp_path, "1.8", {"stone": solid((1, 1, 1), 8)})
    assert tiles.shape[1] == 16
    tiles, _ = load(tmp_path / "b", "1.8", {"stone": solid((1, 1, 1), 30)})
    assert tiles.shape[1] == 32


def test_animated_takes_first_frame(tmp_path):
    strip = np.concatenate([solid((200, 0, 0)), solid((0, 0, 200)), solid((0, 0, 200))])
    tiles, _ = load(tmp_path, "1.8", {"water_still": strip})
    assert tiles[B.T_WATER][..., 0].min() > tiles[B.T_WATER][..., 2].max()


def test_fallback_names(tmp_path):
    tiles, missing = load(tmp_path, "1.13", {"log_oak": solid((90, 60, 30)), "stone": solid((1, 1, 1))})
    assert (tiles[B.T_LOG_SIDE][..., :3] == (90, 60, 30)).all()


def test_missing_uses_generated(tmp_path, base):
    tiles, missing = load(tmp_path, "1.8", {"stone": solid((10, 20, 30))})
    assert (tiles[B.T_STONE][..., :3] == (10, 20, 30)).all()
    assert np.array_equal(tiles[B.T_DIRT], base[B.T_DIRT])
    assert "dirt" in missing


def test_grey_grass_tinted(tmp_path):
    tiles, _ = load(tmp_path, "1.8", {"grass_top": solid((128, 128, 128))})
    t = tiles[B.T_GRASS_TOP]
    assert (t[..., 3] == TINT_ALPHA).all()
    assert abs(t[..., :3].mean() - 204) <= 1


def test_colored_grass_not_tinted(tmp_path):
    tiles, _ = load(tmp_path, "1.8", {"grass_top": solid((40, 160, 40))})
    t = tiles[B.T_GRASS_TOP]
    assert (t[..., 3] == 255).all() and (t[..., :3] == (40, 160, 40)).all()


def test_grass_side_overlay(tmp_path):
    overlay = np.zeros((16, 16, 4), np.uint8)
    overlay[:3] = (150, 150, 150, 255)
    tiles, _ = load(tmp_path, "1.8", {"grass_side": solid((120, 80, 50)), "grass_side_overlay": overlay})
    t = tiles[B.T_GRASS_SIDE]
    assert (t[:3, :, 3] == TINT_ALPHA).all()
    assert (t[3:, :, 3] == 255).all() and (t[3:, :, :3] == (120, 80, 50)).all()


def test_spruce_fixed_color(tmp_path):
    leaves = solid((255, 255, 255, 255))
    leaves[::4, ::4, 3] = 0
    tiles, _ = load(tmp_path, "1.8", {"leaves_spruce": leaves})
    t = tiles[B.T_SPRUCE_LEAVES]
    seen = t[..., 3] > 0
    assert (t[seen][:, 3] == 255).all()
    assert (t[seen][:, :3] == (0x61, 0x99, 0x61)).all()


def test_leaf_holes_filled(tmp_path):
    leaves = solid((200, 200, 200, 255))
    leaves[::2, ::2] = (0, 0, 0, 0)
    tiles, _ = load(tmp_path, "1.8", {"leaves_oak": leaves})
    t = tiles[B.T_LEAVES]
    holes = t[..., 3] == 0
    assert holes.any()
    seen_mean = t[~holes][:, :3].astype(float).mean(axis=0)
    assert np.allclose(t[holes][:, :3], seen_mean, atol=1)


def test_corrupt_png_is_missing(tmp_path):
    tiles, missing = load(tmp_path, "1.8", {"dirt": solid((1, 2, 3))}, raw={"stone": b"\x89PNG not really"})
    assert "stone" in missing


def test_palette_and_grey_alpha_modes(tmp_path):
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("LA", (16, 16), (90, 255)).save(buf, "PNG")
    buf2 = io.BytesIO()
    Image.new("P", (16, 16), 3).save(buf2, "PNG")
    tiles, missing = load(tmp_path, "1.8", {}, raw={"stone": buf.getvalue(), "dirt": buf2.getvalue()})
    assert "stone" not in missing and "dirt" not in missing
    assert (tiles[B.T_STONE][..., :3] == 90).all()


def test_empty_pack_raises(tmp_path):
    with pytest.raises(PackError):
        load(tmp_path, "1.8", {"not_a_block_we_know": solid((1, 1, 1))})


def test_zip_pack_loads(tmp_path):
    tiles, _ = load(tmp_path, "1.13", {"stone": solid((10, 20, 30))}, zip=True)
    assert (tiles[B.T_STONE][..., :3] == (10, 20, 30)).all()


@pytest.mark.skipif(not os.path.isfile(JAR_18), reason="no local Minecraft 1.8")
def test_real_minecraft_jar(base):
    (info,) = find_packs([], [JAR_18])
    tiles, missing = load_pack(info, base)
    assert tiles.shape[1] == 16
    without_18 = sum(1 for names_18, _ in TILE_FILES.values() if not names_18)
    assert len(missing) <= 5, missing
    assert without_18 < 40
