"""Pictures of chosen views of a world, without a window, with debug versions of the shaders.
Used by holes.py; also useful alone. Env: TAG, RES (1280x720), RD (64), LOD (medium), FANCY (0),
WORLD_SEED, VIEWS (a json file of views, see make_views.py; a path from the repository's root), VARIANT (base | nofar | noblocks |
tag: each level of the distant terrain in its own color), PATCH (deep: every column side goes down
to the bottom of the world), MASK (1: the sky in magenta, no clouds, and a mask of the sky saved).
Writes tools/out/<view><TAG>.png (and mask_<view><TAG>.npy), and tools/out/log<TAG>.txt."""
import json
import math
import multiprocessing
import os
import sys
import time

import numpy as np

TAG = os.environ.get("TAG", "")
VARIANT = os.environ.get("VARIANT", "base")
SLEEP = float(os.environ.get("SLEEP", "0"))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the repository
OUT = os.path.join(ROOT, "tools", "out")  # what the checks write (not in Git)
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, ROOT); os.chdir(ROOT)

TAGC = ("const vec3 TAGC[8] = vec3[](vec3(1.0,0.15,0.15), vec3(1.0,0.6,0.1), vec3(1.0,1.0,0.2), vec3(0.2,1.0,0.2),"
        " vec3(0.2,1.0,1.0), vec3(0.2,0.4,1.0), vec3(0.8,0.2,1.0), vec3(1.0,1.0,1.0));\n")


def patch_shaders(R):
    patches = os.environ.get("PATCH", "").split(",")
    v = R.LOD_VERTEX_SHADER
    if "noband" in patches:  # sides never get the extra depth of the bands
        old = "if (band) y = min(neighbor, top) - spacing;"
        assert old in v
        v = v.replace(old, "if (false) y = top;")
    if "noclip" in patches:  # no culling against the view's planes
        old = "            keep = false;\n    }\n    if (!keep) {"
        assert old in v
        v = v.replace(old, "            keep = keep;\n    }\n    if (!keep) {")
    if "deep" in patches:  # every side goes all the way down
        old = "    vec3 pos = vec3(origin.x"
        assert old in v
        v = v.replace(old, "    if (in_pos.y < 0.5) y = 0.0;\n" + old)
    R.LOD_VERTEX_SHADER = v
    if os.environ.get("MASK"):  # the sky in pure magenta and no clouds: every other pixel is terrain
        old = "    out_color = vec4(mix(color, fog_color, sky_fog), 1.0);\n}"
        assert old in R.SKY_FRAGMENT_SHADER
        R.SKY_FRAGMENT_SHADER = R.SKY_FRAGMENT_SHADER.replace(old, "    out_color = vec4(1.0, 0.0, 1.0, 1.0);\n}")
        old = "    if ((near_pass == 1) != (length(v_pos.xz) < near_radius)) discard;"
        assert old in R.CLOUD_FRAGMENT_SHADER
        R.CLOUD_FRAGMENT_SHADER = R.CLOUD_FRAGMENT_SHADER.replace(old, "    discard;")
    if "tag" not in VARIANT:
        return
    # Distant terrain: one hue per level, sides darker; blocks: gray
    src = R.LOD_FRAGMENT_SHADER.replace("uniform int mode;", "uniform int mode;\nuniform int level;\n" + TAGC, 1)
    old = "    out_color = vec4(fog(shade_opaque(albedo, v_face, ao, direct), dist), 1.0);\n}"
    assert old in src
    R.LOD_FRAGMENT_SHADER = src.replace(
        old, "    out_color = vec4(TAGC[level] * (v_face == 2 ? 1.0 : 0.5) * (0.55 + 0.45 * ao), 1.0);\n}")
    src = R.BLOCK_FRAGMENT_SHADER
    old = "    if (mode == 0)  // (a lamp shows its own colors, day and night)"
    assert old in src
    R.BLOCK_FRAGMENT_SHADER = src.replace(
        old, "    albedo = vec3(dot(albedo, vec3(0.3, 0.6, 0.1)));\n" + old)


def settle(app, max_seconds=120.0):
    r = app.renderer
    t0 = time.perf_counter()
    calm = 0
    for _ in range(6000):  # (frames, not seconds: the PC may go to sleep in the middle of a run)
        app.dt = 0
        app.update()
        app.draw_world()
        if SLEEP:
            time.sleep(SLEEP)  # lets the sampler thread run (it starves beside a spinning game loop)
        ch, far = r.chunks, r.far
        busy = (ch.progress(app.player.eye(), r.sim_distance) < 1 or ch.pending or ch.preparing
                or far.working or far.pending or far.edits or far.progress() < 1)
        calm = 0 if busy else calm + 1
        if calm >= 16:
            break
        if os.environ.get("TRACE") and time.perf_counter() - settle.last > 1.0:
            settle.last = time.perf_counter()
            settle.say(f"  t={time.perf_counter() - t0:5.1f} blocks={ch.progress(app.player.eye(), r.sim_distance):.3f} "
                       f"working={far.working} pending={far.pending} landed={[o is not None for o in far.origins]} "
                       f"drawn={far.drawn_levels(app.player.eye())}")
    return time.perf_counter() - t0


settle.last = 0.0


def shot(name):
    import pyxel
    from PIL import Image
    w, h = pyxel.width, pyxel.height
    idx = np.frombuffer(pyxel.screen.data_ptr(), np.uint8, count=w * h).reshape(h, w)
    pal = np.array([((c >> 16) & 255, (c >> 8) & 255, c & 255) for c in pyxel.colors[:256]], np.uint8)
    Image.fromarray(pal[idx]).save(os.path.join(OUT, name))


if __name__ == "__main__":
    import random
    random.seed(7)
    from pycraft.render import shaders as R
    patch_shaders(R)
    from pycraft.app import App, parse_settings
    from pycraft.world import World

    log = open(os.path.join(OUT, "log%s.txt" % TAG), "w")

    def say(*a):
        print(*a, file=log, flush=True)

    settle.say = say
    try:
        app = App(headless=True)
        app.save_path = os.path.join(OUT, "world%s_%d.npz" % (TAG, os.getpid()))  # never the real save
        app.settings_path = os.path.join(OUT, "settings%s_%d.json" % (TAG, os.getpid()))
        # The game's own settings, not the player's: the same pictures on every computer
        app.settings = parse_settings({})
        if app.renderer.far.tiles is not app.default_tiles:
            app.apply_pack(None)
        w, h = map(int, os.environ.get("RES", "1280x720").split("x"))
        s = app.settings
        s["resolution"], s["fancy"] = (w, h), os.environ.get("FANCY", "0") == "1"
        s["render_distance"], s["lod_quality"] = int(os.environ.get("RD", "64")), os.environ.get("LOD", "medium")
        s["render_scale"] = 1.0
        r = app.renderer
        r.render_distance = s["render_distance"]
        r.set_lod_quality(s["lod_quality"])
        r.set_fancy(s["fancy"])
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
        say(f"loading took {time.perf_counter() - t0:.1f} s")
        say("seed", app.world.seed, "spawn", app.spawn, "settings", s, "variant", VARIANT)
        if "nofar" in VARIANT:
            r.far.render = lambda *a, **k: None
        if "noblocks" in VARIANT:
            r.chunks.render = lambda *a, **k: None
        views = json.load(open(os.path.join(ROOT, os.environ["VIEWS"]))) if os.environ.get("VIEWS") else [
            {"name": "spawn60", "rel": [0, 60, 0], "yaw": 20.0, "pitch": -12.0}]
        p = app.player
        p.flying = True
        for v in views:
            if "rel" in v:
                p.pos = [app.spawn[i] + v["rel"][i] for i in range(3)]
            else:
                p.pos = [float(c) for c in v["pos"]]
            if "look" in v:
                ex, ey, ez = p.eye()
                dx, dy, dz = v["look"][0] - ex, v["look"][1] - ey, v["look"][2] - ez
                p.yaw = math.degrees(math.atan2(dx, dz)) % 360
                p.pitch = math.degrees(math.atan2(dy, math.hypot(dx, dz)))
            else:
                p.yaw, p.pitch = float(v["yaw"]), float(v["pitch"])
            app.time_of_day = v.get("tod", 0.2)
            took = settle(app)
            for _ in range(6):
                app.dt = 0
                app.update()
                app.draw_world()
            shot("%s%s.png" % (v["name"], TAG))
            if os.environ.get("MASK"):
                with r.ctx:
                    sw, sh = r.scene_size
                    px = np.frombuffer(r.scene_texture.read(), np.float16).reshape(sh, sw, 4)[::-1]
                np.save(os.path.join(OUT, "mask_%s%s.npy" % (v["name"], TAG)),
                        (px[..., 0] > 0.9) & (px[..., 1] < 0.1) & (px[..., 2] > 0.9))
            say(f"{v['name']}: pos {[round(c, 1) for c in p.pos]} yaw {p.yaw:.1f} pitch {p.pitch:.1f} "
                f"settled in {took:.1f} s, drawn {r.drawn}, gpu {(r.gpu_time or 0) * 1000:.1f} ms, levels {r.far.levels()}")
        say("done")
    except Exception:
        import traceback
        say(traceback.format_exc())
    finally:
        for child in multiprocessing.active_children():
            child.terminate()
        log.close()
        os._exit(0)
