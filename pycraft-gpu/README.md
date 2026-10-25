# PyCraft

A Minecraft-like game in creative mode, in an endless world 4096 blocks high, with mountain ranges
that rise more than 3,000 blocks above the sea. The 3D world is drawn by the graphics card (OpenGL
through `moderngl`), lit by the sun with shadows, and each finished frame is turned into Pyxel's
256 colors and copied into Pyxel's screen. Pyxel runs the window, keyboard, mouse, menus, HUD, sound
effects and music.

## Run it

```bash
pip install -r requirements.txt
python main.py
```

Desktop only (Windows, Mac, Linux). It does not work in Pyxel's web version, because `moderngl` needs
a real graphics card driver.

## What's in the game

- An endless world, 4096 blocks high, with the sea at height 512
- Continents and oceans; long mountain ranges up to about 3,500 blocks above the sea, with tree
  lines, snow lines and glaciers on the highest peaks; rivers in their own valleys; lakes; hills,
  beaches, steep rocky coasts and badlands mesas
- 18 biomes from the climate (temperature and humidity, colder higher up): ocean, deep ocean, frozen
  ocean, beach, desert, badlands, savanna, jungle, plains, forest, birch forest, swamp, taiga, snowy
  taiga, snowy tundra, alpine meadow, snowy peaks, glacier. Grass, leaves and water change color
  smoothly from one biome to the next
- Oak, birch, spruce, jungle and acacia trees, swamp oaks and cacti
- Caves (tunnels near the surface, big caverns deeper down) and coal, iron, gold and diamond ore
- The terrain far away, up to about 8 km, is drawn too, so you see the mountains from a long way off
- Light from the sun by day and the moon by night, with soft shadows: trees, buildings and cliffs
  cast them, light comes through leaves in spots, and mountains cast shadows kilometers long at
  sunrise and sunset
- Smooth lighting: corners and edges between blocks are darker (ambient occlusion)
- See-through water that reflects the sky, with waves and the sun glinting on them
- Drifting clouds that cast shadows, with the highest mountains rising through them; stars at night,
  a glow around the sun, and a blue haze over faraway mountains
- Anti-aliased edges, and up to 2560x1440 pixels
- 37 blocks to build with
- Walking, sprinting, jumping, swimming and flying (and flying fast)
- An 8-minute day and night cycle, with a sun, a moon and sunsets
- A title screen, a pause menu and a block inventory
- Settings: resolution, frame rate, render distance, graphics and music
- Saving: the game saves when you leave through the menu, and every 2 minutes
- Sound effects and generated background music

## Controls

| Key | Action |
|---|---|
| Mouse / arrow keys | Look around |
| WASD | Move |
| Space | Jump, swim up (against a wall: climb out of water), fly up |
| Left Ctrl | Sprint; while flying: fly fast (42 blocks per second) |
| Left Shift | Fly down |
| F | Toggle flying |
| Left click | Break block (hold to repeat) |
| Right click | Place block |
| 1-9 / mouse wheel | Choose a hotbar slot |
| E | All blocks: click one to put it in the selected slot |
| Esc | Pause menu (settings, save and quit) |
| Tab | Release / capture the mouse |
| F3 | FPS, position, altitude, biome, chunks and seed |
| H | Show / hide help |

The save file, `world2.npz`, is in Pyxel's user data folder
(`pyxel.user_data_dir("PyCraft", "PyCraft GPU")`). Only the blocks you changed are saved: the rest
of the world comes back from the seed. Closing the window with its X button keeps only the last
automatic save. A `world.npz` from the earlier, smaller version of the game is left alone.

## Settings

Open **Settings** from the title screen or the pause menu. Click a setting (or press Right) for its
next value, right-click it (or press Left) for the previous one. Changes apply right away and are
saved in `settings.json`, next to the save file.

| Setting | Values |
|---|---|
| Resolution | 320x180, 384x216, 480x270, 640x360, 800x450, 960x540, 1280x720 (default), 1600x900, 1920x1080, 2560x1440 |
| Frame rate | 30, 60 (default), 75, 120, 144, 165, 240 FPS |
| Render distance | 4, 6, 8 (default), 10, 12 chunks of 16 blocks drawn as blocks; the distant terrain goes on beyond |
| Graphics | fancy (default): shadows and anti-aliasing; fast: without them, for slower graphics cards |
| Music | on / off |

A higher resolution makes the 3D view sharper. The HUD and menus grow with it (each of their pixels
covers 2 to 5 pixels of the screen above 960x540), so they keep about the same size and stay
readable. The mouse turns the same amount for the same hand movement at every resolution. On
Windows, the game uses the screen's real pixels: on a high-DPI screen, Windows would otherwise draw
the window at a lower resolution and stretch it, blurred.

On a laptop graphics chip (AMD Radeon 880M), with fancy graphics, the game runs at about 200 frames
per second at 1280x720, 150 at 1920x1080 and 100 at 2560x1440. If it doesn't keep up with the frame
rate you chose, lower the resolution or switch to fast graphics.

The frame rate is the number of frames the game draws per second. It's useful above 60 only if
your screen's refresh rate (set in your system's display settings) is that high too.

## How it works

```
noise.py     Perlin noise for whole NumPy arrays of points at once
   |
terrain.py   The terrain at any (x, z): height, water, biome, climate. Then the blocks of each
   |         16x16 column and 16x16x16 section: rock layers, surface, water, caves, ores, trees
   |
world.py     The world: sections made the first time they are needed, block access, saving
   |
builder.py   Worker processes that generate the terrain and find every visible block face
   |
renderer.py  OpenGL draws the shadow maps, then the sky, the distant terrain, the clouds and the
   |         blocks near the camera, in full color. A last shader turns the frame into Pyxel's
   |         palette (with dithering), one byte per pixel.
   v
pyxel.screen  The frame is copied into Pyxel's screen, then Pyxel draws the HUD and menus on top.
```

- `blocks.py`: block types, their properties (solid, see-through...) and the textures, generated by
  code into one 128x128 "atlas"
- `player.py`: walking, jumping, swimming, flying, and collisions with blocks
- `ui.py`: draws the HUD and menus scaled up at high resolutions
- `main.py`: the Pyxel app: screens, input, breaking and placing, day/night, saving, sound and HUD

### The terrain

Everything is built from smooth noise, in layers:

1. **Continents.** A very smooth noise decides where the land and the oceans are, and gives a base
   height: deep ocean, shelf, coast, lowlands, inland plateaus.
2. **Mountain ranges.** They follow the line where another very smooth noise crosses zero, so they
   form long chains. A spine rises toward that line, and "ridged" noise adds sharp crests, side
   ridges and valleys on top. Each finer layer of the ridged noise is weighted by the one before,
   so crests get detail while the valleys between them stay smooth, a bit like eroded rock.
3. **Hills and bumps** on top, stronger in some regions than others.
4. **Rivers** follow the zero line of a third noise. The distance to the line (the noise divided
   by the length of its gradient) carves a channel 3 to 12 blocks wide and a valley around it,
   wider where the land is higher. The water lies at the base height, so the banks always hold it.
   Rivers stay out of the mountain ranges, which keeps the ranges whole.
5. **Lakes** fill round basins in flat land; **badlands** turn their relief into stepped mesas.
6. **Climate.** Temperature and humidity are two more smooth noises. Temperature drops with
   altitude, so mountains get forests, then alpine meadows, then snow, then glaciers. The biome
   comes from the climate, and the surface from the biome and the slope: steep ground is bare rock.

The large, smooth layers are only computed every 8 blocks and blended in between, which makes
generating a column about 3 times faster.

### Drawing it

Near the camera, each 16x16 column gets one mesh, made of the visible faces of its sections.
Building meshes takes far longer than a frame, so three worker processes do it in parallel (each
with its own copy of the world: Python threads would wait for each other). The game asks them for
the nearest columns first, uploads what they send back, and rebuilds a section itself right away
when you change a block. Each column counts its changes, so a mesh built from older blocks is
thrown away and asked for again. While building a face, the workers also count the blocks around
each of its corners: the more there are, the darker the corner (ambient occlusion).

Farther away, the terrain is drawn as a smooth height map at six levels of detail, each twice as
coarse and twice as wide as the one before (4 to 128 blocks between points, up to 8 km away). The
heights and colors are kept in textures that wrap around, so when the camera moves only the new
edge is sampled. Each level leaves a hole where a finer level (or the blocks) is drawn. Steep slopes
show as rock, and distant terrain fades into a blue haze.

Everything is drawn relative to the camera, which keeps the numbers small and precise anywhere in
the endless world. The distant terrain and the blocks each get their own depth range, so both stay
precise.

Light comes from the sun by day and from the moon by night. A face gets the light of the sky (less
on its sides and underneath) plus the direct light if it faces the sun and isn't in a shadow.
Shadows come from three shadow maps: pictures of how far everything is from the sun. One holds the
blocks around the camera, two hold the distant terrain within 1 km and within 8 km. A map is only
drawn again when what it shows changes: the sun moved a little, the camera went far, or blocks or
terrain were added. Clouds are a layer of tileable noise about 940 blocks above the sea, drifting
with the wind. They are drawn twice: far away with the distant terrain, nearby after the blocks.
Water is drawn last, see-through, mixing its own color with the reflected sky (more at grazing
angles).

The frame is drawn in full color, then turned into Pyxel's 256 colors. The first 16 are Pyxel's
own (used by the HUD), the next 48 suit the block icons, and the last 192 adapt to what is on
screen. Every other frame, 4096 pixels are sampled; each goes to its nearest palette color, and each
color moves toward the average of its pixels (k-means clustering, done on the graphics card). A
color that no pixel uses goes to split the busiest one in two. Each pixel is then dithered between
the two palette colors that mix best into its color, picked from a table of 32x32x32 colors that is
worked out again whenever the palette changes. The palette only changes when the view does, so a
still view doesn't flicker.

Pyxel's frame rate can't change once its window is open, so the game starts Pyxel with a very high
one and paces the frames itself (`App.run`, with `pyxel.flip`). Movement uses the real time between
frames, so the game runs at the same speed at any frame rate. The resolution changes with
`pyxel.resize`, and the renderer then makes a new off-screen image of the same size.

## Limits

- Water doesn't flow: it stays where it was generated or placed
- No survival mode (health, hunger, mobs, crafting)
- Caves get no sunlight, but the light of the sky still reaches them, so they aren't dark
- The distant terrain is a smooth surface: it shows the shape of the land and its colors, not
  single blocks or trees
- The clouds are flat: seen from their own height, they are a thin line
- Flying fast, you can outrun the block meshes for a moment: the distant terrain fills in until
  they catch up
