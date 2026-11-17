"""Play the game in a real window with scripted keys: load a new world, walk, sprint, jump, place
and break blocks, fly, fly fast, open the menus, change settings, teleport, go back to the title
and continue. The real mouse, keyboard, save file and settings file are never touched: the game
reads its input from a stand-in for the pyxel module, and its data folder is a scratch folder.

It opens a real window for a minute or two, with a copy of the player's own settings.
env: TAG, LOD (override the LOD quality), RD (override the render distance), RES (default 1280x720).
Writes tools/out/play<TAG>.txt and pictures of some moments.
"""
import json, multiprocessing, os, statistics, sys, time, traceback
import numpy as np
TAG = os.environ.get("TAG", "")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the repository
OUT = os.path.join(ROOT, "tools", "out")  # what the checks write (not in Git)
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, ROOT); os.chdir(ROOT)
DATA = os.path.join(OUT, "play_data" + TAG)


class FakePyxel:
    """The pyxel module, with the keyboard and the mouse replaced by the script's."""

    def __init__(self, real):
        self.real, self.held, self.pressed = real, set(), set()
        self.mouse_wheel = 0

    def __getattr__(self, name):
        return getattr(self.real, name)

    @property
    def mouse_x(self):
        return self.real.width // 2

    @property
    def mouse_y(self):
        return self.real.height // 2

    def btn(self, key):
        return key in self.held

    def btnp(self, key, hold=0, repeat=0):
        return key in self.pressed

    def btnr(self, key):
        return False

    def set_mouse_pos(self, x, y):
        pass

    def user_data_dir(self, vendor, app):
        """A scratch folder, with a copy of the player's settings: silent, in a window of a known size."""
        settings = {}
        try:
            with open(os.path.join(self.real.user_data_dir(vendor, app), "settings.json")) as f:
                settings = json.load(f)
        except (OSError, ValueError):
            pass
        settings["music"] = False
        settings["resolution"] = [int(v) for v in os.environ.get("RES", "1280x720").split("x")]
        if os.environ.get("LOD"):
            settings["lod_quality"] = os.environ["LOD"]
        if os.environ.get("RD"):
            settings["render_distance"] = int(os.environ["RD"])
        with open(os.path.join(DATA, "settings.json"), "w") as f:
            json.dump(settings, f)
        return DATA + os.sep


if __name__ == "__main__":
    import pyxel as real_pyxel
    from PIL import Image
    log = open(os.path.join(OUT, f"play{TAG}.txt"), "w")

    def say(*a):
        print(*a, file=log, flush=True)
        print(*a, flush=True)

    try:
        # The player's own settings, copied: silent, and in a window of a known size
        os.makedirs(DATA, exist_ok=True)
        for name in os.listdir(DATA):
            if os.path.isfile(os.path.join(DATA, name)):
                os.remove(os.path.join(DATA, name))
        from pycraft import app as main, controls, ui
        fake = FakePyxel(real_pyxel)
        main.pyxel = ui.pyxel = controls.pyxel = fake
        main.App.sfx = lambda self, sound: None
        K = real_pyxel
        app = main.App()
        assert app.save_path.startswith(DATA) and app.settings_path.startswith(DATA), (app.save_path, app.settings_path)
        r = app.renderer
        say("settings", app.settings)

        clock = {"game": 0.0, "frames": 0}
        times = []  # the work of each frame of the current phase, in seconds

        def frame(held=(), pressed=()):
            """One frame of the game, paced like App.run."""
            fake.held, fake.pressed = set(held), set(pressed)
            now = time.perf_counter()
            app.dt = min(now - frame.last, main.MAX_DT)
            frame.last = now
            app.update()
            app.draw()
            work = time.perf_counter() - now
            app.frame_done(work)
            times.append(work)
            clock["game"] += app.dt
            clock["frames"] += 1
            wait = 1 / app.settings["fps"] - (time.perf_counter() - now)
            if wait > 0:
                time.sleep(wait)
            real_pyxel.flip()
        frame.last = time.perf_counter()

        def hold(seconds, held=(), each=None):
            end = clock["game"] + seconds
            while clock["game"] < end:
                frame(held)
                if each:
                    each()

        def press(*keys):
            frame(pressed=keys)

        def until(test, limit=6000, held=()):
            start, n = time.perf_counter(), 0
            while not test() and n < limit:
                frame(held)
                n += 1
            return time.perf_counter() - start, test()

        def shot(name):
            w, h = real_pyxel.width, real_pyxel.height
            idx = np.frombuffer(real_pyxel.screen.data_ptr(), np.uint8, count=w * h).reshape(h, w)
            pal = np.array([((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in real_pyxel.colors[:256]], np.uint8)
            Image.fromarray(pal[idx]).save(os.path.join(OUT, f"play{TAG}_{name}.png"))

        def phase(name):
            if times:
                ms = sorted(t * 1000 for t in times)
                say(f"  {len(ms)} frames: median {statistics.median(ms):.1f} ms, 95% {ms[int(len(ms) * 0.95)]:.1f} ms, "
                    f"worst {ms[-1]:.1f} ms; GPU {(r.gpu_time or 0) * 1000:.1f} ms, 3D at {r.scene_size}, "
                    f"levels shown {r.far.shown} of {r.far.levels()}, chunks {len(r.chunks.meshes)}, "
                    f"pos {[round(v) for v in app.player.pos] if getattr(app, 'player', None) else None}")
            times.clear()
            say(name)

        def complete():
            return r.far.progress() == 1 and r.far.shown == (0, r.far.levels() - 1)

        phase("title screen, 2 s")
        hold(2)
        shot("title")

        phase("new world")
        app.state = "generating"
        t, ok = until(lambda: app.state == "playing")
        say(f"  playing after {t:.1f} s ({ok}), seed {app.world.seed}, mouse captured {app.mouse_captured}")
        press(K.KEY_F3)
        hold(1)
        shot("start")

        phase("walk, turn, sprint and jump, 6 s")
        hold(2, [K.KEY_W])
        hold(1, [K.KEY_W, K.KEY_LEFT])
        hold(3, [K.KEY_W, K.KEY_LCTRL, K.KEY_SPACE])

        phase("place 5 blocks and break them")
        app.player.pitch = -45.0  # (degrees)
        hold(0.5)
        say('  aiming at', app.target)
        placed = []
        for i in range(5):
            before = app.target
            press(K.MOUSE_BUTTON_RIGHT)
            placed.append(before[1] if before else None)
            hold(0.2)
        say("  placed at", placed, "blocks there:", [app.world.get(*p) if p else None for p in placed])
        hold(1.5)
        shot("placed")
        for i in range(5):
            press(K.MOUSE_BUTTON_LEFT)
            hold(0.2)
        say("  after breaking:", [app.world.get(*p) if p else None for p in placed])
        app.player.pitch = 0.0

        phase("fly up, 4 s")
        press(K.KEY_F)
        hold(4, [K.KEY_SPACE])
        say(f"  flying {app.player.flying}")

        phase("fly fast straight, 10 s")
        low = [99]

        def watch():
            first, last = r.far.shown
            low[0] = min(low[0], last - first + 1)
        hold(10, [K.KEY_W, K.KEY_LCTRL], watch)
        say(f"  fewest levels drawn {low[0]}")
        shot("flight")

        phase("fly fast while turning, 10 s")
        low = [99]
        hold(10, [K.KEY_W, K.KEY_LCTRL, K.KEY_LEFT], watch)
        say(f"  fewest levels drawn {low[0]}")

        phase("stop: wait for the distant terrain")
        t, ok = until(complete)
        say(f"  complete after {t:.1f} s ({ok})")
        shot("stopped")

        phase("inventory, pause, chat")
        press(K.KEY_E); hold(0.5); say("  state", app.state); press(K.KEY_E)
        press(K.KEY_ESCAPE); hold(0.5); say("  state", app.state); press(K.KEY_ESCAPE)
        press(K.KEY_T); hold(0.3); say("  state", app.state); press(K.KEY_ESCAPE)
        hold(0.3); say("  state", app.state)

        phase("next LOD quality, and back")
        for step in (1, -1):
            app.cycle("lod_quality", main.LOD_QUALITY_NAMES, step)
            t, ok = until(complete)
            say(f"  {app.settings['lod_quality']}: complete after {t:.1f} s ({ok})")

        phase("next render distance, and back")
        for step in (1, -1):
            app.cycle("render_distance", main.RENDER_DISTANCES, step)
            hold(2)
            say(f"  {app.settings['render_distance']}: chunks {len(r.chunks.meshes)}")

        phase("teleport 6 km away")
        x, y, z = app.player.pos
        app.run_command(f"/tp {x + 4000:.0f} {max(y, 1400):.0f} {z + 4500:.0f}")
        hold(0.3)  # (the grids notice the jump)
        say('  just after the jump: levels shown', r.far.shown)
        t, ok = until(complete)
        say(f"  distant terrain complete after {t:.1f} s ({ok})")
        hold(2)
        shot("teleport")

        phase("sunset and night")
        app.run_command("/time set sunset"); hold(1.5); shot("sunset")
        app.run_command("/time set night"); hold(1.5)
        app.run_command("/time set day")

        phase("save, title, continue")
        app.save_and_title()
        hold(1.5)
        say("  state", app.state, "save file:", os.path.exists(app.save_path))
        app.start_game(new_world=False)
        t, ok = until(lambda: app.state == "playing")
        say(f"  playing again after {t:.1f} s ({ok})")
        hold(2)
        shot("continue")
        phase("end")
        say("children alive:", sum(c.is_alive() for c in multiprocessing.active_children()))
        say("done")
    except BaseException:
        say(traceback.format_exc())
    finally:
        for child in multiprocessing.active_children():
            child.terminate()
        log.close()
        os._exit(0)
