"""Which biome grows where on the real Earth, from the climate and the ground."""
import numpy as np

from pycraft import terrain as T

HIGH = 900.0  # metres: above, the cold comes from the altitude; below, from the latitude


def biome(t, rain, altitude, depth, relief, plains):
    """Biome of each point: yearly temperature on the ground (degrees), rain (mm a year), altitude
    and depth of the sea (metres), height differences around (metres), and whether open country
    takes the place of the forest. The first rule that matches wins."""
    sea, high = depth > 0, altitude > HIGH
    snow_line = -6 - 4 * np.clip((800 - rain) / 600, 0, 1)  # dry mountains keep less snow
    arid = rain < 10 * t + 70
    rules = [
        (sea & (t < -8), T.FROZEN_OCEAN),
        (sea & (depth > 60), T.DEEP_OCEAN),
        (sea, T.OCEAN),
        (altitude <= 1.5, T.BEACH),
        (high & (t < snow_line), T.SNOWY_PEAKS),
        (high & (t < -3.5), T.ROCKY),
        (high & (t < -1), T.ALPINE),
        ((t < -14) | ((t < -9) & (rain < 250)), T.SNOWY_TUNDRA),
        (t < -5, T.SNOWY_TAIGA),
        (t < 3, T.TAIGA),
        (arid & (relief > 250), T.BADLANDS),
        (arid, T.DESERT),
        ((rain < 20 * t + 140) & (t >= 18), T.SAVANNA),
        (rain < 20 * t + 140, T.PLAINS),
        ((t >= 20) & (rain >= 1500), T.JUNGLE),
        (t >= 20, T.SAVANNA),
        (plains, T.PLAINS),
        (t < 8, T.BIRCH_FOREST),
    ]
    return np.select([r[0] for r in rules], [r[1] for r in rules], T.FOREST).astype(np.uint8)


def is_arid(t, rain):
    """Where biome() looks at the relief."""
    return rain < 10 * t + 70


def game_climate(t, rain):
    """The same climate in the game's own units: (temperature, humidity), about -1 to 1."""
    return 0.35 + 0.0433 * (t - 19), np.interp(rain, [0, 250, 700, 1500, 3000], [-0.8, -0.4, 0.0, 0.4, 0.6])
