"""PyCraft — point d'entrée du jeu.

Usage :
    python main.py
    python main.py --res 1920x1200 --dist 120 --seed 42
"""

from __future__ import annotations

import argparse
import time

import pyxel

from pycraft import config, hud
from pycraft.camera import Camera
from pycraft.mesher import ChunkMeshes
from pycraft.player import Player
from pycraft.renderer import Renderer
from pycraft.world import World

_etat: dict = {}


# ----------------------------------------------------------------------
# Arguments
# ----------------------------------------------------------------------
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
    if width > 3840 or height > 2160:
        raise argparse.ArgumentTypeError("résolution maximale : 3840x2160")
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
        "--detail",
        type=int,
        default=config.DEFAULT_DETAIL_RADIUS,
        help="rayon du maillage détaillé, en blocs (défaut : 24)",
    )
    parser.add_argument(
        "--no-lod",
        action="store_true",
        help="désactive le LOD (tout en maillage détaillé, plus lent)",
    )
    parser.add_argument("--seed", type=int, default=0, help="graine du monde (défaut : 0)")
    return parser.parse_args(argv)


# ----------------------------------------------------------------------
# Construction
# ----------------------------------------------------------------------
def appliquer_palette() -> None:
    """Installe la palette 16 couleurs du jeu (style Minecraft)."""
    for i, couleur in enumerate(config.PALETTE_HEX):
        pyxel.colors[i] = couleur


def construire(
    width: int,
    height: int,
    seed: int,
    distance: int,
    detail: int = 24,
    lod: bool = True,
) -> dict:
    """Construit le monde, la caméra, le joueur et le renderer."""
    monde = World(seed=seed)
    maillages = ChunkMeshes(monde)
    x, y, z = monde.spawn_point()
    joueur = Player(x, y, z, yaw=0.6, pitch=-0.18)
    camera = Camera(x, y, z + joueur.eye, yaw=0.6, pitch=-0.18, width=width, height=height)
    renderer = Renderer(
        monde,
        maillages,
        width,
        height,
        view_distance=distance,
        detail_radius=detail,
        use_detail=lod,
    )
    maintenant = time.perf_counter()
    return {
        "monde": monde,
        "maillages": maillages,
        "camera": camera,
        "renderer": renderer,
        "joueur": joueur,
        "selection": None,
        "souris": False,
        "hotbar_index": 0,
        "seed": seed,
        "fps": 0.0,
        "derniere_frame": maintenant,
        "stats": False,
        "aide": True,
        "aide_manuel": False,
        "aide_fin": maintenant + 5.0,
    }


def relancer(seed: int) -> None:
    """Nouveau monde, mêmes réglages."""
    etat = _etat
    nouveau = construire(
        etat["camera"].width,
        etat["camera"].height,
        seed,
        etat["renderer"].view_distance,
        etat["renderer"].detail_radius,
        etat["renderer"].use_detail,
    )
    ecran = etat.get("ecran", "jeu")
    etat.update(nouveau)
    etat["ecran"] = ecran


# ----------------------------------------------------------------------
# Boucle
# ----------------------------------------------------------------------
def update() -> None:
    etat = _etat
    if not etat:
        return

    maintenant = time.perf_counter()
    if etat["ecran"] == "titre":
        if pyxel.btnp(pyxel.KEY_RETURN) or pyxel.btnp(pyxel.KEY_SPACE):
            etat["ecran"] = "jeu"
            etat["aide"] = True
            etat["aide_fin"] = maintenant + 5.0
        return

    if pyxel.btnp(pyxel.KEY_R):
        relancer(etat["seed"] + 1)
        return
    if pyxel.btnp(pyxel.KEY_F3):
        etat["stats"] = not etat["stats"]
    if pyxel.btnp(pyxel.KEY_H):
        etat["aide"] = not etat["aide"]
        etat["aide_manuel"] = etat["aide"]
        etat["aide_fin"] = maintenant + 5.0
    if etat["aide"] and not etat["aide_manuel"] and maintenant > etat["aide_fin"]:
        etat["aide"] = False

    joueur: Player = etat["joueur"]
    monde: World = etat["monde"]
    maillages: ChunkMeshes = etat["maillages"]
    camera: Camera = etat["camera"]
    dt = 1.0 / config.DEFAULT_FPS

    if not etat["souris"]:
        pyxel.mouse(True)
        pyxel.set_mouse_pos(camera.width // 2, camera.height // 2)
        etat["souris"] = True

    # Souris : delta par rapport au centre, puis recentrage.
    dx = pyxel.mouse_x - camera.width // 2
    dy = pyxel.mouse_y - camera.height // 2
    if dx or dy:
        joueur.set_angles(joueur.yaw + dx * 0.0035, joueur.pitch - dy * 0.0035)
        pyxel.set_mouse_pos(camera.width // 2, camera.height // 2)

    avant = int(pyxel.btn(pyxel.KEY_W)) - int(pyxel.btn(pyxel.KEY_S))
    cote = int(pyxel.btn(pyxel.KEY_D)) - int(pyxel.btn(pyxel.KEY_A))
    tourner = (int(pyxel.btn(pyxel.KEY_RIGHT)) - int(pyxel.btn(pyxel.KEY_LEFT))) * 2.2
    incliner = (int(pyxel.btn(pyxel.KEY_UP)) - int(pyxel.btn(pyxel.KEY_DOWN))) * 1.6
    joueur.update(monde, dt, avant, cote, tourner, incliner)

    # Hotbar
    for i in range(len(config.HOTBAR)):
        if pyxel.btnp(pyxel.KEY_1 + i):
            etat["hotbar_index"] = i

    # Casser / poser
    if pyxel.btnp(pyxel.MOUSE_BUTTON_LEFT):
        joueur.break_block(monde, maillages)
    if pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT):
        joueur.place_block(monde, maillages, config.HOTBAR[etat["hotbar_index"]])

    x, y, z = joueur.eye_position()
    camera.set_position(x, y, z)
    camera.set_angles(joueur.yaw, joueur.pitch)
    etat["selection"] = joueur.raycast(monde, 5.0)


def draw() -> None:
    etat = _etat
    if not etat:
        pyxel.cls(config.SKY_HORIZON)
        return

    if etat["ecran"] == "titre":
        hud.draw_titre(pyxel.width, pyxel.height, etat["seed"])
        return

    # fps lissé
    maintenant = time.perf_counter()
    delta = maintenant - etat["derniere_frame"]
    etat["derniere_frame"] = maintenant
    if delta > 0:
        etat["fps"] = etat["fps"] * 0.9 + (1.0 / delta) * 0.1

    selection = etat.get("selection")
    etat["renderer"].draw(etat["camera"], selection[0] if selection else None)

    hud.draw_crosshair(pyxel.width, pyxel.height)
    hud.draw_hotbar(pyxel.width, pyxel.height, etat["hotbar_index"])
    if etat["aide"]:
        hud.draw_aide(pyxel.width, pyxel.height)
    if etat["stats"]:
        hud.draw_stats(
            pyxel.width,
            pyxel.height,
            etat["fps"],
            etat["renderer"].quads,
            etat["renderer"].chunks_visibles,
            etat["seed"],
        )


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    width, height = args.res
    try:
        pyxel.init(
            width,
            height,
            title=config.TITLE,
            fps=config.DEFAULT_FPS,
            quit_key=pyxel.KEY_ESCAPE,
        )
    except Exception as exc:  # fenêtre impossible (résolution > écran, etc.)
        raise SystemExit(
            f"Impossible d'ouvrir une fenêtre {width}x{height} : {exc}\n"
            "Réduis la résolution avec --res 1280x800."
        ) from exc
    appliquer_palette()
    _etat.update(
        construire(width, height, args.seed, args.dist, args.detail, not args.no_lod)
    )
    _etat["ecran"] = "titre"
    _etat["args"] = args
    pyxel.run(update, draw)


if __name__ == "__main__":
    main()
