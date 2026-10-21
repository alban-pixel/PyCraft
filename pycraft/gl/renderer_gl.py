"""Renderer GPU : terrain, ciel et quantification en palette."""

from __future__ import annotations

import math
from pathlib import Path

import moderngl
import numpy as np

from pycraft import config
from pycraft.camera import Camera
from pycraft.gl.context import GlContext
from pycraft.gl.geometry import GpuMeshes
from pycraft.gl.math import as_uniform, mvp_matrix
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
    ) -> None:
        self.world = world
        self.meshes = meshes
        self.width = int(width)
        self.height = int(height)
        self.view_distance = float(view_distance)
        self.detail_radius = float(detail_radius)
        self.gl = gl if gl is not None else GlContext(width, height)
        self.ctx = self.gl.ctx
        self.gpu = GpuMeshes(self.ctx)
        self.quads = 0
        self.chunks_visibles = 0

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

    def _construire_programmes(self) -> None:
        self.sky_prog = self.ctx.program(
            vertex_shader=_lire("sky.vert"),
            fragment_shader=_lire("sky.frag"),
        )
        self.terrain_prog = self.ctx.program(
            vertex_shader=_lire("terrain.vert"),
            fragment_shader=_lire("terrain.frag"),
        )
        self.post_prog = self.ctx.program(
            vertex_shader=_lire("post.vert"),
            fragment_shader=_lire("post.frag"),
        )
        plein_ecran = np.array([-1.0, -1.0, 3.0, -1.0, -1.0, 3.0], dtype=np.float32)
        self._ecran_vbo = self.ctx.buffer(plein_ecran.tobytes())
        self.post_vao = self.ctx.vertex_array(self.post_prog, [(self._ecran_vbo, "2f", "in_pos")])
        self.sky_vao = self.ctx.vertex_array(self.sky_prog, [(self._ecran_vbo, "2f", "in_pos")])
        self._vaos: dict[tuple[int, int], object] = {}

    def _construire_palette(self) -> None:
        self.lut = build_lut(bits=5)
        self.lut_tex = self.ctx.texture(
            (1024, 32), 1, lut_as_texture(self.lut).tobytes(), dtype="f1"
        )
        self.lut_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        couleurs = np.array(config.PALETTE, dtype=np.float32) / 255.0
        self.terrain_prog["u_colors"].write(np.ascontiguousarray(couleurs).tobytes())

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
        self._rendre_scene(camera, time)
        self._post_traitement()
        self.gl.blit_to_pyxel()

    def _rendre_scene(self, camera: Camera, time: float = 0.0) -> None:
        ciel = np.array(config.PALETTE[config.SKY_HORIZON], dtype=np.float32) / 255.0
        self.scene_fbo.use()
        self.scene_fbo.clear(float(ciel[0]), float(ciel[1]), float(ciel[2]), 1.0)
        self._dessiner_ciel(camera, time)
        self.ctx.enable(moderngl.DEPTH_TEST)

        prog = self.terrain_prog
        prog["u_mvp"].write(as_uniform(mvp_matrix(camera)))
        soleil = np.array([0.45, 0.65, 0.60], dtype=np.float32)
        soleil /= np.linalg.norm(soleil)
        prog["u_sun"].value = tuple(float(v) for v in soleil)
        prog["u_camera"].value = tuple(float(v) for v in camera.pos)
        prog["u_sky"].value = tuple(float(v) for v in ciel)
        prog["u_fog_start"].value = self.view_distance * 0.65
        prog["u_fog_end"].value = self.view_distance

        self.quads = 0
        vus = 0
        for cx, cy, distance in self._chunks_visibles(camera):
            verts, colors = select_mesh(
                self.meshes, cx, cy, distance, self.detail_radius, True
            )
            if len(verts) == 0:
                continue
            vbo, nombre = self.gpu.get(cx, cy, verts, colors)
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
        self.chunks_visibles = vus

    def _dessiner_ciel(self, camera: Camera, time: float) -> None:
        self.ctx.disable(moderngl.DEPTH_TEST)
        prog = self.sky_prog
        prog["u_right"].value = tuple(float(v) for v in camera.right)
        prog["u_up"].value = tuple(float(v) for v in camera.up)
        prog["u_fwd"].value = tuple(float(v) for v in camera.fwd)
        prog["u_res"].value = (float(self.width), float(self.height))
        prog["u_focal"].value = float(camera.focal)
        soleil = np.array([0.45, 0.65, 0.60], dtype=np.float32)
        soleil /= np.linalg.norm(soleil)
        prog["u_sun"].value = tuple(float(v) for v in soleil)
        hor = np.array(config.PALETTE[config.SKY_HORIZON], dtype=np.float32) / 255.0
        zen = np.array(config.PALETTE[config.SKY_TOP], dtype=np.float32) / 255.0
        prog["u_horizon"].value = tuple(float(v) for v in hor)
        prog["u_zenith"].value = tuple(float(v) for v in zen)
        prog["u_time"].value = float(time)
        prog["u_night"].value = 0.0
        self.sky_vao.render()

    def _post_traitement(self) -> None:
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.gl.fbo.use()
        self.scene_tex.use(0)
        self.lut_tex.use(1)
        self.post_prog["u_scene"].value = 0
        self.post_prog["u_lut"].value = 1
        self.post_vao.render()

    def invalidate(self, x: int, y: int) -> None:
        self.gpu.invalidate(x, y)
        for vao in self._vaos.values():
            vao.release()
        self._vaos.clear()

    def close(self) -> None:
        for vao in self._vaos.values():
            vao.release()
        self._vaos.clear()
        self.post_vao.release()
        self.sky_vao.release()
        self.gpu.release()
        self.lut_tex.release()
        self.scene_tex.release()
        self.depth.release()
        self.scene_fbo.release()
        self._ecran_vbo.release()
        self.terrain_prog.release()
        self.sky_prog.release()
        self.post_prog.release()
        self.gl.close()
