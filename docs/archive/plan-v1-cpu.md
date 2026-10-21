# Implementation Plan — PyCraft

## Overview

Monde voxel jouable en vue première personne dans Pyxel, rendu par projection de
faces (algorithme du peintre), **1280×800 par défaut (jusqu'à 1920×1200)**,
**render distance 96–120**, **60 fps visés** sur Mac arm64.

Cible : une démo NSI de quelques minutes où l'on marche, regarde, casse et pose
des blocs, sans jamais voir de ralentissement.

Direction validée : [docs/ideas/pycraft.md](../docs/ideas/pycraft.md).
Intention : [docs/intent/pycraft.md](../docs/intent/pycraft.md).

## Architecture Decisions

- **Monde en `bytearray` plat** (index `(z*NY + y)*NX + x`), 256×256×32 ≈ 2 Mo :
  accès O(1), itération rapide, mutations triviales. Plus rapide qu'un dict de
  tuples (mesuré).
- **Chunks de 16×16 colonnes avec maillage en cache** : construire le maillage
  une fois, le reconstruire uniquement quand un bloc du chunk change. C'est ce
  qui rend la render distance possible.
- **Deux LOD** : maillage « détail » (une face par bloc + mouchetures) dans un
  rayon de 24–32 blocs, maillage « fusionné » (*greedy meshing*) au-delà.
  Le brouillard masque la transition. Sans LOD, le détail coûte ~10 ms à
  1280×800 ; avec LOD fusionné au loin, ~1,6 ms.
- **Transformée vectorisée numpy** (matrice 3×3 sur `(N,4,3)`) puis **dessin en
  `pyxel.tri` depuis des listes Python** : l'accès aux scalaires numpy dans la
  boucle de dessin est le piège de perf principal.
- **Clipping au plan proche obligatoire** : sans lui, une face qui traverse la
  caméra projette un triangle géant qui avale l'écran (reproduit sur prototype).
- **Tri par distance au centroïde** (argsort numpy), du plus loin au plus proche.
- **Pas de threading pour le rendu** : le GIL annule tout gain (mesuré : 6,5 ms
  en 1 comme en 8 threads). Les threads ne servent qu'à précalculer un maillage
  en tâche de fond, ce qui n'est pas nécessaire ici (un chunk = ~1 ms).
- **GPU** : Pyxel ne l'expose pas (pas de shaders) ; SDL2/Metal rasterise déjà,
  et la mesure montre que la résolution ne coûte presque rien (+0,7 ms de
  320×200 à 1280×800). Le levier est donc algorithmique, pas GPU.

## Module layout

```
main.py              # point d'entrée, boucle, entrées, état de jeu
pycraft/
  config.py          # constantes (résolution, FPS, distance, LOD, palette)
  world.py           # World bytearray: get/set/solid, génération seedée
  mesher.py          # maillages détail + greedy, cache par chunk
  camera.py          # Camera: position, yaw/pitch, matrice, projection numpy
  renderer.py        # culling par chunk, LOD, tri, ciel, brouillard, dessin
  player.py          # déplacement, collisions AABB, raycast, casser/poser
  hud.py             # réticule, hotbar, textes
tests/               # pytest, logique pure (sans Pyxel)
tools/bench.py       # mesure fps reproductible (résolution x distance x LOD)
```

---

## Phase 0 — Fondations

### Task 1 : Spike de performance verrouillé

**Description :** rejouer le prototype optimisé et figer les réglages cibles.
Mesurer à 1920×1200, monde 256², distance 120, LOD mixte. Vérifier l'absence de
fissures entre quads fusionnés.

**Acceptance criteria :**
- [ ] 1920×1200 + distance 120 : `frame ≤ 16 ms` (60 fps) avec LOD.
- [ ] 1280×800 + distance 96 : `frame ≤ 8 ms`.
- [ ] Aucune fissure (T-junction) visible sur une capture au LOD fusionné.
- [ ] Les chiffres sont consignés dans `docs/ideas/pycraft.md`.

**Verification :** `tools/bench.py --res 1920x1200 --dist 120` ; captures relues.

**Dependencies :** None.

**Files likely touched :** `tools/bench.py`, `spikes/spike_render.py`.

**Estimated scope :** S.

---

### Task 2 : Squelette du dépôt et outillage

**Description :** git init + remote GitHub, structure de modules, dépendances
(`pyxel`, `numpy`, `pytest`), README minimal, remplacement du `main.py`
provisoire.

**Acceptance criteria :**
- [ ] `git init` + remote `origin` = PyCraft.
- [ ] Branche `deepseek` créée et poussée (`push -u origin deepseek`).
- [ ] `.gitignore` couvre `.venv/`, `__pycache__/`, `*.pyc`, `.DS_Store`.
- [ ] `python -c "import pycraft"` passe ; `pytest` vert sur un test bidon.
- [ ] Premier commit créé.

**Verification :** `.venv/bin/python -m pytest -q` ; `git remote -v`.

**Dependencies :** None.

**Files likely touched :** `main.py`, `pycraft/__init__.py`, `pycraft/config.py`,
`requirements.txt`, `requirements-dev.txt`, `.gitignore`, `README.md`, `tests/test_smoke.py`.

**Estimated scope :** S.

---

### Task 3 : Monde de voxels

**Description :** `World` en bytearray 256×256×32, `get/set/solid`, bornes,
génération seedée (relief + arbres + eau), types de blocs. Aucune dépendance à
Pyxel.

**Acceptance criteria :**
- [ ] `get` hors bornes renvoie `AIR` (ou `STONE` sous z=0, à trancher).
- [ ] Deux `World(seed=42)` sont identiques bloc pour bloc.
- [ ] `set` puis `get` renvoie la nouvelle valeur.
- [ ] Génération 256² en < 150 ms ; ≥ 5 tests unitaires.
- [ ] Spawn jamais dans un bloc solide.

**Verification :** `.venv/bin/python -m pytest -q tests/test_world.py`.

**Dependencies :** Task 2.

**Files likely touched :** `pycraft/world.py`, `pycraft/config.py`, `tests/test_world.py`.

**Estimated scope :** M.

---

## Checkpoint : Fondations

- [ ] Tests verts, monde déterministe, spawn sûr.
- [ ] Perf cible validée (T1) — sinon on ajuste distance/résolution **maintenant**.
- [ ] Revue humaine.

---

## Phase 1 — Rendu

### Task 4 : Caméra, projection vectorisée et clipping

**Description :** `Camera` (position, yaw, pitch, fov) exposant une matrice de
projection, une fonction vectorisée `project(points) -> écran + profondeur`, et
le **clipping au plan proche** (les polygones à cheval sont découpés, pas jetés).

**Acceptance criteria :**
- [ ] Un point droit devant se projette au centre de l'écran (± 0,5 px).
- [ ] Un point derrière renvoie `None` / est exclu.
- [ ] Une face à cheval sur le plan proche est **découpée** (pas de triangle géant).
- [ ] `pitch = 0` → horizon à `H/2`.
- [ ] Tests unitaires sur points connus + cas de clipping.

**Verification :** `.venv/bin/python -m pytest -q tests/test_camera.py`.

**Dependencies :** Task 2.

**Files likely touched :** `pycraft/camera.py`, `tests/test_camera.py`.

**Estimated scope :** M.

---

### Task 5 : Mesher détail par chunk

**Description :** pour chaque chunk de 16×16, produire un maillage « détail »
(une face par bloc exposé, couleur par orientation), stocké en tableau numpy et
mis en cache. Reconstruction ciblée quand un bloc change.

**Acceptance criteria :**
- [ ] Maillage d'un chunk 16×16 < 5 ms ; monde complet < 300 ms.
- [ ] Une face n'est émise que si le voisin est vide (pas de faces internes).
- [ ] `set_block` invalide uniquement les chunks voisins concernés.
- [ ] Test unitaire : un bloc isolé produit exactement 6 faces.

**Verification :** `.venv/bin/python -m pytest -q tests/test_mesher.py`.

**Dependencies :** Task 3.

**Files likely touched :** `pycraft/mesher.py`, `tests/test_mesher.py`.

**Estimated scope :** M.

---

### Task 6 : Greedy meshing et LOD

**Description :** produire un second maillage par chunk en fusionnant les faces
coplanaires de même matière et même hauteur en quads. Au rendu, choisir
« détail » sous 24–32 blocs et « fusionné » au-delà. Corriger les T-junctions
(fissures d'un pixel entre un grand quad et des petits) par recouvrement
contrôlé ou maillage cohérent.

**Acceptance criteria :**
- [ ] Réduction du nombre de quads ≥ 3× en terrain plat.
- [ ] Aucune fissure visible entre LOD détail et LOD fusionné (capture de contrôle).
- [ ] La bascule détail/fusionné ne « saute » pas visuellement (test de
      déplacement continu, 60 s).
- [ ] Tests unitaires sur une grille plate : 1 chunk plat = 1 quad de dessus.

**Verification :** `tools/bench.py --lod on/off` ; captures comparées.

**Dependencies :** Task 5, Task 4.

**Files likely touched :** `pycraft/mesher.py`, `pycraft/renderer.py`, `tests/test_mesher.py`.

**Estimated scope :** L → isoler la fusion dans une fonction pure testable.

---

### Task 7 : Ciel, brouillard, palette et texture

**Description :** ciel en dégradé, soleil, nuages, brouillard de distance aligné
sur la couleur du ciel (pour masquer la transition LOD et la fin du monde), et
mouchetures déterministes sur le LOD détail pour l'effet « texture Minecraft ».

**Acceptance criteria :**
- [ ] Horizon cohérent en rotation (pas de bande qui saute).
- [ ] Le fondu de distance cache la bascule LOD.
- [ ] Les 5 matériaux sont distinguables ; les mouchetures ne scintillent pas
      quand on marche (déterministes par position).

**Verification :** captures avant/après ; test unitaire de la couleur de brouillard.

**Dependencies :** Task 6.

**Files likely touched :** `pycraft/renderer.py`, `pycraft/config.py`.

**Estimated scope :** M.

---

## Checkpoint : Rendu

- [ ] Démo statique 1280×800 @ 60 fps, 1920×1200 @ 30 fps minimum.
- [ ] Pas d'artefact de clipping, de tri ou de T-junction.
- [ ] Revue humaine : le rendu « fait Minecraft ».

---

## Phase 2 — Interaction

### Task 8 : Déplacement et collisions

**Description :** `Player` position/yaw/pitch, ZQSD + souris (flèches en secours), collisions AABB
avec glissement le long des murs, caméra bornée au monde. Pas de gravité
(caméra flottante, décision assumée).

**Acceptance criteria :**
- [ ] Impossible de traverser un mur en fonçant dessus.
- [ ] Glissement le long d'un mur en diagonale.
- [ ] Caméra bornée au monde.
- [ ] Tests unitaires de `move()` sur un monde plat avec mur.

**Verification :** `.venv/bin/python -m pytest -q tests/test_player.py` + manuel.

**Dependencies :** Task 3.

**Files likely touched :** `pycraft/player.py`, `tests/test_player.py`.

**Estimated scope :** M.

---

### Task 9 : Visée par raycast DDA

**Description :** raycast 3D (Amanatides & Woo) depuis la caméra, portée 5 blocs,
retourne case touchée + normale. Surbrillance du bloc visé.

**Acceptance criteria :**
- [ ] 3 cas de test corrects sur un monde connu.
- [ ] `None` si rien à portée.
- [ ] Le contour suit le bloc en tournant ; coût < 0,5 ms/frame.

**Verification :** `.venv/bin/python -m pytest -q tests/test_player.py`.

**Dependencies :** Task 8.

**Files likely touched :** `pycraft/player.py`, `pycraft/renderer.py`, `tests/test_player.py`.

**Estimated scope :** M.

---

### Task 10 : Casser / poser + hotbar

**Description :** clic gauche = casser, clic droit = poser le bloc actif ;
hotbar 1/2/3 ; refus de poser dans le joueur ; reconstruction du maillage des
chunks touchés (< 5 ms).

**Acceptance criteria :**
- [ ] Casser/poser met à jour le rendu immédiatement (une frame).
- [ ] Jamais de bloc dans le volume du joueur.
- [ ] La hotbar change la couleur posée.
- [ ] Tests unitaires casser/poser + refus.

**Verification :** `.venv/bin/python -m pytest -q tests/test_player.py` + manuel.

**Dependencies :** Task 9, Task 6.

**Files likely touched :** `pycraft/player.py`, `pycraft/hud.py`, `main.py`, `tests/test_player.py`.

**Estimated scope :** M.

---

## Checkpoint : Interaction

- [ ] Marcher, viser, casser, poser — sans casser les 60 fps.
- [ ] Revue humaine.

---

## Phase 3 — Finition

### Task 11 : Monde plus riche

**Description :** relief varié, arbres, eau/sable, seed affiché et relançable
avec `R` ; spawn choisi sur un point de vue intéressant.

**Acceptance criteria :**
- [ ] 3 seeds donnent 3 mondes distincts.
- [ ] Relief > 6 blocs et eau/sable visibles depuis le spawn.
- [ ] Spawn sûr ; génération + maillage < 1 s (écran de chargement).

**Verification :** captures des 3 seeds ; test « spawn non solide ».

**Dependencies :** Task 3, Task 7.

**Files likely touched :** `pycraft/world.py`, `pycraft/config.py`, `tests/test_world.py`.

**Estimated scope :** M.

---

### Task 12 : HUD, écran titre, contrôles

**Description :** réticule, hotbar, aide `H`, écran titre, `R` relance,
`Échap` quitte, affichage FPS optionnel (`F3`).

**Acceptance criteria :**
- [ ] Écran titre + « Entrée ».
- [ ] Aide qui s'efface puis revient avec `H`.
- [ ] Réticule centré quelle que soit la résolution ; aucun débordement.
- [ ] `F3` affiche fps + nombre de quads.

**Verification :** captures ; test manuel.

**Dependencies :** Task 10.

**Files likely touched :** `pycraft/hud.py`, `main.py`.

**Estimated scope :** S.

---

### Task 13 : Réglages qualité / résolution / distance

**Description :** fichier de config ou arguments CLI (`--res`, `--dist`,
`--lod`, `--detail`) ; valeurs par défaut 1280×800 / 96 / LOD on ; messages
d'erreur si la résolution dépasse l'écran.

**Acceptance criteria :**
- [ ] `--res 1920x1200 --dist 120` fonctionne sans erreur.
- [ ] Valeurs par défaut = celles du plan.
- [ ] Le jeu ne démarre pas si la fenêtre dépasse l'écran (message clair).
- [ ] `README` documente les options.

**Verification :** lancement avec 3 combinaisons ; `pytest` vert.

**Dependencies :** Task 12.

**Files likely touched :** `pycraft/config.py`, `main.py`, `README.md`.

**Estimated scope :** S.

---

### Task 14 : Documentation, démo et push

**Description :** README final avec captures, `docs/technique.md` (projection,
clipping, greedy meshing, LOD, chiffres de perf), benchmark reproductible, push
GitHub.

**Acceptance criteria :**
- [ ] README avec 2 captures et commandes exactes.
- [ ] `docs/technique.md` explique projection + clipping + greedy + LOD en 2 pages.
- [ ] `pytest` vert, `python main.py` démarre sans erreur.
- [ ] Push sur `origin/main` (ou instructions si credentials absents).

**Verification :** `pytest -q` ; `git log --oneline -5` ; relecture README.

**Dependencies :** Tasks 11–13.

**Files likely touched :** `README.md`, `docs/technique.md`.

**Estimated scope :** S.

---

## Checkpoint : Livraison

- [ ] Tests verts, démo 5 min sans crash.
- [ ] 1280×800 @ 60 fps et 1920×1200 @ 30 fps.
- [ ] Push GitHub fait ; revue finale.

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Perf réelle < cible en scène dense | High | T1 verrouille les réglages ; LOD et distance ajustables ; mesure avant chaque phase |
| Fissures T-junction entre quads fusionnés | Med | Recouvrement contrôlé ou maillage cohérent ; test visuel dédié en T6 |
| Couture visible entre LOD détail et fusionné | Med | Brouillard aligné sur le ciel ; chevauchement des rayons ; test de déplacement continu |
| Bug de clipping (triangle géant) | High | `clip_near()` isolée et testée dès T4 |
| Accès numpy dans la boucle de dessin | High | Toujours convertir en listes avant la boucle ; bench dédié |
| Fenêtre 1920×1200 plus grande que l'écran | Low | Défaut 1280×800 ; garde-fou au démarrage |
| Dérive du périmètre | Med | « Not Doing » fait foi ; tout ajout remplace une tâche |

## Décisions

- **Résolution par défaut : 1280×800** (1920×1200 via `--res`).
- **Contrôles : clavier (ZQSD) + souris** pour la caméra, flèches en secours.
- **Pas de date de rendu fixe.**
- **Git : branche `deepseek`**, push périodique sur `origin` à chaque étape.
