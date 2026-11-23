# Mode capture — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task, inline (the owner asked for no subagents). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One key (F2) takes a screenshot of the world in full colour at 3840×2160, with the best shaders the engine has, seen up to 60 km, with real blocks drawn farther than in play, saved as a PNG.

**Architecture:** F2 puts the game in a `"screenshot"` state: the renderer is given a *reach* of 61 440 blocks (the distant terrain is rebuilt with enough levels, the blocks are meshed out to 24 chunks), and the game waits, frozen, behind a progress bar, until everything is built. Then `Renderer.capture` draws the frame off screen at 3840×2160, 16 times with a sub-pixel jitter of the projection, into a float accumulator (16× supersampling of edges, textures, leaves and shadows), with a `hq` shader switch (16-tap shadow filter, 4096² shadow maps, 32-step clouds) and without Pyxel's 256-colour palette. The average goes through the same `finish()` as the game, is read back as RGB and written as a PNG with `zlib`. The renderer then goes back to the settings' reach and the game resumes.

**Tech Stack:** Python ≥ 3.9, numpy, moderngl (OpenGL 3.3), Pyxel, `zlib`/`struct` from the standard library, pytest.

**Spec:** the owner's request in chat (23 novembre 2026): « screenshot mode qui render tout en full résolution avec des ultra bons shaders en full qualité », then « render plus loin, genre le full 60 km de vision dans le screenshot mode, donc ça doit aussi render les chunks loin ». No separate design document; the decisions below are this plan's and are listed so the owner can overrule them at review:

| Decision | Value |
|---|---|
| Key | F2 (new action `screenshot`, can be rebound) |
| Size | 3840×2160, shrunk to the card's limits keeping 16:9 |
| Anti-aliasing | 16 jittered passes (Halton 2,3), no MSAA |
| Reach | 61 440 blocks of distant terrain; real blocks to 24 chunks (384 blocks; 12 in play) |
| Wait | until everything is built, at most 180 s; ESC cancels |
| What is in the picture | the world only: no HUD, no block outline, no message |
| Where | `<Pyxel user data dir>/screenshots/YYYY-MM-DD_HH.MM.SS.png` (`_2`, `_3`… when taken in the same second) |

## Global Constraints

- Set-up: `.venv/bin/python -m pip install -e ".[dev]"`. Tests: `SDL_AUDIODRIVER=dummy .venv/bin/python -m pytest -q`. 357 pass before Task 1; the count never goes down.
- Branch `feature/screenshot`, cut from an up-to-date `main`; one pull request. Never push to `main`.
- Commits: an imperative subject, **no co-author line and no Claude attribution**, in commits and pull requests alike.
- No new dependency: the PNG is written with `zlib` and `struct` (Pillow stays optional for the game).
- No sound or music in any test (volumes 0, `SDL_AUDIODRIVER=dummy`).
- The game outside the screenshot is unchanged: same frame, same palette, same speed (`tools/bench.py` within 5 %), same levels of distant terrain for every LOD quality. Every new shader path is behind `hq == 1`, and `hq` is 0 unless capturing.
- All GLSL stays in `pycraft/render/shaders.py` (tools patch it there).
- Every OpenGL call happens inside `with self.ctx` (see `Renderer.render`).
- Comments and docstrings in plain English saying why; lines of 120 characters at most; on-screen text in English.
- The Earth plan's Task 9 (`feature/earth-horizon`, not merged) plans `sky.haze(view_distance)` and the far projection rule below with the same names and values: whichever lands second reuses the other's, never a second copy.

## Review Focus

1. **The frame after the capture took seconds**: the automatic render scale must not drop to 50 % because of it — the scaler is reset after the capture (Task 5, `test_capture_resets_scaler`).
2. **A graphics card whose texture or viewport limit is under 3840** (older Intel, some Windows drivers): the picture is shrunk to fit, 16:9 kept, never a GL error (Task 1, `test_fit_size`).
3. **The screenshots folder can't be written** (a file in its place, disk full, read-only): a message says so, the game goes on, the renderer is back to the settings' reach (Task 5, `test_save_fails_cleanly`).
4. **An Earth world without internet, or a far terrain that never settles**: the wait ends after 180 s and the picture is taken with what is there; ESC cancels at any time and restores the reach (Task 5, `test_timeout_captures_anyway`, `test_escape_cancels`).
5. **Two screenshots in the same second**: two files, neither overwritten (Task 1, `test_same_second`).

---

### Task 1: Pure helpers (sizes, jitter, file names, PNG)

**Files:**
- Create: `pycraft/screenshot.py`
- Modify: `pycraft/render/constants.py` (append), `pycraft/render/gl.py` (append)
- Test: `tests/test_screenshot.py`

**Interfaces:**
- Produces, in `pycraft/render/constants.py`: `SCREENSHOT_SIZE = (3840, 2160)`, `SCREENSHOT_PASSES = 16`, `SCREENSHOT_SHADOW_SIZE = 4096`, `SCREENSHOT_REACH = 61440.0`, `SCREENSHOT_SIM_DISTANCE = 24`, `SCREENSHOT_WAIT = 180.0` (seconds).
- Produces, in `pycraft/render/gl.py`: `jittered(proj: np.ndarray, dx: float, dy: float, width: int, height: int) -> np.ndarray` — a copy of a perspective matrix whose picture moves by (dx, dy) pixels (adds `2*dx/width` and `2*dy/height` to the x and y rows' third column, with the sign that moves the picture right and up for positive values).
- Produces, in `pycraft/screenshot.py`:
  - `halton_offsets(n: int) -> list[tuple[float, float]]`: the first n points of the Halton sequence in bases 2 and 3, starting at index 1, each minus 0.5 (so in [-0.5, 0.5)).
  - `fit_size(size: tuple[int, int], max_texture: int, max_viewport: tuple[int, int]) -> tuple[int, int]`: the largest size of the same ratio that fits both limits, both sides rounded down to even numbers.
  - `screenshot_path(folder: str, when: time.struct_time) -> str`: creates `folder` if missing; `YYYY-MM-DD_HH.MM.SS.png`, or with `_2`, `_3`… before `.png` if taken.
  - `write_png(path: str, rgb: np.ndarray) -> None`: an (h, w, 3) uint8 array as an 8-bit RGB PNG (signature, IHDR, one zlib IDAT with filter byte 0 per row, IEND, CRCs with `zlib.crc32`).

- [ ] **Step 1: Write the failing tests** in `tests/test_screenshot.py`:
  - `test_halton`: `halton_offsets(4) == [(0.0, -1/6), (-0.25, 1/6), (0.25, -7/18), (-0.375, -1/18)]` (`pytest.approx`), and every one of `halton_offsets(16)` is in [-0.5, 0.5) on both axes, all distinct.
  - `test_jittered`: with `p = perspective(70, 16/9, 0.05, 6000)`, the point `(0, 0, -10, 1)` projected by `jittered(p, 1, 0, 1920, 1080)` lands `2/1920` to the right in NDC of where `p` puts it (`approx`, abs 1e-6), and `jittered(p, 0, 0, …)` equals `p`; `p` itself is not changed.
  - `test_fit_size`: `fit_size((3840, 2160), 16384, (16384, 16384)) == (3840, 2160)`; `fit_size((3840, 2160), 2048, (16384, 16384)) == (2048, 1152)`; `fit_size((3840, 2160), 16384, (3000, 16384)) == (3000, 1686)`.
  - `test_png_round_trip` (skipped without Pillow, `pytest.importorskip("PIL")`): a random (5, 7, 3) uint8 array written then read with Pillow is equal, mode `"RGB"`, size (7, 5).
  - `test_same_second`: in `tmp_path / "shots"` (missing), two calls with the same `struct_time` give `…_12.34.56.png` then `…_12.34.56_2.png` once the first file exists; the folder was created.
- [ ] **Step 2: Run** `SDL_AUDIODRIVER=dummy .venv/bin/python -m pytest tests/test_screenshot.py -q` — Expected: fails on the imports.
- [ ] **Step 3: Implement** the constants, `jittered`, and `pycraft/screenshot.py`.
- [ ] **Step 4: Run** the whole suite — Expected: 357 + 5 pass (4 if Pillow is missing).
- [ ] **Step 5: Commit** `Add the screenshot's sizes, jitter and PNG writer`.

### Task 2: A reach of 60 km

**Files:**
- Modify: `pycraft/render/far.py`, `pycraft/render/renderer.py`, `pycraft/render/constants.py` (`CLOUD_EXTENT`), `pycraft/sky.py`, `pycraft/app.py` (`draw_world`'s haze)
- Test: `tests/test_reach.py`

**Interfaces:**
- Consumes: `SCREENSHOT_SIM_DISTANCE` (Task 1).
- Produces:
  - `far.levels_for(spacing: int, size: int, reach: float) -> int`: the fewest levels with `(size // 2 - LOD_MARGIN) * (spacing << (levels - 1)) >= reach` (the rule of `FarTerrain.levels()`).
  - In `renderer.py`, module functions `view_distance(render_distance: int, reach: float | None) -> float` (`reach` when given, else `min(render_distance * CHUNK, FAR_LIMIT)`), `sim_distance(render_distance: int, reach: float | None) -> int` (`SCREENSHOT_SIM_DISTANCE` when reach is given, else `SIM_DISTANCES.get(render_distance, 12)`), and `far_planes(view: float) -> tuple[float, float]` (`(1.0, 30000.0)` up to a view of 8192, beyond it `(16.0, 2 * view)`). The properties `Renderer.view_distance` / `sim_distance` call them with `self.reach`, and `render()` builds `far_vp` with `far_planes(self.view_distance)`.
  - `Renderer.reach: float | None = None` and `Renderer.set_reach(reach: float | None) -> None`: stores it, then rebuilds the distant terrain (`_rebuild_far(far.tiles, levels=…)`) when the number of levels must change: `max(LOD_QUALITIES[q][2], levels_for(spacing, size, reach))` with a reach, `LOD_QUALITIES[q][2]` without (q: the current quality, from `(far.spacing, far.size)`). Nothing is rebuilt when the count is already right.
  - `Renderer.reach_progress(cam) -> float`: `self.progress(cam, self.sim_distance)`, but at most 0.99 while `chunks.pending`, `chunks.preparing`, `far.working`, `far.pending` or `far.edits` is non-empty (the test `tools/render_views.settle` uses): 1.0 means built and idle.
  - `sky.haze(view_distance: float) -> float`: `min(HAZE, 1.78 / view_distance)`; `App.draw_world` passes `haze(end)` instead of `HAZE`.
  - `CLOUD_EXTENT = 65536.0` (the cloud slab must reach the horizon; at 8 km the fog hides the difference).

- [ ] **Step 1: Write the failing tests** in `tests/test_reach.py`:
  - `test_levels_for`: `levels_for(*LOD_QUALITIES[q][:2], 61440)` is 10, 9, 10, 9 for low, medium, high, ultra (the same counts as the Earth plan's `EARTH_LEVELS`), and `levels_for(2, 128, 7680) == 7`.
  - `test_distances`: `view_distance(512, None) == 8000`, `view_distance(64, None) == 1024`, `view_distance(64, 61440.0) == 61440.0`; `sim_distance(256, None) == 12`, `sim_distance(32, 61440.0) == 24`.
  - `test_far_planes`: `far_planes(8000) == (1.0, 30000.0)`, `far_planes(61440) == (16.0, 122880.0)`.
  - `test_haze`: `haze(4096) == haze(8000) == HAZE` (1/4500: play looks the same) and `haze(61440) == pytest.approx(1.78 / 61440)`.
  - `test_sim_distance_fits_ready_map`: `SCREENSHOT_SIM_DISTANCE + 2 <= READY_SIZE // 2` (the map of columns drawn as blocks covers 64×64 chunks).
- [ ] **Step 2: Run** them — Expected: fail on the imports.
- [ ] **Step 3: Implement** the functions, `set_reach`, `reach_progress`, the far planes and the haze.
- [ ] **Step 4: Run** the whole suite — Expected: all pass. Then `python tools/holes.py` (its 4 worlds, 4 stray pixels at most) and `python tools/bench.py` before and after on `main`'s settings: within 5 %.
- [ ] **Step 5: Commit** `Let the renderer see 60 km`.

### Task 3: The high-quality shaders and the accumulator

**Files:**
- Modify: `pycraft/render/shaders.py`, `pycraft/render/shadows.py`
- Create: `pycraft/render/accumulate.py`
- Test: `tests/test_hq_render.py` (GL tests: the `ctx` fixture of `tests/test_upload.py`, skipped without a context)

**Interfaces:**
- Consumes: `SCREENSHOT_SHADOW_SIZE` (Task 1).
- Produces:
  - Uniform `int hq` (0 by default) in `SHADOWS` and `CLOUD_FRAGMENT_SHADER`. In `pcf()`: with `hq == 1`, 16 lookups on the 16-point Poisson disk of NVIDIA's "Percentage-Closer Soft Shadows" sample, scaled to 1.5 texels, averaged; otherwise the 4 lookups of today, unchanged. In the clouds: `int steps = hq == 1 ? 32 : 6;` replaces the constant 6 (loop bound and the two divisions).
  - `Shadows(ctx, atlas, tint, size=SHADOW_SIZE)`: `self.size`; `ShadowMap(light, half, cam, key, version, size)` snaps to `2 * half / size`; `update()`'s `shadow_texel` uses `self.size`. `Shadows.release() -> None` frees its textures, framebuffers and placeholder.
  - `ACCUMULATE_SCENE_FRAGMENT_SHADER` and `RESOLVE_FRAGMENT_SHADER` in `shaders.py` (the first copies `texelFetch(scene, ivec2(gl_FragCoord.xy), 0)`; the second outputs `vec4(finish(sum / float(count)), 1.0)` with the rows flipped, like `POST_FRAGMENT_SHADER`, and uses `FINISH`).
  - `class Accumulator(ctx, size: tuple[int, int])` in `pycraft/render/accumulate.py`: an RGBA `f4` texture and its framebuffer, cleared to 0; `add(scene: moderngl.Texture) -> None` draws the scene into it with additive blending (`ONE, ONE`) and counts it; `resolve(dim: float, tint: tuple) -> np.ndarray` returns the average through `finish()` as an (h, w, 3) uint8 array, top row first; `release() -> None`.

- [ ] **Step 1: Write the failing tests:**
  - `test_shaders_compile_with_hq`: the block, distant terrain and cloud programs compile on the `ctx` fixture and each has an `hq` uniform.
  - `test_shadow_size`: `Shadows(ctx, atlas, tint, size=SCREENSHOT_SHADOW_SIZE).textures[0].size == (4096, 4096)` (atlas and tint from `make_tile_textures(ctx, build_tiles())`), then `release()` raises nothing; `Shadows(ctx, atlas, tint).size == SHADOW_SIZE`.
  - `test_accumulator_average`: four (8, 4) `f2` RGBA textures of constant grey 0.1, 0.2, 0.3, 0.4 added; `resolve(1.0, (1.0, 1.0, 1.0))` is (4, 8, 3), every value `round(0.25 * 255) ± 1`.
  - `test_accumulator_rows`: a scene texture whose bottom row (OpenGL's row 0) is red and the rest black: in `resolve()`'s array, the last row is red and row 0 is black.
  - `test_accumulator_finish`: one texture of 2.0: every value is 254 or 255 (`finish` rolls off highlights); with `dim=0.5`, every value is `round(0.5 * finish(2.0) * 255) ± 1` where `finish(2.0) = 0.8 + 0.2 * (1 - exp(-6))`.
- [ ] **Step 2: Run** `… -m pytest tests/test_hq_render.py -q` — Expected: fail on the imports.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the whole suite — Expected: all pass. `python tools/holes.py` unchanged (the game draws with `hq` 0).
- [ ] **Step 5: Commit** `Add high-quality shadows and clouds, and a frame accumulator`.

### Task 4: `Renderer.capture`

**Files:**
- Modify: `pycraft/render/renderer.py`
- Create: `tools/screenshot.py`
- Modify: `tools/README.md` (one row)

**Interfaces:**
- Consumes: Tasks 1–3 (`jittered`, `halton_offsets`, `fit_size`, `Accumulator`, `Shadows(size=)`, `far_planes`, `set_reach`, `reach_progress`).
- Produces:
  - `draw_frame` is split, with no change to what the game draws: `frame_values(eye, now) -> tuple[dict, tuple]` (the uniforms `render()` builds today, and `cam`) and `draw_scene(values, far_vp, near_vp, cam, target, shadows) -> None` (from `palette.apply()` to the near clouds and the outline, into `self.scene_fbo`, using `shadows` instead of `self.shadows`). `draw_frame` = `draw_scene` + the resolve, post pass and palette sampling, as today.
  - `Renderer.capture(eye, forward, size=SCREENSHOT_SIZE, passes=SCREENSHOT_PASSES) -> np.ndarray`: (h, w, 3) uint8, top row first, `(h, w)` from `fit_size(size, ctx.info["GL_MAX_TEXTURE_SIZE"], ctx.info["GL_MAX_VIEWPORT_DIMS"])`. Inside `with self.ctx`, in a `try/finally` that puts back `self.size`, `self.render_scale` and the framebuffers (`make_framebuffers()`) whatever happens:
    1. `self.size = (w, h)`, `render_scale = 1.0`; a scene framebuffer without MSAA (`f2` texture + depth) bound as `self.scene_fbo`;
    2. `now` read once (waves and clouds don't move between passes); `values = frame_values(...)` plus `hq = 1`, `shadows_on = 1`;
    3. a `Shadows(ctx, texture, tint_texture, size=SCREENSHOT_SHADOW_SIZE)` whose maps are drawn by the first pass and kept for the others (same camera, same light);
    4. for each `(dx, dy)` of `halton_offsets(passes)`: `far_vp = jittered(perspective(fov, w/h, *far_planes(view)), dx, dy, w, h) @ view`, the same for `near_vp` with `(0.05, 6000)`; `draw_scene(..., target=None, shadows=hq_shadows)`; `accumulator.add(scene_texture)`;
    5. `accumulator.resolve(1.0, finish tint)` (the underwater tint is kept, `dim` is always 1); release the accumulator, the HQ shadows and the temporary framebuffer.
  - `tools/screenshot.py`: like `tools/render_views.py` (headless App, its own settings and save in `tools/out/`), env `RES`, `RD`, `LOD`, `WORLD_SEED`; loads the world, `set_reach(SCREENSHOT_REACH)`, settles on `reach_progress == 1` (at most `SCREENSHOT_WAIT`), `capture()`, writes `tools/out/screenshot.png`, `set_reach(None)`, draws 30 normal frames. Exits 1 if: the picture is not (2160, 3840, 3) (or the `fit_size` result), it has fewer than 1000 distinct colours, the renderer's `size`/`scene_size` after differ from before, `far.n_levels` after differs from before, or the normal frame after the capture is all one palette index. Logs the wait, the capture time and `levels()` in `tools/out/screenshot.txt`.

- [ ] **Step 1: Write `tools/screenshot.py`** (it is this task's test: the capture needs a world, the sampler process and the workers).
- [ ] **Step 2: Run** `python tools/screenshot.py` — Expected: exits 1 (`capture` missing).
- [ ] **Step 3: Implement** the split and `capture`.
- [ ] **Step 4: Run** `python tools/screenshot.py` — Expected: exit 0; look at `tools/out/screenshot.png`: mountains to the horizon, soft shadow edges, no palette dithering, no seam between blocks and distant terrain. Then the whole suite, `python tools/holes.py` and `python tools/bench.py` (within 5 % of Task 2's numbers).
- [ ] **Step 5: Commit** `Capture the world at 4K with 16 jittered passes`.

### Task 5: F2 in the game

**Files:**
- Modify: `pycraft/controls.py` (`ACTIONS`), `pycraft/play.py` (`update_playing`), `pycraft/app.py` (inherit the mixin, `screenshot_dir`, `update`, `draw`), `pycraft/screens/hud.py` (`help_lines`)
- Create: `pycraft/screens/screenshot.py`
- Test: `tests/test_screenshot_mode.py`

**Interfaces:**
- Consumes: `Renderer.set_reach`, `reach_progress`, `capture` (Tasks 2, 4); `screenshot_path`, `write_png` (Task 1); `SCREENSHOT_REACH`, `SCREENSHOT_WAIT`.
- Produces:
  - `("screenshot", "Take a screenshot", "F2")` appended to `ACTIONS` (18 keys: two columns of 9 in the Keys tab, which is full after this); `(key("screenshot"), "Screenshot")` at the end of the help's second column.
  - `App.screenshot_dir = os.path.join(data_dir, "screenshots")`.
  - `class Screenshots` (App inherits it), state `"screenshot"`:
    - `start_screenshot() -> None`: from `"playing"` only; `renderer.set_reach(SCREENSHOT_REACH)`, `self.screenshot_started = time.perf_counter()`, `self.screenshot_due = False`, `set_state("screenshot")`. `update_playing` calls it on `keys.pressed("screenshot")` and returns.
    - `update_screenshot(cancel: bool) -> None`: `cancel` → `end_screenshot()`, `notify("Screenshot cancelled")`; else `screenshot_due = True` once `reach_progress(eye) >= 1` or `SCREENSHOT_WAIT` seconds have passed. `App.update` calls it with `pyxel.btnp(pyxel.KEY_ESCAPE)`, and its building budget is 0.06 s in `"screenshot"` as in `"loading"`.
    - `draw_screenshot() -> None`: called by `App.draw` after `draw_world()` in that state. If `screenshot_due`: `take_screenshot()`; otherwise `draw_message_box(f"Preparing the screenshot... {p * 100:.0f}%  ESC: cancel", p)`.
    - `take_screenshot() -> None`: `eye, forward = self.camera()`; `rgb = renderer.capture(eye, forward)`; `write_png(screenshot_path(self.screenshot_dir, time.localtime()), rgb)`; `notify(f"Screenshot saved: {name}")`. On `OSError` or `moderngl.Error`: `notify(f"Screenshot failed: {e}")` (cut with `fit_text`) and the error on stderr. In every case: `end_screenshot()`, `self.scaler.reset()`.
    - `end_screenshot() -> None`: `renderer.set_reach(None)`, `set_state("playing")`.
  - The world doesn't move while waiting: `update_playing` is not called in `"screenshot"` (time of day, machines and player stand still); `draw_world` doesn't dim it.

- [ ] **Step 1: Write the failing tests** in `tests/test_screenshot_mode.py`, on a `Game(App)` without window like `tests/test_earth_app.py`'s, with a fake renderer (records `set_reach` calls, `reach_progress` returns a set value, `capture` returns a (4, 6, 3) array or raises) and a fake scaler:
  - `test_defaults_unique`: `DEFAULTS["screenshot"] == "F2"` and the existing uniqueness test still passes.
  - `test_waits_then_captures`: after `start_screenshot()` the state is `"screenshot"` and `set_reach` got `SCREENSHOT_REACH`; with progress 0.5, `update_screenshot(False)` leaves `screenshot_due` False; with 1.0 it is True; `take_screenshot()` writes one PNG in `tmp_path`, the message starts with `"Screenshot saved: "`, the state is `"playing"`, the last `set_reach` call is `None`.
  - `test_escape_cancels`: `update_screenshot(True)` → state `"playing"`, last reach `None`, message `"Screenshot cancelled"`, no file.
  - `test_timeout_captures_anyway`: progress stuck at 0.3 and `screenshot_started` set `SCREENSHOT_WAIT + 1` seconds back: `screenshot_due` becomes True.
  - `test_save_fails_cleanly`: `screenshot_dir` is an existing *file*: `take_screenshot()` raises nothing, the message starts with `"Screenshot failed"`, state `"playing"`, last reach `None`.
  - `test_capture_resets_scaler`: after `take_screenshot()` (success and failure), the fake scaler's `reset` was called.
  - `test_only_while_playing`: from `"paused"`, `start_screenshot()` changes nothing.
- [ ] **Step 2: Run** them — Expected: fail on the imports.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the whole suite — Expected: all pass. Then `python tools/menus.py` (Keys tab with 18 keys, help panel), `python tools/play_window.py`, and by hand: `python -m pycraft`, a world, F2 — the bar fills, the PNG opens at 3840×2160, the game goes on at its usual frame rate within a few seconds; F2 then ESC cancels.
- [ ] **Step 5: Commit** `Take a screenshot with F2`.

### Task 6: Documentation

**Files:** Modify `README.md` (controls and what F2 does, where the files go), `docs/technique.md` (a « Mode capture » section: the reach, the wait, the jittered passes, `hq`, the accumulator, why no palette).

- [ ] **Step 1:** Write both, in the files' own languages (README in English, technique in French).
- [ ] **Step 2:** The whole suite passes; links in both files open.
- [ ] **Step 3: Commit** `Document the screenshot mode`, then open the pull request with `tools/out/screenshot.png` (shrunk) in its description.
