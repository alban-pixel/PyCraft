"""What is drawn over the world while playing: crosshair, hotbar, notices, the F3 info and
the list of controls."""
import math

import pyxel

from pycraft.blocks import BLOCK_NAMES, TILE
from pycraft.terrain import SEA_LEVEL
from pycraft.ui import AMBER, ASH, BLACK, COAL, GOLD, IRON, TEXT, TEXT_HOT, WHITE, text_width


HOTBAR_SLOT = TILE + 6
NAME_SECONDS = 3.0  # the chosen block's name shows this long above the hotbar


class Hud:
    """The App's HUD."""

    def hotbar_rects(self):
        """(x, y, w, h) of each slot of the hotbar, at the bottom of the screen."""
        n = len(self.hotbar)
        x0 = (self.ui.width - HOTBAR_SLOT * n) // 2
        y0 = self.ui.height - HOTBAR_SLOT - 4
        return [(x0 + i * HOTBAR_SLOT, y0, HOTBAR_SLOT, HOTBAR_SLOT) for i in range(n)]
    def draw_hud(self):
        ui = self.ui
        self.draw_hotbar()
        if self.state == "inventory":
            return  # (the rest would show through the inventory)
        cx, cy = ui.width // 2, ui.height // 2
        # The crosshair, with a dark rim so it shows on bright blocks and on the sky too
        if self.settings["crosshair"] == "cross":
            ui.shade(cx - 5, cy - 1, 11, 3, 0.5)
            ui.shade(cx - 1, cy - 5, 3, 4, 0.5)
            ui.shade(cx - 1, cy + 2, 3, 4, 0.5)
            ui.hline(cx - 4, cx + 4, cy, WHITE)
            ui.vline(cx, cy - 4, cy + 4, WHITE)
        elif self.settings["crosshair"] == "dot":
            ui.shade(cx - 2, cy - 2, 4, 4, 0.5)
            ui.rect(cx - 1, cy - 1, 2, 2, WHITE)

        y0 = self.hotbar_rects()[0][1]
        if self.state == "playing":  # (the chat line would cover them)
            if self.play_time - self.selected_time < NAME_SECONDS:
                ui.center_text(y0 - 14, BLOCK_NAMES[self.hotbar[self.selected]], TEXT, shadow=True)
            if self.message and self.play_time - self.message_time < 2.5:
                ui.toast(y0 - 30, self.message)

        y = 2
        if self.show_debug:
            y = self.draw_debug(y) + 3
        if self.show_help:
            self.draw_help(y)
        if not self.mouse_captured and self.state == "playing":
            ui.toast(cy + 10, "Click to capture the mouse")
    def draw_hotbar(self):
        ui = self.ui
        rects = self.hotbar_rects()
        x0, y0, size, _ = rects[0]
        ui.rect(x0 - 3, y0 - 3, size * len(rects) + 6, size + 6, BLACK)
        ui.rect(x0 - 2, y0 - 2, size * len(rects) + 4, size + 4, COAL)
        ui.rectb(x0 - 2, y0 - 2, size * len(rects) + 4, size + 4, IRON)
        for i, (block, (x, y, w, h)) in enumerate(zip(self.hotbar, rects)):
            ui.slot(x, y, w)
            self.draw_icon(x + 3, y + 3, block)
            ui.text(x + 2, y + 2, str(i + 1), TEXT_HOT if i == self.selected else ASH, shadow=True)
        x, y, w, h = rects[self.selected]  # the chosen slot: a thick amber frame
        ui.rectb(x - 1, y - 1, w + 2, h + 2, GOLD)
        ui.rectb(x, y, w, h, AMBER)
    def draw_text_panel(self, y, lines):
        """(text, color) lines on a see-through panel at the left of the screen. Returns its bottom."""
        ui = self.ui
        w, h = max(text_width(s) for s, _ in lines) + 10, len(lines) * 8 + 5
        ui.glass(2, y, w, h)
        for i, (s, col) in enumerate(lines):
            ui.text(7, y + 3 + i * 8, s, col, shadow=True)
        return y + h
    def draw_debug(self, y):
        px, py, pz = self.player.pos
        hours = int((self.time_of_day * 24 + 6) % 24)
        biome = self.world.biome_at(math.floor(px), math.floor(pz))
        r = self.renderer
        sw, sh = r.scene_size
        gpu = "" if r.gpu_time is None else f"  GPU {r.gpu_time * 1000:.1f} ms"
        auto = ", auto" if self.settings["render_scale"] == "auto" else ""
        first, last = r.far.shown
        far = f"levels {first + 1}-{last + 1} of {r.far.levels()}" if last >= first else "not ready yet"
        lines = [f"FPS {self.fps:4.0f} / {self.settings['fps']}  {pyxel.width}x{pyxel.height}"
                 + ("" if self.settings["fancy"] else "  fast graphics"),
                 f"3D drawn at {sw}x{sh} ({r.render_scale:.0%}{auto}){gpu}",
                 f"XYZ {px:7.1f} {py:6.1f} {pz:7.1f}  Altitude {py - SEA_LEVEL - 1:5.0f}",
                 f"Biome {biome}",
                 f"Chunks {r.drawn} drawn / {len(r.chunks.meshes)} built",
                 f"Distant terrain: {far}",
                 f"Time {hours:02d}:00  Seed {self.world.seed}" + ("  FLY" if self.player.flying else "")]
        return self.draw_text_panel(y, [(line, TEXT) for line in lines])
    def help_lines(self):
        """The controls, with the keys they have now: (keys, what they do), in two columns."""
        key = self.controls.name
        move = [key(action) for action in ("forward", "left", "back", "right")]
        return [
            [("".join(move) if all(len(k) == 1 for k in move) else " ".join(move), "Move"),
             (key("jump"), "Jump, swim, fly up"), (key("down"), "Fly down"), (key("sprint"), "Sprint, fly fast"),
             (key("fly"), "Fly on/off"), (key("zoom"), "Zoom"), (key("inventory"), "All the blocks"),
             (key("chat"), "Chat, commands")],
            [(key("break"), "Break"), (key("place"), "Place, use"), (key("pick"), "Pick the block"),
             ("1-9, WHEEL", "Choose a block"), (key("mouse"), "Free the mouse"), (key("info"), "Info"),
             (key("help"), "Hide this help"), ("ESC", "Menu, settings")],
        ]
    def draw_help(self, y):
        """The controls in two columns: the keys in amber, what they do in white."""
        ui = self.ui
        lines = self.help_lines()
        columns = [(column, max(text_width(k) for k, _ in column) + 6, max(text_width(a) for _, a in column))
                   for column in lines]
        w = sum(kw + aw for _, kw, aw in columns) + 12 * (len(columns) - 1) + 10
        h = max(len(column) for column in lines) * 8 + 15
        ui.glass(2, y, w, h)
        ui.text(7, y + 3, "Controls", TEXT_HOT, shadow=True)
        x = 7
        for column, kw, aw in columns:
            for i, (keys, action) in enumerate(column):
                ui.text(x, y + 13 + i * 8, keys, AMBER, shadow=True)
                ui.text(x + kw, y + 13 + i * 8, action, TEXT, shadow=True)
            x += kw + aw + 12
