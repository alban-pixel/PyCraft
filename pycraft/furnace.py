"""Furnaces: what each one holds, and the fire and cooking that go on in it, one simulation tick at a time.

The contents live here, by position, not in the world's block state (a byte is too small for three stacks);
the block itself only shows whether the fire is lit (FURNACE or FURNACE_ON, facing the same way).
"""
from dataclasses import dataclass, field

import numpy as np

from pycraft import blocks as B
from pycraft import items as I
from pycraft import recipes as R
from pycraft.inventory import EMPTY

INPUT, FUEL, OUTPUT = 0, 1, 2
ALL_FURNACES = set(B.LIT_FURNACE) | set(B.UNLIT_FURNACE)


@dataclass
class FurnaceState:
    slots: list = field(default_factory=lambda: [EMPTY, EMPTY, EMPTY])  # input, fuel, output
    burn_left: float = 0  # ticks of fire left
    burn_total: float = 0  # ticks the current fuel gave, for the flame drawn on the screen
    cook: int = 0  # ticks toward COOK_TICKS

    def can_smelt(self):
        """True when the input has a smelting result and the output has room for one more of it."""
        item, count, _ = self.slots[INPUT]
        result = R.smelt_result(item) if count else None
        if result is None:
            return False
        out, n, _ = self.slots[OUTPUT]
        return out == 0 or (out == result and n < I.max_stack(result))


class Furnaces:
    def __init__(self):
        self.states = {}  # (x, y, z) -> FurnaceState

    def get(self, pos):
        return self.states.setdefault(tuple(pos), FurnaceState())

    def remove(self, pos):
        """Forget the furnace at pos (it was broken); returns what it held."""
        state = self.states.pop(tuple(pos), None)
        return [] if state is None else [s for s in state.slots if s != EMPTY]

    def tick(self, sim):
        world = sim.world
        for pos in list(self.states):
            block = world.get(*pos)
            if block not in ALL_FURNACES:
                del self.states[pos]  # broken or replaced (the game takes the contents out first)
                continue
            f = self.states[pos]
            smeltable = f.can_smelt()
            if f.burn_left <= 0 and smeltable:
                fuel, n, _ = f.slots[FUEL]
                value = R.fuel_value(fuel) if n else 0
                if value > 0:
                    f.slots[FUEL] = (fuel, n - 1, 0) if n > 1 else EMPTY
                    f.burn_total = f.burn_left = value * R.COOK_TICKS
            if f.burn_left > 0:
                f.burn_left -= 1
                if smeltable:
                    f.cook += 1
                    if f.cook >= R.COOK_TICKS:
                        f.cook = 0
                        self._smelt_one(f)
                else:
                    f.cook = 0
            else:
                f.burn_left, f.cook = 0, 0  # the fire is out: what was cooking cools down
            lit = f.burn_left > 0
            want = B.LIT_FURNACE.get(block, block) if lit else B.UNLIT_FURNACE.get(block, block)
            if want != block:
                sim.set_block(*pos, want, world.get_state(*pos))

    @staticmethod
    def _smelt_one(f):
        item, count, _ = f.slots[INPUT]
        result = R.smelt_result(item)
        f.slots[INPUT] = (item, count - 1, 0) if count > 1 else EMPTY
        out, n, _ = f.slots[OUTPUT]
        f.slots[OUTPUT] = (result, n + 1 if out else 1, 0)

    def to_array(self):
        """For the save: (n, 12) int64 rows of x, y, z, the 3 stacks as (item, count), burn left, burn total, cook.
        Damage isn't kept: a furnace never holds a tool for long (wooden tools burn whole)."""
        rows = [(*pos, *(v for it, n, _ in f.slots for v in (it, n)), int(f.burn_left), int(f.burn_total), f.cook)
                for pos, f in self.states.items()]
        return np.array(rows, np.int64).reshape(-1, 12)

    @classmethod
    def from_array(cls, arr):
        furnaces = cls()
        for row in np.asarray(arr, np.int64).reshape(-1, 12).tolist():
            slots = [(row[3 + 2 * i], row[4 + 2 * i], 0) if row[4 + 2 * i] > 0 and row[3 + 2 * i] else EMPTY
                     for i in range(3)]
            furnaces.states[tuple(row[:3])] = FurnaceState(slots, row[9], row[10], row[11])
        return furnaces
