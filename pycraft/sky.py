"""The sky and the light through the day: colors of the sky, the sun's and the moon's light, the fog."""
import math

import numpy as np


HAZE = 1 / 4500  # share of light lost per block of distance: far mountains fade into the sky
FOG_START = 0.75  # the fog that hides the end of the world starts at this share of the view distance

# Sky colors (RGB 0-1)
DAY_ZENITH, DAY_HORIZON = (0.38, 0.6, 1.0), (0.68, 0.84, 1.0)
NIGHT_ZENITH, NIGHT_HORIZON = (0.01, 0.01, 0.06), (0.06, 0.08, 0.18)
SUNSET = (1.0, 0.55, 0.3)
UNDERWATER_FOG = (0.08, 0.2, 0.5)

# Light (RGB): direct light from the sun or the moon, and the light of the whole sky
NOON_LIGHT, SUNSET_LIGHT, MOON_LIGHT = (0.56, 0.54, 0.48), (0.6, 0.36, 0.2), (0.1, 0.12, 0.17)
DAY_SKY_LIGHT, NIGHT_SKY_LIGHT, SUNSET_SKY_LIGHT = (0.52, 0.56, 0.63), (0.17, 0.19, 0.28), (0.58, 0.46, 0.44)
SUN_GLOW = (1.0, 0.7, 0.4)
SUN_TILT = 0.5  # the sun's path leans to one side (63 degrees up at most), so walls facing it get light
CLOUD_COVER = 0.56  # share of the sky without clouds (about)


def mix(a, b, t):
    return tuple(float(x + (y - x) * t) for x, y in zip(a, b))


def scale(color, k):
    return tuple(float(c * k) for c in color)


def smoothstep(lo, hi, x):
    t = min(max((x - lo) / (hi - lo), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def environment(time_of_day):
    """Light and sky for a time of day (0 = sunrise, 0.25 = noon, 0.5 = sunset, 0.75 = midnight),
    as values for Renderer.set_environment, and how much it is day (0-1)."""
    angle = time_of_day * 2 * math.pi
    sun_height = math.sin(angle)
    day = smoothstep(-0.2, 0.25, sun_height)
    low_sun = math.exp(-(sun_height / 0.18) ** 2)  # 1 at sunrise and sunset
    zenith = mix(NIGHT_ZENITH, DAY_ZENITH, day)
    horizon = mix(mix(NIGHT_HORIZON, DAY_HORIZON, day), SUNSET, 0.8 * low_sun)
    sun = np.array([math.cos(angle), sun_height, SUN_TILT])
    sun /= np.linalg.norm(sun)
    # Direct light from the sun by day, from the moon by night, and none while either is at the horizon
    if sun_height >= 0:
        light_dir = sun
        color = mix(SUNSET_LIGHT, NOON_LIGHT, smoothstep(0.0, 0.45, sun_height))
        light = scale(color, smoothstep(0.0, 0.1, sun_height))
    else:
        light_dir = -sun
        light = scale(MOON_LIGHT, smoothstep(0.0, 0.1, -sun_height))
    sky_light = mix(mix(NIGHT_SKY_LIGHT, DAY_SKY_LIGHT, day), SUNSET_SKY_LIGHT, 0.35 * low_sun * day)
    return {
        "light_dir": tuple(float(c) for c in light_dir), "light_color": light, "sky_light": sky_light,
        "zenith": zenith, "horizon": horizon, "sun_dir": tuple(float(c) for c in sun),
        "sun_glow": scale(SUN_GLOW, day * (0.35 + 0.65 * low_sun)),
        "night": 1.0 - smoothstep(-0.35, -0.05, sun_height), "cloud_cover": CLOUD_COVER,
    }, day
