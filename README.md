# PyCraft

Jeu de type Minecraft en mode créatif, en vrai 3D : un monde de blocs **infini**,
4096 blocs de haut, que l'on explore à pied, à la nage ou en volant. Le monde est
dessiné par la carte graphique (OpenGL via `moderngl`), éclairé par le soleil avec
des ombres, puis chaque image terminée est convertie dans la palette de 256
couleurs de **Pyxel**, qui gère la fenêtre, les entrées, les menus, le HUD, les
effets sonores et la musique.

Projet NSI — la documentation détaillée du jeu est dans
[`pycraft-gpu/README.md`](pycraft-gpu/README.md).

## Lancer le jeu

Le plus simple sur macOS : **double-cliquer `PyCraft.command`**. Au premier
lancement il crée l'environnement virtuel et installe les dépendances, puis le
jeu démarre.

Ou à la main :

```bash
cd pycraft-gpu
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

Desktop uniquement (macOS, Windows, Linux) : `moderngl` a besoin d'un vrai
driver graphique, donc pas de version web Pyxel.

## Contrôles (extrait)

| Touche | Action |
|---|---|
| Souris / flèches | Regarder |
| ZQSD / WASD | Se déplacer |
| Espace | Sauter, nager, monter en volant |
| Ctrl gauche | Sprint (en vol : vitesse rapide) |
| F | Voler / marcher |
| Clic gauche / droit | Casser / poser un bloc |
| 1–9, molette | Choisir le bloc de la hotbar |
| E | Inventaire de tous les blocs |
| Échap | Menu pause (réglages, sauvegarde, quitter) |
| F3 | FPS, position, altitude, biome, seed |

La liste complète est dans `pycraft-gpu/README.md`.

## Contenu du dépôt

```
pycraft-gpu/     # LE JEU : moteur GPU (moderngl) + frontend Pyxel
  main.py        #   application Pyxel : écrans, entrées, casser/poser, cycle jour/nuit
  terrain.py     #   génération du terrain : continents, montagnes, rivières, biomes
  builder.py     #   processus workers : génération + maillage des chunks
  renderer.py    #   OpenGL : shadow maps, LOD lointain, ciel, palette Pyxel
  blocks.py      #   types de blocs, textures (atlas généré)
  world.py       #   monde : sections à la demande, sauvegarde
  player.py      #   déplacement, collisions, nage, vol
  ui.py          #   HUD et menus
  noise.py       #   bruit de Perlin vectorisé
main.py          # ANCIEN prototype NSI-Game (vaisseau Pyxel 2D), conservé
requirements.txt # dépendances du prototype racine
SPEC.md          # spec initiale (approche 2D — voir note de mise à jour en tête)
docs/            # intention, idées, technique
  technique.md   #   architecture réelle du moteur GPU
tasks/           # plan/todo de l'ancienne approche 2D (documents historiques)
PyCraft.command  # lanceur double-clic macOS
```

## Branches

| Branche | Contenu |
|---|---|
| `SWE-2` | **Version de référence.** Tout PyCraft : monde infini, 18 biomes, montagnes de 3 000+ blocs, terrasses de lave et grabens (Iceland), LOD qualité low→ultra, réglages (résolution, fps, distance, graphismes, musique), sauvegarde, sons. 3 processus workers pour le terrain. |
| `m1-pro` | Tout `SWE-2` **+** passage à l'échelle sur les cœurs de la machine : workers = `cpu_count − 4`, requêtes de colonnes réparties sur tous les workers, pool de threads pour l'emballage des meshes et thread dédié pour l'échantillonnage du terrain lointain. Développée sur Mac Apple Silicon. |

Autres branches : `master`/`origin/main` = commit de base documentaire ;
`origin/claude` et `origin/gpu-renderer` = états intermédiaires du moteur GPU ;
`minePy` et `minecraft-python-pyxel` = expériences parallèles autour du moteur
Minecraft Python (sans rapport avec PyCraft).

## Documentation

- [`pycraft-gpu/README.md`](pycraft-gpu/README.md) — fonctionnalités, contrôles,
  réglages, architecture et limites du jeu (en anglais).
- [`docs/technique.md`](docs/technique.md) — comment le moteur GPU fonctionne
  (français).
- [`SPEC.md`](SPEC.md) — spec initiale du projet ; voir la note de mise à jour en
  tête pour l'état réel.
