"""Palette 256 couleurs et quantification RGB → indice.

Pyxel affiche un framebuffer 8 bits : chaque pixel est un indice dans
`pyxel.colors`. La palette est construite ici (16 familles × 16 nuances) et
étendue au démarrage ; un LUT 32³ accélère la conversion RGB → indice.
"""

from __future__ import annotations

import colorsys

import numpy as np

# 16 familles de teintes : ciel, eau, herbe, feuillage, terre, sable, pierre,
# bois, neige, lave, soleil, nuit, rouge, rose, turquoise, gris sombre.
_FAMILLES: tuple[tuple[float, float, float], ...] = (
    (0.58, 0.55, 1.00),
    (0.55, 0.80, 0.60),
    (0.28, 0.60, 0.75),
    (0.30, 0.55, 0.45),
    (0.08, 0.50, 0.60),
    (0.12, 0.45, 0.90),
    (0.00, 0.00, 0.60),
    (0.07, 0.55, 0.45),
    (0.60, 0.05, 0.98),
    (0.05, 0.90, 1.00),
    (0.13, 0.50, 1.00),
    (0.65, 0.50, 0.25),
    (0.00, 0.70, 0.80),
    (0.90, 0.40, 0.95),
    (0.45, 0.50, 0.70),
    (0.00, 0.00, 0.35),
)

_NUANCES = 16


# Couleurs explicites : primaires, ciel, matières de base.
_BASES: tuple[tuple[int, int, int], ...] = (
    (255, 0, 0), (255, 140, 0), (255, 230, 80), (80, 220, 80),
    (0, 200, 255), (0, 80, 255), (170, 0, 255), (255, 120, 200),
    (255, 255, 255), (0, 0, 0), (120, 90, 60), (130, 130, 130),
    (150, 200, 245), (240, 245, 250), (35, 45, 80), (255, 240, 190),
)


def _construire_palette() -> np.ndarray:
    """Construit 256 couleurs uniques : bases + rampes HSV + remplissage."""
    couleurs: list[tuple[int, int, int]] = list(_BASES)
    for i, (teinte, saturation, valeur) in enumerate(_FAMILLES):
        for j in range(_NUANCES):
            t = j / (_NUANCES - 1)
            v = 0.12 + 0.88 * t
            s = saturation * (1.0 - 0.20 * t)
            # léger décalage de teinte pour éviter les doublons entre familles
            h = (teinte + 0.006 * j) % 1.0
            r, g, b = colorsys.hsv_to_rgb(h, min(1.0, s), min(1.0, v))
            couleurs.append((int(r * 255), int(g * 255), int(b * 255)))

    uniques: list[tuple[int, int, int]] = []
    vus: set[tuple[int, int, int]] = set()
    for c in couleurs:
        if c not in vus:
            vus.add(c)
            uniques.append(c)
    # Complète avec un treillis pseudo-aléatoire déterministe.
    i = 0
    while len(uniques) < 256:
        c = ((i * 37 + 11) % 256, (i * 91 + 53) % 256, (i * 151 + 97) % 256)
        if c not in vus:
            vus.add(c)
            uniques.append(c)
        i += 1
    return np.array(uniques[:256], dtype=np.uint8)


PALETTE = _construire_palette()


def nearest_index(couleurs: np.ndarray, palette: np.ndarray = PALETTE) -> np.ndarray:
    """Indice de la couleur de palette la plus proche (distance RGB)."""
    couleurs = np.asarray(couleurs, dtype=np.int32)
    pal = palette.astype(np.int32)
    d = ((couleurs[:, None, :] - pal[None, :, :]) ** 2).sum(axis=2)
    return d.argmin(axis=1).astype(np.uint8)


def build_lut(palette: np.ndarray = PALETTE, bits: int = 5) -> np.ndarray:
    """Table (2^bits)³ : couleur quantifiée → indice de palette."""
    n = 1 << bits
    pas = 256 // n
    centres = np.arange(n) * pas + pas // 2
    grille = np.stack(np.meshgrid(centres, centres, centres, indexing="ij"), axis=-1)
    couleurs = grille.reshape(-1, 3).astype(np.uint8)
    return nearest_index(couleurs, palette).reshape(n, n, n)


def lut_lookup(lut: np.ndarray, couleurs: np.ndarray, bits: int = 5) -> np.ndarray:
    """Indices pour des couleurs RGB (N, 3) uint8, via le LUT."""
    couleurs = np.asarray(couleurs, dtype=np.uint8)
    q = (couleurs >> (8 - bits)).astype(np.intp)
    return lut[q[..., 0], q[..., 1], q[..., 2]]


def detect_palette_size(pyxel_module) -> int:
    """Renvoie 256 si la palette s'étend, 16 sinon.

    L'extension au-delà de 16 couleurs n'est pas documentée : on la teste en
    écrivant un indice 200. En cas d'échec, on garde 16 couleurs.
    """
    try:
        while len(pyxel_module.colors) < 256:
            pyxel_module.colors.append(0)
        pyxel_module.pset(0, 0, 200)
        pyxel_module.pget(0, 0)
        return 256
    except Exception:
        return 16
