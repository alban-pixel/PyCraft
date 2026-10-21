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


def _grille_aleatoire(rng: random.Random, gw: int, gh: int) -> list[list[float]]:
    return [[rng.random() for _ in range(gw)] for _ in range(gh)]


def _echantillon(grille: list[list[float]], x: float, y: float, cellule: float) -> float:
    """Interpolation bilinéaire (smoothstep) d'une grille de bruit de valeur."""
    gx = x / cellule
    gy = y / cellule
    ix = min(int(gx), len(grille[0]) - 2)
    iy = min(int(gy), len(grille) - 2)
    fx = gx - ix
    fy = gy - iy
    fx = fx * fx * (3 - 2 * fx)
    fy = fy * fy * (3 - 2 * fy)
    a = grille[iy][ix]
    b = grille[iy][ix + 1]
    c = grille[iy + 1][ix]
    d = grille[iy + 1][ix + 1]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


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
        """Relief, lacs, plages et arbres — déterministe pour une graine donnée."""
        self.seed = seed
        self.data = bytearray(self.sx * self.sy * self.sz)
        rng = random.Random(seed)

        sea = min(config.SEA_LEVEL, self.sz // 3)
        max_h = self.sz - 2
        heights: list[int] = [0] * (self.sx * self.sy)

        # 1. Relief : deux octaves de bruit de valeur (grandes collines + ondulations).
        cellule1 = max(8, self.sx // 4)
        cellule2 = max(4, self.sx // 14)
        grille1 = _grille_aleatoire(rng, self.sx // cellule1 + 3, self.sy // cellule1 + 3)
        grille2 = _grille_aleatoire(rng, self.sx // cellule2 + 3, self.sy // cellule2 + 3)
        for y in range(self.sy):
            for x in range(self.sx):
                n1 = _echantillon(grille1, x, y, cellule1)
                n2 = _echantillon(grille2, x, y, cellule2)
                base = 3.0 + 10.0 * n1 + 3.5 * n2
                heights[y * self.sx + x] = max(3, min(max_h, int(round(base))))

        # 2. Lacs : on creuse des cuvettes sous le niveau de la mer.
        self._creuser_lacs(heights, rng, sea)

        # 3. Remplissage des colonnes (pierre, terre, herbe/sable, eau).
        for y in range(self.sy):
            for x in range(self.sx):
                h = heights[y * self.sx + x]
                colonne = bytearray()
                for z in range(h):
                    colonne.append(_STONE if z < h - 3 else Block.DIRT)
                if h > sea + 1:
                    colonne[h - 1] = Block.GRASS
                else:
                    colonne[h - 1] = Block.SAND
                for _ in range(h, sea):
                    colonne.append(_WATER)
                depart = y * self.sx + x
                self.data[depart : depart + len(colonne) * self._stride : self._stride] = colonne

        # 4. Arbres.
        self._planter_arbres(rng, sea)

    def _creuser_lacs(self, heights: list[int], rng: random.Random, sea: int) -> None:
        """Creuse quelques cuvettes pour garantir des lacs visibles."""
        nombre = max(1, (self.sx * self.sy) // 12000)
        for _ in range(nombre):
            lx = rng.randrange(10, max(11, self.sx - 10))
            ly = rng.randrange(10, max(11, self.sy - 10))
            rayon = rng.randint(7, 14)
            fond = max(2, sea - 3)
            for dy in range(-rayon, rayon + 1):
                for dx in range(-rayon, rayon + 1):
                    d2 = (dx * dx + dy * dy) / (rayon * rayon)
                    if d2 >= 1.0:
                        continue
                    x, y = lx + dx, ly + dy
                    if not self.in_bounds(x, y, 0):
                        continue
                    i = y * self.sx + x
                    h = heights[i]
                    if h <= fond:
                        continue
                    facteur = 1.0 - math.sqrt(d2)  # 1 au centre, 0 au bord
                    cible = int(round(h - (h - fond) * facteur * 1.6))
                    heights[i] = max(2, min(h, cible))

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
