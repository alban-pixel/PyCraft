# PyCraft

A Minecraft-like game in creative mode, in an endless world 4096 blocks high, with mountain ranges
that rise more than 3,000 blocks above the sea. The 3D world is drawn by the graphics card (OpenGL
through `moderngl`), lit by the sun with shadows, and each finished frame is turned into Pyxel's
256 colors and copied into Pyxel's screen. Pyxel runs the window, keyboard, mouse, menus, HUD, sound
effects and music.

## Warning: a lot of graphical bugs

**This version has a lot of graphical bugs**, mostly in the distant terrain (the columns drawn
beyond the real blocks). They were already there before the November 9 performance work, which
didn't fix them. Seen so far:

- Holes in the distant terrain: the sky shows through mountains, in rows of gaps
- Distant mountainsides drawn as stacked, wavy stripes of columns instead of a solid slope
- Seen from close, a mountain can look like a wall of loose columns with sky between them

The performance changes were measured in headless tests (no window); they still need playing in a
real window.

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
- Shaped after Iceland: rare long graben valleys sink the land between two sheer walls, their
  floors hummocky lava fields (the deepest dip under the sea); rare flat-topped volcanoes (tuyas)
  rise behind a cliff rampart; cliff country settles into terraced lava strata; moss creeps over
  the rocks of cool wet country and turns their grass olive
- 18 biomes from the climate (temperature and humidity, colder higher up): ocean, deep ocean, frozen
  ocean, beach, desert, badlands, savanna, jungle, plains, forest, birch forest, swamp, taiga, snowy
  taiga, snowy tundra, alpine meadow, snowy peaks, glacier. Grass, leaves and water change color
  smoothly from one biome to the next
- Oak, birch, spruce, jungle and acacia trees, swamp oaks and cacti
- Tall grass, ferns, dead bushes and patches of flowers (poppies, dandelions, blue orchids,
  cornflowers, oxeye daisies, alliums) on the ground, by biome; you walk through them, and you can
  plant them, with oak saplings, on grass, dirt or podzol (dead bushes on sand)
- Caves (tunnels near the surface, big caverns deeper down) and coal, iron, gold and diamond ore
- The terrain far away, up to about 8 km, is drawn too — seabed and see-through water included —
  so you see the mountains from a long way off
- Light from the sun by day and the moon by night, with soft shadows: trees, buildings and cliffs
  cast them, light comes through leaves in spots, and mountains cast shadows kilometers long at
  sunrise and sunset
- Smooth lighting: corners and edges between blocks are darker (ambient occlusion)
- See-through water that reflects the sky, with waves and the sun glinting on them
- Drifting clouds that cast shadows, with the highest mountains rising through them; stars at night,
  a glow around the sun, and a blue haze over faraway mountains
- Anti-aliased edges, and up to 2560x1440 pixels
- 172 blocks to build with: the terrain's own, and the full blocks of the classic block set, such as
  planks of every wood, stone, deepslate, nether and prismarine bricks, granite, diorite and andesite
  (raw and polished), every sandstone, blocks of coal, iron, gold, diamond, emerald, lapis and
  redstone, obsidian, netherrack, end stone, bookshelves, hay bales, pumpkins and melons, 16 colors
  of wool, terracotta and stained glass, and machines that look the part (furnace, crafting table,
  TNT, pistons...). Glowstone, sea lanterns, lamps and jack o'lanterns glow day and night (they don't
  light up what is around them), and furnaces, dispensers, droppers and jack o'lanterns face the
  player who places them
- Plants: tall grass, ferns, dead bushes, six kinds of flowers and oak saplings, which also grow wild
  in the world
- Walking, sprinting, jumping, swimming and flying (and flying fast)
- An 8-minute day and night cycle, with a sun, a moon and sunsets
- A title screen, a pause menu and a block inventory with tabs: Nature, Building, Colors, Plants
  and Special
- Settings: resolution, interface size, 3D resolution, frame rate, render distance, LOD quality,
  graphics and music
- Automatic scaling: the menus and the HUD keep the same size at every resolution, and the 3D view
  is drawn at a lower resolution while the game can't keep up with the frame rate
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
| E | All blocks: click one to put it in the selected slot (click a hotbar slot to select it). Tab / Shift+Tab or a click change the tab. If a tab's blocks don't all fit on the screen, they go on pages: mouse wheel, Left/Right, Page Up/Down or the arrows under the slots turn them |
| Esc | Pause menu (settings, save and quit) |
| Tab | Release / capture the mouse |
| F3 | FPS, the size the 3D view is drawn at and the graphics card's time, position, altitude, biome, chunks and seed |
| H | Show / hide the controls |
| T or / | Chat: `/tp x y z`, `/time set day\|noon\|sunset\|night\|midnight` |

The save file, `world2.npz`, is in Pyxel's user data folder
(`pyxel.user_data_dir("PyCraft", "PyCraft GPU")`). Only the blocks you changed are saved: the rest
of the world comes back from the seed. Closing the window with its X button keeps only the last
automatic save. A `world.npz` from the earlier, smaller version of the game is left alone.

## Settings

Open **Settings** from the title screen or the pause menu. Click a setting (or press Right) for its
next value; right-click it, click its `<` (or press Left) for the previous one. The line under the
settings explains the one selected. Changes apply right away and are saved in `settings.json`, next
to the save file.

| Setting | Values |
|---|---|
| Resolution | 320x180, 384x216, 480x270, 640x360, 800x450, 960x540, 1280x720 (default), 1600x900, 1920x1080, 2560x1440 |
| Interface size | Auto (default), or 1x up to the largest that leaves the menus room (the screen's height / 180) |
| 3D resolution | Auto (default), 100%, 75%, 50% of the resolution, in width and in height |
| Frame rate | 30, 60 (default), 75, 120, 144, 165, 240 FPS |
| Render distance | 32, 64, 128, 256 (default), 512 chunks of 16 blocks; the distant terrain goes on beyond |
| LOD quality | low (default), medium, high, ultra: the detail of the distant terrain — grid width from 127 to 511 columns, 6 to 8 levels, finest column 1 or 2 blocks |
| Graphics | fancy (default): shadows and anti-aliasing; fast: without them, for slower graphics cards |
| Music | on / off |

A higher resolution makes the 3D view sharper. With the interface size on Auto, the HUD and menus
grow with it (each of their pixels covers 2 to 5 pixels of the screen above 960x540), so they keep
about the same size and stay readable; a fixed size makes them smaller or bigger.

With the 3D resolution on **Auto**, the game measures every frame (and, with an OpenGL timer, how
long the graphics card took for it). When the frames take longer than the frame rate allows and the
graphics card is a large part of that, the 3D view is drawn smaller, by steps of 5% from 100% down
to 50% (never fewer than 540 lines). When frames have time to spare it grows back, one step every
1.5 seconds. The menus, the HUD and the dithering always stay at the full resolution. The F3
screen shows the size the 3D view is drawn at. Part of the work doesn't shrink with the picture:
the distant terrain's shapes cost about the same at any resolution (see below).

The mouse turns the same amount for the same hand movement at every resolution. On Windows, the
game uses the screen's real pixels: on a high-DPI screen, Windows would otherwise draw the window at
a lower resolution and stretch it, blurred.

On a laptop with an AMD Ryzen AI 9 H 365 and its Radeon 880M graphics, at a render distance of 64
chunks, medium LOD quality and 100% 3D resolution, a still view takes about 22 ms a frame at
1280x720 (46 FPS with fast graphics, 43 with fancy) and 26 to 28 ms at 2560x1440 (39 and 36 FPS),
and flying fast about as long. The distant terrain alone takes about 3 ms of the graphics card's
time a frame at low LOD quality, 9 at medium, 11 at high and 19 at ultra, whatever the resolution.
If the game doesn't keep up with the frame rate you chose, lower the LOD quality first, then the
render distance or the resolution, or switch to fast graphics.

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
  code into one 256x256 "atlas" (16x16 tiles of 16x16 pixels)
- `player.py`: walking, jumping, swimming, flying, and collisions with blocks
- `ui.py`: draws the HUD and menus scaled up at high resolutions, and their parts: panels, buttons,
  setting rows, progress bars, tooltips
- `autoscale.py`: picks the 3D view's render scale from the time frames take (3D resolution: Auto)
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
Building meshes takes far longer than a frame, so worker processes do it in parallel — three on
the SWE-2 branch, scaled to the machine's cores (`cpu_count - 4`, minus what the game, its window
and the GL driver need) on m1-pro and claude, at most 8 on claude (`cpu_count` counts hardware
threads, twice the cores on most PC processors: 16 workers did no better than 8 on a 10-core Ryzen)
— each with its own copy of the world: Python threads would wait
for each other on this work. The game asks them for the nearest columns first — spread over all the
workers on m1-pro and claude — uploads what they send back, and rebuilds a section itself right away when you
change a block. Each column counts its changes, so a mesh built from older blocks is thrown away and
asked for again. While building a face, the workers also count the blocks around each of its corners:
the more there are, the darker the corner (ambient occlusion). Plants are not cubes: each one is two
quads crossed along the diagonals of its block, seen from both sides, whose see-through texels are
cut out (in the shadows too) and which are lit like the top of a block.

On m1-pro and claude, two more jobs leave the game's thread: packing a finished mesh for the card runs on a
small pool of threads, and the distant terrain's sampling runs on its own thread — NumPy releases
the GIL through its big loops, so both really work beside the game's thread, while the card's calls
themselves stay on it.

Farther away, the terrain is drawn as columns at 6 to 8 levels of detail (the LOD quality setting
picks the count, the grid width and the finest column: 1 or 2 blocks), each twice as coarse and
twice as wide as the one before, up to 8 km away. The simplification happens in voxel space before
any meshing: each cell aggregates the sub-samples under its footprint (or its four finer cells,
when they are known) into a mean top, a majority block, canopy and water coverage and an averaged
color — so rivers, forests and even the player's buildings survive at range instead of aliasing
away. The seabed is drawn as true terrain and the water as a see-through layer over it, like the
water between the blocks. The records are kept in textures that wrap around, so when the camera
moves only the new edge is produced. Each level leaves a hole where a finer level (or the blocks)
is drawn. Steep slopes show as rock, and distant terrain fades into a blue haze. Its shader finds
the texture of each block's face in a small table kept as a texture: as a constant array in the
shader, picked per pixel by block, the AMD Radeon 880M's driver copied it into every pixel's
scratch memory, and the distant terrain took 73 ms of the card's time a frame at 2560x1440
instead of 9.

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
`pyxel.resize`, and the renderer then makes a new off-screen image of the same size. The last shader
draws the frame's rows upside down, top to bottom like Pyxel's screen, so the frame is read straight
into it, without being flipped afterward. Under 100% 3D resolution, the full-color image is smaller:
the shader that turns it into palette colors scales it up first, with a Catmull-Rom filter (sharper
than a bilinear one, from 9 bilinear samples), so the dithering stays at the screen's own
resolution.

## Limits

- Water doesn't flow: it stays where it was generated or placed
- No survival mode (health, hunger, mobs, crafting)
- Caves get no sunlight, but the light of the sky still reaches them, so they aren't dark
- The distant terrain is a smooth surface: it shows the shape of the land and its colors, not
  single blocks or trees
- The clouds are flat: seen from their own height, they are a thin line
- Flying fast, you can outrun the block meshes for a moment: the distant terrain fills in until
  they catch up
