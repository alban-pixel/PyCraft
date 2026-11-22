"""Map tiles made of a formula, for the tests of the Earth: no network."""
import io

import numpy as np
from PIL import Image


class World:
    """fetch(key) -> the tile of a ground given as ground(px, py) in pixels of one zoom, seen at any
    zoom (each pixel takes the ground's value at its center). `tiles` replaces some whole tiles."""

    def __init__(self, zoom, ground, tiles=()):
        self.zoom, self.ground, self.tiles, self.asked = zoom, ground, dict(tiles), []

    def fetch(self, key):
        self.asked.append(key)
        if key in self.tiles:
            return self.tiles[key].astype(np.float32)
        z, tx, ty = key
        scale = 2.0 ** (self.zoom - z)
        px = (tx * 256 + np.arange(256) + 0.5) * scale
        py = (ty * 256 + np.arange(256) + 0.5) * scale
        return np.asarray(self.ground(*np.meshgrid(px, py)), dtype=np.float32) + np.zeros((256, 256), np.float32)


def png(heights):
    """A tile as the server sends it."""
    v = np.round((np.asarray(heights, dtype=np.float64) + 32768) * 256).astype(np.int64)
    out = io.BytesIO()
    Image.fromarray(np.stack([v >> 16, v >> 8 & 255, v & 255], axis=-1).astype(np.uint8)).save(out, "PNG")
    return out.getvalue()
