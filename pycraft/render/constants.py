"""Numbers the renderer's parts share: the qualities of the distant terrain, the sizes of the
shadow maps, the clouds, the palette, and the texture unit each texture is bound to."""


LOD_QUALITIES = {  # name -> (width of a column on the finest level in blocks, grid points per side, levels)
    "low": (2, 128, 7),  # what the distant terrain always was
    "medium": (2, 256, 7),  # same columns, but every level reaches twice as far
    "high": (1, 256, 8),  # one column per block near the blocks, then coarser and coarser
    "ultra": (1, 512, 6),  # one column per block as far as the blocks go, every level twice as wide
}
LOD_QUALITY_NAMES = list(LOD_QUALITIES)
# A level's grid follows the camera by steps of 4 to 16 cells, along x and along z on their own:
# a strip of new cells a few cells wide costs the sampler half as much per cell as thin ones (it
# also samples the points around the strip, for the slopes), and a job stays short
LOD_STEP_MIN, LOD_STEP_MAX = 4, 16
LOD_MARGIN = 4  # columns along the edge of a level that the next, coarser one always draws
LOD_BAND = 24  # columns over which a level gives way to the next one, cell by cell
CROWN_DARK = 0.45  # how dark the leaves of an open crown are (its inner air folding into the color)
CROWN_RISE = 48  # blocks over which the crowns rise to their height, past the blocks: a slope, not a wall of leaves
WET_ALPHA_MIN = 0.35  # opacity of the water of a cell only a little wet (1: like a full one)
FAR_LIMIT = 8000.0  # the coarsest level reaches about 8 km
SIM_DISTANCES = {32: 6, 64: 8, 128: 10, 256: 12, 512: 12}  # render distance -> radius drawn as blocks (chunks)
COLUMN_FACES = (  # (normal, 4 corners) of a column's top, of one side along x and of one along z
    ((0, 1, 0), ((0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0))),
    ((1, 0, 0), ((1, 1, 0), (1, 1, 1), (1, 0, 1), (1, 0, 0))),
    ((0, 0, 1), ((0, 1, 1), (0, 0, 1), (1, 0, 1), (1, 1, 1))),
)
LOD_TILES = 16  # a level's grid is drawn as 16x16 tiles: only those that may be in view are sent to the card
READY_SIZE = 64  # the map of columns drawn as blocks covers 64x64 chunks around the camera
SHADOW_SIZE = 2048  # texels per side of each shadow map
SHADOW_DEPTH = 4500.0  # the shadow maps hold what is less than this far from the camera along the light
# A map whose content changed is drawn again at most this often (seconds; the blocks' map, then the
# distant terrain's two): while the player flies, new meshes and new cells land many times a second
SHADOW_EVERY = (0.1, 0.5, 0.5)
TERRAIN_SHADOW_HALF = (1024.0, 8192.0)  # half the width of the two shadow maps of the distant terrain
CLOUD_PERIOD = 4096.0  # the cloud pattern repeats every 4096 blocks
CLOUD_WIND = (6.0, 2.0)  # blocks per second
CLOUD_EXTENT = 65536.0  # half the width of the cloud layer drawn around the camera (past a screenshot's horizon)
MSAA_SAMPLES = 4  # anti-aliasing: samples per pixel with "fancy" graphics
FIXED_COLORS = 64  # palette entries that never change: Pyxel's 16 (HUD) and 48 for the block icons
SAMPLES = 64  # the frame is sampled at 64 x 64 points to adapt the palette
ADAPT_EVERY = 2  # frames between two adjustments of the palette
MIX_PENALTY = 0.35  # how much dithering between two distant colors is avoided (it looks noisy)
# Texture units
ATLAS_UNIT = 0  # the tiles' colors (a texture array, a layer per tile)
COLORS_UNIT = 1
READY_UNIT = 2
CLOUDS_UNIT = 3
SHADOW_UNITS = (4, 5, 6)
DATA_UNIT = 7
TILE_AVG_UNIT = 9
BLOCK_TILES_UNIT = 10
COARSE_UNIT = 11
FINE_UNIT = 12
TINT_UNIT = 13  # which texels of the tiles take the biome color (a texture array too)
# The screenshot (F2): its size, the jittered passes averaged into it, its shadow maps, how far it
# sees, the radius drawn as real blocks for it (chunks), and how long it waits for them (seconds)
SCREENSHOT_SIZE = (3840, 2160)
SCREENSHOT_PASSES = 16
SCREENSHOT_SHADOW_SIZE = 4096
SCREENSHOT_REACH = 61440.0
SCREENSHOT_SIM_DISTANCE = 24
SCREENSHOT_WAIT = 180.0
