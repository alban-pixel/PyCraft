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
| `beach_inland`: beach more than 64 blocks from the sea | ≤ 5% | 25–31% |
| `swamp_high`: swamp more than 8 blocks above the sea | ≤ 5% | 32–37% |
| `terraces_outside_badlands`: badlands terraces outside badlands | ≤ 10% | 27–35% |
| `specks`: land with no neighbor of its own biome (48-block grid) | ≤ 0.2% | 0.7% |
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
4. **Landform biomes from the land** (done). `sample()` estimates the distance to the coast like
   the rivers' distance: the smooth ground level's height above the sea over how fast it rises
   (the continentalness's gradient, computed only for points within a few blocks of sea level,
   so it costs about 3%). Beaches: within 32 blocks of the coast, not on river or lake banks.
   Swamps: humid ground at most 5 blocks above the sea, within 300 blocks of the coast or by a
   river or a lake. `sample()` also returns `shore` (the beach strip, and the banks just above
   a river or a lake), and the sand, gravel and clay follow it instead of covering every column
   within 2 blocks of sea level: shingle on steep shores, rock on cliffs, snow on cold ones. No
   new biome (River, Stony shore): the surface does it. Met on the four seeds: `beach_inland`
   1.6–3.2%, `swamp_high` 0. The measure now counts the first block of shallow sea as sea (the
   generator gives it a land biome); with it, the old generator's `beach_inland` is 25–31%, not
   the 47–56% first reported, and the baseline was recomputed from the step 1 generator.
5. **Terrain follows the biome** (done). The terracing strength (`mesa`) uses the temperature at
   the height of the ground (the biomes' cooling with altitude) and starts at 0.35 like the hot
   biomes, and the biome is badlands exactly where it passes 0.3. Met on the four seeds:
   `terraces_outside_badlands` 0–0.1% (was 27–35%: plains at 0.25–0.35 and the mountains of hot
   countries); badlands 0.9–2.5% of the map.
6. **Borders** (done for the specks). The small noise on the temperature and the humidity varied
   every 70–90 blocks, so borders came out dotted; it now varies over 350–400 blocks, so they
   wander without specks. The measure leaves beaches out (a strip narrower than its grid, by
   design). Met on the four seeds: `specks` 0.1% (was 0.6–0.7%). Not done: blending trees and
   ground blocks across a border (tints already change smoothly); it would need a second,
   finer biome map for every chunk.
7. **Old worlds** (done). A save holds only the sections the player changed; the rest comes back
   from the seed, so a new generator would change all the untouched land of an old world and
   leave seams around its builds. `terrain.GENERATOR_VERSION` is 2; `TerrainGenerator(seed,
   version)` keeps version 1 (the generator of main 2e9d45b) as a few branches: its climate,
   border noise, terracing and `_biome_v1`, and no `ice` or `shore` in `sample()`, so the
   blocks and the distant terrain use the old shores and ice. `World(seed, earth, version)`;
   `save()` writes `generator`, and `load()` reads a save without it as version 1. The builders
   and the distant terrain's sampler get the version in their messages. The Earth's generator
   has no versions. Version 1 was checked equal to main on 82 arrays (sample on two seeds, 72
   sections); `tests/test_generator_version.py` holds a sample of main's generator
   (`tests/data/generator_v1.npz`).
8. **Check.** `tools/biomes.py` meets every goal on the four seeds; pytest; `tools/holes.py`,
   `tools/render_views.py`, a play-test; the speed budget.

Open questions for the owner: add River and Stony shore biomes in step 4, or keep the 18? Keep the
old generator for old worlds (step 7), or accept a seam?
