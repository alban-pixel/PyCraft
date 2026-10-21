# NSI-Game

Base de projet Python pour un jeu vidéo rétro avec **[Pyxel](https://github.com/kitao/pyxel)**.

## Prérequis

- Python 3.10+ (testé avec Python 3.14)
- Un environnement virtuel `.venv` déjà créé à la racine du projet

## Installation

```bash
# Depuis la racine du projet
source .venv/bin/activate          # macOS / Linux
pip install -r requirements.txt    # installe pyxel
```

*(Windows : `.venv\Scripts\activate` puis `pip install -r requirements.txt`)*

## Lancer le jeu

```bash
source .venv/bin/activate
python main.py
```

Sans activer le venv, on peut aussi faire : `.venv/bin/python main.py`

## Commandes

| Touche                  | Action              |
| ----------------------- | ------------------- |
| Flèches / ZQSD / WASD   | Déplacer le vaisseau|
| Espace                  | Tirer               |
| R                       | Recommencer         |
| Échap                   | Quitter             |

## Structure du projet

```
NSI-Game/
├── .venv/            # environnement virtuel (non versionné)
├── main.py           # point d'entrée + jeu
├── requirements.txt  # dépendances (pyxel)
├── .gitignore
└── README.md
```

## Comment ça marche

Pyxel fonctionne avec deux fonctions appelées automatiquement à chaque image (30 FPS ici) :

- `update()` : la **logique** (lecture des touches, déplacement, collisions)
- `draw()` : l'**affichage** (dessin des formes)

Dans `main.py` :

- `Jeu` contient l'état de la partie (vaisseau, tirs, étoiles, score).
- `Etoile` et `Tir` sont des petites classes d'objets du jeu.
- La classe `Jeu` est prête à être enrichie (ennemis, collision tir–ennemi via `pyxel.pget`, score).

## Idées pour aller plus loin

- Ajouter des ennemis qui descendent et détecter les collisions avec les tirs.
- Ajouter des sons avec `pyxel.sounds` et `pyxel.play`.
- Créer des sprites dans l'éditeur Pyxel et les afficher avec `pyxel.blt`.
