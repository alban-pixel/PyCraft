"""Survival rules that don't need a window: health (falls, drowning, slow healing, death) and the progress of
breaking a block, which takes time in Survival."""
import math

import numpy as np

from pycraft import items as I
from pycraft.blocks import DEFAULT_HOTBAR
from pycraft.inventory import EMPTY, Inventory

EPS = 1e-9  # so that 60 frames of 1/60 s add up to a whole second


class Health:
    MAX_HP = 20  # 10 hearts
    MAX_AIR = 300  # ticks of air under water (15 s)
    REGEN_SECONDS = 4  # +1 HP this often
    DROWN_SECONDS = 0.5  # -1 HP this often without air: 2 HP a second

    def __init__(self):
        self.reset()

    def reset(self):
        self.hp = self.MAX_HP
        self.air = float(self.MAX_AIR)
        self._regen = 0.0
        self._drown = 0.0

    @property
    def dead(self):
        return self.hp <= 0

    def damage(self, n):
        self.hp = max(0, self.hp - n)

    def update(self, dt, head_in_water, creative):
        """One frame of breathing and healing; returns the damage taken."""
        if creative:
            self.air, self._drown = float(self.MAX_AIR), 0.0
            return 0
        if self.dead:
            return 0
        taken = 0
        if head_in_water:
            if self.air > 0:
                self.air = max(0.0, self.air - dt * 20)
            else:
                self._drown += dt
                while self._drown >= self.DROWN_SECONDS - EPS:
                    self._drown -= self.DROWN_SECONDS
                    self.damage(1)
                    taken += 1
        else:
            self.air, self._drown = float(self.MAX_AIR), 0.0
        if self.hp < self.MAX_HP and not self.dead:
            self._regen += dt
            while self._regen >= self.REGEN_SECONDS - EPS and self.hp < self.MAX_HP:
                self._regen -= self.REGEN_SECONDS
                self.hp += 1
        else:
            self._regen = 0.0
        return taken

    def fall_damage(self, distance, landed_in_water, creative):
        """Hurt the player for landing after a fall of `distance` blocks; returns the damage."""
        if creative or landed_in_water or distance <= 3:
            return 0
        n = math.ceil(distance - 3 - EPS)
        self.damage(n)
        return n


class BreakProgress:
    """How far the block under the crosshair is toward breaking, while the button is held on it.

    Progress is kept as a fraction, not as time: switching to a better tool halfway goes on from where it was,
    at the new tool's speed.
    """

    def __init__(self):
        self.reset()

    def reset(self):
        self.fraction = 0.0
        self._key = None

    def update(self, target, block, tool_item, dt, creative):
        """One frame of holding the button on `target` (which holds `block`); True on the frame it breaks."""
        if creative:
            self.reset()
            return True
        if (target, block) != self._key:
            self.reset()
            self._key = (target, block)
        seconds = I.break_seconds(block, tool_item)
        if seconds == 0:
            self.reset()
            return True
        if math.isinf(seconds):
            self.fraction = 0.0
            return False
        self.fraction = min(1.0, self.fraction + dt / seconds)
        if self.fraction >= 1 - EPS:
            self.reset()
            return True
        return False


SURVIVAL, CREATIVE = 0, 1
MODE_NAMES = {SURVIVAL: "Survival", CREATIVE: "Creative"}


def convert_old_save(data):
    """(mode, inventory) from a save's data. A save from before Survival (no "inventory") is a Creative game
    whose hotbar of 9 block numbers becomes 9 stacks of one."""
    if "inventory" in data:
        return int(data["mode"]), Inventory.from_array(data["inventory"])
    inv = Inventory()
    for i, block in enumerate(np.asarray(data.get("hotbar", DEFAULT_HOTBAR)).tolist()[:9]):
        if block:
            inv.slots[i] = (int(block), 1, 0)
    return CREATIVE, inv


def creative_inventory():
    """A new Creative game's inventory: the default hotbar, one of each."""
    inv = Inventory()
    inv.slots[:9] = [(b, 1, 0) if b else EMPTY for b in list(DEFAULT_HOTBAR)[:9]]
    return inv


def parse_gamemode(text):
    """SURVIVAL or CREATIVE from /gamemode's argument (a name, its first letter or its number), else None."""
    return {"survival": SURVIVAL, "s": SURVIVAL, "0": SURVIVAL,
            "creative": CREATIVE, "c": CREATIVE, "1": CREATIVE}.get(text.strip().lower())


def harvest(inv, slot, block, rng, contents=()):
    """Survival: the player broke block with the stack in inv.slots[slot]. Its drops (and contents, a broken
    furnace's) go into the inventory, and the tool wears. Returns (items lost for want of room, the name of the
    tool if it broke, else None)."""
    tool = inv.slots[slot][0]
    lost = sum(inv.add(item, n) for item, n in I.drops(block, tool, rng))
    lost += sum(inv.add(item, n, damage) for item, n, damage in contents)
    broke = None
    if tool in I.TOOLS and I.hardness(block) > 0 and inv.damage_tool(slot):
        broke = I.name(tool)
    return lost, broke
