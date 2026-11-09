"""Automatic render scale: the 3D view is drawn smaller when the frames take longer than the frame
rate allows, and back at full size when there is time to spare. The menus, the HUD and the
dithering always stay at the screen's own resolution."""
import math
import time

STEPS = (0.5, 0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0)  # share of the width and the height
MIN_LINES = 540  # never fewer lines than this (it would blur a lot, for little: part of the work doesn't shrink)
SMOOTHING = 0.15  # weight of each new frame in the running averages
SETTLE_FRAMES = 8  # frames measured after a change before the next one
DOWN_WAIT, UP_WAIT = 0.25, 1.5  # and seconds: slower to go back up, so it doesn't swing up and down
SLOW, ROOMY = 1.05, 0.85  # too slow above this share of a frame's time; room to grow below this one
GPU_BOUND = 0.35  # below this share of a frame's time, a smaller 3D view would hardly help
STALL, STARTUP_STALL = 3.0, 1.0  # frames slower than 3x the average (or 1 s, at first) aren't measured


class AutoScale:
    def __init__(self):
        self.lowest = 0  # the smallest step allowed at this resolution
        self.reset()

    def reset(self, height=None):
        """Start again from full size (a new resolution or frame rate). height: the screen's, in pixels."""
        if height is not None:
            self.lowest = next((i for i, s in enumerate(STEPS) if s * height >= MIN_LINES), len(STEPS) - 1)
        self.step = len(STEPS) - 1
        self.restart()

    def restart(self, now=None):
        self.work = None  # average seconds of work per frame (update and draw, not the wait for the next)
        self.gpu = None  # average seconds the graphics card spent on the frame
        self.frames = 0
        self.changed = time.perf_counter() if now is None else now

    @property
    def scale(self):
        return STEPS[self.step]

    def update(self, work, gpu, target, now=None):
        """Measure a frame: `work` seconds in all, `gpu` of them on the graphics card (None if it
        can't tell), for a frame rate of one frame every `target` seconds. Returns the scale to use."""
        now = time.perf_counter() if now is None else now
        # A stall (the first frame compiling the shaders, a save, a burst of world building) has
        # nothing to do with the size of the 3D view: left out, so it doesn't swamp the averages
        if work > (STARTUP_STALL if self.work is None else STALL * self.work):
            return self.scale
        a = SMOOTHING
        self.work = work if self.work is None else self.work + a * (work - self.work)
        if gpu is not None:
            self.gpu = gpu if self.gpu is None else self.gpu + a * (gpu - self.gpu)
        self.frames += 1
        if self.frames < SETTLE_FRAMES:
            return self.scale
        waited = now - self.changed
        # Unknown: count the whole frame as the graphics card's, the worst case
        gpu = min(self.gpu, self.work) if self.gpu is not None else self.work
        scale = self.scale
        if (self.work > SLOW * target and self.step > self.lowest and gpu > GPU_BOUND * self.work
                and waited > DOWN_WAIT):
            # The graphics card's time goes with the number of pixels, the scale squared: shrink
            # until the frame would fit (with a little margin), by one step at least
            spare = gpu - (self.work - 0.95 * target)
            wanted = scale * math.sqrt(max(spare, 0.0) / gpu)
            fitting = [i for i, s in enumerate(STEPS) if s <= wanted]
            self.step = max(min(fitting[-1] if fitting else 0, self.step - 1), self.lowest)
            self.restart(now)
        elif self.work < ROOMY * target and self.step < len(STEPS) - 1 and waited > UP_WAIT:
            bigger = STEPS[self.step + 1]
            if self.work + gpu * ((bigger / scale) ** 2 - 1) < 0.9 * target:  # would still fit
                self.step += 1
                self.restart(now)
        return self.scale
