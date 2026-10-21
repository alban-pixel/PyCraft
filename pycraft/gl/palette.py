"""Palette 256 couleurs et quantification RGB → indice.

Pyxel affiche un framebuffer 8 bits : chaque pixel est un indice dans
`pyxel.colors`. La palette est construite ici (16 familles × 16 nuances) et
étendue au démarrage ; un LUT 32³ accélère la conversion RGB → indice.
"""

from __future__ import annotations

import colorsys

import numpy as np

from pycraft import config

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


# Rampes explicites, insérées juste après les 16 couleurs de base : le ciel,
# l'eau et le brouillard ont besoin de dégradés continus. Sans elles, un bleu
# intermédiaire tombe sur la famille cyan et le ciel se couvre de liserés verts.
_RAMPES: tuple[tuple[str, ...], ...] = (
    # nuit → jour (zénith)
    ("0A1020", "132445", "1D3B6E", "2A4E86", "38639E", "4878B4", "5A8FC8", "6FA4D8"),
    # horizon clair
    ("74B3E0", "86C1E8", "9ACFEF", "AFDCF4", "C4E7F8", "D9F0FB"),
    # aube et crépuscule
    ("3A2233", "5E2F2C", "87402C", "B05630", "D4703A", "E88C50", "F2A876"),
    # nuages
    ("C8CDD8", "DDE2EA", "EFF2F7", "FAFBFD"),
)


def _construire_palette() -> np.ndarray:
    """256 couleurs uniques.

    Les 16 premières sont **exactement** la palette du jeu (config.PALETTE) : le
    HUD, les couleurs de blocs et l'ancien renderer CPU restent cohérents. Les
    240 suivantes sont des rampes pour les dégradés et l'éclairage.
    """
    bases: list[tuple[int, int, int]] = [(int(r), int(g), int(b)) for r, g, b in config.PALETTE]
    vus: set[tuple[int, int, int]] = set(bases)
    uniques: list[tuple[int, int, int]] = list(bases)

    for rampe in _RAMPES:
        for hexa in rampe:
            c = (int(hexa[0:2], 16), int(hexa[2:4], 16), int(hexa[4:6], 16))
            if c not in vus:
                vus.add(c)
                uniques.append(c)

    for teinte, saturation, _ in _FAMILLES:
        for j in range(_NUANCES):
            t = j / (_NUANCES - 1)
            v = 0.10 + 0.90 * t
            s = saturation * (1.0 - 0.20 * t)
            h = (teinte + 0.004 * j) % 1.0
            r, g, b = colorsys.hsv_to_rgb(h, min(1.0, s), min(1.0, v))
            c = (int(r * 255), int(g * 255), int(b * 255))
            if c not in vus:
                vus.add(c)
                uniques.append(c)

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


def install_palette(pyxel_module) -> int:
    """Étend la palette Pyxel et installe les 256 couleurs du jeu.

    À appeler **après** `pyxel.init()`. Renvoie la taille effective (256 ou 16).
    """
    taille = detect_palette_size(pyxel_module)
    for i in range(taille):
        r, g, b = (int(v) for v in PALETTE[i])
        pyxel_module.colors[i] = (r << 16) | (g << 8) | b
    return taille


def lut_as_texture(lut: np.ndarray) -> np.ndarray:
    """Réorganise le LUT (32, 32, 32) en image 2D (hauteur=32, largeur=1024).

    x = r + 32·g, y = b : une texture 2D se sample de façon fiable partout.
    """
    return np.ascontiguousarray(lut.transpose(2, 1, 0).reshape(32, 1024))
