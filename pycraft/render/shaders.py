"""The GLSL programs of the renderer, and the pieces several of them share (light, clouds,
shadows, waves, Oklab colors...). Each program is a Python string, put together and filled in with
the renderer's numbers here; render.renderer and render.palette compile them. Tools replace some of
them before the renderer is made (see tools/render_views.py), which is why the other modules reach
them as shaders.NAME."""

from pycraft import blocks as B
from pycraft import terrain as T
from pycraft.blocks import ATLAS_TILES
from pycraft.render.constants import (CLOUD_EXTENT, CLOUD_PERIOD, CROWN_DARK, CROWN_RISE, LOD_BAND,
                                      LOD_MARGIN, SAMPLES, WET_ALPHA_MIN)


# Block numbers and the badlands' rock layers, for the distant terrain's shaders. The atlas tile of
# each face of each block is a small texture (Renderer.block_tiles), not a constant array: picked
# per pixel by block, a constant array is copied into every pixel's scratch memory by some drivers
# (AMD Radeon 880M on Windows: the distant terrain took 73 ms of a frame at 2560x1440, 8.8 ms now)
BLOCK_IDS = "".join("const int %s = %d;\n" % (name, getattr(B, name)) for name in (
    "GRASS", "DIRT", "STONE", "PODZOL", "MUD", "MOSS", "GRAVEL", "SNOW", "WATER", "ICE", "TERRACOTTA", "RED_SAND",
    "LEAVES", "SPRUCE_LEAVES", "BIRCH_LEAVES", "JUNGLE_LEAVES", "ACACIA_LEAVES"))
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
in uvec4 in_info;     // tile (layer of the texture array), corner of the face (0-3), face direction (0-5, plants 6-7), kind (builder.KIND)
in vec4 in_tint;      // biome color for grass, leaves and water; ambient occlusion
in uvec4 in_uv;       // place on the tile, in 16ths (x, y)
out vec2 v_uv;
out vec3 v_pos;
out vec3 v_tint;
out float v_ao;
flat out int v_face;
flat out int v_kind;
flat out int v_tile;
void main() {
    vec3 pos = origin + in_pos;
    gl_Position = vp * vec4(pos, 1.0);
    if (mode == 2) gl_Position.z = max(gl_Position.z, -1.0);  // nearer the light than the map: flattened onto it
    v_uv = vec2(in_uv.xy) / 16.0;  // in the tile: each tile is its own layer, so nothing bleeds in
    v_face = int(in_info.z);
    v_kind = int(in_info.w);
    v_tile = int(in_info.x);
    v_tint = in_tint.rgb;
    v_ao = in_tint.a;
    v_pos = pos;
}
""" % {"atlas": ATLAS_TILES}
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
uniform sampler2DArray atlas;      // the tiles, mipmapped: no shimmer far off
uniform sampler2DArray tint_mask;  // 1 where a texel takes the biome color (mipmapped too: a share)
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
    vec3 uvw = vec3(v_uv, float(v_tile));
    vec4 tex = texture(atlas, uvw);
    float tinted = texture(tint_mask, uvw).r;
    // The cut-out from the full-size texture: the mipmaps' averaged alpha would thin out plants far off
    float alpha = textureLod(atlas, uvw, 0.0).a;
    bool plant = v_kind == 4;
    if (alpha < 0.5 && (v_kind == 1 || plant || (v_kind == 3 && mode == 2))) discard;  // see-through texel
    if (mode == 2) return;  // shadow map: only the depth counts
    int face = plant ? 2 : v_face;  // plants (crossed quads, faces 6-7) are lit like the top of a block
    vec3 n = NORMALS[face];
    if (!drawn_as_blocks(cell_of(v_pos.xz - n.xz * 0.01))) discard;  // the distant terrain shows here
    vec3 albedo = tex.rgb * mix(vec3(1.0), v_tint, tinted);  // texels colored by the biome
    if (v_kind == 3 && alpha < 0.5) albedo *= v_tint * 0.4;  // a hole in leaves: the shaded leaves inside
    if (v_kind != 1) albedo = far_albedo(albedo, v_tile, v_tint, length(v_pos));
    // A plant's shadow is tested a block toward the light, so it doesn't shadow itself
    float direct = direct_light(plant ? v_pos + light_dir : v_pos, n);
    if (mode == 0)  // (a lamp shows its own colors, day and night)
        out_color = vec4(fog(v_kind == 5 ? albedo : shade_opaque(albedo, face, v_ao, direct), length(v_pos)), 1.0);
    else
        out_color = shade_water(albedo, v_pos, v_face, direct);
}
"""
# --- Distant terrain: mode 0 the colors, 1 the shadow maps ---------------------------------------

LOD_VERTEX_SHADER = """
#version 330
uniform mat4 vp;
uniform usampler2D data;     // grid_size x grid_size, wrapping: heights and blocks of each grid point
uniform usampler2D coarse_data;  // the same for the next, coarser level (when fade_own is 1)
uniform usampler2D fine_data;    // and for the finer level (when fade_inner is 1)
uniform sampler2D colors;    // same layout: the biome's color of the grass (or of the water)
uniform ivec2 grid_origin;   // grid coordinates of point (0, 0)
uniform ivec2 coarse_origin; // the same for the coarser and the finer level, in their own grids
uniform ivec2 fine_origin;
uniform vec2 origin;         // its position relative to the camera (x, z)
uniform float cam_y;
uniform float spacing;
uniform int grid_size;       // grid points per side (a power of two); grid_size - 1 columns are drawn
uniform int mode;
uniform int level;
uniform int water_pass;      // 1 draws the water layer over the ground columns, 0 the ground
uniform vec4 inner;          // square of the finer level (relative to the camera: min x, min z, max x, max z)
uniform int fade_inner;      // 1 when a finer level is drawn: give way to it, cell by cell
uniform vec4 own;            // this level's square
uniform int fade_own;        // 1 when a coarser level takes over at the edge of this one
uniform int use_ready;       // leave out what the blocks draw (not in the shadow maps)
uniform vec4 clip_planes[3]; // left, right and near planes of vp: nothing is drawn outside them
uniform ivec2 tiles[256];     // the tiles of the grid to draw (LOD_TILES x LOD_TILES at most): the cell at the corner of each
uniform int tile_width;      // cells along a tile's side
uniform vec2 lee;            // a shadow map: the horizontal direction the light travels in
uniform int far_sides;       // 1: the pass that draws the two other sides of the columns around the blocks
uniform float block_reach;   // how far from the camera blocks can be drawn
uniform sampler2D ready;     // 64x64 wrapping map of the chunk columns drawn as blocks
uniform ivec2 cam_chunk;
uniform vec2 cam_in_chunk;
in vec3 in_pos;              // unit cube corner: x, z in {0, 1}; y = 1 on top, 0 down a side
in vec3 in_norm;             // the face's normal: up, +x or +z (a side is moved to -x or -z when that is the one to draw)
out vec3 v_pos;
flat out int v_face;
flat out ivec3 v_blocks;     // top block, the block under it, crown leaves (0: no tree)
flat out vec3 v_tint;
flat out vec2 v_tops;        // heights of the ground and of the column (with its crown), in the world
flat out float v_bottom;     // a side: height of the lowest column it faces
flat out ivec2 v_local;      // the column's cell in the grid, for the top's ambient occlusion
flat out vec2 v_corner;      // the column's corner, relative to the camera
flat out vec2 v_aux;         // canopy coverage, water coverage of the cell (0-1)
flat out int v_flags;        // bit 0: the cell's color is emissive (a lamp a player placed)
""" + CELLS + """
// A grid point's texel: height of the ground's top surface (as float bits), then the 4 packed
// bytes (top block, block under it, crown leaves or 0, crown height), then the water's surface
// (bits, -1 where the cell is dry or frozen over). The sampler has already put bare rock where
// the ground is too steep for soil, and no trees there (see lod.py)
uvec4 data_at(ivec2 local) { return texelFetch(data, (grid_origin + local) & (grid_size - 1), 0); }
float height_of(uvec4 d) { return uintBitsToFloat(d.x); }
float wsurf_of(uvec4 d) { return uintBitsToFloat(d.z); }
ivec4 blocks_of(uvec4 d) { return ivec4(d.y & 255u, (d.y >> 8) & 255u, (d.y >> 16) & 255u, d.y >> 24); }
// How high the column of a texel is drawn: up to its ground and, beyond the blocks, up to its
// crown of leaves if it has one (where the blocks are drawn they have the real trees: no fake
// crowns there, and past them the crowns rise little by little). c: the column's center,
// relative to the camera. Every column that looks at another one works out its height with
// this, so their sides always meet
float drawn_top(uvec4 d, vec2 c) {
    float h = height_of(d);
    if (((d.y >> 16) & 255u) != 0u)
        h += float(d.y >> 24) * smoothstep(block_fade.y, block_fade.y + %(rise)d.0, length(c));
    return h;
}
float level_fade(vec2 center, vec4 rect, float fine) {  // 1 at the edge of a finer level's square, 0 well inside
    float d = min(min(center.x - rect.x, rect.z - center.x), min(center.y - rect.y, rect.w - center.y));
    return 1.0 - clamp((d - %(margin)d.0 * fine) / (%(band)d.0 * fine), 0.0, 1.0);
}
void main() {
    // One instance per cell of the grid: a square column of blocks, like Distant Horizons. The
    // cells come tile by tile, for the tiles that may be in view (and, for the water pass,
    // that have water)
    int per = tile_width * tile_width, k = gl_InstanceID %% per;
    ivec2 local = tiles[gl_InstanceID / per] + ivec2(k %% tile_width, k / tile_width);
    ivec2 g = grid_origin + local;
    vec2 center = origin + (vec2(local) + 0.5) * spacing;
    uvec4 own_data = data_at(local);
    float ground = height_of(own_data);
    float top = water_pass == 1 ? wsurf_of(own_data) : drawn_top(own_data, center);
    bool keep = water_pass == 0 || top >= 0.0;  // (the water pass: a dry cell has nothing to draw)
    keep = keep && max(local.x, local.y) < grid_size - 1;  // (the last tiles reach one cell past the grid)
    // Is this cell drawn by this level? Each 2x2 group of its cells is drawn either by this level
    // or by the next, coarser one: both pick it with the same number
    if (fade_inner == 1) keep = keep && cell_hash(g, level) < level_fade(center, inner, spacing * 0.5);
    if (fade_own == 1) {
        ivec2 parent = g >> 1;
        keep = keep && cell_hash(parent, level + 1)
                       >= level_fade(origin + (vec2(parent * 2 - grid_origin) + 1.0) * spacing, own, spacing);
    }
    float dist = length(center);
    if (far_sides == 1 && dist >= block_reach) keep = false;
    // Where the blocks are all drawn, the columns fold away. Further out the blocks give way to
    // them cell by cell: there the columns are drawn whole, under the blocks too. A block that
    // gives way then shows the column behind it, never a hole — a real slope and its columns
    // don't have the same shape, and on a cliff their sides would not meet
    if (use_ready == 1 && dist < block_fade.y + spacing) {
        ivec2 rel = ivec2(floor((center + cam_in_chunk) / 16.0));
        bool in_chunk = abs(rel.x) < 32 && abs(rel.y) < 32
                        && texelFetch(ready, (cam_chunk + rel) & 63, 0).r > 0.5;
        if (in_chunk && dist + 0.71 * spacing < block_fade.x) keep = false;
        // The water is a see-through layer over the aquatic floor: cells whose water the blocks
        // already draw have nothing to add
        if (water_pass == 1 && in_chunk && drawn_as_blocks(cell_of(center))) keep = false;
    }
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
    // Of a column's four sides only the two turned toward the eye can be seen: the mesh has one
    // side along x and one along z, put there. A shadow map gets the two sides turned away from
    // the light instead. With the tops they stop the same light as all four would (light that
    // enters the ground through a missing side can only leave it through one of them), and they
    // also stop the light that slips under the terrain at the edge of a grid, which the sides
    // turned toward the light would let through.
    // The view has one way in under the ground: the mouth of a cave, among the blocks. Deep
    // inside, a cave has no walls (its sections are only built around the player), and behind
    // it the terrain is a shell: the eye would go through the mountain and out to the sky. So a
    // second pass draws the two other sides of the columns around the blocks, and stretches
    // those at the edge down to the bottom of the world: a wall all around, under the ground
    vec3 corner = in_pos, norm = in_norm;
    vec2 eye = mode == 1 ? lee : far_sides == 1 ? center : -center;
    if (in_norm.x != 0.0 && eye.x < 0.0) { corner.x = 0.0; norm.x = -1.0; }
    if (in_norm.z != 0.0 && eye.y < 0.0) { corner.z = 0.0; norm.z = -1.0; }
    // A side goes down to the lowest surface it may face, and folds away when nothing it faces
    // is lower. What it faces is the column next to it in this level — or, where two levels share
    // the cells, the coarser column or the two finer columns that may be drawn there instead
    float low = top;
    bool seam = false;  // the side may touch the columns of another level
    if (norm.y == 0.0) {
        ivec2 dn = ivec2(int(norm.x), int(norm.z));
        ivec2 ncell = local + dn, gn = g + dn;
        vec2 ncenter = center + vec2(dn) * spacing;
        if (min(ncell.x, ncell.y) < 0 || max(ncell.x, ncell.y) >= grid_size - 1)
            low = top - 4.0 * spacing;  // the edge of the grid
        else
            low = min(low, drawn_top(data_at(ncell), ncenter));
        if (fade_own == 1 && (gn >> 1) != (g >> 1)) {
            ivec2 p = gn >> 1;  // the coarser cell on the other side
            vec2 pc = origin + (vec2(p * 2 - grid_origin) + 1.0) * spacing;
            if (level_fade(pc, own, spacing) > 0.0) {
                seam = true;
                if (all(greaterThanEqual(p, coarse_origin)) && all(lessThan(p, coarse_origin + grid_size - 1)))
                    low = min(low, drawn_top(texelFetch(coarse_data, p & (grid_size - 1), 0), pc));
            }
        }
        if (fade_inner == 1 && level_fade(ncenter, inner, spacing * 0.5) < 1.0) {
            seam = true;
            // The two finer cells along this side, inside the cell it faces
            ivec2 c = 2 * gn + ivec2(dn.x < 0 ? 1 : 0, dn.y < 0 ? 1 : 0);
            ivec2 along = ivec2(abs(dn.y), abs(dn.x));
            for (int i = 0; i < 2; i++) {
                if (all(greaterThanEqual(c, fine_origin)) && all(lessThan(c, fine_origin + grid_size - 1)))
                    low = min(low, drawn_top(texelFetch(fine_data, c & (grid_size - 1), 0),
                                             origin + (vec2(c - 2 * grid_origin) + 0.5) * (spacing * 0.5)));
                c += along;
            }
        }
    }
    float y = top;
    if (corner.y < 0.5) {  // the bottom of a side
        // Where two levels meet, a side always goes down a little: their corners don't fall at
        // exactly the same places, and no pixel must show through between them
        if (seam) y = min(low, top) - max(0.5, 0.5 * spacing);
        else if (low < top) y = low - 0.5;
        if (far_sides == 1 && dist >= block_reach - 2.0 * spacing) y = low = 0.0;
    }
    // The faces of the ground overlap by a hair — the top juts out all around, a side at both of
    // its ends: the corners of two faces don't fall at the same places along the edge they share
    // (their heights differ), and now and then a pixel of sky would show between them
    vec2 grow = vec2(0.0);
    if (water_pass == 0) {
        vec2 out_ = (corner.xz * 2.0 - 1.0) * (0.01 * spacing);
        grow = norm.y != 0.0 ? out_ : norm.x != 0.0 ? vec2(0.0, out_.y) : vec2(out_.x, 0.0);
    }
    vec3 pos = vec3(origin.x + (float(local.x) + corner.x) * spacing + grow.x, y - cam_y,
                    origin.y + (float(local.y) + corner.z) * spacing + grow.y);
    v_pos = pos;
    gl_Position = vp * vec4(pos, 1.0);
    if (mode == 1) {
        gl_Position.z = max(gl_Position.z, -1.0);  // nearer the light than the map: flattened onto it
        return;
    }
    v_face = norm.x > 0.5 ? 0 : norm.x < -0.5 ? 1 : norm.y > 0.5 ? 2 : norm.z > 0.5 ? 4 : 5;
    v_blocks = water_pass == 1 ? ivec3(0) : blocks_of(own_data).xyz;
    vec4 c = texelFetch(colors, g & (grid_size - 1), 0);
    v_tint = c.rgb;
    v_tops = vec2(ground, top);
    v_aux = vec2(float(own_data.w & 255u), float((own_data.w >> 8) & 255u)) / 255.0;
    v_flags = int((own_data.w >> 16) & 255u);
    v_bottom = low;
    v_corner = origin + vec2(local) * spacing;
    v_local = local;  // the fragment shader works out which columns around are taller
}
""" % {"margin": LOD_MARGIN, "band": LOD_BAND, "rise": CROWN_RISE}
LOD_FRAGMENT_SHADER = """
#version 330
uniform int mode;
uniform int water_pass;      // 1: the pixel is a face of the water layer, see-through
uniform float cam_y;
uniform float spacing;
uniform vec2 cam_frac;       // the camera's x and z, modulo 256: where a block starts
uniform float cam_x;         // the camera's x (the badlands' layers shift at x = 0)
uniform sampler2DArray atlas;
uniform sampler2DArray tint_mask;
uniform usampler2D data;     // the level's grid: heights and blocks (see the vertex shader)
uniform ivec2 grid_origin;
uniform int grid_size;
uniform vec2 block_fade;     // distances where the blocks give way to the columns (see CELLS)
in vec3 v_pos;
flat in int v_face;
flat in ivec3 v_blocks;
flat in vec3 v_tint;
flat in vec2 v_tops;
flat in float v_bottom;
flat in ivec2 v_local;
flat in vec2 v_corner;
flat in vec2 v_aux;
flat in int v_flags;
out vec4 out_color;
uniform usampler2D block_tiles;  // 6 x NUM_BLOCKS: the atlas tile of each face of each block
""" + LIGHT + CLOUDS + SHADOWS + WAVES + BLOCK_SHADING + BLOCK_IDS + BANDS_GLSL + """
// The very top of the column of a cell, as it is drawn (see drawn_top in the vertex shader):
// worked out per pixel, only where a top needs its ambient occlusion — a cell is a few pixels
// wide at the distances where the cost matters
float lod_top(ivec2 cell) {
    uvec4 d = texelFetch(data, (grid_origin + cell) & (grid_size - 1), 0);
    float h = uintBitsToFloat(d.x);
    if (((d.y >> 16) & 255u) != 0u)
        h += float(d.y >> 24) * smoothstep(block_fade.y, block_fade.y + %(rise)d.0,
                                           length(v_corner + (vec2(cell - v_local) + 0.5) * spacing));
    return h;
}
void main() {
    if (mode == 1) return;  // shadow map: only the depth counts
    // Which block this point of the column is, like the generator stacks them
    vec3 w = vec3(v_pos.x + cam_frac.x, v_pos.y + cam_y, v_pos.z + cam_frac.y);
    // Where on the face's texture, unwrapped (the texture repeats on every block): its rate of
    // change picks the mipmap level, worked out here while every pixel of the quad still runs
    vec2 g = v_face == 2 ? w.xz : v_face == 0 ? vec2(w.z, -w.y) : v_face == 1 ? vec2(-w.z, -w.y)
           : v_face == 4 ? vec2(-w.x, -w.y) : vec2(w.x, -w.y);
    vec2 g_dx = dFdx(g), g_dy = dFdy(g);
    float ground = v_tops.x;
    int block;
    if (water_pass == 1) block = WATER;
    else if (v_face == 2) block = v_blocks.z != 0 ? v_blocks.z : v_blocks.x;
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
    // The texture repeats on every block, as on the blocks near the camera — unless the column
    // carries its own color: the blocks the player changed, averaged into the tint
    vec2 uv = fract(g);
    float dist = length(v_pos);
    vec3 albedo;
    if (block == 255) {
        albedo = v_tint;
    } else {
        int tile = int(texelFetch(block_tiles, ivec2(v_face, block), 0).r);
        bool leaves = block == LEAVES || block == SPRUCE_LEAVES || block == BIRCH_LEAVES || block == JUNGLE_LEAVES
                      || block == ACACIA_LEAVES;
        vec3 tint = block == GRASS || block == WATER ? v_tint
                  : (block == LEAVES || block == JUNGLE_LEAVES || block == ACACIA_LEAVES) ? v_tint * vec3(0.68, 0.78, 0.66)
                  : vec3(1.0);
        vec3 uvw = vec3(uv, float(tile));
        vec4 tex = textureGrad(atlas, uvw, g_dx, g_dy);
        albedo = tex.rgb * mix(vec3(1.0), tint, textureGrad(tint_mask, uvw, g_dx, g_dy).r);  // biome colors
        if (leaves && textureLod(atlas, uvw, 0.0).a < 0.5) albedo *= tint * 0.4;  // a hole in leaves: the shaded leaves inside
        albedo = far_albedo(albedo, tile, tint, dist);
        // A crown of leaves is opaque from afar: its inner air folds into the color — the more
        // open the crown, the darker — and the bottom of a crown stays darker than its top
        if (v_blocks.z != 0 && w.y > ground + 0.001)
            albedo *= mix(%(crown_dark).2f, 1.0, v_aux.x)
                      * mix(0.6, 1.0, clamp((w.y - ground) / max(v_tops.y - ground, 1.0), 0.0, 1.0));
    }
    if ((v_flags & 1) != 0) {  // an emissive cell: a lamp a player placed, shining at any distance
        out_color = vec4(fog(albedo, dist), 1.0);
        return;
    }
    // Ambient occlusion like the blocks': darker within a block of a taller column around
    float ao = 1.0;
    if (v_face == 2 && water_pass == 0) {  // (water is not darkened by its neighbors)
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
    } else if (v_bottom < v_tops.y && water_pass == 0) {
        ao = 0.5 + (3.0 - (1.0 - clamp(v_pos.y + cam_y - v_bottom, 0.0, 1.0))) / 6.0;
    }
    vec3 n = NORMALS[v_face];
    float direct = direct_light(v_pos, n);
    if (water_pass == 1) {  // see-through, like the blocks' water: the floor is drawn underneath
        out_color = shade_water(albedo, v_pos, v_face, direct);
        out_color.a *= mix(%(wet_min).2f, 1.0, v_aux.y);  // a partly wet cell is partly see-through
        return;
    }
    out_color = vec4(fog(shade_opaque(albedo, v_face, ao, direct), dist), 1.0);
}
""" % {"bands": len(T.BANDS), "atlas": ATLAS_TILES, "crown_dark": CROWN_DARK, "wet_min": WET_ALPHA_MIN,
       "rise": CROWN_RISE}
# --- Sky, clouds and the outline of the block looked at ------------------------------------------

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
uniform vec2 out_size;      // size of the frame on screen: the scene can be drawn smaller (render scale)
out float index;
""" + OKLAB + FINISH + """
int bayer8(ivec2 p) {  // ordered dithering threshold, 0-63
    int xy = p.x ^ p.y, v = 0;
    for (int i = 0; i < 3; i++) v = (v << 2) | (((xy >> i) & 1) << 1) | ((p.y >> i) & 1);
    return v;
}
vec3 scene_color(vec2 at) {
    ivec2 size = textureSize(scene, 0);
    if (size == ivec2(out_size)) return texelFetch(scene, ivec2(at), 0).rgb;
    // Drawn smaller: scaled up with a Catmull-Rom filter (sharper than a bilinear one), its 4x4
    // texels read as 3x3 bilinear samples
    vec2 pos = at / out_size * vec2(size) - 0.5;
    vec2 base = floor(pos);
    vec2 f = pos - base;
    vec2 w0 = f * (-0.5 + f * (1.0 - 0.5 * f));
    vec2 w1 = 1.0 + f * f * (-2.5 + 1.5 * f);
    vec2 w2 = f * (0.5 + f * (2.0 - 1.5 * f));
    vec2 w3 = f * f * (-0.5 + 0.5 * f);
    vec2 w12 = w1 + w2;
    vec2 inv = 1.0 / vec2(size);
    vec2 t0 = (base - 0.5) * inv, t12 = (base + 0.5 + w2 / w12) * inv, t3 = (base + 2.5) * inv;
    vec3 c = (texture(scene, vec2(t0.x, t0.y)).rgb * w0.x + texture(scene, vec2(t12.x, t0.y)).rgb * w12.x
              + texture(scene, vec2(t3.x, t0.y)).rgb * w3.x) * w0.y;
    c += (texture(scene, vec2(t0.x, t12.y)).rgb * w0.x + texture(scene, vec2(t12.x, t12.y)).rgb * w12.x
          + texture(scene, vec2(t3.x, t12.y)).rgb * w3.x) * w12.y;
    c += (texture(scene, vec2(t0.x, t3.y)).rgb * w0.x + texture(scene, vec2(t12.x, t3.y)).rgb * w12.x
          + texture(scene, vec2(t3.x, t3.y)).rgb * w3.x) * w3.y;
    return max(c, 0.0);  // (the filter can overshoot a little at sharp edges)
}
void main() {
    // Upside down: OpenGL's rows go bottom-up, Pyxel's top-down, so the frame read back is
    // already in Pyxel's order
    vec2 at = vec2(gl_FragCoord.x, out_size.y - gl_FragCoord.y);
    ivec2 p = ivec2(at);
    vec3 c = finish(scene_color(at));
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
