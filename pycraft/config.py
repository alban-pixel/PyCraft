"""Constantes globales de PyCraft.

Ce module n'importe pas Pyxel : il est utilisable par les tests et par les
modules de logique pure (world, mesher, camera).
"""

from enum import IntEnum

TITLE = "PyCraft"
VERSION = "0.1.0"

# --- Affichage ---------------------------------------------------------
DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 800
DEFAULT_FPS = 60

# --- Monde -------------------------------------------------------------
CHUNK_SIZE = 16
WORLD_X = 256
WORLD_Y = 256
WORLD_Z = 32
SEA_LEVEL = 5

# --- Caméra / rendu ----------------------------------------------------
NEAR_PLANE = 0.2
FOV_DEG = 72.0
DEFAULT_VIEW_DISTANCE = 96
DEFAULT_DETAIL_RADIUS = 24
FOG_START = 0.65   # fraction de la distance de vue où le brouillard commence
FOG_FULL = 0.92    # fraction où la couleur devient celle du ciel

# --- Couleurs (indices de la palette Pyxel 16 couleurs) ----------------
SKY_TOP = 1
SKY_HORIZON = 12
SUN_COLOR = 10
CLOUD_COLOR = 7
FOG_COLOR = SKY_HORIZON
CROSSHAIR_COLOR = 7
TEXT_COLOR = 7
HUD_BG = 0
SELECTED_COLOR = 10


class Block(IntEnum):
    """Types de blocs. La valeur entière est stockée dans le bytearray."""

    AIR = 0
    GRASS = 1
    DIRT = 2
    STONE = 3
    SAND = 4
    WOOD = 5
    LEAVES = 6
    WATER = 7


# Couleurs par bloc : (dessus, côtés +x, côtés +y, dessous)
BLOCK_COLORS: dict[Block, tuple[int, int, int, int]] = {
    Block.GRASS: (11, 3, 4, 4),
    Block.DIRT: (4, 2, 4, 2),
    Block.STONE: (13, 6, 6, 6),
    Block.SAND: (10, 9, 9, 10),
    Block.WOOD: (9, 4, 4, 4),
    Block.LEAVES: (3, 11, 3, 11),
    Block.WATER: (12, 5, 12, 5),
}

SOLID_BLOCKS = frozenset(
    b for b in Block if b not in (Block.AIR, Block.WATER)
)

# Bloc posé par défaut dans la hotbar
HOTBAR: tuple[Block, ...] = (Block.GRASS, Block.STONE, Block.WOOD)
