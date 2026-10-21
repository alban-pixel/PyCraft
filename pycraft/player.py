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

    def set_angles(self, yaw: float, pitch: float) -> None:
        limite = math.pi / 2 - 0.01
        self.yaw = yaw % (2 * math.pi)
        self.pitch = max(-limite, min(limite, pitch))
