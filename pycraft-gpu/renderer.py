"""GPU renderer: draws the world with OpenGL (moderngl) off-screen, then copies the frame into Pyxel's screen.

Near the camera the world is drawn block by block: each 16x16 column of the world gets one mesh,
made of the visible faces of its sections, and a few columns are built every frame, nearest first.
Farther away, up to about 8 km, the terrain is drawn as a smooth height map at six levels of detail
(a "clipmap"), sampled from the same terrain generator, so the mountains thousands of blocks high
can be seen from far away. Everything is drawn relative to the camera, which keeps the numbers
small and precise anywhere in the endless world.

The shaders output Pyxel palette indices directly (one byte per pixel), so the frame can be copied
into pyxel.screen with no conversion on the CPU. Transparency is done by "dithering": leaves and glass
skip their see-through texels, and water skips every other pixel in a checkerboard.
"""
import functools
import math
import time

import moderngl
import numpy as np

from blocks import (ACACIA_LEAVES, BIRCH_LEAVES, GRASS, ICE, JUNGLE_LEAVES, LEAVES, RED_SAND, SAND, SNOW,
                    SPRUCE_LEAVES, TERRACOTTA, WATER, block_colors)
import terrain as T
from builder import IN_FLIGHT, WATER_SURFACE, WORKERS, Builders, mesh_section
from terrain import CHUNK, WORLD_HEIGHT

OUTLINE_INDEX = 0  # Pyxel black
LOD_SIZE = 128  # vertices per side of each level of the distant terrain
LOD_LEVELS = 6
LOD_SPACING = 4  # blocks between vertices on the finest level; each level doubles it
LOD_STRIPS_PER_FRAME = 4
READY_SIZE = 64  # the map of columns drawn as blocks covers 64x64 chunks around the camera

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

# Haze that grows with distance (blue mountains far away), plus a linear fog: under water, and to
# hide the far edge of the distant terrain
FOG = """
uniform vec3 fog_color;
uniform float fog_density;
uniform float fog_start;
uniform float fog_end;
vec3 fog(vec3 color, float dist) {
    float haze = 1.0 - exp(-dist * fog_density);
    float linear = clamp((dist - fog_start) / (fog_end - fog_start), 0.0, 1.0);
    return mix(color, fog_color, max(haze, linear));
}
"""

BLOCK_VERTEX_SHADER = """
#version 330
uniform mat4 vp;      // view and projection, with the camera at (0, 0, 0)
uniform vec3 origin;  // corner of this column, relative to the camera
in vec3 in_pos;       // relative to the corner of the column
in uvec4 in_info;     // atlas tile, corner of the face (0-3), face direction (0-5), kind
in vec4 in_tint;      // biome color for grass, leaves and water
out vec2 v_uv;
out float v_shade;
out float v_dist;
out vec3 v_tint;
flat out int v_kind;
const vec2 CORNERS[4] = vec2[](vec2(0.0, 0.0), vec2(1.0, 0.0), vec2(1.0, 1.0), vec2(0.0, 1.0));
// Light from one side (see SUN in the distant terrain): faces toward it are brighter
const float SHADES[6] = float[](0.76, 0.6, 0.95, 0.5, 0.71, 0.6);
const float INSET = 0.5 / 16.0;  // half a texel, so neighbor tiles never bleed in
void main() {
    vec3 pos = origin + in_pos;
    gl_Position = vp * vec4(pos, 1.0);
    vec2 tile = vec2(float(in_info.x % 8u), float(in_info.x / 8u));
    v_uv = (tile + INSET + CORNERS[in_info.y] * (1.0 - 2.0 * INSET)) / 8.0;
    v_shade = SHADES[in_info.z];
    v_kind = int(in_info.w);
    v_tint = in_tint.rgb;
    v_dist = length(pos);
}
"""

BLOCK_FRAGMENT_SHADER = """
#version 330
uniform sampler2D atlas;
uniform float light;
in vec2 v_uv;
in float v_shade;
in float v_dist;
in vec3 v_tint;
flat in int v_kind;
out float index;
""" + TO_PALETTE + FOG + """
void main() {
    vec4 tex = texture(atlas, v_uv);
    if (v_kind == 1 && tex.a < 0.5) discard;  // see-through texel (leaves, glass)
    if (v_kind == 2 && ((int(gl_FragCoord.x) + int(gl_FragCoord.y)) & 1) == 0) discard;  // water
    vec3 color = tex.rgb;
    if (tex.a > 0.5 && tex.a < 0.9) color *= v_tint;  // texel colored by the biome
    index = to_palette(fog(color * v_shade * light, v_dist));
}
"""

LOD_VERTEX_SHADER = """
#version 330
uniform mat4 vp;
uniform sampler2D heights;   // 128x128, wrapping around: grid point (x, z) is at texel (x & 127, z & 127)
uniform sampler2D colors;    // same layout; alpha = 1 for water
uniform ivec2 grid_origin;   // grid coordinates of vertex (0, 0)
uniform vec2 origin;         // its position relative to the camera (x, z)
uniform float cam_y;
uniform float spacing;
in vec2 in_grid;
out vec3 v_color;
out float v_shade;
out float v_dist;
out vec2 v_xz;
const vec3 SUN = vec3(0.396, 0.88, 0.264);  // fixed light direction, high in the sky
float height_at(ivec2 local) { return texelFetch(heights, (grid_origin + local) & 127, 0).r; }
void main() {
    ivec2 local = ivec2(in_grid);
    ivec2 lo = max(local - 1, 0), hi = min(local + 1, 127);
    float dx = (height_at(ivec2(hi.x, local.y)) - height_at(ivec2(lo.x, local.y))) / (float(hi.x - lo.x) * spacing);
    float dz = (height_at(ivec2(local.x, hi.y)) - height_at(ivec2(local.x, lo.y))) / (float(hi.y - lo.y) * spacing);
    vec3 n = normalize(vec3(-dx, 1.0, -dz));
    vec4 c = texelFetch(colors, (grid_origin + local) & 127, 0);
    float h = height_at(local);
    bool snow = min(c.r, c.b) > 0.85;  // snow holds on steeper slopes than grass
    float rock = smoothstep(snow ? 1.6 : 1.0, snow ? 2.4 : 1.6, length(vec2(dx, dz))) * (1.0 - c.a);  // bare rock
    float strata = 0.92 + 0.08 * sin(h * 0.09) + 0.04 * sin(h * 0.023);  // layers in the cliffs
    v_color = mix(c.rgb, vec3(0.49) * strata, rock);
    v_shade = 0.6 + 0.4 * max(dot(n, SUN), 0.0);  // same light as the faces of the blocks
    vec3 pos = vec3(origin.x + float(local.x) * spacing, h - cam_y, origin.y + float(local.y) * spacing);
    v_xz = pos.xz;
    v_dist = length(pos);
    gl_Position = vp * vec4(pos, 1.0);
}
"""

LOD_FRAGMENT_SHADER = """
#version 330
uniform float light;
uniform int level;
uniform vec4 inner;          // area drawn by the finer level, relative to the camera: min x, min z, max x, max z
uniform sampler2D ready;     // 64x64 wrapping map of the columns drawn as blocks
uniform ivec2 cam_chunk;
uniform vec2 cam_in_chunk;
in vec3 v_color;
in float v_shade;
in float v_dist;
in vec2 v_xz;
out float index;
""" + TO_PALETTE + FOG + """
void main() {
    if (level == 0) {  // leave a hole where the blocks are drawn
        ivec2 rel = ivec2(floor((v_xz + cam_in_chunk) / 16.0));
        if (abs(rel.x) < 32 && abs(rel.y) < 32 && texelFetch(ready, (cam_chunk + rel) & 63, 0).r > 0.5) discard;
    } else if (all(greaterThan(v_xz, inner.xy)) && all(lessThan(v_xz, inner.zw))) {
        discard;  // the finer level draws this part
    }
    index = to_palette(fog(v_color * v_shade * light, v_dist));
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
uniform mat4 vp;
in vec3 in_pos;
void main() { gl_Position = vp * vec4(in_pos, 1.0); }
"""

OUTLINE_FRAGMENT_SHADER = f"""
#version 330
out float index;
void main() {{ index = {OUTLINE_INDEX}.0 / 255.0; }}
"""

CUBE_EDGES = [(0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4), (0, 4), (1, 5), (2, 6), (3, 7)]

# Distant terrain: the block that covers the ground in each biome, and its trees' leaves
GROUND = np.full(len(T.BIOME_NAMES), GRASS)
GROUND[[T.BEACH, T.DESERT, T.OCEAN, T.DEEP_OCEAN]] = SAND
GROUND[T.BADLANDS] = TERRACOTTA
GROUND[[T.SNOWY_TAIGA, T.SNOWY_TUNDRA, T.SNOWY_PEAKS, T.FROZEN_OCEAN]] = SNOW
GROUND[T.GLACIER] = ICE
CANOPY_LEAVES = np.full(len(T.BIOME_NAMES), LEAVES)
CANOPY_LEAVES[[T.TAIGA, T.SNOWY_TAIGA, T.SNOWY_TUNDRA, T.ALPINE]] = SPRUCE_LEAVES
CANOPY_LEAVES[T.BIRCH_FOREST] = BIRCH_LEAVES
CANOPY_LEAVES[T.JUNGLE] = JUNGLE_LEAVES
CANOPY_LEAVES[T.SAVANNA] = ACACIA_LEAVES


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


def frustum_planes(vp):
    """The 6 planes (a, b, c, d) of the view: a point p is inside when a*x + b*y + c*z + d >= 0 for all."""
    m = vp.astype(np.float64)
    return np.array([m[3] + m[0], m[3] - m[0], m[3] + m[1], m[3] - m[1], m[3] + m[2], m[3] - m[2]])


def boxes_visible(planes, lo, hi):
    """For boxes lo..hi (arrays (n, 3)), True for those that touch the view."""
    visible = np.ones(len(lo), dtype=bool)
    for a, b, c, d in planes:
        # The corner of each box farthest along the plane's normal
        px = np.where(a > 0, hi[:, 0], lo[:, 0])
        py = np.where(b > 0, hi[:, 1], lo[:, 1])
        pz = np.where(c > 0, hi[:, 2], lo[:, 2])
        visible &= a * px + b * py + c * pz + d >= 0
    return visible


# --- Block meshes ------------------------------------------------------------------------------

class ColumnMesh:
    def __init__(self):
        self.parts = {}  # cy -> vertices of that section (or None)
        self.vao = self.vbo = self.ibo = None
        self.y_range = (0, 0)

    def release(self):
        for obj in (self.vao, self.vbo, self.ibo):
            if obj is not None:
                obj.release()
        self.vao = self.vbo = self.ibo = None


@functools.lru_cache(maxsize=8)
def column_offsets(radius):
    """(dx, dz) of the columns within radius chunks, nearest first."""
    r = radius + 0.5
    offsets = [(dx, dz) for dx in range(-radius, radius + 1) for dz in range(-radius, radius + 1)
               if dx * dx + dz * dz <= r * r]
    return sorted(offsets, key=lambda o: o[0] * o[0] + o[1] * o[1])


class Chunks:
    """Block meshes of the columns around the camera.

    Worker processes (see builder.py) build them, nearest first; this uploads them to the graphics
    card and draws them. Block changes are rebuilt right away here. Each column counts its changes
    ("version"): a mesh a worker built from older blocks is thrown away and asked for again."""

    def __init__(self, ctx, program, world):
        self.ctx, self.program = ctx, program
        self.meshes = {}  # (cx, cz) -> ColumnMesh
        self.radius = 8
        self.builders = Builders()
        self.ready = np.zeros((READY_SIZE, READY_SIZE), np.uint8)  # [cz & 63, cx & 63] = 255 when drawn
        self.ready_changed = True
        self.ready_texture = ctx.texture((READY_SIZE, READY_SIZE), 1, dtype="f1")
        self.ready_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.set_world(world)

    def set_world(self, world):
        self.release()
        self.world = world
        self.built = {}  # (cx, cz) -> sections the workers have meshed
        self.versions = {}  # (cx, cz) -> number of block changes
        self.pending = {}  # finished meshes waiting for their upload
        self.asked_columns = set()  # columns asked of a worker for the game's own world
        self.builders.set_world(world)

    def release(self):
        for mesh in self.meshes.values():
            mesh.release()
        self.meshes = {}
        self.ready[:] = 0
        self.ready_changed = True

    def progress(self, cam, radius):
        """Share of the columns within radius chunks of the camera that are drawn (for loading)."""
        pcx, pcz = math.floor(cam[0] / CHUNK), math.floor(cam[2] / CHUNK)
        near = [(pcx + dx, pcz + dz) for dx, dz in column_offsets(radius)]
        return sum(k in self.meshes for k in near) / len(near)

    def update(self, cam, budget):
        """Drop far columns, upload finished meshes for up to `budget` seconds, ask for more."""
        pcx, pcy, pcz = (math.floor(c / CHUNK) for c in cam)
        far = (self.radius + 1.5) ** 2

        def is_far(key):
            return (key[0] - pcx) ** 2 + (key[1] - pcz) ** 2 > far

        for key in [k for k in self.meshes if is_far(k)]:
            self.meshes.pop(key).release()
            self.ready[key[1] % READY_SIZE, key[0] % READY_SIZE] = 0
            self.ready_changed = True
        for key in [k for k in self.built if is_far(k)]:
            del self.built[key]
        meshes, columns = self.builders.finished()
        for col in columns:
            self.world.columns.setdefault((col.cx, col.cz), col)
            self.asked_columns.discard((col.cx, col.cz))
        for key, version, parts, done in meshes:
            self.pending[key] = (version, parts, done)
        deadline = time.perf_counter() + budget
        while self.pending and time.perf_counter() < deadline:
            key = next(iter(self.pending))
            version, parts, done = self.pending.pop(key)
            if is_far(key) or version != self.versions.get(key, 0):
                continue  # not wanted any more, or built from blocks changed since: asked for again
            mesh = self.meshes.get(key) or ColumnMesh()
            self.meshes[key] = mesh
            mesh.parts.update(parts)
            self.built[key] = done
            self.upload(key, mesh)

        # The game's own world needs the columns around the player (walking, aiming): ask a worker
        # for them ahead of time, so the game doesn't have to generate them itself
        around = [(pcx + dx, pcz + dz) for dx in range(-3, 4) for dz in range(-3, 4)]
        missing = [k for k in around if k not in self.world.columns and k not in self.asked_columns]
        if missing:
            self.asked_columns.update(missing)
            self.builders.request_columns(missing)

        # Hand out the nearest columns still to build (and the caves around the camera's height)
        caves = set(range(max(pcy - 2, 0), min(pcy + 3, WORLD_HEIGHT // CHUNK)))
        jobs = []
        for dx, dz in column_offsets(self.radius):
            key = (pcx + dx, pcz + dz)
            near = abs(dx) <= 2 and abs(dz) <= 2
            done = self.built.get(key)
            if done is not None and not (near and not caves <= done):
                continue
            if key in self.pending or self.builders.busy(key):
                continue
            jobs.append((key, self.versions.get(key, 0), done or set(), caves if near else set()))
            if len(jobs) >= WORKERS * IN_FLIGHT:
                break
        if jobs:
            self.builders.request((pcx, pcy, pcz), jobs)

    def upload(self, key, mesh):
        mesh.release()
        parts = [p for p in mesh.parts.values() if p is not None]
        if parts:
            vertices = np.concatenate(parts)
            faces = len(vertices) // 4
            indices = (np.arange(faces, dtype=np.uint32)[:, None] * 4 + np.array([0, 1, 2, 0, 2, 3], np.uint32))
            mesh.vbo = self.ctx.buffer(vertices.tobytes())
            mesh.ibo = self.ctx.buffer(indices.tobytes())
            mesh.vao = self.ctx.vertex_array(self.program, [(mesh.vbo, "3f 4u1 4f1", "in_pos", "in_info", "in_tint")],
                                             index_buffer=mesh.ibo, index_element_size=4)
            ys = vertices["pos"][:, 1]
            mesh.y_range = (float(ys.min()), float(ys.max()))
        self.ready[key[1] % READY_SIZE, key[0] % READY_SIZE] = 255
        self.ready_changed = True

    def block_changed(self, x, y, z):
        """Rebuild the sections touching block (x, y, z) right away, and tell the workers."""
        self.builders.block_changed(x, y, z, self.world.get(x, y, z))
        cx, cy, cz = x >> 4, y >> 4, z >> 4
        todo = {(cx, cy, cz)}
        for axis, v in ((0, x), (1, y), (2, z)):
            for side in ((-1,) if v % CHUNK == 0 else ()) + ((1,) if v % CHUNK == CHUNK - 1 else ()):
                key = [cx, cy, cz]
                key[axis] += side
                todo.add(tuple(key))
        columns = set()
        for kx, ky, kz in todo:
            self.versions[(kx, kz)] = self.versions.get((kx, kz), 0) + 1
            mesh = self.meshes.get((kx, kz))
            if mesh is not None and 0 <= ky < WORLD_HEIGHT // CHUNK:
                mesh.parts[ky] = mesh_section(self.world, self.world.column(kx, kz), kx, ky, kz)
                columns.add((kx, kz))
        for key in columns:
            self.upload(key, self.meshes[key])

    def render(self, vp, cam):
        drawn = [(k, m) for k, m in self.meshes.items() if m.vao is not None]
        if not drawn:
            return 0
        corner = np.array([(k[0] * CHUNK - cam[0], m.y_range[0] - cam[1], k[1] * CHUNK - cam[2]) for k, m in drawn])
        size = np.array([(CHUNK, m.y_range[1] - m.y_range[0], CHUNK) for _, m in drawn])
        visible = boxes_visible(frustum_planes(vp), corner, corner + size)
        origin = self.program["origin"]
        for (key, mesh), (ox, _, oz), show in zip(drawn, corner, visible):
            if show:
                origin.value = (ox, -cam[1], oz)
                mesh.vao.render()
        return int(visible.sum())


# --- Distant terrain ---------------------------------------------------------------------------

class FarTerrain:
    """The terrain beyond the blocks, as six square grids of 128x128 points around the camera, each
    twice as coarse and twice as wide as the one before (4 to 128 blocks between points, up to 8 km
    away). Heights and colors live in textures that wrap around: when the camera moves, only the
    new rows or columns at the edge are sampled."""

    def __init__(self, ctx, program, world, colors):
        self.ctx, self.program, self.world, self.colors = ctx, program, world, colors
        n = LOD_SIZE
        i, j = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
        grid = np.stack([i.ravel(), j.ravel()], axis=1).astype("f4")
        quads = (i[:-1, :-1] * n + j[:-1, :-1]).ravel()
        indices = np.stack([quads, quads + n, quads + n + 1, quads, quads + n + 1, quads + 1], axis=1)
        self.vbo = ctx.buffer(grid.tobytes())
        self.ibo = ctx.buffer(indices.astype("u4").tobytes())
        self.vao = ctx.vertex_array(program, [(self.vbo, "2f", "in_grid")], index_buffer=self.ibo,
                                    index_element_size=4)
        self.heights = [ctx.texture((n, n), 1, dtype="f4") for _ in range(LOD_LEVELS)]
        self.color_maps = [ctx.texture((n, n), 4, dtype="f1") for _ in range(LOD_LEVELS)]
        for tex in self.heights + self.color_maps:
            tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.origins = [None] * LOD_LEVELS  # grid coordinates of each level's vertex (0, 0)
        self.queue = []  # texture writes still to do

    def set_world(self, world):
        self.world = world
        self.origins = [None] * LOD_LEVELS
        self.queue = []

    def sample(self, x, z):
        """Height of the top surface (water included) and color at points (x, z), for the textures."""
        s = self.world.gen.sample(x, z)
        height = np.maximum(np.floor(s["height"]) + 1, s["water"] + WATER_SURFACE).astype("f4")
        grass, foliage, water = T.tints(s["temperature"], s["humidity"], s["biome"])
        biome = s["biome"]
        ground = GROUND[biome]
        color = self.colors[ground] * np.where((ground == GRASS)[..., None], grass, 1.0)
        badlands = biome == T.BADLANDS
        color[badlands] = (self.colors[TERRACOTTA] + self.colors[RED_SAND]) / 2
        leaves = CANOPY_LEAVES[biome]
        tinted = np.isin(leaves, (LEAVES, JUNGLE_LEAVES, ACACIA_LEAVES))[..., None]
        canopy = self.colors[leaves] * np.where(tinted, foliage, 1.0) * 0.8  # shade under the trees
        color = color + (canopy - color) * T.CANOPY[biome][..., None]
        wet = s["water"] > s["height"]
        color[wet] = (self.colors[WATER] * water)[wet]
        ice = wet & (s["temperature"] < -0.55)
        color[ice] = self.colors[ICE]
        rgba = np.concatenate([color, (wet & ~ice)[..., None]], axis=-1)
        return height, (np.clip(rgba, 0, 1) * 255).astype("u1")

    def update(self, cam):
        n = LOD_SIZE
        writes = []  # (level, grid xs, grid zs, texel u, texel v)
        for level in range(LOD_LEVELS):
            spacing = LOD_SPACING << level
            new = (math.floor(cam[0] / spacing) - n // 2, math.floor(cam[2] / spacing) - n // 2)
            old = self.origins[level]
            if old == new:
                continue
            self.origins[level] = new
            # Texel (u, v) holds grid point (x, z) with x & 127 == u and z & 127 == v
            xs = new[0] + (np.arange(n) - new[0]) % n  # grid x of each texel column
            zs = new[1] + (np.arange(n) - new[1]) % n  # grid z of each texel row
            if old is None or abs(new[0] - old[0]) >= n or abs(new[1] - old[1]) >= n:
                writes.append((level, xs, zs, 0, 0))
                continue
            # Only the new columns (x) and rows (z) that came into view
            gx = range(old[0] + n, new[0] + n) if new[0] > old[0] else range(new[0], old[0])
            writes += [(level, np.array([x]), zs, x % n, 0) for x in gx]
            gz = range(old[1] + n, new[1] + n) if new[1] > old[1] else range(new[1], old[1])
            writes += [(level, xs, np.array([z]), 0, z % n) for z in gz]
        # Whole levels (a new world, a jump far away) are done at once; edge strips a few per frame,
        # oldest first, so several levels moving together don't make one long frame
        self.queue += writes
        if any(len(w[1]) * len(w[2]) > LOD_SIZE for w in self.queue):
            writes, self.queue = self.queue, []
        else:
            writes, self.queue = self.queue[:LOD_STRIPS_PER_FRAME], self.queue[LOD_STRIPS_PER_FRAME:]
        if not writes:
            return
        # Sample all the new points of all levels together: one big call is much faster than many
        points = []
        for level, xs, zs, _, _ in writes:
            spacing = float(LOD_SPACING << level)
            z, x = np.meshgrid(zs * spacing, xs * spacing, indexing="ij")  # texture rows are z
            points.append((x.ravel(), z.ravel()))
        height, color = self.sample(np.concatenate([p[0] for p in points]), np.concatenate([p[1] for p in points]))
        start = 0
        for level, xs, zs, u, v in writes:
            end = start + len(xs) * len(zs)
            viewport = (u, v, len(xs), len(zs))
            self.heights[level].write(height[start:end].tobytes(), viewport=viewport)
            self.color_maps[level].write(color[start:end].tobytes(), viewport=viewport)
            start = end

    def render(self, vp, cam, chunks):
        p = self.program
        p["vp"].write(vp.T.copy().tobytes())
        p["cam_y"] = float(cam[1])
        pcx, pcz = math.floor(cam[0] / CHUNK), math.floor(cam[2] / CHUNK)
        p["cam_chunk"] = (pcx, pcz)
        p["cam_in_chunk"] = (float(cam[0] - pcx * CHUNK), float(cam[2] - pcz * CHUNK))
        p["heights"], p["colors"], p["ready"] = 0, 1, 2
        chunks.ready_texture.use(2)
        inner = (0.0, 0.0, 0.0, 0.0)
        for level in range(LOD_LEVELS):
            spacing = LOD_SPACING << level
            gx, gz = self.origins[level]
            ox, oz = gx * spacing - cam[0], gz * spacing - cam[2]
            p["level"] = level
            p["inner"] = inner
            p["grid_origin"] = (gx, gz)
            p["origin"] = (float(ox), float(oz))
            p["spacing"] = float(spacing)
            self.heights[level].use(0)
            self.color_maps[level].use(1)
            self.vao.render()
            # The next level leaves a hole for this one, a bit smaller so the two overlap
            margin = 2 * (spacing * 2)
            extent = (LOD_SIZE - 1) * spacing
            inner = (float(ox + margin), float(oz + margin), float(ox + extent - margin), float(oz + extent - margin))


# --- Renderer ----------------------------------------------------------------------------------

class Renderer:
    def __init__(self, ctx, world, atlas, width, height, fov=70):
        """ctx must be created before pyxel.init, so Pyxel's own OpenGL context ends up current."""
        self.ctx = ctx
        self.fov = fov
        self.fbo = None
        self.render_distance = 8
        self.drawn = 0  # block columns drawn in the last frame
        # Lighting and sky, changed by the game every frame (see set_environment)
        self.light = 1.0
        self.zenith = self.horizon = (0.6, 0.8, 1.0)
        self.sun_dir = (0.0, 1.0, 0.0)
        self.fog = (self.horizon, 1 / 3500, 6000.0, 8000.0)
        self.colors = block_colors(atlas)
        with self.ctx:
            self.program = ctx.program(vertex_shader=BLOCK_VERTEX_SHADER, fragment_shader=BLOCK_FRAGMENT_SHADER)
            self.lod_program = ctx.program(vertex_shader=LOD_VERTEX_SHADER, fragment_shader=LOD_FRAGMENT_SHADER)
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
            self.chunks = Chunks(ctx, self.program, world)
            self.far = FarTerrain(ctx, self.lod_program, world, self.colors)
        self.world = world
        self.resize(width, height)

    def resize(self, width, height):
        """Draw frames of a new size (when the resolution setting changes)."""
        self.size = (width, height)
        with self.ctx:
            if self.fbo:
                for obj in (*self.fbo.color_attachments, self.fbo.depth_attachment, self.fbo):
                    obj.release()
            color = self.ctx.texture((width, height), 1, dtype="f1")
            depth = self.ctx.depth_renderbuffer((width, height))
            self.fbo = self.ctx.framebuffer(color_attachments=[color], depth_attachment=depth)

    def set_world(self, world):
        """Use another world (after loading or generating one)."""
        self.world = world
        with self.ctx:
            self.chunks.set_world(world)
            self.far.set_world(world)

    def set_environment(self, light, zenith, horizon, sun_dir, fog_color, fog_density, fog_start, fog_end):
        self.light = light
        self.zenith, self.horizon, self.sun_dir = zenith, horizon, sun_dir
        self.fog = (fog_color, fog_density, fog_start, fog_end)

    def update(self, cam, budget):
        """Upload the block meshes built near the camera (for up to `budget` seconds) and refresh the
        distant terrain around it."""
        with self.ctx:
            self.chunks.radius = self.render_distance
            self.far.update(cam)
            self.chunks.update(cam, budget)

    def progress(self, cam, radius=3):
        return self.chunks.progress(cam, radius)

    def block_changed(self, x, y, z):
        with self.ctx:
            self.chunks.block_changed(x, y, z)

    def render(self, screen, eye, forward, target=None):
        """Draw the world seen from eye into screen (a (height, width) uint8 view of pyxel.screen)."""
        width, height = self.size
        aspect = width / height
        view = look_at((0, 0, 0), forward)
        far_vp = perspective(self.fov, aspect, 1.0, 30000) @ view
        near_vp = perspective(self.fov, aspect, 0.05, 6000) @ view
        cam = tuple(float(c) for c in eye)
        fog_color, fog_density, fog_start, fog_end = self.fog
        # Every OpenGL call, setting shader values included, must happen inside `with self.ctx`:
        # outside it, Pyxel's own context is the current one (with a window; not in headless tests)
        with self.ctx:
            for p in (self.program, self.lod_program):
                p["light"] = self.light
                p["fog_color"] = fog_color
                p["fog_density"] = fog_density
                p["fog_start"] = fog_start
                p["fog_end"] = fog_end
            if self.chunks.ready_changed:
                self.chunks.ready_texture.write(self.chunks.ready.tobytes())
                self.chunks.ready_changed = False
            self.fbo.use()
            self.fbo.clear(depth=1.0)

            self.ctx.disable(moderngl.DEPTH_TEST)
            self.sky_program["inv_vp"].write(np.linalg.inv(far_vp).T.astype("f4").tobytes())
            self.sky_program["zenith"] = self.zenith
            self.sky_program["horizon"] = self.horizon
            self.sky_program["sun_dir"] = self.sun_dir
            self.sky_vao.render(moderngl.TRIANGLE_STRIP)

            # Distant terrain first, then clear the depth (not the colors) and draw the blocks on top:
            # each pass gets the depth precision it needs
            self.ctx.enable(moderngl.DEPTH_TEST)
            if None not in self.far.origins:
                self.far.render(far_vp, cam, self.chunks)
            self.fbo.color_mask = (False, False, False, False)
            self.fbo.clear(depth=1.0)
            self.fbo.color_mask = (True, True, True, True)
            self.fbo.use()  # the color mask only comes back into effect when the framebuffer is bound

            self.texture.use(0)
            self.program["vp"].write(near_vp.T.copy().tobytes())
            self.drawn = self.chunks.render(near_vp, cam)

            if target:
                corners = np.array([(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=np.float64)
                corners = (corners - 0.5) * 1.004 + 0.5 + np.array(target) - np.array(cam)
                lines = corners[np.array(CUBE_EDGES).ravel()]
                self.outline_vbo.write(lines.astype("f4").tobytes())
                self.outline_program["vp"].write(near_vp.T.copy().tobytes())
                self.outline_vao.render(moderngl.LINES)
            frame = np.frombuffer(self.fbo.read(components=1, dtype="f1"), dtype=np.uint8)
        screen[:, :] = frame.reshape(height, width)[::-1]  # OpenGL rows go bottom-up
