"""The title screen and the pause menu: their buttons, by mouse or keyboard."""
import pyxel

from pycraft.sound import SND_CLICK
from pycraft.ui import AMBER, BASE_HEIGHT, BLACK, CREAM, GOLD, RUST, TEXT_DIM, text_width


BUTTON_W, BUTTON_H, BUTTON_PITCH = 128, 15, 19  # buttons of the title screen and the pause menu


class Menus:
    """The App's title screen and pause menu."""

    def menu_items(self):
        """(label, action) pairs for the buttons of the title screen or of the pause menu."""
        if self.state == "title":
            items = []
            if not self.world_is_fresh:
                items.append(("Continue", lambda: self.start_game(new_world=False)))
            items.append(("New world", self.new_world_clicked))
            items.append(("Settings", self.open_settings))
            items.append(("Quit", pyxel.quit))
            return items
        if self.state == "paused":
            return [
                ("Resume", lambda: self.set_state("playing")),
                ("Settings", self.open_settings),
                ("Save and go to title", self.save_and_title),
                ("Save and quit", self.save_and_quit),
            ]
        return []
    def new_world_clicked(self):
        if self.world_is_fresh:
            self.start_game(new_world=True)
        else:
            self.state = "generating"  # draw a message first, generate on the next update
    def save_and_title(self):
        self.save()
        self.save_data = self.snapshot()  # for "Continue"
        self.title_spot = list(self.player.pos)
        self.set_state("title")
    def save_and_quit(self):
        self.save()
        pyxel.quit()
    def update_menu(self):
        """The buttons of the title screen and of the pause menu: the mouse, or the arrows and Enter."""
        items = self.menu_items()
        ui = self.ui
        hovered = self.button_at(ui.mouse_x, ui.mouse_y, len(items))
        if hovered is not None and (ui.mouse_x, ui.mouse_y) != self.last_mouse:
            self.menu_index = hovered
        self.last_mouse = (ui.mouse_x, ui.mouse_y)
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            self.menu_index = (self.menu_index + 1) % len(items)
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W):
            self.menu_index = (self.menu_index - 1) % len(items)
        chosen = None
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
            chosen = self.menu_index
        if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT) and hovered is not None:
            chosen = hovered
        if chosen is not None:
            self.sfx(SND_CLICK)
            items[chosen][1]()
    def menu_top(self):
        """UI y of the first button of the title screen and the pause menu: below the middle."""
        return self.ui.height // 2 + 2
    def button_rect(self, i):
        return (self.ui.width - BUTTON_W) // 2, self.menu_top() + i * BUTTON_PITCH, BUTTON_W, BUTTON_H
    def button_at(self, mx, my, count):
        for i in range(count):
            x, y, w, h = self.button_rect(i)
            if x <= mx < x + w and y <= my < y + h:
                return i
        return None
    def draw_title(self):
        ui = self.ui
        cx, h = ui.width // 2, ui.height
        logo = 5 * h // BASE_HEIGHT  # the logo grows with the interface
        y = h * 48 // BASE_HEIGHT - 3 - 3 * (logo - 1)  # top of the scaled 28x6 logo
        x = cx - 14 * logo
        depth = max(1, logo // 4)  # the letters stand out of the screen: gold on top, amber then rust below
        for dx, dy, col in ((2 * depth, 3 * depth, BLACK), (0, 2 * depth, RUST), (0, depth, AMBER), (0, 0, GOLD)):
            pyxel.pal(7, col)
            ui.blt(x + dx, y + dy, 1, 0, 0, 28, 6, 0, scale=logo)
        pyxel.pal()
        ui.center_text(h // 2 - 22, "A Minecraft-like game made with Pyxel", CREAM, shadow=True)
        self.draw_menu()
        ui.text(3, h - 9, f"Seed {self.world.seed}", TEXT_DIM, shadow=True)
        hint = "Mouse or arrows to choose, ENTER to pick"
        ui.text(ui.width - text_width(hint) - 3, h - 9, hint, TEXT_DIM, shadow=True)
    def draw_menu(self):
        """The buttons of the title screen and the pause menu."""
        for i, (label, _) in enumerate(self.menu_items()):
            self.ui.button(*self.button_rect(i), label, hot=i == self.menu_index)
