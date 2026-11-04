"""GPU renderer: draws the world with OpenGL (moderngl) off-screen, then copies the frame into Pyxel's screen.

Near the camera the world is drawn block by block: each 16x16 column of the world gets one mesh,
made of the visible faces of its sections, and a few columns are built every frame, nearest first.
Farther away, up to about 8 km, the terrain is drawn as blocky columns at six levels of detail
(a "clipmap"), sampled from the same terrain generator, so the mountains thousands of blocks high
can be seen from far away. Everything is drawn relative to the camera, which keeps the numbers
small and precise anywhere in the endless world.

Each frame is first drawn in full color: the sky with its sun, moon and stars, the distant terrain,
clouds, then the blocks, with see-through water that reflects the sky. Everything is lit by the
sun (or the moon): faces turned away from it get only the light of the sky, corners get darker
(ambient occlusion, worked out with the meshes), and shadow maps give the shadows. One shadow map
holds the blocks around the camera, two more the distant terrain, so mountains cast shadows
kilometers long. Clouds drift and cast their own shadows.

The finished image is then turned into Pyxel's 256 colors, on the graphics card too. 192 of the
colors adapt to what is on screen: a few thousand pixels are sampled every other frame and the
colors move toward them (k-means clustering). Each pixel is dithered between the two palette colors
that mix best into its own color. The shader writes one byte per pixel, the palette index, which is
copied into pyxel.screen.
"""
import functools
import math
import time

import moderngl
import numpy as np

from blocks import (ACACIA_LEAVES, ALL_LEAVES, ATLAS_TILES, BIRCH_LEAVES, BLOCK_TILES, ICE, JUNGLE_LEAVES, LEAVES,
                    SPRUCE_LEAVES, TILE, TINT_ALPHA, WATER)
import blocks as B
import terrain as T
from builder import IN_FLIGHT, WATER_SURFACE, WORKERS, Builders, mesh_section
from terrain import CHUNK, SEA_LEVEL, WORLD_HEIGHT

LOD_QUALITIES = {  # name -> (width of a column on the finest level in blocks, grid points per side, levels)
    "low": (2, 128, 7),  # what the distant terrain always was
    "medium": (2, 256, 7),  # same columns, but every level reaches twice as far
    "high": (1, 256, 8),  # one column per block near the blocks, then coarser and coarser
    "ultra": (1, 512, 6),  # one column per block as far as the blocks go, every level twice as wide
}
LOD_QUALITY_NAMES = list(LOD_QUALITIES)
LOD_STRIPS_PER_FRAME = 4
LOD_MARGIN = 4  # columns along the edge of a level that the next, coarser one always draws
LOD_BAND = 24  # columns over which a level gives way to the next one, cell by cell
FAR_LIMIT = 8000.0  # the coarsest level reaches about 8 km
SIM_DISTANCES = {32: 6, 64: 8, 128: 10, 256: 12, 512: 12}  # render distance -> radius drawn as blocks (chunks)
CUBE_FACES = (  # (normal, 6 corners) for the 5 visible faces of a unit cube, corners CCW seen from outside
    ((0, 1, 0), ((0, 1, 0), (1, 1, 1), (1, 1, 0), (0, 1, 0), (0, 1, 1), (1, 1, 1))),
    ((1, 0, 0), ((1, 1, 0), (1, 0, 1), (1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1))),
    ((-1, 0, 0), ((0, 1, 1), (0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0), (0, 0, 0))),
    ((0, 0, 1), ((0, 1, 1), (0, 0, 1), (1, 0, 1), (0, 1, 1), (1, 0, 1), (1, 1, 1))),
    ((0, 0, -1), ((1, 1, 0), (1, 0, 0), (0, 0, 0), (1, 1, 0), (0, 0, 0), (0, 1, 0))),
)
READY_SIZE = 64  # the map of columns drawn as blocks covers 64x64 chunks around the camera
SHADOW_SIZE = 2048  # texels per side of each shadow map
SHADOW_DEPTH = 4500.0  # the shadow maps hold what is less than this far from the camera along the light
TERRAIN_SHADOW_HALF = (1024.0, 8192.0)  # half the width of the two shadow maps of the distant terrain
CLOUD_HEIGHT = SEA_LEVEL + 940.0  # high mountains rise through the clouds
CLOUD_PERIOD = 4096.0  # the cloud pattern repeats every 4096 blocks
CLOUD_WIND = (6.0, 2.0)  # blocks per second
CLOUD_EXTENT = 24000.0  # half the width of the cloud layer drawn around the camera
MSAA_SAMPLES = 4  # anti-aliasing: samples per pixel with "fancy" graphics
FIXED_COLORS = 64  # palette entries that never change: Pyxel's 16 (HUD) and 48 for the block icons
SAMPLES = 64  # the frame is sampled at 64 x 64 points to adapt the palette
ADAPT_EVERY = 2  # frames between two adjustments of the palette
MIX_PENALTY = 0.35  # how much dithering between two distant colors is avoided (it looks noisy)

# Texture units
ATLAS_UNIT = 0
COLORS_UNIT = 1
READY_UNIT = 2
CLOUDS_UNIT = 3
SHADOW_UNITS = (4, 5, 6)
DATA_UNIT = 7
TILE_AVG_UNIT = 9

# --- Shader code shared by several programs ---------------------------------------------------

# Block numbers, the atlas tile of each face of each block, and the badlands' rock layers, for the
# distant terrain's shaders
BLOCK_IDS = "".join("const int %s = %d;\n" % (name, getattr(B, name)) for name in (
    "GRASS", "DIRT", "STONE", "PODZOL", "MUD", "GRAVEL", "SNOW", "WATER", "ICE", "TERRACOTTA", "RED_SAND",
    "LEAVES", "SPRUCE_LEAVES", "BIRCH_LEAVES", "JUNGLE_LEAVES", "ACACIA_LEAVES"))
BLOCK_TILES_GLSL = "const int BLOCK_TILES[%d] = int[](%s);\n" % (
    BLOCK_TILES.size, ", ".join(str(int(t)) for t in BLOCK_TILES.ravel()))
BANDS_GLSL = "const int BANDS[%d] = int[](%s);\n" % (len(T.BANDS), ", ".join(str(int(b)) for b in T.BANDS))

LIGHT = """
const vec3 NORMALS[6] = vec3[](vec3(1.0, 0.0, 0.0), vec3(-1.0, 0.0, 0.0), vec3(0.0, 1.0, 0.0),
                               vec3(0.0, -1.0, 0.0), vec3(0.0, 0.0, 1.0), vec3(0.0, 0.0, -1.0));
uniform vec3 light_dir;    // toward the sun by day, the moon by night
uniform vec3 light_color;  // its direct light (none while it crosses the horizon)
uniform vec3 sky_light;    // light from the whole sky, on surfaces facing up
uniform vec3 zenith;
uniform vec3 horizon;
uniform vec3 sun_dir;
uniform vec3 sun_glow;     // the bright sky around the sun
// Haze that grows with distance (blue mountains far away), plus a linear fog: under water, and to
// hide the far edge of the distant terrain
uniform vec3 fog_color;
uniform float fog_density;
uniform float fog_start;
uniform float fog_end;
float fog_amount(float dist) {
    float haze = 1.0 - exp(-dist * fog_density);
    float linear = clamp((dist - fog_start) / (fog_end - fog_start), 0.0, 1.0);
    return max(haze, linear);
}
vec3 fog(vec3 color, float dist) { return mix(color, fog_color, fog_amount(dist)); }
vec3 sky_color(vec3 dir) {
    vec3 color = mix(horizon, zenith, clamp(dir.y * 1.6, 0.0, 1.0));
    float s = max(dot(dir, sun_dir), 0.0);
    return color + sun_glow * (0.3 * pow(s, 5.0) + 0.5 * pow(s, 48.0));
}
"""

CLOUDS = """
uniform sampler2D clouds;   // tileable noise
uniform vec2 cloud_origin;  // the camera's position plus the wind's drift, in cloud texture units
uniform float cloud_height; // middle of the cloud slab above the camera
uniform float cloud_cover;  // noise level where the clouds begin
const float CLOUD_THICK = 80.0;  // the clouds are a slab this many blocks thick
const float CLOUD_HALF = CLOUD_THICK / 2.0;
float cloud_density(vec2 xz) {  // xz relative to the camera
    vec2 uv = cloud_origin + xz / %(period).1f;
    float n = 0.72 * texture(clouds, uv).r + 0.28 * texture(clouds, uv * 6.0).r;
    return smoothstep(cloud_cover, cloud_cover + 0.16, n);
}
float cloud_shadow(vec3 pos) {
    if (light_dir.y < 0.03 || pos.y > cloud_height + CLOUD_HALF) return 1.0;
    return 1.0 - 0.55 * cloud_density(pos.xz + light_dir.xz * ((cloud_height - pos.y) / light_dir.y));
}
""" % {"period": CLOUD_PERIOD}

SHADOWS = """
uniform int shadows_on;
uniform sampler2DShadow shadow_near;  // the blocks around the camera
uniform sampler2DShadow shadow_mid;   // the terrain within about 1 km
uniform sampler2DShadow shadow_far;   // the terrain up to 8 km
uniform mat4 shadow_vp0;              // position relative to the camera -> place in each map (0-1)
uniform mat4 shadow_vp1;
uniform mat4 shadow_vp2;
uniform vec3 shadow_texel;            // size of a texel of each map, in blocks
float pcf(sampler2DShadow map, vec3 p) {  // 4 filtered lookups: soft edges
    vec2 t = 0.5 / vec2(textureSize(map, 0));
    return 0.25 * (texture(map, vec3(p.xy + vec2(-t.x, -t.y), p.z)) + texture(map, vec3(p.xy + vec2(t.x, -t.y), p.z))
                 + texture(map, vec3(p.xy + vec2(-t.x, t.y), p.z)) + texture(map, vec3(p.xy + vec2(t.x, t.y), p.z)));
}
bool inside(vec3 p) { return all(greaterThan(p, vec3(0.001))) && all(lessThan(p, vec3(0.999))); }
// Shadows of the terrain (mountains), from the maps of the distant terrain
float terrain_shadow(vec3 pos, vec3 n) {
    vec3 p = (shadow_vp1 * vec4(pos + n * (2.0 * shadow_texel.y), 1.0)).xyz;
    if (inside(p)) return pcf(shadow_mid, p);
    p = (shadow_vp2 * vec4(pos + n * (2.0 * shadow_texel.z), 1.0)).xyz;
    if (inside(p)) return pcf(shadow_far, p);
    return 1.0;
}
float block_shadow(vec3 pos, vec3 n) {
    vec3 p = (shadow_vp0 * vec4(pos + n * (1.5 * shadow_texel.x), 1.0)).xyz;
    float s = inside(p) ? pcf(shadow_near, p) : 1.0;
    // Mountains farther away, tested a few blocks toward the light: the smooth distant terrain lies
    // about where the blocks are, and must not shadow them
    return min(s, terrain_shadow(pos + light_dir * 6.0, n));
}
"""

WAVES = """
uniform vec2 wave_origin;  // the camera's x and z, modulo 256 (the waves repeat every 256 blocks)
uniform float time;
vec3 wave_normal(vec2 xz) {
    vec2 p = xz + wave_origin;
    const float K = 6.2831853 / 256.0;
    vec2 slope = vec2(0.0);
    // Each wave fits a whole number of times in 256 blocks: (direction, amplitude, speed)
    slope += vec2(37.0, 11.0) * (K * 0.06) * cos(dot(vec2(37.0, 11.0), p) * K + time * 1.6);
    slope += vec2(-13.0, 41.0) * (K * 0.05) * cos(dot(vec2(-13.0, 41.0), p) * K + time * 1.9);
    slope += vec2(71.0, -53.0) * (K * 0.025) * cos(dot(vec2(71.0, -53.0), p) * K + time * 2.7);
    slope += vec2(-97.0, -89.0) * (K * 0.018) * cos(dot(vec2(-97.0, -89.0), p) * K + time * 3.4);
    return normalize(vec3(-slope.x, 1.0, -slope.y));
}
"""

OKLAB = """
// OKLab: a color space where distances match how different colors look
vec3 oklab(vec3 srgb) {
    vec3 c = mix(srgb / 12.92, pow((srgb + 0.055) / 1.055, vec3(2.4)), step(0.04045, srgb));
    float l = pow(max(0.4122214708 * c.r + 0.5363325363 * c.g + 0.0514459929 * c.b, 0.0), 1.0 / 3.0);
    float m = pow(max(0.2119034982 * c.r + 0.6806995451 * c.g + 0.1073969566 * c.b, 0.0), 1.0 / 3.0);
    float s = pow(max(0.0883024619 * c.r + 0.2817188376 * c.g + 0.6299787005 * c.b, 0.0), 1.0 / 3.0);
    return vec3(0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s,
                1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s,
                0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s);
}
"""

FINISH = """
uniform float dim;  // darker behind the menus
uniform vec3 tint;
vec3 finish(vec3 c) {
    c = min(c, 0.8) + 0.2 * (1.0 - exp(-5.0 * max(c - 0.8, 0.0)));  // highlights roll off toward white
    return clamp(c * tint * dim, 0.0, 1.0);
}
"""

FULLSCREEN_VERTEX_SHADER = """
#version 330
in vec2 in_pos;
out vec2 v_ndc;
void main() { gl_Position = vec4(in_pos, 0.0, 1.0); v_ndc = in_pos; }
"""

# --- Blocks: mode 0 the opaque faces, 1 the water, 2 the shadow map ------------------------------

BLOCK_VERTEX_SHADER = """
#version 330
uniform mat4 vp;      // view and projection, with the camera at (0, 0, 0)
uniform vec3 origin;  // corner of this column, relative to the camera
uniform int mode;
in vec3 in_pos;       // relative to the corner of the column
in uvec4 in_info;     // atlas tile, corner of the face (0-3), face direction (0-5), kind (see builder.KIND)
in vec4 in_tint;      // biome color for grass, leaves and water; ambient occlusion
out vec2 v_uv;
out vec3 v_pos;
out vec3 v_tint;
out float v_ao;
flat out int v_face;
flat out int v_kind;
flat out int v_tile;
const vec2 CORNERS[4] = vec2[](vec2(0.0, 0.0), vec2(1.0, 0.0), vec2(1.0, 1.0), vec2(0.0, 1.0));
const float INSET = 0.5 / 16.0;  // half a texel, so neighbor tiles never bleed in
void main() {
    vec3 pos = origin + in_pos;
    gl_Position = vp * vec4(pos, 1.0);
    if (mode == 2) gl_Position.z = max(gl_Position.z, -1.0);  // nearer the light than the map: flattened onto it
    vec2 tile = vec2(float(in_info.x % 8u), float(in_info.x / 8u));
    v_uv = (tile + INSET + CORNERS[in_info.y] * (1.0 - 2.0 * INSET)) / 8.0;
    v_face = int(in_info.z);
    v_kind = int(in_info.w);
    v_tile = int(in_info.x);
    v_tint = in_tint.rgb;
    v_ao = in_tint.a;
    v_pos = pos;
}
"""

# Lighting shared by the blocks and the distant terrain, so both look the same where one gives way
# to the other
BLOCK_SHADING = """
const float FACE_LIGHT[6] = float[](0.8, 0.8, 1.0, 0.55, 0.9, 0.9);  // share of the sky's light on each side
const float BOUNCE = 0.12;  // sunlight thrown back by the ground onto walls and undersides
float direct_light(vec3 pos, vec3 n) {  // facing the light, and not in a shadow
    float d = max(dot(n, light_dir), 0.0);
    if (d > 0.0 && shadows_on == 1) d *= block_shadow(pos, n);
    if (d > 0.0) d *= cloud_shadow(pos);
    return d;
}
// Far away a block covers only a few pixels: its texture would shimmer and make moire, so it
// turns into the average color of its tile (see tile_averages)
uniform sampler2D tile_avg;
uniform float px_per_block;  // size on screen of a block 1 block away, in pixels
vec3 far_albedo(vec3 albedo, int tile, vec3 tint, float dist) {
    vec4 plain = texelFetch(tile_avg, ivec2(tile, 0), 0), tinted = texelFetch(tile_avg, ivec2(tile, 1), 0);
    vec3 average = plain.rgb * (1.0 - plain.a) + tinted.rgb * tint * plain.a;
    return mix(average, albedo, smoothstep(2.0, 6.0, px_per_block / dist));
}
vec3 shade_opaque(vec3 albedo, int face, float ao, float direct) {
    vec3 ambient = sky_light * FACE_LIGHT[face] + light_color * (face == 2 ? 0.0 : BOUNCE);
    return albedo * (ambient * ao + light_color * (direct * (0.6 + 0.4 * ao)));
}
// Water: see-through, reflecting the sky (more at grazing angles), with the sun glinting on waves.
// Returns the color with the fog, and how opaque it is.
vec4 shade_water(vec3 albedo, vec3 pos, int face, float direct) {
    float dist = length(pos);
    vec3 n = NORMALS[face];
    vec3 base = albedo * (sky_light + light_color * direct);
    vec3 view = pos / dist;
    if (dot(view, n) > 0.0)  // the surface seen from under the water
        return vec4(fog(base * 0.7, dist), 0.75);
    // The waves flatten out where a pixel covers several blocks of water (far away, or seen at a
    // grazing angle): smaller than a pixel, they would only make moire
    float footprint = dist * dist / (max(abs(pos.y), 0.5) * px_per_block);  // blocks per pixel, in depth
    vec3 wn = face == 2 ? normalize(mix(wave_normal(pos.xz), n, smoothstep(0.4, 1.5, footprint))) : n;
    float fresnel = 0.03 + 0.97 * pow(1.0 - max(dot(-view, wn), 0.0), 5.0);
    vec3 r = reflect(view, wn);
    float glint = pow(max(dot(r, light_dir), 0.0), 300.0) * (direct > 0.0 ? 1.0 : 0.0);
    vec3 color = mix(base, sky_color(r), fresnel) + light_color * (glint * 4.0);
    float f = fog_amount(dist);  // far away, the fog hides what's under the water too
    return vec4(mix(color, fog_color, f), mix(mix(0.6, 1.0, fresnel), 1.0, f));
}
"""

# Where the blocks give way to the distant terrain, and each level of it to the next: every cell
# picks a number once and for all, and the finer version is drawn there while the fade at its
# distance stays below that number. Far away fewer and fewer cells are left, never a sharp line.
CELLS = """
uniform ivec2 cam_cell;    // the camera's cell (2x2 columns)
uniform vec2 cam_in_cell;  // the camera's x and z inside it
uniform vec2 block_fade;   // distances where the fade begins and ends
float cell_hash(ivec2 c, int level) {
    uint h = uint(c.x) * 0x8da6b343u ^ uint(c.y) * 0xd8163841u ^ uint(level) * 0xcb1ab31fu;
    h ^= h >> 16; h *= 0x7feb352du; h ^= h >> 15; h *= 0x846ca68bu; h ^= h >> 16;
    return float(h >> 8) / 16777216.0;
}
ivec2 cell_of(vec2 xz) { return cam_cell + ivec2(floor((xz + cam_in_cell) / 2.0)); }  // xz relative to the camera
float block_fade_at(ivec2 cell) {  // 0 near the camera, 1 where only the distant terrain is left
    vec2 center = vec2(cell - cam_cell) * 2.0 + 1.0 - cam_in_cell;
    return smoothstep(block_fade.x, block_fade.y, length(center));
}
bool drawn_as_blocks(ivec2 cell) { return cell_hash(cell, 0) >= block_fade_at(cell); }
"""

BLOCK_FRAGMENT_SHADER = """
#version 330
uniform sampler2D atlas;
uniform int mode;
in vec2 v_uv;
in vec3 v_pos;
in vec3 v_tint;
in float v_ao;
flat in int v_face;
flat in int v_kind;
flat in int v_tile;
out vec4 out_color;
""" + LIGHT + CLOUDS + SHADOWS + WAVES + BLOCK_SHADING + CELLS + """
void main() {
    vec4 tex = texture(atlas, v_uv);
    if (tex.a < 0.5 && (v_kind == 1 || (v_kind == 3 && mode == 2))) discard;  // see-through texel
    if (mode == 2) return;  // shadow map: only the depth counts
    vec3 n = NORMALS[v_face];
    if (!drawn_as_blocks(cell_of(v_pos.xz - n.xz * 0.01))) discard;  // the distant terrain shows here
    vec3 albedo = tex.rgb;
    if (tex.a > 0.5 && tex.a < 0.9) albedo *= v_tint;  // texel colored by the biome
    if (v_kind == 3 && tex.a < 0.5) albedo *= v_tint * 0.4;  // a hole in leaves: the shaded leaves inside
    if (v_kind != 1) albedo = far_albedo(albedo, v_tile, v_tint, length(v_pos));
    float direct = direct_light(v_pos, n);
    if (mode == 0)
        out_color = vec4(fog(shade_opaque(albedo, v_face, v_ao, direct), length(v_pos)), 1.0);
    else
        out_color = shade_water(albedo, v_pos, v_face, direct);
}
"""

# --- Distant terrain: mode 0 the colors, 1 the shadow maps ---------------------------------------

LOD_VERTEX_SHADER = """
#version 330
uniform mat4 vp;
uniform usampler2D data;     // grid_size x grid_size, wrapping: heights and blocks of each grid point
uniform sampler2D colors;    // same layout: the biome's color of the grass (or of the water)
uniform ivec2 grid_origin;   // grid coordinates of point (0, 0)
uniform vec2 origin;         // its position relative to the camera (x, z)
uniform float cam_y;
uniform float spacing;
uniform int grid_size;       // grid points per side (a power of two); grid_size - 1 columns are drawn
uniform int mode;
uniform int level;
uniform vec4 inner;          // square of the finer level (relative to the camera: min x, min z, max x, max z)
uniform int fade_inner;      // 1 when a finer level is drawn: give way to it, cell by cell
uniform vec4 own;            // this level's square
uniform int fade_own;        // 1 when a coarser level takes over at the edge of this one
uniform int use_ready;       // leave out what the blocks draw (not in the shadow maps)
uniform vec4 clip_planes[3]; // left, right and near planes of vp: nothing is drawn outside them
uniform sampler2D ready;     // 64x64 wrapping map of the chunk columns drawn as blocks
uniform ivec2 cam_chunk;
uniform vec2 cam_in_chunk;
in vec3 in_pos;              // unit cube corner: x, z in {0, 1}; y = 1 on top, 0 down a side
in vec3 in_norm;             // the face's axis-aligned normal
out vec3 v_pos;
flat out int v_face;
flat out ivec3 v_blocks;     // top block, the block under it, crown leaves (0: no tree)
flat out vec3 v_tint;
flat out float v_depth;      // depth of the water over the bottom
flat out vec2 v_tops;        // heights of the ground and of the column (with its crown), in the world
flat out float v_bottom;     // a side: height of the column it faces
flat out ivec2 v_local;      // the column's cell in the grid, for the top's ambient occlusion
flat out vec2 v_corner;      // the column's corner, relative to the camera
""" + BLOCK_IDS + CELLS + """
const int FACE_OF[6] = int[](0, 1, 2, 4, 5, 3);  // in_norm -> face number (+x -x +y +z -z)
// A grid point's texel: height of the top surface (as float bits), then the 4 packed bytes
// (top block, block under it, crown leaves or 0, crown height)
uvec4 data_at(ivec2 local) { return texelFetch(data, (grid_origin + local) & (grid_size - 1), 0); }
float height_of(uvec4 d) { return uintBitsToFloat(d.x); }
ivec4 blocks_of(uvec4 d) { return ivec4(d.y & 255u, (d.y >> 8) & 255u, (d.y >> 16) & 255u, d.y >> 24); }
float height_at(ivec2 local) { return height_of(data_at(local)); }
// The very top of a column: the terrain at its corner plus its crown of leaves, if it has one
float column_top(ivec2 cell) {
    uvec4 d = data_at(cell);
    return height_of(d) + (((d.y >> 16) & 255u) != 0u ? float(d.y >> 24) : 0.0);
}
float level_fade(vec2 center, vec4 rect, float fine) {  // 1 at the edge of a finer level's square, 0 well inside
    float d = min(min(center.x - rect.x, rect.z - center.x), min(center.y - rect.y, rect.w - center.y));
    return 1.0 - clamp((d - %(margin)d.0 * fine) / (%(band)d.0 * fine), 0.0, 1.0);
}
void main() {
    // One instance per cell of the grid: a square column of blocks, like Distant Horizons
    ivec2 local = ivec2(gl_InstanceID %% (grid_size - 1), gl_InstanceID / (grid_size - 1));
    ivec2 g = grid_origin + local;
    vec2 center = origin + (vec2(local) + 0.5) * spacing;
    // Is this cell drawn by this level? Each 2x2 group of its cells is drawn either by this level
    // or by the next, coarser one: both pick it with the same number
    bool keep = true, band = false;
    if (fade_inner == 1) {
        float f = level_fade(center, inner, spacing * 0.5);
        keep = cell_hash(g, level) < f;
        band = f > 0.0 && f < 1.0;
    }
    if (fade_own == 1) {
        ivec2 parent = g >> 1;
        float f = level_fade(origin + (vec2(parent * 2 - grid_origin) + 1.0) * spacing, own, spacing);
        keep = keep && cell_hash(parent, level + 1) >= f;
        band = band || (f > 0.0 && f < 1.0);
    }
    float dist = length(center);
    if (use_ready == 1 && dist + 0.71 * spacing < block_fade.x) {  // the blocks hide it all
        ivec2 rel = ivec2(floor((center + cam_in_chunk) / 16.0));
        if (abs(rel.x) < 32 && abs(rel.y) < 32 && texelFetch(ready, (cam_chunk + rel) & 63, 0).r > 0.5) keep = false;
    }
    band = band || (dist > block_fade.x && dist < block_fade.y + 2.0 * spacing);
    // Nothing of the column reaches the view if a box one cell wide and as tall as the world is
    // outside one of the planes. The box is generous on purpose: the missing vertices can only
    // hide things that no pixel would have shown anyway
    vec3 ctr = vec3(center.x, 2048.0 - cam_y, center.y);
    for (int i = 0; i < 3; i++) {
        vec4 pl = clip_planes[i];
        if (dot(pl.xyz, ctr) + pl.w < -((abs(pl.x) + abs(pl.z)) * 0.71 * spacing + abs(pl.y) * 2048.0))
            keep = false;
    }
    if (!keep) {
        gl_Position = vec4(2.0, 2.0, 2.0, 1.0);  // every vertex at the same place outside the view: nothing drawn
        return;
    }
    uvec4 own_data = data_at(local);
    ivec4 b = blocks_of(own_data);
    float ground = height_of(own_data);
    // Bare rock where it is too steep for soil (snow on the peaks holds a little longer)
    float h00 = ground, h10 = height_at(local + ivec2(1, 0));
    float h01 = height_at(local + ivec2(0, 1)), h11 = height_at(local + ivec2(1, 1));
    float slope = (max(max(h00, h10), max(h01, h11)) - min(min(h00, h10), min(h01, h11))) / spacing;
    bool soil = b.x == GRASS || b.x == PODZOL || b.x == MUD || b.x == DIRT || b.x == GRAVEL || (b.x == SNOW && b.y == DIRT);
    if ((slope >= 2.0 && soil) || (slope >= 4.0 && b.x == SNOW)) { b.x = STONE; b.y = STONE; b.z = 0; }
    float top = ground + (b.z != 0 ? float(b.w) : 0.0);
    // A side goes down to the top of the column it faces (or becomes a skirt outside the grid),
    // and folds away when that column is higher. Where two levels or the blocks share the cells,
    // the neighbor may be drawn by the other one: then every side goes down a bit further.
    ivec2 ncell = local + ivec2(int(in_norm.x), int(in_norm.z));
    float neighbor = top;
    if (in_norm.y == 0.0)
        neighbor = (min(ncell.x, ncell.y) < 0 || max(ncell.x, ncell.y) >= grid_size - 1)
                 ? top - 4.0 * spacing : column_top(ncell);
    float y = top;
    if (in_pos.y < 0.5) {
        if (band) y = min(neighbor, top) - spacing;
        else if (neighbor < top) y = neighbor - 0.5;
    }
    vec3 pos = vec3(origin.x + (float(local.x) + in_pos.x) * spacing, y - cam_y,
                    origin.y + (float(local.y) + in_pos.z) * spacing);
    v_pos = pos;
    gl_Position = vp * vec4(pos, 1.0);
    if (mode == 1) {
        gl_Position.z = max(gl_Position.z, -1.0);  // nearer the light than the map: flattened onto it
        return;
    }
    int axis = in_norm.x > 0.5 ? 0 : in_norm.x < -0.5 ? 1 : in_norm.y > 0.5 ? 2 : in_norm.z > 0.5 ? 3 : 4;
    v_face = FACE_OF[axis];
    v_blocks = b.xyz;
    vec4 c = texelFetch(colors, g & (grid_size - 1), 0);
    v_tint = c.rgb;
    v_depth = c.a * 255.0;
    v_tops = vec2(ground, top);
    v_bottom = neighbor;
    v_corner = origin + vec2(local) * spacing;
    v_local = local;  // the fragment shader works out which columns around are taller
}
""" % {"margin": LOD_MARGIN, "band": LOD_BAND}

LOD_FRAGMENT_SHADER = """
#version 330
uniform int mode;
uniform float cam_y;
uniform float spacing;
uniform vec2 cam_frac;       // the camera's x and z, modulo 256: where a block starts
uniform float cam_x;         // the camera's x (the badlands' layers shift at x = 0)
uniform sampler2D atlas;
uniform usampler2D data;     // the level's grid: heights and blocks (see the vertex shader)
uniform ivec2 grid_origin;
uniform int grid_size;
in vec3 v_pos;
flat in int v_face;
flat in ivec3 v_blocks;
flat in vec3 v_tint;
flat in float v_depth;
flat in vec2 v_tops;
flat in float v_bottom;
flat in ivec2 v_local;
flat in vec2 v_corner;
out vec4 out_color;
""" + LIGHT + CLOUDS + SHADOWS + WAVES + BLOCK_SHADING + BLOCK_IDS + BLOCK_TILES_GLSL + BANDS_GLSL + """
// The very top of the column of a cell: worked out per pixel, only where a top needs its ambient
// occlusion — a cell is a few pixels wide at the distances where the cost matters
float lod_top(ivec2 cell) {
    uvec4 d = texelFetch(data, (grid_origin + cell) & (grid_size - 1), 0);
    return uintBitsToFloat(d.x) + (((d.y >> 16) & 255u) != 0u ? float(d.y >> 24) : 0.0);
}
void main() {
    if (mode == 1) return;  // shadow map: only the depth counts
    // Which block this point of the column is, like the generator stacks them
    vec3 w = vec3(v_pos.x + cam_frac.x, v_pos.y + cam_y, v_pos.z + cam_frac.y);
    float ground = v_tops.x;
    int block;
    if (v_face == 2) block = v_blocks.z != 0 ? v_blocks.z : v_blocks.x;
    else if (v_blocks.z != 0 && w.y > ground + 0.001) block = v_blocks.z;
    else if (w.y > ground - 1.0) block = v_blocks.x;
    else {
        float depth = ground - w.y;
        block = depth < 4.0 ? v_blocks.y : STONE;
        if (v_blocks.y == TERRACOTTA && v_blocks.x == RED_SAND && depth < 41.0) {
            int y = int(floor(w.y)) + 7 * (cam_x + v_pos.x < 0.0 ? -1 : cam_x + v_pos.x < 16.0 ? 0 : 1);
            block = BANDS[((y %% %(bands)d) + %(bands)d) %% %(bands)d];
        }
    }
    // The texture repeats on every block, as on the blocks near the camera
    vec3 f = fract(w);
    vec2 uv = v_face == 2 ? f.xz : v_face == 0 ? vec2(f.z, 1.0 - f.y) : v_face == 1 ? vec2(1.0 - f.z, 1.0 - f.y)
            : v_face == 4 ? vec2(1.0 - f.x, 1.0 - f.y) : vec2(f.x, 1.0 - f.y);
    int tile = BLOCK_TILES[block * 6 + v_face];
    bool leaves = block == LEAVES || block == SPRUCE_LEAVES || block == BIRCH_LEAVES || block == JUNGLE_LEAVES
                  || block == ACACIA_LEAVES;
    vec3 tint = block == GRASS || block == WATER ? v_tint
              : (block == LEAVES || block == JUNGLE_LEAVES || block == ACACIA_LEAVES) ? v_tint * vec3(0.68, 0.78, 0.66)
              : vec3(1.0);
    ivec2 texel = ivec2(tile %% 8, tile / 8) * 16 + min(ivec2(uv * 16.0), 15);
    vec4 tex = texelFetch(atlas, texel, 0);
    vec3 albedo = tex.rgb;
    if (tex.a > 0.5 && tex.a < 0.9) albedo *= tint;  // texel colored by the biome
    if (leaves && tex.a < 0.5) albedo *= tint * 0.4;  // a hole in leaves: the shaded leaves inside
    float dist = length(v_pos);
    albedo = far_albedo(albedo, tile, tint, dist);
    // Ambient occlusion like the blocks': darker within a block of a taller column around
    float ao = 1.0;
    if (v_face == 2) {
        int taller = 0;  // which of the 8 columns around are taller (bits: +x -x +z -z, then corners)
        const ivec2 AROUND[8] = ivec2[](ivec2(1, 0), ivec2(-1, 0), ivec2(0, 1), ivec2(0, -1),
                                        ivec2(1, 1), ivec2(-1, 1), ivec2(1, -1), ivec2(-1, -1));
        for (int i = 0; i < 8; i++) {
            ivec2 c = v_local + AROUND[i];
            if (min(c.x, c.y) >= 0 && max(c.x, c.y) <= grid_size - 2 && lod_top(c) > v_tops.y + 0.5)
                taller |= 1 << i;
        }
        vec2 p = v_pos.xz - v_corner;  // inside the column, in blocks
        bool east = p.x > spacing * 0.5, south = p.y > spacing * 0.5;
        float dx = east ? spacing - p.x : p.x, dz = south ? spacing - p.y : p.y;
        int c1 = east ? 0 : 1, c2 = south ? 2 : 3;
        #define occluded(bit, d) ((((taller >> (bit)) & 1) == 1) ? 1.0 - clamp(d, 0.0, 1.0) : 0.0)
        float s1 = occluded(c1, dx), s2 = occluded(c2, dz);
        float d = occluded(4 + c1 + (south ? 0 : 2), max(dx, dz));
        ao = 0.5 + (3.0 - clamp(s1 + s2 + max(d, s1 * s2), 0.0, 3.0)) / 6.0;
        #undef occluded
    } else if (v_bottom < v_tops.y) {
        ao = 0.5 + (3.0 - (1.0 - clamp(v_pos.y + cam_y - v_bottom, 0.0, 1.0))) / 6.0;
    }
    vec3 n = NORMALS[v_face];
    float direct = direct_light(v_pos, n);
    if (block == WATER && v_face == 2) {  // the bottom seen through the water, as with the blocks
        vec4 c = shade_water(albedo, v_pos, 2, direct);
        int bed = BLOCK_TILES[v_blocks.y * 6 + 2];
        vec3 p = v_pos - vec3(0.0, v_depth, 0.0);
        vec3 bed_albedo = far_albedo(texelFetch(atlas, ivec2(bed %% 8, bed / 8) * 16 + min(ivec2(uv * 16.0), 15), 0).rgb,
                                     bed, vec3(1.0), dist);
        vec3 bottom = fog(shade_opaque(bed_albedo, 2, 1.0, direct_light(p, n)), length(p));
        out_color = vec4(mix(bottom, c.rgb, c.a), 1.0);
    } else {
        out_color = vec4(fog(shade_opaque(albedo, v_face, ao, direct), dist), 1.0);
    }
}
""" % {"bands": len(T.BANDS)}

SKY_FRAGMENT_SHADER = """
#version 330
uniform mat4 inv_vp;
uniform float night;    // 1 when the stars are out
uniform float sky_fog;  // 1 under water: only the fog's color
in vec2 v_ndc;
out vec4 out_color;
""" + LIGHT + """
void main() {
    vec4 far = inv_vp * vec4(v_ndc, 1.0, 1.0);
    vec4 near = inv_vp * vec4(v_ndc, -1.0, 1.0);
    vec3 dir = normalize(far.xyz / far.w - near.xyz / near.w);
    vec3 color = sky_color(dir);
    if (night > 0.0 && dir.y > 0.0) {  // stars: a few cells of a fine grid of directions light up
        vec3 p = dir * 300.0;
        vec3 cell = floor(p);
        float h = fract(sin(dot(cell, vec3(127.1, 311.7, 74.7))) * 43758.5453);
        if (h > 0.996) {
            float glow = smoothstep(0.5, 0.0, length(p - cell - 0.5)) * (h - 0.996) / 0.004;
            color += vec3(0.85, 0.88, 1.0) * (night * glow * min(dir.y * 5.0, 1.0));
        }
    }
    // Square sun and moon, like Minecraft's
    vec3 side = normalize(cross(sun_dir, vec3(0.0, 0.0, 1.0)));
    vec3 up = cross(side, sun_dir);
    if (dot(dir, sun_dir) > 0.0 && max(abs(dot(dir, side)), abs(dot(dir, up))) < 0.04)
        color = mix(vec3(1.5, 0.75, 0.35), vec3(1.6, 1.5, 1.1), smoothstep(-0.05, 0.3, sun_dir.y));
    if (dot(dir, -sun_dir) > 0.0 && max(abs(dot(dir, side)), abs(dot(dir, up))) < 0.03)
        color = vec3(0.9, 0.9, 1.0);
    out_color = vec4(mix(color, fog_color, sky_fog), 1.0);
}
"""

CLOUD_VERTEX_SHADER = """
#version 330
uniform mat4 vp;
uniform float cloud_height;
in vec2 in_pos;
out vec3 v_pos;
void main() {
    v_pos = vec3(in_pos.x * %(extent).1f, cloud_height, in_pos.y * %(extent).1f);
    gl_Position = vp * vec4(v_pos, 1.0);
}
""" % {"extent": CLOUD_EXTENT}

CLOUD_FRAGMENT_SHADER = """
#version 330
uniform int near_pass;      // drawn twice: far away with the distant terrain, nearby after the blocks
uniform float near_radius;
in vec3 v_pos;
out vec4 out_color;
""" + LIGHT + CLOUDS + """
void main() {
    if ((near_pass == 1) != (length(v_pos.xz) < near_radius)) discard;
    // The clouds are a slab cloud_height +/- CLOUD_HALF thick: accumulate the noise density along
    // the view ray inside it, with a profile that peaks in the middle of the slab, so the clouds
    // look puffy from every side and fade out at their edges
    vec3 dir = normalize(v_pos);
    float a = (cloud_height - CLOUD_HALF) / dir.y, b = (cloud_height + CLOUD_HALF) / dir.y;
    float lo = max(min(a, b), 0.0), hi = min(max(a, b), lo + 4.0 * CLOUD_THICK);
    if (hi <= lo) discard;
    float d = 0.0;
    for (int i = 0; i < 6; i++) {
        vec3 p = dir * mix(lo, hi, (float(i) + 0.5) / 6.0);
        float u = clamp((p.y - cloud_height + CLOUD_HALF) / CLOUD_THICK, 0.0, 1.0);
        d += cloud_density(p.xz) * u * (1.0 - u) * 4.0;
    }
    float tau = d / 6.0 * clamp((hi - lo) / CLOUD_THICK, 0.0, 1.5);
    d = 1.0 - exp(-tau * 3.5);
    if (d < 0.005) discard;
    vec3 lit = sky_light * 1.1 + light_color * (0.4 + 0.8 * max(light_dir.y, 0.0));
    // From below, the thick middle of a cloud is darker than its edges
    vec3 color = cloud_height > 0.0 ? mix(lit, sky_light * 0.9 + light_color * 0.2, 0.7 * d) : lit;
    float dist = length(v_pos);
    out_color = vec4(fog(color, dist), 0.92 * d);
}
"""

OUTLINE_VERTEX_SHADER = """
#version 330
uniform mat4 vp;
in vec3 in_pos;
void main() { gl_Position = vp * vec4(in_pos, 1.0); }
"""

OUTLINE_FRAGMENT_SHADER = """
#version 330
out vec4 out_color;
void main() { out_color = vec4(0.0, 0.0, 0.0, 1.0); }
"""

# --- Palette -----------------------------------------------------------------------------------

POST_FRAGMENT_SHADER = """
#version 330
uniform sampler2D scene;
uniform sampler2D palette;  // 256x1: each palette color in OKLab
uniform usampler2D lut;     // 32x32x32 colors -> the two palette colors to dither between
out float index;
""" + OKLAB + FINISH + """
int bayer8(ivec2 p) {  // ordered dithering threshold, 0-63
    int xy = p.x ^ p.y, v = 0;
    for (int i = 0; i < 3; i++) v = (v << 2) | (((xy >> i) & 1) << 1) | ((p.y >> i) & 1);
    return v;
}
void main() {
    ivec2 p = ivec2(gl_FragCoord.xy);
    vec3 c = finish(texelFetch(scene, p, 0).rgb);
    ivec3 cell = ivec3(c * 31.0 + 0.5);
    uvec2 pair = texelFetch(lut, ivec2(cell.r + 32 * (cell.b & 7), cell.g + 32 * (cell.b >> 3)), 0).rg;
    vec3 lab = oklab(c);
    vec3 a = texelFetch(palette, ivec2(int(pair.x), 0), 0).rgb;
    vec3 ab = texelFetch(palette, ivec2(int(pair.y), 0), 0).rgb - a;
    float t = clamp(dot(lab - a, ab) / max(dot(ab, ab), 1e-8), 0.0, 1.0);  // share of the second color
    uint chosen = (float(bayer8(p & 7)) + 0.5) / 64.0 < t ? pair.y : pair.x;
    index = float(chosen) / 255.0;
}
"""

LUT_FRAGMENT_SHADER = """
#version 330
uniform sampler2D palette;
uniform float mix_penalty;
out uvec2 pair;
""" + OKLAB + """
void main() {
    // This texel's color: 32 levels of red and green, and blue in 8 x 4 tiles
    ivec2 p = ivec2(gl_FragCoord.xy);
    vec3 lab = oklab(vec3(float(p.x & 31), float(p.y & 31), float((p.x >> 5) + 8 * (p.y >> 5))) / 31.0);
    // The 4 nearest palette colors
    float d0 = 1e9, d1 = 1e9, d2 = 1e9, d3 = 1e9;
    int i0 = 0, i1 = 0, i2 = 0, i3 = 0;
    for (int i = 0; i < 256; i++) {
        vec3 q = texelFetch(palette, ivec2(i, 0), 0).rgb - lab;
        float d = dot(q, q);
        if (d >= d3) continue;
        if (d < d2) {
            d3 = d2; i3 = i2;
            if (d < d1) {
                d2 = d1; i2 = i1;
                if (d < d0) { d1 = d0; i1 = i0; d0 = d; i0 = i; } else { d1 = d; i1 = i; }
            } else { d2 = d; i2 = i; }
        } else { d3 = d; i3 = i; }
    }
    // The nearest alone, or the pair that mixes best into this color (close pairs preferred:
    // dithering between very different colors looks noisy)
    int ids[4] = int[](i0, i1, i2, i3);
    vec3 cols[4];
    for (int k = 0; k < 4; k++) cols[k] = texelFetch(palette, ivec2(ids[k], 0), 0).rgb;
    float best = d0;
    int ba = i0, bb = i0;
    for (int a = 0; a < 3; a++) {
        for (int b = a + 1; b < 4; b++) {
            vec3 ab = cols[b] - cols[a];
            float len2 = max(dot(ab, ab), 1e-8);
            float t = clamp(dot(lab - cols[a], ab) / len2, 0.0, 1.0);
            vec3 e = lab - cols[a] - t * ab;
            float err = dot(e, e) + mix_penalty * t * (1.0 - t) * len2;
            if (err < best) { best = err; ba = ids[a]; bb = ids[b]; }
        }
    }
    pair = uvec2(ba, bb);
}
"""

SAMPLE_FRAGMENT_SHADER = """
#version 330
uniform sampler2D scene;
uniform int frame;
out vec4 sample_lab;
""" + OKLAB + FINISH + """
uint hash(uint x) {
    x ^= x >> 16; x *= 0x7feb352du; x ^= x >> 15; x *= 0x846ca68bu; x ^= x >> 16;
    return x;
}
void main() {
    // One pixel in each cell of a 64x64 grid over the frame, at a different place every time
    ivec2 q = ivec2(gl_FragCoord.xy);
    ivec2 size = textureSize(scene, 0);
    ivec2 cell = max(size / %(n)d, ivec2(1));
    uint h = hash(uint(q.x + %(n)d * q.y) * 1664525u + uint(frame) * 1013904223u);
    ivec2 p = q * size / %(n)d + ivec2(int(h %% uint(cell.x)), int((h >> 16) %% uint(cell.y)));
    sample_lab = vec4(oklab(finish(texelFetch(scene, p, 0).rgb)), 1.0);
}
""" % {"n": SAMPLES}

ACCUMULATE_VERTEX_SHADER = """
#version 330
uniform sampler2D samples;
uniform sampler2D palette;
out vec4 v_sum;
out vec4 v_square;
void main() {
    // One point per sample, sent to the column of its nearest palette color
    vec3 lab = texelFetch(samples, ivec2(gl_VertexID %% %(n)d, gl_VertexID / %(n)d), 0).rgb;
    float best = 1e9;
    int index = 0;
    for (int i = 0; i < 256; i++) {
        vec3 q = texelFetch(palette, ivec2(i, 0), 0).rgb - lab;
        float d = dot(q, q);
        if (d < best) { best = d; index = i; }
    }
    gl_Position = vec4((float(index) + 0.5) / 128.0 - 1.0, 0.0, 0.0, 1.0);
    v_sum = vec4(lab, 1.0);
    v_square = vec4(lab * lab, best);
}
""" % {"n": SAMPLES}

ACCUMULATE_FRAGMENT_SHADER = """
#version 330
in vec4 v_sum;
in vec4 v_square;
layout(location = 0) out vec4 sum;     // added up: OKLab of the samples, and their number
layout(location = 1) out vec4 square;  // their squares, and their squared distance to the color
void main() { sum = v_sum; square = v_square; }
"""

CUBE_EDGES = [(0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4), (0, 4), (1, 5), (2, 6), (3, 7)]

# Distant terrain: the leaves of each biome's trees, and how high their crowns reach above the
# ground (the average of its kinds of trees, weighted by how many there are)
CANOPY_LEAVES = np.full(len(T.BIOME_NAMES), LEAVES)
CANOPY_LEAVES[[T.TAIGA, T.SNOWY_TAIGA, T.SNOWY_TUNDRA, T.ALPINE]] = SPRUCE_LEAVES
CANOPY_LEAVES[T.BIRCH_FOREST] = BIRCH_LEAVES
CANOPY_LEAVES[T.JUNGLE] = JUNGLE_LEAVES
CANOPY_LEAVES[T.SAVANNA] = ACACIA_LEAVES
CROWN_ABOVE = {T.SPRUCE: 3, T.JUNGLE_TREE: 2}  # leaves above the trunk's top (1 for the other trees)
CANOPY_HEIGHT = np.zeros(len(T.BIOME_NAMES), np.uint8)
for _biome, _kinds in T.TREES.items():
    _tall = [(sum(T.TREE_HEIGHTS[k]) / 2 + CROWN_ABOVE.get(k, 1), w) for k, w in _kinds.items() if k != T.CACTUS_PLANT]
    if _tall:
        CANOPY_HEIGHT[_biome] = round(sum(h * w for h, w in _tall) / sum(w for _, w in _tall))
LEAF_TILES = {int(t) for b in ALL_LEAVES for t in BLOCK_TILES[b]}


def tile_averages(atlas):
    """(64, 2, 4) float array: for each atlas tile, the average of its texels that keep their own
    color (rgb) and the share of texels the biome colors (a), then the average of those (rgb).
    Far away, a block is smaller than a pixel: the distant terrain uses these instead of the texture.
    The holes in leaves count as the leaves behind them, in the shade."""
    out = np.zeros((ATLAS_TILES * ATLAS_TILES, 2, 4), np.float32)
    rgb, alpha = atlas[..., :3].astype(np.float32) / 255, atlas[..., 3]
    for t in range(ATLAS_TILES * ATLAS_TILES):
        ty, tx = divmod(t, ATLAS_TILES)
        cell = (slice(ty * TILE, (ty + 1) * TILE), slice(tx * TILE, (tx + 1) * TILE))
        c, a = rgb[cell].reshape(-1, 3), alpha[cell].ravel()
        tinted = a == TINT_ALPHA
        hole = a < 128
        c = np.where(hole[:, None], c * 0.4, c)  # see-through texels: the shaded leaves inside
        tinted |= hole & (t in LEAF_TILES)
        plain = ~tinted
        if plain.any():
            out[t, 0, :3] = c[plain].mean(axis=0)
        if tinted.any():
            out[t, 1, :3] = c[tinted].mean(axis=0)
        out[t, 0, 3] = tinted.mean()
    return out

# Triangles of a face, split along one diagonal or the other: along the brighter corners, so
# ambient occlusion shades the face evenly
FACE_TRIANGLES = np.array([0, 1, 2, 0, 2, 3], np.uint32)
FLIPPED_TRIANGLES = np.array([1, 2, 3, 1, 3, 0], np.uint32)


def srgb_to_oklab(rgb):
    """OKLab of sRGB colors (0-1), arrays of shape (..., 3)."""
    rgb = np.asarray(rgb, dtype=np.float64)
    c = np.where(rgb > 0.04045, ((rgb + 0.055) / 1.055) ** 2.4, rgb / 12.92)
    lms = np.cbrt(c @ np.array([[0.4122214708, 0.2119034982, 0.0883024619],
                                [0.5363325363, 0.6806995451, 0.2817188376],
                                [0.0514459929, 0.1073969566, 0.6299787005]]))
    return lms @ np.array([[0.2104542553, 1.9779984951, 0.0259040371],
                           [0.7936177850, -2.4285922050, 0.7827717662],
                           [-0.0040720468, 0.4505937099, -0.8086757660]])


def oklab_to_srgb(lab):
    """sRGB colors (0-1, clipped) of OKLab colors."""
    lms = np.asarray(lab, dtype=np.float64) @ np.array([[1.0, 1.0, 1.0],
                                                        [0.3963377774, -0.1055613458, -0.0894841775],
                                                        [0.2158037573, -0.0638541728, -1.2914855480]])
    c = (lms ** 3) @ np.array([[4.0767416621, -1.2684380046, -0.0041960863],
                               [-3.3077115913, 2.6097574011, -0.7034186147],
                               [0.2309699292, -0.3413193965, 1.7076147010]])
    c = np.clip(c, 0.0, 1.0)
    return np.where(c > 0.0031308, 1.055 * c ** (1 / 2.4) - 0.055, 12.92 * c)


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


def matrix_bytes(m):
    """A matrix in the column-major layout OpenGL expects."""
    return np.ascontiguousarray(np.asarray(m, dtype="f4").T).tobytes()


def set_uniforms(program, values):
    """Set the uniforms a program has among values (the others are skipped)."""
    for name, value in values.items():
        uniform = program.get(name, None)
        if uniform is None:
            continue
        if isinstance(value, np.ndarray):
            uniform.write(matrix_bytes(value))
        else:
            uniform.value = value


def cloud_texture(size=512, seed=3):
    """Tileable noise for the clouds: random noise with its fine detail filtered out (in the frequency
    domain, so it wraps around), then spread evenly over 0-1, so the cover is the share of clear sky."""
    rng = np.random.default_rng(seed)
    f = np.fft.fftfreq(size)
    k = np.hypot(*np.meshgrid(f, f, indexing="ij"))
    k[0, 0] = 1.0
    noise = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((size, size))) / k ** 1.4))
    ranks = np.argsort(np.argsort(noise.ravel()))
    return (ranks / (ranks.size - 1)).reshape(size, size).astype("f4")


# --- Block meshes ------------------------------------------------------------------------------

class ColumnMesh:
    def __init__(self):
        self.parts = {}  # cy -> vertices of that section (or None)
        self.vao = self.vbo = self.ibo = None
        self.y_range = (0, 0)
        self.solid = 0  # indices of the faces drawn first (all but water)
        self.water = 0  # indices of the water faces, which come after them

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
        self.version = 0  # counts the changes to the meshes (the shadow map is drawn again)
        self.in_view = []  # (mesh, (x, y, z) of its corner relative to the camera) seen in the last frame
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
        self.in_view = []
        self.version += 1
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
            self.version += 1
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
        self.version += 1
        parts = [p for p in mesh.parts.values() if p is not None]
        if parts:
            faces = np.concatenate(parts).reshape(-1, 4)
            water = faces["info"][:, 0, 3] == 2
            faces = faces[np.argsort(water, kind="stable")]  # the water faces last: drawn after the rest
            mesh.water = int(water.sum()) * 6
            mesh.solid = len(faces) * 6 - mesh.water
            ao = faces["tint"][:, :, 3].astype(np.int32)
            flip = (ao[:, 0] + ao[:, 2] < ao[:, 1] + ao[:, 3])[:, None]
            indices = (np.arange(len(faces), dtype=np.uint32)[:, None] * 4
                       + np.where(flip, FLIPPED_TRIANGLES, FACE_TRIANGLES))
            mesh.vbo = self.ctx.buffer(faces.tobytes())
            mesh.ibo = self.ctx.buffer(indices.astype(np.uint32).tobytes())
            mesh.vao = self.ctx.vertex_array(self.program, [(mesh.vbo, "3f 4u1 4f1", "in_pos", "in_info", "in_tint")],
                                             index_buffer=mesh.ibo, index_element_size=4)
            ys = faces["pos"][..., 1]
            mesh.y_range = (float(ys.min()), float(ys.max()))
        self.ready[key[1] % READY_SIZE, key[0] % READY_SIZE] = 255
        self.ready_changed = True

    def block_changed(self, x, y, z):
        """Rebuild the sections touching block (x, y, z) right away, and tell the workers."""
        self.builders.block_changed(x, y, z, self.world.get(x, y, z))
        # The block's section, and the sections next to it when it is on their border (diagonal
        # ones too: the shading of their corners depends on it)
        steps = [[0] + ([-1] if v % CHUNK == 0 else []) + ([1] if v % CHUNK == CHUNK - 1 else []) for v in (x, y, z)]
        cx, cy, cz = x >> 4, y >> 4, z >> 4
        todo = {(cx + a, cy + b, cz + c) for a in steps[0] for b in steps[1] for c in steps[2]}
        columns = set()
        for kx, ky, kz in todo:
            self.versions[(kx, kz)] = self.versions.get((kx, kz), 0) + 1
            mesh = self.meshes.get((kx, kz))
            if mesh is not None and 0 <= ky < WORLD_HEIGHT // CHUNK:
                mesh.parts[ky] = mesh_section(self.world, self.world.column(kx, kz), kx, ky, kz)
                columns.add((kx, kz))
        for key in columns:
            self.upload(key, self.meshes[key])

    def find_in_view(self, vp, cam):
        """The columns in view (kept for the water, drawn after everything else)."""
        drawn = [(k, m) for k, m in self.meshes.items() if m.vao is not None]
        if not drawn:
            self.in_view = []
            return 0
        corner = np.array([(k[0] * CHUNK - cam[0], m.y_range[0] - cam[1], k[1] * CHUNK - cam[2]) for k, m in drawn])
        size = np.array([(CHUNK, m.y_range[1] - m.y_range[0], CHUNK) for _, m in drawn])
        visible = boxes_visible(frustum_planes(vp), corner, corner + size)
        self.in_view = [(m, (float(ox), -cam[1], float(oz))) for (_, m), (ox, _, oz), show
                        in zip(drawn, corner, visible) if show]
        return len(self.in_view)

    def render(self, water=False):
        origin = self.program["origin"]
        for mesh, corner in self.in_view:
            if water and mesh.water:
                origin.value = corner
                mesh.vao.render(vertices=mesh.water, first=mesh.solid)
            elif not water and mesh.solid:
                origin.value = corner
                mesh.vao.render(vertices=mesh.solid)

    def render_shadow(self, cam):
        """Every column (for the shadow map: what is out of view can still cast a shadow into it)."""
        origin = self.program["origin"]
        for (cx, cz), mesh in self.meshes.items():
            if mesh.vao is not None and mesh.solid:
                origin.value = (cx * CHUNK - cam[0], -cam[1], cz * CHUNK - cam[2])
                mesh.vao.render(vertices=mesh.solid)


# --- Distant terrain ---------------------------------------------------------------------------

class FarTerrain:
    """The terrain beyond the blocks, as `levels` square grids of (size - 1)^2 columns around the
    camera, each twice as coarse and twice as wide as the one before (spacing to spacing x 2^levels
    blocks wide). Every column is drawn like a stack of blocks: the same blocks the generator puts
    there, with the same textures and light as the blocks near the camera, and trees as crowns of
    leaves. Heights, colors and blocks live in textures that wrap around: when the camera moves, only
    the new rows or columns at the edge are sampled. Each level gives way to the next one cell by
    cell (see CELLS). The LOD quality setting picks (spacing, size, levels) from LOD_QUALITIES."""

    def __init__(self, ctx, program, world, atlas_texture, atlas, spacing=2, size=128, levels=7):
        self.ctx, self.program, self.world, self.atlas = ctx, program, world, atlas_texture
        self.atlas_data = atlas  # kept to rebuild the tile averages if the quality changes
        self.spacing, self.size, self.n_levels = spacing, size, levels
        n = size
        # A unit cube (no bottom face: it is never seen), drawn once per cell of the grid. The
        # shader stretches each side down to the top of the column it faces.
        verts = []
        for normal, face in CUBE_FACES:
            verts += [corner + normal for corner in face]
        self.vbo = ctx.buffer(np.array(verts, dtype="f4").tobytes())
        self.vao = ctx.vertex_array(program, [(self.vbo, "3f 3f", "in_pos", "in_norm")])
        self.data_maps = [ctx.texture((n, n), 4, dtype="u4") for _ in range(levels)]
        self.color_maps = [ctx.texture((n, n), 4, dtype="f1") for _ in range(levels)]
        self.tile_avg = ctx.texture((ATLAS_TILES * ATLAS_TILES, 2), 4,
                                    tile_averages(atlas).transpose(1, 0, 2).tobytes(), dtype="f4")
        for tex in self.data_maps + self.color_maps + [self.tile_avg]:
            tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.origins = [None] * levels  # grid coordinates of each level's point (0, 0)
        self.queue = []  # texture writes still to do
        self.version = 0  # counts the changes (the shadow maps of the terrain are drawn again)
        self.view_distance = FAR_LIMIT  # beyond it the fog hides everything: no level drawn there

    def set_world(self, world):
        self.world = world
        self.origins = [None] * self.n_levels
        self.queue = []
        self.version += 1

    def sample(self, x, z, gx, gz, level):
        """At points (x, z), grid points (gx, gz) of a level: biome color (rgba) and the packed
        texel (height bits, then top block, the block under it, crown leaves or 0, crown height),
        for the textures."""
        gen = self.world.gen
        s = gen.sample(x, z)
        top = np.floor(s["height"]).astype(np.int32)
        height = np.maximum(top + 1, s["water"] + WATER_SURFACE).astype("f4")
        # The same top blocks as the generator's, but for the slope (the shader does the steep rock)
        surface, filler, _ = T._surface(s, top, np.zeros_like(top), gen.surface.fbm2(x / 9, z / 9, 2) * 2)
        grass, _, water = T.tints(s["temperature"], s["humidity"], s["biome"])
        wet = top < s["water"]
        ice = wet & (s["temperature"] < -0.55)
        filler = np.where(wet, surface, filler)  # the bottom under the water
        surface = np.where(wet, np.where(ice, ICE, WATER), surface)
        # Trees: a cell is under a crown as often as the biome's trees cover the ground
        biome = s["biome"]
        trees = (cell_hashes(gx, gz, level) < T.CANOPY[biome]) & ~wet & np.isin(surface, (B.GRASS, B.PODZOL, B.SNOW))
        leaves = np.where(trees, CANOPY_LEAVES[biome], 0)
        crown = np.where(trees, CANOPY_HEIGHT[biome], 0)
        color = np.where(wet[:, None], water, grass)
        depth = np.clip(np.where(wet, s["water"] - top, 0), 0, 255)  # the water's depth, down to the bottom
        rgba = np.concatenate([np.clip(color, 0, 1) * 255, depth[:, None]], axis=1).astype("u1")
        # One 4xu32 texel per grid point: the height's bits, then the 4 blocks packed in one word
        packed = (surface.astype("u4") | filler.astype("u4") << 8
                  | leaves.astype("u4") << 16 | crown.astype("u4") << 24)
        data = np.stack([height.astype("f4").view("u4"), packed,
                         np.zeros_like(packed), np.zeros_like(packed)], axis=1)
        return rgba, data

    def update(self, cam):
        n = self.size
        writes = []  # (level, grid xs, grid zs, texel u, texel v)
        for level in range(self.n_levels):
            spacing = self.spacing << level
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
        if any(len(w[1]) * len(w[2]) > n for w in self.queue):
            writes, self.queue = self.queue, []
        else:
            writes, self.queue = self.queue[:LOD_STRIPS_PER_FRAME], self.queue[LOD_STRIPS_PER_FRAME:]
        if not writes:
            return
        self.version += 1
        # Sample all the new points of all levels together: one big call is much faster than many
        grids = []
        for level, xs, zs, _, _ in writes:
            gz, gx = np.meshgrid(zs, xs, indexing="ij")  # texture rows are z
            grids.append((gx.ravel(), gz.ravel(), np.full(gx.size, level)))
        gx, gz, levels = (np.concatenate([g[i] for g in grids]) for i in range(3))
        spacing = (self.spacing << levels).astype(float)
        color, data = self.sample(gx * spacing, gz * spacing, gx, gz, levels)
        start = 0
        for level, xs, zs, u, v in writes:
            end = start + len(xs) * len(zs)
            viewport = (u, v, len(xs), len(zs))
            self.data_maps[level].write(data[start:end].tobytes(), viewport=viewport)
            self.color_maps[level].write(color[start:end].tobytes(), viewport=viewport)
            start = end

    def levels(self):
        """The levels to draw: up to the first that reaches past the view distance."""
        for level in range(self.n_levels):
            if (self.size // 2 - LOD_MARGIN) * (self.spacing << level) >= self.view_distance:
                return level + 1
        return self.n_levels

    def render(self, vp, cam, chunks, shadow=False):
        p = self.program
        p["vp"].write(matrix_bytes(vp))
        p["mode"] = 1 if shadow else 0
        p["cam_y"] = float(cam[1])
        p["use_ready"] = 0 if shadow else 1
        if not shadow:
            pcx, pcz = math.floor(cam[0] / CHUNK), math.floor(cam[2] / CHUNK)
            set_uniforms(p, {"cam_chunk": (pcx, pcz), "ready": READY_UNIT,
                             "cam_in_chunk": (float(cam[0] - pcx * CHUNK), float(cam[2] - pcz * CHUNK))})
            chunks.ready_texture.use(READY_UNIT)
        set_uniforms(p, {"data": DATA_UNIT, "colors": COLORS_UNIT,
                         "tile_avg": TILE_AVG_UNIT, "atlas": ATLAS_UNIT, "grid_size": self.size})
        p["clip_planes"].write(frustum_planes(vp)[[0, 1, 4]].astype("f4").tobytes())  # left right near
        self.atlas.use(ATLAS_UNIT)
        self.tile_avg.use(TILE_AVG_UNIT)
        count = self.levels()
        rects = []
        for level in range(count):
            spacing = self.spacing << level
            gx, gz = self.origins[level]
            ox, oz = gx * spacing - cam[0], gz * spacing - cam[2]
            extent = (self.size - 1) * spacing
            rects.append((float(ox), float(oz), float(ox + extent), float(oz + extent)))
        for level in range(count):
            spacing = self.spacing << level
            gx, gz = self.origins[level]
            set_uniforms(p, {"level": level, "grid_origin": (gx, gz), "origin": rects[level][:2],
                             "spacing": float(spacing), "own": rects[level], "fade_own": int(level < count - 1),
                             "inner": rects[level - 1] if level else (0.0, 0.0, 0.0, 0.0),
                             "fade_inner": int(level > 0)})
            self.data_maps[level].use(DATA_UNIT)
            self.color_maps[level].use(COLORS_UNIT)
            self.vao.render(vertices=30, instances=(self.size - 1) ** 2)


def cell_hashes(gx, gz, level):
    """A number in [0, 1) for each grid cell of a level, always the same (where trees grow)."""
    with np.errstate(over="ignore"):
        h = (np.asarray(gx).astype(np.uint64) * np.uint64(0x9E3779B97F4A7C15)
             ^ np.asarray(gz).astype(np.uint64) * np.uint64(0xC2B2AE3D27D4EB4F)
             ^ np.asarray(level).astype(np.uint64) * np.uint64(0x165667B19E3779F9))
        h ^= h >> np.uint64(33)
        h *= np.uint64(0xFF51AFD7ED558CCD)
        h ^= h >> np.uint64(33)
    return (h >> np.uint64(11)).astype(np.float64) / float(1 << 53)


# --- Shadows -----------------------------------------------------------------------------------

class ShadowMap:
    """How one shadow map was drawn: the light's direction and the map's square, fixed in the world
    (so it can be used as the camera moves, until it is drawn again)."""

    def __init__(self, light, half, cam, key, version):
        self.key, self.version, self.half, self.cam = key, version, half, cam
        # Axes of the light's view: right, up, and toward the light
        helper = np.array([0.0, 0.0, 1.0]) if abs(light[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        right = np.cross(helper, light)
        right /= np.linalg.norm(right)
        self.rotation = np.array([right, np.cross(light, right), light])
        # The square's center: the camera, snapped to whole texels so the shadows' edges stay still
        texel = 2 * half / SHADOW_SIZE
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

    def __init__(self, ctx, atlas):
        self.ctx, self.atlas = ctx, atlas
        self.textures, self.fbos = [], []
        for _ in range(3):
            tex = ctx.depth_texture((SHADOW_SIZE, SHADOW_SIZE))
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
        for i in range(3):
            old = self.maps[i]
            if (old is not None and old.key == key and old.version == versions[i] and old.half == halves[i]
                    and math.hypot(cam[0] - old.cam[0], cam[2] - old.cam[2]) < 0.15 * halves[i]
                    and abs(cam[1] - old.cam[1]) < 0.5 * SHADOW_DEPTH):
                continue
            if i > 0 and None in far.origins:
                continue
            new = ShadowMap(light, halves[i], cam, key, versions[i])
            self.maps[i] = new
            self.draw(i, new.matrix(cam), cam, chunks, far, block_program, lod_program)
        values = {"shadow_texel": tuple(2 * h / SHADOW_SIZE for h in halves)}
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
            block_program["mode"] = 2
            block_program["vp"].write(matrix_bytes(vp))
            chunks.render_shadow(cam)
        else:
            far.render(vp, cam, chunks, shadow=True)
        ctx.polygon_offset = (0.0, 0.0)

    def use(self):
        for tex, unit in zip(self.textures, SHADOW_UNITS):
            tex.use(unit)


# --- Palette -----------------------------------------------------------------------------------

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
        self.lut_program = ctx.program(vertex_shader=FULLSCREEN_VERTEX_SHADER, fragment_shader=LUT_FRAGMENT_SHADER)
        self.lut_vao = ctx.vertex_array(self.lut_program, [(quad, "2f", "in_pos")])
        self.sample_program = ctx.program(vertex_shader=FULLSCREEN_VERTEX_SHADER,
                                          fragment_shader=SAMPLE_FRAGMENT_SHADER)
        self.sample_vao = ctx.vertex_array(self.sample_program, [(quad, "2f", "in_pos")])
        self.accumulate_program = ctx.program(vertex_shader=ACCUMULATE_VERTEX_SHADER,
                                              fragment_shader=ACCUMULATE_FRAGMENT_SHADER)
        self.accumulate_vao = ctx.vertex_array(self.accumulate_program, [])

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


# --- Renderer ----------------------------------------------------------------------------------

class Renderer:
    def __init__(self, ctx, world, atlas, width, height, fixed_colors, fov=70):
        """ctx must be created before pyxel.init, so Pyxel's own OpenGL context ends up current.
        fixed_colors: the first 64 colors of the palette (0xRRGGBB), which never change."""
        self.ctx = ctx
        self.fov = fov
        self.size = None
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
            self.program = ctx.program(vertex_shader=BLOCK_VERTEX_SHADER, fragment_shader=BLOCK_FRAGMENT_SHADER)
            self.lod_program = ctx.program(vertex_shader=LOD_VERTEX_SHADER, fragment_shader=LOD_FRAGMENT_SHADER)
            self.sky_program = ctx.program(vertex_shader=FULLSCREEN_VERTEX_SHADER, fragment_shader=SKY_FRAGMENT_SHADER)
            self.cloud_program = ctx.program(vertex_shader=CLOUD_VERTEX_SHADER, fragment_shader=CLOUD_FRAGMENT_SHADER)
            self.outline_program = ctx.program(
                vertex_shader=OUTLINE_VERTEX_SHADER, fragment_shader=OUTLINE_FRAGMENT_SHADER)
            self.post_program = ctx.program(vertex_shader=FULLSCREEN_VERTEX_SHADER,
                                            fragment_shader=POST_FRAGMENT_SHADER)
            self.texture = ctx.texture((atlas.shape[1], atlas.shape[0]), 4, atlas.tobytes())
            self.texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
            self.clouds = ctx.texture((512, 512), 1, cloud_texture().tobytes(), dtype="f4")
            self.clouds.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
            self.clouds.build_mipmaps()
            quad = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype="f4").tobytes())
            self.sky_vao = ctx.vertex_array(self.sky_program, [(quad, "2f", "in_pos")])
            self.cloud_vao = ctx.vertex_array(self.cloud_program, [(quad, "2f", "in_pos")])
            self.post_vao = ctx.vertex_array(self.post_program, [(quad, "2f", "in_pos")])
            self.outline_vbo = ctx.buffer(reserve=24 * 3 * 4)
            self.outline_vao = ctx.vertex_array(self.outline_program, [(self.outline_vbo, "3f", "in_pos")])
            self.chunks = Chunks(ctx, self.program, world)
            self.far = FarTerrain(ctx, self.lod_program, world, self.texture, atlas,
                                  *LOD_QUALITIES[LOD_QUALITY_NAMES[0]])
            self.shadows = Shadows(ctx, self.texture)
            self.palette = Palette(ctx, fixed)
            self.palette.apply()
            for p in (self.program, self.lod_program, self.cloud_program):
                set_uniforms(p, {"atlas": ATLAS_UNIT, "clouds": CLOUDS_UNIT, "tile_avg": TILE_AVG_UNIT,
                                 "shadow_near": SHADOW_UNITS[0],
                                 "shadow_mid": SHADOW_UNITS[1], "shadow_far": SHADOW_UNITS[2]})
        self.world = world
        self.resize(width, height)

    def resize(self, width, height):
        """Draw frames of a new size (when the resolution setting changes)."""
        self.size = (width, height)
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
        with self.ctx:
            self.far = FarTerrain(self.ctx, self.lod_program, self.world, self.texture,
                                  far.atlas_data, spacing, size, levels)
            self.far.version = far.version + 1  # the shadow maps are drawn again
            for res in far.data_maps + far.color_maps + [far.tile_avg, far.vbo, far.vao]:
                res.release()

    def make_framebuffers(self):
        width, height = self.size
        ctx = self.ctx
        with ctx:
            for obj in self.fbos:
                for part in (*obj.color_attachments, obj.depth_attachment, obj):
                    if part is not None:
                        part.release()
            # The frame in full color (with several samples per pixel for anti-aliasing), the same
            # frame with one color per pixel, and the palette indices read back for Pyxel
            samples = MSAA_SAMPLES if self.fancy else 0
            self.scene_texture = ctx.texture((width, height), 4, dtype="f2")
            self.scene_texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
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
        return self.chunks.progress(cam, radius)

    def block_changed(self, x, y, z):
        with self.ctx:
            self.chunks.block_changed(x, y, z)

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
        cell = (math.floor(cam[0] / 2), math.floor(cam[2] / 2))
        values.update({
            "block_fade": (0.5 * fade_end, float(fade_end)), "cam_cell": cell,
            "cam_in_cell": (float(cam[0] - 2 * cell[0]), float(cam[2] - 2 * cell[1])),
            "cam_frac": (float(cam[0] % 256.0), float(cam[2] % 256.0)), "cam_x": float(cam[0]),
            "px_per_block": height / (2 * math.tan(math.radians(self.fov) / 2)),
        })
        self.far.view_distance = self.view_distance
        finish = {"dim": float(self.dim), "tint": (0.75, 0.9, 1.0) if self.underwater else (1.0, 1.0, 1.0)}
        # Every OpenGL call, setting shader values included, must happen inside `with self.ctx`:
        # outside it, Pyxel's own context is the current one (with a window; not in headless tests)
        with self.ctx:
            ctx = self.ctx
            self.palette.apply()
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

            # Distant terrain and far clouds first, then clear the depth (not the colors) and draw
            # the blocks on top: each pass gets the depth precision it needs
            ctx.enable(moderngl.DEPTH_TEST)
            if None not in self.far.origins:
                self.far.render(far_vp, cam, self.chunks)
            near_radius = (self.sim_distance + 2) * CHUNK
            self.render_clouds(far_vp, near_radius, near_pass=False)
            fbo.color_mask = (False, False, False, False)
            fbo.clear(depth=1.0)
            fbo.color_mask = (True, True, True, True)
            fbo.use()  # masks only come back into effect when the framebuffer is bound

            self.texture.use(ATLAS_UNIT)
            self.far.tile_avg.use(TILE_AVG_UNIT)
            self.program["vp"].write(matrix_bytes(near_vp))
            self.program["mode"] = 0
            self.drawn = self.chunks.find_in_view(near_vp, cam)
            self.chunks.render()
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            fbo.depth_mask = False
            fbo.use()
            self.program["mode"] = 1
            self.chunks.render(water=True)
            ctx.disable(moderngl.BLEND)
            fbo.depth_mask = True
            fbo.use()
            self.render_clouds(near_vp, near_radius, near_pass=True)

            if target:
                corners = np.array([(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)], dtype=np.float64)
                corners = (corners - 0.5) * 1.004 + 0.5 + np.array(target) - np.array(cam)
                lines = corners[np.array(CUBE_EDGES).ravel()]
                self.outline_vbo.write(lines.astype("f4").tobytes())
                self.outline_program["vp"].write(matrix_bytes(near_vp))
                self.outline_vao.render(moderngl.LINES)

            # Down to one color per pixel, then to Pyxel's palette
            ctx.disable(moderngl.DEPTH_TEST)
            if fbo is not self.resolved_fbo:
                ctx.copy_framebuffer(self.resolved_fbo, fbo)
            self.scene_texture.use(0)
            self.palette.texture.use(1)
            self.palette.lut.use(2)
            set_uniforms(self.post_program, {"scene": 0, "palette": 1, "lut": 2, **finish})
            self.index_fbo.use()
            self.post_vao.render(moderngl.TRIANGLE_STRIP)
            adapt = self.palette.wants_samples()
            if adapt:
                self.palette.sample(self.scene_texture, finish)
            frame = np.frombuffer(self.index_fbo.read(components=1, dtype="f1"), dtype=np.uint8)
            if adapt:
                self.palette.adapt()  # for the next frame: this one was drawn for the current palette
        screen[:, :] = frame.reshape(height, width)[::-1]  # OpenGL rows go bottom-up

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
