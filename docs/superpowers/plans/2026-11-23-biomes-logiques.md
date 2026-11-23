# Biomes logiques — plan

**Goal:** In the usual (procedural) world, every biome is where it makes sense: the climate follows
the land and the sea, one snow line holds everywhere, beaches are at the sea, swamps in wet
lowland, badlands terraces only in badlands, no specks. The Earth mode has its own rules
(`pycraft/earth/biomes.py`) and is out of scope.

**Measure:** `python tools/biomes.py` gives 11 measures for the four seeds of `tools/views/`, each
with a goal, against `tools/biomes_baseline.json` (the generator before this work).
`tests/test_biomes.py` checks the same goals on a 32 km square of seed 424242; the goals not met yet
are in its `NOT_YET` set, marked as expected failures. A step is done when its goals are met
and their names have left `NOT_YET`.

## What was wrong (baseline, four seeds)

| Measure | Goal | Baseline |
|---|---|---|
| `humidity_vs_coast`: correlation of humidity with the distance to the sea | ≤ −0.3 | −0.07 to +0.05: no link |
| `snow_near_hot`: snowy lowland within 1500 blocks of a hot biome | ≤ 1% | 15–25% |
| `snowy_share`: land under snow or ice | ≤ 25% | 24–28% |
| `dry_share`: desert and badlands | ≥ 4% | 3.7–6% |
| `ice_off_cold_coast`: frozen ocean whose ice field touches no cold coast | ≤ 5% | 0.1–7% |
| `snow_line_conflict`: land on the wrong side of the best single snow line | ≤ 2% | 8–11% |
| `beach_inland`: beach more than 64 blocks from the sea | ≤ 5% | 47–56% |
| `swamp_high`: swamp more than 8 blocks above the sea | ≤ 5% | 32–37% |
| `terraces_outside_badlands`: badlands terraces outside badlands | ≤ 10% | 27–35% |
| `specks`: land with no neighbor of its own biome (48-block grid) | ≤ 0.2% | 0.9% |
| `hot_touches_snow`: hot and snowy biomes side by side | 0 | 0 (keep it) |

Speed: `TerrainGenerator.sample()` takes about 3.2–4.3 µs a column. It must not grow by more than
about 15%: the distant terrain samples millions of columns.

## Steps

1. **Measure first** (done): `tools/biomes.py`, the baseline, `tests/test_biomes.py`.
   `sample()` also returns `terraces`, the strength of the badlands terracing.
2. **Climate with geography** (done). Humidity falls with the continentalness (inland) and behind
   mountain ranges (rain shadow, wind from −x), plus noise. Temperature zones twice as large
   (13600 instead of 6800 blocks) and 0.1 warmer. Only shallow sea freezes (by the coasts), and
   `sample()` returns that `ice` mask for the blocks and the distant terrain. Met on the four
   seeds: `humidity_vs_coast` (−0.55 to −0.63), `dry_share`, `ice_off_cold_coast` (0–0.1%);
   `snowy_share` on three. `sample()` is 3–4% slower. What is left of `snow_near_hot` (4–9%) and
   of `snowy_share` (26% on seed 137206379) is the "cold and dry" rule, which makes snowy tundra
   from −0.3 on dry mountains around 1000–1200 blocks up (about 95% of the snow near hot biomes):
   both goals move to step 3.
3. **One snow line** (done). Named climate lines in `terrain.py`, the same in the lowlands and the
   mountains: `CONIFERS` (−0.3), `SNOW_LINE` (−0.7: snow on the ground and ice on the water,
   everywhere), `TREE_LINE` (−1.05: tundra), `ICE_CAP` (−1.5: glaciers). `high` remains, but only
   picks the mountain form of a band (alpine meadow instead of taiga, snowy peaks instead of
   snowy taiga), never whether there is snow. The "cold and dry" snowy tundra at −0.3 became a cold
   steppe (plains). Met on the four seeds: `snow_line_conflict` 0 (was 8–11%), `snow_near_hot` 0
   (was 15–25%), `snowy_share` 14–20%. Snowy peaks grow (6–9% of the map), alpine meadows move
   about 300 blocks up.
4. **Landform biomes from the land.** Beaches from the distance to the coast (sand on flat shores,
   gravel or stone on steep ones, snow on cold ones); lake and river banks get their own sand,
   gravel and clay and are no longer "Beach"; swamps in flat, wet lowland by rivers and lakes, not
   under a height line. Goals: `beach_inland`, `swamp_high`.
5. **Terrain follows the biome.** Badlands terraces only where the final biome is badlands.
   Goal: `terraces_outside_badlands`.
6. **Borders.** Blend surface blocks and trees across a border; no specks. Goal: `specks`. The
   distant terrain uses the same `sample()`, so it follows.
7. **Old worlds.** The save records the generator's version; old worlds keep the old generator so
   that their new chunks don't leave seams. New worlds get the new one.
8. **Check.** `tools/biomes.py` meets every goal on the four seeds; pytest; `tools/holes.py`,
   `tools/render_views.py`, a play-test; the speed budget.

Open questions for the owner: add River and Stony shore biomes in step 4, or keep the 18? Keep the
old generator for old worlds (step 7), or accept a seam?
