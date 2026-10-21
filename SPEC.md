# Spec : PyCraft v2 — jeu complet, rendu GPU

> Version 2 — 21 octobre 2026. Remplace la v1 (démo voxel, rendu CPU, créatif).
> Statut : **en attente d'approbation**. Carte des capacités :
> [CAPABILITIES.md](CAPABILITIES.md).

## Objective

Transformer la démo voxel actuelle en **jeu complet** — survie **et** créatif —
avec un rendu de type *shader pack* Minecraft : éclairage directionnel, eau
animée, brouillard, cycle jour/nuit, textures procédurales.

Le rendu est calculé par le **GPU** (OpenGL 4.1 via moderngl), quantifié sur une
palette indexée, puis affiché par Pyxel. L'esthétique reste **rétro** : pixels
nets, palette maîtrisée, tramage assumé.

**Pour qui :** Alban (projet NSI) ; le jury, qui doit voir un jeu fini et beau.
**Pourquoi :** la démo actuelle est jouable mais visuellement pauvre ; on veut un
rendu qui marque et un vrai contenu de jeu.

**Succès global :** on peut survivre (vie, faim, dégâts), construire, affronter
des mobs, sauvegarder sa partie, et le tout est beau et fluide.

> **Correction vérifiée** : Pyxel 2.9.9 annonce 16 couleurs, mais son framebuffer
> est 8 bits et sa palette extensible à **256 entrées** (testé en fenêtre réelle :
> 241 couleurs distinctes). Le rendu vise 256 couleurs, avec repli 16.

## Périmètre

Huit modules, détaillés dans [CAPABILITIES.md](CAPABILITIES.md) :

| Module | Contenu |
|---|---|
| `gpu-render` | renderer GLSL, framebuffer indexé, eau, brouillard, ciel |
| `render-fx` | jour/nuit, AO, tramage fin, post-traitement, HUD enrichi |
| `world-sim` | blocs variés, structures, eau qui coule, horloge |
| `survival` | vie, faim, dégâts, mort/respawn |
| `inventory-craft` | inventaire 9 slots, items, craft |
| `mobs` | spawn, IA, combat |
| `persistence` | sauvegarde monde + joueur + inventaire |
| `audio` | sons procéduraux (pas, casse, pose), ambiance, musique |
| `creative` | vol, palette de blocs, casse instantanée |

Ordre : `gpu-render → render-fx → world-sim → audio → survival → inventory-craft →
mobs → persistence → creative`.

**Hors périmètre :** multijoueur, serveur, redstone, villages PNJ, dimensions
multiples (Nether/End), shaders de type ray tracing.

## Capacités Pyxel vérifiées (21/10/2026)

Sondées dans la doc officielle **et** à l'exécution sur cette machine :

| Capacité | Statut | Détail |
|---|---|---|
| Palette 256 couleurs | ✅ vérifié, **non documenté** | `NUM_COLORS=16`, mais `pyxel.colors` s'étend à 256 et les indices 0-255 s'affichent (241 couleurs distinctes mesurées en fenêtre) |
| Indices > 255 | ❌ | `OverflowError` — le framebuffer est 8 bits, 256 couleurs maximum |
| Couleur RGB par pixel | ❌ | les primitives prennent un indice, pas un `0xRRGGBB` |
| Palette modifiable à chaud | ✅ | changer `colors[i]` change l'affichage sans redessiner |
| Résolutions | ✅ | 1920×1200, 2560×1600, 3840×2160 testées (buffer indexé 8,3 Mo en 4K) |
| Fullscreen / mode écran | ✅ | `pyxel.fullscreen()`, `pyxel.screen_mode()` |
| Audio | ✅ | 64 sons, 8 musiques, 4 canaux, `Sound.set(notes, tones, volumes, effects, speed)` |
| Manettes | ✅ | 4 manettes, boutons + axes |
| Police personnalisée | ✅ | `pyxel.Font("fichier.bdf")` |
| Saisie texte | ✅ | `pyxel.set_input_text()` |
| `blt3d` (plan en perspective) | ✅ | warp d'image natif, utile pour un ciel/océan de secours |
| Dithering alpha | ✅ | `pyxel.dither(0..1)` |

Conséquences : **256 couleurs** au lieu de 16, fenêtre jusqu'en 4K, audio natif,
manettes — soit tout ce qu'il faut pour un jeu complet.

## Cible visuelle

Rendu de type *shader pack*, quantifié sur 256 couleurs (rétro assumé) :

- **Ciel** : dégradé horizon/zénith, soleil et lune, étoiles la nuit, nuages
  procéduraux qui défilent, halo autour du soleil.
- **Éclairage** : soleil directionnel, ambiante, **ombres portées** (shadow map),
  occlusion ambiante par sommet, torches (lumières ponctuelles), blocs émissifs.
- **Eau** : vagues animées (normales), reflets du ciel, transparence, brouillard
  et teinte sous-marine.
- **Brouillard** : distance + hauteur, coloré par le ciel, version sous-marine.
- **Météo** : pluie/neige en particules, éclairs, nuages.
- **Post-traitement** : vignette, courbe de couleurs, cycle jour/nuit par palette,
  tramage rétro optionnel.
- **Effets** : particules de casse, balancement de marche, flash de dégâts.

## Tech Stack

| Élément | Version | Rôle |
|---|---|---|
| Python | 3.14.7 (venv) | langage |
| Pyxel | 2.9.9 | fenêtre, entrées, HUD, framebuffer 8 bits |
| moderngl | 5.13.0 | contexte OpenGL 4.1 hors écran (Metal sur macOS) |
| numpy | 2.5.4 | matrices, maillages, readback |
| pytest | 9.1.1 | tests |

Fallback : renderer CPU existant (`--cpu`), 100 % Pyxel, déjà mesuré à 3,4 ms.

## Commands

```bash
# Installation
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt

# Lancer
.venv/bin/python main.py                     # GPU par défaut
.venv/bin/python main.py --cpu               # renderer CPU (fallback)
.venv/bin/python main.py --res 1920x1200 --dist 120 --seed 42
.venv/bin/python main.py --res 2560x1600 --fullscreen

# Tests
.venv/bin/python -m pytest -q                # tests sans GPU
.venv/bin/python -m pytest -q -m gpu         # intégration OpenGL (skippable)

# Benchmark
.venv/bin/python tools/bench.py --renderer gpu --res 1280x800 --dist 96
```

Pas de build ni de lint : projet Python interprété. Vérification = tests +
lancement réel + bench.

## Project Structure

```
main.py                 # boucle, entrées, sélection renderer, état de jeu
pycraft/
  config.py             # constantes, palette 256, types de blocs, items
  world.py              # monde bytearray, génération, blocs
  mesher.py             # maillages détail + greedy, cache
  camera.py             # caméra, projection, clipping
  player.py             # déplacement, collisions, raycast, casser/poser
  hud.py                # réticule, hotbar, aide, écran titre, stats
  renderer.py           # renderer CPU (fallback)
  gl/
    context.py          # contexte moderngl, détection palette, close()
    geometry.py         # packing chunk → VBO
    renderer_gl.py      # GlRenderer
    shaders/*.glsl
  survival.py           # vie, faim, dégâts, respawn        (module survival)
  inventory.py          # inventaire, items, craft           (module inventory-craft)
  mobs.py               # IA, spawn, combat                  (module mobs)
  persistence.py        # sauvegarde JSON + monde binaire    (module persistence)
tests/                  # tests unitaires, un fichier par module
tools/bench.py          # benchmark CPU / GPU
docs/                   # technique, intention, idées
CAPABILITIES.md         # carte des modules (index)
SPEC-gpu-render.md      # spec du module 1
```

## Code Style

Mêmes conventions que la v1 : commentaires et docstrings en français,
identifiants en anglais, types sur les fonctions publiques, fonctions pures
testables, aucun numpy scalaire dans une boucle de dessin Python.

Pour le GPU : GLSL en anglais, uniforms nommés, aucune constante magique dans les
shaders, et **jamais** de création de contexte OpenGL à l'import.

```python
def quantize(couleur: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """Indice de la couleur de palette la plus proche, par pixel."""
    ...
```

## Testing Strategy

- **Sans GPU (par défaut)** : logique pure (monde, maillages, caméra, joueur,
  survie, inventaire, sauvegarde), matrices et packing du renderer, quantification
  de palette. Doit tourner en < 5 s.
- **GPU (`@pytest.mark.gpu`)** : ouverture de contexte, rendu d'une scène de
  contrôle, readback non uniforme. Skippé si le contexte échoue.
- **Visuel** : captures PNG comparées à la main aux checkpoints.
- **Performance** : `tools/bench.py`, cible ≤ 8 ms/frame à 1280×800 pour le GPU et
  ≤ 8 ms pour le CPU.
- **Règle TDD** : tout comportement nouveau arrive avec un test qui échoue d'abord.

## Boundaries

**Toujours :**
- Garder `--cpu` fonctionnel et testé.
- Lancer `pytest` avant chaque commit.
- Détecter la palette étendue au démarrage et replier en 16 couleurs sinon.
- Libérer les ressources GPU (`close()`).
- Mesurer avant d'affirmer une performance.

**Demander avant :**
- Ajouter une dépendance au-delà de moderngl/numpy/pytest.
- Changer l'ordre ou le périmètre des modules.
- Modifier `SPEC.md`, `CAPABILITIES.md` ou une spec de module.
- Introduire une shadow map ou un upscale de résolution interne.

**Jamais :**
- Créer un contexte GL à l'import.
- Rendre la suite de tests dépendante du GPU.
- Casser ou supprimer le renderer CPU.
- Ajouter du gameplay hors périmètre (redstone, Nether, villages).
- Committer `.venv/`, des secrets, ou utiliser `git add -A`.

## Success Criteria

1. Le jeu se lance par défaut en GPU et affiche un monde avec ciel dégradé, eau
   animée, brouillard et éclairage lisible.
2. **1920×1200 : ≤ 6 ms/frame** (rendu + readback + blit), p95 ; **2560×1600 : ≤ 10 ms**.
3. `--cpu` fonctionne toujours et reste ≤ 8 ms à 1280×800.
4. La survie est jouable : vie, faim, dégâts, mort et respawn.
5. L'inventaire et le craft fonctionnent (9 slots, au moins 6 recettes).
6. Au moins 2 types de mobs avec une IA simple et du combat.
6b. Ombres portées visibles, eau animée avec reflets, brouillard et cycle jour/nuit.
6c. Sons de pas, casse, pose et une musique d'ambiance.
7. La sauvegarde recharge le monde, le joueur et l'inventaire à l'identique.
8. Le mode créatif (vol, casse instantanée, palette de blocs) est accessible.
9. La palette 256 est détectée ; en cas d'échec, le jeu tourne en 16 couleurs.
10. `pytest -q` est vert sans GPU ; les tests GPU passent ou sont skippés.

## Open Questions

- **Shadow map** : résolution (1024² ou 2048²) et portée ?
- **Palette 256** : fixe et dessinée à la main, ou générée depuis une image de
  référence puis figée ? (recommandation : générée puis figée)
- **Résolution par défaut** : 1280×800 (compatible tous écrans) ou 1920×1200
  (plus beau, fenêtre possiblement plus grande que l'écran) ?
- **Profondeur de la survie** : faim simulée en continu ou seulement visuelle ?
- **Sauvegarde** : un seul emplacement ou plusieurs slots ?
