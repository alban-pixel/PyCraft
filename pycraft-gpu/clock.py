"""Deterministic 20 Hz game clock and temporal sub-frame interpolator.

Implements the fixed-step logic required by voxel simulation engines:
- Fixed tick duration: Delta t = 0.05 s (20 ticks/sec).
- Time accumulator with spiral-of-death catch-up clamp.
- Sub-frame interpolation factor alpha in [0.0, 1.0) for temporal lerp.
- Exact 24,000 tick circadian day/night cycle.
"""
import math
from typing import Callable, Optional

TICK_RATE = 20  # Ticks per second
TICK_DURATION = 1.0 / TICK_RATE  # 0.05 seconds = 50 ms
MAX_CATCHUP_TICKS = 5  # Maximum ticks processed per frame to prevent spiral of death
TICKS_PER_DAY = 24000  # Canonical Minecraft day duration (20 minutes)


class GameClock:
    """Fixed-step deterministic clock managing simulation ticks decoupled from render frames."""

    def __init__(self, initial_tick: int = 0):
        self.world_tick = int(initial_tick)
        self.accumulator = 0.0
        self.sub_frame_alpha = 0.0
        self.paused = False

    @property
    def time_of_day(self) -> float:
        """Fraction of the current day in [0.0, 1.0) based on 24,000 ticks."""
        return (self.world_tick % TICKS_PER_DAY) / float(TICKS_PER_DAY)

    @property
    def solar_insolation(self) -> float:
        """Circadian solar modulation I_sun(t) = max(0, cos(t * 2 * pi / 24000))."""
        angle = (self.world_tick % TICKS_PER_DAY) * (2.0 * math.pi / TICKS_PER_DAY)
        return max(0.0, math.cos(angle))

    def advance(self, dt: float, tick_callback: Optional[Callable[[int], None]] = None) -> int:
        """Advance the accumulator by dt seconds and execute fixed-step ticks.

        Args:
            dt: Real elapsed frame time in seconds.
            tick_callback: Optional callable(world_tick) executed on each tick.

        Returns:
            The number of ticks processed in this update.
        """
        if self.paused or dt <= 0:
            return 0

        self.accumulator += dt

        # Prevent spiral-of-death if frame time stalls
        if self.accumulator > TICK_DURATION * MAX_CATCHUP_TICKS:
            self.accumulator = TICK_DURATION * MAX_CATCHUP_TICKS

        ticks_processed = 0
        while self.accumulator >= TICK_DURATION:
            if tick_callback is not None:
                tick_callback(self.world_tick)
            self.world_tick += 1
            self.accumulator -= TICK_DURATION
            ticks_processed += 1

        self.sub_frame_alpha = max(0.0, min(1.0, self.accumulator / TICK_DURATION))
        return ticks_processed

    def step_single_tick(self, tick_callback: Optional[Callable[[int], None]] = None) -> None:
        """Deterministically advance exactly 1 tick (used in test suites and debugging)."""
        if tick_callback is not None:
            tick_callback(self.world_tick)
        self.world_tick += 1
        self.sub_frame_alpha = 0.0
        self.accumulator = 0.0

    def reset(self, tick: int = 0) -> None:
        """Reset the clock state."""
        self.world_tick = int(tick)
        self.accumulator = 0.0
        self.sub_frame_alpha = 0.0


def interpolate_position(p_prev, p_curr, alpha: float):
    """Sub-frame linear interpolation: P_render = (1 - alpha) * P_{t-1} + alpha * P_t."""
    return tuple((1.0 - alpha) * p0 + alpha * p1 for p0, p1 in zip(p_prev, p_curr))
