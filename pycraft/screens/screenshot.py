"""The screenshot (F2): the world is built 60 km around while the game waits, frozen, then drawn
at 4K with the best shaders and saved as a PNG; the game then goes on as before."""
import os
import sys
import time

import moderngl

from pycraft.render.constants import SCREENSHOT_REACH, SCREENSHOT_WAIT
from pycraft.screenshot import screenshot_path, write_png
from pycraft.settings import fit_text


class Screenshots:
    """The App's screenshot, in the "screenshot" state."""

    def start_screenshot(self):
        """From play only: see far, build the world out there, and wait for it."""
        if self.state != "playing":
            return
        self.renderer.set_reach(SCREENSHOT_REACH)
        self.screenshot_started = time.perf_counter()
        self.screenshot_due = False
        self.set_state("screenshot")

    def update_screenshot(self, cancel):
        """The world stands still while it is built; the picture is taken once it is all there (or
        after SCREENSHOT_WAIT seconds, with what is there: an Earth world without internet)."""
        if cancel:
            self.end_screenshot()
            self.notify("Screenshot cancelled")
            return
        waited = time.perf_counter() - self.screenshot_started
        if self.renderer.reach_progress(self.camera()[0]) >= 1 or waited > SCREENSHOT_WAIT:
            self.screenshot_due = True

    def draw_screenshot(self):
        if self.screenshot_due:
            self.take_screenshot()
            return
        done = self.renderer.reach_progress(self.camera()[0])
        self.draw_message_box(f"Preparing the screenshot... {done * 100:.0f}%  ESC: cancel", done)

    def take_screenshot(self):
        """Draw the picture and save it. Whatever happens, the game goes on as before."""
        try:
            eye, forward = self.camera()
            rgb = self.renderer.capture(eye, forward)
            path = screenshot_path(self.screenshot_dir, time.localtime())
            write_png(path, rgb)
            self.notify(f"Screenshot saved: {os.path.basename(path)}")
        except (OSError, moderngl.Error) as e:
            print(f"Screenshot failed: {e!r}", file=sys.stderr)
            self.notify(fit_text(f"Screenshot failed: {e}", 60, keep="start"))
        finally:
            self.end_screenshot()
            self.scaler.reset()  # (the frame of the capture was long: not a reason to draw smaller)

    def end_screenshot(self):
        self.renderer.set_reach(None)
        self.set_state("playing")
