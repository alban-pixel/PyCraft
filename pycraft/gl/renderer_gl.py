"""Renderer GPU : terrain, ciel et quantification en palette."""

from __future__ import annotations

import math
from pathlib import Path

import moderngl
import numpy as np

from pycraft import config
from pycraft.camera import Camera
from pycraft.cube import selection_edges
from pycraft.gl.context import GlContext
from pycraft.gl.geometry import GpuMeshes, split_water
from pycraft.gl.math import as_uniform, light_matrix, mvp_matrix
from pycraft.gl.palette import build_lut, install_palette, lut_as_texture
from pycraft.mesher import CHUNK, ChunkMeshes, select_mesh
from pycraft.world import World

_SHADERS = Path(__file__).parent / "shaders"


def _lire(nom: str) -> str:
    return (_SHADERS / nom).read_text(encoding="utf-8")


class GlRenderer:
    """Dessine le monde avec OpenGL et écrit la frame indexée dans Pyxel."""

    def __init__(
        self,
        world: World,
        meshes: ChunkMeshes,
        width: int,
        height: int,
        view_distance: float = config.DEFAULT_VIEW_DISTANCE,
        detail_radius: float = config.DEFAULT_DETAIL_RADIUS,
        gl: GlContext | None = None,
        shadows: bool = True,
    ) -> None:
        self.world = world
        self.meshes = meshes
        self.width = int(width)
        self.height = int(height)
        self.view_distance = float(view_distance)
        self.detail_radius = float(detail_radius)
        self.gl = gl if gl is not None else GlContext(width, height)
        self.shadows = bool(shadows)
        # Soleil derrière la caméra : les ombres tombent vers elle et restent visibles.
        self.sun_dir = np.array([0.45, 0.65, 0.60], dtype=np.float64)
        self.sun_dir /= np.linalg.norm(self.sun_dir)
        self.ctx = self.gl.ctx
        self.gpu = GpuMeshes(self.ctx)
        self.quads = 0
        self.chunks_visibles = 0
        self._light_mvp = np.eye(4, dtype=np.float64)
        self._jour = 1.0
        self._temps = 0.0
        self.rain = 0.0
        self._tint = (1.0, 1.0, 1.0)
        self._ciel_horizon = np.array(config.PALETTE[config.SKY_HORIZON], np.float32) / 255.0
        self._ciel_zenith = np.array(config.PALETTE[config.SKY_TOP], np.float32) / 255.0

        self.palette_size = 16
        try:
            import pyxel

            self.palette_size = install_palette(pyxel)
        except Exception:
            # Pyxel n'est pas initialisé (tests purs) : on garde 16.
            pass

        self._construire_cibles()
        self._construire_programmes()
        self._construire_palette()

    # ------------------------------------------------------------------
    def _construire_cibles(self) -> None:
        self.scene_tex = self.ctx.texture((self.width, self.height), 4)
        self.scene_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.depth = self.ctx.depth_renderbuffer((self.width, self.height))
        self.scene_fbo = self.ctx.framebuffer(
            color_attachments=[self.scene_tex], depth_attachment=self.depth
        )
        # Shadow map en couleur R32F : gl_FragCoord.z est écrit explicitement,
        # ce qui évite les subtilités de sampling des textures de profondeur.
        self.shadow_tex = self.ctx.texture((2048, 2048), 1, dtype="f4")
        self.shadow_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self._shadow_depth = self.ctx.depth_renderbuffer((2048, 2048))
        self.shadow_fbo = self.ctx.framebuffer(
            color_attachments=[self.shadow_tex], depth_attachment=self._shadow_depth
        )

    def _construire_programmes(self) -> None:
        self.sky_prog = self.ctx.program(
            vertex_shader=_lire("sky.vert"),
            fragment_shader=_lire("sky.frag"),
        )
        self.terrain_prog = self.ctx.program(
            vertex_shader=_lire("terrain.vert"),
            fragment_shader=_lire("terrain.frag"),
        )
        self.shadow_prog = self.ctx.program(
            vertex_shader=_lire("shadow.vert"),
            fragment_shader=_lire("shadow.frag"),
        )
        self.water_prog = self.ctx.program(
            vertex_shader=_lire("water.vert"),
            fragment_shader=_lire("water.frag"),
        )
        self.post_prog = self.ctx.program(
            vertex_shader=_lire("post.vert"),
            fragment_shader=_lire("post.frag"),
        )
        self.lignes_prog = self.ctx.program(
            vertex_shader=_lire("lignes.vert"),
            fragment_shader=_lire("lignes.frag"),
        )
        # 12 arêtes × 2 sommets, réécrits à chaque image (24 vec3).
        self._lignes_vbo = self.ctx.buffer(reserve=24 * 3 * 4, dynamic=True)
        self.lignes_vao = self.ctx.vertex_array(
            self.lignes_prog, [(self._lignes_vbo, "3f", "in_pos")]
        )
        plein_ecran = np.array([-1.0, -1.0, 3.0, -1.0, -1.0, 3.0], dtype=np.float32)
        self._ecran_vbo = self.ctx.buffer(plein_ecran.tobytes())
        self.post_vao = self.ctx.vertex_array(self.post_prog, [(self._ecran_vbo, "2f", "in_pos")])
        self.sky_vao = self.ctx.vertex_array(self.sky_prog, [(self._ecran_vbo, "2f", "in_pos")])
        self._vaos: dict[tuple[int, int], object] = {}
        self._shadow_vaos: dict[tuple[int, int], object] = {}
        self._water_vaos: dict[tuple[int, int], object] = {}

    def _construire_palette(self) -> None:
        self.lut = build_lut(bits=5)
        self.lut_tex = self.ctx.texture(
            (1024, 32), 1, lut_as_texture(self.lut).tobytes(), dtype="f1"
        )
        self.lut_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        couleurs = np.array(config.PALETTE, dtype=np.float32) / 255.0
        self.terrain_prog["u_colors"].write(np.ascontiguousarray(couleurs).tobytes())
        materiaux = np.array(config.MATERIALS, dtype=np.int32)
        self.terrain_prog["u_material"].write(np.ascontiguousarray(materiaux).tobytes())

    # ------------------------------------------------------------------
    def _chunks_visibles(self, camera: Camera):
        dist = self.view_distance
        x_min = max(0, int((camera.pos[0] - dist) // CHUNK))
        x_max = min((self.world.sx - 1) // CHUNK, int((camera.pos[0] + dist) // CHUNK))
        y_min = max(0, int((camera.pos[1] - dist) // CHUNK))
        y_max = min((self.world.sy - 1) // CHUNK, int((camera.pos[1] + dist) // CHUNK))
        fwd = camera.fwd
        longueur = math.hypot(fwd[0], fwd[1]) or 1.0
        cos_limite = math.cos(math.radians(camera.fov_deg / 2 + 14))
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
                yield cx, cy, distance

    # ------------------------------------------------------------------
    def draw(self, camera: Camera, selection=None, time: float = 0.0) -> None:
        self._temps = time
        self._rendre_scene(camera, time, selection)
        self._post_traitement()
        self.gl.blit_to_pyxel()

    def _rendre_scene(
        self, camera: Camera, time: float = 0.0, selection=None
    ) -> None:
        ciel = np.array(config.PALETTE[config.SKY_HORIZON], dtype=np.float32) / 255.0
        self.scene_fbo.use()
        self.scene_fbo.clear(float(ciel[0]), float(ciel[1]), float(ciel[2]), 1.0)
        self._dessiner_ciel(camera, time)
        if self.shadows:
            self._dessiner_ombres(camera)
        self.scene_fbo.use()
        self.ctx.enable(moderngl.DEPTH_TEST)

        prog = self.terrain_prog
        prog["u_mvp"].write(as_uniform(mvp_matrix(camera)))
        prog["u_sun"].value = tuple(float(v) for v in self.sun_dir)
        prog["u_camera"].value = tuple(float(v) for v in camera.pos)
        prog["u_sky"].value = tuple(float(v) for v in ciel)
        prog["u_fog_start"].value = self.view_distance * 0.65
        prog["u_fog_end"].value = self.view_distance
        prog["u_shadow_on"].value = 1.0 if self.shadows else 0.0
        prog["u_daylight"].value = 0.35 + 0.65 * self._jour
        prog["u_light_mvp"].write(as_uniform(self._light_mvp))
        self.shadow_tex.use(2)
        prog["u_shadow"].value = 2

        self.quads = 0
        vus = 0
        self._eau: list[tuple[int, int]] = []
        for cx, cy, distance in self._chunks_visibles(camera):
            verts, colors = select_mesh(
                self.meshes, cx, cy, distance, self.detail_radius, True
            )
            if len(verts) == 0:
                continue
            opaques_v, opaques_c, eau_v, eau_c = split_water(verts, colors)
            if len(opaques_v):
                vbo, nombre = self.gpu.get(cx, cy, opaques_v, opaques_c, "opaque")
                vao = self._vaos.get((cx, cy))
                if vao is None:
                    vao = self.ctx.vertex_array(
                        prog,
                        [(vbo, "3f 3f 1f 1f", "in_pos", "in_normal", "in_color", "in_ao")],
                    )
                    self._vaos[(cx, cy)] = vao
                vao.render()
                self.quads += nombre // 6
                vus += 1
            if len(eau_v):
                vbo_eau, nombre_eau = self.gpu.get(cx, cy, eau_v, eau_c, "water")
                self._eau.append((cx, cy, vbo_eau, nombre_eau))
        self.chunks_visibles = vus
        self._dessiner_eau(camera, time)
        self._dessiner_contour(camera, selection)

    def _dessiner_eau(self, camera: Camera, time: float) -> None:
        if not self._eau:
            return
        prog = self.water_prog
        prog["u_mvp"].write(as_uniform(mvp_matrix(camera)))
        prog["u_time"].value = float(time)
        prog["u_camera"].value = tuple(float(v) for v in camera.pos)
        eau = np.array(config.PALETTE[config.BLOCK_COLORS[config.Block.WATER][0]], dtype=np.float32) / 255.0
        ciel = np.array(config.PALETTE[config.SKY_HORIZON], dtype=np.float32) / 255.0
        prog["u_water"].value = tuple(float(v) for v in eau)
        prog["u_sky"].value = tuple(float(v) for v in ciel)
        self.ctx.depth_mask = False
        for cx, cy, vbo, nombre in self._eau:
            vao = self._water_vaos.get((cx, cy))
            if vao is None:
                vao = self.ctx.vertex_array(
                    prog, [(vbo, "3f 3f 1x4 1f", "in_pos", "in_normal", "in_ao")]
                )
                self._water_vaos[(cx, cy)] = vao
            vao.render()
            self.quads += nombre // 6
        self.ctx.depth_mask = True

    def _dessiner_contour(self, camera: Camera, selection) -> None:
        """Contour du bloc visé : 12 arêtes, comme le renderer CPU."""
        if selection is None:
            return
        edges = selection_edges(*selection)
        verts = np.array([p for edge in edges for p in edge], dtype=np.float32)
        self._lignes_vbo.write(verts.tobytes())
        prog = self.lignes_prog
        prog["u_mvp"].write(as_uniform(mvp_matrix(camera)))
        prog["u_res"].value = (float(self.width), float(self.height))
        couleur = np.array(config.PALETTE[config.SELECTED_COLOR], dtype=np.float32) / 255.0
        prog["u_color"].value = tuple(float(v) for v in couleur)
        # glLineWidth > 1 n'est pas garanti (cœur de profil) : on épaissit en
        # décalant le trait d'un pixel, ce qui donne un contour de 2 px.
        for dx in (0.0, 1.0):
            for dy in (0.0, 1.0):
                prog["u_offset"].value = (dx, dy)
                self.lignes_vao.render(moderngl.LINES)

    def _dessiner_ombres(self, camera: Camera) -> None:
        cible = camera.pos + camera.fwd * 20.0
        self._light_mvp = light_matrix(cible, self.sun_dir)
        self.shadow_fbo.use()
        self.shadow_fbo.clear(1.0, 0.0, 0.0, 1.0)
        self.ctx.enable(moderngl.DEPTH_TEST)
        prog = self.shadow_prog
        prog["u_light_mvp"].write(as_uniform(self._light_mvp))
        for cx, cy, distance in self._chunks_visibles(camera):
            verts, colors = select_mesh(self.meshes, cx, cy, distance, self.detail_radius, True)
            if len(verts) == 0:
                continue
            vbo, _ = self.gpu.get(cx, cy, verts, colors)
            vao = self._shadow_vaos.get((cx, cy))
            if vao is None:
                vao = self.ctx.vertex_array(
                    prog, [(vbo, "3f 3x4 1x4 1x4", "in_pos")]
                )
                self._shadow_vaos[(cx, cy)] = vao
            vao.render()

    @staticmethod
    def daylight(time: float) -> float:
        """0 = nuit, 1 = plein jour (période de 120 s)."""
        return max(0.0, min(1.0, 0.5 + 0.55 * math.sin(time * math.pi / 60.0)))

    def _ambiance(self, time: float) -> None:
        jour = self.daylight(time)
        self._jour = jour
        jour_h = np.array(config.PALETTE[config.SKY_HORIZON], dtype=np.float32) / 255.0
        jour_z = np.array(config.PALETTE[config.SKY_TOP], dtype=np.float32) / 255.0
        nuit_h = np.array([0.05, 0.07, 0.16], dtype=np.float32)
        nuit_z = np.array([0.01, 0.02, 0.06], dtype=np.float32)
        self._ciel_horizon = nuit_h + (jour_h - nuit_h) * jour
        self._ciel_zenith = nuit_z + (jour_z - nuit_z) * jour
        tint = np.array([0.55, 0.62, 0.90], dtype=np.float32)
        self._tint = tint + (np.ones(3, dtype=np.float32) - tint) * jour

    def _dessiner_ciel(self, camera: Camera, time: float) -> None:
        self.ctx.disable(moderngl.DEPTH_TEST)
        prog = self.sky_prog
        prog["u_right"].value = tuple(float(v) for v in camera.right)
        prog["u_up"].value = tuple(float(v) for v in camera.up)
        prog["u_fwd"].value = tuple(float(v) for v in camera.fwd)
        prog["u_res"].value = (float(self.width), float(self.height))
        prog["u_focal"].value = float(camera.focal)
        prog["u_sun"].value = tuple(float(v) for v in self.sun_dir)
        self._ambiance(time)
        prog["u_horizon"].value = tuple(float(v) for v in self._ciel_horizon)
        prog["u_zenith"].value = tuple(float(v) for v in self._ciel_zenith)
        prog["u_time"].value = float(time)
        prog["u_night"].value = float(1.0 - self._jour)
        self.sky_vao.render()

    def _post_traitement(self) -> None:
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.gl.fbo.use()
        self.scene_tex.use(0)
        self.lut_tex.use(1)
        self.post_prog["u_scene"].value = 0
        self.post_prog["u_lut"].value = 1
        self.post_prog["u_tint"].value = tuple(float(v) for v in self._tint)
        self.post_prog["u_vignette"].value = 0.55
        self.post_prog["u_rain"].value = float(self.rain)
        self.post_prog["u_time"].value = float(self._temps)
        self.post_vao.render()

    def invalidate(self, x: int, y: int) -> None:
        self.gpu.invalidate(x, y)
        for vao in self._vaos.values():
            vao.release()
        for vao in self._shadow_vaos.values():
            vao.release()
        for vao in self._water_vaos.values():
            vao.release()
        self._water_vaos.clear()
        self._vaos.clear()
        self._shadow_vaos.clear()

    def close(self) -> None:
        for vao in self._vaos.values():
            vao.release()
        for vao in self._shadow_vaos.values():
            vao.release()
        for vao in self._water_vaos.values():
            vao.release()
        self._water_vaos.clear()
        self._vaos.clear()
        self._shadow_vaos.clear()
        self.post_vao.release()
        self.sky_vao.release()
        self.lignes_vao.release()
        self._lignes_vbo.release()
        self.lignes_prog.release()
        self.gpu.release()
        self.lut_tex.release()
        self.scene_tex.release()
        self.depth.release()
        self.scene_fbo.release()
        self._ecran_vbo.release()
        self.terrain_prog.release()
        self.sky_prog.release()
        self.water_prog.release()
        self.post_prog.release()
        self.gl.close()
