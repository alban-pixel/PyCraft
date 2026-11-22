"""The Earth's climate: the yearly temperature and rain of any place, from CHELSA 2.1 (1981-2010),
made into a small file by tools/make_climate.py."""
import os

import numpy as np

FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "climate.npz")
LAPSE = 0.0065  # degrees lost for each metre up
CELLS = 6  # cells in a degree, from 180 W and 84 N
NORTH = 84.0
T_STEP = 5.0  # temperatures are kept in fifths of a degree
R_STEP = 2.5  # rain as its square root (it goes from 1 to 10000 mm), in steps of 1/2.5


def write(temperature, rain):
    """Make the file. (The differences from a cell to the next pack better than the values.)"""
    t = np.round(temperature * T_STEP).astype(np.int16)
    r = np.clip(np.round(np.sqrt(np.maximum(rain, 0)) * R_STEP), 0, 255).astype(np.int16)
    np.savez_compressed(FILE, **{k: np.diff(v, axis=1, prepend=0).astype(np.int16) for k, v in (("t", t), ("r", r))})


class Climate:
    def __init__(self):
        with np.load(FILE) as f:
            self.t = np.cumsum(f["t"], axis=1, dtype=np.int16).astype(np.float32) / T_STEP
            self.r = (np.cumsum(f["r"], axis=1, dtype=np.int16).astype(np.float32) / R_STEP) ** 2

    def at(self, lat, lon):
        """(temperature in degrees Celsius as it would be at sea level, rain in mm a year)."""
        rows, cols = self.t.shape
        v = np.clip((NORTH - np.asarray(lat)) * CELLS - 0.5, 0, rows - 1.001)
        u = (np.asarray(lon) + 180) * CELLS - 0.5
        i, j = np.floor(v).astype(int), np.floor(u).astype(int)
        fv, fu = v - i, u - j
        j, j2 = j % cols, (j + 1) % cols
        return tuple((m[i, j] * (1 - fv) + m[i + 1, j] * fv) * (1 - fu) + (m[i, j2] * (1 - fv) + m[i + 1, j2] * fv) * fu
                     for m in (self.t, self.r))
