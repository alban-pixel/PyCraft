"""PyCraft — point d'entrée du jeu.

Usage :
    python main.py
    python main.py --res 1920x1200 --dist 120 --seed 42
"""

from __future__ import annotations

import argparse

import pyxel

from pycraft import config
from pycraft.camera import Camera
from pycraft.mesher import ChunkMeshes
from pycraft.player import Player
from pycraft.renderer import Renderer
from pycraft.world import World

_etat: dict = {}


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
    parser.add_argument("--seed", type=int, default=0, help="graine du monde (défaut : 0)")
    return parser.parse_args(argv)


def appliquer_palette() -> None:
    """Installe la palette 16 couleurs du jeu (style Minecraft)."""
    for i, couleur in enumerate(config.PALETTE_HEX):
        pyxel.colors[i] = couleur


def construire(width: int, height: int, seed: int, distance: int) -> dict:
    """Construit le monde, la caméra et le renderer."""
    monde = World(seed=seed)
    maillages = ChunkMeshes(monde)
    x, y, z = monde.spawn_point()
    joueur = Player(x, y, z, yaw=0.6, pitch=-0.18)
    camera = Camera(x, y, z + joueur.eye, yaw=0.6, pitch=-0.18, width=width, height=height)
    renderer = Renderer(monde, maillages, width, height, view_distance=distance)
    return {
        "monde": monde,
        "maillages": maillages,
        "camera": camera,
        "renderer": renderer,
        "joueur": joueur,
        "selection": None,
        "souris": False,
    }


def update() -> None:
    etat = _etat
    if not etat:
        return
    joueur = etat["joueur"]
    monde = etat["monde"]
    camera = etat["camera"]
    dt = 1.0 / config.DEFAULT_FPS

    if not etat["souris"]:
        pyxel.mouse(True)
        pyxel.set_mouse_pos(camera.width // 2, camera.height // 2)
        etat["souris"] = True

    # Souris : delta par rapport au centre, puis recentrage (pas de mouvement relatif natif)
    mx, my = pyxel.mouse_x, pyxel.mouse_y
    dx = mx - camera.width // 2
    dy = my - camera.height // 2
    if dx or dy:
        joueur.set_angles(joueur.yaw + dx * 0.0035, joueur.pitch - dy * 0.0035)
        pyxel.set_mouse_pos(camera.width // 2, camera.height // 2)

    avant = int(pyxel.btn(pyxel.KEY_W)) - int(pyxel.btn(pyxel.KEY_S))
    cote = int(pyxel.btn(pyxel.KEY_D)) - int(pyxel.btn(pyxel.KEY_A))
    tourner = (int(pyxel.btn(pyxel.KEY_RIGHT)) - int(pyxel.btn(pyxel.KEY_LEFT))) * 2.2
    incliner = (int(pyxel.btn(pyxel.KEY_UP)) - int(pyxel.btn(pyxel.KEY_DOWN))) * 1.6
    joueur.update(monde, dt, avant, cote, tourner, incliner)

    x, y, z = joueur.eye_position()
    camera.set_position(x, y, z)
    camera.set_angles(joueur.yaw, joueur.pitch)
    etat["selection"] = joueur.raycast(monde, 5.0)


def draw() -> None:
    etat = _etat
    if not etat:
        pyxel.cls(config.SKY_HORIZON)
        return
    selection = etat.get("selection")
    etat["renderer"].draw(etat["camera"], selection[0] if selection else None)


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
    appliquer_palette()
    _etat.update(construire(width, height, args.seed, args.dist))
    _etat["args"] = args
    pyxel.run(update, draw)


if __name__ == "__main__":
    main()
