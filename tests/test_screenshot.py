"""The screenshot's helpers: the jitter of its passes, its size on a small graphics card, its file
name and the PNG it is written to."""
import time

import numpy as np
import pytest

from pycraft.render.gl import jittered, perspective
from pycraft.screenshot import fit_size, halton_offsets, screenshot_path, write_png


def test_halton():
    expected = [(0.0, -1 / 6), (-0.25, 1 / 6), (0.25, -7 / 18), (-0.375, -1 / 18)]
    for got, want in zip(halton_offsets(4), expected):
        assert got == pytest.approx(want)
    offsets = halton_offsets(16)
    assert len(set(offsets)) == 16
    assert all(-0.5 <= v < 0.5 for point in offsets for v in point)


def test_jittered():
    p = perspective(70, 16 / 9, 0.05, 6000)
    before = p.copy()
    point = np.array([0.0, 0.0, -10.0, 1.0])

    def ndc(m):
        clip = m @ point
        return clip[:2] / clip[3]

    moved = ndc(jittered(p, 1, 0, 1920, 1080))
    assert moved[0] == pytest.approx(ndc(p)[0] + 2 / 1920, abs=1e-6)
    assert moved[1] == pytest.approx(ndc(p)[1], abs=1e-6)
    up = ndc(jittered(p, 0, 1, 1920, 1080))
    assert up[1] == pytest.approx(ndc(p)[1] + 2 / 1080, abs=1e-6)
    assert np.array_equal(jittered(p, 0, 0, 1920, 1080), p)
    assert np.array_equal(p, before)


def test_fit_size():
    assert fit_size((3840, 2160), 16384, (16384, 16384)) == (3840, 2160)
    assert fit_size((3840, 2160), 2048, (16384, 16384)) == (2048, 1152)
    assert fit_size((3840, 2160), 16384, (3000, 16384)) == (3000, 1686)


def test_png_round_trip(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    rgb = np.random.default_rng(3).integers(0, 256, (5, 7, 3), dtype=np.uint8)
    path = str(tmp_path / "a.png")
    write_png(path, rgb)
    with Image.open(path) as image:
        assert image.mode == "RGB" and image.size == (7, 5)
        assert np.array_equal(np.asarray(image), rgb)


def test_same_second(tmp_path):
    folder = tmp_path / "shots"
    when = time.strptime("2026-11-23 12:34:56", "%Y-%m-%d %H:%M:%S")
    first = screenshot_path(str(folder), when)
    assert first.endswith("2026-11-23_12.34.56.png") and folder.is_dir()
    open(first, "wb").close()
    second = screenshot_path(str(folder), when)
    assert second.endswith("2026-11-23_12.34.56_2.png")
