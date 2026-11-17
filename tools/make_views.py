"""make_views.py seed [out.json]: views around the spawn of a world and in front of its steepest
slopes, for render_views.py and holes.py (default: tools/views/<seed>.json)."""
import json, math, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the repository
OUT = os.path.join(ROOT, "tools", "out")  # what the checks write (not in Git)
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, ROOT); os.chdir(ROOT)
from pycraft.world import World
seed = int(sys.argv[1])
out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "tools", "views", f"{seed}.json")
world = World(seed)
spawn = world.find_spawn()
views = []
for up in (30, 160):
    for yaw in (0, 90, 180, 270):
        views.append({"name": f"s{up}_{yaw}", "pos": [spawn[0], spawn[1] + up, spawn[2]], "yaw": yaw + 17, "pitch": -10 if up == 30 else -22})
# The steepest slopes within 2.5 km: seen from 140 blocks downhill, a little above the ground there
step = 25
g = np.arange(-100, 101) * step
x, z = np.meshgrid(spawn[0] + g, spawn[2] + g, indexing="ij")
h = world.gen.sample(x, z)["height"]
gx, gz = np.gradient(h, step)
slope = np.hypot(gx, gz)
order = np.argsort(-slope.ravel())
picked = []
for i in order:
    ix, iz = divmod(int(i), slope.shape[1])
    if ix in (0, slope.shape[0] - 1) or iz in (0, slope.shape[1] - 1) or h[ix, iz] < 520:
        continue
    p = (float(x[ix, iz]), float(z[ix, iz]))
    if any(math.hypot(p[0] - q[0], p[1] - q[1]) < 500 for q in picked):
        continue
    picked.append(p)
    d = np.array([gx[ix, iz], gz[ix, iz]]) / slope[ix, iz]  # uphill
    for k, (back, side) in enumerate(((140, 0), (90, 110))):
        cx, cz = p[0] - d[0] * back - d[1] * side, p[1] - d[1] * back + d[0] * side
        ground = float(world.gen.sample(np.array([cx]), np.array([cz]))["height"][0])
        cy = max(ground, 512) + 25
        views.append({"name": f"steep{len(picked)}{'ab'[k]}", "pos": [cx, cy, cz], "look": [p[0], float(h[ix, iz]), p[1]]})
    if len(picked) >= 4:
        break
json.dump(views, open(out, "w"), indent=1)
print(seed, "spawn", [round(v, 1) for v in spawn], "steepest", [(round(p[0]), round(p[1])) for p in picked], "max slope", round(float(slope.max()), 1), len(views), "views")
