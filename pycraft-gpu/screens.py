"""The Survival screens: the inventory (with its 2x2 crafting grid), the crafting table (3x3) and the furnace.

Layout and clicks take plain numbers (UI pixels), so they are tested without a window; draw() is given the
game's Ui and its draw_icon. A screen works on the player's Inventory directly, and keeps its own crafting grid
and the stack held by the mouse (the cursor), which go back into the inventory when it closes.
"""
import items as I
import recipes as R
from inventory import (EMPTY, HOTBAR, MAIN, click, craft_all, give_back, grid_items, shift_click, take_result)
from ui import BLACK, BLUE, GREY, NAVY, TEXT, WHITE, text_width

SLOT = 18  # a 16-pixel icon and a 1-pixel edge around it
PAD = 8  # inside the panel, around the slots
HEADER = 24  # the panel's title
GAP = 8  # between the top part (grid or furnace) and the inventory rows
HOTBAR_GAP = 4
PANEL_W = 9 * SLOT + 2 * PAD
TITLES = {"inventory": "Inventory", "table": "Crafting", "furnace": "Furnace"}
RED, ORANGE, YELLOW, GREEN = 8, 9, 10, 11  # Pyxel's colors


class Screen:
    def __init__(self, inv, kind, furnace=None):
        self.inv = inv
        self.kind = kind
        self.size = {"inventory": 2, "table": 3}.get(kind, 0)  # of the crafting grid
        self.grid = [EMPTY] * (self.size * self.size)
        self.furnace = furnace
        self.cursor = EMPTY
        self.message = ""

    # --- Layout -----------------------------------------------------------------------------------

    def _top_height(self):
        return SLOT * (3 if self.kind in ("table", "furnace") else 2)

    def panel(self, width, height):
        h = HEADER + self._top_height() + GAP + 3 * SLOT + HOTBAR_GAP + SLOT + PAD
        return (width - PANEL_W) // 2, (height - h) // 2, PANEL_W, h

    def layout(self, width, height):
        """The top-left corner of every slot, by region."""
        px, py, _, _ = self.panel(width, height)
        left, top = px + PAD, py + HEADER
        result_x = left + 8 * SLOT  # the rightmost column
        out = {}
        if self.kind == "furnace":
            out["input"] = [(left + 2 * SLOT, top)]
            out["fuel"] = [(left + 2 * SLOT, top + 2 * SLOT)]
            out["output"] = [(result_x - SLOT, top + SLOT)]
        else:
            gx = left + (3 - self.size) * SLOT
            out["grid"] = [(gx + c * SLOT, top + r * SLOT) for r in range(self.size) for c in range(self.size)]
            out["result"] = [(result_x - SLOT, top + (self.size * SLOT - SLOT) // 2)]
        rows_y = top + self._top_height() + GAP
        out["main"] = [(left + c * SLOT, rows_y + r * SLOT) for r in range(3) for c in range(9)]
        out["hotbar"] = [(left + c * SLOT, rows_y + 3 * SLOT + HOTBAR_GAP) for c in range(9)]
        return out

    def _arrow_at(self, width, height):
        """Where the arrow between the grid (or the furnace's input) and the result goes."""
        lay = self.layout(width, height)
        rx, ry = lay["output" if self.kind == "furnace" else "result"][0]
        x0 = (lay["input"][0][0] if self.kind == "furnace" else lay["grid"][-1][0]) + SLOT + 6
        return x0, ry + 5, rx - 6 - x0

    def slot_at(self, mx, my, width, height):
        for region, spots in self.layout(width, height).items():
            for i, (x, y) in enumerate(spots):
                if x <= mx < x + SLOT and y <= my < y + SLOT:
                    return region, i
        return None

    # --- Clicks -----------------------------------------------------------------------------------

    def result(self):
        if not self.size:
            return EMPTY
        found = R.match(grid_items(self.grid, 0, self.size))
        return EMPTY if found is None else (found[0], found[1], 0)

    def _lists(self):
        """Every slot of the screen in one list (inventory, grid, furnace), for moves across them."""
        return self.inv.slots + self.grid + (self.furnace.slots if self.furnace else [])

    def _split(self, slots):
        self.inv.slots = slots[:36]
        n = len(self.grid)
        self.grid = slots[36:36 + n]
        if self.furnace:
            self.furnace.slots = slots[36 + n:]

    def _index(self, region, i):
        """The slot's place in _lists()."""
        if region == "hotbar":
            return i
        if region == "main":
            return 9 + i
        if region == "grid":
            return 36 + i
        return 36 + len(self.grid) + ("input", "fuel", "output").index(region)

    def click(self, mx, my, width, height, button, shift):
        hit = self.slot_at(mx, my, width, height)
        if hit is None:
            return
        region, i = hit
        if region == "result":
            if shift:
                self.grid = craft_all(self.grid, self.size, self.inv)
            else:
                self.grid, self.cursor, _ = take_result(self.grid, self.size, self.cursor)
            return
        if shift:
            self._split(shift_click(self._lists(), self._index(region, i), self._shift_targets(region, i)))
            return
        if region == "output":
            self._take_output()
            return
        if region == "fuel" and self.cursor != EMPTY and R.fuel_value(self.cursor[0]) == 0:
            return  # only what burns goes in the fuel slot
        slots, self.cursor = click(self._lists(), self.cursor, self._index(region, i), button)
        self._split(slots)

    def _shift_targets(self, region, i):
        """Where a shift-click sends the stack in this slot."""
        everywhere = list(HOTBAR) + list(MAIN)
        if region in ("grid", "input", "fuel", "output"):
            return everywhere
        across = list(MAIN) if region == "hotbar" else list(HOTBAR)
        if self.kind == "furnace":
            item = self.inv.slots[self._index(region, i)][0]
            base = 36 + len(self.grid)
            if R.smelt_result(item) is not None:
                return [base]  # smeltables to the input...
            if R.fuel_value(item) > 0:
                return [base + 1]  # ...fuels to the fuel slot
        return across

    def _take_output(self):
        out = self.furnace.slots[2]
        if out == EMPTY:
            return
        if self.cursor == EMPTY:
            self.cursor, self.furnace.slots[2] = out, EMPTY
        elif self.cursor[0] == out[0]:
            room = I.max_stack(out[0]) - self.cursor[1]
            n = min(room, out[1])
            if n > 0:
                self.cursor = (out[0], self.cursor[1] + n, 0)
                self.furnace.slots[2] = (out[0], out[1] - n, 0) if out[1] > n else EMPTY

    def close(self):
        """Put the grid and the cursor back into the inventory; returns how many items were lost."""
        lost = give_back(self.inv, self.grid + [self.cursor])
        self.grid = [EMPTY] * len(self.grid)
        self.cursor = EMPTY
        self.message = f"Inventory full: {lost} item{'s' if lost > 1 else ''} lost" if lost else ""
        return lost

    # --- Drawing ----------------------------------------------------------------------------------

    def draw(self, ui, draw_icon, mx, my, width, height):
        px, py, pw, ph = self.panel(width, height)
        ui.panel(px, py, pw, ph, TITLES[self.kind])
        lay = self.layout(width, height)
        hovered = None
        for region, spots in lay.items():
            for i, (x, y) in enumerate(spots):
                stack = self._stack(region, i)
                over = x <= mx < x + SLOT and y <= my < y + SLOT
                if over:
                    hovered = stack
                draw_slot(ui, draw_icon, x, y, stack, over)
        ax, ay, aw = self._arrow_at(width, height)
        if self.kind == "furnace":
            f = self.furnace
            fx, fy = lay["input"][0][0], lay["input"][0][1] + SLOT
            flame = f.burn_left / f.burn_total if f.burn_total else 0
            ui.rect(fx + 5, fy + 3, 8, 12, NAVY)
            lit = round(12 * min(max(flame, 0), 1))
            if lit:
                ui.rect(fx + 5, fy + 15 - lit, 8, lit, ORANGE)
                ui.rect(fx + 7, fy + 15 - lit + lit // 3, 4, lit - lit // 3, YELLOW)
            draw_arrow(ui, ax, ay, aw, f.cook / R.COOK_TICKS)
        else:
            draw_arrow(ui, ax, ay, aw, None)
        if self.cursor != EMPTY:
            draw_stack(ui, draw_icon, mx - 8, my - 8, self.cursor)
        elif hovered not in (None, EMPTY):
            ui.tooltip(mx, my, I.name(hovered[0]))

    def _stack(self, region, i):
        if region == "result":
            return self.result()
        return self._lists()[self._index(region, i)]


def draw_stack(ui, draw_icon, x, y, stack):
    """An item's icon at (x, y), with its count (above 1) and its wear (a damaged tool)."""
    item, count, damage = stack
    if not item:
        return
    draw_icon(x, y, item)
    tool = I.TOOLS.get(item)
    if tool is not None and damage > 0:
        left = max(0.0, 1 - damage / tool.durability)
        ui.rect(x + 2, y + 13, 12, 2, BLACK)
        ui.rect(x + 2, y + 13, max(1, round(12 * left)), 1, GREEN if left > 0.5 else YELLOW if left > 0.2 else RED)
    if count > 1:
        s = str(count)
        ui.text(x + 17 - text_width(s), y + 11, s, WHITE, shadow=True)


def draw_slot(ui, draw_icon, x, y, stack, hot=False):
    ui.rect(x, y, SLOT, SLOT, BLUE if hot else BLACK)
    ui.rectb(x, y, SLOT, SLOT, WHITE if hot else NAVY)
    draw_stack(ui, draw_icon, x + 1, y + 1, stack)


def draw_arrow(ui, x, y, w, fraction):
    """An arrow pointing right, w pixels long; filled from the left by fraction (None: not a progress)."""
    shaft = w - 5
    ui.rect(x, y + 3, shaft, 2, GREY)
    for i in range(5):
        ui.vline(x + shaft + i, y + i, y + 7 - i, GREY)
    if fraction:
        filled = round((w - 1) * min(fraction, 1))
        ui.rect(x, y + 3, min(filled, shaft), 2, TEXT)
        for i in range(max(0, filled - shaft)):
            ui.vline(x + shaft + i, y + i, y + 7 - i, TEXT)

