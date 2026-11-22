"""Makes pycraft/earth/climate.npz: the yearly temperature (brought to sea level) and rain of the
whole Earth, every 1/6 of a degree, from CHELSA 2.1 (CC0) and the Terrarium elevation tiles.

Downloads about 200 MB, once: the result is in the repository.

Usage: python tools/make_climate.py"""
import concurrent.futures
import os
import sys
import time
import urllib.request
import zlib

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pycraft.earth import climate, clean, tiles  # noqa: E402

CHELSA = "https://os.zhdk.cloud.switch.ch/chelsav2/GLOBAL/climatologies/1981-2010/bio/CHELSA_{}_1981-2010_V.2.1.tif"
WIDTH, HEIGHT = 43200, 20880  # 120 pixels a degree, from 180 W and 84 N
CELL = 20  # pixels on a side of a cell of 1/6 degree
STRIPS, SIZES = 83762, 242  # where the file's tables start: each row's place and its size (4 bytes each)
NO_DATA = 65535


def get(url, start=None, count=None):
    headers = {} if start is None else {"Range": f"bytes={start}-{start + count - 1}"}
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as answer:
                return answer.read()
        except OSError:
            if attempt == 4:
                raise
            time.sleep(1 + attempt)


def read_cells(name):
    """A CHELSA map averaged to cells, from 4 rows in each 20."""
    url = CHELSA.format(name)
    head = get(url, 0, STRIPS + 4 * HEIGHT)
    if head[:4] != b"II*\x00":
        raise SystemExit(f"{url}: not the file this tool knows")
    offsets = np.frombuffer(head, "<u4", HEIGHT, STRIPS)
    sizes = np.frombuffer(head, "<u4", HEIGHT, SIZES)

    def row(r):
        data = zlib.decompress(get(url, int(offsets[r]), int(sizes[r])))
        values = np.cumsum(np.frombuffer(data, "<u2", WIDTH), dtype=np.uint16).astype(float)  # predictor 2
        values[values == NO_DATA] = np.nan
        return values.reshape(-1, CELL)

    out = np.empty((HEIGHT // CELL, WIDTH // CELL))
    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        def cell_row(k):
            part = np.concatenate([row(CELL * k + i) for i in (2, 7, 12, 17)], axis=1)
            good = np.isfinite(part)
            total = np.where(good, part, 0).sum(axis=1)
            out[k] = np.where(good.any(axis=1), total / np.maximum(good.sum(axis=1), 1), np.nan)
        for k, _ in enumerate(pool.map(cell_row, range(len(out)))):
            if k % 100 == 0:
                print(f"{name}: row {k} of {len(out)}", flush=True)
    return out


def ground(lat, lon):
    """Average height of the land of each cell, from the tiles of zoom 4 (0 at sea)."""
    n = 16
    with concurrent.futures.ThreadPoolExecutor(16) as pool:
        keys = [(4, x, y) for y in range(n) for x in range(n)]
        parts = list(pool.map(lambda k: clean.decode(get(tiles.URL.format(z=k[0], x=k[1], y=k[2]))), keys))
    world = np.maximum(np.block([parts[y * n:y * n + n] for y in range(n)]), 0)
    size = n * 256
    world = np.pad(world, ((0, 0), (1, 1)), mode="wrap")
    out = 0.0
    for dlat in (-1 / 24, 1 / 24):
        for dlon in (-1 / 24, 1 / 24):
            r = np.radians(np.clip(lat + dlat, -85, 85))[:, None]
            v = (1 - np.arcsinh(np.tan(r)) / np.pi) / 2 * size - 0.5
            u = ((lon + dlon + 180) / 360 * size - 0.5)[None, :] + 1
            i, j = np.clip(v.astype(int), 0, size - 2), np.clip(u.astype(int), 0, size)
            fv, fu = v - i, u - j
            out = out + (world[i, j] * (1 - fv) + world[i + 1, j] * fv) * (1 - fu) \
                + (world[i, j + 1] * (1 - fv) + world[i + 1, j + 1] * fv) * fu
    return out / 4


def fill(a):
    """Cells without data take the nearest row's that has some."""
    for k in range(1, len(a)):
        a[k] = np.where(np.isnan(a[k]), a[k - 1], a[k])
    for k in range(len(a) - 2, -1, -1):
        a[k] = np.where(np.isnan(a[k]), a[k + 1], a[k])
    return a


if __name__ == "__main__":
    temperature = fill(read_cells("bio1")) / 10 - 273.15  # tenths of a kelvin
    rain = fill(read_cells("bio12")) / 10  # tenths of a millimetre
    rows, cols = temperature.shape
    lat, lon = 84 - (np.arange(rows) + 0.5) / 6, -180 + (np.arange(cols) + 0.5) / 6
    climate.write(temperature + climate.LAPSE * ground(lat, lon), rain)
    print("written,", os.path.getsize(climate.FILE), "bytes")
