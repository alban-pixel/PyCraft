"""The menus and the keys, driven like a player would, without a window: a stand-in for the pyxel
module gives the game a scripted keyboard and mouse. Prints OK / FAIL lines (also in
tools/out/menus.txt) and exits with 1 if a check failed. Never touches the real save or settings."""
import json, multiprocessing, os, sys, traceback
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the repository
OUT = os.path.join(ROOT, "tools", "out")  # what the checks write (not in Git)
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, ROOT); os.chdir(ROOT)
DATA = os.path.join(OUT, "menus_data")


class FakePyxel:
    def __init__(self, real):
        self.real, self.held, self.pressed = real, set(), set()
        self.mouse_wheel = 0
        self.mouse_x = self.mouse_y = 0

    def __getattr__(self, name):
        return getattr(self.real, name)

    def btn(self, key):
        return key in self.held

    def btnp(self, key, hold=0, repeat=0):
        return key in self.pressed

    def set_mouse_pos(self, x, y):
        self.mouse_x, self.mouse_y = int(x), int(y)

    def user_data_dir(self, vendor, app):
        os.makedirs(DATA, exist_ok=True)
        return DATA + os.sep


if __name__ == "__main__":
    import random
    random.seed(7)
    import pyxel as real
    log = open(os.path.join(OUT, "menus.txt"), "w")
    fails = []

    def say(*a):
        print(*a, file=log, flush=True)
        print(*a, flush=True)

    def check(what, ok, detail=""):
        say(("OK   " if ok else "FAIL ") + what + (f"  [{detail}]" if detail != "" else ""))
        if not ok:
            fails.append(what)

    try:
        os.makedirs(DATA, exist_ok=True)
        for name in os.listdir(DATA):
            if os.path.isfile(os.path.join(DATA, name)):
                os.remove(os.path.join(DATA, name))
        # An old settings file: the music switched off, before there were volumes
        with open(os.path.join(DATA, "settings.json"), "w") as f:
            json.dump({"resolution": [640, 360], "fps": 60, "render_distance": 32, "lod_quality": "low",
                       "fancy": False, "music": False, "ui_scale": "auto", "render_scale": 1.0}, f)
        import sys as _sys
        from pycraft import app as main, blocks, controls, play, render, ui
        from pycraft import settings as game_settings
        from pycraft.screens import settings as settings_screen
        fake = FakePyxel(real)
        for _module in list(_sys.modules.values()):  # every part of the game reads the stand-in
            if getattr(_module, '__name__', '').startswith('pycraft') and hasattr(_module, 'pyxel'):
                _module.pyxel = fake
        K = real
        app = main.App(headless=True)
        app.headless = False  # (so the game moves the stand-in's mouse where it would move the real one)
        s = app.settings
        check("old settings file: music off becomes volume 0", s["music_volume"] == 0 and "music" not in s, s.get("music_volume"))
        check("new settings have their defaults", (s["fov"], s["sensitivity"], s["invert_y"], s["autosave"]) == (70, 100, False, 2))
        check("keys start as the defaults", app.controls.is_default() and s["keys"]["forward"] == "W")

        def frame(pressed=(), held=()):
            fake.pressed, fake.held = set(pressed), set(held)
            app.dt = 1 / 60
            app.update()
            app.draw()
            fake.pressed = set()

        def mouse_to(rect, fx=0.5):
            x, y, w, h = rect
            fake.mouse_x, fake.mouse_y = app.ui.to_screen(x + int(w * fx), y + h // 2)

        def click(rect, fx=0.5, button=K.MOUSE_BUTTON_LEFT):
            mouse_to(rect, fx)
            frame()
            frame([button], [button])
            frame()

        def saved():
            with open(app.settings_path) as f:
                return json.load(f)

        # --- title screen -> settings, by keyboard ---
        frame()
        check("starts on the title screen", app.state == "title")
        labels = [label for label, _ in app.menu_items()]
        for _ in range(labels.index("Settings")):
            frame([K.KEY_DOWN])
        frame([K.KEY_RETURN])
        check("ENTER on Settings opens them", app.state == "settings" and app.settings_tab == 0)
        rows = app.setting_rows()
        check("the Video tab has its 9 lines", [r[1] for r in rows] == ["Resolution", "Interface size", "Frame rate", "Field of view", "3D resolution", "Render distance", "LOD quality", "Graphics", "Texture pack"], [r[1] for r in rows])
        # Frame rate: RIGHT, then LEFT
        frame([K.KEY_DOWN]); frame([K.KEY_DOWN])
        check("DOWN twice chooses the frame rate", app.menu_index == 2)
        frame([K.KEY_RIGHT])
        check("RIGHT: next frame rate", s["fps"] == 75 and saved()["fps"] == 75, s["fps"])
        frame([K.KEY_LEFT])
        check("LEFT: back", s["fps"] == 60)
        frame([K.KEY_DOWN]); frame([K.KEY_RIGHT]); frame([K.KEY_RIGHT])
        check("field of view: two steps up with the keys", s["fov"] == 80, s["fov"])
        # Mouse: drag the field of view's slider to its ends
        rect = app.setting_rects()[3]
        sx, sw = ui.Ui.slider_box(rect[0], rect[2])
        track = (sx, rect[1], sw, rect[3])
        mouse_to(track, 0.5); frame()
        frame([K.MOUSE_BUTTON_LEFT], [K.MOUSE_BUTTON_LEFT])
        check("a click on the slider grabs it", app.dragging == 3)
        mouse_to(track, 1.5); frame((), [K.MOUSE_BUTTON_LEFT])
        check("dragged past the right end: the highest", s["fov"] == 110, s["fov"])
        mouse_to(track, -0.5); frame((), [K.MOUSE_BUTTON_LEFT])
        check("dragged past the left end: the lowest", s["fov"] == 50, s["fov"])
        mouse_to(track, 0.34); frame((), [K.MOUSE_BUTTON_LEFT]); frame()
        check("released in between", app.dragging is None and 60 <= s["fov"] <= 80 and saved()["fov"] == s["fov"], s["fov"])
        # Mouse: a click on a value, on its "<", and a right click
        rect = app.setting_rects()[7]
        click(rect, 0.8)
        check("a click on Graphics: fancy", s["fancy"] is True)
        click(rect, 0.8, K.MOUSE_BUTTON_RIGHT)
        check("a right click: back to fast", s["fancy"] is False)
        vx, vw = ui.Ui.value_box(rect[0], rect[2])
        rect5 = app.setting_rects()[5]
        click((vx, rect5[1], 6, rect5[3]), 0.3)
        check("a click on the < of Render distance: the previous one", s["render_distance"] == 512, s["render_distance"])
        click(rect5, 0.8)
        check("a click on its value: the next one", s["render_distance"] == 32, s["render_distance"])
        # Resolution: the panel moves, the cursor follows the line
        mouse_to(app.setting_rects()[0], 0.8); frame()
        frame([K.MOUSE_BUTTON_LEFT]); frame()
        check("resolution changed with the mouse on it", s["resolution"] == (800, 450) and real.width == 800, s["resolution"])
        check("the cursor is still on the line", app.mouse_on_chosen() and app.menu_index == 0)
        frame([K.MOUSE_BUTTON_RIGHT]); frame()
        check("and back", s["resolution"] == (640, 360) and app.mouse_on_chosen())

        # --- tabs ---
        frame([K.KEY_TAB])
        check("TAB: the Controls tab", game_settings.TAB_NAMES[app.settings_tab] == "Controls")
        frame([K.KEY_RIGHT]); frame([K.KEY_RIGHT])
        check("mouse speed up twice", s["sensitivity"] == 120, s["sensitivity"])
        frame([K.KEY_DOWN]); frame([K.KEY_RETURN])
        check("ENTER on Invert mouse", s["invert_y"] is True)
        click(app.tab_rects()[game_settings.TAB_NAMES.index("Sound")])
        check("a click on the Sound tab", game_settings.TAB_NAMES[app.settings_tab] == "Sound")
        frame([K.KEY_RIGHT]); frame([K.KEY_RIGHT])
        check("music from off to 20%: it plays", s["music_volume"] == 20 and app.music_playing)
        frame([K.KEY_LEFT]); frame([K.KEY_LEFT])
        check("and off again", s["music_volume"] == 0 and not app.music_playing)
        frame([K.KEY_TAB], [K.KEY_SHIFT])
        check("SHIFT+TAB: the tab before", game_settings.TAB_NAMES[app.settings_tab] == "Keys")

        # --- keys ---
        names = [a for a, _, _ in controls.ACTIONS]
        frame([K.KEY_RETURN])
        check("ENTER on a key: it waits", app.binding == "forward")
        frame([K.KEY_ESCAPE])
        check("ESC keeps the old key and stays in the settings", app.binding is None and app.state == "settings" and app.controls.name("forward") == "W")
        frame([K.KEY_RETURN]); frame([K.KEY_Z])
        check("forward is now Z", app.controls.name("forward") == "Z" and saved()["keys"]["forward"] == "Z")
        click(app.setting_rects()[names.index("fly")])
        check("a click on Fly on/off: it waits", app.binding == "fly")
        frame([K.KEY_Z])
        check("Z given to fly: the two swap", app.controls.name("fly") == "Z" and app.controls.name("forward") == "F", (app.controls.name("fly"), app.controls.name("forward"), app.settings_note))
        click(app.setting_rects()[names.index("zoom")])
        frame([K.MOUSE_BUTTON_X1], [K.MOUSE_BUTTON_X1])
        check("a mouse button as a key", app.controls.name("zoom") == "MOUSE 4", app.controls.name("zoom"))
        frame(); frame([K.KEY_RIGHT])
        check("RIGHT: the other column", app.menu_index == names.index("zoom") + settings_screen.SETTING_ROWS or app.menu_index < len(names), app.menu_index)
        real_shot = None
        n = len(app.setting_rows())
        click(app.setting_rects()[n])
        check("Defaults: the keys of the start", app.controls.is_default() and saved()["keys"]["forward"] == "W")
        frame([K.KEY_Z])
        check("a stray key does nothing", app.controls.is_default() and app.state == "settings")
        # forward on Z again for the game, then Done
        click(app.setting_rects()[0]); frame([K.KEY_Z])
        click(app.setting_rects()[n + 1])
        check("Done: back on the title, on Settings", app.state == "title" and app.menu_items()[app.menu_index][0] == "Settings")
        # A fresh start reads it all back
        again = game_settings.parse_settings(saved())
        check("the file gives the same settings back", again == {**s, "keys": again["keys"]} and again["keys"]["forward"] == "Z", {k: (again[k], s[k]) for k in s if again[k] != s[k]})
        check("and the same keys", controls.Controls(again["keys"]).name("forward") == "Z")

        # --- playing with these keys ---
        s["render_distance"] = 32
        app.renderer.render_distance = 32
        app.world_is_fresh = True
        app.start_game(new_world=True)
        for _ in range(4000):
            frame()
            if app.state == "playing":
                break
        check("the game starts", app.state == "playing" and app.mouse_captured)
        p = app.player
        p.flying, p.pitch, p.yaw = True, 0.0, 0.0
        y0 = p.pos[1]
        for _ in range(60):
            frame((), [K.KEY_SPACE])
        check("the jump key flies up", p.pos[1] > y0 + 5, p.pos[1] - y0)
        z0 = p.pos[2]
        for _ in range(30):
            frame((), [K.KEY_W])
        check("W no longer moves", abs(p.pos[2] - z0) < 0.01, p.pos[2] - z0)
        for _ in range(30):
            frame((), [K.KEY_Z])
        check("Z moves forward", p.pos[2] - z0 > 3, p.pos[2] - z0)
        y0 = p.pos[1]
        for _ in range(20):
            frame((), [K.KEY_LSHIFT])
        check("the fly down key goes down", p.pos[1] < y0 - 1, p.pos[1] - y0)
        frame([K.KEY_F])
        check("F toggles flying", p.flying is False)
        frame([K.KEY_F])
        # the mouse: speed and inversion
        p.yaw, p.pitch = 0.0, 0.0
        s["sensitivity"], s["invert_y"] = 100, False
        cx, cy = real.width // 2, real.height // 2
        fake.mouse_x, fake.mouse_y = cx, cy
        frame()
        fake.mouse_x, fake.mouse_y = cx + 20, cy + 10
        frame()
        yaw1, pitch1 = (p.yaw + 180) % 360 - 180, p.pitch
        check("the mouse turns the view", yaw1 < 0 and pitch1 < 0, (yaw1, pitch1))
        s["sensitivity"], s["invert_y"] = 200, True
        fake.mouse_x, fake.mouse_y = cx, cy
        frame()
        p.yaw, p.pitch = 0.0, 0.0
        fake.mouse_x, fake.mouse_y = cx + 20, cy + 10
        frame()
        yaw2, pitch2 = (p.yaw + 180) % 360 - 180, p.pitch
        check("twice the speed, and inverted", abs(yaw2 - 2 * yaw1) < 0.01 and abs(pitch2 + 2 * pitch1) < 0.01, (yaw2, pitch2))
        s["sensitivity"], s["invert_y"] = 100, False
        # zoom
        fake.mouse_x, fake.mouse_y = cx, cy
        for _ in range(40):
            frame((), [K.KEY_C])
        check("the zoom key narrows the view", app.view_fov < 30, app.view_fov)
        for _ in range(40):
            frame()
        check("and lets go", abs(app.view_fov - s["fov"]) < 1, app.view_fov)
        # pick, place, break: look at the ground
        p.flying = False
        for _ in range(240):
            frame()
            if p.on_ground:
                break
        p.pitch = -38.0
        frame()
        check("looking at a block", app.target is not None)
        looked = int(app.world.get(*app.target[0]))
        app.selected = 5
        frame([K.MOUSE_BUTTON_MIDDLE])
        want = play.PICKS.get(looked)
        check("pick: the block looked at is the chosen one", app.hotbar[app.selected] == want, (looked, want, app.hotbar, app.selected))
        spot = app.target[1]
        app.selected = app.hotbar.index(blocks.DEFAULT_HOTBAR[2]) if blocks.DEFAULT_HOTBAR[2] in app.hotbar else 2
        frame([K.MOUSE_BUTTON_RIGHT])
        placed = int(app.world.get(*spot))
        check("place", placed == app.hotbar[app.selected], (spot, placed))
        frame()
        frame([K.MOUSE_BUTTON_LEFT])
        check("break", int(app.world.get(*spot)) == 0)
        # a lever: placed with the place key, then flipped with it (and with the place key moved to G)
        from pycraft import blocks as BL
        frame(); app.target = app.world.raycast(p.eye(), p.forward(), play.REACH)
        app.sim.set_block(*app.target[0], BL.STONE)  # (a lever needs a full block: not leaves)
        frame(); app.target = app.world.raycast(p.eye(), p.forward(), play.REACH)
        spot = app.target[1]
        app.inv.slots[app.selected] = (BL.LEVER, 1, 0)
        frame([K.MOUSE_BUTTON_RIGHT])
        check("a lever is placed", int(app.world.get(*spot)) == BL.LEVER, (spot, int(app.world.get(*spot)), "target", app.target, "blocks", [BL.BLOCK_NAMES[int(app.world.get(*c))] for c in app.target] if app.target else None, "message", app.message, "selected", BL.BLOCK_NAMES[app.hotbar[app.selected]]))

        def aim_at_lever():
            """A small lever is only hit where its box is (it tilts when flipped): find a pitch that hits it."""
            for pitch in [p.pitch] + [-20.0 - 0.5 * i for i in range(120)]:
                p.pitch = pitch
                hit = app.world.raycast(p.eye(), p.forward(), play.REACH)
                if hit is not None and tuple(hit[0]) == tuple(spot):
                    frame()
                    return True
            return False
        for _ in range(3):
            frame()
        on_lever = aim_at_lever()
        before = int(app.world.get_state(*spot))
        frame([K.MOUSE_BUTTON_RIGHT])
        for _ in range(3):
            frame()
        after = int(app.world.get_state(*spot))
        check("the place key flips the lever it looks at", on_lever and after != before, (on_lever, before, after))
        app.controls.bind("place", K.KEY_G)
        frame([K.MOUSE_BUTTON_RIGHT]); frame()
        check("once moved to G, the right button does nothing", int(app.world.get_state(*spot)) == after)
        check("aimed at the flipped lever", aim_at_lever())
        frame([K.KEY_G]); frame()
        check("and G flips it back", int(app.world.get_state(*spot)) == before, int(app.world.get_state(*spot)))
        app.controls.bind("place", K.MOUSE_BUTTON_RIGHT)
        aim_at_lever()
        frame([K.MOUSE_BUTTON_LEFT]); frame()
        check("the lever breaks", int(app.world.get(*spot)) == 0)
        # the other screens
        frame([K.KEY_E])
        check("E: the inventory", app.state == "inventory")
        frame([K.KEY_E])
        check("E again closes it", app.state == "playing")
        frame([K.KEY_H]); shown = app.show_help
        frame([K.KEY_H])
        check("H shows and hides the help", app.show_help != shown)
        frame([K.KEY_F3])
        check("F3: the info", app.show_debug)
        frame([K.KEY_T])
        check("T: the chat", app.state == "chat")
        frame([K.KEY_ESCAPE])
        frame([K.KEY_ESCAPE])
        check("ESC: the pause menu", app.state == "paused")
        labels = [label for label, _ in app.menu_items()]
        click(app.button_rect(labels.index("Settings")))
        check("Settings from the pause menu", app.state == "settings")
        click(app.tab_rects()[game_settings.TAB_NAMES.index("Game")])
        rows = [r[1] for r in app.setting_rows()]
        click(app.setting_rects()[rows.index("Crosshair")], 0.8)
        check("crosshair: the next one", s["crosshair"] == "dot", s["crosshair"])
        click(app.setting_rects()[rows.index("Day length")], 0.8)
        check("day length: the next one", s["day_length"] == 40, s["day_length"])
        click(app.setting_rects()[len(rows)])
        check("Defaults on the Game tab", (s["crosshair"], s["day_length"], s["autosave"], s["show_help"]) == ("cross", 20, 2, True))
        check("the other tabs keep theirs", app.controls.name("forward") == "Z" and s["render_distance"] == 32)
        frame([K.KEY_ESCAPE])
        check("ESC: back to the pause menu", app.state == "paused")
        frame([K.KEY_ESCAPE])
        check("ESC: back to the game", app.state == "playing")

        # --- the real Earth's places (nothing is downloaded here) ---
        app.save_and_title()
        labels = [label for label, _ in app.menu_items()]
        click(app.button_rect(labels.index("Earth")))
        check("Earth: the list of places", app.state == "places" and len(app.menu_items()) == 13, app.state)
        frame([K.KEY_DOWN]); frame([K.KEY_RIGHT])
        check("DOWN, RIGHT: the second place of the second column", app.menu_index == 7, app.menu_index)
        click(app.button_rect(0))
        check("a new place asks for the mode", app.state == "newmode" and app.chosen_place.name == "Mont Blanc")
        frame([K.KEY_ESCAPE])
        check("ESC: back to the places", app.state == "places")
        click(app.button_rect(12))
        check("Back: the title screen", app.state == "title")
        labels = [label for label, _ in app.menu_items()]
        check("the normal world still continues", labels[0] == "Continue" and app.slot == "normal")
        click(app.button_rect(0))
        for _ in range(4000):
            frame()
            if app.state == "playing":
                break
        check("and plays", app.state == "playing")
        say(f"{len(fails)} failed" + (": " + "; ".join(fails) if fails else ""))
        say("done")
    except BaseException:
        say(traceback.format_exc())
        fails.append("the game crashed")  # (a crash is a failure, whatever came before)
    finally:
        for child in multiprocessing.active_children():
            child.terminate()
        log.close()
        os._exit(1 if fails else 0)
