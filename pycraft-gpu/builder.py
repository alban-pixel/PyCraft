"""Terrain builders: worker processes that generate the world and build the block meshes.

Generating and meshing terrain takes far longer than a frame. Done by the game itself, it would
make it stutter, and a Python thread wouldn't help much: only one thread runs Python code at a
time. So separate processes do it, in parallel, each with its own copy of the world. The game sends
them the columns it wants (nearest first) and every block the player changes; they send back the
vertices of each column's sections. The game keeps its own world for walking, aiming and editing.
"""
import multiprocessing
import queue
import traceback

import numpy as np

from blocks import ACACIA_LEAVES, BLOCK_TILES, CUTOUT, GRASS, JUNGLE_LEAVES, LEAVES, NUM_BLOCKS, OPAQUE, SELF_CULL, WATER
from terrain import CHUNK
from world import World

WATER_SURFACE = 0.875  # water blocks are a bit lower than a full block

# For each face direction (+x, -x, +y, -y, +z, -z): neighbor offset and 4 corners
FACES = [
    ((1, 0, 0), [(1, 1, 0), (1, 1, 1), (1, 0, 1), (1, 0, 0)]),
    ((-1, 0, 0), [(0, 1, 1), (0, 1, 0), (0, 0, 0), (0, 0, 1)]),
    ((0, 1, 0), [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)]),
    ((0, -1, 0), [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)]),
    ((0, 0, 1), [(1, 1, 1), (0, 1, 1), (0, 0, 1), (1, 0, 1)]),
    ((0, 0, -1), [(0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 0)]),
]
FACE_CORNERS = [np.array(corners, dtype=np.float32) for _, corners in FACES]
TOP_CORNERS = [np.array(corners)[:, 1] == 1 for _, corners in FACES]

# One vertex: position relative to its column's corner; atlas tile, face corner (0-3), face
# direction (0-5) and kind; biome color
VERTEX = np.dtype([("pos", "<f4", 3), ("info", "u1", 4), ("tint", "u1", 4)])
KIND = np.where(np.arange(NUM_BLOCKS) == WATER, 2, np.where(CUTOUT, 1, 0)).astype(np.uint8)
TINT = np.zeros(NUM_BLOCKS, np.uint8)  # 1 grass, 2 leaves, 3 water: which biome color a block takes
TINT[GRASS] = 1
TINT[[LEAVES, JUNGLE_LEAVES, ACACIA_LEAVES]] = 2
TINT[WATER] = 3

WORKERS = 3
IN_FLIGHT = 4  # columns asked of each worker at a time: enough to keep it busy, few enough to follow the player


def _neighbor_layer(s, axis, index):
    """One layer of a section next door (the whole section can be a single block id)."""
    if isinstance(s, int):
        return s
    return np.take(s, index, axis=axis)


def mesh_section(world, col, cx, cy, cz):
    """Vertices of every visible face in a section (positions relative to the column's corner),
    or None when nothing in it can be seen."""
    s = world.section(cx, cy, cz)
    if isinstance(s, int) and s == 0:
        return None
    around = [world.section(cx + 1, cy, cz), world.section(cx - 1, cy, cz), world.section(cx, cy + 1, cz),
              world.section(cx, cy - 1, cz), world.section(cx, cy, cz + 1), world.section(cx, cy, cz - 1)]
    if isinstance(s, int) and OPAQUE[s] and all(isinstance(n, int) and OPAQUE[n] for n in around):
        return None  # solid rock all around: no face can show
    padded = np.zeros((CHUNK + 2,) * 3, dtype=np.uint8)
    padded[1:-1, 1:-1, 1:-1] = s
    padded[-1, 1:-1, 1:-1] = _neighbor_layer(around[0], 0, 0)
    padded[0, 1:-1, 1:-1] = _neighbor_layer(around[1], 0, CHUNK - 1)
    padded[1:-1, -1, 1:-1] = _neighbor_layer(around[2], 1, 0)
    padded[1:-1, 0, 1:-1] = _neighbor_layer(around[3], 1, CHUNK - 1)
    padded[1:-1, 1:-1, -1] = _neighbor_layer(around[4], 2, 0)
    padded[1:-1, 1:-1, 0] = _neighbor_layer(around[5], 2, CHUNK - 1)
    core = padded[1:-1, 1:-1, 1:-1]
    water_above = padded[1:-1, 2:, 1:-1] == WATER
    tints = [None, col.grass, col.foliage, col.water_tint]
    parts = []
    for face, ((dx, dy, dz), _) in enumerate(FACES):
        neighbor = padded[1 + dx:1 + dx + CHUNK, 1 + dy:1 + dy + CHUNK, 1 + dz:1 + dz + CHUNK]
        # A face shows when its neighbor doesn't hide it: not opaque, and not the same glass/water/leaves
        visible = (core != 0) & ~OPAQUE[neighbor] & ~((core == neighbor) & SELF_CULL[core])
        i, j, k = np.nonzero(visible)
        if i.size == 0:
            continue
        blocks = core[i, j, k]
        v = np.empty((i.size, 4), VERTEX)
        pos = np.stack([i, j + cy * CHUNK, k], axis=1).astype(np.float32)[:, None, :] + FACE_CORNERS[face][None]
        low = (blocks == WATER) & ~water_above[i, j, k]  # the top of the water is a bit lower
        pos[low[:, None] & TOP_CORNERS[face][None], 1] -= 1 - WATER_SURFACE
        v["pos"] = pos
        info = np.empty((i.size, 4, 4), np.uint8)
        info[..., 0] = BLOCK_TILES[blocks, face][:, None]
        info[..., 1] = np.arange(4)
        info[..., 2] = face
        info[..., 3] = KIND[blocks][:, None]
        v["info"] = info
        tint = np.full((i.size, 4), 255, np.uint8)
        which = TINT[blocks]
        for t in (1, 2, 3):
            sel = which == t
            if sel.any():
                tint[sel, :3] = tints[t][i[sel], k[sel]]
        v["tint"] = tint[:, None, :]
        parts.append(v.reshape(-1))
    return np.concatenate(parts) if parts else None


def wanted_sections(world, cx, cz):
    """Sections of a column that can have visible faces: from its lowest ground (neighbors
    included) up to its highest block, trees next door included, plus any the player changed."""
    col = world.column(cx, cz)
    tree_top = max(world.column(cx + dx, cz + dz).tree_top for dx in (-1, 0, 1) for dz in (-1, 0, 1))
    top = max(col.highest, tree_top)
    wanted = set(range(max(col.lowest - 1, 0) // CHUNK, top // CHUNK + 1))
    return wanted | world.edited_columns.get((cx, cz), set())


# --- Worker processes ----------------------------------------------------------------------------

def _worker(tasks, results):
    """Main loop of a worker process. Messages:
    ("world", generation, seed, edited sections) start over with another world
    ("set", x, y, z, block)                      a block the player changed
    ("columns", generation, [column])            send these columns back (for the game's own world)
    ("build", generation, (cx, cy, cz) of the camera, [(column, version, sections done, caves)])
    """
    world = generation = None
    forget_center = None
    parent = multiprocessing.parent_process()
    while True:
        try:
            msg = tasks.get(timeout=1.0)
        except queue.Empty:
            if parent is not None and not parent.is_alive():
                return  # the game is gone
            continue
        try:
            if msg[0] == "world":
                _, generation, seed, edited = msg
                world, forget_center = World(seed), None
                for key, blocks in edited:
                    world.sections[key] = blocks
                    world.edited.add(key)
                    world.edited_columns.setdefault((key[0], key[2]), set()).add(key[1])
            elif msg[0] == "set":
                world.set(*msg[1:])
            elif msg[0] == "columns" and msg[1] == generation:
                world.load_columns(msg[2])
                results.put(("columns", generation, [world.column(*key) for key in msg[2]]))
            elif msg[0] == "build" and msg[1] == generation:
                _, _, (pcx, pcy, pcz), jobs = msg
                if forget_center is None or max(abs(forget_center[0] - pcx), abs(forget_center[1] - pcz)) > 4:
                    world.forget(pcx, pcz, 24)
                    forget_center = (pcx, pcz)
                # The columns these jobs need, generated together: much faster than one by one
                world.load_columns([(cx + dx, cz + dz) for (cx, cz), _, _, _ in jobs
                                    for dx in range(-2, 3) for dz in range(-2, 3)])
                for (cx, cz), version, done, caves in jobs:
                    wanted = wanted_sections(world, cx, cz) | caves
                    col = world.column(cx, cz)
                    parts = {cy: mesh_section(world, col, cx, cy, cz) for cy in wanted - done}
                    results.put(("built", generation, (cx, cz), version, parts, done | wanted))
        except Exception:  # noqa: BLE001 - reported by the game
            results.put(("error", traceback.format_exc()))


class Builders:
    """The game's side of the worker processes."""

    def __init__(self, count=WORKERS):
        ctx = multiprocessing.get_context("spawn")
        self.results = ctx.Queue()
        self.tasks = [ctx.Queue() for _ in range(count)]
        self.in_flight = [set() for _ in range(count)]  # columns each worker is building
        self.generation = 0
        for tasks in self.tasks:
            ctx.Process(target=_worker, args=(tasks, self.results), daemon=True, name="terrain builder").start()

    def set_world(self, world):
        """Start building another world (with the sections the player changed in it)."""
        self.generation += 1
        edited = [(k, world.sections[k]) for k in world.edited]
        edited = [(k, np.full((CHUNK,) * 3, s, np.uint8) if isinstance(s, int) else s) for k, s in edited]
        for tasks, flying in zip(self.tasks, self.in_flight):
            tasks.put(("world", self.generation, world.seed, edited))
            flying.clear()

    def block_changed(self, x, y, z, block):
        for tasks in self.tasks:
            tasks.put(("set", x, y, z, block))

    def busy(self, key):
        return any(key in flying for flying in self.in_flight)

    def request_columns(self, keys):
        """Ask for columns (terrain.Column objects) for the game's own world."""
        self.tasks[0].put(("columns", self.generation, keys))

    def request(self, camera_chunk, jobs):
        """Hand out jobs (column, version, sections done, caves) to the workers with room."""
        for tasks, flying in zip(self.tasks, self.in_flight):
            room = IN_FLIGHT - len(flying)
            if room <= 0 or not jobs:
                continue
            mine, jobs = jobs[:room], jobs[room:]
            flying.update(job[0] for job in mine)
            tasks.put(("build", self.generation, camera_chunk, mine))

    def finished(self):
        """Results ready so far, current world only: a list of meshes (column, version,
        {cy: vertices}, sections done) and a list of terrain.Column objects."""
        out, columns = [], []
        while True:
            try:
                msg = self.results.get_nowait()
            except queue.Empty:
                return out, columns
            if msg[0] == "error":
                raise RuntimeError("a terrain builder process failed:\n" + msg[1])
            if msg[0] == "columns":
                if msg[1] == self.generation:
                    columns += msg[2]
                continue
            _, generation, key, version, parts, done = msg
            for flying in self.in_flight:
                flying.discard(key)
            if generation == self.generation:
                out.append((key, version, parts, done))
