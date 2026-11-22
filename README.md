# PyCraft

A Minecraft-like game in creative mode, in an endless world 10240 blocks high, with mountain ranges
that rise more than 3,000 blocks above the sea. The 3D world is drawn by the graphics card (OpenGL
through `moderngl`), lit by the sun with shadows, and each finished frame is turned into Pyxel's
256 colors and copied into Pyxel's screen. Pyxel runs the window, keyboard, mouse, menus, HUD, sound
effects and music.

## Run it

Double-click `PyCraft.command` (macOS) or `PyCraft.bat` (Windows). On the first launch it makes a
virtual environment in `.venv` and installs the game's dependencies (again whenever `pyproject.toml`
changes), then the game starts.

Or by hand, from the repository's root:

```bash
python -m pip install -e .
python -m pycraft
```

Desktop only (Windows, Mac, Linux). It does not work in Pyxel's web version, because `moderngl` needs
a real graphics card driver.

## What's in the game

- An endless world, 10240 blocks high, with the sea at height 512
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
- Redstone that works (see below): levers, stone buttons, pressure plates, redstone dust, redstone
  torches, repeaters, redstone lamps, pistons and sticky pistons, TNT and blocks of redstone
- Two game modes, chosen for each new world: **Survival** and **Creative** (see below)
- Walking, sprinting, jumping, swimming and flying (and flying fast, in Creative)
- A day and night cycle, with a sun, a moon and sunsets (20 minutes long, or 10, 40 or 60)
- A title screen, a pause menu and a block inventory with tabs: Nature, Building, Colors, Plants,
  Redstone and Special
- Settings on five tabs, among them the resolution, the field of view, the mouse speed, the
  volumes, and a key of your choice for every action
- Automatic scaling: the menus and the HUD keep the same size at every resolution, and the 3D view
  is drawn at a lower resolution while the game can't keep up with the frame rate
- Saving: the game saves when you leave through the menu, and every 2 minutes (or 1, 5, 10, or never)
- Sound effects and generated background music

## Controls

These are the keys the game starts with. Every one in the first table can be changed in
**Settings → Keys**, to another key or to a mouse button.

| Key | Action |
|---|---|
| W A S D | Move |
| Space | Jump, swim up (against a wall: climb out of water), fly up |
| Left Shift | Fly down |
| Left Ctrl | Sprint; while flying: fly fast (42 blocks per second) |
| F | Toggle flying (Creative only) |
| C | Zoom, for as long as it is held |
| Left click | Break block. Creative: at once (hold to repeat). Survival: hold until it breaks |
| Right click | Place block (hold to repeat); on a lever: flip it; on a button: press it; on a repeater: change its delay; on a crafting table or a furnace: open it |
| Middle click | Pick the block you look at: its hotbar slot becomes the chosen one, or it takes the chosen slot's place |
| E | Survival: the inventory (see below). Creative: all blocks: click one to put it in the selected slot (click a hotbar slot to select it). Tab / Shift+Tab or a click change the tab. If a tab's blocks don't all fit on the screen, they go on pages: mouse wheel, Left/Right, Page Up/Down or the arrows under the slots turn them |
| T | Chat: `/tp x y z`, `/time set day\|noon\|sunset\|night\|midnight`, `/gamemode survival\|creative`, `/earth lat lon` |
| Tab | Release / capture the mouse |
| F3 | FPS, the size the 3D view is drawn at and the graphics card's time, position, altitude, biome, chunks, the levels of the distant terrain on screen and seed |
| H | Show / hide the controls, with the keys they have now |

These stay as they are:

| Key | Action |
|---|---|
| Mouse / arrow keys | Look around |
| 1-9 / mouse wheel | Choose a hotbar slot |
| / | Chat, starting a command |
| Esc | Pause menu (settings, save and quit); in a menu: back |

The save file, `world2.npz`, is in Pyxel's user data folder
(`pyxel.user_data_dir("PyCraft", "PyCraft GPU")`). Only the blocks you changed are saved: the rest
of the world comes back from the seed. Closing the window with its X button keeps only the last
automatic save. A `world.npz` from the earlier, smaller version of the game is left alone.

## Settings

Open **Settings** from the title screen or the pause menu. They are on five tabs: click a tab, or
press Tab (Shift+Tab for the one before). Then:

- a setting with a few values: click it (or press Right) for the next one; right-click it, click
  its `<` (or press Left) for the previous one;
- a setting on a scale: drag its slider, or press Left and Right;
- a key: click it (or press Enter), then press the key or mouse button the action should have. If
  another action had it, the two swap. Esc keeps the old key.

The line under the settings explains the one selected. **Defaults** puts the settings of the tab
shown back as they were at first. Changes apply right away and are saved in `settings.json`, next
to the save file.

| Tab | Setting | Values |
|---|---|---|
| Video | Resolution | 320x180, 384x216, 480x270, 640x360, 800x450, 960x540, 1280x720 (default), 1600x900, 1920x1080, 2560x1440 |
| | Interface size | Auto (default), or 1x up to the largest that leaves the menus room (the screen's height / 180) |
| | Frame rate | 30, 60 (default), 75, 120, 144, 165, 240 FPS |
| | Field of view | 50 to 110 degrees from the top of the screen to the bottom (default 70) |
| | 3D resolution | Auto (default), 100%, 75%, 50% of the resolution, in width and in height |
| | Render distance | 32, 64, 128, 256 (default), 512 chunks of 16 blocks; the distant terrain goes on beyond |
| | LOD quality | low (default), medium, high, ultra: the detail of the distant terrain — grid width from 127 to 511 columns, 6 to 8 levels, finest column 1 or 2 blocks |
| | Graphics | fancy (default): shadows and anti-aliasing; fast: without them, for slower graphics cards |
| | Texture pack | Default (the game's own textures), then every texture pack found (see below) |
| Controls | Mouse speed | 10% to 300% (default 100%) |
| | Invert mouse | off (default); on: pushing the mouse forward looks down |
| | Arrow keys speed | 30 to 240 degrees per second (default 120), for looking around with the arrow keys |
| Keys | one line per action | any key or mouse button, except those the second table of Controls keeps |
| Sound | Music | off to 100% (default 50%) |
| | Sound effects | off to 100% (default) |
| Game | Autosave | every 1, 2 (default), 5 or 10 minutes, or off |
| | Day length | 10, 20 (default), 40 or 60 minutes for a day and its night |
| | Controls help | at the start (default): the list of keys shows for the first seconds of a game; hidden |
| | Crosshair | cross (default), dot, none |

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
chunks, medium LOD quality and 100% 3D resolution, a still view takes about 7 ms a frame at
1280x720 with fast graphics and 9 with fancy (135 and 118 FPS), and 11 and 14 ms at 2560x1440 (88
and 70 FPS). Flying fast, frames take about half as long again. (Measured without a window, with no
limit on the frame rate; these times vary by a few ms from one run to the next on this laptop.) At
2560x1440, the distant terrain alone takes about 2 ms of the graphics card's time a frame at
medium LOD quality and 5 at ultra. If the game doesn't
keep up with the frame rate you chose, lower the LOD quality first, then the render distance or the
resolution, or switch to fast graphics.

Opening a world shows a loading bar until the blocks around you and every level of the distant
terrain are there: about 2 seconds at low LOD quality, 4 at medium and high, and 5 at ultra (11 at
a render distance of 256 chunks, where the blocks keep the processor busier).

The frame rate is the number of frames the game draws per second. It's useful above 60 only if
your screen's refresh rate (set in your system's display settings) is that high too.

## How it works

The game is the `pycraft` package (the folder of the same name); its modules:

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
lod.py       One more process that works out what the terrain far away looks like, at every
   |         level of detail
   |
render/      OpenGL draws the shadow maps, then the sky, the blocks near the camera, the distant
   |         terrain behind them and the clouds, in full color. A last shader turns the frame
   |         into Pyxel's palette (with dithering), one byte per pixel. Its parts: chunks (the
   |         blocks), far (the distant terrain), shadows, palette, shaders (the GLSL), gl, textures.
   v
pyxel.screen  The frame is copied into Pyxel's screen, then Pyxel draws the HUD and menus on top.
```

- `blocks.py`: block types and their properties (solid, see-through...), and which tile each face of
  each block shows
- `tiles.py`: the textures, generated by code: 16x16-pixel tiles, also put together as one
  256x256 "atlas" for the icons
- `shapes.py`: the shapes of the blocks that aren't full cubes, as boxes turned by the block's state
- `packs.py`: finds texture packs and reads their block textures into the game's tiles
- `sim.py`: the clock of the world's machines, 20 ticks a second, waking only the blocks that changed
- `redstone.py`: how levers, buttons, plates, torches, repeaters and dust power each other, and the
  lamps, pistons and TNT they drive
- `player.py`: walking, jumping, swimming, flying, and collisions with blocks
- `controls.py`: the actions of the game, the key or mouse button each one has, and the names of
  the keys in the menus and in `settings.json`
- `ui.py`: draws the HUD and menus scaled up at high resolutions, and their parts: panels, buttons,
  tabs, setting rows, sliders, key caps, slots, progress bars, tooltips. Its 16 colors (dark
  stone, warm white, amber for what is chosen) are the first 16 of the palette
- `autoscale.py`: picks the 3D view's render scale from the time frames take (3D resolution: Auto)
- `app.py`: the Pyxel app (`App`): the window, the frame loop, the states, starting and saving a game,
  drawing the world. Its screens are classes it inherits from: `screens/menus.py` (title and pause),
  `screens/settings.py`, `screens/inventory.py`, `screens/hud.py`, `screens/chat.py`, and `play.py`
  (moving, looking, breaking, placing, levers), with `sound.py` for the sounds and music
- `settings.py`: the settings' values, defaults and tabs, and reading `settings.json`
- `sky.py`: the colors of the sky and the light through the day; `icons.py`: the block icons

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

On m1-pro and claude, packing a finished mesh for the card runs on a small pool of threads: NumPy
releases the GIL through its big loops, so the packing really works beside the game's thread, while
the card's calls themselves stay on it. On m1-pro the distant terrain's sampling runs on a thread
as well. On claude it has a process of its own (`lod.py`): the game's thread spends its time inside
OpenGL calls, which keep the GIL, so a sampling thread waited for a whole call at each of its
thousands of steps, and on a PC that couldn't hold its frame rate the terrain beyond the blocks
stayed missing for minutes. In its process the sampler spreads a level over a few threads, and
shares a whole level with the builder processes that have nothing to build.

Farther away, the terrain is drawn as columns at 6 to 8 levels of detail (the LOD quality setting
picks the count, the grid width and the finest column: 1 or 2 blocks), each twice as coarse and
twice as wide as the one before, up to 8 km away. The simplification happens in voxel space before
any meshing: each cell aggregates the sub-samples under its footprint (or its four finer cells,
when they are known) into a mean top, a majority block, canopy and water coverage and an averaged
color — so rivers, forests and even the player's buildings survive at range instead of aliasing
away. The sampler measures the slope under each sub-sample the way the terrain generator does, so
a steep cell is bare rock without trees at every level, as it is in the real blocks. The seabed is
drawn as true terrain and the water as a see-through layer over it, like the water between the
blocks. The records are kept in textures that wrap around, so when the camera moves only the new
edge is produced, a strip of 4 to 16 cells at a time, and a level's grid only moves once the cells
of its new edge have come back from the sampler. A level that is far behind (after a teleport) is
left out until it has caught up: the coarser levels cover its ground meanwhile. A block you place
or break marks its cell, which is sampled again, and the change climbs from level to level.

Each level leaves a hole where a finer level (or the blocks) is drawn, and gives way to it cell by
cell over a band of 24 columns. The side of a column goes down to the lowest top that is really
drawn next to it: its neighbor's on the same level, or, where two levels meet, the coarser cell's
or the two finer cells'. A neighbor only counts with its tree crown where it draws one. Before,
walls stopped short on steep slopes and the sky showed between the columns, in stripes. Columns
are drawn whole under the blocks that fade out at the render distance, so there is always ground
behind a block that isn't drawn, and tree crowns rise over 48 blocks past that edge instead of
standing there as a wall of leaves. Distant terrain fades into a blue haze.

Most of the card's time for the distant terrain goes into the vertices of its columns, so as few
as possible are sent. Each level's grid is cut into 16x16 tiles, and a tile is only drawn when the
box from the foot of its lowest column to the top of its highest touches the view, and when a
finer level doesn't draw all of its cells; the nearest tiles go first. Of a column's four sides
only the two turned toward the camera are drawn. A shadow map gets the two turned away from the
light: with the tops they stop the same light as all four. One thing could still show the back of
a far column: the mouth of a cave. A cave's walls are only built near the player, and the distant
terrain is a hollow shell, so the eye would go through the mountain and out to the sky. The
columns around the blocks therefore get their two other sides as well, stretched down to the
bottom of the world at the edge of the blocks: a wall under the ground, all around. The water is
drawn tile by tile too, for the tiles that have some. Its shader finds the
texture of each block's face in a small table kept as a texture: as a constant array in the
shader, picked per pixel by block, the AMD Radeon 880M's driver copied it into every pixel's
scratch memory, and the distant terrain took 73 ms of the card's time a frame at 2560x1440.

Everything is drawn relative to the camera, which keeps the numbers small and precise anywhere in
the endless world. The blocks are drawn first, into the near half of the depth buffer, and the
distant terrain into the far half: each has its own depth range, so both stay precise, the distant
terrain is always behind the blocks, and the card skips its pixels that blocks already cover.

Light comes from the sun by day and from the moon by night. A face gets the light of the sky (less
on its sides and underneath) plus the direct light if it faces the sun and isn't in a shadow.
Shadows come from three shadow maps: pictures of how far everything is from the sun. One holds the
blocks around the camera, two hold the distant terrain within 1 km and within 8 km. A map is only
drawn again when what it shows changes: the sun moved a little, the camera went far, or blocks or
terrain were added (new terrain alone redraws a map at most every tenth of a second for the
blocks, every half second for the distant terrain). Clouds are a layer of tileable noise about 940
blocks above the sea, drifting with the wind. They are drawn twice: far away after the distant
terrain, nearby at the end. The blocks' water is drawn between the two, see-through, mixing its
own color with the reflected sky (more at grazing angles).

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

## Survival and Creative

**New world** on the title screen asks for a mode; `/gamemode survival|creative` (or `s`, `c`, `0`,
`1`) switches it during the game and keeps the inventory. A save from before the modes loads in
Creative, with its hotbar.

**Creative** is the game as it was: blocks break at once, the hotbar never runs out, you can fly,
and nothing hurts you.

**Survival** starts with nothing:

- **Breaking takes time**, from the block's hardness and the tool: a bar under the crosshair shows
  how far it is. The right tool goes faster (pickaxe for stone and ores, axe for wood, shovel for
  dirt, sand and gravel). Stone and ores need a pickaxe to drop anything, and iron, gold, diamond,
  emerald, redstone and obsidian need a pickaxe of stone, iron or diamond. Bedrock never breaks.
- **What breaks goes into the inventory**, with Minecraft 1.8's drops: stone gives cobblestone,
  coal ore gives coal, lapis 4 to 8 lapis, gravel sometimes flint, leaves sometimes a sapling or an
  apple, glass and ice nothing. If there's no room, it's lost ("Inventory full").
- **Tools**: pickaxes, axes and shovels of wood, stone, iron, gold and diamond. They wear out
  (59 uses for wood, 1561 for diamond) and break.
- **The inventory** (E): 36 slots, the bottom row is the hotbar, a 2x2 crafting grid. Left click
  takes or puts a stack (or swaps it); right click takes half, or puts one; Shift+click moves a
  stack between the hotbar and the rest, or out of the grid. Clicking the result crafts once;
  Shift+click on it crafts as many as it can. What's left in the grid goes back when you close it.
- **Crafting**: a crafting table (right click) gives a 3x3 grid. About 60 recipes: planks, sticks,
  the table, the furnace, the 15 tools, the redstone parts (torch, lever, button, plate, repeater,
  lamp, piston, sticky piston), blocks of 9 ingots or gems and back, polished and cut stones,
  sandstone, bricks, note block, jukebox, dropper.
- **The furnace** (right click): ore, sand, cobblestone, clay, logs... on top, fuel below (coal,
  charcoal, wood, sticks, wooden tools, a block of coal). One item takes 10 seconds; a coal cooks 8.
  It lights up while it burns and keeps cooking when you walk away. Breaking it gives you what is in
  it.
- **Health**: 10 hearts. A fall of more than 3 blocks hurts (not into water), and under water the
  air bubbles run out after 15 seconds, then you drown. Health comes back slowly (half a heart every
  4 seconds). At zero, **Respawn** takes you back to the world's start, inventory kept.

Not there yet: hunger and food, items dropped on the ground (nothing is scattered when you die),
swords, armor, chests.

## The real Earth

**Earth** on the title screen goes to a famous place of the real Earth, at one block per metre: Mont
Blanc, Everest, K2, the Matterhorn, the Grand Canyon, Yosemite, Mount Fuji, Geirangerfjord,
Kilimanjaro, Torres del Paine, Reunion and Na Pali. `/earth lat lon` goes anywhere else (latitudes up to 84).
The relief, the sea and the climate are real; the caves, the ores, the trees and the plants are the
game's own. There are no lakes, rivers, towns or roads, and land under the level of the sea is
under water.

- The first visit downloads the place (a few MB), then it plays without internet. While you play,
  the ground ahead comes by itself; if it is late, you are held at its edge for a moment.
- Without internet at a new place, the game offers a usual world instead.
- Each place has its own world and its own save (the `earth` folder beside your save, with at most
  2 GB of tiles). Your normal world is never touched: it is **Normal world** on the title screen.
- It needs Pillow. The data's credits are in [`docs/CREDITS.md`](docs/CREDITS.md).

## Redstone

The machines run 20 ticks a second, and only where something changes. A simpler cousin of
Minecraft's rules, meant to be predictable:

- **Levers, buttons and pressure plates** give power 15 around them, and power the block they are
  fixed to. A button stays pressed for a second; a plate stays down while you stand on it.
- **Redstone dust** carries power, losing 1 a block, so it reaches 15 blocks. It climbs and goes
  down steps of one block. It powers the block under it and the blocks it points into: a line's
  ends, or each arm of a corner (a lamp beside a line that just passes by stays dark).
- **Redstone torches** are lit unless the block they are fixed to is powered (a NOT gate, 2 ticks
  late). A torch flipping more than 8 times in 3 seconds burns out for 3 seconds.
- **Repeaters** carry power one way only, after 1 to 4 notches of delay (right-click to change it).
- **Lamps** light at once and go out 2 ticks later. **Pistons** push up to 12 blocks, and break
  plants and redstone parts in their way; a **sticky piston** pulls the block in front of it back.
  Bedrock, obsidian and extended pistons can't be moved. Pistons don't take power from their face.
- **TNT** explodes 4 seconds after being powered, in a radius of 4 blocks, sparing bedrock,
  obsidian and water, and lighting the TNT around it.
- Levers, buttons and torches are fixed to the face you aim at (no torch on a ceiling); dust,
  plates and repeaters need a full block under them, and repeaters point the way you look.
  Pistons face you. A part whose support goes breaks.

## Texture packs

The game can draw its blocks with a texture pack in Minecraft's format instead of its own textures.
Pick it in **Settings → Texture pack**: it applies right away, without reloading the world.

- **Where packs come from:** the `resourcepacks` folder next to the save file (the settings line
  shows where it is when Default is selected); the `resourcepacks` folder of a Minecraft installed
  on this computer; and the Minecraft versions installed there, listed as "Minecraft 1.8" and so on.
  Packs are read where they are: nothing is copied, extracted or downloaded, and the game ships no
  pack.
- **What's read:** a folder or a `.zip` with `assets/minecraft/textures/blocks/` (Minecraft 1.8 to
  1.12) or `assets/minecraft/textures/block/` (1.13 and later), and `pack.mcmeta` for its
  description. Only the block textures are used: no models, sounds, fonts, sky or menus.
- **Resolution:** the pack's own, from 16 to 256 pixels a block (the size most of its textures
  have). Textures are mipmapped, so HD packs stay sharp up close and don't shimmer far away.
- **Biome colors:** grass, leaves and water keep the colors of their biome when the pack's
  textures are grey, as Minecraft's are. Spruce and birch leaves take Minecraft's fixed colors.
- **What a pack lacks** (a block Minecraft doesn't have, or a texture missing from the pack) is
  drawn with the game's own texture. Animated textures show their first frame.
- A pack that can't be read is reported under the settings, and the game goes back to Default.

Reading packs needs Pillow, installed with the game's other dependencies.
Without it the game runs with its own textures only.

To run the tests: `python -m pip install -e ".[dev]"`, then `python -m pytest`.

## Limits

- Water doesn't flow: it stays where it was generated or placed
- Survival has no hunger, no mobs and no items on the ground (see above)
- Caves get no sunlight, but the light of the sky still reaches them, so they aren't dark
- The distant terrain shows the shape of the land and its colors, not single blocks or trees: a
  forest is a layer of leaves over the ground, and a building much smaller than the cell it stands
  in only leaves its color there
- The clouds are flat: seen from their own height, they are a thin line
- Flying fast, you can outrun the block meshes for a moment: the distant terrain fills in until
  they catch up
