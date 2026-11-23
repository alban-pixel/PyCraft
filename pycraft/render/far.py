"""The distant terrain: a clipmap of columns, level after level, from textures the sampler
process (lod.py) fills in."""

import math

import moderngl
import numpy as np

from pycraft.tiles import block_colors
from pycraft.blocks import ATLAS_TILES
from pycraft.render.constants import (ATLAS_UNIT, COARSE_UNIT, COLORS_UNIT, COLUMN_FACES, DATA_UNIT,
                                      FAR_LIMIT, FINE_UNIT, LOD_BAND, LOD_MARGIN, LOD_STEP_MAX, LOD_STEP_MIN,
                                      LOD_TILES, READY_UNIT, TILE_AVG_UNIT, TINT_UNIT)
from pycraft.render.gl import boxes_visible, frustum_planes, matrix_bytes, set_uniforms
from pycraft.render.textures import tile_averages
from pycraft.lod import sample_step
from pycraft.terrain import CHUNK


def levels_for(spacing, size, reach):
    """The fewest levels that reach `reach` blocks (the rule of FarTerrain.levels)."""
    levels = 1
    while (size // 2 - LOD_MARGIN) * (spacing << (levels - 1)) < reach:
        levels += 1
    return levels


class FarTerrain:
    """The terrain beyond the blocks, as `levels` square grids of (size - 1)^2 columns around the
    camera, each twice as coarse and twice as wide as the one before (spacing to spacing x 2^levels
    blocks wide). Every column is drawn like a stack of blocks: the same blocks the generator puts
    there, with the same textures and light as the blocks near the camera, and trees as crowns of
    leaves. Heights, colors and blocks live in textures that wrap around: when the camera moves, only
    the new rows or columns at the edge are sampled. Each level gives way to the next one cell by
    cell (see CELLS). The LOD quality setting picks (spacing, size, levels) from LOD_QUALITIES.

    The texels come from the sampler's process (lod.py), a job at a time. A level's grid only
    follows the camera once its new cells have landed: until then the level is drawn where it
    was, so the textures never show cells that are not sampled yet."""

    def __init__(self, ctx, program, world, atlas_texture, tint_texture, tiles, sampler, spacing=2, size=128,
                 levels=7):
        self.ctx, self.program, self.atlas, self.tint = ctx, program, atlas_texture, tint_texture
        self.tiles = tiles  # kept to rebuild the tile averages if the quality changes
        self.spacing, self.size, self.n_levels = spacing, size, levels
        self.sampler = sampler  # lod.SamplerProcess: it makes the texels
        n = size
        # A column, drawn once per cell: its top and two of its sides, which the shader puts on
        # the sides to draw (the other two can't be seen, nor the bottom) and stretches down to
        # the top of the column each one faces. Most of the card's time for the distant terrain
        # goes into the vertices and the small triangles of the columns in view: 12 vertices and
        # 6 triangles a column, not the 30 and 10 of a cube without its bottom
        verts, indices = [], []
        for normal, face in COLUMN_FACES:
            indices += [len(verts) + i for i in (0, 1, 2, 0, 2, 3)]
            verts += [corner + normal for corner in face]
        self.vbo = ctx.buffer(np.array(verts, dtype="f4").tobytes())
        self.ibo = ctx.buffer(np.array(indices, dtype="u4").tobytes())
        self.vao = ctx.vertex_array(program, [(self.vbo, "3f 3f", "in_pos", "in_norm")], index_buffer=self.ibo)
        # The grid's tiles: the cell at the corner of each one, and the list sent to the shader
        self.tile_width = n // LOD_TILES
        t = np.arange(LOD_TILES) * self.tile_width
        self.tile_cells = np.stack(np.meshgrid(t, t, indexing="xy"), axis=-1).reshape(-1, 2).astype("i4")
        self.tile_list = np.zeros((LOD_TILES ** 2, 2), dtype="i4")
        # The heights of every texel (the ground, and the column with its crown), kept here too:
        # the lowest and highest of each tile say whether it can be in view
        self.grounds = [np.zeros((n, n), dtype="f4") for _ in range(levels)]
        self.crowns = [np.zeros((n, n), dtype="f4") for _ in range(levels)]
        self.height_stamps = [0] * levels  # counts the writes into a level's heights
        self.tile_heights = [None] * levels  # (origin, stamp, lowest, highest of each tile)
        self.data_maps = [ctx.texture((n, n), 4, dtype="u4") for _ in range(levels)]
        self.color_maps = [ctx.texture((n, n), 4, dtype="f1") for _ in range(levels)]
        self.tile_avg = ctx.texture((ATLAS_TILES * ATLAS_TILES, 2), 4,
                                    tile_averages(tiles).transpose(1, 0, 2).tobytes(), dtype="f4")
        for tex in self.data_maps + self.color_maps + [self.tile_avg]:
            tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        # Which texels have water, and how high: the water pass only draws the tiles that have some
        self.wet_masks = [np.zeros((n, n), dtype="u1") for _ in range(levels)]
        self.waters = [np.zeros((n, n), dtype="f4") for _ in range(levels)]
        self.version = 0  # counts the changes (the shadow maps of the terrain are drawn again)
        self.view_distance = FAR_LIMIT  # beyond it the fog hides everything: no level drawn there
        self.block_colors = block_colors(tiles)  # flat colors for plants and player's blocks
        self.set_world(world)

    def set_world(self, world):
        """Start over, with another world (or with the same one, for a new grid)."""
        self.world = world
        self.origins = [None] * self.n_levels  # grid coordinates of each level's point (0, 0); None: nothing landed
        self.working = False  # the sampler has a job of ours
        self.pending = 0  # cells the sampler has yet to sample again (changes climbing the levels)
        self.edits = set()  # finest cells where the player changed a block since the last job
        self.shown = (0, -1)  # the levels drawn in the last frame (first, last)
        self.block_reach = 0.0  # how far from the camera blocks can be drawn (set by the renderer)
        for mask in self.wet_masks:
            mask.fill(0)
        self.sampler.configure(world, self.spacing, self.size, self.n_levels, self.block_colors)
        self.version += 1

    def block_changed(self, x, y, z):
        """A block the player changed may show in the distant terrain: the finest cell it stands
        in is sampled again, and the change climbs the levels from there."""
        self.sampler.block_changed(x, y, z, self.world.get(x, y, z))
        self.edits.add((math.floor(x / self.spacing), math.floor(z / self.spacing)))

    def update(self, cam):
        """Write the texels the sampler has finished, then ask it for the cells the camera's
        moves bring into the grids."""
        n = self.size
        for msg in self.sampler.finished():
            if msg[0] == "level":
                _, _, level, origin, runs, rgba, data, wet = msg
                self._upload_runs(level, runs, rgba, data, wet)
                self.origins[level] = origin  # the grid moves now that its cells are there
                self.version += 1
            else:  # ("done", number, cells left to sample again)
                self.working, self.pending = False, msg[2]
        if self.working:
            return
        wanted = self.levels()
        batch, origins = [], [None] * self.n_levels
        for level in range(wanted):
            spacing = self.spacing << level
            old = self.origins[level]
            new = (math.floor(cam[0] / spacing) - n // 2, math.floor(cam[2] / spacing) - n // 2)
            whole = old is None or max(abs(new[0] - old[0]), abs(new[1] - old[1])) >= n // 2
            if not whole:
                # Only the new columns (x) and rows (z) that come into view, a few steps at a time
                new = tuple(o + (max(-LOD_STEP_MAX, min(LOD_STEP_MAX, v - o)) if abs(v - o) >= LOD_STEP_MIN else 0)
                            for o, v in zip(old, new))
            # On Earth, the grid stays where it is until the tiles of its new place are there
            if new != old and not self.world.level_ready(new[0] * spacing, new[1] * spacing, (new[0] + n) * spacing,
                                                         (new[1] + n) * spacing, sample_step(spacing)):
                origins[level] = old
                continue
            xs = new[0] + (np.arange(n) - new[0]) % n  # grid x of each texel column
            zs = new[1] + (np.arange(n) - new[1]) % n  # grid z of each texel row
            if whole:
                # A whole level (a new world, a jump far away). Texel (u, v) holds grid point
                # (x, z) with x & (n - 1) == u and z & (n - 1) == v
                batch.append((level, xs, zs))
            else:
                gx = range(old[0] + n, new[0] + n) if new[0] > old[0] else range(new[0], old[0])
                batch += [(level, np.array([x]), zs) for x in gx]
                gz = range(old[1] + n, new[1] + n) if new[1] > old[1] else range(new[1], old[1])
                batch += [(level, xs, np.array([z])) for z in gz]
            origins[level] = new
        for level in range(wanted, self.n_levels):
            self.origins[level] = None  # beyond the view: left alone, sampled again if the view grows
        if batch or self.edits or self.pending:
            self.sampler.request(batch, origins, self.edits)
            self.working, self.edits = True, set()

    def _upload_runs(self, level, runs, rgba, data, wet):
        """Write a level's runs of texels (xs, zs), one after the other in the arrays, into its
        textures, wet mask included."""
        n = self.size
        start = 0
        for xs, zs in runs:
            end = start + len(xs) * len(zs)
            u, v = int(xs[0]) % n, int(zs[0]) % n
            viewport = (u, v, len(xs), len(zs))
            self.data_maps[level].write(data[start:end].tobytes(), viewport=viewport)
            self.color_maps[level].write(rgba[start:end].tobytes(), viewport=viewport)
            self.wet_masks[level][u:u + len(xs), v:v + len(zs)] = (
                wet[start:end].reshape(len(zs), len(xs)).T)
            ground = data[start:end, 0].view("f4").reshape(len(zs), len(xs)).T
            packed = data[start:end, 1].reshape(len(zs), len(xs)).T
            self.grounds[level][u:u + len(xs), v:v + len(zs)] = ground
            self.crowns[level][u:u + len(xs), v:v + len(zs)] = ground + np.where((packed >> 16) & 255, packed >> 24, 0)
            self.waters[level][u:u + len(xs), v:v + len(zs)] = data[start:end, 2].view("f4").reshape(len(zs), len(xs)).T
            start = end
        self.height_stamps[level] += 1

    def tile_bounds(self, level):
        """(lowest, highest) height that the columns and the water of each tile of a level's grid
        can reach, and whether the tile has water, in the order of tile_cells. Worked out again
        only when the grid moved or got new cells."""
        origin, stamp = self.origins[level], self.height_stamps[level]
        cached = self.tile_heights[level]
        if cached is None or cached[0] != origin or cached[1] != stamp:
            n, t, w = self.size, LOD_TILES, self.tile_width
            shift = (-(origin[0] % n), -(origin[1] % n))  # texels (wrapping around) -> cells of the grid
            low = np.roll(self.grounds[level], shift, axis=(0, 1)).reshape(t, w, t, w).min(axis=(1, 3))
            high = np.roll(np.maximum(self.crowns[level], self.waters[level]), shift,
                           axis=(0, 1)).reshape(t, w, t, w).max(axis=(1, 3))
            wet = np.roll(self.wet_masks[level], shift, axis=(0, 1)).reshape(t, w, t, w).any(axis=(1, 3))
            # A side goes down to the top of the column it faces, which may be in the next tile,
            # and a little further where two levels meet or at the edge of the grid
            around = np.pad(low, 1, mode="edge")
            low = np.min([around[1 + i:1 + i + t, 1 + j:1 + j + t] for i in (-1, 0, 1) for j in (-1, 0, 1)], axis=0)
            spacing = self.spacing << level
            cached = (origin, stamp, low.T.ravel() - 4.0 * spacing - 1.0, high.T.ravel() + 1.0, wet.T.ravel())
            self.tile_heights[level] = cached
        return cached[2:]

    def levels(self):
        """The levels the view needs: up to the first that reaches past the view distance."""
        for level in range(self.n_levels):
            if (self.size // 2 - LOD_MARGIN) * (self.spacing << level) >= self.view_distance:
                return level + 1
        return self.n_levels

    def progress(self):
        """Share of the levels the view needs that have landed (for the loading screen)."""
        wanted = self.levels()
        return sum(origin is not None for origin in self.origins[:wanted]) / wanted

    def drawn_levels(self, cam):
        """(first, last) of the levels to draw, (0, -1) for none: the longest run of levels
        whose grids are around the camera — the coarser run, of two as long. A level whose cells
        are late (a jump far away, a camera faster than the sampler) is left out until its grid
        has caught up to an eighth of its width: each grid then fits well inside the next one."""
        n = self.size
        best, start = (0, -1), None
        wanted = self.levels()
        for level in range(wanted + 1):
            near = False
            if level < wanted and self.origins[level] is not None:
                spacing = self.spacing << level
                ox, oz = self.origins[level]
                near = max(abs(math.floor(cam[0] / spacing) - n // 2 - ox),
                           abs(math.floor(cam[2] / spacing) - n // 2 - oz)) <= n // 8
            if near and start is None:
                start = level
            elif not near and start is not None:
                if level - start >= best[1] - best[0] + 1:
                    best = (start, level - 1)
                start = None
        return best

    def tiles_in_view(self, planes, cam, first, last, rects):
        """For each level from first to last, the corner cells of the tiles of its grid to draw,
        nearest first, those of them that reach where blocks are drawn, and those that have
        water. A tile is left out
        when a box around it, from the foot of its lowest column to the top of its highest, is
        outside one of the planes, or when the finer level draws all of its cells (the hole in
        the middle of a level). Without this every cell of every grid goes through the vertex
        shader each frame, and at the finest qualities that is where the card's time went: more
        than two thirds of the cells are behind the camera, beside the view or under it."""
        levels = range(first, last + 1)
        spacing = np.array([float(self.spacing << level) for level in levels])[:, None]
        corner = np.array([rects[level][:2] for level in levels])
        lo_x = corner[:, :1] + self.tile_cells[None, :, 0] * spacing
        lo_z = corner[:, 1:] + self.tile_cells[None, :, 1] * spacing
        hi_x, hi_z = lo_x + self.tile_width * spacing, lo_z + self.tile_width * spacing
        pad = 0.5 * spacing  # (the sides at the edge of a grid and the faces' overlap reach a little outside)
        heights = [self.tile_bounds(level) for level in levels]
        bottom = np.array([h[0] for h in heights]) - cam[1]
        top = np.array([h[1] for h in heights]) - cam[1]
        lo = np.stack([lo_x - pad, bottom, lo_z - pad], axis=-1)
        hi = np.stack([hi_x + pad, top, hi_z + pad], axis=-1)
        show = boxes_visible(planes, lo.reshape(-1, 3), hi.reshape(-1, 3)).reshape(lo_x.shape)
        lo[..., 1] = -1.0 - cam[1]  # (the sides around the blocks go down to the bottom of the world)
        deep = boxes_visible(planes, lo.reshape(-1, 3), hi.reshape(-1, 3)).reshape(lo_x.shape)
        for i, level in enumerate(levels):
            if level > first:  # the cells well inside the finer level's square are all drawn by it
                x0, z0, x1, z1 = rects[level - 1]
                m = (LOD_MARGIN + LOD_BAND) * 0.5 * spacing[i, 0]
                show[i] &= ~((lo_x[i] >= x0 + m) & (hi_x[i] <= x1 - m) & (lo_z[i] >= z0 + m) & (hi_z[i] <= z1 - m))
        near = (lo_x + hi_x) ** 2 + (lo_z + hi_z) ** 2  # nearest first: what is behind is not shaded for nothing
        gap_x, gap_z = np.maximum(np.maximum(lo_x, -hi_x), 0.0), np.maximum(np.maximum(lo_z, -hi_z), 0.0)
        by_blocks = deep & (gap_x ** 2 + gap_z ** 2 < self.block_reach ** 2)
        out = []
        for i in range(len(spacing)):
            order = np.flatnonzero(show[i])[np.argsort(near[i][show[i]])]
            out.append((self.tile_cells[order], self.tile_cells[by_blocks[i]], self.tile_cells[order[heights[i][2][order]]]))
        return out

    def render(self, vp, cam, chunks, shadow=False):
        first, last = self.drawn_levels(cam)
        if not shadow:
            self.shown = (first, last)
        if last < first:
            return
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
        set_uniforms(p, {"data": DATA_UNIT, "coarse_data": COARSE_UNIT, "fine_data": FINE_UNIT,
                         "colors": COLORS_UNIT, "tile_avg": TILE_AVG_UNIT,
                         "atlas": ATLAS_UNIT, "tint_mask": TINT_UNIT, "grid_size": self.size})
        planes = frustum_planes(vp)
        p["clip_planes"].write(planes[[0, 1, 4]].astype("f4").tobytes())  # left right near
        p["tile_width"] = self.tile_width
        p["block_reach"] = self.block_reach
        p["lee"] = (float(vp[2][0]), float(vp[2][2])) if shadow else (0.0, 0.0)  # (depth grows away from the light)
        self.atlas.use(ATLAS_UNIT)
        self.tint.use(TINT_UNIT)
        self.tile_avg.use(TILE_AVG_UNIT)
        rects = {}
        for level in range(first, last + 1):
            spacing = self.spacing << level
            gx, gz = self.origins[level]
            ox, oz = gx * spacing - cam[0], gz * spacing - cam[2]
            extent = (self.size - 1) * spacing
            rects[level] = (float(ox), float(oz), float(ox + extent), float(oz + extent))
        tiles = self.tiles_in_view(planes[:5], cam, first, last, rects)
        # The ground and the aquatic floor first, then the water over them: see-through like the
        # blocks' water. It only needs its top face (the mesh's first 6 vertices): the ground
        # columns close the edges, and the shadow maps skip water anyway. And only the tiles that
        # have water are drawn
        for wpass in ((0,) if shadow else (0, 1)):
            if wpass:
                ctx = self.ctx
                ctx.enable(moderngl.BLEND)
                ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
                ctx.fbo.depth_mask = False
            p["water_pass"] = wpass
            for level in range(first, last + 1):
                finer, coarser = level > first, level < last
                set_uniforms(p, {"level": level, "grid_origin": self.origins[level], "origin": rects[level][:2],
                                 "spacing": float(self.spacing << level), "own": rects[level],
                                 "fade_own": int(coarser),
                                 "coarse_origin": self.origins[level + 1] if coarser else (0, 0),
                                 "inner": rects[level - 1] if finer else (0.0, 0.0, 0.0, 0.0),
                                 "fade_inner": int(finer),
                                 "fine_origin": self.origins[level - 1] if finer else (0, 0)})
                # (a level without a neighbor gets its own grid in its place: never read, but an
                # integer texture must be bound where the shader has an integer sampler)
                self.data_maps[level].use(DATA_UNIT)
                self.data_maps[level + 1 if coarser else level].use(COARSE_UNIT)
                self.data_maps[level - 1 if finer else level].use(FINE_UNIT)
                self.color_maps[level].use(COLORS_UNIT)
                if wpass:
                    cells = tiles[level - first][2]
                    if len(cells):
                        self.tile_list[:len(cells)] = cells
                        p["tiles"].write(self.tile_list.tobytes())
                        self.vao.render(vertices=6, instances=len(cells) * self.tile_width ** 2)
                else:
                    cells, by_blocks = tiles[level - first][:2]
                    if len(cells):
                        self.tile_list[:len(cells)] = cells
                        p["tiles"].write(self.tile_list.tobytes())
                        self.vao.render(vertices=18, instances=len(cells) * self.tile_width ** 2)
                    if len(by_blocks) and not shadow:  # the two other sides (the mesh's last 12 vertices)
                        self.tile_list[:len(by_blocks)] = by_blocks
                        p["tiles"].write(self.tile_list.tobytes())
                        p["far_sides"] = 1
                        self.vao.render(vertices=12, first=6, instances=len(by_blocks) * self.tile_width ** 2)
                        p["far_sides"] = 0
            if wpass:
                ctx.fbo.depth_mask = True
                ctx.disable(moderngl.BLEND)
