"""Shapes of the blocks that aren't full cubes (or are cubes turned by their state): boxes, in 16ths
of a block, described facing up and turned to the way the block's state says.

Each face of a box shows the part of its tile that matches where the face is in the block, as
Minecraft's block models do: a 2-pixel stick in the middle of a block shows the middle 2 columns of
its tile. A texture pack's lever or torch therefore fits its boxes."""
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from pycraft import blocks as B
from pycraft.blocks import (AIR, DOWN, EAST, FACING_VECTORS, LEVER, NORTH, OPAQUE, PISTON, PISTON_HEAD, REDSTONE_TORCH,
                            REDSTONE_WIRE, REPEATER, SOUTH, STICKY_PISTON, STONE_BUTTON, STONE_PRESSURE_PLATE, UP, WEST)

# Face order everywhere: +x, -x, +y, -y, +z, -z (builder.FACES); their corners, in the same order
# as the cubes' faces (the top ones first, so the texture stands upright)
FACE_NORMALS = np.array(FACING_VECTORS)[[2, 3, 0, 1, 4, 5]]  # +x, -x, +y, -y, +z, -z
_FACE_CORNERS = np.array([
    [(1, 1, 0), (1, 1, 1), (1, 0, 1), (1, 0, 0)],
    [(0, 1, 1), (0, 1, 0), (0, 0, 0), (0, 0, 1)],
    [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)],
    [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
    [(1, 1, 1), (0, 1, 1), (0, 0, 1), (1, 0, 1)],
    [(0, 1, 0), (1, 1, 0), (1, 0, 0), (0, 0, 0)],
], np.float64)
ALL_FACES = 0b111111
POWER = 15  # strongest redstone power

# Rotations taking "up" to each facing (FACING_VECTORS order), as 3x3 matrices on (x, y, z)
_TURN = {
    UP: np.eye(3, dtype=int),
    DOWN: np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]]),
    EAST: np.array([[0, 1, 0], [-1, 0, 0], [0, 0, 1]]),
    WEST: np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]]),
    SOUTH: np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]]),
    NORTH: np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]]),
}
# Turns about the vertical, taking north (-z) to each horizontal facing
_SPIN = {
    NORTH: np.eye(3, dtype=int),
    SOUTH: np.array([[-1, 0, 0], [0, 1, 0], [0, 0, -1]]),
    EAST: np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]]),
    WEST: np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]]),
}


@dataclass(frozen=True)
class Box:
    lo: tuple  # (x, y, z) in 16ths, facing up
    hi: tuple
    tiles: tuple  # one tile per face: +x, -x, +y, -y, +z, -z (facing up)
    faces: int = ALL_FACES  # bit i: face i is drawn
    shear: tuple = None  # (axis, by, amount): coordinate axis moves by amount x (coordinate by - lo[by])
    kind: int = None  # builder.KIND of its faces (None: the block's)
    tint: bool = False  # takes the redstone color (dust)


@dataclass
class Quad:
    corners: np.ndarray  # (4, 3) in blocks, within the block's cell
    uv: np.ndarray  # (4, 2) uint8, 16ths of the tile
    face: int  # which way it faces: 0-5 as builder.FACES
    tile: int
    kind: object  # None: the block's
    tint: bool
    boundary: bool  # lies on the side of the cell: hidden by an opaque neighbor there


def _six(t):
    return (t,) * 6


def _cube_tiles(side, top, bottom):
    return (side, side, top, bottom, side, side)


def _uv(corner, face):
    """Where a point (in blocks, facing up, before any turn) is on the tile of a face, in 16ths."""
    x, y, z = corner
    u, v = {0: (z, 1 - y), 1: (1 - z, 1 - y), 2: (x, z), 3: (x, z), 4: (1 - x, 1 - y), 5: (x, 1 - y)}[face]
    return np.clip(np.rint(np.array([u, v]) * 16), 0, 16)


def _box_quads(box, turn):
    out = []
    lo, hi = np.array(box.lo, float) / 16, np.array(box.hi, float) / 16
    for face in range(6):
        if not box.faces >> face & 1:
            continue
        corners = lo + _FACE_CORNERS[face] * (hi - lo)
        uv = np.array([_uv(c, face) for c in corners], np.uint8)
        if box.shear is not None:
            axis, by, amount = box.shear
            corners = corners.copy()
            corners[:, axis] += amount * (corners[:, by] - lo[by])
        turned = (corners - 0.5) @ turn.T + 0.5
        normal = turn @ FACE_NORMALS[face]
        out_face = int(np.flatnonzero((FACE_NORMALS == normal).all(axis=1))[0])
        axis = int(np.flatnonzero(normal)[0])
        side = 1.0 if normal[axis] > 0 else 0.0
        boundary = box.shear is None and bool(np.allclose(turned[:, axis], side))
        out.append(Quad(turned, uv, out_face, box.tiles[face], box.kind, box.tint, boundary))
    return out


def _facing(state):
    return state & 7 if (state & 7) < 6 else UP


def _wire_tint(power):
    """The color of redstone dust at a power (0-15), 0-255 RGB."""
    p = power / POWER
    return (int(255 * (0.3 + 0.7 * p)), int(255 * max(0.0, p * p * 0.7 - 0.5) + 10), 10)


WIRE_CONNECTS = {LEVER, STONE_BUTTON, STONE_PRESSURE_PLATE, REDSTONE_TORCH, REDSTONE_WIRE, B.REDSTONE_BLOCK}


def wire_links(around):
    """Which of the 4 sides (E, W, S, N) a dust connects to: dust there (level, a step up when
    nothing opaque is above, a step down when the side is open), or a redstone part, or a
    repeater facing along that side."""
    above_open = not OPAQUE[around(0, 1, 0)[0]]
    links = []
    for d in (EAST, WEST, SOUTH, NORTH):
        dx, _, dz = FACING_VECTORS[d]
        block, state = around(dx, 0, dz)
        linked = block in WIRE_CONNECTS
        if block == REPEATER and _facing(state) in (d, B.OPPOSITE[d]):
            linked = True
        if not linked and above_open and OPAQUE[block] and around(dx, 1, dz)[0] == REDSTONE_WIRE:
            linked = True
        if not linked and not OPAQUE[block] and around(dx, -1, dz)[0] == REDSTONE_WIRE:
            linked = True
        links.append(linked)
    return tuple(links)


@lru_cache(maxsize=4096)
def _quads_cached(block, state, links):
    boxes, turn = _model(block, state, links)
    quads = []
    for box in boxes:
        quads += _box_quads(box, turn)
    return quads


def model_quads(block, state, around):
    """The quads of a shaped block: around(dx, dy, dz) gives the (block, state) next to it (the
    dust looks at its neighbors to know where it goes)."""
    links = wire_links(around) if block == REDSTONE_WIRE else None
    return _quads_cached(block, state, links)


def _model(block, state, links):
    """(boxes facing up, rotation) of a block in a state."""
    facing = _facing(state)
    stone = B.T_STONE
    if block in (PISTON, STICKY_PISTON):
        top = B.T_STICKY_PISTON_TOP if block == STICKY_PISTON else B.T_PISTON_TOP
        if state & 8:  # extended: a short base, the rod going into the head's cell
            base = Box((0, 0, 0), (16, 12, 16), _cube_tiles(B.T_PISTON_SIDE, B.T_PISTON_INNER, B.T_PISTON_BOTTOM))
            rod = Box((6, 12, 6), (10, 16, 10), _six(B.T_PISTON_SIDE), faces=0b110011)
            return [base, rod], _TURN[facing]
        return [Box((0, 0, 0), (16, 16, 16), _cube_tiles(B.T_PISTON_SIDE, top, B.T_PISTON_BOTTOM))], _TURN[facing]
    if block == PISTON_HEAD:
        top = B.T_STICKY_PISTON_TOP if state & 8 else B.T_PISTON_TOP
        plate = Box((0, 12, 0), (16, 16, 16), _cube_tiles(B.T_PISTON_SIDE, top, top))
        rod = Box((6, 0, 6), (10, 12, 10), _six(B.T_PISTON_SIDE), faces=0b110011)
        return [plate, rod], _TURN[facing]
    if block == LEVER:
        on = bool(state & 8)
        # The stick tilts along x on the walls facing east or west, else along z (bit 4 turns
        # a lever on the floor or the ceiling the other way)
        along_x = facing in (EAST, WEST) or (facing in (UP, DOWN) and state & 16)
        base = Box((5, 0, 4), (11, 3, 12), _six(B.T_COBBLE)) if not along_x else \
            Box((4, 0, 5), (12, 3, 11), _six(B.T_COBBLE))
        tilt = 0.7 if on else -0.7
        stick = Box((7, 1, 7), (9, 11, 9), _six(B.T_LEVER), shear=(0 if along_x else 2, 1, tilt), kind=1)
        return [base, stick], _TURN[facing]
    if block == STONE_BUTTON:
        depth = 1 if state & 8 else 2
        return [Box((5, 0, 6), (11, depth, 10), _six(stone))], _TURN[facing]
    if block == STONE_PRESSURE_PLATE:
        return [Box((1, 0, 1), (15, 0.5 if state & 8 else 1, 15), _six(stone))], _TURN[UP]
    if block == REDSTONE_TORCH:
        lit = not state & 8
        tile = B.T_REDSTONE_TORCH_ON if lit else B.T_REDSTONE_TORCH_OFF
        kind = 5 if lit else 1
        if facing in (UP, DOWN):
            return [Box((7, 0, 7), (9, 10, 9), _six(tile), kind=kind)], _TURN[UP]
        # On a wall: leaning out of it, its foot against the wall (built facing north, then spun)
        stick = Box((7, 3, 13), (9, 13, 15), _six(tile), shear=(2, 1, -0.35), kind=kind)
        return [stick], _SPIN[facing]
    if block == REPEATER:
        out = facing if facing in _SPIN else NORTH
        powered = bool(state & 32)
        delay = (state >> 3) & 3
        top = B.T_REPEATER_ON if powered else B.T_REPEATER_OFF
        torch = B.T_REDSTONE_TORCH_ON if powered else B.T_REDSTONE_TORCH_OFF
        kind = 5 if powered else 1
        slab = Box((0, 0, 0), (16, 2, 16), _cube_tiles(B.T_SMOOTH_STONE, top, B.T_SMOOTH_STONE))
        front = Box((7, 2, 2), (9, 7, 4), _six(torch), kind=kind)
        z = 6 + 2 * delay
        back = Box((7, 2, z), (9, 7, z + 2), _six(torch), kind=kind)
        return [slab, front, back], _SPIN[out]
    if block == REDSTONE_WIRE:
        h = 0.25
        east, west, south, north = links or (False,) * 4
        if (east or west) and not (south or north):
            east = west = True  # a line goes across the whole block
        if (south or north) and not (east or west):
            south = north = True
        boxes = [Box((5, 0, 5), (11, h, 11), _six(B.T_REDSTONE_DUST), faces=0b000100, kind=1, tint=True)]
        if east:
            boxes.append(Box((11, 0, 5), (16, h, 11), _six(B.T_REDSTONE_DUST), faces=0b000100, kind=1, tint=True))
        if west:
            boxes.append(Box((0, 0, 5), (5, h, 11), _six(B.T_REDSTONE_DUST), faces=0b000100, kind=1, tint=True))
        if south:
            boxes.append(Box((5, 0, 11), (11, h, 16), _six(B.T_REDSTONE_DUST), faces=0b000100, kind=1, tint=True))
        if north:
            boxes.append(Box((5, 0, 0), (11, h, 5), _six(B.T_REDSTONE_DUST), faces=0b000100, kind=1, tint=True))
        return boxes, _TURN[UP]
    raise ValueError(f"block {block} has no shape")


def wire_tint(state):
    return _wire_tint(state & 15)


@lru_cache(maxsize=1024)
def selection_box(block, state):
    """(lo, hi) of what can be aimed at, in blocks within the cell: the whole cell for a cube."""
    if not B.SHAPED[block]:
        return (0.0, 0.0, 0.0), (1.0, 1.0, 1.0)
    if block == REDSTONE_WIRE:
        return (0.0, 0.0, 0.0), (1.0, 1 / 16, 1.0)
    quads = _quads_cached(block, state, None)
    corners = np.concatenate([q.corners for q in quads])
    lo, hi = corners.min(axis=0), corners.max(axis=0)
    hi = np.maximum(hi, lo + 1 / 16)  # never flat: a plate can still be aimed at
    return tuple(float(v) for v in np.clip(lo, 0, 1)), tuple(float(v) for v in np.clip(hi, 0, 1))


def nothing_around(dx, dy, dz):
    return AIR, 0
