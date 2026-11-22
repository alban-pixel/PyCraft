"""The blocks near the camera: one mesh per 16x16 column of the world, built by the worker
processes (builder.py), packed for the card on a few threads, uploaded nearest first, and drawn."""

import concurrent.futures
import functools
import math
import time

import moderngl
import numpy as np

from pycraft.builder import IN_FLIGHT, WORKERS, Builders, mesh_section
from pycraft.render.constants import READY_SIZE
from pycraft.render.gl import boxes_visible, frustum_planes
from pycraft.terrain import CHUNK, WORLD_HEIGHT


# Triangles of a face, split along one diagonal or the other: along the brighter corners, so
# ambient occlusion shades the face evenly
FACE_TRIANGLES = np.array([0, 1, 2, 0, 2, 3], np.uint32)
FLIPPED_TRIANGLES = np.array([1, 2, 3, 1, 3, 0], np.uint32)
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
def affected_sections(positions):
    """The sections to mesh again after these blocks changed: each block's section, and the
    sections next to it when it is on their border (diagonal ones too: the shading of their
    corners depends on it)."""
    todo = set()
    for x, y, z in positions:
        steps = [[0] + ([-1] if v % CHUNK == 0 else []) + ([1] if v % CHUNK == CHUNK - 1 else []) for v in (x, y, z)]
        cx, cy, cz = x >> 4, y >> 4, z >> 4
        todo |= {(cx + a, cy + b, cz + c) for a in steps[0] for b in steps[1] for c in steps[2]}
    return todo
def prepare_faces(parts):
    """The bytes a column mesh is made of, from its sections' vertices: the water faces last,
    and one index buffer for all of them. Pure number crunching — runs on a worker thread."""
    faces = np.concatenate(parts).reshape(-1, 4)
    water = faces["info"][:, 0, 3] == 2
    faces = faces[np.argsort(water, kind="stable")]  # the water faces last: drawn after the rest
    water_count = int(water.sum()) * 6
    solid = len(faces) * 6 - water_count
    ao = faces["tint"][:, :, 3].astype(np.int32)
    flip = (ao[:, 0] + ao[:, 2] < ao[:, 1] + ao[:, 3])[:, None]
    indices = (np.arange(len(faces), dtype=np.uint32)[:, None] * 4
               + np.where(flip, FLIPPED_TRIANGLES, FACE_TRIANGLES))
    ys = faces["pos"][..., 1]
    return faces.tobytes(), indices.astype(np.uint32).tobytes(), water_count, solid, \
        (float(ys.min()), float(ys.max()))
class Chunks:
    """Block meshes of the columns around the camera.

    Worker processes (see builder.py) build them, nearest first; this uploads them to the graphics
    card and draws them. Block changes are rebuilt right away here. Each column counts its changes
    ("version"): a mesh a worker built from older blocks is thrown away and asked for again.
    Packing a mesh for the card is done on a pool of threads (numpy frees the GIL for it), so the
    frames stay smooth while whole areas arrive."""

    def __init__(self, ctx, program, world, shared=None):
        """shared: work the builders can take when they have nothing to build (see builder.py)."""
        self.ctx, self.program = ctx, program
        self.meshes = {}  # (cx, cz) -> ColumnMesh
        self.radius = 8
        self.version = 0  # counts the changes to the meshes (the shadow map is drawn again)
        self.in_view = []  # (mesh, (x, y, z) of its corner relative to the camera) seen in the last frame
        self.builders = Builders(shared=shared)
        self.pool = concurrent.futures.ThreadPoolExecutor(2, thread_name_prefix="mesh prep")
        self.preparing = {}  # (cx, cz) -> (version, future of prepare_faces)
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
        self.preparing = {}

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
        # (a mesh being packed goes with its column: flying diagonally, a column at the edge can
        # be far one frame and near again the next, and its packed faces would land on no mesh)
        for key in [k for k in self.preparing if is_far(k)]:
            del self.preparing[key]
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
            # Packing is done on a worker thread; the card's buffers are made when it lands
            packed = [p for p in mesh.parts.values() if p is not None]
            if packed:
                self.preparing[key] = (version, self.pool.submit(prepare_faces, packed))
            else:
                self.upload(key, mesh, None)
        # Upload the meshes whose packing finished (the card's calls stay on this thread)
        for key in [k for k, (v, f) in self.preparing.items() if f.done()]:
            if time.perf_counter() >= deadline:
                break
            version, future = self.preparing.pop(key)
            if key not in self.meshes or version != self.versions.get(key, 0):
                self.built.pop(key, None)  # built from blocks changed since: asked for again
                continue
            self.upload(key, self.meshes[key], future.result())

        # The game's own world needs the columns around the player (walking, aiming): ask a worker
        # for them ahead of time, so the game doesn't have to generate them itself
        around = [(pcx + dx, pcz + dz) for dx in range(-3, 4) for dz in range(-3, 4)]
        missing = [k for k in around if k not in self.world.columns and k not in self.asked_columns
                   and self.world.ready(*k)]
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
            if key in self.pending or self.builders.busy(key) or not self.world.ready(*key):
                continue
            jobs.append((key, self.versions.get(key, 0), done or set(), caves if near else set()))
            if len(jobs) >= WORKERS * IN_FLIGHT:
                break
        if jobs:
            self.builders.request((pcx, pcy, pcz), jobs)

    def upload(self, key, mesh, prepared=None):
        """Make the card buffers of a mesh, from what prepare_faces produced (done on the spot
        when not given, as for a block the player changed)."""
        if prepared is None:
            parts = [p for p in mesh.parts.values() if p is not None]
            prepared = prepare_faces(parts) if parts else None
        mesh.release()
        self.version += 1
        if prepared is not None:
            vbo, ibo, mesh.water, mesh.solid, mesh.y_range = prepared
            mesh.vbo = self.ctx.buffer(vbo)
            mesh.ibo = self.ctx.buffer(ibo)
            mesh.vao = self.ctx.vertex_array(self.program, [(mesh.vbo, "3f 4u1 4f1 4u1", "in_pos", "in_info", "in_tint", "in_uv")],
                                             index_buffer=mesh.ibo, index_element_size=4)
        self.ready[key[1] % READY_SIZE, key[0] % READY_SIZE] = 255
        self.ready_changed = True

    def block_changed(self, x, y, z):
        """Rebuild the sections touching block (x, y, z) right away, and tell the workers."""
        self.blocks_changed([(x, y, z)])

    def blocks_changed(self, positions):
        """Rebuild the sections touching these blocks right away, each section once (a TNT blast
        or a line of dust changes many blocks of the same few sections), and tell the workers."""
        for x, y, z in positions:
            self.builders.block_changed(x, y, z, self.world.get(x, y, z), self.world.get_state(x, y, z))
        todo = affected_sections(positions)
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
