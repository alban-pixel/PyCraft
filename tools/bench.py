"""Frame and graphics card times in 8 fixed views around the spawn, without a window.
Env: TAG, RES (2560x1440), RD (64), LOD (medium), FANCY (0), WORLD_SEED (137206379),
PROF (1: time the distant terrain's pass alone). Writes tools/out/bench<TAG>.txt."""
import multiprocessing, os, sys, time
import numpy as np
TAG = os.environ.get("TAG", "")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the repository
OUT = os.path.join(ROOT, "tools", "out")  # what the checks write (not in Git)
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, ROOT); os.chdir(ROOT)


def far_busy(far):
    if hasattr(far, "working"):
        return far.working or far.pending or far.edits or far.progress() < 1
    return bool(far.queue) or far.sampling is not None or any(far.dirty) or None in far.origins


def settle(app, frames=20000):
    r = app.renderer
    t0, calm = time.perf_counter(), 0
    for _ in range(frames):
        app.dt = 0
        app.update()
        app.draw_world()
        time.sleep(0.02)  # (the old game's sampler thread needs the game's thread to let go)
        ch = r.chunks
        busy = ch.progress(app.player.eye(), r.sim_distance) < 1 or ch.pending or ch.preparing or far_busy(r.far)
        calm = 0 if busy else calm + 1
        if calm >= 10:
            break
    return time.perf_counter() - t0


if __name__ == "__main__":
    import random
    random.seed(7)
    from pycraft.app import App
    from pycraft.world import World
    log = open(os.path.join(OUT, "bench%s.txt" % TAG), "w")

    def say(*a):
        print(*a, file=log, flush=True)
        print(*a, flush=True)

    try:
        app = App(headless=True)
        app.save_path = os.path.join(OUT, "world_bench%s_%d.npz" % (TAG, os.getpid()))
        app.settings_path = os.path.join(OUT, "settings_bench%s_%d.json" % (TAG, os.getpid()))
        w, h = map(int, os.environ.get("RES", "2560x1440").split("x"))
        s = app.settings
        s["resolution"], s["fancy"] = (w, h), os.environ.get("FANCY", "0") == "1"
        s["render_distance"], s["lod_quality"] = int(os.environ.get("RD", "64")), os.environ.get("LOD", "medium")
        if "render_scale" in s:
            s["render_scale"] = 1.0
        r = app.renderer
        r.render_distance = s["render_distance"]
        r.set_lod_quality(s["lod_quality"])
        r.set_fancy(s["fancy"])
        app.set_resolution(w, h)
        if hasattr(app, "apply_render_scale"):
            app.apply_render_scale()
        app.world = World(seed=int(os.environ.get("WORLD_SEED", "137206379")))
        r.set_world(app.world)
        app.spawn = app.world.find_spawn()
        app.world_is_fresh = True
        t0 = time.perf_counter()
        app.start_game(new_world=True)
        while app.state == "loading":
            app.dt = 1 / 60
            app.update()
            app.draw()
        t_load = time.perf_counter() - t0
        t_full = t_load + settle(app)
        app.show_help = False
        app.time_of_day = 0.2
        say(f"{TAG}: {w}x{h} fancy={s['fancy']} rd={s['render_distance']} lod={s['lod_quality']}: "
            f"playing after {t_load:.1f} s, world complete after {t_full:.1f} s")
        prof = os.environ.get("PROF") == "1"
        q = None
        if prof:
            r.timer = None  # (timer queries can't nest)
            q = r.ctx.query(time=True)
            orig = r.far.render
            took = []

            def far_render(*a, **k):
                if k.get("shadow") or (len(a) > 3 and a[3]):
                    return orig(*a, **k)
                with q:
                    out = orig(*a, **k)
                took.append(1)
                return out
            r.far.render = far_render
        p = app.player
        p.flying = True
        all_ms, all_gpu = [], []
        for up, pitch in ((30, -10), (160, -22)):
            for yaw in (17, 107, 197, 287):
                p.pos = [app.spawn[0], app.spawn[1] + up, app.spawn[2]]
                p.yaw, p.pitch = float(yaw), float(pitch)
                settle(app, 400)
                ms, gpu = [], []
                end = time.perf_counter() + 2.5
                while time.perf_counter() < end:
                    t = time.perf_counter()
                    app.dt = 0
                    app.update()
                    app.draw()
                    ms.append((time.perf_counter() - t) * 1000)
                    if prof:
                        gpu.append(q.elapsed / 1e6)
                    elif r.gpu_time is not None:
                        gpu.append(r.gpu_time * 1000)
                ms, gpu = np.array(ms[3:]), np.array(gpu[3:])
                all_ms.append(np.median(ms))
                all_gpu.append(np.median(gpu))
                say(f"  up {up:3d} yaw {yaw:3d}: frame {np.median(ms):5.1f} ms ({1000 / np.median(ms):3.0f} FPS), "
                    f"{'distant terrain' if prof else 'GPU'} {np.median(gpu):5.1f} ms")
        say(f"{TAG}: mean of the views: frame {np.mean(all_ms):.1f} ms ({1000 / np.mean(all_ms):.0f} FPS), "
            f"{'distant terrain' if prof else 'GPU'} {np.mean(all_gpu):.1f} ms; worst view {np.max(all_ms):.1f} ms")
    except Exception:
        import traceback
        say(traceback.format_exc())
    finally:
        for child in multiprocessing.active_children():
            child.terminate()
        log.close()
        os._exit(0)
