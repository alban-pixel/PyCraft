"""Tests for the findings of the final review: junk packs must never crash the game, and empty
or see-through textures must not spoil the colors."""
import json
import zipfile

import numpy as np

from pycraft import blocks as B
from pycraft.blocks import TINT_ALPHA
from pycraft.tiles import block_colors, build_tiles, tiles_to_atlas
from pycraft.app import icon_palette, load_tiles
from pycraft.packs import find_packs, load_pack
from pycraft.render import split_tiles
from tests.packfactory import make_pack, png, solid


def _corrupt_member(path, member):
    """Damage the deflate stream of one member of a zip, leaving the zip's directory intact."""
    with zipfile.ZipFile(path) as z:
        info = z.getinfo(member)
        start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        size = info.compress_size
    data = bytearray(open(path, "rb").read())
    for i in range(start, start + size):
        data[i] = 0xFF
    open(path, "wb").write(bytes(data))


def _deflated_pack(tmp_path, textures, description="x"):
    path = tmp_path / "p.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("pack.mcmeta", json.dumps({"pack": {"description": description * 50}}))
        for name, pixels in textures.items():
            z.writestr(f"assets/minecraft/textures/blocks/{name}.png", png(pixels))
    return str(path)


def test_corrupt_mcmeta_does_not_crash(tmp_path):
    path = _deflated_pack(tmp_path, {"stone": solid((1, 2, 3))})
    _corrupt_member(path, "pack.mcmeta")
    (found,) = find_packs([str(tmp_path)], [])  # no exception, and the pack is still listed
    assert found.description == ""


def test_corrupt_texture_member_is_missing(tmp_path):
    path = _deflated_pack(tmp_path, {"stone": solid((1, 2, 3)), "dirt": solid((4, 5, 6))})
    _corrupt_member(path, "assets/minecraft/textures/blocks/stone.png")
    (info,) = find_packs([str(tmp_path)], [])
    tiles, missing = load_pack(info, build_tiles())
    assert "stone" in missing


def test_deeply_nested_description(tmp_path):
    root = str(tmp_path)
    path = make_pack(root, "Deep", "1.8", {"stone": solid((1, 2, 3))})
    with open(f"{path}/pack.mcmeta", "w") as f:
        f.write('{"pack": {"description": ' + "[" * 5000 + "]" * 5000 + "}}")
    (info,) = find_packs([root], [])
    assert info.description == ""


def test_load_tiles_never_raises(tmp_path):
    default = build_tiles()
    junk = tmp_path / "junk.zip"
    junk.write_bytes(b"PK\x03\x04 not a zip at all")
    tiles, message, path = load_tiles(str(junk), [], default)
    assert tiles is default and path is None and message.startswith("Pack unreadable")


def test_clear_glass_icons(tmp_path):
    tiles = build_tiles()
    tiles[B.T_GLASS, ..., 3] = 0  # a "clear glass" pack
    colors, indices = icon_palette(tiles_to_atlas(tiles))
    assert len(colors) == 48


def test_block_colors_empty_tile():
    tiles = build_tiles()
    tiles[B.T_GLASS, ..., 3] = 0
    tiles[B.T_TALL_GRASS, ..., 3] = 0
    assert np.isfinite(block_colors(tiles)).all()


def test_see_through_water_stays_water(tmp_path):
    water = solid((60, 60, 200, 60))  # alpha below 128: a "clear water" pack
    make_pack(str(tmp_path), "W", "1.8", {"water_still": water})
    (info,) = find_packs([str(tmp_path)], [])
    tiles, _ = load_pack(info, build_tiles())
    assert (tiles[B.T_WATER][..., 3] > 0).all()


def test_tint_mask_holes_take_the_mean():
    tiles = np.zeros((256, 4, 4, 4), np.uint8)
    tiles[B.T_TALL_GRASS, :2] = (200, 200, 200, TINT_ALPHA)  # half tinted, half holes
    _, mask = split_tiles(tiles)
    assert (mask[B.T_TALL_GRASS, :2] == 255).all()
    assert (mask[B.T_TALL_GRASS, 2:] == 255).all()  # holes don't dilute the tint in the mipmaps


def test_load_tiles_any_error_falls_back(tmp_path, monkeypatch):
    from pycraft import packs
    make_pack(str(tmp_path), "P", "1.8", {"stone": solid((1, 2, 3))})
    found = find_packs([str(tmp_path)], [])

    def broken(info, base):
        raise KeyError("something unexpected inside the pack")
    monkeypatch.setattr(packs, "load_pack", broken)
    default = build_tiles()
    tiles, message, path = load_tiles(found[0].path, found, default)
    assert tiles is default and path is None and "Pack unreadable" in message
