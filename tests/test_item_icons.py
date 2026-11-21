import numpy as np

from pycraft import blocks as B
from pycraft import items as I
from pycraft import packs
from pycraft.icons import icon_palette, item_atlas
from pycraft.tiles import build_tiles, tiles_to_atlas
from tests.packfactory import make_pack, solid


def test_item_tiles_shape_and_visible():
    tiles = I.build_item_tiles()
    assert tiles.shape == (64, 16, 16, 4) and tiles.dtype == np.uint8
    assert set(np.unique(tiles[..., 3])) <= {0, 255}
    for item in range(I.STICK, I.DIAMOND_SHOVEL + 1):
        assert (tiles[item - I.FIRST_ITEM, ..., 3] > 0).sum() >= 20, I.name(item)


def test_item_tiles_differ():
    tiles = I.build_item_tiles()
    seen = {tiles[item - I.FIRST_ITEM].tobytes() for item in range(I.STICK, I.DIAMOND_SHOVEL + 1)}
    assert len(seen) == I.NUM_ITEMS  # no two items share an icon


def test_item_files_cover_items():
    for item in range(I.FIRST_ITEM, I.FIRST_ITEM + I.NUM_ITEMS):
        assert item in packs.ITEM_FILES, I.name(item)
    assert packs.ITEM_FILES[I.WOODEN_PICKAXE] == (("wood_pickaxe",), ("wooden_pickaxe",))


def test_load_item_tiles_from_pack(tmp_path):
    stick = solid((10, 200, 30))
    path = make_pack(str(tmp_path), "P", "1.8", {"stone": solid((90, 90, 90))}, items={"stick": stick})
    info = packs.PackInfo("P", path, "", "1.8")
    base = I.build_item_tiles()
    tiles, missing = packs.load_item_tiles(info, base)
    assert (tiles[I.STICK - I.FIRST_ITEM] == stick).all()
    assert (tiles[I.COAL - I.FIRST_ITEM] == base[I.COAL - I.FIRST_ITEM]).all()
    assert "coal" in missing


def test_load_item_tiles_shrinks_big_icons(tmp_path):
    path = make_pack(str(tmp_path), "Z", "1.13", {"stone": solid((90, 90, 90))},
                     items={"diamond": solid((0, 200, 200), size=32)}, zip=True)
    info = packs.PackInfo("Z", path, "", "1.13")
    tiles, _ = packs.load_item_tiles(info, I.build_item_tiles())
    assert tiles.shape == (64, 16, 16, 4)
    assert (tiles[I.DIAMOND - I.FIRST_ITEM, ..., :3] == (0, 200, 200)).all()


def test_load_item_tiles_never_raises(tmp_path):
    info = packs.PackInfo("X", str(tmp_path / "missing.zip"), "", "1.8")
    base = I.build_item_tiles()
    tiles, missing = packs.load_item_tiles(info, base)
    assert (tiles == base).all() and missing


def test_icon_palette_with_items():
    colors, blocks_idx, items_idx = icon_palette(tiles_to_atlas(build_tiles()), item_atlas(I.build_item_tiles()))
    assert len(colors) == 48
    assert blocks_idx.shape == (256, 256) and items_idx.shape == (256, 256)
    stick = items_idx[0:16, 0:16]  # tile 0 is the stick
    assert (stick > 0).sum() >= 20 and (stick[stick > 0] >= 16).all()


def test_icon_palette_without_items():
    colors, blocks_idx, items_idx = icon_palette(tiles_to_atlas(build_tiles()))
    assert len(colors) == 48 and items_idx is None
