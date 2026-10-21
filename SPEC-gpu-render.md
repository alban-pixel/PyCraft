# Spec : module `gpu-render`

> Module 1/8 de [CAPABILITIES.md](CAPABILITIES.md). Statut : **à approuver**.
> Produit : [SPEC.md](SPEC.md).

## Objective

Remplacer le rendu CPU (algorithme du peintre) par un **renderer GPU** qui dessine
la scène voxel en OpenGL 4.1 (via moderngl), la quantifie sur les **16 couleurs**
de Pyxel avec tramage, puis écrit la frame dans le framebuffer de Pyxel.

Résultat attendu : un rendu de type *shader pack* Minecraft — éclairage
directionnel, eau animée, brouillard, ciel dégradé — mais **rétro** (palette
indexée, pixels nets), affiché dans la fenêtre Pyxel, avec les entrées et le HUD
de Pyxel.

> **Correction vérifiée (21/10/2026)** : Pyxel 2.9.9 annonce 16 couleurs
> (`NUM_COLORS = 16`) mais son framebuffer est **8 bits** et sa palette est
> **extensible** : `pyxel.colors.append(...)` puis dessin avec des indices 0-255
> fonctionne. Testé en fenêtre réelle : **241 couleurs distinctes** affichées
> simultanément. On vise donc une **palette de 256 couleurs** (avec repli 16 si
> une future version casse l'extension).

Le renderer CPU existant reste le **fallback** (`--cpu`) et ne doit jamais cesser
de fonctionner.

## Tech Stack

| Élément | Version | Rôle |
|---|---|---|
| Python | 3.14.7 | — |
| Pyxel | 2.9.9 | fenêtre, entrées, HUD, framebuffer indexé |
| moderngl | 5.13.0 | contexte OpenGL 4.1 hors écran |
| numpy | 2.5.4 | matrices, packing, readback |
| pytest | 9.1.1 | tests |

Vérifié sur cette machine : contexte `OpenGL 4.1 Metal`, renderer `Apple M1 Pro`,
readback 1280×800 R8 = **0,64 ms**.

## Architecture

```
ChunkMeshes (existant)                    chaque chunk = (quads, couleurs)
        │
        ▼
GlRenderer
  ├─ geometry.py   → VBO par chunk : position, normale, type de bloc, AO
  ├─ sky.glsl      → plein écran : gradient, soleil, nuages, étoiles
  ├─ terrain.glsl  → opaque : texture procédurale, lumière, brouillard, tramage
  ├─ water.glsl    → eau : vagues animées, teinte, transparence tramée
  └─ readback      → glReadPixels 1 octet/pixel → pyxel.screen.data_ptr()
```

Passes par frame :

1. **Ciel** : plein écran, couleur calculée depuis la direction du rayon.
2. **Opaque** : terrain, tri par chunk (frustum culling conservé côté CPU).
3. **Eau** : maillage eau, sommet déplacé par `sin(t + x·k + y·k)`, alpha tramé.
4. **Readback** : `fbo.read(components=1, dtype='f1')` puis `memmove` dans l'écran.
5. **HUD** : dessiné par Pyxel par-dessus (réticule, hotbar, texte).

### Palette et quantification

Pyxel affiche un **framebuffer indexé 8 bits** : chaque pixel est un indice dans
une palette RGB. La palette est étendue au démarrage à **256 entrées**
(`pyxel.colors`), choisies pour couvrir les rampes utiles : ciel (jour/nuit),
herbe, terre, pierre, sable, bois, feuillage, eau.

Le fragment shader calcule une couleur linéaire, puis choisit l'**indice de
palette le plus proche** (uniform `vec3 palette[256]`). Un **tramage de Bayer
4×4** optionnel (amplitude réglable) peut être ajouté pour l'esthétique rétro ou
si la palette est volontairement réduite (mode 16 couleurs).

Vérification au démarrage : on écrit un indice 200, on relit, et si l'extension
n'est pas honorée, on repasse en mode 16 couleurs avec un avertissement.

### Géométrie

- Un VBO par chunk visible, construit depuis `ChunkMeshes.detail/greedy`.
- Attributs : `position (vec3)`, `face (float 0-5)`, `bloc (float)`, `ao (float 0-1)`.
- `invalidate(x, y)` marque les chunks à re-téléverser (même logique que le cache CPU).
- Pas de shadow map dans le MVP (voir Open Questions).

## Interface

```python
class GlRenderer:
    def __init__(self, world, meshes, width, height,
                 view_distance=96, detail_radius=24) -> None: ...
    def draw(self, camera, selection=None) -> None: ...
    def invalidate(self, x, y) -> None: ...
    def close(self) -> None: ...
    quads: int                 # statistiques F3
    chunks_visibles: int
```

Contrat :

- `draw()` écrit **tout** `pyxel.screen` (aucune zone non couverte).
- `draw()` ne modifie ni `World` ni `ChunkMeshes`.
- Le contexte GL est créé dans `__init__`, jamais à l'import du module.
- Si le contexte échoue, l'exception remonte avec un message explicite ; `main`
  bascule sur le renderer CPU ou demande `--cpu`.

## Commands

```bash
.venv/bin/python main.py                      # GPU par défaut
.venv/bin/python main.py --cpu                # ancien renderer (fallback)
.venv/bin/python main.py --res 1920x1200 --dist 120
.venv/bin/python tools/bench.py --renderer gpu
.venv/bin/python -m pytest -q                 # sans GPU
.venv/bin/python -m pytest -q -m gpu          # intégration GL (peut être skip)
```

## Project Structure

```
pycraft/gl/
  __init__.py        # exporte GlRenderer
  context.py         # création du contexte, gestion d'erreur, close()
  geometry.py        # packing chunk → VBO, cache GPU
  renderer_gl.py     # GlRenderer : passes, uniforms, readback
  shaders/
    sky.vert / sky.frag
    terrain.vert / terrain.frag
    water.vert / water.frag
    common.glsl      # bayer4(), palette(), hash()
tests/
  test_gl_math.py    # matrices, view/proj (sans GL)
  test_gl_geometry.py# packing des sommets (sans GL)
  test_gl_render.py  # intégration, marquée @pytest.mark.gpu
```

## Code Style

- Python : mêmes conventions que l'existant (français commenté, types, fonctions
  pures testables).
- GLSL : noms en anglais, constantes en `#define`, aucun nombre magique dans les
  shaders ; les paramètres passent par des uniforms nommés.

```python
def packing_chunk(verts: np.ndarray, couleurs: np.ndarray) -> np.ndarray:
    """Empaquette les quads d'un chunk en interleaved float32 (position, face, bloc, ao)."""
    ...
```

## Testing Strategy

- **Sans GL (majorité)** : matrices de projection/vue, `bayer4`, quantification
  palette, packing des sommets, cache d'invalidation. Ce sont des tests unitaires
  rapides, exécutés par défaut.
- **Intégration GL** (`@pytest.mark.gpu`) : ouvre un contexte, rend une scène de
  64×64 avec un bloc connu, vérifie que la sortie contient au moins 2 couleurs
  distinctes et que le ciel est en haut. Skippé si le contexte est indisponible.
- **Rendu de référence** : capture PNG comparée à la main aux checkpoints.
- **Performance** : `tools/bench.py --renderer gpu`, cible ≤ 8 ms/frame à 1280×800
  (rendu + readback + blit).

## Boundaries

**Toujours :**
- Garder `--cpu` fonctionnel et testé.
- Libérer les ressources GL (`close()`), y compris en cas d'erreur.
- Écrire la frame dans `pyxel.screen` (jamais dans une autre surface pour l'affichage).
- Mesurer avant d'affirmer une performance.

**Demander avant :**
- Ajouter une dépendance au-delà de moderngl/numpy/pytest.
- Changer la taille de la palette (256, avec repli 16).
- Ajouter une shadow map ou un rendu à résolution interne réduite.
- Modifier ce document.

**Jamais :**
- Créer un contexte GL à l'import d'un module.
- Rendre la suite de tests dépendante du GPU (les tests GL sont marqués et skippables).
- Casser ou supprimer le renderer CPU.
- Écrire dans le framebuffer Pyxel autre chose que la frame finale.

## Success Criteria

1. `python main.py` affiche la scène via le renderer GL, sans régression visible
   par rapport au CPU (terrain, ciel, eau, brouillard).
2. **1280×800 : frame ≤ 8 ms** (rendu + readback + blit), p95 mesuré par le bench.
3. `--cpu` lance toujours le jeu et le bench CPU reste ≤ 8 ms.
4. Une modification de bloc (casser/poser) est visible **à la frame suivante**.
5. Les shaders compilent au démarrage ; en cas d'erreur, message lisible + bascule CPU.
6. Les tests sans GL passent ; les tests GL passent ou sont explicitement skippés.
7. Le ciel contient un dégradé d'au moins **8 teintes**, l'eau ondule avec le temps.
8. La palette étendue (256) est détectée au démarrage ; en cas d'échec, le jeu
   bascule en 16 couleurs sans planter.

## Risks and Mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Contexte CGL indisponible sur une autre machine | High | Bascule CPU automatique + message ; `--cpu` documenté |
| Erreur de compilation GLSL | High | Validation au démarrage, log du shader fautif |
| Readback synchrone lent | Med | Mesuré 0,64 ms ; si besoin, résolution interne réduite |
| Extension de palette non honorée par une future version | Med | Détection au démarrage + repli 16 couleurs |
| Bandes de quantification | Low | 256 couleurs + Bayer optionnel |
| Précision du depth buffer | Med | Plan proche 0,1, far = distance de vue + marge |
| Ordre de transparence de l'eau | Med | Eau rendue après l'opaque, sans écriture de profondeur |

## Open Questions

- **Shadow map** : dans ce module ou dans `render-fx` ? (recommandation : `render-fx`,
  pour garder `gpu-render` livrable vite)
- **Textures** : procédurales (hash) pour le MVP, atlas de textures ensuite ?
- **Palette** : fixe et soignée à la main, ou générée par quantification d'une
  image de référence (médiane/coupes) puis figée ?
- **Résolution interne** : 1:1 avec la fenêtre au départ ; upscale si le budget
  de frame le permet ?
