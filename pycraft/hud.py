"""HUD : réticule, hotbar, aide, écran titre et statistiques."""

from __future__ import annotations

import pyxel

from pycraft import config


_TAMPON = None


def text_big(x: int, y: int, texte: str, couleur: int, echelle: int = 2) -> None:
    """Texte Pyxel agrandi : dessiné dans une image puis blitté avec scale."""
    global _TAMPON
    if _TAMPON is None:
        _TAMPON = pyxel.Image(256, 12)
    _TAMPON.cls(0)
    _TAMPON.text(0, 0, texte, couleur)
    pyxel.blt(x, y, _TAMPON, 0, 0, len(texte) * 4, 6, colkey=0, scale=echelle)


def slot_rect(width: int, height: int, index: int, count: int) -> tuple[int, int, int, int]:
    """Rectangle du slot `index` de la hotbar, centrée en bas de l'écran."""
    taille = 34
    ecart = 6
    total = count * taille + (count - 1) * ecart
    x0 = width // 2 - total // 2
    x = x0 + index * (taille + ecart)
    return x, height - 40, taille, taille


def draw_crosshair(width: int, height: int) -> None:
    cx, cy = width // 2, height // 2
    c = config.CROSSHAIR_COLOR
    pyxel.line(cx - 6, cy, cx - 2, cy, c)
    pyxel.line(cx + 2, cy, cx + 6, cy, c)
    pyxel.line(cx, cy - 6, cx, cy - 2, c)
    pyxel.line(cx, cy + 2, cx, cy + 6, c)


def draw_hotbar(width: int, height: int, index: int) -> None:
    for i, bloc in enumerate(config.HOTBAR):
        x, y, w, h = slot_rect(width, height, i, len(config.HOTBAR))
        pyxel.rect(x, y, w, h, config.HUD_BG)
        pyxel.rectb(x, y, w, h, config.SELECTED_COLOR if i == index else 13)
        pyxel.rect(x + 7, y + 7, w - 14, h - 14, config.BLOCK_COLORS[bloc][0])
        text_big(x + 3, y + 3, str(i + 1), config.TEXT_COLOR, 2)


def draw_aide(width: int, height: int) -> None:
    lignes = (
        "ZQSD bouger  ·  souris/flèches regarder",
        "clic gauche casser  ·  clic droit poser",
        "1/2/3 choisir le bloc  ·  R nouveau monde",
        "F3 statistiques  ·  H aide  ·  Échap quitter",
    )
    largeur = max(len(l) for l in lignes) * 4 * 2 + 16
    x = (width - largeur) // 2
    y = height - 120
    pyxel.rect(x, y, largeur, len(lignes) * 14 + 10, config.HUD_BG)
    pyxel.rectb(x, y, largeur, len(lignes) * 14 + 10, 13)
    for i, ligne in enumerate(lignes):
        text_big(x + 8, y + 7 + i * 14, ligne, config.TEXT_COLOR, 2)


def draw_stats(width: int, height: int, fps: float, quads: int, chunks: int, seed: int) -> None:
    pyxel.rect(2, 2, 250, 58, config.HUD_BG)
    text_big(6, 6, f"{fps:4.0f} fps  {quads} quads", config.TEXT_COLOR, 2)
    text_big(6, 22, f"chunks {chunks}  seed {seed}", config.TEXT_COLOR, 2)
    text_big(6, 38, "PyCraft", 13, 2)


def draw_titre(width: int, height: int, seed: int) -> None:
    pyxel.cls(config.SKY_TOP)
    titre = "PyCraft"
    text_big(width // 2 - len(titre) * 4 * 3, height // 2 - 70, titre, config.TEXT_COLOR, 6)
    sous = "monde de blocs en 3D dans Pyxel"
    text_big(width // 2 - len(sous) * 4, height // 2 - 6, sous, config.SKY_HORIZON, 2)
    start = "ENTREE, clic ou ZQSD pour jouer"
    text_big(width // 2 - len(start) * 4, height // 2 + 34, start, config.SELECTED_COLOR, 2)
    seed_txt = f"seed {seed}"
    text_big(width // 2 - len(seed_txt) * 2, height // 2 + 56, seed_txt, 13, 1)
    bas = "ZQSD bouger · souris regarder · clics casser/poser"
    text_big(width // 2 - len(bas) * 2, height - 28, bas, 13, 1)
