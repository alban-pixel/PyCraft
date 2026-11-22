"""The Earth's map grid: blocks, latitudes and the numbers of the map's tiles."""
import numpy as np

from pycraft.earth.grid import EarthGrid


def test_round_trip():
    grid = EarthGrid(45.9237, 6.8694)
    x, z = grid.block(*grid.latlon(12345.0, -6789.0))
    assert abs(x - 12345) < 0.01 and abs(z + 6789) < 0.01


def test_one_block_is_a_metre():
    # From Chamonix, the summit of Mont Blanc is 10.1 km to the south and 325 m to the west
    x, z = EarthGrid(45.9237, 6.8694).block(45.8326, 6.8652)
    assert abs(z - 10130) < 60 and abs(x + 325) < 10


def test_axes():
    grid = EarthGrid(-33.0, 151.0)
    assert grid.block(-33.0, 151.1)[0] > 0  # east is +x
    assert grid.block(-33.1, 151.0)[1] > 0  # south is +z


def test_zoom_for():
    grid = EarthGrid(45.92, 6.87)
    assert grid.zoom_for(1) == 14
    assert grid.zoom_for(512) == 8
    assert grid.zoom_for(10 ** 9) == 0


def test_pixels_match_the_tile_numbers():
    # The well-known tile of a place: the whole world is one tile at zoom 0, cut in 4 at zoom 1
    px, py = EarthGrid(10.0, 20.0).pixels(np.zeros(1), np.zeros(1), 1)
    assert 256 < px[0] < 512 and 0 < py[0] < 256  # north-east quarter


def test_tiles_cover_the_rectangle():
    grid = EarthGrid(45.92, 6.87)
    keys = grid.tiles(-100, -100, 5000, 100, 14)
    px, py = grid.pixels(np.array([-100.0, 5000.0]), np.array([-100.0, 100.0]), 14)
    for x, y in zip(px, py):
        assert (14, int(x // 256), int(y // 256)) in keys
    assert len(keys) == len(set(keys))


def test_tiles_wrap_and_clamp():
    zoom = 12
    keys = EarthGrid(10.0, 179.999).tiles(-3000, -3000, 3000, 3000, zoom)
    columns = {tx for _, tx, _ in keys}
    assert 0 in columns and 2 ** zoom - 1 in columns
    assert all(0 <= tx < 2 ** zoom for tx in columns)
    assert all(0 <= ty for _, _, ty in EarthGrid(85.0, 0.0).tiles(-50000, -50000, 50000, 50000, 8))
