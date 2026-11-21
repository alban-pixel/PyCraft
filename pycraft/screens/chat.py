"""The command line: /tp, /time and /gamemode."""
import pyxel

from pycraft.survival import parse_gamemode
from pycraft.ui import AMBER, TEXT, TEXT_DIM


class Chat:
    """The App's chat line and its commands."""

    def update_chat(self):
        """The command line is open: the world and the clock go on, the player stands still."""
        self.play_time += self.dt
        self.time_of_day = (self.time_of_day + self.dt / (self.settings["day_length"] * 60)) % 1.0
        if pyxel.btnp(pyxel.KEY_ESCAPE):
            self.set_state("playing")
            return
        if pyxel.btnp(pyxel.KEY_RETURN):
            text, self.chat_text = self.chat_text, ""
            self.set_state("playing")
            self.run_command(text)
            return
        hold, repeat = self.frames(0.4), self.frames(0.05)
        if pyxel.btnp(pyxel.KEY_BACKSPACE, hold=hold, repeat=repeat):
            self.chat_text = self.chat_text[:-1]
        for i in range(26):
            if pyxel.btnp(pyxel.KEY_A + i, hold=hold, repeat=repeat):
                self.chat_text += chr(ord("a") + i)
        for i in range(10):
            if pyxel.btnp(pyxel.KEY_0 + i, hold=hold, repeat=repeat):
                self.chat_text += str(i)
        for key, char in ((pyxel.KEY_SPACE, " "), (pyxel.KEY_MINUS, "-"), (pyxel.KEY_SLASH, "/"),
                          (pyxel.KEY_PERIOD, ".")):
            if pyxel.btnp(key, hold=hold, repeat=repeat):
                self.chat_text += char
        self.chat_text = self.chat_text[:64]
    def run_command(self, text):
        parts = text.strip().split()
        if not parts:
            return
        cmd = parts[0].lstrip("/").lower()
        if cmd == "tp":
            try:
                if len(parts) != 4:
                    raise ValueError
                coords = [float(v) if v != "~" else self.player.pos[i] for i, v in enumerate(parts[1:])]
            except ValueError:
                self.notify("Usage: /tp x y z")
                return
            self.player.pos = coords
            self.player.vel_y = 0.0
            self.notify(f"Teleported to {coords[0]:.0f} {coords[1]:.0f} {coords[2]:.0f}")
        elif cmd == "time" and len(parts) == 3 and parts[1] == "set":
            named = {"sunrise": 0.0, "day": 0.05, "noon": 0.25, "sunset": 0.5, "night": 0.6,
                     "midnight": 0.75}
            v = parts[2].lower()
            try:
                t = named[v] if v in named else float(v)
            except (KeyError, ValueError):
                self.notify("Usage: /time set day|noon|sunset|night|<0-1>")
                return
            self.time_of_day = (t / 24000 if t > 1 else t) % 1.0
            self.notify(f"Time set to {self.time_of_day * 24 % 24:.0f}:00")
        elif cmd == "gamemode":
            mode = parse_gamemode(parts[1]) if len(parts) == 2 else None
            if mode is None:
                self.notify("Usage: /gamemode survival|creative")
                return
            self.set_mode(mode)
        else:
            self.notify(f"Unknown command: {parts[0]}  (/tp x y z, /time set ..., /gamemode ...)")
    def draw_chat(self):
        ui = self.ui
        y = self.hotbar_rects()[0][1] - 19
        ui.text(4, y - 9, "ENTER run  ESC cancel  /tp x y z  /time set day|night  /gamemode s|c", TEXT_DIM, shadow=True)
        ui.glass(2, y - 1, ui.width - 4, 12, 0.85)
        ui.rect(2, y - 1, 2, 12, AMBER)
        cursor = "_" if self.play_time % 1.0 < 0.6 else ""
        ui.text(8, y + 2, "> " + self.chat_text + cursor, TEXT)
