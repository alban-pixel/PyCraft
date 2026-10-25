"""Smooth gradient noise (Perlin noise), computed for whole NumPy arrays of coordinates at once."""
import numpy as np

PERIOD = 1024  # the lattice repeats every 1024 units; octaves are rotated and shifted, so it never shows


def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def smoothstep(lo, hi, x):
    t = np.clip((x - lo) / (hi - lo), 0.0, 1.0)
    return t * t * (3 - 2 * t)


class Noise:
    """2D and 3D Perlin noise in about [-1, 1], plus fractal sums of several octaves."""

    def __init__(self, seed):
        rng = np.random.default_rng(seed)
        self.perm = np.tile(rng.permutation(PERIOD), 2).astype(np.int64)
        angle = rng.uniform(0, 2 * np.pi, PERIOD)
        self.gx2, self.gy2 = np.cos(angle), np.sin(angle)
        g = rng.normal(size=(PERIOD, 3))
        g /= np.linalg.norm(g, axis=1, keepdims=True)
        self.gx3, self.gy3, self.gz3 = g.T.copy()
        # Every octave gets its own shift and rotation, so the octaves don't line up
        self.shift = rng.uniform(0, PERIOD, (16, 3))
        turn = rng.uniform(0, 2 * np.pi, 16)
        self.cos, self.sin = np.cos(turn), np.sin(turn)

    def noise2(self, x, y):
        x0, y0 = np.floor(x), np.floor(y)
        fx, fy = x - x0, y - y0
        ix = x0.astype(np.int64) & (PERIOD - 1)
        iy = y0.astype(np.int64) & (PERIOD - 1)
        p, gx, gy = self.perm, self.gx2, self.gy2
        a, b = p[ix] + iy, p[ix + 1] + iy
        h00, h01, h10, h11 = p[a], p[a + 1], p[b], p[b + 1]
        n00 = gx[h00] * fx + gy[h00] * fy
        n10 = gx[h10] * (fx - 1) + gy[h10] * fy
        n01 = gx[h01] * fx + gy[h01] * (fy - 1)
        n11 = gx[h11] * (fx - 1) + gy[h11] * (fy - 1)
        u, v = _fade(fx), _fade(fy)
        nx0 = n00 + u * (n10 - n00)
        nx1 = n01 + u * (n11 - n01)
        return (nx0 + v * (nx1 - nx0)) * 1.4142

    def noise3(self, x, y, z):
        x0, y0, z0 = np.floor(x), np.floor(y), np.floor(z)
        fx, fy, fz = x - x0, y - y0, z - z0
        ix = x0.astype(np.int64) & (PERIOD - 1)
        iy = y0.astype(np.int64) & (PERIOD - 1)
        iz = z0.astype(np.int64) & (PERIOD - 1)
        p = self.perm
        a, b = p[ix] + iy, p[ix + 1] + iy
        aa, ab, ba, bb = p[a] + iz, p[a + 1] + iz, p[b] + iz, p[b + 1] + iz

        def grad(h, dx, dy, dz):
            h = p[h]
            return self.gx3[h] * dx + self.gy3[h] * dy + self.gz3[h] * dz

        u, v, w = _fade(fx), _fade(fy), _fade(fz)
        x00 = grad(aa, fx, fy, fz) + u * (grad(ba, fx - 1, fy, fz) - grad(aa, fx, fy, fz))
        x10 = grad(ab, fx, fy - 1, fz) + u * (grad(bb, fx - 1, fy - 1, fz) - grad(ab, fx, fy - 1, fz))
        x01 = grad(aa + 1, fx, fy, fz - 1) + u * (grad(ba + 1, fx - 1, fy, fz - 1) - grad(aa + 1, fx, fy, fz - 1))
        x11 = grad(ab + 1, fx, fy - 1, fz - 1) + u * (
            grad(bb + 1, fx - 1, fy - 1, fz - 1) - grad(ab + 1, fx, fy - 1, fz - 1))
        y0_ = x00 + v * (x10 - x00)
        y1_ = x01 + v * (x11 - x01)
        return (y0_ + w * (y1_ - y0_)) * 1.25

    def _octave2(self, x, y, i, freq):
        """Coordinates of octave i: scaled, rotated and shifted."""
        xs, ys = x * freq, y * freq
        return (xs * self.cos[i] - ys * self.sin[i] + self.shift[i, 0],
                xs * self.sin[i] + ys * self.cos[i] + self.shift[i, 1])

    def fbm2(self, x, y, octaves, lacunarity=2.0, gain=0.5):
        """Sum of octaves of noise, each finer and fainter than the last. About [-1, 1]."""
        total, amp, norm, freq = 0.0, 1.0, 0.0, 1.0
        for i in range(octaves):
            total = total + amp * self.noise2(*self._octave2(x, y, i, freq))
            norm += amp
            amp *= gain
            freq *= lacunarity
        return total / norm

    def ridged2(self, x, y, octaves, lacunarity=2.0, gain=0.5, sharpness=2.0):
        """Ridged multifractal noise in [0, 1]: sharp crests where the noise crosses zero.

        Each octave is weighted by the one before it, so crests get fine detail while the
        valleys between them stay smooth, a bit like eroded mountains."""
        total, amp, norm, freq, weight = 0.0, 1.0, 0.0, 1.0, 1.0
        for i in range(octaves):
            signal = (1.0 - np.abs(self.noise2(*self._octave2(x, y, i, freq)))) ** 2 * weight
            total = total + amp * signal
            norm += amp
            weight = np.clip(signal * sharpness, 0.0, 1.0)
            amp *= gain
            freq *= lacunarity
        return total / norm

    def fbm3(self, x, y, z, octaves, lacunarity=2.0, gain=0.5):
        total, amp, norm, freq = 0.0, 1.0, 0.0, 1.0
        for i in range(octaves):
            s = self.shift[i]
            total = total + amp * self.noise3(x * freq + s[0], y * freq + s[1], z * freq + s[2])
            norm += amp
            amp *= gain
            freq *= lacunarity
        return total / norm
