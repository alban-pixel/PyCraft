"""Maillage des chunks : faces visibles, couleurs, cache.

Deux maillages sont prévus :
- `detail` : une face par bloc exposé (utilisé près de la caméra) ;
- `greedy` : faces coplanaires fusionnées (utilisé au loin, ajouté en T6).

Ce module n'importe pas Pyxel.
"""

from __future__ import annotations

import numpy as np

from pycraft import config
from pycraft.config import Block
from pycraft.world import World

CHUNK = config.CHUNK_SIZE
EPS = 0.02  # recouvrement des quads fusionnés (anti T-junction)

# 0:+z 1:-z 2:+x 3:-x 4:+y 5:-y
DIRS = ((0, 0, 1), (0, 0, -1), (1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0))
CORNERS = (
    ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),
    ((0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)),
    ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)),
    ((0, 1, 0), (0, 0, 0), (0, 0, 1), (0, 1, 1)),
    ((1, 1, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1)),
    ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),
)

EMPTY_VERTS = np.zeros((0, 4, 3), dtype=np.float32)
EMPTY_COLORS = np.zeros(0, dtype=np.uint8)


def face_color(block_value: int, direction: int) -> int:
    """Couleur (indice palette) d'une face selon l'orientation."""
    couleurs = config.BLOCK_COLORS[Block(block_value)]
    if direction == 0:
        return couleurs[0]
    if direction == 1:
        return couleurs[3]
    if direction in (2, 3):
        return couleurs[1]
    return couleurs[2]


def build_detail(world: World, cx: int, cy: int) -> tuple[np.ndarray, np.ndarray]:
    """Maillage « une face par bloc exposé » d'un chunk."""
    data = world.data
    sx, sy, sz = world.sx, world.sy, world.sz
    stride = sx * sy
    x0, y0 = cx * CHUNK, cy * CHUNK
    quads: list[list[tuple[int, int, int]]] = []
    cols: list[int] = []

    for y in range(y0, y0 + CHUNK):
        for x in range(x0, x0 + CHUNK):
            base = y * sx + x
            for z in range(sz):
                b = data[base + z * stride]
                if b == 0:
                    continue
                for d in range(6):
                    dx, dy, dz = DIRS[d]
                    nx, ny, nz = x + dx, y + dy, z + dz
                    if nz < 0:
                        continue  # le sol hors monde cache la face du dessous
                    if nx < 0 or ny < 0 or nx >= sx or ny >= sy or nz >= sz:
                        voisin = 0
                    else:
                        voisin = data[nz * stride + ny * sx + nx]
                    if voisin != 0:
                        continue
                    quads.append([(x + a, y + b2, z + c) for a, b2, c in CORNERS[d]])
                    cols.append(face_color(b, d))

    if not quads:
        return EMPTY_VERTS.copy(), EMPTY_COLORS.copy()
    return np.array(quads, dtype=np.float32), np.array(cols, dtype=np.uint8)


class ChunkMeshes:
    """Cache des maillages par chunk, invalidé quand un bloc change."""

    def __init__(self, world: World) -> None:
        self.world = world
        self._detail: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}
        self._greedy: dict[tuple[int, int], tuple[np.ndarray, np.ndarray]] = {}

    def detail(self, cx: int, cy: int) -> tuple[np.ndarray, np.ndarray]:
        key = (cx, cy)
        mesh = self._detail.get(key)
        if mesh is None:
            mesh = build_detail(self.world, cx, cy)
            self._detail[key] = mesh
        return mesh

    def greedy(self, cx: int, cy: int) -> tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError("greedy meshing : tâche T6")

    def invalidate(self, x: int, y: int) -> None:
        """Oublie le chunk contenant (x, y) et ses voisins de bord."""
        cx, cy = x // CHUNK, y // CHUNK
        cles = {(cx, cy)}
        if x % CHUNK == 0:
            cles.add((cx - 1, cy))
        if x % CHUNK == CHUNK - 1:
            cles.add((cx + 1, cy))
        if y % CHUNK == 0:
            cles.add((cx, cy - 1))
        if y % CHUNK == CHUNK - 1:
            cles.add((cx, cy + 1))
        for cle in cles:
            self._detail.pop(cle, None)
            self._greedy.pop(cle, None)

    def reset(self) -> None:
        self._detail.clear()
        self._greedy.clear()
