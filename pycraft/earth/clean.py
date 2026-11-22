"""Elevation tiles as the server sends them, and what is wrong with them.

The tiles put together dozens of surveys, and some of their pixels are broken: runs at -7000 m in
the middle of the Himalayas, single wells and spikes. The sea is flat at 0 in the fine tiles and has
its floor only in the coarse ones, and the surveys round the sharpest summits off."""
import io
import math

import numpy as np

from pycraft.earth.grid import EQUATOR, TILE, EarthGrid

SEA_ZOOM = 8  # the finest zoom that has the sea's floor everywhere
# At these zooms a broken run can be told from the ground three zooms coarser. At coarser ones that
# would plane the summits down (Everest lost 1500 m at zoom 8): only single pixels are mended there
FINE_ZOOM = 13
SUMMIT_WIDTH = 250.0  # metres around a summit that rise with it
SUMMIT_MOST = 150.0  # more than this missing is not a rounded summit: it is left alone

SUMMITS = [("Everest", 27.9881, 86.9250, 8849), ("K2", 35.8808, 76.5155, 8611),
           ("Kangchenjunga", 27.7025, 88.1475, 8586), ("Mont Blanc", 45.8326, 6.8652, 4806),
           ("Matterhorn", 45.9766, 7.6585, 4478), ("Denali", 63.0692, -151.0070, 6190),
           ("Kilimanjaro", -3.0674, 37.3556, 5895), ("Fuji", 35.3606, 138.7274, 3776),
           ("Aconcagua", -32.6532, -70.0109, 6961), ("Piton des Neiges", -21.0983, 55.4797, 3070)]


def decode(png):
    """The heights in metres of a Terrarium tile, as (256, 256) [row, column]."""
    from PIL import Image  # (here: the rest of the game runs without Pillow)
    rgb = np.asarray(Image.open(io.BytesIO(png)).convert("RGB")).astype(np.float32)
    return rgb[..., 0] * 256 + rgb[..., 1] + rgb[..., 2] / 256 - 32768


def _around(a, middle=True):
    """The 3x3 values around each one (8 of them without the middle), stacked first."""
    p = np.pad(a, 1, mode="edge")
    h, w = a.shape
    return np.stack([p[i:i + h, j:j + w] for i in range(3) for j in range(3) if middle or (i, j) != (1, 1)])


def _nearby(zoom, tx, ty, fetch):
    """The 3x3 tiles around one, as a single array."""
    n = 2 ** zoom
    return np.block([[fetch((zoom, (tx + i) % n, min(max(ty + j, 0), n - 1))) for i in (-1, 0, 1)]
                     for j in (-1, 0, 1)])


def _coarse(key, zoom, fetch, smooth=False):
    """This tile's pixels as a coarser zoom sees them, and how much that ground varies around each."""
    z, tx, ty = key
    scale = 2 ** (z - zoom)
    cx, cy = tx // scale, ty // scale
    m = _nearby(zoom, cx, cy, fetch)
    u = (tx - cx * scale + (np.arange(TILE) + 0.5) / TILE) * TILE / scale + TILE - 0.5
    v = (ty - cy * scale + (np.arange(TILE) + 0.5) / TILE) * TILE / scale + TILE - 0.5
    left, top = int(u[0]) - 4, int(v[0]) - 4  # (the rest of these 9 tiles is never read)
    m = m[top:int(v[-1]) + 6, left:int(u[-1]) + 6]
    u, v = u - left, v - top
    if smooth:
        for _ in range(2):  # the coarse tiles have broken pixels too
            m = np.median(_around(m), axis=0)
    j, i = np.floor(u).astype(int), np.floor(v).astype(int)
    fu, fv = (u - j)[None, :], (v - i)[:, None]
    g = {(a, b): m[np.ix_(i + a, j + b)] for a in (-1, 0, 1, 2) for b in (-1, 0, 1, 2)}
    value = (g[0, 0] * (1 - fv) + g[1, 0] * fv) * (1 - fu) + (g[0, 1] * (1 - fv) + g[1, 1] * fv) * fu
    stack = np.stack(list(g.values()))
    return value, stack.max(axis=0) - stack.min(axis=0)


def _mend_runs(key, h, fetch):
    reference, relief = _coarse(key, key[0] - 3, fetch, smooth=True)
    off = np.abs(h - reference)
    bad = off > 150 + relief
    if not bad.any():
        return h
    for _ in range(3):  # a broken run's own edges are half broken
        p = np.pad(bad, 1)
        near = p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
        bad |= near & (off > 60 + 0.5 * relief)
    return np.where(bad, reference, h)


def _mend_pixels(h):
    others = np.sort(_around(h, middle=False), axis=0)  # its 8 neighbors: their median and quartiles
    middle = (others[3] + others[4]) / 2
    low, high = 0.25 * others[1] + 0.75 * others[2], 0.75 * others[5] + 0.25 * others[6]
    return np.where(np.abs(h - middle) > 400 + 4 * (high - low), middle, h)


def _sea_floor(key, h, fetch):
    flat = np.abs(h) < 0.5
    if not flat.any():
        return h
    floor, _ = _coarse(key, SEA_ZOOM, fetch)
    return np.where(flat & (floor < -1), floor, h)


def _raise_summits(key, h, fetch):
    """Give the great summits back the metres the surveys rounded off. The bump is put on the highest
    pixel near the summit's place, as the tiles have it: the same one seen from any tile around."""
    zoom, tx, ty = key
    n = 2 ** zoom
    for _, lat, lon, metres in SUMMITS:
        px, py = (float(v) for v in EarthGrid(lat, lon).pixels(0.0, 0.0, zoom))
        size = EQUATOR * math.cos(math.radians(lat)) / TILE / n  # metres a pixel
        reach = 5 * SUMMIT_WIDTH / size + 1
        if not (-reach < px - tx * TILE < TILE + reach and -reach < py - ty * TILE < TILE + reach):
            continue
        r = max(int(math.ceil(SUMMIT_WIDTH / size)), 1)
        best = None
        tiles = {}
        for y in range(int(py) - r, int(py) + r + 1):
            for x in range(int(px) - r, int(px) + r + 1):
                where = (zoom, x // TILE % n, min(max(y // TILE, 0), n - 1))
                if where not in tiles:
                    tiles[where] = fetch(where)
                value = float(tiles[where][y % TILE, x % TILE])
                if best is None or value > best[0]:
                    best = (value, x, y)
        missing = metres - best[0]
        if 0 < missing < SUMMIT_MOST:
            cols = np.arange(TILE) + tx * TILE - best[1]
            rows = np.arange(TILE) + ty * TILE - best[2]
            away = np.hypot(cols[None, :], rows[:, None]) * size
            h = h + missing * np.exp(-(away / SUMMIT_WIDTH) ** 2)
    return h


def clean(key, fetch):
    """The heights of tile key = (zoom, tx, ty), mended. fetch(key) gives the tiles as they came."""
    h = fetch(key)
    h = _mend_runs(key, h, fetch) if key[0] >= FINE_ZOOM else _mend_pixels(h)
    if key[0] > SEA_ZOOM:
        h = _sea_floor(key, h, fetch)
    return np.asarray(_raise_summits(key, h, fetch), dtype=np.float32)
