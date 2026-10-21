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
    parser.add_argument("--cpu", action="store_true", help="force le renderer CPU (sans OpenGL)")
    parser.add_argument("--no-shadows", action="store_true", help="désactive les ombres (GPU)")
    parser.add_argument("--weather", action="store_true", help="active la pluie (GPU)")
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
    gl=None,
    shadows: bool = True,
) -> dict:
    """Construit le monde, la caméra, le joueur et le renderer."""
    monde = World(seed=seed)
    maillages = ChunkMeshes(monde)
    x, y, z = monde.spawn_point()
    joueur = Player(x, y, z, yaw=0.6, pitch=-0.18)
    camera = Camera(x, y, z + joueur.eye, yaw=0.6, pitch=-0.18, width=width, height=height)
    # --no-lod : un seul niveau de détail, le maillage détaillé partout.
    rayon_detail = float(detail) if lod else float("inf")
    if gl is not None:
        from pycraft.gl.renderer_gl import GlRenderer

        renderer = GlRenderer(
            monde,
            maillages,
            width,
            height,
            view_distance=distance,
            detail_radius=rayon_detail,
            gl=gl,
            shadows=shadows,
        )
    else:
        renderer = Renderer(
            monde,
            maillages,
            width,
            height,
            view_distance=distance,
            detail_radius=rayon_detail,
            use_detail=True,
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
    ancien = etat["renderer"]
    etat.update(nouveau)
    etat["ecran"] = ecran
    try:
        ancien.close()
    except Exception:
        pass


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
        cible = joueur.raycast(monde)
        if joueur.break_block(monde, maillages) and cible:
            renderer.invalidate(cible[0][0], cible[0][1])
    if pyxel.btnp(pyxel.MOUSE_BUTTON_RIGHT):
        cible = joueur.raycast(monde)
        if joueur.place_block(monde, maillages, config.HOTBAR[etat["hotbar_index"]]) and cible:
            renderer.invalidate(cible[0][0], cible[0][1])

    x, y, z = joueur.eye_position()
    camera.set_position(x, y, z)
    camera.set_angles(joueur.yaw, joueur.pitch)
    etat["selection"] = joueur.raycast(monde, 5.0)

    if etat.get("weather") and hasattr(renderer, "rain"):
        # Pas de pluie sous un toit : on teste le bloc au-dessus de la tête.
        couvert = monde.is_solid(
            int(joueur.x), int(joueur.y), int(joueur.z + joueur.height + 1.0)
        )
        renderer.rain = 0.0 if couvert else 1.0


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
    etat["renderer"].draw(
        etat["camera"],
        selection[0] if selection else None,
        time=pyxel.frame_count / 60.0,
    )

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
    gl = None
    if not args.cpu:
        try:
            from pycraft.gl.context import GlContext

            # OBLIGATOIRE : le contexte GL doit être créé avant Pyxel.
            gl = GlContext(width, height)
        except Exception as exc:
            print(f"OpenGL indisponible ({exc}) — bascule sur le renderer CPU.")
            gl = None
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
    if gl is None:
        appliquer_palette()
    try:
        etat = construire(
            width, height, args.seed, args.dist, args.detail, not args.no_lod,
            gl=gl, shadows=not args.no_shadows,
        )
    except Exception as exc:
        if gl is None:
            raise
        print(f"Renderer GPU en échec ({exc}) — bascule sur le renderer CPU.")
        gl.close()
        etat = construire(
            width, height, args.seed, args.dist, args.detail, not args.no_lod,
            gl=None,
        )
    _etat.update(etat)
    _etat["weather"] = bool(args.weather) and hasattr(etat["renderer"], "rain")
    if _etat["weather"]:
        _etat["renderer"].rain = 1.0
    _etat["ecran"] = "titre"
    _etat["args"] = args
    pyxel.run(update, draw)


if __name__ == "__main__":
    main()
