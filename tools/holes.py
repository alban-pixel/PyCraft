"""The hole test of the distant terrain: python tools/holes.py [seed] [lod] [render distance]

Every view of tools/views/<seed>.json is drawn twice, without a window, with the sky in magenta:
once as the game draws it, once with every side of the distant terrain's columns pulled down to
the bottom of the world. A pixel of sky in the first picture that the second one covers is a hole:
the sky showing through the terrain. Prints the holes of each view (a pixel or two on the outline of
a mountain is expected) and exits with 1 if there are more than `--allow` (default 4).
Defaults: seed 137206379, LOD quality low, render distance 256."""
import glob
import os
import subprocess
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "out")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    allow = int(next((a.split("=")[1] for a in sys.argv[1:] if a.startswith("--allow=")), 4))
    seed, lod, rd = (args + ["137206379", "low", "256"][len(args):])[:3]
    views = os.path.join(ROOT, "tools", "views", f"{seed}.json")
    if not os.path.exists(views):
        subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_views.py"), seed], check=True)
    tag = f"_holes_{seed}_{lod}_{rd}"
    env = dict(os.environ, WORLD_SEED=seed, LOD=lod, RD=rd, VIEWS=views, MASK="1")
    runs = [subprocess.Popen([sys.executable, os.path.join(ROOT, "tools", "render_views.py")],
                             env=dict(env, TAG=tag + suffix, **({"PATCH": "deep"} if suffix == "d" else {})))
            for suffix in ("n", "d")]
    for run in runs:
        run.wait()
    for suffix in ("n", "d"):
        with open(os.path.join(OUT, f"log{tag}{suffix}.txt")) as f:
            log = f.read()
        if "Traceback" in log or "done" not in log:
            print(log)
            sys.exit(2)
    total = 0
    for path in sorted(glob.glob(os.path.join(OUT, f"mask_*{tag}n.npy"))):
        name = os.path.basename(path)[5:-len(tag) - 5]
        normal, deep = np.load(path), np.load(os.path.join(OUT, f"mask_{name}{tag}d.npy"))
        holes = normal & ~deep
        total += int(holes.sum())
        ys, xs = np.nonzero(holes)
        where = f" around x {int(np.median(xs))} y {int(np.median(ys))}" if len(xs) else ""
        print(f"{name:12s} sky {normal.mean() * 100:5.1f}%  holes {int(holes.sum()):6d} px{where}")
    print(f"seed {seed}, LOD {lod}, render distance {rd}: {total} holes in all")
    sys.exit(1 if total > allow else 0)


if __name__ == "__main__":
    main()
