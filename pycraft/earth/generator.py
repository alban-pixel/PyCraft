"""The terrain of the real Earth: the generator's caves, ores, trees and blocks, over heights and a
climate that come from data instead of noise."""
import functools

import numpy as np

from pycraft.earth import biomes
from pycraft.earth.climate import LAPSE, Climate
from pycraft.earth.grid import TILE, EarthGrid
from pycraft.earth.tiles import TileReader
from pycraft.noise import smoothstep
from pycraft.terrain import CHUNK, SEA_LEVEL, WORLD_HEIGHT, TerrainGenerator

FINE_SPACING = 8  # points farther apart than this don't show the small relief added between the data's
RELIEF_REACH = 500.0  # blocks around a point that tell a country of cliffs from a plain
RELIEF_ZOOMS = 4  # and how much coarser the tiles are that tell it
SHORE = 0.5  # metres: the data's sea is at 0 (give or take rounding)
SHALLOW = 3.0  # metres of water where the data has the sea's surface and no floor
SKY_REACH, SKY_ZOOM = 20000.0, 9  # how far the summits are that the clouds are above, and where they are read
REACH_CHUNKS = 3  # chunks around one that building its mesh may generate


class EarthGenerator(TerrainGenerator):
    def __init__(self, seed, place):
        super().__init__(seed)
        self.place = place
        self.grid = EarthGrid(place.lat, place.lon)
        self.reader = TileReader(place.root)
        self.climate_map = Climate()

    def climate(self, x, z):
        t0, rain = self.climate_map.at(*self.grid.latlon(x, z))
        return {"t0": t0, "rain": rain}

    def metres(self, x, z, zoom):
        """The data's height at points, 0 at sea level."""
        return self.reader.heights(*self.grid.pixels(x, z, zoom), zoom).astype(np.float64)

    def fine_relief(self, x, z, metres, slope):
        """The bumps the data is too coarse to have: small in the plains, crags on the slopes."""
        rough = np.clip(0.6 + 1.8 * slope, 0.6, 6) * smoothstep(SHORE, SHORE + 4, metres)
        return self.detail.fbm2(x / 27, z / 27, 3) * rough

    def relief(self, x, z, zoom):
        zoom = max(zoom - RELIEF_ZOOMS, 0)
        r = RELIEF_REACH
        around = [self.metres(x + dx, z + dz, zoom) for dx, dz in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r))]
        return np.max(around, axis=0) - np.min(around, axis=0)

    def sample(self, x, z, clim=None, spacing=1):
        k = self.climate(x, z) if clim is None else clim
        zoom = self.grid.zoom_for(spacing)
        metres = self.metres(x, z, zoom)
        sea = metres < SHORE
        if spacing <= FINE_SPACING:
            slope = np.hypot(self.metres(x + 8, z, zoom) - metres, self.metres(x, z + 8, zoom) - metres) / 8
            metres = np.where(sea, metres, np.maximum(metres + self.fine_relief(x, z, metres, slope), SHORE))
        depth = np.where(sea, np.maximum(-metres, SHALLOW), 0.0)
        # The deepest seas are squeezed above the bottom of the world
        floor = np.where(depth > 200, 200 + 300 * np.tanh((depth - 200) / 2000), depth)
        height = SEA_LEVEL + np.where(sea, -floor, metres)
        height = np.clip(height, 8, WORLD_HEIGHT - 64)
        altitude = np.where(sea, 0.0, metres)
        # (a little noise: the climate's borders are not straight lines)
        t = k["t0"] - LAPSE * altitude + 0.8 * self.surface.noise2(x / 90, z / 90)
        rain = k["rain"] * (1 + 0.08 * self.surface.noise2(x / 70 + 500, z / 70))
        relief = np.zeros(np.shape(metres))
        arid = biomes.is_arid(t, rain) & ~sea
        if arid.any():
            relief[arid] = self.relief(np.asarray(x)[arid], np.asarray(z)[arid], zoom)
        plains = self.hilliness.fbm2(x / 900, z / 900, 2) * 2.3 > 0.35
        biome = biomes.biome(t, rain, altitude, depth, relief, plains)
        temperature, humidity = biomes.game_climate(t, rain)
        none = np.zeros(np.shape(metres))
        return {"height": height, "water": np.where(sea, SEA_LEVEL, -1), "biome": biome, "temperature": temperature,
                "humidity": humidity, "continent": none, "mask": none, "river": none.astype(bool),
                "moss": (rain > 1200) & (t > 0) & (t < 7)}

    def shift(self, heights):
        return max(0, int(np.median(heights)) - SEA_LEVEL - 64)

    @functools.cached_property
    def cloud_height(self):
        """Above every summit around the place: seen from a valley, clouds any lower would hide them."""
        g = np.arange(-SKY_REACH, SKY_REACH + 1, 500.0)
        x, z = np.meshgrid(g, g, indexing="ij")
        return float(SEA_LEVEL + max(940.0, self.metres(x, z, SKY_ZOOM).max() + 300.0))

    def sky_tiles(self):
        """The tiles that tell how high the summits around the place are."""
        return self.grid.tiles(-SKY_REACH, -SKY_REACH, SKY_REACH, SKY_REACH, SKY_ZOOM)

    # --- The tiles the ground is made from ------------------------------------------------------

    def _tiles(self, x0, z0, x1, z1, spacing):
        zoom = self.grid.zoom_for(spacing)
        r = RELIEF_REACH
        return (self.grid.tiles(x0, z0, x1 + 8, z1 + 8, zoom)
                + self.grid.tiles(x0 - r, z0 - r, x1 + r, z1 + r, max(zoom - RELIEF_ZOOMS, 0)))

    def area_tiles(self, x0, z0, x1, z1):
        """Every tile that the terrain of a rectangle of blocks needs."""
        return self._tiles(x0, z0, x1, z1, 1)

    def column_tiles(self, cx, cz):
        """Every tile that the mesh of a chunk needs."""
        x0, z0 = (cx - REACH_CHUNKS) * CHUNK, (cz - REACH_CHUNKS) * CHUNK
        width = (2 * REACH_CHUNKS + 1) * CHUNK
        return self._tiles(x0, z0, x0 + width, z0 + width, 1)

    def level_tiles(self, x0, z0, x1, z1, step):
        """Every tile that a part of the distant terrain needs, its points `step` blocks apart."""
        return self._tiles(x0 - 2 * step, z0 - 2 * step, x1 + 2 * step, z1 + 2 * step, step)

    def tile_at(self, x, z):
        """The finest tile a block is in."""
        px, py = self.grid.pixels(x, z, self.grid.zoom_for(1))
        return int(px // TILE), int(py // TILE)

    def tiles_ahead(self, x, z):
        """The tiles of the ground around a block, as far as the second one from its own: 3 to 5 km,
        more than a minute of fast flight."""
        zoom = self.grid.zoom_for(1)
        r = 2 * self.grid.around / 2 ** zoom
        return self._tiles(x - r, z - r, x + r, z + r, 1)

    # --- Where to start --------------------------------------------------------------------------

    def spawn(self):
        """(x, z) of the dry and fairly flat block nearest to the place itself, or None."""
        g = np.arange(-400, 401, 8.0)
        x, z = np.meshgrid(g, g, indexing="ij")
        s = self.sample(x, z)
        flat = np.abs(self.sample(x + 3, z + 3)["height"] - s["height"]) < 3
        ok = flat & (s["water"] < 0)
        if not ok.any():
            return None
        px, pz = x[ok], z[ok]
        best = int(np.argmin(np.hypot(px, pz)))
        return int(px[best]), int(pz[best])
