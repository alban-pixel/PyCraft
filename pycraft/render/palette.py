"""Pyxel's 256 colors: 64 that never change (the interface and the block icons) and 192 that
follow what is on screen, and the dithering between them."""

import math

import moderngl
import numpy as np

from pycraft.render import shaders
from pycraft.lod import oklab_to_srgb, srgb_to_oklab
from pycraft.render.constants import ADAPT_EVERY, FIXED_COLORS, MIX_PENALTY, SAMPLES
from pycraft.render.gl import set_uniforms


class Palette:
    """Pyxel's 256 colors. The first 64 never change: Pyxel's 16 (the HUD) and 48 for the block
    icons. The other 192 follow what's on screen: every other frame a few thousand pixels are
    sampled, each goes to its nearest palette color (on the graphics card), and each color moves
    toward the average of its pixels. A color no pixel uses goes to split the busiest one in two."""

    def __init__(self, ctx, fixed_colors):
        self.ctx = ctx
        rgb = np.zeros((256, 3))
        rgb[:FIXED_COLORS] = np.asarray(fixed_colors, dtype=np.float64) / 255
        # Start from an even spread of colors (they adapt within a second)
        levels = np.linspace(0.0, 1.0, 6)
        cube = np.stack(np.meshgrid(levels, levels, levels, indexing="ij"), axis=-1).reshape(-1, 3)
        rgb[FIXED_COLORS:] = cube[np.linspace(0, len(cube) - 1, 256 - FIXED_COLORS).astype(int)]
        self.lab = srgb_to_oklab(rgb)
        self.adaptive = np.arange(256) >= FIXED_COLORS
        self.sums = np.zeros((256, 4))  # running totals of the samples of each color (decaying)
        self.squares = np.zeros((256, 4))
        self.unused = np.zeros(256, int)  # adjustments in a row each color had no samples
        self.pending = True
        self.version = 0
        self.colors = []  # the palette of the last frame drawn, as 0xRRGGBB for pyxel.colors
        self.frame = 0
        self.texture = ctx.texture((256, 1), 4, dtype="f4")
        self.texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.lut = ctx.texture((32 * 8, 32 * 4), 2, dtype="u1")
        self.lut.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.lut_fbo = ctx.framebuffer(color_attachments=[self.lut])
        self.samples = ctx.texture((SAMPLES, SAMPLES), 4, dtype="f4")
        self.samples.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.samples_fbo = ctx.framebuffer(color_attachments=[self.samples])
        self.totals = [ctx.texture((256, 1), 4, dtype="f4") for _ in range(2)]
        self.totals_fbo = ctx.framebuffer(color_attachments=self.totals)
        quad = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4").tobytes())
        self.lut_program = ctx.program(vertex_shader=shaders.FULLSCREEN_VERTEX_SHADER,
                                       fragment_shader=shaders.LUT_FRAGMENT_SHADER)
        self.lut_vao = ctx.vertex_array(self.lut_program, [(quad, "2f", "in_pos")])
        self.sample_program = ctx.program(vertex_shader=shaders.FULLSCREEN_VERTEX_SHADER,
                                          fragment_shader=shaders.SAMPLE_FRAGMENT_SHADER)
        self.sample_vao = ctx.vertex_array(self.sample_program, [(quad, "2f", "in_pos")])
        self.accumulate_program = ctx.program(vertex_shader=shaders.ACCUMULATE_VERTEX_SHADER,
                                              fragment_shader=shaders.ACCUMULATE_FRAGMENT_SHADER)
        self.accumulate_vao = ctx.vertex_array(self.accumulate_program, [])

    def set_fixed(self, colors):
        """New colors (0xRRGGBB) for the block icons, palette entries 16 to FIXED_COLORS - 1 (a new
        texture pack): taken at the next apply()."""
        rgb = np.array([[(c >> 16) & 255, (c >> 8) & 255, c & 255] for c in colors], np.float64) / 255
        self.lab[16:FIXED_COLORS] = srgb_to_oklab(rgb)
        self.pending = True

    def apply(self):
        """Upload the palette if it changed, and work out again the dithering pairs."""
        if not self.pending:
            return
        self.pending = False
        rgb8 = np.rint(oklab_to_srgb(self.lab) * 255).astype(np.uint8)
        shown = srgb_to_oklab(rgb8 / 255)  # the colors as they will really look
        self.lab[self.adaptive] = shown[self.adaptive]  # keeps the adaptive colors inside what can be shown
        self.texture.write(np.concatenate([shown, np.ones((256, 1))], axis=1).astype("f4").tobytes())
        self.texture.use(0)
        self.lut_program["palette"] = 0
        self.lut_program["mix_penalty"] = MIX_PENALTY
        self.lut_fbo.use()
        self.lut_vao.render(moderngl.TRIANGLE_STRIP)
        self.colors = [int(r) << 16 | int(g) << 8 | int(b) for r, g, b in rgb8]
        self.version += 1

    def wants_samples(self):
        self.frame += 1
        return self.frame % ADAPT_EVERY == 0

    def sample(self, scene, finish):
        """Sample the frame and add up the samples of each palette color (on the graphics card)."""
        ctx = self.ctx
        scene.use(0)
        set_uniforms(self.sample_program, {"scene": 0, "frame": self.frame % 100000, **finish})
        self.samples_fbo.use()
        self.sample_vao.render(moderngl.TRIANGLE_STRIP)
        self.samples.use(0)
        self.texture.use(1)
        set_uniforms(self.accumulate_program, {"samples": 0, "palette": 1})
        self.totals_fbo.use()
        self.totals_fbo.clear(0.0, 0.0, 0.0, 0.0)
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.ONE, moderngl.ONE
        self.accumulate_vao.render(moderngl.POINTS, vertices=SAMPLES * SAMPLES)
        ctx.disable(moderngl.BLEND)

    def adapt(self):
        """Move the adaptive colors toward their samples (one step of k-means)."""
        sums = np.frombuffer(self.totals[0].read(), "f4").reshape(256, 4).astype(np.float64)
        squares = np.frombuffer(self.totals[1].read(), "f4").reshape(256, 4).astype(np.float64)
        # Totals that decay over a few steps: steadier than one frame's samples, so the palette
        # stays still when the view does
        self.sums = 0.6 * self.sums + sums
        self.squares = 0.6 * self.squares + squares
        count = self.sums[:, 3]
        used = count > 0.5
        self.unused = np.where(sums[:, 3] > 0, 0, self.unused + 1)
        mean = np.where(used[:, None], self.sums[:, :3] / np.maximum(count, 1e-9)[:, None], self.lab)
        lab = self.lab.copy()
        move = self.adaptive & used
        lab[move] += 0.7 * (mean[move] - lab[move])
        # Colors unused for a while: each splits the color whose samples are farthest from it
        error = self.squares[:, 3].copy()
        split = False
        for dead in np.nonzero(self.adaptive & (self.unused >= 6))[0][:4]:
            j = int(np.argmax(error))
            if count[j] < 2 or error[j] < 1e-4:
                break
            spread = np.maximum(self.squares[j, :3] / count[j] - mean[j] ** 2, 0.0)
            axis = int(np.argmax(spread))
            offset = np.zeros(3)
            offset[axis] = 0.7 * math.sqrt(spread[axis]) + 0.002
            lab[dead] = mean[j] + offset
            if self.adaptive[j]:
                lab[j] = mean[j] - offset
            error[j] = 0.0
            self.unused[dead] = 0
            self.sums[[dead, j]] = 0.0
            self.squares[[dead, j]] = 0.0
            split = True
        if split or np.abs(lab - self.lab).max() > 0.004:
            self.lab = lab
            self.pending = True
