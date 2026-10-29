"""Unit tests for the 20 Hz deterministic clock and temporal interpolator."""
import math
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from clock import GameClock, TICK_DURATION, TICKS_PER_DAY, interpolate_position


def test_clock_initialization():
    clock = GameClock(initial_tick=0)
    assert clock.world_tick == 0
    assert clock.accumulator == 0.0
    assert clock.sub_frame_alpha == 0.0
    assert clock.time_of_day == 0.0
    assert math.isclose(clock.solar_insolation, 1.0, rel_tol=1e-5)


def test_clock_advance_single_tick():
    clock = GameClock()
    ticks_run = []

    def callback(t):
        ticks_run.append(t)

    # Advance by 0.05s (exactly 1 tick at 20 Hz)
    processed = clock.advance(0.05, callback)
    assert processed == 1
    assert clock.world_tick == 1
    assert ticks_run == [0]
    assert math.isclose(clock.accumulator, 0.0, abs_tol=1e-7)
    assert math.isclose(clock.sub_frame_alpha, 0.0, abs_tol=1e-7)


def test_clock_advance_sub_frame():
    clock = GameClock()
    # Advance by 0.025s (half a tick: 0 ticks processed, alpha = 0.5)
    processed = clock.advance(0.025)
    assert processed == 0
    assert clock.world_tick == 0
    assert math.isclose(clock.sub_frame_alpha, 0.5, abs_tol=1e-5)

    # Advance by another 0.035s (total 0.06s: 1 tick processed, remaining 0.01s -> alpha = 0.2)
    processed = clock.advance(0.035)
    assert processed == 1
    assert clock.world_tick == 1
    assert math.isclose(clock.accumulator, 0.01, abs_tol=1e-5)
    assert math.isclose(clock.sub_frame_alpha, 0.2, abs_tol=1e-5)


def test_clock_catchup_limit():
    clock = GameClock()
    # If the game stalls for 2 seconds (40 potential ticks), limit to MAX_CATCHUP_TICKS (5)
    processed = clock.advance(2.0)
    assert processed == 5
    assert clock.world_tick == 5
    assert math.isclose(clock.accumulator, 0.0, abs_tol=1e-7)


def test_circadian_cycle():
    clock = GameClock(initial_tick=0)  # Noon (sun directly overhead)
    assert math.isclose(clock.solar_insolation, 1.0, rel_tol=1e-5)

    clock.world_tick = 6000  # Sunset (cos(pi/2) = 0)
    assert math.isclose(clock.solar_insolation, 0.0, abs_tol=1e-5)

    clock.world_tick = 12000  # Midnight (cos(pi) = -1 -> clamped to 0)
    assert clock.solar_insolation == 0.0

    clock.world_tick = 18000  # Sunrise (cos(3pi/2) = 0)
    assert math.isclose(clock.solar_insolation, 0.0, abs_tol=1e-5)

    clock.world_tick = 24000  # Next noon
    assert clock.time_of_day == 0.0
    assert math.isclose(clock.solar_insolation, 1.0, rel_tol=1e-5)


def test_interpolate_position():
    p0 = (0.0, 10.0, 5.0)
    p1 = (10.0, 20.0, 15.0)

    # alpha = 0.0 -> p0
    res0 = interpolate_position(p0, p1, 0.0)
    assert res0 == p0

    # alpha = 1.0 -> p1
    res1 = interpolate_position(p0, p1, 1.0)
    assert res1 == p1

    # alpha = 0.5 -> midpoint
    res_half = interpolate_position(p0, p1, 0.5)
    assert res_half == (5.0, 15.0, 10.0)
