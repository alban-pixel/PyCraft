"""Measures how logical the biome map of the usual world is (not the Earth's), and draws it.

    python tools/biomes.py [seed ...]     the map and the measures of each seed (default: the seeds
                                          of tools/views/), against tools/biomes_baseline.json
    python tools/biomes.py --baseline     writes the measures of the default seeds to that file

Options: --size BLOCKS (side of the square around 0, 0; default 49152), --step BLOCKS (between two
points; default 48). Each measure has a goal (GOALS); the tests in tests/test_biomes.py hold the
generator to the same goals. The maps go to tools/out/biomes_<seed>.png."""
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pycraft import terrain as T  # noqa: E402

OUT = os.path.join(ROOT, "tools", "out")
BASELINE = os.path.join(ROOT, "tools", "biomes_baseline.json")
SIZE, STEP = 49152, 48

OCEANS = (T.OCEAN, T.DEEP_OCEAN, T.FROZEN_OCEAN)
SNOWY = (T.SNOWY_TAIGA, T.SNOWY_TUNDRA, T.SNOWY_PEAKS, T.GLACIER)  # ground under snow or ice
HOT = (T.DESERT, T.BADLANDS, T.SAVANNA, T.JUNGLE)
DRY = (T.DESERT, T.BADLANDS)
LOWLAND_SNOW = (T.SNOWY_TAIGA, T.SNOWY_TUNDRA)  # (snow on a mountain may rise above a hot plain)
COLD_COAST = (T.TAIGA, T.SNOWY_TAIGA, T.SNOWY_TUNDRA, T.SNOWY_PEAKS, T.GLACIER, T.ALPINE, T.ROCKY)

# name: (what it measures, "<=" or ">=", goal, the step of the plan that should reach it)
GOALS = {
    "humidity_vs_coast": ("correlation of the humidity with the distance to the sea, on land", "<=", -0.3, 2),
    "snow_near_hot": ("share of the snowy lowland (snowy taiga, tundra) less than 1500 blocks from a hot "
                      "biome", "<=", 0.01, 3),
    "hot_touches_snow": ("borders between a hot biome and a snowy one", "<=", 0, 2),
    "snowy_share": ("share of the land under snow or ice", "<=", 0.25, 3),
    "dry_share": ("share of the land that is desert or badlands", ">=", 0.04, 2),
    "ice_off_cold_coast": ("share of the frozen ocean in ice fields that touch no cold coast", "<=", 0.05, 2),
    "snow_line_conflict": ("share of the land on the wrong side of the best single snow line "
                           "(snow where it is warmer than snowless ground)", "<=", 0.02, 3),
    "beach_inland": ("share of the beach more than 64 blocks from the sea", "<=", 0.05, 4),
    "swamp_high": ("share of the swamp more than 8 blocks above the sea", "<=", 0.05, 4),
    "terraces_outside_badlands": ("share of the land with badlands terraces that is not badlands", "<=", 0.1, 5),
    "specks": ("share of the land in a patch smaller than two points (no neighbor of its biome; "
               "beaches aside)", "<=", 0.002, 6),
}


def sample_grid(gen, size=SIZE, step=STEP, center=(0, 0)):
    """The terrain every `step` blocks on a square of `size` blocks: a dict of 2D arrays [x, z]."""
    n = size // step
    xs = (np.arange(n) - n // 2) * step
    x, z = np.meshgrid(xs + float(center[0]), xs + float(center[1]), indexing="ij")
    keys = ("biome", "height", "temperature", "humidity", "water", "river", "terraces")
    out = {k: [] for k in keys}
    start = time.perf_counter()
    for i in range(0, n, 64):
        s = gen.sample(x[i:i + 64], z[i:i + 64])
        for k in keys:
            out[k].append(s[k])
    grid = {k: np.concatenate(v) for k, v in out.items()}
    grid["sample_us"] = (time.perf_counter() - start) / x.size * 1e6
    grid["top"] = np.floor(grid["height"]) - T.SEA_LEVEL
    grid["step"] = step
    return grid


def grow(mask, cells):
    """mask, widened by `cells` points in every direction (a square)."""
    out = mask.copy()
    for _ in range(int(cells)):
        wide = out.copy()
        wide[1:] |= out[:-1]
        wide[:-1] |= out[1:]
        wide[:, 1:] |= wide[:, :-1].copy()
        wide[:, :-1] |= wide[:, 1:].copy()
        out = wide
    return out


def flood(mask, seeds):
    """The points of mask connected (through mask) to the seeds."""
    reach = seeds & mask
    while True:
        more = grow(reach, 8) & mask
        for _ in range(8):  # (8 steps at a time, then the exact edge)
            more = grow(more, 1) & mask
        if (more == reach).all():
            return reach
        reach = more


def distance(mask, cap):
    """Points to the nearest point of mask (in squares), up to cap."""
    dist = np.full(mask.shape, cap, np.int32)
    reached = mask.copy()
    dist[reached] = 0
    for d in range(1, cap):
        wide = grow(reached, 1)
        new = wide & ~reached
        if not new.any():
            break
        dist[new] = d
        reached = wide
    return dist


def measures(grid):
    """The measures of GOALS (and a few more) for a sampled grid."""
    b, top, step = grid["biome"], grid["top"], grid["step"]
    # The sea: the ocean biomes, and the shallow water at sea level by the shore (land biomes, as the
    # generator calls the first block of depth)
    ocean = np.isin(b, OCEANS) | ((grid["water"] == T.SEA_LEVEL) & (top < 0))
    land = ~ocean
    snowy = np.isin(b, SNOWY) & land
    hot = np.isin(b, HOT)
    n_land = max(land.sum(), 1)
    m = {}

    far = distance(ocean, cap=int(16000 / step))
    m["humidity_vs_coast"] = float(np.corrcoef(grid["humidity"][land], far[land])[0, 1])
    low_snow = np.isin(b, LOWLAND_SNOW)
    m["snow_near_hot"] = float((low_snow & grow(hot, round(1500 / step))).sum() / max(low_snow.sum(), 1))
    touch = 0
    for a, c in ((b[1:], b[:-1]), (b[:, 1:], b[:, :-1])):
        pa, pc = np.isin(a, HOT), np.isin(c, SNOWY)
        qa, qc = np.isin(a, SNOWY), np.isin(c, HOT)
        touch += int(((pa & pc) | (qa & qc)).sum())
    m["hot_touches_snow"] = touch
    m["snowy_share"] = float(snowy.sum() / n_land)
    m["dry_share"] = float(np.isin(b, DRY).sum() / n_land)

    ice = b == T.FROZEN_OCEAN
    on_shore = ice & grow(np.isin(b, COLD_COAST), 1)
    m["ice_off_cold_coast"] = float((ice & ~flood(ice, on_shore)).sum() / max(ice.sum(), 1))

    # The best single snow line: the coldest k points of land under snow, the others bare. Count
    # the points that this gets wrong, for the best k
    t = grid["temperature"][land]
    s = snowy[land][np.argsort(t, kind="stable")]
    bare_below = np.concatenate([[0], np.cumsum(~s)])
    snow_above = s.sum() - np.concatenate([[0], np.cumsum(s)])
    m["snow_line_conflict"] = float((bare_below + snow_above).min() / max(len(s), 1))

    beach = b == T.BEACH
    m["beach_inland"] = float((beach & ~grow(ocean, max(1, round(64 / step)))).sum() / max(beach.sum(), 1))
    swamp = b == T.SWAMP
    m["swamp_high"] = float((swamp & (top > 8)).sum() / max(swamp.sum(), 1))
    terraced = (grid["terraces"] > 0.3) & land
    m["terraces_outside_badlands"] = float((terraced & (b != T.BADLANDS)).sum() / max(terraced.sum(), 1))

    alone = land & (b != T.BEACH)  # (a beach is a strip narrower than the grid, by design)
    alone[1:] &= b[1:] != b[:-1]
    alone[:-1] &= b[:-1] != b[1:]
    alone[:, 1:] &= b[:, 1:] != b[:, :-1]
    alone[:, :-1] &= b[:, :-1] != b[:, 1:]
    m["specks"] = float(alone.sum() / n_land)

    m["sample_us"] = float(grid["sample_us"])
    counts = np.bincount(b.ravel(), minlength=len(T.BIOME_NAMES))
    m["shares"] = {T.BIOME_NAMES[i]: round(float(c / b.size), 4) for i, c in enumerate(counts) if c}
    return m


def meets(name, value):
    _, op, goal, _ = GOALS[name]
    return value <= goal if op == "<=" else value >= goal


COLORS = {T.OCEAN: (40, 70, 160), T.DEEP_OCEAN: (20, 40, 110), T.FROZEN_OCEAN: (150, 170, 220),
          T.BEACH: (230, 220, 160), T.DESERT: (240, 200, 110), T.BADLANDS: (200, 100, 50),
          T.SAVANNA: (180, 170, 70), T.JUNGLE: (30, 140, 30), T.PLAINS: (130, 190, 90), T.FOREST: (50, 110, 50),
          T.BIRCH_FOREST: (110, 160, 90), T.SWAMP: (70, 90, 60), T.TAIGA: (40, 90, 80),
          T.SNOWY_TAIGA: (180, 210, 200), T.SNOWY_TUNDRA: (240, 245, 250), T.ALPINE: (140, 150, 120),
          T.SNOWY_PEAKS: (220, 220, 230), T.GLACIER: (170, 220, 240), T.ROCKY: (120, 120, 120)}


def draw(grid, path):
    """The biome map, north up, with the rivers and a legend of the biomes on it."""
    from PIL import Image, ImageDraw
    b = grid["biome"]
    img = np.zeros(b.shape + (3,), np.uint8)
    for biome, color in COLORS.items():
        img[b == biome] = color
    img[grid["river"]] = (60, 120, 220)
    im = Image.fromarray(img.transpose(1, 0, 2))
    d = ImageDraw.Draw(im)
    shown = [i for i in COLORS if (b == i).any()]
    d.rectangle([0, 0, 112, 6 + 12 * len(shown)], fill=(255, 255, 255))
    for row, biome in enumerate(shown):
        d.rectangle([4, 4 + row * 12, 14, 14 + row * 12], fill=COLORS[biome], outline=(0, 0, 0))
        d.text((18, 3 + row * 12), T.BIOME_NAMES[biome], fill=(0, 0, 0))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    im.save(path)


def default_seeds():
    names = os.listdir(os.path.join(ROOT, "tools", "views"))
    return sorted(int(n[:-5]) for n in names if n.endswith(".json") and n[:-5].isdigit())


def main(argv):
    size, step, seeds, write = SIZE, STEP, [], False
    args = iter(argv)
    for a in args:
        if a == "--size":
            size = int(next(args))
        elif a == "--step":
            step = int(next(args))
        elif a == "--baseline":
            write = True
        else:
            seeds.append(int(a))
    seeds = seeds or default_seeds()
    base = {}
    if os.path.exists(BASELINE):
        with open(BASELINE, encoding="utf-8") as f:
            saved = json.load(f)
        if (saved["size"], saved["step"]) == (size, step):
            base = saved["seeds"]
    results = {}
    for seed in seeds:
        grid = sample_grid(T.TerrainGenerator(seed), size, step)
        m = measures(grid)
        results[str(seed)] = m
        path = os.path.join(OUT, f"biomes_{seed}.png")
        draw(grid, path)
        old = base.get(str(seed), {})
        print(f"\nseed {seed}: {size} blocks square, a point every {step}; map: {os.path.relpath(path, ROOT)}")
        print(f"  {'measure':27s} {'goal':>9s} {'baseline':>9s} {'now':>9s}")
        for name, (_, op, goal, plan_step) in GOALS.items():
            was = f"{old[name]:9.3f}" if name in old else " " * 9
            mark = "ok" if meets(name, m[name]) else f"to do (step {plan_step})"
            print(f"  {name:27s} {op}{goal:7.3f} {was} {m[name]:9.3f}  {mark}")
        was = f"{old['sample_us']:9.2f}" if "sample_us" in old else " " * 9
        print(f"  {'sample_us (per column)':27s} {'':9s} {was} {m['sample_us']:9.2f}")
        print("  shares: " + ", ".join(f"{k} {v:.1%}" for k, v in sorted(m["shares"].items(), key=lambda kv: -kv[1])))
    if write:
        with open(BASELINE, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"size": size, "step": step, "seeds": results}, f, indent=1)
            f.write("\n")
        print(f"\nwrote {os.path.relpath(BASELINE, ROOT)}")
    missed = sum(not meets(n, results[s][n]) for s in results for n in GOALS)
    print(f"\n{missed} of {len(GOALS) * len(results)} goals not met")


if __name__ == "__main__":
    main(sys.argv[1:])
