# Spec : PyCraft

> Version 1 — 21 octobre 2026. Source : [docs/intent/pycraft.md](docs/intent/pycraft.md),
> [docs/ideas/pycraft.md](docs/ideas/pycraft.md), [tasks/plan.md](tasks/plan.md).
> Statut : **approuvée le 21 octobre 2026**.

## Objective

Construire **PyCraft** : un monde de blocs en vraie 3D, en vue première personne,
où l'on se déplace, regarde autour de soi, casse et pose des blocs — rendu avec
les primitives 2D de Pyxel.

**Pour qui :** Alban (projet NSI) ; le professeur / jury découvre le jeu en
quelques minutes de démonstration.

**Pourquoi maintenant :** échéance à 2–4 semaines, aucune grille imposée. C'est
l'effet visuel qui doit marquer, et le code doit pouvoir être expliqué à l'oral.

**Succès global :** à l'ouverture, on voit un paysage de blocs en perspective,
fluide, dans lequel on peut marcher, viser, casser et poser — sans artefact
visible et sans ralentissement.

**Non-objectifs (assumés) :** survie (vie, faim), mobs, craft, inventaire complet,
monde infini en streaming, multijoueur, sauvegarde, sons, packs de textures.

## Tech Stack

| Élément | Version | Rôle |
|---|---|---|
| Python | 3.14.7 (venv local) | langage |
| Pyxel | 2.9.9 | fenêtre, entrées, primitives 2D |
| numpy | 2.5.4 | projection vectorisée, maillages |
| pytest | à installer (`requirements-dev.txt`) | tests |

Cible : macOS arm64 (SDL2 + Metal). Aucune autre plateforme n'est supportée
officiellement.

**Contrainte fondatrice :** Pyxel ne sait dessiner qu'en 2D (`tri`, `rect`,
`blt`, `text`) et n'expose ni shaders ni GPU programmable. La 3D est donc
calculée à la main en Python, puis rasterisée par Pyxel.

## Commands

Toutes les commandes se lancent depuis la racine du projet, avec le venv local.

```bash
# Installation (une fois)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# Lancer le jeu (réglages par défaut : 1280x800, distance 96)
.venv/bin/python main.py

# Lancer en haute qualité
.venv/bin/python main.py --res 1920x1200 --dist 120

# Tests (suite complète)
.venv/bin/python -m pytest -q

# Tests d'un module
.venv/bin/python -m pytest -q tests/test_world.py

# Benchmark reproductible
.venv/bin/python tools/bench.py --res 1280x800 --dist 96
```

Il n'y a **ni build ni lint** : projet Python interprété, sans outil de
compilation. La vérification = tests + lancement réel du jeu.

## Project Structure

```
main.py              # point d'entrée : boucle, entrées, état de jeu
pycraft/
  __init__.py
  config.py          # constantes : résolution, FPS, distance, LOD, palette, types
  world.py           # World en bytearray, get/set/solid, génération seedée
  mesher.py          # maillage détail + greedy, cache par chunk
  camera.py          # caméra, matrice, projection numpy, clipping plan proche
  renderer.py        # culling, LOD, tri, ciel, brouillard, dessin
  player.py          # déplacement, collisions AABB, raycast DDA, casser/poser
  hud.py             # réticule, hotbar, aide, écran titre
tests/
  test_world.py
  test_mesher.py
  test_camera.py
  test_renderer.py
  test_player.py
tools/
  bench.py           # mesure fps (résolution x distance x LOD)
docs/
  intent/pycraft.md  # intention validée
  ideas/pycraft.md   # direction et mesures
  technique.md       # explication des algorithmes (projection, clipping, LOD)
tasks/
  plan.md            # plan d'implémentation
  todo.md            # checklist de suivi
```

Règle de dépendance : `world` et `mesher` n'importent **jamais** `pyxel` ;
`renderer` et `hud` ne modifient **jamais** `World` ; `player` modifie `World`
mais ne dessine rien.

## Code Style

- Commentaires et docstrings **en français**, identifiants en anglais.
- Type hints sur les fonctions publiques.
- Fonctions pures privilégiées pour tout ce qui est testable (projection,
  clipping, fusion de faces) ; les classes portent l'état.
- Pas de numpy dans la boucle de dessin : les coordonnées écran sont converties
  en listes Python avant les appels `pyxel.tri`.

```python
def clip_near(poly: list[tuple[float, float, float]], near: float) -> list[tuple[float, float, float]]:
    """Découpe un polygone 3D contre le plan z = near.

    Retourne une liste vide si le polygone est entièrement derrière la caméra.
    """
    if all(p[2] >= near for p in poly):
        return poly
    if all(p[2] < near for p in poly):
        return []
    ...
```

Conventions : constantes en `MAJUSCULES`, types de blocs en `IntEnum`,
chunks indexés par `(cx, cy)`.

## Testing Strategy

- **Framework :** pytest. Les tests vivent dans `tests/`, un fichier par module.
- **Tests unitaires (majoritaires, « small ») :** logique pure, sans fenêtre
  Pyxel — `world`, `mesher`, `camera`, `player`, fonctions de `renderer`.
  Ils doivent tourner en moins de 2 s.
- **Tests de rendu :** les fonctions pures (projection, clipping, tri, choix de
  couleur) sont testées ; le rendu complet est vérifié par **capture d'écran
  relue manuellement** aux checkpoints, pas par test automatique.
- **Tests de performance :** hors suite pytest par défaut
  (marqueur `@pytest.mark.slow`), exécutés via `tools/bench.py`.
- **Couverture attendue :** chaque module contenant de la logique a des tests ;
  pas d'objectif de pourcentage imposé.
- **Règle TDD :** tout nouveau comportement arrive avec un test qui échoue
  d'abord, sauf configuration pure.

## Performance Budget

Mesures de référence (fenêtre réelle, Mac arm64, monde 256×256×32) :

| Configuration | Cible | Mesuré en prototype |
|---|---|---|
| 1280×800, distance 96, LOD | **≥ 60 fps** (≤ 16,7 ms) | 3,35 ms |
| 1920×1200, distance 120, LOD | **≥ 30 fps** (≤ 33 ms) | 5,21 ms |
| Rebuild d'un chunk après casser/poser | **≤ 5 ms** | — |
| Génération + maillage au démarrage | **≤ 1 s** | ~170 ms |

Contraintes connues : le coût dominant est le nombre d'appels `pyxel.tri`
(~0,6 µs) et la collecte Python ; la résolution est presque gratuite (+0,7 ms de
320×200 à 1280×800). Le threading est **exclu** (GIL, mesuré sans gain).

## Boundaries

**Toujours :**
- Lancer `pytest` avant chaque commit.
- Garder `world`/`mesher` indépendants de Pyxel.
- Commenter en français ; typer les fonctions publiques.
- Mesurer avant d'affirmer une performance.
- Committer une tâche à la fois, avec un message descriptif.

**Demander avant :**
- Ajouter une dépendance (numpy, pytest et pyxel sont déjà approuvés).
- Changer la résolution, la distance ou le LOD par défaut.
- Changer la taille du monde ou des chunks.
- Modifier `docs/SPEC.md` (c'est ce document).
- Toucher à la configuration git/GitHub.

**Jamais :**
- Committer `.venv/`, des secrets, ou `git add -A`.
- Supprimer ou désactiver un test pour faire passer la suite.
- Utiliser `git push --force` ou réécrire l'historique.
- Ajouter du gameplay hors périmètre (survie, mobs, craft, inventaire).
- Lancer du rendering dans des threads.
- Introduire un accès numpy scalaire dans la boucle `pyxel.tri`.

## Success Criteria

1. `python main.py` ouvre une fenêtre **1280×800**, monde 256×256×32 généré,
   et tient **≥ 60 fps en moyenne sur 60 s** de déplacement continu.
2. `--res 1920x1200 --dist 120` tient **≥ 30 fps** sur la même séquence.
3. Le monde est **déterministe** : même seed ⇒ même monde, bloc pour bloc.
4. On se déplace en 1ʳᵉ personne (ZQSD + flèches/souris) ; **impossible de
   traverser un mur** ; la caméra reste dans les bornes.
5. La visée par raycast (portée 5 blocs) **surligne** le bloc ciblé et renvoie
   `None` si rien n'est à portée.
6. Casser (clic gauche) et poser (clic droit, 3 blocs en hotbar) mettent à jour
   le rendu **en une frame** ; jamais de bloc dans le volume du joueur.
7. Aucun artefact visible : pas de triangle géant au clipping, pas de fissure
   entre quads fusionnés, pas de couture nette entre LOD détail et fusionné.
8. La suite `pytest -q` est **verte** ; chaque module testable a ses tests.
9. `README.md` (installation, commandes, captures) et `docs/technique.md`
   (projection, clipping, greedy meshing, LOD, chiffres) sont à jour.

## Décisions actées

1. **Résolution par défaut : 1280×800** ; 1920×1200 disponible via `--res 1920x1200`.
2. **Caméra : clavier + souris.** Souris = delta calculé sur la position
   (`pyxel.mouse(True)`, `mouse_x` / `mouse_y`) ; les flèches restent un secours.
3. **Pas de date de rendu fixe** : rythme libre, une tâche à la fois.
4. **Git** : branche `deepseek` pour le développement, push périodique sur
   `origin` (`alban-pixel/PyCraft`) à chaque étape terminée.
