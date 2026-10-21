"""PyCraft — point d'entrée du jeu.

Usage :
    python main.py
    python main.py --res 1920x1200 --dist 120
"""

from __future__ import annotations

import argparse

import pyxel

from pycraft import config


def parse_res(text: str) -> tuple[int, int]:
    """Convertit '1280x800' en (1280, 800)."""
    try:
        w, h = text.lower().split("x")
        width, height = int(w), int(h)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"résolution invalide {text!r} (attendu : LARGEURxHAUTEUR, ex. 1280x800)"
        ) from exc
    if width < 160 or height < 120:
        raise argparse.ArgumentTypeError("résolution minimale : 160x120")
    return width, height


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PyCraft — monde de blocs 3D dans Pyxel")
    parser.add_argument(
        "--res",
        type=parse_res,
        default=(config.DEFAULT_WIDTH, config.DEFAULT_HEIGHT),
        help="résolution de la fenêtre (défaut : 1280x800)",
    )
    parser.add_argument(
        "--dist",
        type=int,
        default=config.DEFAULT_VIEW_DISTANCE,
        help="distance de vue en blocs (défaut : 96)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="graine du monde (défaut : 0)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    width, height = args.res
    pyxel.init(
        width,
        height,
        title=config.TITLE,
        fps=config.DEFAULT_FPS,
        quit_key=pyxel.KEY_ESCAPE,
    )
    pyxel.run(update, draw)


def update() -> None:
    """Logique du jeu, appelée à chaque frame par Pyxel."""


def draw() -> None:
    """Affichage, appelé à chaque frame par Pyxel."""
    pyxel.cls(config.SKY_HORIZON)
    titre = f"{config.TITLE} {config.VERSION}"
    pyxel.text(pyxel.width // 2 - len(titre) * 2, pyxel.height // 2 - 4, titre, config.TEXT_COLOR)
    pyxel.text(
        pyxel.width // 2 - 60,
        pyxel.height // 2 + 6,
        "monde en construction — Echap pour quitter",
        config.TEXT_COLOR,
    )


if __name__ == "__main__":
    main()
