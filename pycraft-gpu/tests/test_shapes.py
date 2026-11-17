import numpy as np

import blocks as B
from blocks import (AIR, DOWN, EAST, LEVER, NORTH, PISTON, PISTON_HEAD, REDSTONE_TORCH, REDSTONE_WIRE, REPEATER,
                    SHAPED, STONE, UP)
from builder import mesh_section
from shapes import model_quads, selection_box
from world import World

Y = 3000
NOTHING = lambda dx, dy, dz: (AIR, 0)  # noqa: E731


def test_shaped_flags():
    for b in (LEVER, REDSTONE_WIRE, REDSTONE_TORCH, REPEATER, PISTON, PISTON_HEAD, B.STONE_BUTTON,
              B.STONE_PRESSURE_PLATE):
        assert SHAPED[b]
    assert not SHAPED[STONE] and not B.SOLID[LEVER] and B.SOLID[PISTON_HEAD]


def test_lever_quads():
    quads = model_quads(LEVER, UP, NOTHING)
    assert len(quads) == 12  # base and stick, six faces each
    lo = np.min([q.corners for q in quads], axis=(0, 1))
    assert abs(lo[1]) < 1e-6  # on the floor


def test_rotation_down_is_upside_down():
    quads = model_quads(LEVER, DOWN, NOTHING)
    corners = np.concatenate([q.corners for q in quads])
    assert abs(corners[:, 1].max() - 1) < 1e-6 and corners[:, 1].min() > 0.2  # hangs from the ceiling


def test_wall_lever_on_east_face():
    corners = np.concatenate([q.corners for q in model_quads(LEVER, EAST, NOTHING)])
    assert abs(corners[:, 0].min()) < 1e-6  # stuck to the wall at x = 0, standing out toward +x


def test_auto_uv_matches_position():
    # The piston head's arm (x 6..10) seen from +z: u = 16 - 16 x, so 6..10
    quads = model_quads(PISTON_HEAD, UP, NOTHING)
    arm = [q for q in quads if q.face == 4 and q.corners[:, 0].max() < 0.7]
    assert arm and set(np.unique(arm[0].uv[:, 0])) == {6, 10}


def test_retracted_piston_is_a_turned_cube():
    quads = model_quads(PISTON, NORTH, NOTHING)
    assert len(quads) == 6
    front = [q for q in quads if q.face == 5][0]  # -z
    assert front.tile == B.T_PISTON_TOP
    assert all(q.boundary for q in quads)


def test_extended_piston_has_short_base():
    quads = model_quads(PISTON, UP | 8, NOTHING)
    ys = np.concatenate([q.corners[:, 1] for q in quads])
    assert abs(ys.max() - 1) < 1e-6 and any(abs(y - 0.75) < 1e-6 for y in ys)


def test_wire_connects_to_neighbors():
    alone = model_quads(REDSTONE_WIRE, 15, NOTHING)

    def east_wire(dx, dy, dz):
        return (REDSTONE_WIRE, 0) if (dx, dy, dz) == (1, 0, 0) else (AIR, 0)
    joined = model_quads(REDSTONE_WIRE, 15, east_wire)
    reach = max(q.corners[:, 0].max() for q in joined)
    assert abs(reach - 1) < 1e-6
    assert max(q.corners[:, 0].max() for q in alone) < 1
    assert all(q.tint for q in joined)


def test_selection_boxes():
    lo, hi = selection_box(REDSTONE_WIRE, 0)
    assert hi[1] <= 1 / 16 + 1e-6
    lo, hi = selection_box(STONE, 0)
    assert tuple(lo) == (0, 0, 0) and tuple(hi) == (1, 1, 1)


def test_mesh_shaped_block():
    w = World(5)
    w.set(5, Y, 7, LEVER, UP)
    w.set(5, Y - 1, 7, STONE)
    v = mesh_section(w, w.column(0, 0), 0, Y >> 4, 0)
    assert v is not None and len(v) % 4 == 0


def test_raycast_hits_wire_box_not_cell():
    w = World(5)
    w.set(5, Y, 7, STONE)
    w.set(5, Y + 1, 7, REDSTONE_WIRE, 0)
    # Level with the middle of the cell above the floor: passes over the wire
    hit = w.raycast((2.5, Y + 1.5, 7.5), (1, 0, 0), 6)
    assert hit is None
    # Down onto the wire: hits it
    hit = w.raycast((5.5, Y + 3, 7.5), (0, -1, 0), 6)
    assert hit[0] == (5, Y + 1, 7)


def test_shaped_ignored_by_edited_tops():
    w = World(5)
    col = w.column(0, 0)
    x, z = 3, 4
    top = int(col.height[x, z])
    w.set(x, top + 1, z, REDSTONE_WIRE, 0)
    tops = w.edited_tops(0, 0)
    assert tops["top_y"][x, z] == top


def test_every_facing_turns_up_the_right_way():
    from shapes import _TURN
    for f, v in enumerate(B.FACING_VECTORS):
        assert tuple(_TURN[f] @ (0, 1, 0)) == v
