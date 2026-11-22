# Mode Terre — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task, inline (the owner asked for no subagents). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Play on the real Earth at one block per metre: pick a place, wait for a short download, walk and fly over its real relief, with a view up to 65 km.

**Architecture:** A `pycraft/earth/` package holds the map grid, the elevation clean-up, the tile cache (one downloader process writes tiles to disk, every other process only reads them), the climate, and `EarthGenerator`, a `TerrainGenerator` whose `climate()` and `sample()` come from the data. Chunks, far levels and the player only go where the tiles are ready, so nothing in the game waits for the network.

**Tech Stack:** Python ≥ 3.9, numpy, Pillow (PNG), `urllib` and `zlib` from the standard library, moderngl, Pyxel, pytest.

**Spec:** [`docs/superpowers/specs/2026-11-21-mode-terre-design.md`](../specs/2026-11-21-mode-terre-design.md). Binding: every value it pins (clean-up thresholds, biome rules, distances, haze) is copied from it.

## Global Constraints

- Set-up: `.venv/bin/python -m pip install -e ".[dev]"` (pytest is not installed in `.venv` today). Tests: `.venv/bin/python -m pytest -q`. Note the count before Task 1; it never goes down.
- One branch and pull request per lot: `feature/earth-relief` (Tasks 1–8), `feature/earth-horizon` (Task 9), `feature/earth-cover` (Tasks 10–12). Each is cut from an up-to-date `main`. Never push to `main`.
- Commits: an imperative subject, **no co-author line and no Claude attribution**, in commits and pull requests alike.
- No new dependency. Tests never use the network: they write small synthetic tiles into `tmp_path`.
- A normal world is unchanged: same blocks, same saves, no request sent. Only a world with `earth` set reads or downloads tiles.
- The game's thread never does network work and never generates a column that isn't ready.
- Requests use `urllib`'s default headers: nothing about the player or the project.
- No code translated from Earth Platform (LGPL).
- Comments and docstrings in plain English saying why; lines of 120 characters at most; on-screen text in English.
- `SEA_LEVEL` stays 512. New biomes are appended, never renumbered.

## Review Focus

1. **Wi-Fi drops while flying**: the game keeps its frame rate, and far tiles come from coarser ones (Tasks 3 and 7).
2. **A half-written or corrupt tile on disk** (game killed, disk full): it is deleted and downloaded again, never a crash (Task 3).
3. **`/tp` or `/earth` across the date line or near a pole**: tile numbers wrap or clamp, and the game goes through loading (Tasks 1 and 8).
4. **A player with a normal save tries Earth, then goes back**: `world2.npz` is byte-for-byte what it was (Task 8).
5. **Certificate errors of a python.org Python on macOS**: handled like "no internet", with the offline screen (Task 3).

---

## Lot 1 — Relief (`feature/earth-relief`)

### Task 1: The map grid

**Files:** Create `pycraft/earth/__init__.py`, `pycraft/earth/grid.py`; Test `tests/test_earth_grid.py`.

**Interfaces (Produces):**
- `TILE = 256`, `MAX_ZOOM = 14`, `EQUATOR = 40075016.686`; a key is `(zoom, tx, ty)`.
- `class EarthGrid(lat, lon)`:
  - `pixels(x, z, zoom) -> (px, py)`: global pixel coordinates (float64 arrays), with `px_per_block = 256 * 2**zoom / (EQUATOR * cos(lat))` ;
  - `latlon(x, z) -> (lat, lon)` and `block(lat, lon) -> (x, z)` ;
  - `zoom_for(spacing) -> int`: `clip(round(log2(EQUATOR * cos(lat) / 256 / spacing)), 0, MAX_ZOOM)` ;
  - `tiles(x0, z0, x1, z1, zoom, margin=3) -> list[key]`: every tile a rectangle of blocks reads, `margin` pixels around it included; `tx` wraps modulo `2**zoom`, `ty` is clamped.

- [ ] **Step 1: Failing tests:**
  - `test_round_trip`: `block(*latlon(12345, -6789))` is within 0.01 block ;
  - `test_one_block_is_a_metre`: at Chamonix (45.9237, 6.8694) the summit of Mont Blanc (45.8326, 6.8652) is `z = 10130 ± 60`, `x = -325 ± 10` ;
  - `test_axes`: east is +x, south is +z ;
  - `test_zoom_for`: at latitude 45.92, `zoom_for(1) == 14`, `zoom_for(512) == 8` ; `zoom_for(10**9) == 0` ;
  - `test_tiles_wrap_and_clamp`: around longitude 179.999 both `tx == 0` and `tx == 2**zoom - 1` appear, none outside ; at latitude 85 no `ty < 0`.
- [ ] **Step 2:** Run them; they fail on the import. **Step 3:** Implement. **Step 4:** Whole suite green.
- [ ] **Step 5:** Commit `Add the Earth's map grid`.

### Task 2: Decoding and cleaning elevations

**Files:** Create `pycraft/earth/clean.py`; Test `tests/test_earth_clean.py`.

**Interfaces (Produces):**
- `decode(png: bytes) -> np.ndarray`: float32 (256, 256), indexed `[row, column]`, `R*256 + G + B/256 - 32768`.
- `clean(key, fetch) -> np.ndarray`: `fetch(key) -> np.ndarray` gives raw tiles. The spec's "Nettoyage" section, in this order: reference (zooms 13–14) or isolated pixels (0–12), then sea floor, then summits.
- `SUMMITS: list[(name, lat, lon, metres)]`: Everest 27.9881 86.9250 8849, K2 35.8808 76.5155 8611, Kangchenjunga 27.7025 88.1475 8586, Mont Blanc 45.8326 6.8652 4806, Matterhorn 45.9766 7.6585 4478, Denali 63.0692 -151.0070 6190, Kilimanjaro -3.0674 37.3556 5895, Fuji 35.3606 138.7274 3776, Aconcagua -32.6532 -70.0109 6961, Piton des Neiges -21.0983 55.4797 3070.

The measured height of a summit is the highest raw value within 250 m of it in that tile and its neighbours. The bump is centred on that highest pixel, not on the table's coordinates: they may be a few pixels apart.

- [ ] **Step 1: Failing tests**, on synthetic tiles from a `fetch` over a dict:
  - `test_decode`: a one-colour PNG of (128, 0, 128) gives 0.5 ;
  - `test_broken_run_is_replaced`: z14 on a plane at 6000 m with a run of 300 pixels at −7000: all back within 5 m of 6000 ;
  - `test_real_cliff_survives`: z14 with a 700 m cliff also present in its z11 tiles: unchanged bit for bit ;
  - `test_coarse_peak_survives`: z8 with a cone rising 4000 m over 8 pixels: unchanged ;
  - `test_coarse_spike_goes`: z10 plane at 100 m with one pixel at −9000: that pixel is 100 ;
  - `test_sea_floor`: z14 all 0, z8 at −3000: all −3000 ± 1 ; with z8 at +20: stays 0 ;
  - `test_summit_restored`: a cone peaking at 8750 at Everest's pixel peaks at 8849 ± 1, and a pixel 2 km away moves by less than 0.01.
- [ ] **Step 2:** They fail. **Step 3:** Implement. **Step 4:** Whole suite green.
- [ ] **Step 5:** Commit `Clean the Earth's elevation tiles`.

### Task 3: The tile cache and its downloader process

**Files:** Create `pycraft/earth/tiles.py`; Test `tests/test_earth_tiles.py`.

**Interfaces:**
- Consumes `clean.decode`, `clean.clean`, `grid.TILE`.
- Produces:
  - `URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"` ;
  - `tile_path(root, key) -> str`: `root/dem-v1/z/x/y.npy` (a change of clean-up changes `dem-v1`, so the same cache always gives the same terrain) ;
  - `save_tile(root, key, h)`: int16, half metres, written to a temporary file then `os.replace`d ; `load_tile(root, key) -> np.ndarray | None`: float32 metres; a file that can't be read or has another shape is deleted and gives None ;
  - `class TileReader(root, capacity=96)`: `heights(px, py, zoom) -> np.ndarray`, bicubic (Catmull-Rom), for any number of points. A missing tile is read from its nearest parent on disk, down to zoom 0; with none at all, 0. Used by every process; it never downloads ;
  - `class Downloader(root, get, threads=16)`: `fetch_one(key) -> bool`. `get(url) -> bytes` raises `OSError` on any failure (certificate errors included). 3 tries. After 3 tiles failed in a row it is offline: for 30 s each `fetch_one` fails at once without calling `get`. Raw tiles used as references are kept in memory (64 at most) ;
  - `class TileStore(root)`, on the game's side, with its downloader in a spawned daemon process (which ends when the game does, like `builder._worker`): `want(keys)`, `poll()`, `ready(keys) -> bool` (each key on disk, or failed this session), `missing(keys) -> list`, `progress(keys) -> float`, `offline -> bool`, `retry()` (forget the failures), `close()`.
- At start, the downloader deletes the least recently used tiles beyond 2 GB. The newest `want` comes first in its queue.

- [ ] **Step 1: Failing tests** (with a fake `get`; `TileStore` takes `start=False` to run without its process):
  - `test_save_load`: −10905.5 and 8849.0 survive ;
  - `test_corrupt_tile_is_deleted`: a truncated `.npy` gives None and the file is gone ;
  - `test_bicubic`: on tiles of `h = 3*px + 2*py`, random points are exact within 0.6 m (half-metre storage), across tile borders too ;
  - `test_parent_fallback`: with only a z8 tile of 500 m, a z14 read inside it gives 500 ; with nothing, 0 ;
  - `test_wraps`: a read across `tx = 0` uses the tile at `2**zoom - 1` ;
  - `test_retries_then_offline`: a `get` that always raises is called 9 times for 3 keys, then 0 times for the 4th ;
  - `test_certificate_error_is_offline`: the same with `ssl.SSLCertVerificationError` ;
  - `test_ready_after_failure`: a failed key counts as ready, and not any more after `retry()`.
- [ ] **Step 2:** They fail. **Step 3:** Implement. **Step 4:** Whole suite green.
- [ ] **Step 5:** One real run by hand: a script fetches the 9 z14 tiles around Everest into a temporary folder. Expected: no height under 5400, highest 8849 ± 1.
- [ ] **Step 6:** Commit `Add the Earth's tile cache and its downloader`.

### Task 4: A world knows its place on Earth

**Files:** Modify `pycraft/world.py`, `pycraft/terrain.py`, `pycraft/builder.py`, `pycraft/lod.py`, `pycraft/render/constants.py`, `pycraft/render/renderer.py`; Test `tests/test_earth_world.py`.

**Interfaces (Produces):**
- `pycraft/earth/__init__.py`: `class Place(NamedTuple): lat: float; lon: float; root: str` (`root`: the cache folder). Picklable: it is sent to the processes.
- `World(seed, earth=None)`, `World.earth`, `World.store = None` ; `terrain.make_generator(seed, earth)` (imports `EarthGenerator` only when `earth` is set).
- `World.save` writes `earth=np.array([lat, lon])` for an Earth world only; `World.load(path, root=None)` reads it. `SAVE_VERSION` stays 3.
- The builder's `("world", …)`, the sampler's `("config", …)` and its shared work carry `world.earth` after the seed; `_help_sampler` compares both.
- `WORLD_HEIGHT = 10240`.
- `TerrainGenerator.cloud_height = SEA_LEVEL + 940` and `.shift(heights) -> int` (0): how far a column's ores and deepslate are moved up. `Column.shift`; `deep` adds it; `_add_ores` compares `y - shift` with each ore's `top`.
- `TerrainGenerator.sample(x, z, clim=None, spacing=1)` ignores `spacing`; `lod` passes its `step`.
- `_surface`: the moss rule also needs `s["moss"]` when that key is there. `ROCKY = 18`, "Rocky slopes": stone, gravel where `noise > 0.2`; no trees.
- The renderer reads the cloud height from `world.gen`; `CLOUD_HEIGHT` goes away.

- [ ] **Step 1: Failing tests:**
  - `test_procedural_unchanged`: before any edit, record a SHA-256 of the sections of 4 chunks (seeds 7 and 424242) over their whole height, and paste both digests in the test ;
  - `test_save_load_earth`: an Earth world comes back with the same `earth` (root given to `load`) ; a save without `earth` gives None ;
  - `test_height`: a block set at y = 9400 is read back ; y = 10240 is outside ;
  - `test_shift_moves_ores`: with a generator whose `shift` is 4000, coal appears in a stone section at y = 4600, and with 0 it doesn't.
- [ ] **Step 2:** They fail. **Step 3:** Implement. **Step 4:** Whole suite green, `python tools/holes.py` passes as before.
- [ ] **Step 5:** Commit `Let a world know its place on Earth`.

### Task 5: The climate

**Files:** Create `tools/make_climate.py`, `pycraft/earth/climate.py`, `pycraft/earth/climate.npz` (3 MB at most), `docs/CREDITS.md`; Modify `pyproject.toml` (package data); Test `tests/test_earth_climate.py`.

**Interfaces (Produces):** `class Climate()`: `at(lat, lon) -> (t0, rain)`: °C brought to sea level, and mm a year; bilinear; longitudes wrap; north of 84° the nearest row.

- The tool reads `CHELSA_bio1` and `CHELSA_bio12` (`https://os.zhdk.cloud.switch.ch/chelsav2/GLOBAL/climatologies/1981-2010/bio/CHELSA_<name>_1981-2010_V.2.1.tif`): 43200×20880, uint16, one deflated strip per row, predictor 2, 120 pixels a degree, from 180° W and 84° N. Every 5th row by HTTP range request, averaged to 1/6°. Raw values: tenths of a kelvin, and tenths of a mm; 65535 is no data (filled from the nearest). It brings temperatures to sea level with `0.0065 ×` the z4 Terrarium height (averaged to the same cells, 0 at least). **About 200 MB of download, once, on the developer's machine: say so before running it.**
- `docs/CREDITS.md`: the Terrain Tiles attribution in full (from Tilezen's `attribution.md`) and CHELSA's citation.

- [ ] **Step 1: Failing tests** (they fix the scales):
  - Paris (48.86, 2.35): `t0` 9 to 13, rain 500 to 800 ; Sahara (23.3, 5.5): rain < 80 ; Singapore (1.35, 103.82): `t0` 25 to 29, rain > 1800 ; Yakutsk (62.03, 129.73): `t0` < −5 ; Chamonix: `t0` 8 to 15 ;
  - `at(10, 179.99)` and `at(10, -179.99)` differ by less than 0.2 °C.
- [ ] **Step 2:** They fail. **Step 3:** Write the tool, run it, commit its output. **Step 4:** Whole suite green.
- [ ] **Step 5:** Commit `Add the real climate`.

### Task 6: The Earth generator

**Files:** Create `pycraft/earth/generator.py`, `pycraft/earth/biomes.py`; Test `tests/test_earth_generator.py`.

**Interfaces:**
- Consumes Tasks 1 to 5.
- Produces:
  - `biomes.biome(t, rain, altitude, depth, relief, plains) -> uint8 array`: the spec's rules in their order (`depth`: of the sea, 0 on land; `plains`: bool, where rule 10 gives plains) ; `biomes.game_climate(t, rain) -> (temperature, humidity)` ;
  - `class EarthGenerator(TerrainGenerator)`, `__init__(seed, place)`: `grid`, `reader`, `climate_map`.
    - `climate(x, z) -> {"t0", "rain"}` (smooth: blended on the 8-block lattice like the others) ;
    - `sample(x, z, clim=None, spacing=1)`: the same keys as the parent's, plus `moss` (`rain > 1200` and `0 < t < 7`). Heights at `grid.zoom_for(spacing)`, plus the spec's fine relief when `spacing <= 8`, then the sea floor's squeeze, `+ SEA_LEVEL`, clipped to 8…`WORLD_HEIGHT - 64`. `relief` from 5 reads (here and 500 m each way) at 4 zooms coarser. `continent` and `mask` are zeros, `river` is False ;
    - `shift(heights)`: `max(0, int(median(heights)) - SEA_LEVEL - 64)` ;
    - `cloud_height`: `max(SEA_LEVEL + 940, ground at (0, 0) + 1200)` ;
    - `column_tiles(cx, cz) -> list[key]`: what building the mesh of a chunk reads (the chunks at ±3, every zoom `sample` uses) ; `level_tiles(x0, z0, x1, z1, step) -> list[key]`: the same for a far level.
  - `World.find_spawn` for an Earth world: the point nearest to (0, 0), every 8 blocks within 400, that is dry and has a slope under 3; else the origin, at sea level at least.

- [ ] **Step 1: Failing tests** (tiles written by `save_tile`):
  - `test_flat_height`: tiles at 1000 m: `height` is within 1 of 1512 everywhere ;
  - `test_near_and_far_agree`: on a 30 % slope, `sample` at spacing 1 and 8 differ by less than 8 blocks ;
  - `test_sea`: tiles at −50: water 512, ocean biome ; at −10905: ground ≥ 8 and water 512 ;
  - `test_biome_rules`: one case per spec rule, 1 to 10, with the values on each side of its threshold ;
  - `test_chunk_borders`: the heights of two neighbour chunks built in separate batches match the same call over both ;
  - `test_columns_build`: `World(7, place).section(...)` gives stone under, a surface block on top, air above, at y = 1512 ;
  - `test_column_tiles_cover_reads`: a `TileReader` that records its misses sees none while building chunk (0, 0)'s mesh with exactly `column_tiles(0, 0)` on disk ;
  - `test_spawn_is_dry`: half sea, half land: the spawn is on land.
- [ ] **Step 2:** They fail. **Step 3:** Implement. **Step 4:** Whole suite green.
- [ ] **Step 5:** Time `columns()` of 64 chunks: no slower than the procedural one measured in the same run (47 ms on 21 November 2026). Commit `Generate the terrain from the real Earth`.

### Task 7: Nothing waits for the network

**Files:** Modify `pycraft/world.py`, `pycraft/render/chunks.py`, `pycraft/render/far.py`, `pycraft/render/renderer.py`, `pycraft/play.py`, `pycraft/app.py`; Test `tests/test_earth_ready.py`.

**Interfaces (Produces):**
- `World.ready(cx, cz) -> bool`: True without a store; else whether `gen.column_tiles(cx, cz)` are ready, asking for those that aren't. A True answer is remembered (until `set_world`).
- `World.level_ready(x0, z0, x1, z1, step) -> bool`, the same for a far level.
- `World.prefetch(x, z)`: wants the tiles within 2 z14 tiles of the player, called when the player's tile changes.
- `Chunks.update` asks for columns and meshes only where `ready`. `FarTerrain.update` keeps a level's old grid until its new one is `level_ready`.
- `Playing`: a move into a chunk that isn't ready is undone on x and z, with the notice "Loading the terrain...". Coming from `/tp`, the state becomes `"loading"`.
- While loading, nothing on the game's thread reads blocks where the world isn't ready (`head_in_water`, `camera`).

- [ ] **Step 1: Failing tests** (a fake store: `ready(keys)`, `want(keys)`):
  - `test_procedural_always_ready` ; `test_ready_asks_once`: two calls on a missing chunk: the second asks for nothing new ;
  - `test_chunks_skip_unready`: with only chunk (0, 0) ready, the jobs given to the builders hold only (0, 0) ;
  - `test_far_level_keeps_its_grid`: an unready level isn't in the batch and its origin doesn't move ; once ready, it is ;
  - `test_player_is_held`: walking toward an unready chunk stops at its edge, and goes on once ready ;
  - `test_game_thread_never_generates_unready`: `gen.columns` raising for unready keys, 200 frames of flight straight at them raise nothing.
- [ ] **Step 2:** They fail. **Step 3:** Implement. **Step 4:** Whole suite green, `python tools/holes.py` passes.
- [ ] **Step 5:** Commit `Wait for the Earth's tiles without stopping the game`.

### Task 8: Places, loading, offline, saves

**Files:** Create `pycraft/earth/places.py`, `pycraft/screens/earth.py`; Modify `pycraft/app.py`, `pycraft/screens/menus.py`, `pycraft/screens/chat.py`, `README.md`, `docs/technique.md`, `docs/roadmap.md`, `tools/menus.py`; Test `tests/test_earth_app.py`.

**Interfaces (Produces):**
- `places.PLACES: list[(name, lat, lon, look_lat, look_lon)]`:

  | Name | Start | Looks at |
  |---|---|---|
  | Mont Blanc | 45.9237 6.8694 | 45.8326 6.8652 |
  | Everest | 27.9957 86.8285 | 27.9881 86.9250 |
  | K2 | 35.7447 76.5136 | 35.8808 76.5155 |
  | Matterhorn | 45.9836 7.7846 | 45.9766 7.6585 |
  | Grand Canyon | 36.0617 -112.1077 | 36.1500 -112.1100 |
  | Yosemite | 37.7308 -119.5738 | 37.7460 -119.5330 |
  | Mount Fuji | 35.4986 138.7686 | 35.3606 138.7274 |
  | Geirangerfjord | 62.1255 7.1650 | 62.1050 7.0940 |
  | Kilimanjaro | -2.9000 37.2500 | -3.0674 37.3556 |
  | Torres del Paine | -51.0700 -73.0000 | -50.9423 -72.9876 |
  | Réunion | -21.1300 55.4700 | -21.0983 55.4797 |
  | Na Pali | 22.1500 -159.6460 | 22.1700 -159.6400 |

- `places.slot(lat, lon) -> str` (`"+45.9237+006.8694"`), `places.yaw_to(grid, lat, lon) -> float` (0 is +z, like `Player.yaw`).
- `App.slot`: `"normal"` (`world2.npz`), `earth/<slot>.npz`, or `earth/generated.npz`; `save()` writes the current slot. "Continue" resumes the world last played in this session, else the normal one, loading it from disk when another is in memory. A new normal world always goes back to the normal slot. The title only loads the normal save, so the game starts without internet.
- `class EarthScreens` (in `screens/earth.py`), which `App` inherits from: states `"places"` (2 columns of 6 buttons, "saved" beside those with a save, the credits' line at the bottom), `"earth_loading"` ("Downloading the Earth... 63%" and a bar; Escape goes back), `"earth_offline"` (Retry, Play a generated world, Back). Without Pillow, the Earth button says "Needs Pillow".
- `App.begin_earth(lat, lon, look=None)`: makes the `World` and its `TileStore` (cache in `<data_dir>/earth`), wants the spawn's chunk tiles and the tiles of every far level the view needs, and leaves the renderer's world alone until they are ready; then the spawn, `set_world`, `"loading"`.
- `/earth <lat> <lon>`: saves the current world, then `begin_earth`. Latitude within ±84, longitude within ±180, else "Usage: /earth lat lon".
- F3 shows the latitude, the longitude and the real altitude in an Earth world.

- [ ] **Step 1: Failing tests:**
  - `test_slot`: the value above, and (-21.13, 55.47) gives `"-21.1300+055.4700"` ; `test_yaw`: south 0, east 90 ;
  - `test_normal_save_untouched`: enter Earth, save, go back to the title: `world2.npz` has the same bytes ;
  - `test_continue_after_earth`: "Continue" after an Earth game resumes it ; after a restart it gives the normal world ;
  - `test_offline_screen`: a store that is offline and not ready leads to `"earth_offline"` ; "Play a generated world" gives a world with `earth is None` saved in `earth/generated.npz` ;
  - `test_visited_place_needs_no_network`: all tiles on disk, `get` raising: it reaches `"loading"` ;
  - `test_earth_command`: `/earth 85 0` and `/earth a b` give the usage ; `/earth -16.5 179.99` starts a download whose keys are all valid.
- [ ] **Step 2:** They fail. **Step 3:** Implement. **Step 4:** Whole suite green; `python tools/menus.py` (with the new screens added to it), `python tools/holes.py`, `python tools/play_window.py`.
- [ ] **Step 5:** By hand, and reported in the pull request: Mont Blanc and Everest, 5 minutes of fast flight (worst frame, whether the notice appeared), network cut during a flight, a visited place offline, the time to enter.
- [ ] **Step 6:** Commit `Play on the real Earth`, open the pull request.

**Checkpoint: the owner looks at Mont Blanc and Everest in the game and says whether to go on, before Lot 2.**

---

## Lot 2 — Horizon (`feature/earth-horizon`)

### Task 9: See 65 km

**Files:** Modify `pycraft/render/constants.py`, `pycraft/render/renderer.py`, `pycraft/render/far.py`, `pycraft/sky.py`, `pycraft/app.py`, `pycraft/settings.py`, `pycraft/screens/settings.py`, `docs/technique.md`, `tools/render_views.py`, `tools/holes.py`; Create `tools/views/earth.json`; Test `tests/test_settings.py`, `tests/test_earth_far.py`.

**Interfaces (Produces):**
- `FAR_LIMIT` (8000) and `LOD_QUALITIES` stay: at 8192 or with more levels, low and ultra would draw one level more in a normal world. New: `EARTH_FAR_LIMIT = 65536.0` and `EARTH_LEVELS = {"low": 10, "medium": 9, "high": 10, "ultra": 9}`, used for an Earth world; the far terrain is rebuilt (`_rebuild_far`) when the kind of world changes.
- Setting `earth_distance` in `[512, 1024, 2048, 4096]`, default 2048, with its row in Video; `RENDER_DISTANCES` is unchanged. `Renderer.view_distance` is `min(earth_distance * CHUNK, EARTH_FAR_LIMIT)` in an Earth world, and as today in a normal one.
- `sky.haze(view_distance) -> float`: `min(1 / 4500, 1.78 / view_distance)`.
- The far projection beyond a view of 8192: near 16, far `2 × view_distance`; under it, 1 and 30000 as today.
- `tools/render_views.py` takes `EARTH=lat,lon`; `earth.json` has 8 views around Mont Blanc and Everest.

- [ ] **Step 1: Failing tests:**
  - `test_haze`: `haze(4096) == haze(8000) == 1/4500`, `haze(32768)` is 1.78/32768 ;
  - `test_every_quality_reaches`: `(size // 2 - LOD_MARGIN) * (spacing << (EARTH_LEVELS[q] - 1)) >= 60000` for the four qualities ;
  - `test_earth_distance_setting`: default 2048, 777 refused ;
  - `test_normal_levels_unchanged`: for a normal world at 512 chunks, `view_distance == 8000` and `levels()` is 7, 7, 8, 6 for low, medium, high, ultra ; going from an Earth world to a normal one gives these again.
- [ ] **Step 2:** They fail. **Step 3:** Implement. **Step 4:** Whole suite green; `python tools/holes.py` on its 4 worlds and on `earth.json` (4 stray pixels at most); `python tools/bench.py` before and after on a normal world: within 5 %.
- [ ] **Step 5:** Pictures of `earth.json` in the pull request; commit `See 65 km on Earth`.

---

## Lot 3 — Ground and water (`feature/earth-cover`)

### Task 10: Land cover tiles

**Files:** Create `pycraft/earth/cover.py`; Modify `pycraft/earth/tiles.py`, `docs/CREDITS.md`; Test `tests/test_earth_cover.py`.

**Interfaces (Produces):**
- `cover.source(lat, lon) -> str`: `https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N45E006_Map.tif` (south-west corner, multiples of 3°).
- `cover.parse_header(data: bytes) -> list[Level]`, `Level(width, height, offsets, sizes)`: little-endian TIFF, 7 levels from 36000 to 562, uint8, blocks of 1024, compression 8 (zlib), no predictor. All its tables fit in the first 64 KB; a lone block's offset and size are in the entry itself.
- `cover.tile(key, read) -> np.ndarray`: uint8 (256, 256) classes of a map tile, nearest pixel, from the level whose pixel is nearest to the tile's; `read(url, start, count) -> bytes | None` (None: no such file, class 0).
- `Downloader.fetch_one` also makes the cover tile, saved in `root/cover-v1/z/x/y.npy`; a tile is ready with both. A cover that fails gives class 0 for the session, and doesn't fail the heights. `TileReader.cover(px, py, zoom) -> uint8` (nearest; 0 when missing).

- [ ] **Step 1: Failing tests**, with a small TIFF made in the test (2 levels, 4 blocks): `test_parse_header`, `test_tile_classes` (known classes at known places), `test_missing_file_is_zero`, `test_single_block_level`, `test_source_names` (N45E006; S24W070 for −21.1, −69.9), `test_cover_failure_keeps_heights`.
- [ ] **Step 2:** They fail. **Step 3:** Implement. **Step 4:** Whole suite green. **Step 5:** Commit `Read the real land cover`.

### Task 11: Forests, glaciers, lakes and rivers

**Files:** Modify `pycraft/earth/generator.py`, `pycraft/earth/biomes.py`; Create `pycraft/earth/water.py`; Test `tests/test_earth_water.py`, `tests/test_earth_generator.py`.

**Interfaces (Produces):**
- `biomes.biome(..., cover)`: classes 10 trees, 20 shrubs, 30 grass, 40 crops, 50 built, 60 bare, 70 snow, 80 water, 90 wetland, 95 mangroves, 100 moss; 0 is unknown (the rules of Lot 1). The mapping is the spec's; 100 gives alpine meadow, 20 gives savanna from 18 °C, else plains; snow is a glacier where the slope is under 0.5 m a metre.
- `water.levels(heights, cover) -> (water, bed)`: the spec's rule (lowest height within 9 pixels, bed lower by `1 + 6 f²`). Worked out on a whole tile with its neighbours, so it is the same from every chunk, and kept beside the heights in the reader's cache. Classes are read at the same zoom as the heights.
- Sea: class 80 or 0, with a height ≤ 0. Land under zero with another class is dry.

- [ ] **Step 1: Failing tests:** `test_cover_mapping` (one case per class), `test_lake_is_level` (a lake over noisy heights of ±2 m: one level over its inner part), `test_lake_bed`, `test_river_has_water_every_step` (a 3 % slope, 30 m wide), `test_water_across_tiles` (two tiles give the same level on both sides of their border), `test_land_below_zero_is_dry` (−5 m, class 40), `test_dead_sea` (−430 m, class 80: water at 512 − 430).
- [ ] **Step 2:** They fail. **Step 3:** Implement. **Step 4:** Whole suite green, `python tools/holes.py` on `earth.json`. **Step 5:** Commit `Grow the real forests and fill the real lakes`.

### Task 12: Last look and notes

**Files:** Modify `docs/technique.md`, `docs/roadmap.md`, `README.md`, the spec (what changed).

- [ ] **Step 1:** By hand, with a picture each: the 12 places. For each: recognisable or not, what is wrong.
- [ ] **Step 2:** The spec's "Réussi si" list, measured again and written in `docs/technique.md`.
- [ ] **Step 3:** Commit `Document the Earth mode`, open the pull request. Follow-ups, each with its own plan: IGN heights in France, a travel map, Earth's curvature.
