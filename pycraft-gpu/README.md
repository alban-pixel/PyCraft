# PyCraft

A Minecraft-like game in creative mode. The 3D world is drawn by the graphics card (OpenGL through
`moderngl`), and each finished frame is copied into Pyxel's screen. Pyxel runs the window, keyboard,
mouse, menus, HUD, sound effects and music.

## Run it

```bash
pip install -r requirements.txt
python main.py
```

Desktop only (Windows, Mac, Linux). It does not work in Pyxel's web version, because `moderngl` needs
a real graphics card driver.

## What's in the game

- A 128 x 64 x 128 world: hills, beaches, lakes, trees, caves, coal, iron, gold and diamond ore, snowy peaks, bedrock at the bottom
- 17 blocks to build with, including glass, water, glowstone and snow
- Walking, sprinting, jumping, swimming and flying
- Full support for both QWERTY (WASD) and AZERTY (ZQSD) keyboard layouts
- 3D block break particles with palette matching
- GPU View Frustum Culling for optimal chunk rendering performance
- An 8-minute day and night cycle, with a sun, a moon and sunsets
- Settings screen: resolution, target frame rate, field of view (FOV) and music
- A title screen, a pause menu and an interactive block inventory
- Saving: the game saves when you leave through the menu, and every 2 minutes
- Sound effects and generated background music
- Automated unit test suite (`pytest`)

## Controls

| Key | Action |
|---|---|
| Mouse / arrow keys | Look around |
| WASD / ZQSD | Move (compatible QWERTY & AZERTY) |
| Space | Jump, swim up (against a wall: climb out of water), fly up |
| Left Ctrl | Sprint |
| Left Shift | Fly down |
| F | Toggle flying |
| Left click | Break block (hold to repeat) |
| Right click | Place block |
| 1-9 / mouse wheel | Choose a hotbar slot |
| E | All blocks: click one to put it in the selected slot |
| Esc | Pause menu & Settings |
| Tab | Release / capture the mouse |
| F3 | FPS, position, time, seed and targeted block |
| H | Show / hide help |

The save file and settings are stored in Pyxel's user data folder (`pyxel.user_data_dir("PyCraft", "PyCraft GPU")`).

## Settings

Open **Settings** from the title screen or the pause menu. Click a setting (or press Right / D) for its
next value, right-click it (or press Left / A / Q) for the previous one. Changes apply immediately and are
saved in `settings.json`.

| Setting | Values |
|---|---|
| Resolution | 320x180 (default), 384x216, 480x270, 640x360, 800x450, 960x540 |
| Frame rate | 30, 60 (default), 75, 120, 144, 165, 240 FPS |
| Field of view | 60°, 70° (default), 80°, 90° |
| Music | on / off |

## How it works

```
world.py     World = 3D NumPy array of block ids, terrain from pyxel.noise, caves, ores, water, trees
   |
renderer.py  Chunks (16x16) are culled against the view frustum (saving draw calls).
   |         For visible chunks, NumPy finds every exposed face and builds triangles.
   |         OpenGL draws the sky, then the blocks, with textures, shading and fog.
   |         The shaders output Pyxel palette numbers directly (with Bayer dithering).
   v
pyxel.screen  The frame is copied into Pyxel's screen, then Pyxel draws 3D particles, HUD and menus on top.
```

- `blocks.py`: block definitions (19 blocks), properties (solid, opaque, cutout...), particle colors and procedural 128x128 atlas
- `world.py`: world storage, procedural noise generation (mountains, lakes, ores, snow), DDA raycasting, NPZ saving/loading
- `player.py`: physical movement, AABB collisions against voxel grid, jumping, swimming, flying
- `renderer.py`: off-screen OpenGL rendering, camera matrices, view frustum culling, chunk mesh generation, day/night lighting
- `main.py`: main Pyxel application, frame pacing, settings management, menus, block break particle effects, HUD and sounds

## Tests

Run the automated test suite from the project root:

```bash
pytest -v
```
