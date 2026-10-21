import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

from main import MouseGrabber


def test_mouse_grabber_lifecycle():
    grabber = MouseGrabber()
    assert not grabber.captured

    # Capture
    grabber.capture(160, 90)
    assert grabber.captured

    # Delta when captured
    dx, dy = grabber.get_delta(165, 95, 160, 90)
    assert isinstance(dx, float)
    assert isinstance(dy, float)

    # Release
    grabber.release()
    assert not grabber.captured

    # Delta when released should be (0.0, 0.0)
    dx, dy = grabber.get_delta(165, 95, 160, 90)
    assert dx == 0.0
    assert dy == 0.0
