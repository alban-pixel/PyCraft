import math
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import blocks
from player import Player
from world import World


def test_player_eye_and_forward():
    p = Player(10.0, 5.0, 10.0)
    eye = p.eye()
    assert eye[0] == 10.0
    assert eye[1] > 5.0
    assert eye[2] == 10.0

    # Yaw 0, pitch 0 -> looking along +z
    p.yaw = 0.0
    p.pitch = 0.0
    fw = p.forward()
    assert math.isclose(fw[0], 0.0, abs_tol=1e-5)
    assert math.isclose(fw[1], 0.0, abs_tol=1e-5)
    assert math.isclose(fw[2], 1.0, abs_tol=1e-5)

    # Pitch 90 -> looking up +y
    p.pitch = 90.0
    fw = p.forward()
    assert math.isclose(fw[1], 1.0, abs_tol=1e-5)


def test_player_overlap():
    p = Player(10.0, 5.0, 10.0)
    assert p.overlaps(10, 5, 10)
    assert p.overlaps(10, 6, 10)
    assert not p.overlaps(15, 5, 10)


def test_player_collision_resolution():
    w = World(size=(16, 32, 16), seed=1, generate=False)
    # Put a solid block at (5, 5, 5)
    w.set(5, 5, 5, blocks.STONE)

    p = Player(5.5, 6.0, 5.5)
    # Move down towards solid block
    hit = p._move_axis(w, axis=1, distance=-1.5)
    assert hit is True
    # Player's feet should be resting on top of y=5, so y=6.0 + epsilon
    assert p.pos[1] >= 6.0
