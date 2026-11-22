"""The distant terrain's sampler: what every cell of every level of detail looks like.

The distant terrain (render.far.FarTerrain) is drawn from textures that hold, for each cell of each
of its levels, the height of the ground, its top blocks, a color, and how much of the cell trees
and water cover. This module makes those texels, from the terrain generator and from the blocks
the player changed.

It runs in a process of its own. Sampling a whole level takes seconds, far too long for a frame,
and a thread beside the game doesn't do: the game's thread spends its time inside OpenGL calls,
which keep Python's lock, so a sampling thread waits for a whole call at each of its thousands of
steps. On a PC that can't hold its frame rate, a first sampling of 12 seconds took minutes, and
the world beyond the blocks stayed empty. In its own process the sampler also spreads the work
over a few threads: there, NumPy really runs them side by side. And a whole level to sample is
shared with the terrain builders' processes (builder.py) that have nothing to build.
"""
import concurrent.futures
import multiprocessing
import os
import queue
import threading
import time
import traceback

import numpy as np

from pycraft import blocks as B
from pycraft import terrain as T
from pycraft.blocks import ACACIA_LEAVES, ALL_LEAVES, BIRCH_LEAVES, ICE, JUNGLE_LEAVES, LEAVES, SPRUCE_LEAVES
from pycraft.builder import TINT, WATER_SURFACE
from pycraft.terrain import CHUNK
from pycraft.world import World

LOD_SUB = 2  # directly sampled cells: sub-samples per side of a cell's footprint, aggregated together
LOD_DIRTY_PER_JOB = 256  # cells sampled again per job at most, for a block the player changed under them
LOD_FRESH_PER_JOB = 4096  # and cells made again of their finer cells, when those have just come into the grid
CROWN_MIN_COV = 38  # canopy coverage (of 255) under which a cell gets no crown of leaves
CANOPY_SHADE = 0.3  # how much a full canopy darkens the ground under it
PLANT_MIX = 0.3  # share of a plant's color mixed into the ground it grows on
CUSTOM = 255  # "block" of a column carrying its own color: the blocks the player changed
# Threads sampling side by side: more than 6 only get in each other's way (they share Python's lock
# between two NumPy calls)
SAMPLER_THREADS = min(max((os.cpu_count() or 4) // 3, 2), 6)
CHUNK_POINTS = 32768  # points sampled in one go: few enough to stay in the processor's cache
HELP_FROM = 4  # a job of at least this many chunks is shared with the terrain builders
HELP_TIMEOUT = 20.0  # seconds without a chunk coming back before the sampler does the rest itself

# The leaves of each biome's trees, and how high their crowns reach above the ground (the average
# of its kinds of trees, weighted by how many there are)
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


class Cancelled(Exception):
    """The job being done is not wanted any more (another world, another LOD quality)."""


class Sampler:
    """Makes the texels of a distant terrain of `levels` grids of size x size cells, the finest
    ones `spacing` blocks wide. It remembers what every level knows about each of its cells (see
    _aggregate), so that a coarser level can be made of the finer cells under it: the cascade."""

    def __init__(self, world, spacing, size, levels, block_colors, threads=SAMPLER_THREADS, alive=lambda: True,
                 shared=None, number=0):
        """shared: (work, done), the queues where big jobs are shared with the terrain builders;
        number: tells this sampler's chunks from those of another one in them."""
        self.world = world
        self.threads, self.shared, self.number = threads, shared, number
        self.calls = 0  # counts the shared jobs
        self.spacing, self.size, self.n_levels = spacing, size, levels
        self.block_colors = block_colors  # flat colors for plants and the player's blocks
        self.alive = alive  # False once this sampler's work is not wanted any more
        self.origins = [None] * levels  # grid coordinates of each level's point (0, 0), once the job at hand is done
        # What each level knows about every cell of its grid: the values a level hands to the
        # coarser one for the cells it covers, texel for texel
        self.rec = [self._new_records() for _ in range(levels)]
        # Cells to make again, level by level. marks: a block changed under them — sampled again
        # whatever it takes. fresh: their finer cells have just come into the finer grid — made
        # again as the aggregate of those, once all four are there (cheap), else left as they are
        self.marks = [set() for _ in range(levels)]
        self.fresh = [set() for _ in range(levels)]
        self.pool = (concurrent.futures.ThreadPoolExecutor(threads, thread_name_prefix="lod sampler")
                     if threads > 1 else None)

    def close(self):
        if self.pool is not None:
            self.pool.shutdown(wait=False, cancel_futures=True)

    def _new_records(self):
        """An empty grid of cells for one level. tagx/tagz say which grid point each texel
        currently holds: a cell's children are usable only where the tags match."""
        n = self.size
        return {"ground": np.zeros((n, n), "f4"), "wsurf": -np.ones((n, n), "f4"),
                "surf": np.zeros((n, n), "u1"), "fill": np.zeros((n, n), "u1"),
                "leaves": np.zeros((n, n), "u1"), "crown": np.zeros((n, n), "u1"),
                "cov": np.zeros((n, n), "u1"), "wetcov": np.zeros((n, n), "u1"),
                "icecov": np.zeros((n, n), "u1"), "flags": np.zeros((n, n), "u1"),
                "depth": np.zeros((n, n), "u1"), "tint": np.zeros((n, n, 3), "u1"),
                "tagx": np.full((n, n), -(1 << 30), "i4"), "tagz": np.full((n, n), -(1 << 30), "i4")}

    # --- Sampling the generator ------------------------------------------------------------------

    def _fields(self, s, x, z, sx, sz, level, slope):
        """Sub-records at world points (x, z), sub-lattice cells (sx, sz) of a level, from the
        generator's samples s there and their slope (blocks of drop per block): one value per
        array, everything the aggregation needs to weigh over a cell's footprint."""
        gen = self.world.gen
        top = np.floor(s["height"]).astype(np.int32)
        wet = top < s["water"]
        ice = wet & (s["temperature"] < -0.55)
        # The column is the ground itself — the aquatic floor too, under the water. The water is
        # another column on top of it, see-through like the blocks' (a solid ice column where the
        # water is frozen, a full block tall like the ice blocks are)
        f = {"ground": np.where(ice, s["water"] + 1.0, top + 1).astype("f4"),
             "wsurf": np.where(wet & ~ice, s["water"] + WATER_SURFACE, -1.0).astype("f4"),
             "flags": np.zeros(x.shape, "u1")}
        # The same top blocks as the generator's, bare rock where it is too steep for soil included
        surface, filler, _ = T._surface(s, top, slope, gen.surface.fbm2(x / 9, z / 9, 2) * 2)
        surface = np.where(ice, ICE, surface)
        filler = np.where(ice, ICE, filler)
        f["surf"], f["fill"] = surface.astype("u1"), filler.astype("u1")
        # Trees: a sub-cell is under a crown as often as the biome's trees cover the ground (never
        # on a slope, like the generator's trees); the coverage becomes a continuous value when the
        # cell's sub-samples are aggregated
        biome = s["biome"]
        trees = ((cell_hashes(sx, sz, level) < T.CANOPY[biome]) & ~wet & (slope <= 1)
                 & np.isin(surface, (B.GRASS, B.PODZOL, B.SNOW)))
        f["leaves"] = np.where(trees, CANOPY_LEAVES[biome], 0).astype("u1")
        f["crown"] = np.where(trees, CANOPY_HEIGHT[biome], 0).astype("u1")
        f["cov"] = (trees * 255).astype("u1")
        f["wetcov"] = ((wet & ~ice) * 255).astype("u1")
        f["icecov"] = (ice * 255).astype("u1")
        grass, _, water = T.tints(s["temperature"], s["humidity"], biome)
        tint = np.where(wet[:, None], water, grass)
        # Plants have no geometry out here, but their color still speckles the ground
        plants = T._scatter_plants(gen, x, z, biome, surface, top, s["water"])
        has_plant = plants > 0
        if has_plant.any():
            pcolor = self.block_colors[plants]
            tinted = TINT[plants] == 1  # grass-tinted plants take the biome's color
            pcolor[tinted] *= tint[tinted]
            tint[has_plant] = tint[has_plant] * (1 - PLANT_MIX) + pcolor[has_plant] * PLANT_MIX
        f["tint"] = (np.clip(tint, 0, 1) * 255).astype("u1")
        f["depth"] = np.clip(np.where(wet, s["water"] - top, 0), 0, 255).astype("u1")  # down to the bottom
        return f

    def _aggregate(self, f):
        """Merge K sub-records per cell into one record: the mean solid top, the majority top
        block (the highest sub-column wins ties), continuous canopy and water coverage, colors
        averaged in a perceptual space, and an emissive flag that never dies out."""
        K = f["ground"].shape[1]
        n = f["ground"].shape[0]
        out = {"ground": f["ground"].mean(axis=1)}
        wet = f["wetcov"].astype("f4") / 255
        ice = f["icecov"].astype("f4") / 255
        out["wetcov"] = (wet.mean(axis=1) * 255).astype("u1")
        out["icecov"] = (ice.mean(axis=1) * 255).astype("u1")
        wsum = np.maximum(wet.sum(axis=1), 1e-9)
        wsurf = (f["wsurf"] * wet).sum(axis=1) / wsum  # the liquid water's mean surface
        frozen = out["icecov"] > out["wetcov"]  # the frozen part wins: the cell is ice
        out["wsurf"] = np.where(frozen | (wet.sum(axis=1) == 0), -1.0, wsurf)
        # Top block: the majority rules, and the higher the sub-column the bigger its say —
        # a tower poking far above the cell's mean outvotes the lowland it stands on (the
        # drawn top face sits where the tall part's material is, not where the valley's is)
        surf = f["surf"].astype("u4")
        votes = (surf[:, :, None] == surf[:, None, :]).sum(axis=2).astype("f4")
        votes += np.clip(f["ground"] - out["ground"][:, None], 0, 32) / 4
        win = votes.argmax(axis=1)
        out["surf"] = surf[np.arange(n), win].astype("u1")
        out["fill"] = f["fill"][np.arange(n), win]
        cov = f["cov"].astype("f4") / 255
        out["cov"] = (cov.mean(axis=1) * 255).astype("u1")
        # Crown: the leaf kind with the most coverage wins; under the threshold no crown at all
        lw = np.zeros((n, 256), "f4")
        np.add.at(lw, (np.repeat(np.arange(n), K), f["leaves"].ravel()), cov.ravel())
        out["leaves"] = lw.argmax(axis=1).astype("u1")
        cw = np.maximum((cov * (f["crown"] > 0)).sum(axis=1), 1e-9)
        out["crown"] = np.clip((f["crown"] * cov).sum(axis=1) / cw, 0, 255).astype("u1")
        bare = out["cov"] < CROWN_MIN_COV
        out["leaves"][bare] = out["crown"][bare] = 0
        out["tint"] = np.clip(oklab_to_srgb(srgb_to_oklab(f["tint"].astype("f4") / 255).mean(axis=1)) * 255,
                              0, 255).astype("u1")
        out["depth"] = np.clip((f["depth"] * wet).sum(axis=1) / wsum, 0, 255).astype("u1")
        out["flags"] = f["flags"].max(axis=1)
        return out

    def _empty(self, count):
        return {"ground": np.zeros(count, "f4"), "wsurf": -np.ones(count, "f4"),
                "surf": np.zeros(count, "u1"), "fill": np.zeros(count, "u1"),
                "leaves": np.zeros(count, "u1"), "crown": np.zeros(count, "u1"),
                "cov": np.zeros(count, "u1"), "wetcov": np.zeros(count, "u1"),
                "icecov": np.zeros(count, "u1"), "flags": np.zeros(count, "u1"),
                "depth": np.zeros(count, "u1"), "tint": np.zeros((count, 3), "u1")}

    def _sample_cells(self, level, gx, gz, sub):
        """Records of cells (gx, gz), sampled from the generator: in chunks, on several threads."""
        spacing = self.spacing << level
        sub = min(sub, spacing)  # no sub-samples finer than a block: spacing 1 means one
        size = max(CHUNK_POINTS // (sub * sub), 1)
        parts = [slice(i, i + size) for i in range(0, len(gx), size)]

        def chunk(part):
            if not self.alive():
                raise Cancelled
            return self._sample_chunk(level, gx[part], gz[part], sub)

        if self.shared is not None and self.pool is not None and len(parts) >= HELP_FROM:
            recs = self._sample_shared(level, gx, gz, sub, parts)
        elif self.pool is None or len(parts) == 1:
            recs = [chunk(p) for p in parts]
        else:
            recs = list(self.pool.map(chunk, parts))
        return recs[0] if len(recs) == 1 else {k: np.concatenate([r[k] for r in recs]) for k in recs[0]}

    def _sample_shared(self, level, gx, gz, sub, parts):
        """The records of each part of cells (gx, gz), sampled by whoever is free: every part
        goes into a queue, from which this process's threads take them — and so do the terrain
        builders' processes when they have nothing to build (builder._help_sampler). A whole
        level is seconds of work for one process, and the builders have the same world."""
        work, done = self.shared
        self.calls += 1
        call = (self.number, self.calls)
        for i, part in enumerate(parts):
            work.put((call, i, self.world.seed, self.world.earth, self.spacing, self.block_colors, level, gx[part],
                      gz[part], sub))
        recs = [None] * len(parts)
        missing = set(range(len(parts)))
        lock = threading.Lock()
        progress = [time.perf_counter()]

        def finish(i, rec):
            with lock:
                if i in missing:
                    recs[i] = rec
                    missing.discard(i)
                    progress[0] = time.perf_counter()

        def local():
            while missing and self.alive():
                try:
                    item = work.get(timeout=0.02)
                except queue.Empty:
                    continue
                if item[0] == call:  # (else a leftover of a job that was given up)
                    finish(item[1], self._sample_chunk(level, item[7], item[8], sub))

        threads = [self.pool.submit(local) for _ in range(self.threads)]
        while missing and self.alive():
            try:
                c, i, rec = done.get(timeout=0.02)
            except queue.Empty:
                if all(t.done() for t in threads) or time.perf_counter() - progress[0] > HELP_TIMEOUT:
                    # (the threads stopped on an error, or a builder went away with a chunk)
                    for i in list(missing):
                        finish(i, self._sample_chunk(level, gx[parts[i]], gz[parts[i]], sub))
                continue
            if c == call:  # (a builder answers None when it has another world: done here then)
                finish(i, rec if rec is not None else self._sample_chunk(level, gx[parts[i]], gz[parts[i]], sub))
        for t in threads:
            t.result()  # (an error in a thread is raised here)
        if missing:
            raise Cancelled
        return recs

    def _sample_chunk(self, level, gx, gz, sub):
        """Records of cells (gx, gz): the footprint of each is sampled at sub x sub points and
        aggregated. The edited columns are read at every level."""
        world = self.world
        spacing = self.spacing << level
        step = spacing // sub  # blocks between two sub-samples
        # The sub-samples of all the cells lie on one lattice of points `step` blocks apart. A
        # point's slope is its biggest height difference with the 4 points next to it — the slope
        # the generator gives a column of blocks. So the points around the cells are sampled too
        x0, z0 = int(gx.min()), int(gz.min())
        w, h = int(gx.max()) - x0 + 1, int(gz.max()) - z0 + 1
        cells = np.zeros((w, h), bool)
        cells[gx - x0, gz - z0] = True
        want = np.zeros((w * sub + 2, h * sub + 2), bool)  # the cells' points, in a border of one point
        want[1:-1, 1:-1] = np.repeat(np.repeat(cells, sub, axis=0), sub, axis=1)
        need = want.copy()  # with the points next to them
        need[1:] |= want[:-1]
        need[:-1] |= want[1:]
        need[:, 1:] |= want[:, :-1]
        need[:, :-1] |= want[:, 1:]
        px, pz = np.nonzero(need)
        lx, lz = px + (x0 * sub - 1), pz + (z0 * sub - 1)  # the points' places on the lattice
        x, z = (lx + 0.5) * step, (lz + 0.5) * step
        # The broad climate (a kilometer-scale field) is evaluated once per cell under 32 blocks
        # of spacing — it does not meaningfully change across them — and shared by the sub-samples
        clim = None
        if sub > 1 and spacing < 32:
            cx, cz = lx // sub - (x0 - 1), lz // sub - (z0 - 1)  # each point's cell, in a border of one cell
            used = np.zeros((w + 2, h + 2), bool)
            used[cx, cz] = True
            ux, uz = np.nonzero(used)
            where = np.zeros((w + 2, h + 2), np.int64)
            where[ux, uz] = np.arange(len(ux))
            pick = where[cx, cz]
            clim = {k: v[pick] for k, v in
                    world.gen.climate((ux + x0 - 0.5) * spacing, (uz + z0 - 0.5) * spacing).items()}
        s = world.gen.sample(x, z, clim, step)
        top = np.zeros(need.shape, np.int32)
        top[px, pz] = np.floor(s["height"])
        drop = np.zeros(need.shape, np.int32)  # (right at the cells' points: all their neighbors were sampled)
        mid = top[1:-1, 1:-1]
        for other in (top[2:, 1:-1], top[:-2, 1:-1], top[1:-1, 2:], top[1:-1, :-2]):
            np.maximum(drop[1:-1, 1:-1], np.abs(mid - other), out=drop[1:-1, 1:-1])
        # The cells' own points, cell after cell (x first), among the sampled ones
        index = np.zeros(need.shape, np.int64)
        index[px, pz] = np.arange(len(px))
        side = np.arange(sub)
        ix = np.broadcast_to(((gx - x0) * sub + 1)[:, None, None] + side[None, :, None], (len(gx), sub, sub)).ravel()
        iz = np.broadcast_to(((gz - z0) * sub + 1)[:, None, None] + side[None, None, :], (len(gz), sub, sub)).ravel()
        sel = index[ix, iz]
        s = {k: v[sel] for k, v in s.items()}
        x, z, sx, sz = x[sel], z[sel], lx[sel], lz[sel]
        slope = drop[ix, iz]
        if step > 1:
            # Points several blocks apart give the average slope between them: rounded up or
            # down at random (always the same way), a slope of 1.5 makes rock half of the time
            slope = np.floor(slope / step + cell_hashes(sx, sz, level + 97)).astype(np.int32)
        f = self._fields(s, x, z, sx, sz, level, slope)
        self._inject_edited(f, x, z, spacing, sub)  # the player's work shows at every level
        return self._aggregate({k: v.reshape(len(gx), -1, v.shape[-1]) if v.ndim == 2 else v.reshape(len(gx), -1)
                                for k, v in f.items()})

    # --- The blocks the player changed -------------------------------------------------------------

    def _block_fields(self, tops):
        """One sub-record per block of an edited column, from its real top: a crown of leaves
        sits on the block under it (the trunk), like the generator's trees; a block the shader
        doesn't know carries its own resolved color."""
        ty, tb = tops["top_y"], tops["top_b"]
        wy, fb = tops["water_y"], tops["fill_b"]
        leaf = np.isin(tb, ALL_LEAVES)
        lh = tops["leaf_h"]
        safe_leaf = np.where(tb <= B.MOSS, tb, LEAVES)  # unknown leaves look like oak
        custom = tb > B.MOSS
        surf = np.where(custom, CUSTOM, tb)
        surf = np.where(leaf, np.where(fb == B.AIR, safe_leaf, np.where(fb > B.MOSS, CUSTOM, fb)), surf)
        fill = np.where(fb == B.AIR, B.STONE, np.where(fb > B.MOSS, CUSTOM, fb))
        grass = tops["grass"].astype("f4")
        own = surf == CUSTOM
        which = np.where(custom | (leaf & (fb > B.MOSS)), np.where(custom, tb, fb), surf)
        tint = np.where(own[..., None],
                        self.block_colors[which] * np.where((TINT[which] > 0)[..., None], grass / 255, 1.0) * 255,
                        grass)
        pl = tops["plant"]  # plants have no geometry out here: their color speckles the ground
        pcolor = self.block_colors[pl] * 255
        pcolor[TINT[pl] == 1] *= grass[TINT[pl] == 1] / 255
        tint = np.clip(np.where((pl > 0)[..., None], tint * (1 - PLANT_MIX) + pcolor * PLANT_MIX, tint), 0, 255)
        return {"ground": np.where(leaf, ty - lh + 1, ty + 1).astype("f4"),
                "wsurf": np.where(wy > ty, wy + WATER_SURFACE, -1.0).astype("f4"),
                "surf": surf.astype("u1"), "fill": fill.astype("u1"),
                "leaves": np.where(leaf, safe_leaf, 0).astype("u1"),
                "crown": np.where(leaf, np.minimum(lh, 255), 0).astype("u1"),
                "cov": np.where(leaf, 255, 0).astype("u1"),
                "wetcov": np.where(wy > ty, 255, 0).astype("u1"),
                "icecov": np.zeros((CHUNK, CHUNK), "u1"),
                "flags": B.GLOWING[tb].astype("u1"),
                "depth": np.clip(np.where(wy > ty, wy - ty, 0), 0, 255).astype("u1"),
                "tint": tint.astype("u1")}

    def _inject_edited(self, f, x, z, spacing, sub):
        """Rewrite the sub-records that stand on columns the player changed, from their real
        tops: one block per sub-cell when the sub-cells are block-sized or finer, else the
        blocks each sub-cell covers aggregated together — a house stays a house at any level."""
        world, edited = self.world, self.world.edited_columns
        if not edited:
            return
        ss = spacing // sub  # blocks covered by one side of a sub-cell (>= 1: sub <= spacing)
        if ss == 1:
            # One block per sub-cell (the finest level): a direct lookup per sampled point
            bx, bz = np.floor(x).astype(np.int64), np.floor(z).astype(np.int64)
            cx, cz = bx >> 4, bz >> 4
            touched = set(zip(cx.tolist(), cz.tolist())) & edited.keys()
            for ccx, ccz in touched:
                tops = world.edited_tops(ccx, ccz)
                m = (cx == ccx) & (cz == ccz)
                if not m.any():
                    continue
                lx, lz = bx[m] & 15, bz[m] & 15
                if not tops["changed"][lx, lz].any():
                    continue
                bf = self._block_fields(tops)
                idx = np.nonzero(m)[0]
                for k in f:
                    f[k][idx] = bf[k][lx, lz]
            return
        sx, sz = np.floor(x / ss).astype(np.int64), np.floor(z / ss).astype(np.int64)
        for ccx, ccz in set(zip((sx * ss >> 4).tolist(), (sz * ss >> 4).tolist())) & edited.keys():
            tops = world.edited_tops(ccx, ccz)
            bf = self._block_fields(tops)
            gx0, gz0 = ccx * 16, ccz * 16
            for gsx in range(gx0 // ss - 1, (gx0 + 16) // ss + 1):
                for gsz in range(gz0 // ss - 1, (gz0 + 16) // ss + 1):
                    sel = (sx == gsx) & (sz == gsz)
                    if not sel.any():
                        continue
                    bx0, bz0 = max(gsx * ss - gx0, 0), max(gsz * ss - gz0, 0)
                    bx1, bz1 = min(gsx * ss + ss - gx0, 16), min(gsz * ss + ss - gz0, 16)
                    if bx1 <= bx0 or bz1 <= bz0 or not tops["changed"][bx0:bx1, bz0:bz1].any():
                        continue
                    rec = self._aggregate({k: v[bx0:bx1, bz0:bz1].reshape(1, -1) if k != "tint"
                                           else v[bx0:bx1, bz0:bz1].reshape(1, -1, 3)
                                           for k, v in bf.items()})
                    for k in f:
                        f[k][sel] = rec[k][0]

    # --- The cascade -------------------------------------------------------------------------------

    def _children_known(self, level, gx, gz):
        """Which cells of a level have all four finer children sampled in place: their records
        can be aggregated instead of sampling the generator again (cheaper, and it is what makes
        a level inherit the real detail — edited blocks included — of the level under it)."""
        n = self.size
        finer = self.rec[level - 1]
        o = self.origins[level - 1]
        if o is None:
            return np.zeros(gx.shape, bool)
        known = np.ones(gx.shape, bool)
        for dx, dz in ((0, 0), (1, 0), (0, 1), (1, 1)):
            cx, cz = 2 * gx + dx, 2 * gz + dz
            known &= ((cx >= o[0]) & (cx < o[0] + n) & (cz >= o[1]) & (cz < o[1] + n)
                      & (finer["tagx"][cx % n, cz % n] == cx) & (finer["tagz"][cx % n, cz % n] == cz))
        return known

    def _aggregate_children(self, level, px, pz):
        """A level's cells as the aggregate of the four finer cells covering each."""
        n = self.size
        fields = {}
        for k, arr in self.rec[level - 1].items():
            if k in ("tagx", "tagz"):
                continue
            fields[k] = np.stack([arr[(2 * px + dx) % n, (2 * pz + dz) % n]
                                  for dx, dz in ((0, 0), (1, 0), (0, 1), (1, 1))], axis=1)
        return self._aggregate(fields)

    def produce(self, level, gx, gz, strong=None, sub=LOD_SUB):
        """Records for the flat cells (gx, gz) of a level: finer records where they exist (the
        cascade), the generator's sampled sub-records elsewhere; remembered so the next level
        can aggregate them, and marked in it where they changed (in marks for the cells that
        `strong` flags, the ones made again for a block the player changed; in fresh otherwise)."""
        if level == 0:
            rec = self._sample_cells(0, gx, gz, sub)
        else:
            ok = self._children_known(level, gx, gz)
            if ok.all():
                rec = self._aggregate_children(level, gx, gz)
            else:
                rec = self._empty(len(gx))
                if ok.any():
                    casc = self._aggregate_children(level, gx[ok], gz[ok])
                    for k in rec:
                        rec[k][ok] = casc[k]
                if (~ok).any():
                    samp = self._sample_cells(level, gx[~ok], gz[~ok], sub)
                    for k in rec:
                        rec[k][~ok] = samp[k]
        # The parent only has to be resampled where the child actually changed — a cell
        # resampled to the same values is a no-op for the cascade
        n = self.size
        u, v = gx % n, gz % n
        f = self.rec[level]
        changed = ((f["tagx"][u, v] != gx) | (f["tagz"][u, v] != gz)
                   | (f["ground"][u, v] != rec["ground"]) | (f["wsurf"][u, v] != rec["wsurf"])
                   | (f["surf"][u, v] != rec["surf"]) | (f["fill"][u, v] != rec["fill"])
                   | (f["leaves"][u, v] != rec["leaves"]) | (f["crown"][u, v] != rec["crown"])
                   | (f["cov"][u, v] != rec["cov"]) | (f["wetcov"][u, v] != rec["wetcov"])
                   | (f["icecov"][u, v] != rec["icecov"]) | (f["flags"][u, v] != rec["flags"])
                   | (f["depth"][u, v] != rec["depth"]) | (f["tint"][u, v] != rec["tint"]).any(axis=1))
        for k, arr in f.items():  # remembered texel for texel, tagged by their grid point
            if k not in ("tagx", "tagz"):
                arr[u, v] = rec[k]
        f["tagx"][u, v] = gx
        f["tagz"][u, v] = gz
        if level + 1 < self.n_levels and changed.any():
            if strong is not None and (changed & strong).any():
                sel = changed & strong
                self.marks[level + 1].update(zip((gx[sel] >> 1).tolist(), (gz[sel] >> 1).tolist()))
                changed = changed & ~strong
            if changed.any():
                self.fresh[level + 1].update(zip((gx[changed] >> 1).tolist(), (gz[changed] >> 1).tolist()))
        return rec

    def _pack(self, rec):
        """Records to texels: biome color (rgba, the canopy's shade over the ground baked in) and
        the packed texel (ground top bits, then top block, the block under it, crown leaves or 0,
        crown height, then the water's surface bits or -1, then coverage and flags)."""
        cov = rec["cov"].astype("f4") / 255
        shade = np.where(rec["surf"] == CUSTOM, 1.0, 1.0 - CANOPY_SHADE * cov)
        rgba = np.concatenate([np.clip(rec["tint"].astype("f4") * shade[:, None], 0, 255),
                               rec["depth"][:, None].astype("f4")], axis=1).astype("u1")
        packed = (rec["surf"].astype("u4") | rec["fill"].astype("u4") << 8
                  | rec["leaves"].astype("u4") << 16 | rec["crown"].astype("u4") << 24)
        misc = (rec["cov"].astype("u4") | rec["wetcov"].astype("u4") << 8
                | rec["flags"].astype("u4") << 16 | rec["icecov"].astype("u4") << 24)
        data = np.stack([rec["ground"].astype("f4").view("u4"), packed,
                         rec["wsurf"].astype("f4").view("u4"), misc], axis=1)
        return rgba, data, rec["wsurf"] >= 0

    def _sample_runs(self, level, runs, strong=0):
        """Produce all the cells of the given writes (xs, zs) in one pass — sampling is much
        cheaper in one big batch — and pack them for the textures, run after run, rows along z.
        The last `strong` runs are cells made again for a block the player changed."""
        gx, gz, flags = [], [], []
        for i, (xs, zs) in enumerate(runs):
            rz, rx = np.meshgrid(zs, xs, indexing="ij")  # texture rows are z
            gx.append(rx.ravel())
            gz.append(rz.ravel())
            flags.append(np.full(rx.size, i >= len(runs) - strong))
        return self._pack(self.produce(level, np.concatenate(gx), np.concatenate(gz), np.concatenate(flags)))

    def _dirty_runs(self, marks, level, budget, whole, claimed=()):
        """Up to `budget` cells of a level's set in marks (self.marks or self.fresh), grouped
        into runs along x or z, whichever makes fewer writes (a moved strip makes a line of
        parents, not a scatter). The rest stay in the set for another job. A cell out of the
        window is not written — its texel means somewhere else — but if a block changed under
        it the level above still inherits it. `claimed` cells are already being written by this
        job (all of the window when `whole`): they drop out of the set. So do the fresh cells
        whose finer cells are not all there: they stay what they are."""
        cells = marks[level]
        if self.origins[level] is None or not cells:
            marks[level] = set()
            return []
        n = self.size
        ox, oz = self.origins[level]
        inside = {(x, z) for x, z in cells if ox <= x < ox + n and oz <= z < oz + n}
        if marks is self.marks and level + 1 < self.n_levels:
            marks[level + 1].update((x >> 1, z >> 1) for x, z in cells - inside)
        inside = set() if whole else inside - claimed
        if inside and marks is self.fresh:
            cx, cz = (np.fromiter((c[i] for c in inside), np.int64, len(inside)) for i in (0, 1))
            known = self._children_known(level, cx, cz)
            inside = set(zip(cx[known].tolist(), cz[known].tolist()))
        if not inside or budget <= 0:
            marks[level] = inside
            return []
        # Group the cells into runs, along x or along z: whichever orientation needs fewer
        # writes (a moved strip makes a line of parents, not a scatter of single cells)
        xs_, zs_ = (np.fromiter((c[i] for c in inside), np.int64, len(inside)) for i in (0, 1))
        x0, z0 = xs_.min(), zs_.min()
        grid = np.zeros((int(zs_.max() - z0) + 1, int(xs_.max() - x0) + 1), bool)
        grid[zs_ - z0, xs_ - x0] = True

        def runs(grid, across):
            """Contiguous runs of True in a boolean grid: for across, rows of (xs, [z])."""
            g = grid if across else grid.T
            out = []
            for r, row in enumerate(g):
                starts = np.nonzero(np.diff(row.astype(np.int8), prepend=0) == 1)[0]
                ends = np.nonzero(np.diff(row.astype(np.int8), append=0) == -1)[0]
                for a, b in zip(starts, ends):
                    vs = np.arange(a, b + 1) + (x0 if across else z0)  # b is the last True, included
                    key = np.array([r + (z0 if across else x0)])
                    # Split where the texel address wraps around the grid
                    while len(vs) and vs[-1] % n < len(vs) - 1:
                        w = int(len(vs) - 1 - vs[-1] % n)
                        out.append((vs[:w], key) if across else (key, vs[:w]))
                        vs = vs[w:]
                    if len(vs):
                        out.append((vs, key) if across else (key, vs))
            return out

        writes = min((runs(grid, True), runs(grid, False)), key=len)
        # The cells that need it first are the ones about to be drawn: close to the finer
        # level's edge, where this level takes over cell by cell
        if level > 0 and sum(len(w[0]) * len(w[1]) for w in writes) > budget \
                and self.origins[level - 1] is not None:
            fx, fz = self.origins[level - 1]

            def distance(w):
                xs, zs = w
                dx = min(min(2 * x - fx, fx + n - 2 - 2 * x) for x in xs)
                dz = min(min(2 * z - fz, fz + n - 2 - 2 * z) for z in zs)
                return min(dx, dz)
            writes.sort(key=distance)
        taken, taken_n = [], 0
        for w in writes:
            if taken_n and taken_n + len(w[0]) * len(w[1]) > budget:
                break
            taken.append(w)
            taken_n += len(w[0]) * len(w[1])
        covered = {(int(x), int(z)) for xs, zs in taken for x in xs for z in zs}
        marks[level] = inside - covered
        return taken

    # --- Jobs --------------------------------------------------------------------------------------

    def job(self, batch, origins, edits=()):
        """Do the writes of a batch [(level, grid xs, grid zs)], which move the levels' grids to
        `origins`, and make again some of the cells marked for it (`edits`: the finest cells
        where the player changed a block). Level by level, finest first, so the cascade sees
        fresh records: a level's writes mark the cells they touch in the level above, written
        in its turn. Yields (level, runs, rgba, data, wet) for each level written: its writes
        (xs, zs), and the texels of all of them, one run after the other."""
        self.origins = list(origins)
        self.marks[0].update(edits)
        by_level = [[] for _ in range(self.n_levels)]
        whole = [False] * self.n_levels
        for level, xs, zs in batch:
            by_level[level].append((xs, zs))
            if len(xs) * len(zs) >= self.size * self.size:
                whole[level] = True
                self.marks[level], self.fresh[level] = set(), set()  # a new grid: the marks meant other places
        budgets = {id(self.fresh): LOD_FRESH_PER_JOB, id(self.marks): LOD_DIRTY_PER_JOB}
        for level in range(self.n_levels):
            if not self.alive():
                raise Cancelled
            runs, again, claimed = list(by_level[level]), {}, None
            for marks in (self.marks, self.fresh):  # (first the cells a block changed under)
                again[id(marks)] = []
                if not marks[level]:
                    continue
                if claimed is None:
                    claimed = set() if whole[level] else {(int(x), int(z)) for xs, zs in runs for x in xs for z in zs}
                took = self._dirty_runs(marks, level, budgets[id(marks)], whole[level], claimed)
                budgets[id(marks)] -= sum(len(w[0]) * len(w[1]) for w in took)
                claimed |= {(int(x), int(z)) for xs, zs in took for x in xs for z in zs}
                again[id(marks)] = took
            strong = again[id(self.marks)]
            runs += again[id(self.fresh)] + strong
            if runs:
                yield (level, runs) + self._sample_runs(level, runs, len(strong))
        if whole[0]:
            # A block changed while a whole level was sampled (by several processes): its cell
            # is sampled once more here, next job, in case one of them didn't have the change yet
            self.marks[0].update(edits)

    def pending(self):
        """How many cells are still marked to be made again."""
        return sum(len(m) for m in self.marks) + sum(len(m) for m in self.fresh)


# --- The sampler's process -----------------------------------------------------------------------

def _worker(tasks, results, current, work, done):
    """Main loop of the sampler's process. Messages:
    ("config", number, seed, place on Earth or None, edited sections, spacing, size, levels, block colors)
                                                            a new sampler
    ("set", x, y, z, block)                                 a block the player changed
    ("job", number, batch, origins, edits)                  see Sampler.job
    Answers: ("level", number, level, origin, runs, rgba, data, wet) for each level a job wrote,
    then ("done", number, cells still to sample again). `current` holds the number of the
    configuration that counts: the work of any other is dropped. work, done: the queues where
    the sampler shares its big jobs with the terrain builders."""
    sampler = number = None
    parent = multiprocessing.parent_process()
    while True:
        try:
            msg = tasks.get(timeout=1.0)
        except queue.Empty:
            if parent is not None and not parent.is_alive():
                return  # the game is gone
            continue
        try:
            if msg[0] == "config":
                if msg[1] != current.value:
                    continue  # already replaced by another one
                _, number, seed, earth, edited, spacing, size, levels, colors = msg
                if sampler is not None:
                    sampler.close()
                world = World(seed, earth)
                for key, blocks in edited:
                    world.sections[key] = blocks
                    world.edited.add(key)
                    world.edited_columns.setdefault((key[0], key[2]), set()).add(key[1])
                sampler = Sampler(world, spacing, size, levels, colors,
                                  alive=lambda mine=number: current.value == mine,
                                  shared=(work, done), number=number)
            elif msg[0] == "set":
                if sampler is not None:
                    sampler.world.set(*msg[1:])
            elif msg[0] == "job" and sampler is not None and msg[1] == number == current.value:
                _, _, batch, origins, edits = msg
                try:
                    for level, runs, rgba, data, wet in sampler.job(batch, origins, edits):
                        results.put(("level", number, level, origins[level], runs, rgba, data, wet))
                    results.put(("done", number, sampler.pending()))
                except Cancelled:
                    pass
        except Exception:  # noqa: BLE001 - reported by the game
            results.put(("error", traceback.format_exc()))


class SamplerProcess:
    """The game's side of the sampler's process."""

    def __init__(self):
        ctx = multiprocessing.get_context("spawn")
        self.tasks, self.results = ctx.Queue(), ctx.Queue()
        self.current = ctx.Value("i", 0)
        self.number = 0  # counts the configurations: answers to an older one are dropped
        # Where the sampler leaves chunks of its big jobs, for the terrain builders with nothing
        # to build (they get these through builder.Builders), and where they answer
        work, done = ctx.Queue(), ctx.Queue()
        self.shared = (work, done, self.current)
        ctx.Process(target=_worker, args=(self.tasks, self.results, self.current, work, done), daemon=True,
                    name="distant terrain sampler").start()

    def configure(self, world, spacing, size, levels, block_colors):
        """Start over: another world (with the sections the player changed in it) or another grid."""
        self.number += 1
        self.current.value = self.number
        edited = [(k, world.sections[k]) for k in world.edited]
        edited = [(k, np.full((CHUNK,) * 3, s, np.uint8) if isinstance(s, int) else s) for k, s in edited]
        self.tasks.put(("config", self.number, world.seed, world.earth, edited, spacing, size, levels, block_colors))

    def block_changed(self, x, y, z, block):
        self.tasks.put(("set", x, y, z, block))

    def request(self, batch, origins, edits):
        self.tasks.put(("job", self.number, batch, origins, edits))

    def finished(self):
        """The answers ready so far, current configuration only."""
        out = []
        while True:
            try:
                msg = self.results.get_nowait()
            except queue.Empty:
                return out
            if msg[0] == "error":
                raise RuntimeError("the distant terrain's sampler failed:\n" + msg[1])
            if msg[1] == self.number:
                out.append(msg)
