"""The GPU renderer: draws the world with OpenGL (moderngl) off-screen, then copies the frame into
Pyxel's screen.

Near the camera the world is drawn block by block: each 16x16 column of the world gets one mesh,
made of the visible faces of its sections, and a few columns are built every frame, nearest first.
Farther away, up to about 8 km, the terrain is drawn as blocky columns at six levels of detail
(a "clipmap"), sampled from the same terrain generator, so the mountains thousands of blocks high
can be seen from far away. Everything is drawn relative to the camera, which keeps the numbers
small and precise anywhere in the endless world.

Each frame is first drawn in full color: the sky with its sun, moon and stars, the distant terrain,
clouds, then the blocks, with see-through water that reflects the sky. Everything is lit by the
sun (or the moon): faces turned away from it get only the light of the sky, corners get darker
(ambient occlusion, worked out with the meshes), and shadow maps give the shadows. One shadow map
holds the blocks around the camera, two more the distant terrain, so mountains cast shadows
kilometers long. Clouds drift and cast their own shadows.

The finished image is then turned into Pyxel's 256 colors, on the graphics card too. 192 of the
colors adapt to what is on screen: a few thousand pixels are sampled every other frame and the
colors move toward them (k-means clustering). Each pixel is dithered between the two palette colors
that mix best into its own color. The shader writes one byte per pixel, the palette index, which is
copied into pyxel.screen.

The parts: constants, shaders, gl (matrices and helpers), textures, chunks (the blocks), far
(the distant terrain), shadows, palette, and renderer (the Renderer that puts them together)."""

from pycraft.render.renderer import Renderer  # noqa: F401
from pycraft.render.constants import FIXED_COLORS, LOD_QUALITIES, LOD_QUALITY_NAMES  # noqa: F401
from pycraft.render.palette import Palette  # noqa: F401
from pycraft.render.textures import make_tile_textures, split_tiles, tile_averages  # noqa: F401
from pycraft.render.chunks import affected_sections  # noqa: F401
from pycraft.lod import oklab_to_srgb, srgb_to_oklab  # noqa: F401
