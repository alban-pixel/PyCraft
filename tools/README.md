# Checks

Scripts that check the game as a player would see it, beside the unit tests in `tests/`. They need
a graphics card (OpenGL 3.3), so they don't run on GitHub; run them before a pull request that
touches the drawing, the menus or the controls. Everything they write goes to `tools/out/`
(ignored by Git). None of them touches your save or your settings.

| Script | What it checks | Time |
|---|---|---|
| `python tools/holes.py [seed] [lod] [distance]` | No sky through the distant terrain, in 16 views of a world (`tools/views/`). Exits with 1 above 4 stray pixels. | 1–3 min |
| `python tools/menus.py` | The menus and the keys, driven by a scripted mouse and keyboard: settings, tabs, sliders, rebinding, playing with the new keys, levers. Exits with 1 if a check fails. | 1 min |
| `python tools/play_window.py` | A real window for a minute or two, with a copy of your settings: a new world, walking, placing, flying fast, menus, settings, a teleport, saving and continuing. Frame times in `tools/out/play.txt`. | 2–4 min |
| `python tools/bench.py` | Frame and graphics card times in 8 fixed views (env: `RES`, `RD`, `LOD`, `FANCY`, `PROF=1` for the distant terrain alone). | 1–2 min |
| `python tools/render_views.py` | Pictures of the views of a world, with debug shaders (`VARIANT=tag` colors each level of the distant terrain). Used by `holes.py`. | 1 min |
| `python tools/make_views.py <seed>` | Makes `tools/views/<seed>.json`: views around the spawn and in front of the steepest slopes. | seconds |
| `python tools/biomes.py [seed ...]` | How logical the biome map of the usual world is: 11 measures (humidity and the coast, snow near hot biomes, the snow line, beaches, swamps, badlands terraces, specks) against their goals and `tools/biomes_baseline.json`, and a map per seed in `tools/out/biomes_<seed>.png`. `--baseline` rewrites that file. No graphics card needed; `tests/test_biomes.py` holds the same goals. | 20 s |
| `python tools/make_climate.py` | Makes the Earth's climate file (`pycraft/earth/climate.npz`). Downloads about 200 MB; the result is in the repository, so there is no need to run it again. | 5 min |
