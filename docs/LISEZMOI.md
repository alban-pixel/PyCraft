# PyCraft

Jeu de type Minecraft en mode créatif, en vrai 3D : un monde de blocs **infini**, 4096 blocs de
haut, que l'on explore à pied, à la nage ou en volant. Le monde est dessiné par la carte graphique
(OpenGL via `moderngl`), éclairé par le soleil avec des ombres, puis chaque image terminée est
convertie dans la palette de 256 couleurs de **Pyxel**, qui gère la fenêtre, les entrées, les
menus, le HUD, les effets sonores et la musique. Redstone, pistons et TNT fonctionnent, et le jeu
lit les packs de textures au format Minecraft.

Projet NSI. La documentation complète du jeu (contrôles, réglages, fonctionnement) est dans le
[`README.md`](../README.md), en anglais.

## Lancer le jeu

Double-cliquer **`PyCraft.command`** (macOS) ou **`PyCraft.bat`** (Windows) : au premier lancement,
le lanceur crée l'environnement virtuel et installe les dépendances, puis le jeu démarre.

Ou à la main, depuis la racine du dépôt :

```bash
python3 -m venv .venv
.venv/bin/pip install -e .        # Windows : .venv\Scripts\pip install -e .
.venv/bin/python -m pycraft       # Windows : .venv\Scripts\python -m pycraft
```

Desktop uniquement (macOS, Windows, Linux) : `moderngl` a besoin d'un vrai pilote graphique, donc
pas de version web Pyxel.

## Contenu du dépôt

```
pycraft/          le jeu (python -m pycraft)
  app.py          application Pyxel : écrans, entrées, casser/poser, cycle jour/nuit
  terrain.py      génération du terrain : continents, montagnes, rivières, biomes
  world.py        monde : sections à la demande, état des blocs, sauvegarde
  builder.py      processus workers : génération + maillage des chunks
  lod.py          processus d'échantillonnage du terrain lointain
  render/         OpenGL : blocs, terrain lointain, ombres, ciel, palette Pyxel, shaders
  blocks.py       types de blocs, leurs propriétés, la tuile de chaque face
  tiles.py        textures générées par le code
  shapes.py       formes des blocs qui ne sont pas des cubes
  packs.py        packs de textures au format Minecraft
  sim.py          horloge des machines (20 ticks par seconde)
  redstone.py     poudre, torches, répéteurs, leviers, pistons, TNT
  player.py       déplacement, collisions, nage, vol
  controls.py     actions du jeu et leurs touches, modifiables
  ui.py           HUD et menus (thème, boutons, onglets, curseurs)
  noise.py        bruit de Perlin vectorisé
tests/            tests (pytest)
docs/             technique, feuille de route, conceptions (superpowers/), historique (history/)
PyCraft.command   lanceur double-clic macOS
PyCraft.bat       lanceur double-clic Windows
pyproject.toml    dépendances et réglages des tests
```

## Branches

`main` contient tout le jeu et reste toujours jouable. Chaque changement se fait sur une branche
courte, fusionnée par pull request : voir [`CONTRIBUTING.md`](../CONTRIBUTING.md). Les anciennes
branches (`SWE-2`, `m1-pro`, `claude`, `gpu-renderer`, `gpu-renderer-dev`) sont toutes dans
`main` ; leur dernier état est gardé par les tags `archive/…`, et `archive/2d-prototype` garde le
prototype 2D du début (`main.py` NSI-Game à la racine).

## Documentation

- [`README.md`](../README.md) — fonctionnalités, contrôles, réglages, architecture et limites du
  jeu (en anglais).
- [`technique.md`](technique.md) — comment le moteur fonctionne.
- [`roadmap.md`](roadmap.md) — feuille de route vers un jeu de survie complet.
- [`superpowers/`](superpowers/) — conceptions et plans de chaque chantier.
- [`history/`](history/) — l'intention, les idées, la spec et les tâches de l'approche 2D du début.
