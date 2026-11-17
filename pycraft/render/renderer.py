"""The Renderer: draws a frame of the world with the other parts of the package, from the sky to
the palette, and copies it into Pyxel's screen."""

import math
import time

import moderngl
import numpy as np

from pycraft.render import shaders
from pycraft.blocks import BLOCK_TILES
from pycraft.lod import SamplerProcess
from pycraft.render.chunks import Chunks
from pycraft.render.constants import (ATLAS_UNIT, BLOCK_TILES_UNIT, CLOUDS_UNIT, CLOUD_HEIGHT, CLOUD_PERIOD,
                                      CLOUD_WIND, FAR_LIMIT, LOD_QUALITIES, LOD_QUALITY_NAMES, MSAA_SAMPLES,
                                      SHADOW_UNITS, SIM_DISTANCES, TILE_AVG_UNIT, TINT_UNIT)
from pycraft.render.far import FarTerrain
from pycraft.render.gl import depth_half, look_at, matrix_bytes, perspective, set_uniforms
from pycraft.render.palette import Palette
from pycraft.render.shadows import Shadows
from pycraft.render.textures import cloud_texture, make_tile_textures
from pycraft.shapes import selection_box
from pycraft.terrain import CHUNK


CUBE_EDGES = [(0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
class Renderer:
    def __init__(self, ctx, world, tiles, width, height, fixed_colors, fov=70):
        """ctx must be created before pyxel.init, so Pyxel's own OpenGL context ends up current.
        fixed_colors: the first 64 colors of the palette (0xRRGGBB), which never change."""
        self.ctx = ctx
        self.fov = fov
        self.size = None
        self.render_scale = 1.0  # share of the screen's width and height the 3D view is drawn at
        self.gpu_time = None  # seconds the graphics card spent on the last frame (None if it can't tell)
        self.fbos = []
        self.render_distance = 256  # how far the world is seen, in chunks (blocks, then coarser and coarser)
        self.fancy = True  # shadows and anti-aliasing
        self.drawn = 0  # block columns drawn in the last frame
        self.dim = 1.0  # darker behind the menus
        self.underwater = False
        self.start = time.perf_counter()
        # Light and sky, changed by the game every frame (see set_environment)
        self.environment = {
            "light_dir": (0.0, 1.0, 0.0), "light_color": (0.6, 0.6, 0.6), "sky_light": (0.55, 0.6, 0.65),
            "zenith": (0.38, 0.6, 1.0), "horizon": (0.68, 0.84, 1.0), "sun_dir": (0.0, 1.0, 0.0),
            "sun_glow": (0.0, 0.0, 0.0), "night": 0.0, "cloud_cover": 0.56,
            "fog_color": (0.68, 0.84, 1.0), "fog_density": 1 / 7000, "fog_start": 6000.0, "fog_end": 8000.0,
        }
        fixed = np.array([[(c >> 16) & 255, (c >> 8) & 255, c & 255] for c in fixed_colors])
        with self.ctx:
            self.program = ctx.program(vertex_shader=shaders.BLOCK_VERTEX_SHADER,
                                       fragment_shader=shaders.BLOCK_FRAGMENT_SHADER)
            self.lod_program = ctx.program(vertex_shader=shaders.LOD_VERTEX_SHADER,
                                           fragment_shader=shaders.LOD_FRAGMENT_SHADER)
            self.sky_program = ctx.program(vertex_shader=shaders.FULLSCREEN_VERTEX_SHADER,
                                           fragment_shader=shaders.SKY_FRAGMENT_SHADER)
            self.cloud_program = ctx.program(vertex_shader=shaders.CLOUD_VERTEX_SHADER,
                                             fragment_shader=shaders.CLOUD_FRAGMENT_SHADER)
            self.outline_program = ctx.program(
                vertex_shader=shaders.OUTLINE_VERTEX_SHADER, fragment_shader=shaders.OUTLINE_FRAGMENT_SHADER)
            self.post_program = ctx.program(vertex_shader=shaders.FULLSCREEN_VERTEX_SHADER,
                                            fragment_shader=shaders.POST_FRAGMENT_SHADER)
            self.texture, self.tint_texture = make_tile_textures(ctx, tiles)
            # The atlas tile of each face (x) of each block (y), for the distant terrain's shader
            self.block_tiles = ctx.texture((6, len(BLOCK_TILES)), 1, np.asarray(BLOCK_TILES, "u2").tobytes(),
                                           dtype="u2")
            self.block_tiles.filter = (moderngl.NEAREST, moderngl.NEAREST)
            self.lod_program["block_tiles"] = BLOCK_TILES_UNIT
            self.clouds = ctx.texture((512, 512), 1, cloud_texture().tobytes(), dtype="f4")
            self.clouds.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
            self.clouds.build_mipmaps()
            quad = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4").tobytes())
            self.sky_vao = ctx.vertex_array(self.sky_program, [(quad, "2f", "in_pos")])
            self.cloud_vao = ctx.vertex_array(self.cloud_program, [(quad, "2f", "in_pos")])
            self.post_vao = ctx.vertex_array(self.post_program, [(quad, "2f", "in_pos")])
            self.outline_vbo = ctx.buffer(reserve=24 * 3 * 4)
            self.outline_vao = ctx.vertex_array(self.outline_program, [(self.outline_vbo, "3f", "in_pos")])
            self.sampler = SamplerProcess()  # makes the distant terrain's texels, in its own process
            self.chunks = Chunks(ctx, self.program, world, self.sampler.shared)
            self.far = FarTerrain(ctx, self.lod_program, world, self.texture, self.tint_texture, tiles, self.sampler,
                                  *LOD_QUALITIES[LOD_QUALITY_NAMES[0]])
            self.shadows = Shadows(ctx, self.texture, self.tint_texture)
            self.palette = Palette(ctx, fixed)
            self.palette.apply()
            try:  # measures how long the graphics card takes to draw a frame
                self.timer = ctx.query(time=True)
            except moderngl.Error:
                self.timer = None
            for p in (self.program, self.lod_program, self.cloud_program):
                set_uniforms(p, {"atlas": ATLAS_UNIT, "tint_mask": TINT_UNIT, "clouds": CLOUDS_UNIT, "tile_avg": TILE_AVG_UNIT,
                                 "shadow_near": SHADOW_UNITS[0],
                                 "shadow_mid": SHADOW_UNITS[1], "shadow_far": SHADOW_UNITS[2]})
        self.world = world
        self.resize(width, height)

    def resize(self, width, height):
        """Draw frames of a new size (when the resolution setting changes)."""
        self.size = (width, height)
        self.make_framebuffers()

    @property
    def scene_size(self):
        """Size the 3D view is drawn at, before it is scaled up to the screen's size."""
        width, height = self.size
        return max(1, round(width * self.render_scale)), max(1, round(height * self.render_scale))

    def set_render_scale(self, scale):
        """Draw the 3D view at this share of the screen's width and height (0.5-1): fewer pixels to
        draw, scaled up afterward. The palette and the dithering stay at the screen's size."""
        scale = min(max(float(scale), 0.25), 1.0)
        if scale != self.render_scale:
            self.render_scale = scale
            self.make_framebuffers()

    def set_fancy(self, fancy):
        """Shadows and anti-aliasing on or off."""
        if fancy != self.fancy:
            self.fancy = fancy
            self.make_framebuffers()

    def set_lod_quality(self, quality):
        """The LOD quality setting: rebuild the distant terrain at another resolution."""
        spacing, size, levels = LOD_QUALITIES[quality]
        far = self.far
        if (spacing, size, levels) == (far.spacing, far.size, far.n_levels):
            return
        self._rebuild_far(far.tiles, spacing, size, levels)

    def _rebuild_far(self, tiles, spacing=None, size=None, levels=None):
        """Make the distant terrain again: at another resolution, or from other tiles (their
        averages and flat colors, which go to the sampler too). The resolution stays if not given."""
        far = self.far
        spacing = far.spacing if spacing is None else spacing
        size = far.size if size is None else size
        levels = far.n_levels if levels is None else levels
        with self.ctx:
            self.far = FarTerrain(self.ctx, self.lod_program, self.world, self.texture, self.tint_texture,
                                  tiles, self.sampler, spacing, size, levels)
            self.far.version = far.version + 1  # the shadow maps are drawn again
            for res in far.data_maps + far.color_maps + [far.tile_avg, far.vbo, far.ibo, far.vao]:
                res.release()

    def set_tiles(self, tiles):
        """Draw with other tiles (256, N, N, 4) (a texture pack): new textures for the blocks, the
        distant terrain and the shadows. The meshes stay: they only hold tile numbers."""
        old = (self.texture, self.tint_texture)
        with self.ctx:
            self.texture, self.tint_texture = make_tile_textures(self.ctx, tiles)
            self.shadows.atlas, self.shadows.tint = self.texture, self.tint_texture
        self._rebuild_far(tiles)
        with self.ctx:
            for tex in old:
                tex.release()

    def make_framebuffers(self):
        ctx = self.ctx
        with ctx:
            for obj in self.fbos:
                for part in (*obj.color_attachments, obj.depth_attachment, obj):
                    if part is not None:
                        part.release()
            # The frame in full color (with several samples per pixel for anti-aliasing), the same
            # frame with one color per pixel, and the palette indices read back for Pyxel. The
            # first two are smaller with a render scale under 1.
            width, height = self.scene_size
            samples = MSAA_SAMPLES if self.fancy else 0
            self.scene_texture = ctx.texture((width, height), 4, dtype="f2")
            self.scene_texture.filter = (moderngl.LINEAR, moderngl.LINEAR)  # (read between texels when scaled up)
            self.scene_texture.repeat_x = self.scene_texture.repeat_y = False
            self.resolved_fbo = ctx.framebuffer(color_attachments=[self.scene_texture])
            if samples:
                self.scene_fbo = ctx.framebuffer(
                    color_attachments=[ctx.renderbuffer((width, height), 4, samples=samples, dtype="f2")],
                    depth_attachment=ctx.depth_renderbuffer((width, height), samples=samples))
                self.fbos = [self.scene_fbo, self.resolved_fbo]
            else:
                self.scene_fbo = ctx.framebuffer(color_attachments=[self.scene_texture],
                                                 depth_attachment=ctx.depth_renderbuffer((width, height)))
                self.fbos = [self.scene_fbo]
            width, height = self.size
            self.index_texture = ctx.texture((width, height), 1, dtype="f1")
            self.index_fbo = ctx.framebuffer(color_attachments=[self.index_texture])
            self.fbos.append(self.index_fbo)

    def set_world(self, world):
        """Use another world (after loading or generating one)."""
        self.world = world
        with self.ctx:
            self.chunks.set_world(world)
            self.far.set_world(world)

    def set_environment(self, **values):
        """Light, sky and fog: light_dir, light_color, sky_light, zenith, horizon, sun_dir, sun_glow,
        night, cloud_cover, fog_color, fog_density, fog_start, fog_end."""
        self.environment.update(values)

    def update(self, cam, budget):
        """Upload the block meshes built near the camera (for up to `budget` seconds) and refresh the
        distant terrain around it."""
        with self.ctx:
            self.chunks.radius = self.sim_distance
            self.far.view_distance = self.view_distance
            self.far.update(cam)
            self.chunks.update(cam, budget)

    @property
    def sim_distance(self):
        """Radius, in chunks, of the columns drawn as real blocks: grows with the render distance,
        but slowly (meshing them is the costly part); the coarser terrain takes over beyond."""
        return SIM_DISTANCES.get(self.render_distance, 12)

    @property
    def view_distance(self):
        """Where the fog has hidden everything, in blocks."""
        return min(self.render_distance * CHUNK, FAR_LIMIT)

    def progress(self, cam, radius=3):
        """Share of the world around the camera that is ready to be seen (for the loading screen):
        the blocks within radius chunks for one half, the distant terrain for the other."""
        return 0.5 * self.chunks.progress(cam, radius) + 0.5 * self.far.progress()

    def block_changed(self, x, y, z):
        with self.ctx:
            self.chunks.block_changed(x, y, z)
            self.far.block_changed(x, y, z)

    def blocks_changed(self, positions):
        """Many blocks changed at once (the machines of a frame): each section is meshed once."""
        if not positions:
            return
        with self.ctx:
            self.chunks.blocks_changed(positions)
            for x, y, z in positions:
                self.far.block_changed(x, y, z)

    def render(self, screen, eye, forward, target=None):
        """Draw the world seen from eye into screen (a (height, width) uint8 view of pyxel.screen).
        Afterward, self.palette.colors is the palette the frame was drawn for."""
        width, height = self.size
        aspect = width / height
        view = look_at((0, 0, 0), forward)
        far_vp = perspective(self.fov, aspect, 1.0, 30000) @ view
        near_vp = perspective(self.fov, aspect, 0.05, 6000) @ view
        cam = tuple(float(c) for c in eye)
        now = time.perf_counter() - self.start
        env = self.environment
        wind = (cam[0] + CLOUD_WIND[0] * now, cam[2] + CLOUD_WIND[1] * now)
        values = dict(env)
        values.update({
            "time": now % 3600.0,
            "wave_origin": (cam[0] % 256.0, cam[2] % 256.0),
            "cloud_origin": ((wind[0] / CLOUD_PERIOD) % 1.0, (wind[1] / CLOUD_PERIOD) % 1.0),
            "cloud_height": CLOUD_HEIGHT - cam[1],
            "shadows_on": int(self.fancy),
            "sky_fog": 1.0 if self.underwater else 0.0,
        })
        # The blocks give way to the distant terrain between these distances: from half-way to the
        # edge of the columns drawn as blocks (a chunk short of it, wherever the camera is in its chunk)
        fade_end = (self.sim_distance - 1) * CHUNK
        self.far.block_reach = float((self.sim_distance + 3) * CHUNK)  # (past the corner of the farthest mesh)
        cell = (math.floor(cam[0] / 2), math.floor(cam[2] / 2))
        values.update({
            "block_fade": (0.5 * fade_end, float(fade_end)), "cam_cell": cell,
            "cam_in_cell": (float(cam[0] - 2 * cell[0]), float(cam[2] - 2 * cell[1])),
            "cam_frac": (float(cam[0] % 256.0), float(cam[2] % 256.0)), "cam_x": float(cam[0]),
            "px_per_block": self.scene_size[1] / (2 * math.tan(math.radians(self.fov) / 2)),
        })
        self.far.view_distance = self.view_distance
        finish = {"dim": float(self.dim), "tint": (0.75, 0.9, 1.0) if self.underwater else (1.0, 1.0, 1.0)}
        # Every OpenGL call, setting shader values included, must happen inside `with self.ctx`:
        # outside it, Pyxel's own context is the current one (with a window; not in headless tests)
        with self.ctx:
            if self.timer is not None:
                with self.timer:
                    adapt = self.draw_frame(values, finish, far_vp, near_vp, cam, target)
            else:
                adapt = self.draw_frame(values, finish, far_vp, near_vp, cam, target)
            # Straight into Pyxel's screen: the last shader drew the rows top-down, in Pyxel's order
            # (reading into a new array, then flipping it into the screen, took 2 ms more a frame
            # at 2560x1440)
            self.index_fbo.read_into(screen, components=1, dtype="f1")
            if adapt:
                self.palette.adapt()  # for the next frame: this one was drawn for the current palette
            # (read after the frame: the graphics card has finished it)
            self.gpu_time = self.timer.elapsed / 1e9 if self.timer is not None else None

    def draw_frame(self, values, finish, far_vp, near_vp, cam, target):
        """The OpenGL work of render(): the frame in palette indices into self.index_fbo. Returns
        whether the palette sampled it (to adapt once the frame is read back)."""
        ctx = self.ctx
        env = self.environment
        self.palette.apply()
        self.block_tiles.use(BLOCK_TILES_UNIT)  # (the shadow maps draw the distant terrain too)
        if self.chunks.ready_changed:
            self.chunks.ready_texture.write(self.chunks.ready.tobytes())
            self.chunks.ready_changed = False
        if self.fancy:
            values.update(self.shadows.update(cam, env["light_dir"], self.chunks, self.far, self.program,
                                              self.lod_program))
            self.shadows.use()
        for p in (self.program, self.lod_program, self.sky_program, self.cloud_program):
            set_uniforms(p, values)
        self.clouds.use(CLOUDS_UNIT)
        fbo = self.scene_fbo
        fbo.use()
        fbo.clear(depth=1.0)

        ctx.disable(moderngl.DEPTH_TEST)
        self.sky_program["inv_vp"].write(matrix_bytes(np.linalg.inv(far_vp)))
        self.sky_vao.render(moderngl.TRIANGLE_STRIP)

        # The blocks first, then the distant terrain and the far clouds behind them: the blocks
        # take the nearer half of the depth buffer and the distant terrain the farther half, so
        # each keeps the precision of its own projection, and the distant terrain costs nothing
        # where the blocks hide it (it is drawn whole under the blocks that give way to it)
        near_draw, far_draw = depth_half(near_vp, False), depth_half(far_vp, True)
        ctx.enable(moderngl.DEPTH_TEST)
        self.texture.use(ATLAS_UNIT)
        self.tint_texture.use(TINT_UNIT)
        self.far.tile_avg.use(TILE_AVG_UNIT)
        self.program["vp"].write(matrix_bytes(near_draw))
        self.program["mode"] = 0
        self.drawn = self.chunks.find_in_view(near_vp, cam)
        self.chunks.render()
        self.far.render(far_draw, cam, self.chunks)
        near_radius = (self.sim_distance + 2) * CHUNK
        self.render_clouds(far_draw, near_radius, near_pass=False)

        # The blocks' water, see-through, over all of that; then the clouds nearby
        self.texture.use(ATLAS_UNIT)
        self.tint_texture.use(TINT_UNIT)
        self.far.tile_avg.use(TILE_AVG_UNIT)
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        fbo.depth_mask = False
        fbo.use()
        self.program["mode"] = 1
        self.chunks.render(water=True)
        ctx.disable(moderngl.BLEND)
        fbo.depth_mask = True
        fbo.use()
        self.render_clouds(near_draw, near_radius, near_pass=True)

        if target:
            lo, hi = selection_box(self.world.get(*target), self.world.get_state(*target))  # (a lever: its box)
            corners = np.array([(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
            mid = (np.array(lo) + np.array(hi)) / 2
            corners = (corners - mid) * 1.004 + mid + np.array(target) - np.array(cam)
            lines = corners[np.array(CUBE_EDGES).ravel()]
            self.outline_vbo.write(lines.astype("f4").tobytes())
            self.outline_program["vp"].write(matrix_bytes(near_draw))
            self.outline_vao.render(moderngl.LINES)

        # Down to one color per pixel, then to Pyxel's palette
        ctx.disable(moderngl.DEPTH_TEST)
        if fbo is not self.resolved_fbo:
            ctx.copy_framebuffer(self.resolved_fbo, fbo)
        self.scene_texture.use(0)
        self.palette.texture.use(1)
        self.palette.lut.use(2)
        set_uniforms(self.post_program, {"scene": 0, "palette": 1, "lut": 2,
                                         "out_size": tuple(map(float, self.size)), **finish})
        self.index_fbo.use()
        self.post_vao.render(moderngl.TRIANGLE_STRIP)
        adapt = self.palette.wants_samples()
        if adapt:
            self.palette.sample(self.scene_texture, finish)
        return adapt

    def render_clouds(self, vp, near_radius, near_pass):
        ctx = self.ctx
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        fbo = self.scene_fbo
        fbo.depth_mask = False
        fbo.use()
        set_uniforms(self.cloud_program, {"near_pass": int(near_pass), "near_radius": float(near_radius)})
        self.cloud_program["vp"].write(matrix_bytes(vp))
        self.cloud_vao.render(moderngl.TRIANGLE_STRIP)
        fbo.depth_mask = True
        fbo.use()
        ctx.disable(moderngl.BLEND)
