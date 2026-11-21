"""The Creative inventory: every block, on tabs and pages, to put in the hotbar. (Survival has its
own screens: containers.py.)"""
import math

import pyxel

from pycraft.blocks import BLOCK_NAMES, PLACEABLE, PLANT, TILE
from pycraft.sound import SND_CLICK
from pycraft.ui import IRON, TEXT, TEXT_DIM, text_width


INVENTORY_COLUMNS = 13
INVENTORY_SLOT = TILE + 6  # side of a slot of the inventory, in UI pixels
INVENTORY_HEADER, INVENTORY_FOOTER = 19, 16  # room above the slots (the tabs) and below (pages, hints)
INVENTORY_BELOW = 32  # UI pixels kept free at the bottom of the screen: the hotbar

# The inventory's tabs. Plants and colored blocks are found by their names, the others listed here.
NATURE = {"Grass", "Dirt", "Stone", "Sand", "Water", "Snow", "Ice", "Gravel", "Red sand", "Podzol", "Cactus",
          "Deepslate", "Clay", "Mud", "Moss", "Granite", "Diorite", "Andesite", "Obsidian", "Coarse dirt", "Mycelium",
          "Farmland", "Packed ice", "Netherrack", "Soul sand", "End stone", "Brown mushroom block",
          "Red mushroom block", "Mushroom stem", "Pumpkin", "Melon"}
SPECIAL = {"Crafting table", "Furnace", "Dispenser", "Dropper", "Note block", "Jukebox", "Command block",
           "Glowstone", "Sea lantern", "Jack o'lantern", "Monster spawner", "Slime block", "Sponge", "Wet sponge",
           "Bookshelf"}
REDSTONE = {"Lever", "Stone button", "Pressure plate", "Redstone dust", "Redstone torch", "Repeater",
            "Redstone lamp", "Piston", "Sticky piston", "TNT", "Block of redstone"}


def block_category(block):
    name = BLOCK_NAMES[block]
    if PLANT[block]:
        return "Plants"
    if name.lower().endswith(("wool", "terracotta", "stained glass")):
        return "Colors"
    if name in REDSTONE:
        return "Redstone"
    if name in SPECIAL:
        return "Special"
    if name in NATURE or name.endswith((" ore", " log", " leaves")):
        return "Nature"
    return "Building"


CATEGORIES = [(tab, [b for b in PLACEABLE if tab == "All" or block_category(b) == tab])
              for tab in ("All", "Nature", "Building", "Colors", "Plants", "Redstone", "Special")]


class Inventory:
    """The App's inventory screen, and the hotbar's number keys and wheel."""

    def inventory_layout(self):
        """The inventory shows as many rows of slots as fit above the hotbar, and puts the other
        blocks of the tab on more pages. Every tab has the same size, the one "All" needs. Returns
        the left and top of the slots, the rows per page, the number of pages and the page shown."""
        needed = math.ceil(len(PLACEABLE) / INVENTORY_COLUMNS)
        room = self.ui.height - INVENTORY_BELOW - 2
        rows = max(1, min(needed, (room - INVENTORY_HEADER - INVENTORY_FOOTER) // INVENTORY_SLOT))
        pages = max(1, math.ceil(math.ceil(len(self.inventory_blocks()) / INVENTORY_COLUMNS) / rows))
        x0 = (self.ui.width - INVENTORY_COLUMNS * INVENTORY_SLOT) // 2
        panel = INVENTORY_HEADER + rows * INVENTORY_SLOT + INVENTORY_FOOTER
        top = 2 + (room - panel) // 2 + INVENTORY_HEADER
        return x0, top, rows, pages, min(self.inventory_page, pages - 1)
    def inventory_blocks(self):
        return CATEGORIES[self.inventory_tab][1]
    def inventory_slots(self):
        """(block, x, y) of each slot on the page shown."""
        x0, top, rows, pages, page = self.inventory_layout()
        per_page = rows * INVENTORY_COLUMNS
        for i, block in enumerate(self.inventory_blocks()[page * per_page:(page + 1) * per_page]):
            yield block, x0 + (i % INVENTORY_COLUMNS) * INVENTORY_SLOT, top + (i // INVENTORY_COLUMNS) * INVENTORY_SLOT
    def inventory_tabs(self):
        """(x, y, w, h) of each tab, along the top of the inventory."""
        x0, top, _, _, _ = self.inventory_layout()
        x, rects = x0, []
        for name, _ in CATEGORIES:
            w = text_width(name) + 10
            rects.append((x, top - INVENTORY_HEADER + 4, w, 12))
            x += w + 2
        return rects
    def inventory_arrows(self):
        """(x, y, w, h) of the buttons that show the previous and the next page."""
        x0, top, rows, _, _ = self.inventory_layout()
        y = top + rows * INVENTORY_SLOT + 4
        return (x0, y, 11, 11), (x0 + 37, y, 11, 11)
    def update_inventory(self):
        if self.controls.pressed("inventory") or pyxel.btnp(pyxel.KEY_ESCAPE):
            self.set_state("playing")
            return
        ui = self.ui
        tab = self.inventory_tab
        if pyxel.btnp(pyxel.KEY_TAB):  # the next tab (SHIFT+TAB: the previous one)
            back = pyxel.btn(pyxel.KEY_SHIFT)
            tab = (tab + (-1 if back else 1)) % len(CATEGORIES)
        _, _, _, pages, page = self.inventory_layout()
        # With several pages, the wheel turns them (1-9 still choose the hotbar slot)
        self.update_hotbar_keys(wheel=pages == 1)
        forward = pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_PAGEDOWN)
        back = pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_PAGEUP)
        turn = int(forward) - int(back)
        if pages > 1:
            turn -= pyxel.mouse_wheel
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
            for step, rect in zip((-1, 1), self.inventory_arrows()):
                if pages > 1 and ui.mouse_in(*rect):
                    turn = step
            for i, rect in enumerate(self.inventory_tabs()):
                if ui.mouse_in(*rect):
                    tab = i
            for i, rect in enumerate(self.hotbar_rects()):  # choose the slot the next block goes in
                if ui.mouse_in(*rect) and i != self.selected:
                    self.selected, self.selected_time = i, self.play_time
                    self.sfx(SND_CLICK)
            for block, x, y in self.inventory_slots():
                if ui.mouse_in(x, y, INVENTORY_SLOT, INVENTORY_SLOT):
                    self.inv.slots[self.selected] = (block, 1, 0)
                    self.selected_time = self.play_time
                    self.sfx(SND_CLICK)
        if tab != self.inventory_tab:
            self.inventory_tab, self.inventory_page = tab, 0
            self.sfx(SND_CLICK)
            return
        new_page = min(max(page + turn, 0), pages - 1)
        if new_page != page:
            self.sfx(SND_CLICK)
        self.inventory_page = new_page
    def update_hotbar_keys(self, wheel=True):
        before = self.selected
        for i in range(len(self.hotbar)):
            if pyxel.btnp(pyxel.KEY_1 + i):
                self.selected = i
        if wheel and pyxel.mouse_wheel:
            self.selected = (self.selected - pyxel.mouse_wheel) % len(self.hotbar)
        if self.selected != before:
            self.selected_time = self.play_time
    def draw_inventory(self):
        ui = self.ui
        size = INVENTORY_SLOT
        x0, top, rows, pages, page = self.inventory_layout()
        w = INVENTORY_COLUMNS * size + 10
        ui.panel(x0 - 5, top - INVENTORY_HEADER, w, INVENTORY_HEADER + rows * size + INVENTORY_FOOTER)
        ui.hline(x0 - 3, x0 + w - 8, top - 3, IRON)  # the tabs stand on this line
        for i, ((name, _), (x, y, tw, th)) in enumerate(zip(CATEGORIES, self.inventory_tabs())):
            ui.tab(x, y, tw, th, name, active=i == self.inventory_tab, hot=ui.mouse_in(x, y, tw, th))
        hovered = None
        chosen = self.hotbar[self.selected]
        for block, x, y in self.inventory_slots():
            over = ui.mouse_in(x, y, size, size)
            if over:
                hovered = block
            ui.slot(x, y, size, hot=over, chosen=block == chosen)  # (the chosen slot's block: framed in amber)
            self.draw_icon(x + 3, y + 3, block)
        bottom = top + rows * size
        if pages > 1:  # the page buttons, dimmed on the first and the last page
            for (x, y, bw, bh), label, usable in zip(self.inventory_arrows(), "<>", (page > 0, page < pages - 1)):
                ui.button(x, y, bw, bh, label, hot=usable and ui.mouse_in(x, y, bw, bh), enabled=usable)
            ui.center_text(bottom + 7, f"{page + 1}/{pages}", TEXT, cx=x0 + 24)
        hint = "Click: put in the chosen slot   TAB: next tab"
        ui.text(x0 + w - 10 - text_width(hint), bottom + 7, hint, TEXT_DIM)
        if hovered is not None:
            ui.tooltip(ui.mouse_x, ui.mouse_y, BLOCK_NAMES[hovered])
