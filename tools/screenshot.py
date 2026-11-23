"""A screenshot of a world, without a window: the reach of 60 km, the wait, Renderer.capture, then
the game's own frames again. Env: RES (1280x720), RD (64), LOD (medium), WORLD_SEED. Writes
tools/out/screenshot.png and tools/out/screenshot.txt; exits with 1 if a check fails."""
import multiprocessing
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the repository
OUT = os.path.join(ROOT, "tools", "out")  # what the checks write (not in Git)
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, ROOT); os.chdir(ROOT)


def save_frame(app, name):
    """The game's frame as Pyxel shows it (palette colors)."""
    import pyxel
    from pycraft.screenshot import write_png
    pal = np.array([((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in pyxel.colors[:256]], np.uint8)
    write_png(os.path.join(OUT, name), pal[app.screen])


def frame(app):
    app.dt = 0
    app.update()
    app.draw_world()


if __name__ == "__main__":
    failed = []
    log = open(os.path.join(OUT, "screenshot.txt"), "w")

    def say(*a):
        print(*a, file=log, flush=True)
        print(*a, flush=True)

    try:
        import random
        random.seed(7)
        from pycraft.app import App
        from pycraft.render.constants import SCREENSHOT_REACH, SCREENSHOT_SIZE, SCREENSHOT_WAIT
        from pycraft.screenshot import fit_size, write_png
        from pycraft.settings import parse_settings
        from pycraft.world import World

        app = App(headless=True)
        app.save_path = os.path.join(OUT, "world_shot_%d.npz" % os.getpid())  # never the real save
        app.settings_path = os.path.join(OUT, "settings_shot_%d.json" % os.getpid())
        app.settings = parse_settings({})  # the game's own settings, not the player's
        app.settings["music_volume"] = app.settings["sound_volume"] = 0
        w, h = map(int, os.environ.get("RES", "1280x720").split("x"))
        s = app.settings
        s["resolution"], s["fancy"], s["render_scale"] = (w, h), True, 1.0
        s["render_distance"], s["lod_quality"] = int(os.environ.get("RD", "64")), os.environ.get("LOD", "medium")
        r = app.renderer
        r.render_distance = s["render_distance"]
        r.set_lod_quality(s["lod_quality"])
        r.set_fancy(True)
        app.set_resolution(w, h)
        app.apply_render_scale()
        if os.environ.get("WORLD_SEED"):
            app.world = World(seed=int(os.environ["WORLD_SEED"]))
            r.set_world(app.world)
            app.spawn = app.world.find_spawn()
        app.world_is_fresh = True
        app.start_game(new_world=True)
        t0 = time.perf_counter()
        while app.state == "loading" and time.perf_counter() - t0 < 120:
            app.dt = 1 / 60
            app.update()
            app.draw()
        app.show_help = False
        p = app.player
        p.flying = True
        p.pos = [app.spawn[0], app.spawn[1] + 120, app.spawn[2]]
        p.yaw, p.pitch = 30.0, -8.0
        app.time_of_day = 0.2
        for _ in range(10):
            frame(app)
        before = (r.size, r.scene_size, r.far.n_levels, r.sim_distance)
        save_frame(app, "screenshot_game.png")  # the game's own frame, to compare
        say("before", before)

        r.set_reach(SCREENSHOT_REACH)
        t0 = time.perf_counter()
        while r.reach_progress(p.eye()) < 1 and time.perf_counter() - t0 < SCREENSHOT_WAIT:
            frame(app)
            time.sleep(0.01)  # (lets the sampler and the workers run)
        say(f"waited {time.perf_counter() - t0:.1f} s, progress {r.reach_progress(p.eye()):.3f}, "
            f"levels {r.far.levels()} of {r.far.n_levels}, blocks radius {r.sim_distance}")
        t0 = time.perf_counter()
        rgb = r.capture(*app.camera())
        say(f"capture took {time.perf_counter() - t0:.1f} s")
        write_png(os.path.join(OUT, "screenshot.png"), rgb)
        r.set_reach(None)
        for _ in range(30):
            frame(app)
        after = (r.size, r.scene_size, r.far.n_levels, r.sim_distance)
        say("after", after)

        with r.ctx:
            limit = r.ctx.info["GL_MAX_TEXTURE_SIZE"], tuple(r.ctx.info["GL_MAX_VIEWPORT_DIMS"])
        width, height = fit_size(SCREENSHOT_SIZE, *limit)
        if rgb.shape != (height, width, 3):
            failed.append(f"picture is {rgb.shape}, not {(height, width, 3)}")
        colors = len(np.unique(rgb.reshape(-1, 3)[::7], axis=0))
        say("distinct colors (1 pixel in 7):", colors)
        if colors < 1000:
            failed.append(f"only {colors} colors")
        if after != before:
            failed.append(f"renderer not put back: {before} -> {after}")
        if len(np.unique(app.screen)) < 2:
            failed.append("the frame after the capture is one color")
    except Exception:
        import traceback
        say(traceback.format_exc())
        failed.append("crashed")
    finally:
        say("FAILED: " + "; ".join(failed) if failed else "ok")
        log.close()
        for child in multiprocessing.active_children():
            child.terminate()
        os._exit(1 if failed else 0)
