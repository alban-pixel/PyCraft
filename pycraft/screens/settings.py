"""The settings screen: five tabs of settings (one of them the keys), with values
to step through, sliders, keys to give, and Defaults and Done."""
import os

import pyxel

from pycraft.controls import ACTIONS, Controls, LABELS
from pycraft.render import LOD_QUALITY_NAMES
from pycraft.screens.menus import BUTTON_H
from pycraft.settings import (AUTOSAVES, CROSSHAIRS, DAY_LENGTHS, DEFAULT_SETTINGS, FRAME_RATES, RANGES,
                              RENDER_DISTANCES, RENDER_SCALES, RESOLUTIONS, SETTING_TABS, TAB_NAMES, fit_text,
                              next_pack)
from pycraft.sound import SND_CLICK
from pycraft.ui import IRON, TEXT_DIM, TEXT_HOT, Ui


SETTINGS_W, SETTINGS_H = 304, 172  # the settings panel
TAB_H, ROW_H, ROW_PITCH = 13, 12, 13  # its tabs and its rows
SETTING_ROWS = 9  # rows that fit under the tabs (the keys go in two columns of them)


class SettingsScreen:
    """The App's settings screen, and what each change of a setting does."""

    def change_texture_pack(self, step):
        """Next / previous texture pack: applied on the next update, once "Loading textures..." shows."""
        if not self.packs and self.settings["texture_pack"] is None:
            return
        self.pack_to_apply = next_pack(self.settings["texture_pack"], self.packs, step)
        self.pack_message = "Loading textures..."
    def texture_pack_row(self):
        current = self.settings["texture_pack"]
        info = next((p for p in self.packs if p.path == current), None)
        name = "Default" if current is None else info.name if info else os.path.basename(current)
        if self.pack_message:
            explain = self.pack_message
        elif not self.has_pillow:
            explain = "Install Pillow to use texture packs"
        elif current is None:
            explain = "Packs go in " + fit_text(self.pack_dirs[0], 44)
        else:
            explain = info.description if info and info.description else "Minecraft-style texture pack"
        return ("Texture pack", fit_text(name, 19, keep="start"), self.change_texture_pack, fit_text(explain, 56))
    def mouse_on_chosen(self):
        """True if the mouse is on the chosen line of the settings (a change that moves the panel
        then puts the cursor back on it)."""
        x, y, w, h = self.setting_rects()[self.menu_index]
        return self.ui.mouse_in(x, y, w, h)
    def change_resolution(self, step):
        on_row = self.mouse_on_chosen()
        i = RESOLUTIONS.index(self.settings["resolution"])
        self.settings["resolution"] = RESOLUTIONS[(i + step) % len(RESOLUTIONS)]
        self.save_settings()
        self.set_resolution(*self.settings["resolution"])
        self.warp_to_button = on_row  # the row moved: put the cursor back on it next frame
    def change_ui_scale(self, step):
        """Auto, then every scale that leaves the menus room at this resolution."""
        on_row = self.mouse_on_chosen()
        choices = ["auto"] + list(range(1, Ui.max_scale(pyxel.height) + 1))
        current = self.settings["ui_scale"]
        i = choices.index(current) if current in choices else 0
        self.settings["ui_scale"] = choices[(i + step) % len(choices)]
        self.save_settings()
        self.ui.set_screen_size(pyxel.width, pyxel.height, self.settings["ui_scale"])
        self.warp_to_button = on_row
    def cycle(self, key, choices, step):
        """The next (or previous) of a setting's values."""
        i = choices.index(self.settings[key])
        self.settings[key] = choices[(i + step) % len(choices)]
        self.apply_setting(key)
    def nudge(self, key, step):
        """A setting on a scale, one step up or down."""
        low, high, by = RANGES[key]
        self.settings[key] = min(max(self.settings[key] + step * by, low), high)
        self.apply_setting(key)
    def slide(self, key, fraction):
        """A setting on a scale, put where the mouse holds its slider."""
        low, high, by = RANGES[key]
        value = low + round(min(max(fraction, 0.0), 1.0) * (high - low) / by) * by
        if value != self.settings[key]:
            self.settings[key] = value
            self.apply_setting(key)
    def apply_setting(self, key):
        """Make a setting that just changed take effect, and save the settings. (The field of view,
        the mouse and the game's own settings are read where they are used.)"""
        s = self.settings
        if key in ("render_scale", "fps"):  # (a new frame rate: the automatic scale starts again)
            self.apply_render_scale()
        elif key == "render_distance":
            self.renderer.render_distance = s[key]
        elif key == "lod_quality":
            self.renderer.set_lod_quality(s[key])
        elif key == "fancy":
            self.renderer.set_fancy(s[key])
        elif key in ("music_volume", "sound_volume"):
            self.apply_sound()
        self.save_settings()
    def reset_tab(self):
        """The settings of the tab shown go back to what they were at first."""
        keys = SETTING_TABS[TAB_NAMES[self.settings_tab]]
        if keys == ["keys"]:
            self.controls.reset()
            self.settings["keys"] = self.controls.to_settings()
            self.save_settings()
            return
        before = dict(self.settings)
        if "texture_pack" in keys and self.settings["texture_pack"] is not None:
            self.pack_to_apply, self.pack_message = None, "Loading textures..."  # (applied on the next update)
        keys = [key for key in keys if key != "texture_pack"]
        for key in keys:
            self.settings[key] = DEFAULT_SETTINGS[key]
        if (self.settings["resolution"], self.settings["ui_scale"]) != (before["resolution"], before["ui_scale"]):
            self.set_resolution(*self.settings["resolution"])
            self.warp_to_button = True
        for key in keys:
            if self.settings[key] != before[key]:
                self.apply_setting(key)
    def open_settings(self):
        self.settings_parent = self.state
        self.settings_note = ""
        self.packs = self.find_packs()  # (a pack put in the folder while the game runs shows up)
        self.pack_message = ""
        self.set_state("settings")
    def close_settings(self):
        self.binding = self.dragging = None
        self.set_state(self.settings_parent)
        self.menu_index = [label for label, _ in self.menu_items()].index("Settings")
    def setting_rows(self):
        """The lines of the tab of the settings that shows. Each is (kind, name, value, change,
        explanation, fraction, slide): a "choice" has a few values and change takes a step (1 for
        the next, -1 for the previous); a "slider" is on a scale, at `fraction` of it, and slide
        puts it at another fraction; a "key" is an action and its key, and change is the action."""
        s = self.settings

        def choice(name, value, change, explain):
            return ("choice", name, value, change, explain, None, None)

        def pick(name, value, key, choices, explain):
            return choice(name, value, lambda step: self.cycle(key, choices, step), explain)

        def slider(name, value, key, explain):
            low, high, _ = RANGES[key]
            return ("slider", name, value, lambda step: self.nudge(key, step), explain,
                    (s[key] - low) / (high - low), lambda fraction: self.slide(key, fraction))

        def volume(key):
            return f"{s[key]}%" if s[key] else "Off"

        tab = TAB_NAMES[self.settings_tab]
        if tab == "Video":
            width, height = s["resolution"]
            ui_size = f"{self.ui.scale}x"
            render = f"{self.renderer.render_scale:.0%}"
            return [
                choice("Resolution", f"{width} x {height}", self.change_resolution,
                       "Pixels in the picture: fewer is faster"),
                choice("Interface size", f"Auto ({ui_size})" if s["ui_scale"] == "auto" else ui_size,
                       self.change_ui_scale, "Size of the menus, the text and the hotbar"),
                pick("Frame rate", f"{s['fps']} FPS", "fps", FRAME_RATES, "Frames per second the game aims for"),
                slider("Field of view", f"{s['fov']}", "fov", "How wide you see, in degrees: wider shows more, smaller"),
                pick("3D resolution", f"Auto ({render})" if s["render_scale"] == "auto" else render, "render_scale",
                     RENDER_SCALES, "Auto: the world is drawn smaller when it's slow"),
                pick("Render distance", f"{s['render_distance']} chunks", "render_distance", RENDER_DISTANCES,
                     "How far you can see: shorter is faster"),
                pick("LOD quality", s["lod_quality"].capitalize(), "lod_quality", LOD_QUALITY_NAMES,
                     "Detail of the faraway terrain"),
                pick("Graphics", "Fancy" if s["fancy"] else "Fast", "fancy", [False, True],
                     "Fancy: shadows and smooth edges"),
                choice(*self.texture_pack_row()),
            ]
        if tab == "Controls":
            return [
                slider("Mouse speed", f"{s['sensitivity']}%", "sensitivity",
                       "How far the view turns when the mouse moves"),
                pick("Invert mouse", "On" if s["invert_y"] else "Off", "invert_y", [False, True],
                     "On: pushing the mouse forward looks down"),
                slider("Arrow keys speed", f"{s['look_speed']}", "look_speed",
                       "Looking around with the arrow keys, in degrees per second"),
            ]
        if tab == "Keys":
            return [("key", LABELS[action], self.controls.name(action), action,
                     "ENTER or a click, then the new key or mouse button", None, None) for action, _, _ in ACTIONS]
        if tab == "Sound":
            return [
                slider("Music", volume("music_volume"), "music_volume", "Volume of the background music"),
                slider("Sound effects", volume("sound_volume"), "sound_volume",
                       "Volume of the steps, the splashes and the blocks"),
            ]
        minutes = s["autosave"]
        return [
            pick("Autosave", f"Every {minutes} min" if minutes else "Off", "autosave", AUTOSAVES,
                 "The game is also saved when you leave through the menu"),
            pick("Day length", f"{s['day_length']} minutes", "day_length", DAY_LENGTHS,
                 "How long a day and its night last"),
            pick("Controls help", "At the start" if s["show_help"] else "Hidden", "show_help", [False, True],
                 "The list of keys shown when a game starts (the help key brings it back)"),
            pick("Crosshair", s["crosshair"].capitalize(), "crosshair", CROSSHAIRS,
                 "The mark in the middle of the screen"),
        ]
    def update_settings(self):
        """The settings screen: tabs, then the lines of the tab shown, then "Defaults" and "Done".
        The mouse or the keyboard: Up/Down choose a line, Left/Right change it, Tab changes tab."""
        ui = self.ui
        if self.binding is not None:  # an action waits for its new key: the next one pressed is it
            if pyxel.btnp(pyxel.KEY_ESCAPE):
                self.binding = None
                return
            key = Controls.key_pressed()
            if key is not None:
                other = self.controls.bind(self.binding, key)
                self.settings_note = f"{LABELS[other]}: now {self.controls.name(other)}" if other else ""
                self.binding = None
                self.settings["keys"] = self.controls.to_settings()
                self.save_settings()
                self.sfx(SND_CLICK)
            return
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.close_settings()
            return
        rows, rects = self.setting_rows(), self.setting_rects()
        n = len(rows)  # the lines, then "Defaults" (n) and "Done" (n + 1)
        if self.warp_to_button:
            self.warp_to_button = False
            if not self.headless:
                x, y, w, h = rects[self.menu_index]
                pyxel.set_mouse_pos(*ui.to_screen(x + w // 2, y + h // 2))
        mouse = (ui.mouse_x, ui.mouse_y)
        if self.dragging is not None:  # a slider follows the mouse for as long as its button is down
            if pyxel.btn(pyxel.MOUSE_BUTTON_LEFT) and self.dragging < n and rows[self.dragging][0] == "slider":
                x, _, w, _ = rects[self.dragging]
                sx, sw = Ui.slider_box(x, w)
                rows[self.dragging][6]((mouse[0] - sx - 2) / max(sw - 5, 1))
            else:
                self.dragging = None
            self.last_mouse = mouse
            return
        clicked = pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT)
        back = pyxel.btn(pyxel.KEY_SHIFT)
        turn = int(pyxel.btnp(pyxel.KEY_PAGEDOWN) or (pyxel.btnp(pyxel.KEY_TAB) and not back)) \
            - int(pyxel.btnp(pyxel.KEY_PAGEUP) or (pyxel.btnp(pyxel.KEY_TAB) and back))
        for i, rect in enumerate(self.tab_rects()):
            if clicked and ui.mouse_in(*rect):
                turn = i - self.settings_tab
        if turn:
            self.settings_tab = (self.settings_tab + turn) % len(TAB_NAMES)
            self.menu_index, self.settings_note = 0, ""
            self.sfx(SND_CLICK)
            return
        hovered = next((i for i, rect in enumerate(rects) if ui.mouse_in(*rect)), None)
        index = self.menu_index
        if hovered is not None and mouse != self.last_mouse:
            index = hovered
        self.last_mouse = mouse
        if pyxel.btnp(pyxel.KEY_DOWN) or pyxel.btnp(pyxel.KEY_S):
            index = (index + 1) % (n + 2)
        if pyxel.btnp(pyxel.KEY_UP) or pyxel.btnp(pyxel.KEY_W):
            index = (index - 1) % (n + 2)
        step = int(pyxel.btnp(pyxel.KEY_RIGHT) or pyxel.btnp(pyxel.KEY_D)) \
            - int(pyxel.btnp(pyxel.KEY_LEFT) or pyxel.btnp(pyxel.KEY_A))
        if step and index >= n:  # between the two buttons
            index, step = n + (1 if step > 0 else 0), 0
        elif step and rows[index][0] == "key":  # between the two columns of keys
            if 0 <= index + step * SETTING_ROWS < n:
                index += step * SETTING_ROWS
            step = 0
        if index != self.menu_index:
            self.menu_index, self.settings_note = index, ""
        chosen = index if step else None
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
            chosen, step = index, 1
        if clicked and hovered is not None:
            chosen, step = hovered, 1
            if hovered < n and rows[hovered][0] == "choice":
                x, _, w, _ = rects[hovered]
                vx, _ = Ui.value_box(x, w)
                if vx - 3 <= mouse[0] < vx + 8:  # on the "<" of the value: the previous one
                    step = -1
            elif hovered < n and rows[hovered][0] == "slider":
                self.menu_index, self.dragging = hovered, hovered  # (it moves from the next frame on)
                return
        if pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT) and hovered is not None and hovered < n \
                and rows[hovered][0] == "choice":
            chosen, step = hovered, -1
        if chosen is None:
            return
        self.sfx(SND_CLICK)
        self.menu_index = chosen
        if chosen == n:
            self.reset_tab()
            self.settings_note = "Back to the defaults"
        elif chosen == n + 1:
            self.close_settings()
        elif rows[chosen][0] == "key":
            self.binding, self.settings_note = rows[chosen][3], ""
        else:
            rows[chosen][3](step)
    def settings_panel(self):
        """(x, y, w, h) of the settings panel: the tabs, the lines of the tab shown, a line that
        explains the chosen one, and two buttons."""
        return ((self.ui.width - SETTINGS_W) // 2, max(1, (self.ui.height - SETTINGS_H) // 2), SETTINGS_W,
                SETTINGS_H)
    def tab_rects(self):
        x, y, w, _ = self.settings_panel()
        tw = (w - 8) // len(TAB_NAMES)
        return [(x + 4 + i * tw, y + 4, tw, TAB_H) for i in range(len(TAB_NAMES))]
    def setting_rects(self):
        """(x, y, w, h) of each line of the tab shown, then of "Defaults" and of "Done". The keys
        go in two columns."""
        x, y, w, h = self.settings_panel()
        top = y + 4 + TAB_H + 4
        count = len(self.setting_rows())
        if TAB_NAMES[self.settings_tab] == "Keys":
            cw = (w - 12) // 2
            rects = [(x + 6 + (i // SETTING_ROWS) * (cw + 2), top + (i % SETTING_ROWS) * ROW_PITCH, cw - 2, ROW_H)
                     for i in range(count)]
        else:
            rects = [(x + 6, top + i * ROW_PITCH, w - 12, ROW_H) for i in range(count)]
        return rects + [(x + 6, y + h - 20, 84, BUTTON_H), (x + w - 90, y + h - 20, 84, BUTTON_H)]
    def draw_settings(self):
        ui = self.ui
        x, y, w, h = self.settings_panel()
        ui.panel(x, y, w, h)
        ui.hline(x + 2, x + w - 3, y + 4 + TAB_H, IRON)  # the tabs stand on this line
        for i, (name, rect) in enumerate(zip(TAB_NAMES, self.tab_rects())):
            ui.tab(*rect, name, active=i == self.settings_tab, hot=ui.mouse_in(*rect))
        rows, rects = self.setting_rows(), self.setting_rects()
        n = len(rows)
        for i, (row, rect) in enumerate(zip(rows, rects)):
            kind, name, value = row[:3]
            hot = i == self.menu_index
            if kind == "slider":
                ui.slider_row(*rect, name, value, row[5], hot=hot or self.dragging == i)
            elif kind == "key":
                ui.key_row(*rect, name, value, hot=hot, listening=self.binding == row[3])
            else:
                ui.setting_row(*rect, name, value, hot=hot)
        # One line under the settings: what the last change did, or what the chosen line is for
        if self.binding is not None:
            note, col = "Press the new key or mouse button (ESC: keep the old one)", TEXT_HOT
        elif self.settings_note:
            note, col = self.settings_note, TEXT_HOT
        elif self.menu_index < n:
            note, col = rows[self.menu_index][4], TEXT_DIM
        elif self.menu_index == n:
            note, col = "This tab's settings as they were at first", TEXT_DIM
        else:
            note, col = "Back to the menu", TEXT_DIM
        ui.center_text(y + h - 30, note, col, cx=x + w // 2)
        ui.button(*rects[n], "Defaults", hot=self.menu_index == n)
        ui.button(*rects[n + 1], "Done", hot=self.menu_index == n + 1)
        if y + h + 12 <= ui.height:
            ui.center_text(y + h + 5, "TAB: next tab   LEFT/RIGHT or a click: change   ESC: back", TEXT_DIM,
                           shadow=True)
