"""The Earth's tiles on disk, and their download."""
import os
import ssl

import numpy as np
import pytest

from pycraft.earth.tiles import Downloader, TileReader, TileStore, load_tile, save_tile, tile_path
from tests.earthtiles import png


def test_save_load(tmp_path):
    h = np.zeros((256, 256), np.float32)
    h[0, 0], h[5, 9] = -10905.5, 8849.0
    save_tile(tmp_path, (14, 3, 4), h)
    back = load_tile(tmp_path, (14, 3, 4))
    assert back.dtype == np.float32 and (back == h).all()
    assert load_tile(tmp_path, (14, 3, 5)) is None


@pytest.mark.parametrize("damage", ["cut", "empty", "shape"])
def test_corrupt_tile_is_deleted(tmp_path, damage):
    key = (9, 1, 2)
    save_tile(tmp_path, key, np.zeros((256, 256)))
    path = tile_path(tmp_path, key)
    if damage == "shape":
        np.save(path, np.zeros((4, 4), np.int16))
    else:
        data = open(path, "rb").read()
        open(path, "wb").write(data[:1000] if damage == "cut" else b"")
    assert load_tile(tmp_path, key) is None
    assert not os.path.exists(path)


def test_bicubic(tmp_path):
    for tx in (10, 11):
        for ty in (20, 21):
            px, py = np.meshgrid(tx * 256 + np.arange(256) + 0.5, ty * 256 + np.arange(256) + 0.5)
            save_tile(tmp_path, (6, tx, ty), 3 * (px - 2600) + 2 * (py - 5200))
    rng = np.random.default_rng(1)
    px, py = 2560 + 5 + rng.random(4000) * 500, 5120 + 5 + rng.random(4000) * 500
    got = TileReader(tmp_path).heights(px, py, 6)
    assert got.shape == (4000,) and np.abs(got - (3 * (px - 2600) + 2 * (py - 5200))).max() < 0.6


def test_any_shape_and_far_apart_points(tmp_path):
    """The points of a batch can be anywhere: reading them must not need everything in between."""
    save_tile(tmp_path, (14, 100, 100), np.full((256, 256), 50.0))
    save_tile(tmp_path, (14, 9000, 9000), np.full((256, 256), 90.0))
    px = np.array([[100 * 256 + 99.0, 9000 * 256 + 99.0]])
    assert TileReader(tmp_path).heights(px, px, 14).tolist() == [[50.0, 90.0]]


def test_parent_fallback(tmp_path):
    reader = TileReader(tmp_path)
    px, py = np.array([8000 * 256 + 12.0]), np.array([6000 * 256 + 12.0])
    assert reader.heights(px, py, 14)[0] == 0
    save_tile(tmp_path, (8, 8000 >> 6, 6000 >> 6), np.full((256, 256), 500.0))
    assert abs(TileReader(tmp_path).heights(px, py, 14)[0] - 500) < 0.5


def test_a_tile_that_arrives_is_seen(tmp_path):
    reader = TileReader(tmp_path)
    px, py = np.array([8000 * 256 + 100.0]), np.array([6000 * 256 + 100.0])
    assert reader.heights(px, py, 14)[0] == 0
    save_tile(tmp_path, (14, 8000, 6000), np.full((256, 256), 700.0))
    assert reader.heights(px, py, 14)[0] == 700


def test_wraps(tmp_path):
    for tx in (0, 2 ** 5 - 1):
        save_tile(tmp_path, (5, tx, 9), np.full((256, 256), 123.0))
    for px in (-0.5, 0.2, 32 * 256 - 0.1, 32 * 256 + 3.0):
        assert abs(TileReader(tmp_path).heights(np.array([px]), np.array([9 * 256 + 100.0]), 5)[0] - 123) < 0.01


def flat_server(url):
    return png(np.full((256, 256), 321.0))


def test_download(tmp_path):
    down = Downloader(tmp_path, flat_server)
    assert down.fetch_one((14, 5000, 6000))
    assert (load_tile(tmp_path, (14, 5000, 6000)) == 321).all()


@pytest.mark.parametrize("error", [OSError("no route"), ssl.SSLCertVerificationError("no certificates")])
def test_retries_then_offline(tmp_path, error):
    calls = []

    def get(url):
        calls.append(url)
        raise error

    down = Downloader(tmp_path, get, pause=0)
    assert [down.fetch_one((6, i, 5)) for i in range(3)] == [False] * 3
    assert len(calls) == 9 and down.offline
    assert not down.fetch_one((6, 4, 5))
    assert len(calls) == 9


def test_a_broken_answer_is_a_failure(tmp_path):
    """A hotel's sign-in page instead of a tile: not a tile, and not a crash."""
    assert not Downloader(tmp_path, lambda url: b"<html>sign in</html>", pause=0).fetch_one((6, 1, 5))
    assert load_tile(tmp_path, (6, 1, 5)) is None


def test_back_online(tmp_path):
    up = []

    def get(url):
        if not up:
            raise OSError("down")
        return flat_server(url)

    down = Downloader(tmp_path, get, pause=0, offline_seconds=0)
    for i in range(3):
        down.fetch_one((6, i, 5))
    up.append(True)
    assert down.fetch_one((6, 9, 5)) and not down.offline


def test_ready_after_failure(tmp_path):
    store = TileStore(tmp_path, start=False)
    keys = [(6, 1, 1), (6, 2, 1)]
    assert not store.ready(keys) and store.missing(keys) == keys and store.progress(keys) == 0
    save_tile(tmp_path, keys[0], np.zeros((256, 256)))
    store.landed(keys[0], True)
    assert store.progress(keys) == 0.5 and not store.ready(keys)
    store.landed(keys[1], False, offline=True)
    assert store.ready(keys) and store.offline and not store.complete(keys)
    store.retry()
    assert not store.ready(keys) and not store.offline


def test_tiles_already_on_disk_are_ready(tmp_path):
    save_tile(tmp_path, (6, 1, 1), np.zeros((256, 256)))
    assert TileStore(tmp_path, start=False).ready([(6, 1, 1)])


def test_want_asks_once(tmp_path):
    store = TileStore(tmp_path, start=False)
    store.want([(6, 1, 1), (6, 2, 1)])
    store.want([(6, 1, 1)])
    assert store.sent == [[(6, 1, 1), (6, 2, 1)]]


def test_process_downloads(tmp_path):
    """The real process, with the network replaced by files: file:// is an address like any other."""
    import time
    source = tmp_path / "server"
    (source / "3" / "4").mkdir(parents=True)
    (source / "3" / "4" / "2.png").write_bytes(png(np.full((256, 256), 42.0)))
    store = TileStore(tmp_path / "cache", url=source.as_uri() + "/{z}/{x}/{y}.png")
    try:
        store.want([(3, 4, 2)])
        deadline = time.time() + 30
        while not store.complete([(3, 4, 2)]) and time.time() < deadline:
            store.poll()
            time.sleep(0.02)
        assert (load_tile(tmp_path / "cache", (3, 4, 2)) == 42).all()
    finally:
        store.close()


def test_a_tile_in_use_is_not_the_oldest(tmp_path):
    key = (6, 1, 1)
    save_tile(tmp_path, key, np.zeros((256, 256)))
    os.utime(tile_path(tmp_path, key), (1, 1))
    TileReader(tmp_path).heights(np.array([300.0]), np.array([300.0]), 6)
    assert os.path.getmtime(tile_path(tmp_path, key)) > 1000
