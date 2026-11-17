import numpy as np

from blocks import STONE
from builder import mesh_section
from world import World

Y = 3000  # high in the air: nothing else in the section


def mesh_one(block, state=0):
    w = World(99)
    w.set(5, Y, 7, block, state)
    return mesh_section(w, w.column(0, 0), 0, Y >> 4, 0)


def test_cube_uvs_are_tile_corners():
    v = mesh_one(STONE).reshape(-1, 4)
    assert len(v) == 6  # six faces
    uv = v["uv"][..., :2]
    assert set(np.unique(uv)) == {0, 16}
    # the corners in the order the faces list them: (0,0), (16,0), (16,16), (0,16)
    assert (uv == np.array([[0, 0], [16, 0], [16, 16], [0, 16]])).all()
