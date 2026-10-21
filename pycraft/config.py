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

# --- Couleurs (palette 16 couleurs personnalisée, style Minecraft) ------
SKY_TOP = 1
SKY_HORIZON = 12
SUN_COLOR = 10
CLOUD_COLOR = 7
FOG_COLOR = SKY_HORIZON
CROSSHAIR_COLOR = 7
TEXT_COLOR = 7
HUD_BG = 0
SELECTED_COLOR = 10

# Palette appliquée au démarrage (24 bits). Indices utilisés par le jeu :
#   1 ciel profond, 2 terre sombre, 3 herbe, 4 terre, 5 eau profonde,
#   6 pierre claire, 7 blanc, 8 rouge, 9 bois, 10 sable, 11 herbe claire,
#   12 ciel (horizon), 13 pierre, 14 feuillage, 15 sable clair.
PALETTE_HEX: tuple[int, ...] = (
    0x0B0B12, 0x1D3B6E, 0x4A2F1B, 0x4F8F2F, 0x8B5A2B, 0x24467E, 0xB8B8B8, 0xF4F4F4,
    0xB03A2E, 0x9C6B3F, 0xE3C76A, 0x7CC242, 0x74B3E0, 0x8A8A8A, 0x2F6B2A, 0xE8D8A8,
)

PALETTE: tuple[tuple[int, int, int], ...] = tuple(
    ((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF) for c in PALETTE_HEX
)


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
    Block.GRASS: (11, 3, 3, 4),
    Block.DIRT: (4, 2, 2, 4),
    Block.STONE: (6, 13, 13, 6),
    Block.SAND: (15, 10, 10, 15),
    Block.WOOD: (9, 2, 2, 9),
    Block.LEAVES: (14, 3, 3, 14),
    Block.WATER: (12, 5, 5, 12),
}

SOLID_BLOCKS = frozenset(
    b for b in Block if b not in (Block.AIR, Block.WATER)
)

# Bloc posé par défaut dans la hotbar
HOTBAR: tuple[Block, ...] = (Block.GRASS, Block.STONE, Block.WOOD)
