"""Rendu du monde : ciel, brouillard et faces triées (algorithme du peintre)."""

from __future__ import annotations

import math

import numpy as np
import pyxel

from pycraft import config
from pycraft.camera import Camera, clip_near
from pycraft.mesher import CHUNK, ChunkMeshes, select_mesh
from pycraft.world import World

_FOG_STEPS = 4
_fog_cache: dict[tuple[int, int], int] = {}


# ----------------------------------------------------------------------
# Fonctions pures (testables sans fenêtre)
# ----------------------------------------------------------------------
def fog_factor(depth: float, view_distance: float) -> float:
    """0 = pas de brouillard, 1 = couleur du ciel."""
    if view_distance <= 0:
        return 0.0
    t = depth / view_distance
    etendue = config.FOG_FULL - config.FOG_START
    if etendue <= 0:
        return 1.0 if t >= config.FOG_FULL else 0.0
    return min(1.0, max(0.0, (t - config.FOG_START) / etendue))


def nearest_palette(rgb: tuple[float, float, float]) -> int:
    """Indice de la couleur de la palette la plus proche d'un RGB."""
    meilleur, distance = 0, float("inf")
    for i, c in enumerate(config.PALETTE):
        d = (c[0] - rgb[0]) ** 2 + (c[1] - rgb[1]) ** 2 + (c[2] - rgb[2]) ** 2
        if d < distance:
            meilleur, distance = i, d
    return meilleur


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[float, float, float]:
    return (
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t,
    )


def fog_color_index(color: int, factor: float) -> int:
    """Couleur d'une face après application du brouillard (palette 16 couleurs)."""
    if factor <= 0.0:
        return color
    if factor >= 1.0:
        return config.FOG_COLOR
    palier = min(_FOG_STEPS - 1, int(factor * _FOG_STEPS))
    cle = (color, palier)
    couleur = _fog_cache.get(cle)
    if couleur is None:
        t = palier / (_FOG_STEPS - 1)
        couleur = nearest_palette(_mix(config.PALETTE[color], config.PALETTE[config.FOG_COLOR], t))
        _fog_cache[cle] = couleur
    return couleur


_CUBE_EDGES = (
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 6), (6, 7), (7, 4),
    (0, 4), (1, 5), (2, 6), (3, 7),
)


def selection_edges(
    x: int, y: int, z: int, marge: float = 0.004
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Les 12 arêtes du cube (x, y, z) → (x+1, y+1, z+1), légèrement agrandi."""
    lo = (x - marge, y - marge, z - marge)
    hi = (x + 1 + marge, y + 1 + marge, z + 1 + marge)
    coins = [
        (lo[0], lo[1], lo[2]),
        (hi[0], lo[1], lo[2]),
        (hi[0], hi[1], lo[2]),
        (lo[0], hi[1], lo[2]),
        (lo[0], lo[1], hi[2]),
        (hi[0], lo[1], hi[2]),
        (hi[0], hi[1], hi[2]),
        (lo[0], hi[1], hi[2]),
    ]
    return [(coins[a], coins[b]) for a, b in _CUBE_EDGES]


def sky_color_at(t: float) -> int:
    """Couleur du ciel : t = 0 à l'horizon, 1 au zénith."""
    return config.SKY_TOP if t > 0.62 else config.SKY_HORIZON


# ----------------------------------------------------------------------
# Renderer
# ----------------------------------------------------------------------
class Renderer:
    """Dessine le monde vu par une caméra."""

    def __init__(
        self,
        world: World,
        meshes: ChunkMeshes,
        width: int,
        height: int,
        view_distance: float = config.DEFAULT_VIEW_DISTANCE,
        detail_radius: float = config.DEFAULT_DETAIL_RADIUS,
        use_detail: bool = True,
        use_fog: bool = True,
    ) -> None:
        self.world = world
        self.meshes = meshes
        self.width = width
        self.height = height
        self.view_distance = float(view_distance)
        self.detail_radius = float(detail_radius)
        self.use_detail = use_detail
        self.use_fog = use_fog
        self.quads = 0
        self.chunks_visibles = 0

    # ------------------------------------------------------------------
    def draw(self, camera: Camera, selection: tuple[int, int, int] | None = None, time: float = 0.0) -> None:
        self._draw_sky(camera)
        verts, colors = self._gather(camera)
        self.quads = 0
        if len(verts) == 0:
            return
        cam = camera.to_camera(verts.reshape(-1, 3)).reshape(-1, 4, 3)
        z = cam[..., 2]
        devant = (z > config.NEAR_PLANE).all(axis=1)
        self._draw_front(camera, cam, z, colors, devant)
        self._draw_clipped(camera, cam, z, colors, devant)
        if selection is not None:
            self._draw_selection(camera, selection)

    # ------------------------------------------------------------------
    def _gather(self, camera: Camera) -> tuple[np.ndarray, np.ndarray]:
        """Assemble les quads des chunks visibles (distance + cône de vue)."""
        dist = self.view_distance
        x_min = max(0, int((camera.pos[0] - dist) // CHUNK))
        x_max = min((self.world.sx - 1) // CHUNK, int((camera.pos[0] + dist) // CHUNK))
        y_min = max(0, int((camera.pos[1] - dist) // CHUNK))
        y_max = min((self.world.sy - 1) // CHUNK, int((camera.pos[1] + dist) // CHUNK))

        fwd = camera.fwd
        longueur = math.hypot(fwd[0], fwd[1]) or 1.0
        cos_limite = math.cos(math.radians(camera.fov_deg / 2 + 14))

        verts: list[np.ndarray] = []
        colors: list[np.ndarray] = []
        vus = 0
        for cy in range(y_min, y_max + 1):
            for cx in range(x_min, x_max + 1):
                dx = cx * CHUNK + CHUNK / 2 - camera.pos[0]
                dy = cy * CHUNK + CHUNK / 2 - camera.pos[1]
                distance = math.hypot(dx, dy)
                if distance > dist + CHUNK:
                    continue
                if distance > 1.0:
                    cos_angle = (dx * fwd[0] + dy * fwd[1]) / (distance * longueur)
                    if cos_angle < cos_limite:
                        continue
                v, c = select_mesh(self.meshes, cx, cy, distance, self.detail_radius, self.use_detail)
                if len(v):
                    verts.append(v)
                    colors.append(c)
                    vus += 1
        self.chunks_visibles = vus
        if not verts:
            return np.zeros((0, 4, 3), np.float32), np.zeros(0, np.uint8)
        return np.concatenate(verts), np.concatenate(colors)

    # ------------------------------------------------------------------
    def _draw_front(self, camera, cam, z, colors, devant) -> None:
        if not devant.any():
            return
        c = cam[devant]
        zz = z[devant]
        sx = camera.width / 2 + camera.focal * c[..., 0] / zz
        sy = camera.height / 2 - camera.focal * c[..., 1] / zz
        depth = zz.mean(axis=1)
        cols = colors[devant]

        ordre = np.argsort(-depth)
        sx = sx[ordre].tolist()
        sy = sy[ordre].tolist()
        depth = depth[ordre].tolist()
        cols = cols[ordre].tolist()

        tri = pyxel.tri
        distance_vue = self.view_distance
        for i in range(len(cols)):
            couleur = int(cols[i])
            if self.use_fog:
                couleur = fog_color_index(couleur, fog_factor(depth[i], distance_vue))
            a = sx[i]
            b = sy[i]
            tri(a[0], b[0], a[1], b[1], a[2], b[2], couleur)
            tri(a[0], b[0], a[2], b[2], a[3], b[3], couleur)
        self.quads += len(cols)

    # ------------------------------------------------------------------
    def _draw_clipped(self, camera, cam, z, colors, devant) -> None:
        """Quads à cheval sur le plan proche : découpés puis dessinés."""
        partiels = np.nonzero(~devant & (z > config.NEAR_PLANE).any(axis=1))[0]
        if len(partiels) == 0:
            return
        tri = pyxel.tri
        for i in partiels:
            poly = [tuple(float(v) for v in p) for p in cam[i]]
            poly = clip_near(poly, config.NEAR_PLANE)
            if len(poly) < 3:
                continue
            pts = [
                (
                    camera.width / 2 + camera.focal * p[0] / p[2],
                    camera.height / 2 - camera.focal * p[1] / p[2],
                )
                for p in poly
            ]
            couleur = int(colors[i])
            if self.use_fog:
                profondeur = sum(p[2] for p in poly) / len(poly)
                couleur = fog_color_index(couleur, fog_factor(profondeur, self.view_distance))
            x0, y0 = pts[0]
            for k in range(1, len(pts) - 1):
                tri(x0, y0, pts[k][0], pts[k][1], pts[k + 1][0], pts[k + 1][1], couleur)
            self.quads += 1

    def invalidate(self, x: int, y: int) -> None:
        """Invalidation du cache après modification d'un bloc."""
        self.meshes.invalidate(x, y)

    # ------------------------------------------------------------------
    def _draw_selection(self, camera: Camera, bloc: tuple[int, int, int]) -> None:
        """Contour du bloc visé."""
        for a, b in selection_edges(*bloc):
            pa = camera.project_point(a)
            pb = camera.project_point(b)
            if pa is not None and pb is not None:
                pyxel.line(pa[0], pa[1], pb[0], pb[1], config.SELECTED_COLOR)

    # ------------------------------------------------------------------
    def _draw_sky(self, camera: Camera) -> None:
        hy = camera.horizon_y()
        hy = max(-16.0, min(camera.height + 16.0, hy))
        haut = int(max(0, min(camera.height, hy)))
        bandes = 6
        for i in range(bandes):
            y0 = haut * i // bandes
            y1 = haut * (i + 1) // bandes
            if y1 > y0:
                t = 1.0 - (i + 0.5) / bandes
                pyxel.rect(0, y0, camera.width, y1 - y0, sky_color_at(t))
        if haut < camera.height:
            pyxel.rect(0, haut, camera.width, camera.height - haut, config.FOG_COLOR)
        self._draw_sun(camera)

    def _draw_sun(self, camera: Camera) -> None:
        # Direction fixe du soleil (yaw 60°, élévation 38°), très loin.
        dy = math.radians(60)
        el = math.radians(38)
        direction = np.array(
            [math.cos(el) * math.cos(dy), math.cos(el) * math.sin(dy), math.sin(el)]
        )
        point = camera.pos + direction * 400.0
        proj = camera.project_point(tuple(point))
        if proj is not None:
            x, y, _ = proj
            pyxel.circ(x, y, 10, config.SUN_COLOR)
