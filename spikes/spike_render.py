"""Spike de performance — rendu voxel de référence, jetable.

Ce fichier sert à verrouiller les réglages (résolution, distance de vue, LOD)
avant d'écrire le vrai moteur. Il n'est pas importé par le jeu.

    python spikes/spike_render.py --res 1280x800 --dist 96 --detail 16
    python spikes/spike_render.py --res 1920x1200 --dist 120 --detail 24 --capture out.png
"""

from __future__ import annotations

import argparse
import math
import time

import numpy as np
import pyxel

CH = 16
NZ = 32
EPS = 0.02  # recouvrement des quads fusionnés (anti T-junction)


# ----------------------------------------------------------------------
# Monde
# ----------------------------------------------------------------------
def build_world(n: int):
    hmap = np.zeros((n, n), np.int32)
    typemap = np.zeros((n, n), np.uint8)
    for y in range(n):
        for x in range(n):
            h = 6 + 3.0 * math.sin(x / 11.0) + 2.4 * math.cos(y / 13.0) + 1.6 * math.sin((x + y) / 7.0)
            h = max(3, min(26, int(2 * round(h / 2))))
            hmap[y, x] = h
            typemap[y, x] = 1 if h > 7 else (2 if h > 4 else 3)
    return hmap, typemap


TOP = {1: 11, 2: 10, 3: 13}
SIDE_X = {1: 3, 2: 9, 3: 6}
SIDE_Y = {1: 4, 2: 4, 3: 6}


def build_greedy(hmap, typemap, cx, cy, n):
    """Maillage fusionné d'un chunk (terrain heightmap)."""
    quads: list = []
    cols: list = []

    def h_at(x, y):
        if x < 0 or y < 0 or x >= n or y >= n:
            return 0
        return int(hmap[y, x])

    x0c, y0c = cx * CH, cy * CH
    # dessus
    used = set()
    for y in range(y0c, y0c + CH):
        for x in range(x0c, x0c + CH):
            if (x, y) in used:
                continue
            h = h_at(x, y)
            t = typemap[y, x]
            if h >= NZ:
                continue
            x1 = x
            while x1 + 1 < x0c + CH and h_at(x1 + 1, y) == h and typemap[y, x1 + 1] == t and (x1 + 1, y) not in used:
                x1 += 1
            y1 = y
            while y1 + 1 < y0c + CH:
                if not all(h_at(xx, y1 + 1) == h and typemap[y1 + 1, xx] == t and (xx, y1 + 1) not in used for xx in range(x, x1 + 1)):
                    break
                y1 += 1
            for yy in range(y, y1 + 1):
                for xx in range(x, x1 + 1):
                    used.add((xx, yy))
            quads.append(expand([(x, y, h), (x1 + 1, y, h), (x1 + 1, y1 + 1, h), (x, y1 + 1, h)]))
            cols.append(TOP[t])
    # parois x
    for x in range(x0c, x0c + CH):
        for sign in (1, -1):
            y = y0c
            while y < y0c + CH:
                nh, h = h_at(x + sign, y), h_at(x, y)
                if nh >= h:
                    y += 1
                    continue
                key = (nh, h, typemap[y, x])
                y0 = y
                y += 1
                while y < y0c + CH and (h_at(x + sign, y), h_at(x, y), typemap[y, x]) == key:
                    y += 1
                X = x + 1 if sign == 1 else x
                quads.append(expand([(X, y0, key[0]), (X, y0, key[1]), (X, y, key[1]), (X, y, key[0])]))
                cols.append(SIDE_X[key[2]])
    # parois y
    for y in range(y0c, y0c + CH):
        for sign in (1, -1):
            x = x0c
            while x < x0c + CH:
                nh, h = h_at(x, y + sign), h_at(x, y)
                if nh >= h:
                    x += 1
                    continue
                key = (nh, h, typemap[y, x])
                x0 = x
                x += 1
                while x < x0c + CH and (h_at(x, y + sign), h_at(x, y), typemap[y, x]) == key:
                    x += 1
                Y = y + 1 if sign == 1 else y
                quads.append(expand([(x0, Y, key[0]), (x, Y, key[0]), (x, Y, key[1]), (x0, Y, key[1])]))
                cols.append(SIDE_Y[key[2]])
    if not quads:
        return np.zeros((0, 4, 3), np.float32), np.zeros(0, np.uint8)
    return np.array(quads, np.float32), np.array(cols, np.uint8)


FACES = {
    (0, 0, 1): ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),
    (0, 0, -1): ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)),
    (1, 0, 0): ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)),
    (-1, 0, 0): ((0, 1, 0), (0, 0, 0), (0, 0, 1), (0, 1, 1)),
    (0, 1, 0): ((1, 1, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)),
    (0, -1, 0): ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),
}


def expand(quad):
    """Agrandit un quad de EPS dans son plan pour boucher les T-junctions."""
    xs = [p[0] for p in quad]
    ys = [p[1] for p in quad]
    zs = [p[2] for p in quad]
    out = []
    for x, y, z in quad:
        if max(xs) > min(xs):
            x = x + EPS if x == min(xs) else x - EPS
        if max(ys) > min(ys):
            y = y + EPS if y == min(ys) else y - EPS
        if max(zs) > min(zs):
            z = z + EPS if z == min(zs) else z - EPS
        out.append((x, y, z))
    return out


def build_detail(hmap, typemap, cx, cy):
    """Maillage détail : une face par bloc exposé."""
    quads, cols = [], []
    for y in range(cy * CH, cy * CH + CH):
        for x in range(cx * CH, cx * CH + CH):
            h = int(hmap[y, x])
            t = typemap[y, x]
            for (nx, ny, nz), corners in FACES.items():
                if nz == 1:
                    if h < NZ:
                        quads.append([(x + ax, y + ay, h + az) for ax, ay, az in corners])
                        cols.append(TOP[t])
                elif nz == 0:
                    nh = int(hmap[y + ny, x + nx]) if 0 <= x + nx < hmap.shape[1] and 0 <= y + ny < hmap.shape[0] else 0
                    for z in range(nh, h):
                        quads.append([(x + ax, y + ay, z + az) for ax, ay, az in corners])
                        cols.append(SIDE_X[t] if nx else SIDE_Y[t])
    if not quads:
        return np.zeros((0, 4, 3), np.float32), np.zeros(0, np.uint8)
    return np.array(quads, np.float32), np.array(cols, np.uint8)


# ----------------------------------------------------------------------
# Rendu
# ----------------------------------------------------------------------
class Spike:
    def __init__(self, width, height, dist, detail_radius, use_detail=True):
        self.w, self.h = width, height
        self.dist = dist
        self.detail_radius = detail_radius
        self.use_detail = use_detail
        self.n = 256
        t0 = time.perf_counter()
        self.hmap, self.typemap = build_world(self.n)
        self.chunks = {}
        for cy in range(self.n // CH):
            for cx in range(self.n // CH):
                gv, gc = build_greedy(self.hmap, self.typemap, cx, cy, self.n)
                self.chunks[(cx, cy)] = [gv, gc, np.array([cx * CH + CH / 2, cy * CH + CH / 2, 10.0], np.float32), None, None]
        print(f"world+greedy: {(time.perf_counter()-t0)*1000:.0f} ms, quads={sum(len(v) for v, *_ in self.chunks.values())}")

        self.cam = np.array([128.0, 128.0, 30.0], np.float32)
        self.yaw, self.pitch = math.radians(35), math.radians(-24)
        self.f = (self.w / 2) / math.tan(math.radians(75) / 2)
        cy_, sy_ = math.cos(self.yaw), math.sin(self.yaw)
        cp_, sp_ = math.cos(self.pitch), math.sin(self.pitch)
        self.fwd = np.array([cp_ * cy_, cp_ * sy_, sp_], np.float32)
        self.right = np.array([sy_, -cy_, 0.0], np.float32)
        self.up = np.array([-sp_ * cy_, -sp_ * sy_, cp_], np.float32)
        self.tri = pyxel.tri

    def detail_mesh(self, key):
        entry = self.chunks[key]
        if entry[3] is None:
            entry[3] = build_detail(self.hmap, self.typemap, key[0], key[1])
        return entry[3]

    def gather(self):
        vs, cs = [], []
        for key, (gv, gc, center, _, _) in self.chunks.items():
            d = center - self.cam
            dist = float(np.hypot(d[0], d[1]))
            if dist > self.dist:
                continue
            if dist > 1.0:
                ang = math.degrees(math.acos(max(-1, min(1, float(d[0] * self.fwd[0] + d[1] * self.fwd[1]) / (dist + 1e-9)))))
                if ang > 75:
                    continue
            near = self.use_detail and dist <= self.detail_radius
            v, c = self.detail_mesh(key) if near else (gv, gc)
            if len(v):
                vs.append(v)
                cs.append(c)
        if not vs:
            return np.zeros((0, 4, 3), np.float32), np.zeros(0, np.uint8)
        return np.concatenate(vs), np.concatenate(cs)

    def draw(self):
        v, c = self.gather()
        if len(v) == 0:
            return 0
        rel = v - self.cam
        xc = rel @ self.right
        yc = rel @ self.up
        zc = rel @ self.fwd
        vis = (zc > 1.0).all(axis=1)
        xc, yc, zc, c = xc[vis], yc[vis], zc[vis], c[vis]
        sx = (self.w / 2 + self.f * xc / zc).tolist()
        sy = (self.h / 2 - self.f * yc / zc).tolist()
        order = np.argsort(-zc.mean(axis=1)).tolist()
        cc = c.tolist()
        tri = self.tri
        for i in order:
            a, b = sx[i], sy[i]
            tri(a[0], b[0], a[1], b[1], a[2], b[2], cc[i])
            tri(a[0], b[0], a[2], b[2], a[3], b[3], cc[i])
        return len(order)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--res", default="1280x800")
    ap.add_argument("--dist", type=int, default=96)
    ap.add_argument("--detail", type=int, default=16)
    ap.add_argument("--no-detail", action="store_true")
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--capture", default="")
    args = ap.parse_args()

    w, h = (int(x) for x in args.res.lower().split("x"))
    pyxel.init(w, h, title=f"spike {w}x{h}", fps=1000)
    spike = Spike(w, h, args.dist, args.detail, use_detail=not args.no_detail)
    pyxel.cls(12)
    n = spike.draw()
    if args.capture:
        pyxel.screen.save(args.capture, 1)
    t0 = time.perf_counter()
    for _ in range(args.frames):
        pyxel.cls(12)
        n = spike.draw()
    dt = (time.perf_counter() - t0) / args.frames * 1000
    print(f"{w}x{h} dist={args.dist} detail={args.detail}: quads={n} frame={dt:.2f} ms -> {1000/dt:.0f} fps max")
    pyxel.quit()


if __name__ == "__main__":
    main()
