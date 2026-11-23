"""F2 in the game: the wait for the world to be built 60 km around, the capture, the file, and the
game going on as before whatever happens. No window, no graphics card, no sound."""
import os
import time

import numpy as np

from pycraft.app import App
from pycraft.controls import DEFAULTS
from pycraft.player import Player
from pycraft.render.constants import SCREENSHOT_REACH, SCREENSHOT_WAIT


class Renderer:
    """Records what the screenshot asks of the renderer."""

    def __init__(self):
        self.reaches, self.progress, self.fails = [], 0.0, None

    def set_reach(self, reach):
        self.reaches.append(reach)

    def reach_progress(self, cam):
        return self.progress

    def capture(self, eye, forward):
        if self.fails:
            raise self.fails
        return np.full((4, 6, 3), 90, np.uint8)


class Scaler:
    def __init__(self):
        self.resets = 0

    def reset(self, *args):
        self.resets += 1


class Game(App):
    """The App without its window: what the screenshot needs."""

    def __init__(self, folder):
        self.renderer, self.scaler, self.messages = Renderer(), Scaler(), []
        self.screenshot_dir = os.path.join(folder, "screenshots")
        self.player = Player(0.5, 100.0, 0.5)
        self.state, self.headless = "playing", True

    def set_state(self, state):
        self.state = state

    def notify(self, text):
        self.messages.append(text)

    def camera(self):
        return self.player.eye(), self.player.forward()


def files(game):
    folder = game.screenshot_dir
    return sorted(os.listdir(folder)) if os.path.isdir(folder) else []


def test_defaults_unique():
    assert DEFAULTS["screenshot"] == "F2"
    assert list(DEFAULTS.values()).count("F2") == 1


def test_waits_then_captures(tmp_path):
    game = Game(tmp_path)
    game.start_screenshot()
    assert game.state == "screenshot" and game.renderer.reaches == [SCREENSHOT_REACH]
    game.renderer.progress = 0.5
    game.update_screenshot(False)
    assert not game.screenshot_due
    game.renderer.progress = 1.0
    game.update_screenshot(False)
    assert game.screenshot_due
    game.take_screenshot()
    assert len(files(game)) == 1 and files(game)[0].endswith(".png")
    assert game.messages[-1].startswith("Screenshot saved: ")
    assert game.state == "playing" and game.renderer.reaches[-1] is None


def test_escape_cancels(tmp_path):
    game = Game(tmp_path)
    game.start_screenshot()
    game.update_screenshot(True)
    assert game.state == "playing" and game.renderer.reaches[-1] is None
    assert game.messages[-1] == "Screenshot cancelled" and files(game) == []


def test_timeout_captures_anyway(tmp_path):
    game = Game(tmp_path)
    game.start_screenshot()
    game.renderer.progress = 0.3
    game.screenshot_started = time.perf_counter() - SCREENSHOT_WAIT - 1
    game.update_screenshot(False)
    assert game.screenshot_due


def test_save_fails_cleanly(tmp_path):
    game = Game(tmp_path)
    open(game.screenshot_dir, "w").close()  # a file where the folder should be
    game.start_screenshot()
    game.take_screenshot()
    assert game.messages[-1].startswith("Screenshot failed")
    assert game.state == "playing" and game.renderer.reaches[-1] is None


def test_capture_resets_scaler(tmp_path):
    game = Game(tmp_path)
    game.start_screenshot()
    game.take_screenshot()
    assert game.scaler.resets == 1
    game.renderer.fails = OSError("out of memory")
    game.start_screenshot()
    game.take_screenshot()
    assert game.scaler.resets == 2 and game.messages[-1].startswith("Screenshot failed")


def test_only_while_playing(tmp_path):
    game = Game(tmp_path)
    game.state = "paused"
    game.start_screenshot()
    assert game.state == "paused" and game.renderer.reaches == []
