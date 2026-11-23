"""The screenshot's frames added up on the graphics card, in full float precision, then their
average finished like the game's frame (finish()) and read back in full color, without the palette."""

import moderngl
import numpy as np

from pycraft.render import shaders
from pycraft.render.gl import set_uniforms


class Accumulator:
    def __init__(self, ctx, size):
        self.ctx, self.size, self.count = ctx, tuple(size), 0
        quad = np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4").tobytes()
        self.sum = ctx.texture(self.size, 4, dtype="f4")
        self.sum_fbo = ctx.framebuffer(color_attachments=[self.sum])
        self.sum_fbo.clear(0.0, 0.0, 0.0, 0.0)
        self.out = ctx.texture(self.size, 4, dtype="f1")
        self.out_fbo = ctx.framebuffer(color_attachments=[self.out])
        self.add_program = ctx.program(vertex_shader=shaders.FULLSCREEN_VERTEX_SHADER,
                                       fragment_shader=shaders.ACCUMULATE_SCENE_FRAGMENT_SHADER)
        self.resolve_program = ctx.program(vertex_shader=shaders.FULLSCREEN_VERTEX_SHADER,
                                           fragment_shader=shaders.RESOLVE_FRAGMENT_SHADER)
        self.quad = ctx.buffer(quad)
        self.add_vao = ctx.vertex_array(self.add_program, [(self.quad, "2f", "in_pos")])
        self.resolve_vao = ctx.vertex_array(self.resolve_program, [(self.quad, "2f", "in_pos")])

    def add(self, scene):
        """Add a frame (a texture of the same size) to the sum."""
        ctx = self.ctx
        ctx.disable(moderngl.DEPTH_TEST)
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.ONE, moderngl.ONE
        self.sum_fbo.use()
        scene.use(0)
        set_uniforms(self.add_program, {"scene": 0})
        self.add_vao.render(moderngl.TRIANGLE_STRIP)
        ctx.disable(moderngl.BLEND)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.count += 1

    def resolve(self, dim, tint):
        """The average of the frames added, finished: (height, width, 3) uint8, top row first."""
        ctx = self.ctx
        ctx.disable(moderngl.DEPTH_TEST)
        ctx.disable(moderngl.BLEND)
        self.out_fbo.use()
        self.sum.use(0)
        set_uniforms(self.resolve_program, {"sum": 0, "count": float(max(self.count, 1)), "dim": float(dim),
                                            "tint": tuple(map(float, tint))})
        self.resolve_vao.render(moderngl.TRIANGLE_STRIP)
        width, height = self.size
        data = np.frombuffer(self.out_fbo.read(components=4, dtype="f1"), np.uint8)
        return data.reshape(height, width, 4)[..., :3].copy()

    def release(self):
        for obj in (self.add_vao, self.resolve_vao, self.quad, self.add_program, self.resolve_program,
                    self.sum_fbo, self.sum, self.out_fbo, self.out):
            obj.release()
