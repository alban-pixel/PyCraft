"""
PyCraft — Jeu de blocs voxel 3D accéléré par GPU avec Pyxel.

Lancement :
    source .venv/bin/activate
    python main.py

Contrôles :
    Souris / Flèches     : Regarder autour de soi
    WASD / ZQSD          : Déplacement (compatible claviers QWERTY et AZERTY)
    Espace               : Sauter / Nager vers le haut / Monter en vol
    Ctrl gauche          : Courir (Sprint)
    Shift gauche         : Descendre en vol
    F                    : Activer / Désactiver le vol
    Clic gauche          : Casser un bloc (tenir pour répéter)
    Clic droit           : Poser un bloc
    1-9 / Molette        : Choisir le bloc dans la barre d'accès rapide
    E                    : Inventaire de tous les blocs
    Échap                : Menu de pause et paramètres (résolution, FPS, FOV, musique)
    Tab                  : Libérer / capturer la souris
    F3                   : Informations de débogage (FPS, position XYZ, heure, graine)
    H                    : Afficher / masquer l'aide
"""
import importlib.util
import os
import sys

_GPU_DIR = os.path.join(os.path.dirname(__file__), "pycraft-gpu")
if _GPU_DIR not in sys.path:
    sys.path.insert(0, _GPU_DIR)

_gpu_main_path = os.path.join(_GPU_DIR, "main.py")
_spec = importlib.util.spec_from_file_location("pycraft_gpu_main", _gpu_main_path)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["pycraft_gpu_main"] = _mod
_spec.loader.exec_module(_mod)

App = _mod.App

if __name__ == "__main__":
    App().run()
