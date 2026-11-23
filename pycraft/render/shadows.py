"""The three shadow maps: the blocks around the camera, the distant terrain within 1 km, and up to
8 km. A map is drawn again only when what it shows changed."""

import math
import time

import moderngl
import numpy as np

from pycraft.render.constants import (ATLAS_UNIT, SHADOW_DEPTH, SHADOW_EVERY, SHADOW_SIZE, SHADOW_UNITS,
                                      TERRAIN_SHADOW_HALF, TINT_UNIT)
from pycraft.render.gl import matrix_bytes
from pycraft.terrain import CHUNK


class ShadowMap:
    """How one shadow map was drawn: the light's direction and the map's square, fixed in the world
    (so it can be used as the camera moves, until it is drawn again)."""

    def __init__(self, light, half, cam, key, version, size=SHADOW_SIZE):
        self.key, self.version, self.half, self.cam = key, version, half, cam
        self.time = time.perf_counter()  # when it was drawn
        # Axes of the light's view: right, up, and toward the light
        helper = np.array([0.0, 0.0, 1.0]) if abs(light[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        right = np.cross(helper, light)
        right /= np.linalg.norm(right)
        self.rotation = np.array([right, np.cross(light, right), light])
        # The square's center: the camera, snapped to whole texels so the shadows' edges stay still
        texel = 2 * half / size
        center = self.rotation @ np.array(cam, dtype=np.float64)
        center[:2] = np.round(center[:2] / texel) * texel
        self.center = center

    def matrix(self, cam, to_texture=False):
        """Position relative to the camera -> clip space of the map (or 0-1 texture coordinates)."""
        r, half = self.rotation, self.half
        offset = r @ np.array(cam, dtype=np.float64) - self.center
        m = np.zeros((4, 4))
        m[0, :3], m[0, 3] = r[0] / half, offset[0] / half
        m[1, :3], m[1, 3] = r[1] / half, offset[1] / half
        m[2, :3], m[2, 3] = -r[2] / SHADOW_DEPTH, -offset[2] / SHADOW_DEPTH  # nearer the light: smaller depth
        m[3, 3] = 1.0
        if to_texture:
            m[:3] = 0.5 * m[:3] + 0.5 * m[3]
        return m
class Shadows:
    """Three shadow maps, seen from the light: the blocks around the camera, the terrain within
    1 km, and the terrain up to 8 km. A map is drawn again only when what it shows changed: the
    light moved a little (its direction is rounded), the camera went far from the map's center, or
    the meshes or the distant terrain changed."""

    def __init__(self, ctx, atlas, tint, size=SHADOW_SIZE):
        """size: texels per side of each map (bigger for a screenshot)."""
        self.ctx, self.atlas, self.tint, self.size = ctx, atlas, tint, size
        self.textures, self.fbos = [], []
        for _ in range(3):
            tex = ctx.depth_texture((size, size))
            tex.compare_func = "<="  # lookups return 1 where the point is no farther from the light
            tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            tex.repeat_x = tex.repeat_y = False
            self.textures.append(tex)
            self.fbos.append(ctx.framebuffer(depth_attachment=tex))
        # Bound in their place while they are drawn: a texture being drawn must not be bound for reading
        self.placeholder = ctx.depth_texture((1, 1))
        self.placeholder.compare_func = "<="
        self.maps = [None, None, None]

    def update(self, cam, light_dir, chunks, far, block_program, lod_program):
        """Draw the maps that need it; return the uniforms that look them up."""
        key = tuple(int(v) for v in np.round(np.array(light_dir) * 300))  # steps of about 0.2 degrees
        light = np.array(key, dtype=np.float64)
        light /= np.linalg.norm(light)
        halves = ((chunks.radius + 1.5) * CHUNK, *TERRAIN_SHADOW_HALF)
        versions = (chunks.version, far.version, far.version)
        now = time.perf_counter()
        for i in range(3):
            old = self.maps[i]
            if (old is not None and old.key == key and old.half == halves[i]
                    and math.hypot(cam[0] - old.cam[0], cam[2] - old.cam[2]) < 0.15 * halves[i]
                    and abs(cam[1] - old.cam[1]) < 0.5 * SHADOW_DEPTH
                    and (old.version == versions[i] or now - old.time < SHADOW_EVERY[i])):
                continue
            if i > 0 and far.drawn_levels(cam)[1] < 0:
                continue  # (no level of the distant terrain has landed yet)
            new = ShadowMap(light, halves[i], cam, key, versions[i], self.size)
            self.maps[i] = new
            self.draw(i, new.matrix(cam), cam, chunks, far, block_program, lod_program)
        values = {"shadow_texel": tuple(2 * h / self.size for h in halves)}
        outside = np.zeros((4, 4))
        outside[:, 3] = (-1.0, -1.0, -1.0, 1.0)  # before a map is first drawn, its lookups land outside it
        for i, m in enumerate(self.maps):
            values[f"shadow_vp{i}"] = m.matrix(cam, True) if m else outside
        return values

    def draw(self, i, vp, cam, chunks, far, block_program, lod_program):
        ctx = self.ctx
        for unit in SHADOW_UNITS:
            self.placeholder.use(unit)
        self.fbos[i].use()
        self.fbos[i].clear(depth=1.0)
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.polygon_offset = (2.0, 4.0)  # a little farther from the light: surfaces don't shadow themselves
        if i == 0:
            self.atlas.use(ATLAS_UNIT)  # leaves let light through their holes
            self.tint.use(TINT_UNIT)  # (read by the blocks' shader, which also draws the shadows)
            block_program["mode"] = 2
            block_program["vp"].write(matrix_bytes(vp))
            chunks.render_shadow(cam)
        else:
            far.render(vp, cam, chunks, shadow=True)
        ctx.polygon_offset = (0.0, 0.0)

    def release(self):
        for obj in (*self.fbos, *self.textures, self.placeholder):
            obj.release()

    def use(self):
        for tex, unit in zip(self.textures, SHADOW_UNITS):
            tex.use(unit)
