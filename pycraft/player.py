"""Déplacement du joueur et collisions AABB.

Le joueur est une boîte de rayon `radius` et de hauteur `height`, dont la
position (x, y, z) est celle des **pieds**. Les collisions se font axe par axe,
ce qui produit naturellement le glissement le long des murs.
"""

from __future__ import annotations

import math

from pycraft import config
from pycraft.world import World

_EPS = 1e-6


class Player:
    """Position, orientation et déplacement d'un joueur à pied."""

    def __init__(
        self,
        x: float,
        y: float,
        z: float,
        yaw: float = 0.0,
        pitch: float = 0.0,
        speed: float = 6.0,
        radius: float = 0.3,
        height: float = 1.7,
        eye: float = 1.55,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.yaw = float(yaw)
        self.pitch = float(pitch)
        self.speed = float(speed)
        self.radius = float(radius)
        self.height = float(height)
        self.eye = float(eye)

    # ------------------------------------------------------------------
    def eye_position(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z + self.eye)

    def look_direction(self) -> tuple[float, float, float]:
        cp = math.cos(self.pitch)
        return (cp * math.cos(self.yaw), cp * math.sin(self.yaw), math.sin(self.pitch))

    # ------------------------------------------------------------------
    def collides(self, world: World, x: float, y: float, z: float) -> bool:
        """Vrai si la boîte du joueur en (x, y, z) touche un bloc solide."""
        r = self.radius
        x0 = math.floor(x - r)
        x1 = math.floor(x + r)
        y0 = math.floor(y - r)
        y1 = math.floor(y + r)
        z0 = math.floor(z)
        z1 = math.floor(z + self.height - _EPS)
        for bx in range(x0, x1 + 1):
            for by in range(y0, y1 + 1):
                for bz in range(z0, z1 + 1):
                    if world.is_solid(bx, by, bz):
                        return True
        return False

    def move(self, world: World, dx: float, dy: float, dz: float = 0.0) -> None:
        """Déplace le joueur par petits pas (pas de tunnelling), axe par axe."""
        longueur = max(abs(dx), abs(dy), abs(dz))
        pas = max(1, int(longueur / 0.2) + 1)
        for _ in range(pas):
            self._move_step(world, dx / pas, dy / pas, dz / pas)
        self._clamp(world)

    def _move_step(self, world: World, dx: float, dy: float, dz: float) -> None:
        # axe X
        if dx:
            nx = self.x + dx
            if not self.collides(world, nx, self.y, self.z):
                self.x = nx
        # axe Y
        if dy:
            ny = self.y + dy
            if not self.collides(world, self.x, ny, self.z):
                self.y = ny
        # axe Z
        if dz:
            nz = self.z + dz
            if not self.collides(world, self.x, self.y, nz):
                self.z = nz

    def _clamp(self, world: World) -> None:
        marge = self.radius + 0.01
        self.x = min(max(self.x, marge), world.sx - marge)
        self.y = min(max(self.y, marge), world.sy - marge)

    # ------------------------------------------------------------------
    def update(
        self,
        world: World,
        dt: float,
        avant: float = 0.0,
        cote: float = 0.0,
        tourner: float = 0.0,
        incliner: float = 0.0,
    ) -> None:
        """Une frame de déplacement.

        avant  : +1 devant, -1 derrière
        cote   : +1 à droite, -1 à gauche
        tourner / incliner : en radians par seconde
        """
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        distance = self.speed * dt
        dx = (avant * cy + cote * sy) * distance
        dy = (avant * sy - cote * cy) * distance
        self.move(world, dx, dy)
        self.set_angles(self.yaw + tourner * dt, self.pitch + incliner * dt)

    # ------------------------------------------------------------------
    def raycast(
        self, world: World, max_dist: float = 5.0
    ) -> tuple[tuple[int, int, int], tuple[int, int, int]] | None:
        """Bloc visé et normale de sa face, par marche de voxels (Amanatides & Woo)."""
        ox, oy, oz = self.eye_position()
        dx, dy, dz = self.look_direction()
        x, y, z = math.floor(ox), math.floor(oy), math.floor(oz)

        sx = 1 if dx > 0 else (-1 if dx < 0 else 0)
        sy = 1 if dy > 0 else (-1 if dy < 0 else 0)
        sz = 1 if dz > 0 else (-1 if dz < 0 else 0)

        infini = float("inf")
        tdx = abs(1.0 / dx) if dx else infini
        tdy = abs(1.0 / dy) if dy else infini
        tdz = abs(1.0 / dz) if dz else infini
        tmx = ((x + (1 if dx > 0 else 0)) - ox) / dx if dx else infini
        tmy = ((y + (1 if dy > 0 else 0)) - oy) / dy if dy else infini
        tmz = ((z + (1 if dz > 0 else 0)) - oz) / dz if dz else infini

        normale = (0, 0, 0)
        for _ in range(256):
            if tmx <= tmy and tmx <= tmz:
                x += sx
                t = tmx
                tmx += tdx
                normale = (-sx, 0, 0)
            elif tmy <= tmz:
                y += sy
                t = tmy
                tmy += tdy
                normale = (0, -sy, 0)
            else:
                z += sz
                t = tmz
                tmz += tdz
                normale = (0, 0, -sz)
            if t > max_dist:
                return None
            if world.is_solid(x, y, z):
                return (x, y, z), normale
        return None

    # ------------------------------------------------------------------
    def blocks_player_box(self, bx: int, by: int, bz: int) -> bool:
        """Vrai si le cube (bx, by, bz) chevauche la boîte du joueur."""
        r = self.radius
        return (
            bx + 1 > self.x - r
            and bx < self.x + r
            and by + 1 > self.y - r
            and by < self.y + r
            and bz + 1 > self.z
            and bz < self.z + self.height
        )

    def break_block(self, world: World, meshes) -> bool:
        """Casse le bloc visé. Renvoie False si rien n'est cassable."""
        hit = self.raycast(world)
        if hit is None:
            return False
        (x, y, z), _ = hit
        if world.get(x, y, z) is config.Block.AIR:
            return False
        world.set(x, y, z, config.Block.AIR)
        meshes.invalidate(x, y)
        return True

    def place_block(self, world: World, meshes, block: config.Block) -> bool:
        """Pose un bloc sur la face visée, jamais dans le joueur."""
        hit = self.raycast(world)
        if hit is None:
            return False
        (x, y, z), (nx, ny, nz) = hit
        tx, ty, tz = x + nx, y + ny, z + nz
        if not world.in_bounds(tx, ty, tz):
            return False
        if world.get(tx, ty, tz) is not config.Block.AIR:
            return False
        if self.blocks_player_box(tx, ty, tz):
            return False
        world.set(tx, ty, tz, block)
        meshes.invalidate(tx, ty)
        return True

    def set_angles(self, yaw: float, pitch: float) -> None:
        limite = math.pi / 2 - 0.01
        self.yaw = yaw % (2 * math.pi)
        self.pitch = max(-limite, min(limite, pitch))
