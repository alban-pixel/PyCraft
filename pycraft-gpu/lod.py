"""Level-of-Detail (LOD) manager for seamless distant terrain rendering with vertical quality gradient.

Inspired by Distant Horizons & Voxy:
- Unified Depth Space: Renders into the main depth buffer using the same projection matrix.
- Hierarchical Quality Gradient:
  * Level 1 (Close LOD, r_near to r_near + 8): 2x2 micro-columns capturing sharp mountain ridges.
  * Level 2 (Mid LOD, r_near + 8 to r_near + 22): 4x4 sub-cells with stepped vertical faces.
  * Level 3 (Far Silhouette, r_near + 22 to r_max): 8x8 quadrants (4 sub-cells per chunk)
    covering mountain silhouettes up to Y=256 without monolithic flat artifacts or lag.
- Seamless Boundary Skirts: Watertight downward geometry on cell and chunk boundaries guarantees
  zero gaps, zero seams, and zero holes with active near chunks and between LOD tiers.
- Single GPU Draw Call: Consolidates all distant chunk quads into a unified VBO/VAO.
- Early-Z Occlusion & Anti-Double Rendering: Active near chunks render first and are strictly
  excluded from LOD generation to prevent Z-fighting.
"""
import math
from typing import Dict, List, Optional, Set, Tuple

import moderngl
import numpy as np

from blocks import (
    ATLAS_TILES, BLOCK_TILES, CUTOUT, DIRT, GRASS, SAND, SNOW, STONE, WATER,
)

CHUNK = 16
SEA_LEVEL = 22
UV_INSET = 0.5 / 16
CORNER_UV = np.array([(0, 0), (1, 0), (1, 1), (0, 1)], dtype=np.float32)
TRIANGLES = [0, 1, 2, 0, 2, 3]


def make_quad(corners, tile_id: int, shade: float, kind: float = 0.0) -> np.ndarray:
    """Generate 6 vertices (2 triangles) for a quad with texture coordinates and shading."""
    ty, tx = divmod(tile_id, ATLAS_TILES)
    uv = (np.array([tx, ty], dtype=np.float32) + UV_INSET + CORNER_UV * (1 - 2 * UV_INSET)) / ATLAS_TILES
    p = np.array(corners, dtype=np.float32)
    f_pos = p[TRIANGLES]
    f_uv = uv[TRIANGLES]
    f_sh = np.full((6, 1), shade, dtype=np.float32)
    f_kd = np.full((6, 1), kind, dtype=np.float32)
    return np.concatenate([f_pos, f_uv, f_sh, f_kd], axis=1).astype(np.float32)


class LODChunkBuilder:
    """Builds multi-tier macro-voxel geometry for distant chunk columns."""

    @staticmethod
    def _build_subcell_grid(world, cx: int, cz: int, cell_size: int) -> Optional[np.ndarray]:
        """Builds a grid of sub-cells (2x2 for LOD1, 4x4 for LOD2, 8x8 for LOD3) with watertight vertical skirts."""
        x0, z0 = cx * CHUNK, cz * CHUNK
        quads = []

        num_cells = CHUNK // cell_size
        heights = np.zeros((num_cells, num_cells), dtype=np.int32)
        block_types = np.zeros((num_cells, num_cells), dtype=np.int32)

        for u in range(num_cells):
            for v in range(num_cells):
                mx = x0 + u * cell_size + cell_size // 2
                mz = z0 + v * cell_size + cell_size // 2
                h = world.get_column_height(mx, mz)
                heights[u, v] = h
                block_types[u, v] = world.get_surface_block_type(mx, h, mz)

        for u in range(num_cells):
            for v in range(num_cells):
                bx0 = x0 + u * cell_size
                bz0 = z0 + v * cell_size
                bx1 = bx0 + cell_size
                bz1 = bz0 + cell_size
                h_val = float(heights[u, v])
                b_type = int(block_types[u, v])
                is_water = (b_type == WATER)
                kind = 2.0 if is_water else 0.0

                top_tile = int(BLOCK_TILES[b_type, 2])
                side_tile = int(BLOCK_TILES[b_type, 0])

                # Water top surface is slightly lowered by 0.125 blocks to match block water
                h_top = (h_val - 0.125) if is_water else h_val

                # 1. Top face (normal +Y)
                top_corners = [
                    (bx0, h_top, bz0),
                    (bx1, h_top, bz0),
                    (bx1, h_top, bz1),
                    (bx0, h_top, bz1),
                ]
                quads.append(make_quad(top_corners, top_tile, shade=1.0, kind=kind))

                # 2. Skirts and step-downs to adjacent cells (outward CCW winding)
                mid_z = bz0 + cell_size // 2
                mid_x = bx0 + cell_size // 2

                # East (+X)
                if u + 1 < num_cells:
                    h_east = float(heights[u + 1, v])
                    if h_val > h_east:
                        h_bot = max(1.0, h_east)
                        h_top_skirt = (h_val - 0.125) if is_water else h_val
                        if h_top_skirt > h_bot:
                            east_corners = [
                                (bx1, h_top_skirt, bz0),
                                (bx1, h_top_skirt, bz1),
                                (bx1, h_bot, bz1),
                                (bx1, h_bot, bz0),
                            ]
                            quads.append(make_quad(east_corners, side_tile, shade=0.8, kind=kind))
                else:
                    h_east = float(world.get_column_height(bx1 + 1, mid_z))
                    if is_water:
                        if h_val > h_east:
                            h_bot = max(1.0, h_east)
                            h_top_skirt = h_val - 0.125
                            if h_top_skirt > h_bot:
                                east_corners = [
                                    (bx1, h_top_skirt, bz0),
                                    (bx1, h_top_skirt, bz1),
                                    (bx1, h_bot, bz1),
                                    (bx1, h_bot, bz0),
                                ]
                                quads.append(make_quad(east_corners, side_tile, shade=0.8, kind=kind))
                    else:
                        h_bot = max(1.0, min(h_val, h_east) - 4.0)
                        if h_val > h_bot:
                            east_corners = [
                                (bx1, h_val, bz0),
                                (bx1, h_val, bz1),
                                (bx1, h_bot, bz1),
                                (bx1, h_bot, bz0),
                            ]
                            quads.append(make_quad(east_corners, side_tile, shade=0.8, kind=kind))

                # West (-X)
                if u - 1 >= 0:
                    h_west = float(heights[u - 1, v])
                    if h_val > h_west:
                        h_bot = max(1.0, h_west)
                        h_top_skirt = (h_val - 0.125) if is_water else h_val
                        if h_top_skirt > h_bot:
                            west_corners = [
                                (bx0, h_top_skirt, bz1),
                                (bx0, h_top_skirt, bz0),
                                (bx0, h_bot, bz0),
                                (bx0, h_bot, bz1),
                            ]
                            quads.append(make_quad(west_corners, side_tile, shade=0.8, kind=kind))
                else:
                    h_west = float(world.get_column_height(bx0 - 1, mid_z))
                    if is_water:
                        if h_val > h_west:
                            h_bot = max(1.0, h_west)
                            h_top_skirt = h_val - 0.125
                            if h_top_skirt > h_bot:
                                west_corners = [
                                    (bx0, h_top_skirt, bz1),
                                    (bx0, h_top_skirt, bz0),
                                    (bx0, h_bot, bz0),
                                    (bx0, h_bot, bz1),
                                ]
                                quads.append(make_quad(west_corners, side_tile, shade=0.8, kind=kind))
                    else:
                        h_bot = max(1.0, min(h_val, h_west) - 4.0)
                        if h_val > h_bot:
                            west_corners = [
                                (bx0, h_val, bz1),
                                (bx0, h_val, bz0),
                                (bx0, h_bot, bz0),
                                (bx0, h_bot, bz1),
                            ]
                            quads.append(make_quad(west_corners, side_tile, shade=0.8, kind=kind))

                # South (+Z)
                if v + 1 < num_cells:
                    h_south = float(heights[u, v + 1])
                    if h_val > h_south:
                        h_bot = max(1.0, h_south)
                        h_top_skirt = (h_val - 0.125) if is_water else h_val
                        if h_top_skirt > h_bot:
                            south_corners = [
                                (bx1, h_top_skirt, bz1),
                                (bx0, h_top_skirt, bz1),
                                (bx0, h_bot, bz1),
                                (bx1, h_bot, bz1),
                            ]
                            quads.append(make_quad(south_corners, side_tile, shade=0.65, kind=kind))
                else:
                    h_south = float(world.get_column_height(mid_x, bz1 + 1))
                    if is_water:
                        if h_val > h_south:
                            h_bot = max(1.0, h_south)
                            h_top_skirt = h_val - 0.125
                            if h_top_skirt > h_bot:
                                south_corners = [
                                    (bx1, h_top_skirt, bz1),
                                    (bx0, h_top_skirt, bz1),
                                    (bx0, h_bot, bz1),
                                    (bx1, h_bot, bz1),
                                ]
                                quads.append(make_quad(south_corners, side_tile, shade=0.65, kind=kind))
                    else:
                        h_bot = max(1.0, min(h_val, h_south) - 4.0)
                        if h_val > h_bot:
                            south_corners = [
                                (bx1, h_val, bz1),
                                (bx0, h_val, bz1),
                                (bx0, h_bot, bz1),
                                (bx1, h_bot, bz1),
                            ]
                            quads.append(make_quad(south_corners, side_tile, shade=0.65, kind=kind))

                # North (-Z)
                if v - 1 >= 0:
                    h_north = float(heights[u, v - 1])
                    if h_val > h_north:
                        h_bot = max(1.0, h_north)
                        h_top_skirt = (h_val - 0.125) if is_water else h_val
                        if h_top_skirt > h_bot:
                            north_corners = [
                                (bx0, h_top_skirt, bz0),
                                (bx1, h_top_skirt, bz0),
                                (bx1, h_bot, bz0),
                                (bx0, h_bot, bz0),
                            ]
                            quads.append(make_quad(north_corners, side_tile, shade=0.65, kind=kind))
                else:
                    h_north = float(world.get_column_height(mid_x, bz0 - 1))
                    if is_water:
                        if h_val > h_north:
                            h_bot = max(1.0, h_north)
                            h_top_skirt = h_val - 0.125
                            if h_top_skirt > h_bot:
                                north_corners = [
                                    (bx0, h_top_skirt, bz0),
                                    (bx1, h_top_skirt, bz0),
                                    (bx1, h_bot, bz0),
                                    (bx0, h_bot, bz0),
                                ]
                                quads.append(make_quad(north_corners, side_tile, shade=0.65, kind=kind))
                    else:
                        h_bot = max(1.0, min(h_val, h_north) - 4.0)
                        if h_val > h_bot:
                            north_corners = [
                                (bx0, h_val, bz0),
                                (bx1, h_val, bz0),
                                (bx1, h_bot, bz0),
                                (bx0, h_bot, bz0),
                            ]
                            quads.append(make_quad(north_corners, side_tile, shade=0.65, kind=kind))

        if not quads:
            return None
        return np.concatenate(quads, axis=0).astype(np.float32)

    @classmethod
    def build_chunk_lod1(cls, world, cx: int, cz: int) -> Optional[np.ndarray]:
        """Level 1 LOD: Fine 2x2 micro-columns (64 sub-cells per chunk) for close high-detail terrain."""
        return cls._build_subcell_grid(world, cx, cz, cell_size=2)

    @classmethod
    def build_chunk_lod2(cls, world, cx: int, cz: int) -> Optional[np.ndarray]:
        """Level 2 LOD: Medium 4x4 sub-cells (16 sub-cells per chunk) for mid-distance terrain."""
        return cls._build_subcell_grid(world, cx, cz, cell_size=4)

    @classmethod
    def build_chunk_lod3(cls, world, cx: int, cz: int) -> Optional[np.ndarray]:
        """Level 3 LOD: 8x8 quadrants (4 sub-cells per chunk) for distant mountain silhouettes and terrain."""
        return cls._build_subcell_grid(world, cx, cz, cell_size=8)


class LODManager:
    """Manages distant chunk LOD generation, streaming, and GPU buffers with a 3-tier gradient."""

    def __init__(self, ctx: moderngl.Context, program: moderngl.Program, world):
        self.ctx = ctx
        self.program = program
        self.world = world
        self.cache: Dict[Tuple[int, int, int], np.ndarray] = {}  # (cx, cz, level) -> vertex array
        self.active_lod_keys: Set[Tuple[int, int]] = set()
        self.vbo: Optional[moderngl.Buffer] = None
        self.vao: Optional[moderngl.VertexArray] = None
        self.vertex_count = 0
        self.last_center = (-9999, -9999)
        self.last_near_chunks: Set[Tuple[int, int]] = set()

    def set_world(self, world):
        """Update world reference and clear cache."""
        self.world = world
        self.cache.clear()
        self.active_lod_keys.clear()
        self.vertex_count = 0
        if self.vao:
            self.vao.release()
            self.vao = None
        if self.vbo:
            self.vbo.release()
            self.vbo = None
        self.last_center = (-9999, -9999)
        self.last_near_chunks = set()

    def update(self, player_x: float, player_z: float, near_chunks: Set[Tuple[int, int]], render_dist: int = 12, max_lod_dist: int = 48):
        """Update distant LOD chunks using a 3-tier quality gradient."""
        pcx = int(math.floor(player_x / CHUNK))
        pcz = int(math.floor(player_z / CHUNK))

        if (pcx, pcz) == self.last_center and near_chunks == self.last_near_chunks and self.vao is not None:
            return  # No update needed if player stays in the same chunk and near chunks haven't changed

        needed_lods: List[Tuple[int, int, int]] = []  # (cx, cz, level)
        r_near = render_dist
        r_lod1 = render_dist + 8   # Level 1: 2x2 micro-columns
        r_lod2 = render_dist + 20  # Level 2: 4x4 sub-cells
        r_max = max(max_lod_dist, render_dist + 36) # Level 3: 8x8 quadrants

        r_near2 = (r_near + 0.5) ** 2
        r_lod1_2 = (r_lod1 + 0.5) ** 2
        r_lod2_2 = (r_lod2 + 0.5) ** 2
        r_max2 = (r_max + 0.5) ** 2

        for dcx in range(-r_max, r_max + 1):
            for dcz in range(-r_max, r_max + 1):
                d2 = dcx * dcx + dcz * dcz
                if d2 > r_max2:
                    continue
                cx, cz = pcx + dcx, pcz + dcz
                if (cx, cz) in near_chunks:
                    continue  # Active near chunks are rendered by block chunk mesher
                if d2 <= r_near2:
                    continue  # Strictly outside near render distance

                if d2 <= r_lod1_2:
                    needed_lods.append((cx, cz, 1))  # Level 1: 2x2 fine micro-columns
                elif d2 <= r_lod2_2:
                    needed_lods.append((cx, cz, 2))  # Level 2: 4x4 medium cells
                else:
                    needed_lods.append((cx, cz, 3))  # Level 3: 8x8 far quadrants

        # Evict old distant cache entries
        if len(self.cache) > 4000:
            active_keys = set(needed_lods)
            self.cache = {k: v for k, v in self.cache.items() if k in active_keys}

        # Build missing LOD chunk meshes
        parts = []
        for cx, cz, lvl in needed_lods:
            key = (cx, cz, lvl)
            verts = self.cache.get(key)
            if verts is None:
                if lvl == 1:
                    verts = LODChunkBuilder.build_chunk_lod1(self.world, cx, cz)
                elif lvl == 2:
                    verts = LODChunkBuilder.build_chunk_lod2(self.world, cx, cz)
                else:
                    verts = LODChunkBuilder.build_chunk_lod3(self.world, cx, cz)
                if verts is not None:
                    self.cache[key] = verts
            if verts is not None and len(verts) > 0:
                parts.append(verts)

        # Upload unified LOD mesh to GPU
        with self.ctx:
            if self.vao:
                self.vao.release()
                self.vao = None
            if self.vbo:
                self.vbo.release()
                self.vbo = None

            if parts:
                data = np.concatenate(parts, axis=0).astype(np.float32)
                self.vertex_count = len(data)
                self.vbo = self.ctx.buffer(data.tobytes())
                self.vao = self.ctx.vertex_array(
                    self.program, [(self.vbo, "3f 2f 1f 1f", "in_pos", "in_uv", "in_shade", "in_kind")]
                )
            else:
                self.vertex_count = 0

        self.last_center = (pcx, pcz)
        self.last_near_chunks = set(near_chunks)
        self.active_lod_keys = {(cx, cz) for cx, cz, _ in needed_lods}

    def render(self):
        """Draw all distant LOD chunks in a single GPU draw call."""
        if self.vao and self.vertex_count > 0:
            self.vao.render(moderngl.TRIANGLES, vertices=self.vertex_count)


    def render(self):
        """Draw all distant LOD chunks in a single GPU draw call."""
        if self.vao and self.vertex_count > 0:
            self.vao.render(moderngl.TRIANGLES, vertices=self.vertex_count)
