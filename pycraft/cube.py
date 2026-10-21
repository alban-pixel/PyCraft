"""Géométrie d'un cube de bloc : les 12 arêtes du contour de sélection.

Partagé par le renderer CPU (`pycraft.renderer`) et le renderer GPU
(`pycraft.gl.renderer_gl`) pour que le bloc visé ait exactement le même
contour dans les deux modes.
"""

from __future__ import annotations

CUBE_EDGES: tuple[tuple[int, int], ...] = (
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 6), (6, 7), (7, 4),
    (0, 4), (1, 5), (2, 6), (3, 7),
)

# Ordre des coins : bas (z=0) puis haut (z=1), sens trigonométrique en XY.
_CUBE_CORNERS = (
    (0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
    (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1),
)


def cube_corners(
    x: int, y: int, z: int, marge: float = 0.0
) -> list[tuple[float, float, float]]:
    """Les 8 coins du bloc (x, y, z) → (x+1, y+1, z+1), avec une marge."""
    lo = (x - marge, y - marge, z - marge)
    hi = (x + 1 + marge, y + 1 + marge, z + 1 + marge)
    return [
        (lo[0] if cx == 0 else hi[0],
         lo[1] if cy == 0 else hi[1],
         lo[2] if cz == 0 else hi[2])
        for cx, cy, cz in _CUBE_CORNERS
    ]


def selection_edges(
    x: int, y: int, z: int, marge: float = 0.004
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Les 12 arêtes du cube (x, y, z) → (x+1, y+1, z+1), légèrement agrandi."""
    coins = cube_corners(x, y, z, marge)
    return [(coins[a], coins[b]) for a, b in CUBE_EDGES]
