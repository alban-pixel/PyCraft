"""The clock of the world's machines: 20 ticks a second, whatever the frame rate.

Nothing here runs everywhere: only blocks that were told something changed next to them, or that
asked to be woken up later, are looked at. A block reacts through its handler (see redstone.py),
and the blocks it changes tell their neighbors in turn. Each tick looks at MAX_UPDATES blocks at
most: a circuit that keeps itself busy slows down instead of freezing the game."""
import heapq
from collections import deque

import numpy as np

TICK = 1 / 20  # seconds
MAX_UPDATES = 4096  # blocks looked at in one tick, at most; the others wait for the next
MAX_TICKS_PER_UPDATE = 10  # after a long frame, the world catches up half a second at most
NEIGHBORS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))


class Simulation:
    def __init__(self, world, changed):
        """changed(x, y, z): a block was changed (the renderer redraws it)."""
        self.world, self.changed = world, changed
        self.now = 0
        self.scheduled = []  # heap of (tick, order, (x, y, z))
        self.order = 0
        self.queue = deque()  # blocks to look at, this tick or the next ones
        self.queued = set()
        self.handlers = {}  # block -> fn(sim, x, y, z, block, state)
        self.every_tick = []  # fn(sim): run once a tick (the pressure plates under the player)
        self.time = 0.0

    def schedule(self, pos, delay):
        """Look at the block at pos again in delay ticks (at least 1)."""
        heapq.heappush(self.scheduled, (self.now + max(1, int(delay)), self.order, tuple(pos)))
        self.order += 1

    def _queue(self, pos):
        if pos not in self.queued:
            self.queued.add(pos)
            self.queue.append(pos)

    def notify(self, pos):
        """Something changed at pos: look at it and at its 6 neighbors."""
        x, y, z = pos
        self._queue((x, y, z))
        for dx, dy, dz in NEIGHBORS:
            self._queue((x + dx, y + dy, z + dz))

    def set_block(self, x, y, z, block, state=0):
        """Change a block, redraw it and tell its neighbors. False if it was that already."""
        world = self.world
        if world.get(x, y, z) == block and world.get_state(x, y, z) == state:
            return False
        world.set(x, y, z, block, state)
        self.changed(x, y, z)
        self.notify((x, y, z))
        return True

    def tick(self):
        """One tick: the blocks due now, and those told of a change. Returns how many were looked at."""
        self.now += 1
        while self.scheduled and self.scheduled[0][0] <= self.now:
            self._queue(heapq.heappop(self.scheduled)[2])
        for fn in self.every_tick:
            fn(self)
        done = 0
        world, handlers = self.world, self.handlers
        while self.queue and done < MAX_UPDATES:
            pos = self.queue.popleft()
            self.queued.discard(pos)
            done += 1
            block = world.get(*pos)
            handler = handlers.get(block)
            if handler is not None:
                handler(self, pos[0], pos[1], pos[2], block, world.get_state(*pos))
        return done

    def update(self, dt):
        """Run the ticks that dt seconds hold (the rest carries over). Returns how many."""
        self.time += dt
        n = 0
        while self.time >= TICK and n < MAX_TICKS_PER_UPDATE:
            self.time -= TICK
            self.tick()
            n += 1
        if n == MAX_TICKS_PER_UPDATE:
            self.time = min(self.time, TICK)
        return n

    def pending(self):
        """What is waiting, for the save: (n, 4) int64 rows of (ticks from now, x, y, z)."""
        rows = [(t - self.now, *pos) for t, _, pos in self.scheduled] + [(0, *pos) for pos in self.queue]
        return np.array(rows, np.int64).reshape(-1, 4)

    def load_pending(self, rows):
        for delay, x, y, z in np.asarray(rows, np.int64).reshape(-1, 4).tolist():
            if delay <= 0:
                self._queue((x, y, z))
            else:
                self.schedule((x, y, z), delay)
