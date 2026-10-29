"""GPU renderer: draws the world with OpenGL (moderngl) off-screen, then copies the frame into Pyxel's screen.

The shaders output Pyxel palette indices directly (one byte per pixel), so the frame can be copied
into pyxel.screen with no conversion on the CPU. Transparency is done by "dithering": leaves and glass
skip their see-through texels, and water skips every other pixel in a checkerboard.
"""
import math

import moderngl
import numpy as np

from blocks import (
    ATLAS_TILES, BLOCK_TILES, CUTOUT, OPAQUE, SELF_CULL, WATER,
    T_CRACK_0, T_DIRT, T_PIG_BODY, T_PIG_FACE, T_ZOMBIE_BODY, T_ZOMBIE_FACE,
)

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
        self.fov = fov
        self.fbo = None
        self._frame_buf = None
        self.chunks = {}
        self.chunk_centers = {}
        self.chunk_radius = 0.0
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
            sky_quad = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4").tobytes())
            self.sky_vao = ctx.vertex_array(self.sky_program, [(sky_quad, "2f", "in_pos")])
            self.outline_vbo = ctx.buffer(reserve=24 * 3 * 4)
            self.outline_vao = ctx.vertex_array(self.outline_program, [(self.outline_vbo, "3f", "in_pos")])
            self.entity_vbo = ctx.buffer(reserve=256 * 1024)  # 256KB for dynamic mobs
            self.entity_vao = ctx.vertex_array(
                self.program, [(self.entity_vbo, "3f 2f 1f 1f", "in_pos", "in_uv", "in_shade", "in_kind")]
            )
            self.crack_vbo = ctx.buffer(reserve=36 * 7 * 4)
            self.crack_vao = ctx.vertex_array(
                self.program, [(self.crack_vbo, "3f 2f 1f 1f", "in_pos", "in_uv", "in_shade", "in_kind")]
            )
        self.resize(width, height)
        self.set_world(world)

    def resize(self, width, height):
        """Draw frames of a new size (when the resolution setting changes)."""
        self.size = (width, height)
        self.projection = perspective(self.fov, width / height, 0.05, 300)
        with self.ctx:
            if self.fbo:
                for obj in (*self.fbo.color_attachments, self.fbo.depth_attachment, self.fbo):
                    obj.release()
            color = self.ctx.texture((width, height), 1, dtype="f1")
            depth = self.ctx.depth_renderbuffer((width, height))
            self.fbo = self.ctx.framebuffer(color_attachments=[color], depth_attachment=depth)
            self._frame_buf = bytearray(width * height)

    def set_fov(self, fov):
        self.fov = fov
        width, height = self.size
        self.projection = perspective(self.fov, width / height, 0.05, 300)

    def set_world(self, world, spawn_pos=None, render_dist=4):
        """Use a new world (after loading or generating one) and build all of its chunks."""
        self.world = world
        sx, sy, sz = world.size
        self.chunk_radius = math.hypot(CHUNK / 2, sy / 2, CHUNK / 2)
        with self.ctx:
            for chunk in self.chunks.values():
                if chunk:
                    chunk[0].release()
                    chunk[1].release()
            self.chunks = {}
            self.chunk_centers = {}

            if getattr(world, "infinite", False):
                sp_x = spawn_pos[0] if spawn_pos else sx / 2
                sp_z = spawn_pos[2] if spawn_pos else sz / 2
                pcx = int(math.floor(sp_x / CHUNK))
                pcz = int(math.floor(sp_z / CHUNK))
                r = render_dist
                for dcx in range(-r, r + 1):
                    for dcz in range(-r, r + 1):
                        if dcx * dcx + dcz * dcz <= (r + 0.5) ** 2:
                            cx, cz = pcx + dcx, pcz + dcz
                            self.chunk_centers[(cx, cz)] = (cx * CHUNK + CHUNK / 2, sy / 2, cz * CHUNK + CHUNK / 2)
                            self._build_chunk(cx, cz)
            else:
                for cx in range(math.ceil(sx / CHUNK)):
                    for cz in range(math.ceil(sz / CHUNK)):
                        self.chunk_centers[(cx, cz)] = (cx * CHUNK + CHUNK / 2, sy / 2, cz * CHUNK + CHUNK / 2)
                        self._build_chunk(cx, cz)

    def update_streaming(self, player_x, player_z, render_dist=4):
        """Dynamically stream chunks around the player position."""
        if not getattr(self.world, "infinite", False):
            return

        pcx = int(math.floor(player_x / CHUNK))
        pcz = int(math.floor(player_z / CHUNK))
        sy = getattr(self.world, "sy", 64)

        needed = set()
        r2 = (render_dist + 0.5) ** 2
        for dcx in range(-render_dist, render_dist + 1):
            for dcz in range(-render_dist, render_dist + 1):
                if dcx * dcx + dcz * dcz <= r2:
                    needed.add((pcx + dcx, pcz + dcz))

        built_count = 0
        with self.ctx:
            for key in needed:
                if key not in self.chunks:
                    cx, cz = key
                    self.chunk_centers[key] = (cx * CHUNK + CHUNK / 2, sy / 2, cz * CHUNK + CHUNK / 2)
                    self._build_chunk(cx, cz)
                    built_count += 1
                    if built_count >= 2:
                        break

            unload_dist = render_dist + 2
            unload_r2 = unload_dist * unload_dist
            to_remove = []
            for (cx, cz), chunk in self.chunks.items():
                dcx = cx - pcx
                dcz = cz - pcz
                if dcx * dcx + dcz * dcz > unload_r2:
                    to_remove.append((cx, cz))

            for key in to_remove:
                chunk = self.chunks.pop(key, None)
                if chunk:
                    chunk[0].release()
                    chunk[1].release()
                self.chunk_centers.pop(key, None)

    def set_environment(self, light, zenith, horizon, sun_dir, fog_color, fog_start, fog_end):
        self.light = light
        self.zenith, self.horizon, self.sun_dir = zenith, horizon, sun_dir
        self.fog = (fog_color, fog_start, fog_end)

    def rebuild_chunks(self, chunk_coords):
        """Rebuild specified chunks in a single context without re-evaluating unmodified borders."""
        with self.ctx:
            for cx, cz in chunk_coords:
                if (cx, cz) in self.chunks:
                    self._build_chunk(cx, cz)

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
        if hasattr(self.world, "get_mesh_region"):
            region = self.world.get_mesh_region(cx, cz)
        else:
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

    @staticmethod
    def _frustum_planes(vp):
        """Extract the 6 normalized clipping planes (A, B, C, D) from the view-projection matrix."""
        rows = [
            vp[3] + vp[0],  # Left
            vp[3] - vp[0],  # Right
            vp[3] + vp[1],  # Bottom
            vp[3] - vp[1],  # Top
            vp[3] + vp[2],  # Near
            vp[3] - vp[2],  # Far
        ]
        planes = []
        for p in rows:
            norm = float(np.linalg.norm(p[:3]))
            planes.append(p / norm if norm > 1e-7 else p)
        return planes

    def _chunk_in_frustum(self, planes, cx, cz):
        """True if the chunk bounding sphere is inside or intersects the view frustum."""
        center = self.chunk_centers.get((cx, cz))
        if center is None:
            return True
        cx0, cy0, cz0 = center
        r = self.chunk_radius
        for pl in planes:
            if pl[0] * cx0 + pl[1] * cy0 + pl[2] * cz0 + pl[3] < -r:
                return False
        return True

    @staticmethod
    def _make_box_verts(pos, size, yaw_deg, tile_faces, kind=0.0, shade_mult=1.0):
        sx, sy, sz = size
        yaw = math.radians(yaw_deg)
        cos_y, sin_y = math.cos(yaw), math.sin(yaw)
        tiles = [tile_faces] * 6 if isinstance(tile_faces, int) else tile_faces
        parts = []

        for face_idx, ((dx, dy, dz), corners, shade) in enumerate(FACES):
            tile_num = tiles[face_idx]
            ty, tx = divmod(tile_num, ATLAS_TILES)
            corner_uv = (np.array([tx, ty], dtype=np.float32) + UV_INSET + CORNER_UV * (1 - 2 * UV_INSET)) / ATLAS_TILES

            c_arr = (np.array(corners, dtype=np.float32) - 0.5) * np.array([sx, sy, sz], dtype=np.float32)
            rx = c_arr[:, 0] * cos_y + c_arr[:, 2] * sin_y
            rz = -c_arr[:, 0] * sin_y + c_arr[:, 2] * cos_y
            ry = c_arr[:, 1]
            p = np.stack([rx + pos[0], ry + pos[1], rz + pos[2]], axis=1)

            f_p = p[TRIANGLES]
            f_uv = corner_uv[TRIANGLES]
            f_sh = np.full((6, 1), shade * shade_mult, dtype=np.float32)
            f_kd = np.full((6, 1), kind, dtype=np.float32)
            parts.append(np.concatenate([f_p, f_uv, f_sh, f_kd], axis=1))
        return np.concatenate(parts, axis=0)

    def _build_entities_mesh(self, entities, alpha: float = 0.0):
        if not entities:
            return None, 0
        boxes = []
        for ent in entities:
            if hasattr(ent, "prev_pos") and ent.prev_pos is not None:
                x = (1.0 - alpha) * ent.prev_pos[0] + alpha * ent.pos[0]
                y = (1.0 - alpha) * ent.prev_pos[1] + alpha * ent.pos[1]
                z = (1.0 - alpha) * ent.prev_pos[2] + alpha * ent.pos[2]
            else:
                x, y, z = ent.pos
            yaw = ent.yaw
            shade_mult = 1.8 if ent.hurt_timer > 0 else 1.0

            if ent.kind == "zombie":
                # Head
                boxes.append(self._make_box_verts((x, y + 1.55, z), (0.45, 0.45, 0.45), yaw, T_ZOMBIE_FACE, shade_mult=shade_mult))
                # Torso
                boxes.append(self._make_box_verts((x, y + 0.95, z), (0.5, 0.75, 0.28), yaw, T_ZOMBIE_BODY, shade_mult=shade_mult))
                # Extended arms (forward)
                yaw_rad = math.radians(yaw)
                cos_y, sin_y = math.cos(yaw_rad), math.sin(yaw_rad)
                ra_x = x + 0.32 * cos_y + 0.3 * sin_y
                ra_z = z - 0.32 * sin_y + 0.3 * cos_y
                la_x = x - 0.32 * cos_y + 0.3 * sin_y
                la_z = z + 0.32 * sin_y + 0.3 * cos_y
                boxes.append(self._make_box_verts((ra_x, y + 0.95, ra_z), (0.18, 0.18, 0.6), yaw, T_ZOMBIE_FACE, shade_mult=shade_mult))
                boxes.append(self._make_box_verts((la_x, y + 0.95, la_z), (0.18, 0.18, 0.6), yaw, T_ZOMBIE_FACE, shade_mult=shade_mult))
                # Legs
                sw = math.sin(ent.walk_cycle) * 0.15
                rl_x = x + 0.15 * cos_y + sw * sin_y
                rl_z = z - 0.15 * sin_y + sw * cos_y
                ll_x = x - 0.15 * cos_y - sw * sin_y
                ll_z = z + 0.15 * sin_y - sw * cos_y
                boxes.append(self._make_box_verts((rl_x, y + 0.3, rl_z), (0.2, 0.6, 0.2), yaw, T_DIRT, shade_mult=shade_mult))
                boxes.append(self._make_box_verts((ll_x, y + 0.3, ll_z), (0.2, 0.6, 0.2), yaw, T_DIRT, shade_mult=shade_mult))
            elif ent.kind == "pig":
                yaw_rad = math.radians(yaw)
                cos_y, sin_y = math.cos(yaw_rad), math.sin(yaw_rad)
                # Body
                boxes.append(self._make_box_verts((x, y + 0.45, z), (0.65, 0.55, 0.9), yaw, T_PIG_BODY, shade_mult=shade_mult))
                # Head
                hx = x + 0.45 * sin_y
                hz = z + 0.45 * cos_y
                boxes.append(self._make_box_verts((hx, y + 0.6, hz), (0.42, 0.42, 0.42), yaw, T_PIG_FACE, shade_mult=shade_mult))
                # 4 legs
                sw = math.sin(ent.walk_cycle) * 0.12
                for ox, oz, s in [(-0.2, -0.3, sw), (0.2, -0.3, -sw), (-0.2, 0.3, -sw), (0.2, 0.3, sw)]:
                    lx = x + ox * cos_y + (oz + s) * sin_y
                    lz = z - ox * sin_y + (oz + s) * cos_y
                    boxes.append(self._make_box_verts((lx, y + 0.18, lz), (0.18, 0.35, 0.18), yaw, T_PIG_BODY, shade_mult=shade_mult))

        if not boxes:
            return None, 0
        data = np.concatenate(boxes, axis=0).astype("f4")
        return data, len(data)

    def render(self, screen, eye, forward, target=None, entities=None, mining_target=None, crack_stage=-1, render_dist=4, alpha=0.0):
        """Draw the world seen from eye into screen (a (height, width) uint8 view of pyxel.screen)."""
        self.update_streaming(eye[0], eye[2], render_dist=render_dist)
        vp = self.projection @ look_at(eye, forward)
        mvp = vp.T.copy().tobytes()
        fog_color, fog_start, fog_end = self.fog
        planes = self._frustum_planes(vp)
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
            for (cx, cz), chunk in self.chunks.items():
                if chunk and self._chunk_in_frustum(planes, cx, cz):
                    chunk[1].render()

            # Render 3D Mobs with sub-frame temporal interpolation
            if entities:
                ent_data, vcount = self._build_entities_mesh(entities, alpha=alpha)
                if ent_data is not None and vcount > 0:
                    self.entity_vbo.write(ent_data.tobytes())
                    self.entity_vao.render(moderngl.TRIANGLES, vertices=vcount)

            # Render block crack overlay
            if mining_target and 0 <= crack_stage <= 3:
                tx, ty, tz = mining_target
                crack_tile = T_CRACK_0 + crack_stage
                crack_verts = self._make_box_verts((tx + 0.5, ty + 0.5, tz + 0.5), (1.004, 1.004, 1.004), 0.0, crack_tile, kind=1.0)
                self.crack_vbo.write(crack_verts.astype("f4").tobytes())
                self.crack_vao.render(moderngl.TRIANGLES, vertices=36)

            if target:
                corners = np.array([(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype="f4")
                corners = (corners - 0.5) * 1.004 + 0.5 + np.array(target, dtype="f4")
                lines = corners[np.array(CUBE_EDGES).ravel()]
                self.outline_vbo.write(lines.astype("f4").tobytes())
                self.outline_program["mvp"].write(mvp)
                self.outline_vao.render(moderngl.LINES)
            width, height = self.size
            if self._frame_buf is None or len(self._frame_buf) != width * height:
                self._frame_buf = bytearray(width * height)
            self.fbo.read_into(self._frame_buf, components=1, dtype="f1")
        frame = np.frombuffer(self._frame_buf, dtype=np.uint8).reshape(height, width)
        screen[:, :] = frame[::-1]  # OpenGL rows go bottom-up
