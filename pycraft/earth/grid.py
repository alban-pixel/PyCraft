"""Where a block is on Earth.

The elevation data comes as square tiles of a Web Mercator map: at zoom z the world is 2^z by 2^z
tiles of 256x256 pixels. A world keeps that map's grid, scaled so that one block is one metre at
the place where it starts. Mercator stretches everything toward the poles, so the scale drifts with
the latitude: 1 to 2 % at 65 km, which is why each place has a world of its own."""
import math

import numpy as np

TILE = 256  # pixels on a side of a map tile
MAX_ZOOM = 14  # the finest tiles used: 4 to 9 m a pixel, finer than most of the surveys behind them
EQUATOR = 40075016.686  # metres around the Earth


def _mercator(lat, lon):
    """Place on the map, from 0 to 1: west to east and north to south."""
    r = np.radians(lat)
    return (lon + 180) / 360, (1 - np.arcsinh(np.tan(r)) / math.pi) / 2


class EarthGrid:
    """Block (0, 0) is at (lat, lon); +x goes east and +z goes south."""

    def __init__(self, lat, lon):
        self.lat, self.lon = float(lat), float(lon)
        self.around = EQUATOR * math.cos(math.radians(self.lat))  # blocks around the world
        u, v = _mercator(self.lat, self.lon)
        self.u0, self.v0 = float(u), float(v)

    def pixels(self, x, z, zoom):
        """Pixel coordinates of blocks on the whole map of this zoom (a pixel's center is at +0.5)."""
        size = TILE * 2 ** zoom
        return ((self.u0 + np.asarray(x, dtype=np.float64) / self.around) * size,
                (self.v0 + np.asarray(z, dtype=np.float64) / self.around) * size)

    def latlon(self, x, z):
        u = self.u0 + np.asarray(x, dtype=np.float64) / self.around
        v = self.v0 + np.asarray(z, dtype=np.float64) / self.around
        return np.degrees(np.arctan(np.sinh(math.pi * (1 - 2 * v)))), (u % 1.0) * 360 - 180

    def block(self, lat, lon):
        u, v = _mercator(lat, lon)
        du = (u - self.u0 + 0.5) % 1.0 - 0.5  # the short way around
        return float(du * self.around), float((v - self.v0) * self.around)

    def zoom_for(self, spacing):
        """The zoom whose pixels are about this many blocks wide."""
        return min(max(round(math.log2(self.around / TILE / spacing)), 0), MAX_ZOOM)

    def tiles(self, x0, z0, x1, z1, zoom, margin=3):
        """The (zoom, tx, ty) of every tile that the rectangle of blocks needs, with a margin in
        pixels around it (what the interpolation reads next to a point)."""
        px, py = self.pixels(np.array([x0, x1]), np.array([z0, z1]), zoom)
        n = 2 ** zoom
        columns = range(math.floor((px[0] - margin) / TILE), math.floor((px[1] + margin) / TILE) + 1)
        rows = range(math.floor((py[0] - margin) / TILE), math.floor((py[1] + margin) / TILE) + 1)
        return list(dict.fromkeys((zoom, tx % n, min(max(ty, 0), n - 1)) for ty in rows for tx in columns))
