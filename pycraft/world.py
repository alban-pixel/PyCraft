"""Monde voxel en bytearray plat.

Le monde est stocké dans un unique `bytearray` de taille sx*sy*sz, indexé
`(z * sy + y) * sx + x`. Chaque case contient la valeur entière d'un `Block`.
Ce module n'importe pas Pyxel et reste donc testable sans fenêtre.
"""

from __future__ import annotations

import math
import random

from pycraft import config
from pycraft.config import Block

_AIR = Block.AIR
_STONE = Block.STONE
_WATER = Block.WATER


class World:
    """Un monde cubique de blocs, généré de façon déterministe."""

    def __init__(
        self,
        sx: int = config.WORLD_X,
        sy: int = config.WORLD_Y,
        sz: int = config.WORLD_Z,
        seed: int = 0,
    ) -> None:
        self.sx = sx
        self.sy = sy
        self.sz = sz
        self.seed = seed
        self._stride = sx * sy
        self.data = bytearray(sx * sy * sz)
        self.generate(seed)

    # ------------------------------------------------------------------
    # Accès
    # ------------------------------------------------------------------
    def _idx(self, x: int, y: int, z: int) -> int:
        return z * self._stride + y * self.sx + x

    def in_bounds(self, x: int, y: int, z: int) -> bool:
        return 0 <= x < self.sx and 0 <= y < self.sy and 0 <= z < self.sz

    def get(self, x: int, y: int, z: int) -> Block:
        """Bloc en (x, y, z). Hors bornes : air, sauf sous z=0 (pierre)."""
        if z < 0:
            return _STONE
        if z >= self.sz or x < 0 or y < 0 or x >= self.sx or y >= self.sy:
            return _AIR
        return Block(self.data[self._idx(x, y, z)])

    def set(self, x: int, y: int, z: int, block: Block) -> None:
        """Écrit un bloc. Les coordonnées hors bornes sont ignorées."""
        if not self.in_bounds(x, y, z):
            return
        self.data[self._idx(x, y, z)] = int(block)

    def is_solid(self, x: int, y: int, z: int) -> bool:
        """Vrai si le bloc est solide (ni air ni eau)."""
        if z < 0:
            return True
        if z >= self.sz or x < 0 or y < 0 or x >= self.sx or y >= self.sy:
            return False
        value = self.data[self._idx(x, y, z)]
        return value != 0 and value != _WATER

    def surface_height(self, x: int, y: int) -> int:
        """Altitude de la première case libre au-dessus du sol solide."""
        if x < 0 or y < 0 or x >= self.sx or y >= self.sy:
            return 0
        for z in range(self.sz - 1, -1, -1):
            if self.is_solid(x, y, z):
                return z + 1
        return 0

    def spawn_point(self) -> tuple[float, float, float]:
        """Point d'apparition : au centre, sur la terre ferme, hors de l'eau."""
        cx, cy = self.sx // 2, self.sy // 2
        for radius in range(0, max(self.sx, self.sy) // 2):
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    if radius > 0 and max(abs(dx), abs(dy)) != radius:
                        continue
                    x, y = cx + dx, cy + dy
                    if not (0 <= x < self.sx and 0 <= y < self.sy):
                        continue
                    h = self.surface_height(x, y)
                    if h <= config.SEA_LEVEL or h + 3 >= self.sz:
                        continue
                    if self.get(x, y, h - 1) not in (Block.GRASS, Block.SAND):
                        continue
                    if any(not self.is_solid(x, y, h + i) for i in range(3)):
                        return (x + 0.5, y + 0.5, float(h) + 1.7)
        # Repli : au-dessus du centre, quoi qu'il arrive
        h = self.surface_height(cx, cy)
        return (cx + 0.5, cy + 0.5, float(min(h + 2, self.sz - 1)))

    # ------------------------------------------------------------------
    # Génération
    # ------------------------------------------------------------------
    def generate(self, seed: int) -> None:
        """Relief, eau, plages et arbres — déterministe pour une graine donnée."""
        self.seed = seed
        self.data = bytearray(self.sx * self.sy * self.sz)
        rng = random.Random(seed)

        sea = min(config.SEA_LEVEL, self.sz // 3)
        max_h = self.sz - 2
        heights: list[int] = [0] * (self.sx * self.sy)

        for y in range(self.sy):
            for x in range(self.sx):
                bruit = (rng.random() - 0.5) * 1.2
                base = (
                    7.0
                    + 3.0 * math.sin(x / 11.0)
                    + 2.4 * math.cos(y / 13.0)
                    + 1.6 * math.sin((x + y) / 7.0)
                    + bruit
                )
                # hauteurs quantifiées par 2 : plateaux francs, style Minecraft
                h = max(3, min(max_h, 2 * round(base / 2)))
                heights[y * self.sx + x] = h

                colonne = bytearray()
                for z in range(h):
                    if z < h - 3:
                        colonne.append(_STONE)
                    else:
                        colonne.append(Block.DIRT)
                if h > sea + 1:
                    colonne[h - 1] = Block.GRASS
                else:
                    colonne[h - 1] = Block.SAND
                for _ in range(h, sea):
                    colonne.append(_WATER)

                depart = y * self.sx + x
                self.data[depart : depart + len(colonne) * self._stride : self._stride] = colonne

        self._planter_arbres(rng, sea)

    def _planter_arbres(self, rng: random.Random, sea: int) -> None:
        """Plante des arbres sur l'herbe, hors de l'eau et des bords."""
        nombre = max(4, (self.sx * self.sy) // 1600)
        for _ in range(nombre):
            x = rng.randrange(2, max(3, self.sx - 2))
            y = rng.randrange(2, max(3, self.sy - 2))
            sol = self.surface_height(x, y)
            if sol <= sea or sol + 6 >= self.sz:
                continue
            if self.get(x, y, sol - 1) is not Block.GRASS:
                continue
            if not self.is_solid(x, y, sol - 1):
                continue

            tronc = rng.randint(4, 5)
            for z in range(sol, min(sol + tronc, self.sz)):
                self.set(x, y, z, Block.WOOD)
            sommet = sol + tronc
            for dz in (-2, -1, 0):
                rayon = 2 if dz < 0 else 1
                for dy in range(-rayon, rayon + 1):
                    for dx in range(-rayon, rayon + 1):
                        if abs(dx) + abs(dy) > rayon + 1:
                            continue
                        zz = sommet + dz
                        if not self.in_bounds(x + dx, y + dy, zz):
                            continue
                        if self.get(x + dx, y + dy, zz) is Block.AIR:
                            self.set(x + dx, y + dy, zz, Block.LEAVES)
