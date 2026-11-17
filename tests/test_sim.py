from pycraft.blocks import AIR, DIRT, STONE
from pycraft.sim import MAX_UPDATES, TICK, Simulation
from pycraft.world import World

Y = 3000


def make():
    w = World(3)
    calls = []
    changed = []
    sim = Simulation(w, lambda x, y, z: changed.append((x, y, z)))
    sim.handlers[STONE] = lambda s, x, y, z, block, state: calls.append((x, y, z))
    return w, sim, calls, changed


def test_schedule_fires_after_delay():
    w, sim, calls, _ = make()
    w.set(0, Y, 0, STONE)
    sim.schedule((0, Y, 0), 3)
    sim.tick()
    sim.tick()
    assert calls == []
    sim.tick()
    assert calls == [(0, Y, 0)]


def test_set_block_notifies_neighbors():
    w, sim, calls, changed = make()
    w.set(1, Y, 0, STONE)
    w.set(0, Y + 1, 0, STONE)
    w.set(5, Y, 5, STONE)  # far away: not told
    assert sim.set_block(0, Y, 0, DIRT)
    assert changed == [(0, Y, 0)] and w.get(0, Y, 0) == DIRT
    sim.tick()
    assert sorted(calls) == [(0, Y + 1, 0), (1, Y, 0)]


def test_set_block_same_is_nothing():
    w, sim, calls, changed = make()
    w.set(0, Y, 0, STONE)
    assert not sim.set_block(0, Y, 0, STONE)
    assert changed == []


def test_update_cap():
    w, sim, calls, _ = make()
    for i in range(MAX_UPDATES + 100):
        w.set(i, Y, 0, STONE)
        sim.schedule((i, Y, 0), 1)
    assert sim.tick() == MAX_UPDATES
    assert sim.tick() == 100


def test_pending_roundtrip():
    w, sim, calls, _ = make()
    w.set(0, Y, 0, STONE)
    sim.schedule((0, Y, 0), 5)
    sim.tick()
    saved = sim.pending()
    w2 = World(3)
    w2.set(0, Y, 0, STONE)
    sim2 = Simulation(w2, lambda *a: None)
    got = []
    sim2.handlers[STONE] = lambda s, x, y, z, b, st: got.append((x, y, z))
    sim2.load_pending(saved)
    for _ in range(3):
        sim2.tick()
    assert got == []
    sim2.tick()
    assert got == [(0, Y, 0)]


def test_update_runs_ticks_by_time():
    w, sim, calls, _ = make()
    assert sim.update(TICK * 2.5) == 2
    assert sim.update(TICK * 0.6) == 1  # the leftover half tick counts
    assert sim.update(10.0) <= 10  # a long pause doesn't make the game catch up for seconds
    _ = AIR
