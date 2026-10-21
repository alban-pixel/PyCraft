"""GPU renderer: draws the world with OpenGL (moderngl) off-screen, then copies the frame into Pyxel's screen.

The shaders output Pyxel palette indices directly (one byte per pixel), so the frame can be copied
into pyxel.screen with no conversion on the CPU. Transparency is done by "dithering": leaves and glass
skip their see-through texels, and water skips every other pixel in a checkerboard.
"""
import math

import moderngl
import numpy as np

from blocks import ATLAS_TILES, BLOCK_TILES, CUTOUT, OPAQUE, SELF_CULL, WATER

CHUNK = 16
OUTLINE_INDEX = 0  # Pyxel black
WATER_SURFACE = 0.875  # water blocks are a bit lower than a full block

# Palette layout set up in main.py: 0-15 Pyxel's default colors, 16-231 a 6x6x6 RGB cube.
# Shared by the shaders: ordered dithering, then snap each channel to one of the cube's 6 levels.
TO_PALETTE = """
const float bayer[16] = float[](0., 8., 2., 10., 12., 4., 14., 6., 3., 11., 1., 9., 15., 7., 13., 5.);
float to_palette(vec3 color) {
    ivec2 p = ivec2(gl_FragCoord.xy) % 4;
    float threshold = (bayer[p.y * 4 + p.x] + 0.5) / 16.0;
    ivec3 level = ivec3(clamp(floor(color * 5.0 + threshold), 0.0, 5.0));
    return float(16 + level.r * 36 + level.g * 6 + level.b) / 255.0;
}
"""

BLOCK_VERTEX_SHADER = """
#version 330
uniform mat4 mvp;
uniform vec3 cam;
in vec3 in_pos;
in vec2 in_uv;
in float in_shade;
in float in_kind;
out vec2 v_uv;
out float v_shade;
out float v_dist;
flat out int v_kind;
void main() {
    gl_Position = mvp * vec4(in_pos, 1.0);
    v_uv = in_uv;
    v_shade = in_shade;
    v_dist = distance(in_pos, cam);
    v_kind = int(in_kind + 0.5);
}
"""

BLOCK_FRAGMENT_SHADER = """
#version 330
uniform sampler2D atlas;
uniform float light;
uniform vec3 fog_color;
uniform float fog_start;
uniform float fog_end;
in vec2 v_uv;
in float v_shade;
in float v_dist;
flat in int v_kind;
out float index;
""" + TO_PALETTE + """
void main() {
    vec4 tex = texture(atlas, v_uv);
    if (v_kind == 1 && tex.a < 0.5) discard;  // see-through texel (leaves, glass)
    if (v_kind == 2 && ((int(gl_FragCoord.x) + int(gl_FragCoord.y)) & 1) == 0) discard;  // water
    vec3 color = tex.rgb * v_shade * light;
    float fog = clamp((v_dist - fog_start) / (fog_end - fog_start), 0.0, 1.0);
    index = to_palette(mix(color, fog_color, fog));
}
"""

SKY_VERTEX_SHADER = """
#version 330
in vec2 in_pos;
out vec2 v_ndc;
void main() { gl_Position = vec4(in_pos, 0.0, 1.0); v_ndc = in_pos; }
"""

SKY_FRAGMENT_SHADER = """
#version 330
uniform mat4 inv_vp;
uniform vec3 zenith;
uniform vec3 horizon;
uniform vec3 sun_dir;
in vec2 v_ndc;
out float index;
""" + TO_PALETTE + """
void main() {
    vec4 far = inv_vp * vec4(v_ndc, 1.0, 1.0);
    vec4 near = inv_vp * vec4(v_ndc, -1.0, 1.0);
    vec3 dir = normalize(far.xyz / far.w - near.xyz / near.w);
    vec3 color = mix(horizon, zenith, clamp(dir.y * 1.6, 0.0, 1.0));
    // Square sun and moon, like Minecraft's
    vec3 side = normalize(cross(sun_dir, vec3(0.0, 0.0, 1.0)));
    vec3 up = cross(side, sun_dir);
    if (dot(dir, sun_dir) > 0.0 && max(abs(dot(dir, side)), abs(dot(dir, up))) < 0.04)
        color = vec3(1.0, 0.95, 0.6);
    if (dot(dir, -sun_dir) > 0.0 && max(abs(dot(dir, side)), abs(dot(dir, up))) < 0.03)
        color = vec3(0.85, 0.85, 0.95);
    index = to_palette(color);
}
"""

OUTLINE_VERTEX_SHADER = """
#version 330
uniform mat4 mvp;
in vec3 in_pos;
void main() { gl_Position = mvp * vec4(in_pos, 1.0); }
"""

OUTLINE_FRAGMENT_SHADER = f"""
#version 330
out float index;
void main() {{ index = {OUTLINE_INDEX}.0 / 255.0; }}
"""

# For each face direction (+x, -x, +y, -y, +z, -z): neighbor offset, 4 corners, brightness
FACES = [
    ((1, 0, 0), [(1, 1, 0), (1, 1, 1), (1, 0, 1), (1, 0, 0)], 0.8),
    ((-1, 0, 0), [(0, 1, 1), (0, 1, 0), (0, 0, 0), (0, 0, 1)], 0.8),
    ((0, 1, 0), [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)], 1.0),
    ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], 0.5),
    ((0, 0, 1), [(1, 1, 1), (0, 1, 1), (0, 0, 1), (1, 0, 1)], 0.65),
    ((0, 0, -1), [(0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 0)], 0.65),
]
CORNER_UV = np.array([(0, 0), (1, 0), (1, 1), (0, 1)], dtype=np.float32)
TRIANGLES = [0, 1, 2, 0, 2, 3]
UV_INSET = 0.5 / 16  # half a texel, in tile units, so neighbor tiles never bleed in

CUBE_EDGES = [(0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4), (0, 4), (1, 5), (2, 6), (3, 7)]


def perspective(fov, aspect, near, far):
    f = 1 / math.tan(math.radians(fov) / 2)
    return np.array([
        [f / aspect, 0, 0, 0],
        [0, f, 0, 0],
        [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)],
        [0, 0, -1, 0],
    ], dtype="f4")


def look_at(eye, forward):
    eye = np.array(eye, dtype="f4")
    fw = np.array(forward, dtype="f4")
    fw /= np.linalg.norm(fw)
    right = np.cross(fw, [0, 1, 0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fw)
    m = np.identity(4, dtype="f4")
    m[0, :3], m[1, :3], m[2, :3] = right, up, -fw
    m[:3, 3] = -m[:3, :3] @ eye
    return m


class Renderer:
    def __init__(self, ctx, world, atlas, width, height, fov=70):
        """ctx must be created before pyxel.init, so Pyxel's own OpenGL context ends up current."""
        self.ctx = ctx
        self.size = (width, height)
        self.projection = perspective(fov, width / height, 0.05, 300)
        self.chunks = {}
        # Lighting and sky, changed by the game every frame (see set_environment)
        self.light = 1.0
        self.zenith = self.horizon = (0.6, 0.8, 1.0)
        self.sun_dir = (0.0, 1.0, 0.0)
        self.fog = (self.horizon, 40.0, 90.0)
        with self.ctx:
            self.program = ctx.program(vertex_shader=BLOCK_VERTEX_SHADER, fragment_shader=BLOCK_FRAGMENT_SHADER)
            self.sky_program = ctx.program(vertex_shader=SKY_VERTEX_SHADER, fragment_shader=SKY_FRAGMENT_SHADER)
            self.outline_program = ctx.program(
                vertex_shader=OUTLINE_VERTEX_SHADER, fragment_shader=OUTLINE_FRAGMENT_SHADER)
            self.texture = ctx.texture((atlas.shape[1], atlas.shape[0]), 4, atlas.tobytes())
            self.texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
            self.program["atlas"] = 0
            color = ctx.texture((width, height), 1, dtype="f1")
            depth = ctx.depth_renderbuffer((width, height))
            self.fbo = ctx.framebuffer(color_attachments=[color], depth_attachment=depth)
            sky_quad = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4").tobytes())
            self.sky_vao = ctx.vertex_array(self.sky_program, [(sky_quad, "2f", "in_pos")])
            self.outline_vbo = ctx.buffer(reserve=24 * 3 * 4)
            self.outline_vao = ctx.vertex_array(self.outline_program, [(self.outline_vbo, "3f", "in_pos")])
        self.set_world(world)

    def set_world(self, world):
        """Use a new world (after loading or generating one) and build all of its chunks."""
        self.world = world
        sx, _, sz = world.size
        with self.ctx:
            for chunk in self.chunks.values():
                if chunk:
                    chunk[0].release()
                    chunk[1].release()
            self.chunks = {}
            for cx in range(math.ceil(sx / CHUNK)):
                for cz in range(math.ceil(sz / CHUNK)):
                    self._build_chunk(cx, cz)

    def set_environment(self, light, zenith, horizon, sun_dir, fog_color, fog_start, fog_end):
        self.light = light
        self.zenith, self.horizon, self.sun_dir = zenith, horizon, sun_dir
        self.fog = (fog_color, fog_start, fog_end)

    def block_changed(self, x, z):
        """Rebuild the chunk holding (x, z), and its neighbor when the block sits on a chunk border."""
        cx, cz = x // CHUNK, z // CHUNK
        todo = {(cx, cz)}
        if x % CHUNK == 0:
            todo.add((cx - 1, cz))
        if x % CHUNK == CHUNK - 1:
            todo.add((cx + 1, cz))
        if z % CHUNK == 0:
            todo.add((cx, cz - 1))
        if z % CHUNK == CHUNK - 1:
            todo.add((cx, cz + 1))
        with self.ctx:
            for key in todo:
                if key in self.chunks:
                    self._build_chunk(*key)

    def _build_chunk(self, cx, cz):
        """Build the triangles for every visible block face in the chunk (NumPy, no Python loops)."""
        x0, z0 = cx * CHUNK, cz * CHUNK
        # Region of the padded array: the chunk plus a 1-block border of neighbors
        region = self.world.blocks[x0:x0 + CHUNK + 2, :, z0:z0 + CHUNK + 2]
        core = region[1:-1, 1:-1, 1:-1]
        nx, ny, nz = core.shape
        water_above = region[1:-1, 2:, 1:-1] == WATER
        parts = []
        for face, ((dx, dy, dz), corners, shade) in enumerate(FACES):
            neighbor = region[1 + dx:1 + dx + nx, 1 + dy:1 + dy + ny, 1 + dz:1 + dz + nz]
            # A face shows when its neighbor doesn't hide it: not opaque, and not the same glass/water
            visible = (core != 0) & ~OPAQUE[neighbor] & ~((core == neighbor) & SELF_CULL[core])
            i, j, k = np.nonzero(visible)
            if i.size == 0:
                continue
            blocks = core[i, j, k]
            base = np.stack([i + x0, j, k + z0], axis=1).astype(np.float32)
            pos = base[:, None, :] + np.array(corners, dtype=np.float32)[None]  # (n, 4, 3)
            # Lower the top of water blocks that have no water above them
            low = (blocks == WATER) & ~water_above[i, j, k]
            top_corner = np.array(corners)[:, 1] == 1
            pos[low[:, None] & top_corner[None], 1] -= 1 - WATER_SURFACE
            tile = BLOCK_TILES[blocks, face]
            tile_xy = np.stack([tile % ATLAS_TILES, tile // ATLAS_TILES], axis=1).astype(np.float32)
            uv = (tile_xy[:, None, :] + UV_INSET + CORNER_UV[None] * (1 - 2 * UV_INSET)) / ATLAS_TILES
            kind = np.where(blocks == WATER, 2.0, np.where(CUTOUT[blocks], 1.0, 0.0)).astype(np.float32)
            extra = np.stack([np.full(i.size, shade, dtype=np.float32), kind], axis=1)
            extra = np.broadcast_to(extra[:, None, :], (i.size, 4, 2))
            verts = np.concatenate([pos, uv, extra], axis=2)[:, TRIANGLES]  # (n, 6, 7)
            parts.append(verts.reshape(-1, 7))

        old = self.chunks.pop((cx, cz), None)
        if old:
            old[0].release()
            old[1].release()
        if not parts:
            self.chunks[(cx, cz)] = None
            return
        data = np.concatenate(parts).astype("f4")
        vbo = self.ctx.buffer(data.tobytes())
        vao = self.ctx.vertex_array(
            self.program, [(vbo, "3f 2f 1f 1f", "in_pos", "in_uv", "in_shade", "in_kind")])
        self.chunks[(cx, cz)] = (vbo, vao)

    def render(self, screen, eye, forward, target=None):
        """Draw the world seen from eye into screen (a (height, width) uint8 view of pyxel.screen)."""
        vp = self.projection @ look_at(eye, forward)
        mvp = vp.T.copy().tobytes()
        fog_color, fog_start, fog_end = self.fog
        with self.ctx:
            self.fbo.use()
            self.fbo.clear(depth=1.0)

            self.ctx.disable(moderngl.DEPTH_TEST)
            self.sky_program["inv_vp"].write(np.linalg.inv(vp).T.astype("f4").tobytes())
            self.sky_program["zenith"] = self.zenith
            self.sky_program["horizon"] = self.horizon
            self.sky_program["sun_dir"] = self.sun_dir
            self.sky_vao.render(moderngl.TRIANGLE_STRIP)

            self.ctx.enable(moderngl.DEPTH_TEST)
            self.texture.use(0)
            self.program["mvp"].write(mvp)
            self.program["cam"] = tuple(eye)
            self.program["light"] = self.light
            self.program["fog_color"] = fog_color
            self.program["fog_start"] = fog_start
            self.program["fog_end"] = fog_end
            for chunk in self.chunks.values():
                if chunk:
                    chunk[1].render()

            if target:
                corners = np.array([(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype="f4")
                corners = (corners - 0.5) * 1.004 + 0.5 + np.array(target, dtype="f4")
                lines = corners[np.array(CUBE_EDGES).ravel()]
                self.outline_vbo.write(lines.astype("f4").tobytes())
                self.outline_program["mvp"].write(mvp)
                self.outline_vao.render(moderngl.LINES)
            frame = np.frombuffer(self.fbo.read(components=1, dtype="f1"), dtype=np.uint8)
        width, height = self.size
        screen[:, :] = frame.reshape(height, width)[::-1]  # OpenGL rows go bottom-up
