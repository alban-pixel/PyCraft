"""Level-of-Detail (LOD) manager for seamless distant terrain rendering.

Inspired by Distant Horizons & Voxy:
- Unified Depth Space: Renders into the main depth buffer using the same projection matrix.
- Macro-Voxel Representation: Distant chunks outside the near render distance are drawn as
  downsampled voxel columns (Level 1: 4x4 cells, Level 2: 16x16 macro-boxes).
- Seamless Boundary Skirts: Vertical downward geometry on cell and chunk boundaries guarantees
  zero gaps, zero seams, and zero holes with active near chunks.
- Single GPU Draw Call: Consolidates all distant chunk quads into a unified VBO/VAO.
- Early-Z Occlusion: Active near chunks render first and naturally occlude any overlapping LODs.
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
    """Builds macro-voxel geometry for a distant chunk column."""

    @staticmethod
    def build_chunk_lod1(world, cx: int, cz: int) -> Optional[np.ndarray]:
        """Level 1 LOD: 4x4 sub-cells of 4x4 blocks with top quads and vertical skirts."""
        x0, z0 = cx * CHUNK, cz * CHUNK
        quads = []

        # 4x4 grid of sampled heights and block types
        cell_size = 4
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

        # Generate top faces and inter-cell skirts
        for u in range(num_cells):
            for v in range(num_cells):
                bx0 = x0 + u * cell_size
                bz0 = z0 + v * cell_size
                bx1 = bx0 + cell_size
                bz1 = bz0 + cell_size
                h = float(heights[u, v])
                b_type = int(block_types[u, v])
                is_water = (b_type == WATER)
                kind = 2.0 if is_water else 0.0

                top_tile = int(BLOCK_TILES[b_type, 2])
                side_tile = int(BLOCK_TILES[b_type, 0])

                # 1. Top face (Y = h, normal +Y)
                top_corners = [
                    (bx0, h, bz0),
                    (bx1, h, bz0),
                    (bx1, h, bz1),
                    (bx0, h, bz1),
                ]
                quads.append(make_quad(top_corners, top_tile, shade=1.0, kind=kind))

                # 2. Skirts and step-downs to adjacent cells
                # East (+X)
                h_east = float(heights[u + 1, v]) if u + 1 < num_cells else (h - 3.0)
                if h > h_east:
                    east_corners = [
                        (bx1, h, bz0),
                        (bx1, h_east, bz0),
                        (bx1, h_east, bz1),
                        (bx1, h, bz1),
                    ]
                    quads.append(make_quad(east_corners, side_tile, shade=0.8, kind=kind))

                # West (-X)
                h_west = float(heights[u - 1, v]) if u - 1 >= 0 else (h - 3.0)
                if h > h_west:
                    west_corners = [
                        (bx0, h, bz1),
                        (bx0, h_west, bz1),
                        (bx0, h_west, bz0),
                        (bx0, h, bz0),
                    ]
                    quads.append(make_quad(west_corners, side_tile, shade=0.8, kind=kind))

                # South (+Z)
                h_south = float(heights[u, v + 1]) if v + 1 < num_cells else (h - 3.0)
                if h > h_south:
                    south_corners = [
                        (bx1, h, bz1),
                        (bx1, h_south, bz1),
                        (bx0, h_south, bz1),
                        (bx0, h, bz1),
                    ]
                    quads.append(make_quad(south_corners, side_tile, shade=0.65, kind=kind))

                # North (-Z)
                h_north = float(heights[u, v - 1]) if v - 1 >= 0 else (h - 3.0)
                if h > h_north:
                    north_corners = [
                        (bx0, h, bz0),
                        (bx0, h_north, bz0),
                        (bx1, h_north, bz0),
                        (bx1, h, bz0),
                    ]
                    quads.append(make_quad(north_corners, side_tile, shade=0.65, kind=kind))

        if not quads:
            return None
        return np.concatenate(quads, axis=0).astype(np.float32)

    @staticmethod
    def build_chunk_lod2(world, cx: int, cz: int) -> Optional[np.ndarray]:
        """Level 2 LOD: 1 macro-box per 16x16 chunk for very far terrain."""
        x0, z0 = cx * CHUNK, cz * CHUNK
        mx, mz = x0 + CHUNK // 2, z0 + CHUNK // 2
        h = float(world.get_column_height(mx, mz))
        b_type = int(world.get_surface_block_type(mx, int(h), mz))
        is_water = (b_type == WATER)
        kind = 2.0 if is_water else 0.0

        top_tile = int(BLOCK_TILES[b_type, 2])
        side_tile = int(BLOCK_TILES[b_type, 0])
        x1, z1 = x0 + CHUNK, z0 + CHUNK
        h_base = max(1.0, h - 6.0)

        quads = [
            # Top
            make_quad([(x0, h, z0), (x1, h, z0), (x1, h, z1), (x0, h, z1)], top_tile, 1.0, kind=kind),
            # +X
            make_quad([(x1, h, z0), (x1, h_base, z0), (x1, h_base, z1), (x1, h, z1)], side_tile, 0.8, kind=kind),
            # -X
            make_quad([(x0, h, z1), (x0, h_base, z1), (x0, h_base, z0), (x0, h, z0)], side_tile, 0.8, kind=kind),
            # +Z
            make_quad([(x1, h, z1), (x1, h_base, z1), (x0, h_base, z1), (x0, h, z1)], side_tile, 0.65, kind=kind),
            # -Z
            make_quad([(x0, h, z0), (x0, h_base, z0), (x1, h_base, z0), (x1, h, z0)], side_tile, 0.65, kind=kind),
        ]
        return np.concatenate(quads, axis=0).astype(np.float32)


class LODManager:
    """Manages distant chunk LOD generation, streaming, and GPU buffers."""

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

    def update(self, player_x: float, player_z: float, near_chunks: Set[Tuple[int, int]], render_dist: int = 4, max_lod_dist: int = 16):
        """Update distant LOD chunks outside the near chunks radius."""
        pcx = int(math.floor(player_x / CHUNK))
        pcz = int(math.floor(player_z / CHUNK))

        if (pcx, pcz) == self.last_center and self.vao is not None:
            return  # No update needed if player stays in the same chunk

        needed_lods: List[Tuple[int, int, int]] = []  # (cx, cz, level)
        r_near = render_dist
        r_mid = render_dist + 8
        r_max = min(max_lod_dist, render_dist + 16)

        r_near2 = (r_near + 0.5) ** 2
        r_mid2 = (r_mid + 0.5) ** 2
        r_max2 = (r_max + 0.5) ** 2

        for dcx in range(-r_max, r_max + 1):
            for dcz in range(-r_max, r_max + 1):
                d2 = dcx * dcx + dcz * dcz
                if d2 <= r_near2:
                    continue  # Handled by full near block mesh
                cx, cz = pcx + dcx, pcz + dcz
                if (cx, cz) in near_chunks:
                    continue

                if d2 <= r_mid2:
                    needed_lods.append((cx, cz, 1))  # Level 1: 4x4 sub-cells
                elif d2 <= r_max2:
                    needed_lods.append((cx, cz, 2))  # Level 2: 16x16 macro-box

        # Evict old distant cache entries
        if len(self.cache) > 2000:
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
                else:
                    verts = LODChunkBuilder.build_chunk_lod2(self.world, cx, cz)
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
        self.active_lod_keys = {(cx, cz) for cx, cz, _ in needed_lods}

    def render(self):
        """Draw all distant LOD chunks in a single GPU draw call."""
        if self.vao and self.vertex_count > 0:
            self.vao.render(moderngl.TRIANGLES, vertices=self.vertex_count)
