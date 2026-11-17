"""The player's 36 slots, and the clicks that move stacks between slots, a crafting grid and the cursor.

A stack is a tuple (item, count, damage); EMPTY is (0, 0, 0). Only tools carry damage, and they never stack.
The click helpers are pure: they take lists and return new ones, so the screens and the tests can use them on
any list of slots (the inventory, a crafting grid, a furnace) without an Inventory around it.
"""
import numpy as np

import items as I
import recipes as R

EMPTY = (0, 0, 0)
HOTBAR = range(0, 9)
MAIN = range(9, 36)


def _stack(item, count, damage=0):
    """A stack, or EMPTY when nothing is left in it (a count of 0 must never keep its item)."""
    return (item, count, damage) if count > 0 and item else EMPTY


def _can_merge(a, b):
    """True when stacks a and b hold the same stackable item (tools never merge, even with equal damage)."""
    return a[0] == b[0] and a[0] != 0 and I.max_stack(a[0]) > 1


class Inventory:
    """36 slots: 0 to 8 are the hotbar, 9 to 35 the main rows."""

    def __init__(self):
        self.slots = [EMPTY] * 36

    def add(self, item, count, damage=0):
        """Put count items in; returns how many didn't fit.

        Existing stacks of the item are topped up first (hotbar, then main), so picking something up never
        opens a new slot while an old one has room. Then empty slots are used, hotbar first.
        """
        if not item or count <= 0:
            return 0
        top = I.max_stack(item)
        if top > 1:
            for i, (it, n, _) in enumerate(self.slots):
                if it == item and n < top:
                    put = min(count, top - n)
                    self.slots[i] = (item, n + put, 0)
                    count -= put
                    if not count:
                        return 0
        for i, s in enumerate(self.slots):
            if s == EMPTY:
                put = min(count, top)
                self.slots[i] = (item, put, damage)
                count -= put
                if not count:
                    return 0
        return count

    def remove_from(self, i, n):
        item, count, damage = self.slots[i]
        self.slots[i] = _stack(item, count - n, damage)

    def damage_tool(self, i, amount=1):
        """Wear the tool in slot i; True when it broke, which empties the slot."""
        item, count, damage = self.slots[i]
        tool = I.TOOLS.get(item)
        if tool is None:
            return False
        damage += amount
        if damage >= tool.durability:
            self.slots[i] = EMPTY
            return True
        self.slots[i] = (item, count, damage)
        return False

    def to_array(self):
        return np.array(self.slots, dtype=np.int32).reshape(36, 3)

    @classmethod
    def from_array(cls, arr):
        inv = cls()
        rows = np.asarray(arr).reshape(-1, 3)[:36]
        inv.slots[:len(rows)] = [_stack(int(it), int(n), int(d)) for it, n, d in rows]
        return inv


def click(slots, cursor, i, button):
    """One click on slots[i] with the cursor holding `cursor`; returns (new slots, new cursor).

    Left: take the whole stack, put the whole cursor down, merge up to a full stack, or swap two different
    stacks. Right: take half (rounded up), or put one item down on an empty slot or a matching stack.
    """
    slots = list(slots)
    here = slots[i]
    if button == "left":
        if cursor == EMPTY:
            slots[i], cursor = EMPTY, here
        elif here == EMPTY:
            slots[i], cursor = cursor, EMPTY
        elif _can_merge(here, cursor):
            put = min(cursor[1], I.max_stack(here[0]) - here[1])
            slots[i] = (here[0], here[1] + put, 0)
            cursor = _stack(cursor[0], cursor[1] - put)
        else:
            slots[i], cursor = cursor, here
    else:
        if cursor == EMPTY:
            if here != EMPTY:
                take = (here[1] + 1) // 2
                cursor = (here[0], take, here[2])
                slots[i] = _stack(here[0], here[1] - take, here[2])
        elif here == EMPTY:
            slots[i] = (cursor[0], 1, cursor[2])
            cursor = _stack(cursor[0], cursor[1] - 1, cursor[2])
        elif _can_merge(here, cursor) and here[1] < I.max_stack(here[0]):
            slots[i] = (here[0], here[1] + 1, 0)
            cursor = _stack(cursor[0], cursor[1] - 1)
    return slots, cursor


def shift_click(slots, i, targets):
    """Move the stack at i into the target slots (in order): matching stacks first, then empty ones.

    What doesn't fit stays at i. Returns the new list.
    """
    slots = list(slots)
    item, count, damage = slots[i]
    if not item:
        return slots
    top = I.max_stack(item)
    if top > 1:
        for t in targets:
            it, n, _ = slots[t]
            if t != i and it == item and n < top:
                put = min(count, top - n)
                slots[t] = (item, n + put, 0)
                count -= put
                if not count:
                    break
    for t in targets:
        if not count:
            break
        if t != i and slots[t] == EMPTY:
            put = min(count, top)
            slots[t] = (item, put, damage)
            count -= put
    slots[i] = _stack(item, count, damage)
    return slots


def grid_items(slots, start, size):
    """The item ids of the size x size grid stored in slots[start:start + size*size], row by row."""
    cells = [s[0] for s in slots[start:start + size * size]]
    return [cells[r * size:(r + 1) * size] for r in range(size)]


def _consume(grid_slots):
    """The grid with one item taken from every non-empty slot, as crafting does."""
    return [_stack(it, n - 1, d) for it, n, d in grid_slots]


def take_result(grid_slots, size, cursor):
    """Craft once into the cursor; returns (new grid, new cursor, crafted?).

    Allowed when the cursor is empty, or holds the result's item with room for the whole result: a craft
    that would only half fit is refused rather than losing items.
    """
    result = R.match(grid_items(grid_slots, 0, size))
    if result is None:
        return list(grid_slots), cursor, False
    item, n = result
    if cursor == EMPTY:
        return _consume(grid_slots), (item, n, 0), True
    if _can_merge(cursor, (item, n, 0)) and cursor[1] + n <= I.max_stack(item):
        return _consume(grid_slots), (item, cursor[1] + n, 0), True
    return list(grid_slots), cursor, False


def _fits(inv, item, n):
    """True when n of item would all go into inv."""
    trial = Inventory()
    trial.slots = list(inv.slots)
    return trial.add(item, n) == 0


def craft_all(grid_slots, size, inv):
    """Craft as many times as the grid allows, straight into inv, stopping when a whole result wouldn't fit."""
    grid = list(grid_slots)
    while True:
        result = R.match(grid_items(grid, 0, size))
        if result is None or not _fits(inv, *result):
            return grid
        inv.add(*result)
        grid = _consume(grid)


def give_back(inv, stacks):
    """Put stacks back into inv (a closing screen's grid and cursor); returns how many items were lost."""
    return sum(inv.add(it, n, d) for it, n, d in stacks if it)
