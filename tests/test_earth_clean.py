"""Cleaning the elevation tiles: the data's broken pixels go, the real ground stays."""
import numpy as np

from tests.earthtiles import World, png
from pycraft.earth.clean import clean, decode
from pycraft.earth.grid import EarthGrid


def test_decode():
    assert (decode(png(np.full((256, 256), 0.5))) == 0.5).all()
    assert abs(decode(png(np.full((256, 256), -10905.25)))[7, 9] + 10905.25) < 0.01


def test_broken_run_is_replaced():
    plane = np.full((256, 256), 6000.0)
    plane[100, 20:200] = -7000
    plane[101, 20:140] = -7000
    out = clean((14, 9000, 6000), World(14, lambda x, y: 6000.0, {(14, 9000, 6000): plane}).fetch)
    assert np.abs(out - 6000).max() < 5


def test_real_cliff_survives():
    key = (14, 9000, 6000)
    world = World(14, lambda x, y: np.where(x < 9000 * 256 + 128, 1000.0, 1700.0))
    assert (clean(key, world.fetch) == world.fetch(key)).all()


def test_coarse_peak_survives():
    key = (8, 130, 90)
    cx, cy = 130 * 256 + 100.5, 90 * 256 + 100.5
    world = World(8, lambda x, y: np.maximum(4500 - 500 * np.hypot(x - cx, y - cy), 500))
    assert (clean(key, world.fetch) == world.fetch(key)).all()


def test_coarse_spike_goes():
    key = (10, 530, 360)
    plane = np.full((256, 256), 100.0)
    plane[30, 40] = -9000
    out = clean(key, World(10, lambda x, y: 100.0, {key: plane}).fetch)
    assert (out == 100).all()


def test_sea_floor_comes_from_the_coarse_tiles():
    key = (14, 900, 6000)
    flat = np.zeros((256, 256))
    sea = World(14, lambda x, y: -3000.0, {key: flat})
    sea.tiles.update({(11, 112 + i, 750 + j): flat for i in (-1, 0, 1) for j in (-1, 0, 1)})  # zero there too
    assert np.abs(clean(key, sea.fetch) + 3000).max() < 1
    land = World(14, lambda x, y: 20.0, {key: flat})
    assert (clean(key, land.fetch) == 0).all()


def test_summit_restored():
    grid = EarthGrid(27.9881, 86.9250)  # Everest
    px, py = (float(v) for v in grid.pixels(0.0, 0.0, 14))
    key = (14, int(px // 256), int(py // 256))
    cx, cy = np.floor(px) + 0.5, np.floor(py) + 0.5
    world = World(14, lambda x, y: np.maximum(8750 - 4 * np.hypot(x - cx, y - cy), 5000))
    before, after = world.fetch(key), clean(key, world.fetch)
    row, col = int(py) - key[2] * 256, int(px) - key[1] * 256
    assert before[row, col] == 8750 and abs(after[row, col] - 8849) < 1
    metres = 40075016.686 * np.cos(np.radians(27.9881)) / 256 / 2 ** 14
    far = np.hypot(np.arange(256)[None] - col, np.arange(256)[:, None] - row) * metres > 2000
    if far.any():
        assert np.abs(after - before)[far].max() < 0.01


def test_summit_across_a_tile_border():
    """Two neighbor tiles raise the same summit by the same amount: no step between them."""
    grid = EarthGrid(27.9881, 86.9250)
    px, py = (float(v) for v in grid.pixels(0.0, 0.0, 14))
    cx, cy = np.floor(px) + 0.5, np.floor(py) + 0.5
    world = World(14, lambda x, y: 8750 - 0.5 * np.hypot(x - cx, y - cy))
    tx, ty = int(px // 256), int(py // 256)
    left, right = (tx, tx + 1) if px % 256 > 128 else (tx - 1, tx)
    a, b = clean((14, left, ty), world.fetch), clean((14, right, ty), world.fetch)
    assert np.abs(a[:, -1] - b[:, 0]).max() < 6
