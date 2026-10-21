# Spec : module `gpu-render`

> Module 1/9 de [CAPABILITIES.md](CAPABILITIES.md). Statut : **à approuver**.
> Produit : [SPEC.md](SPEC.md).

## Objective

Remplacer le rendu CPU par un **renderer GPU** OpenGL 4.1 (moderngl) qui produit
une image de type *shader pack* Minecraft, quantifiée sur la **palette 256
couleurs** de Pyxel, puis écrite dans le framebuffer de Pyxel.

Le rendu doit être **rétro** (pixels nets, palette maîtrisée) mais riche :
ombres portées, eau animée avec reflets, ciel complet, brouillard, météo.

Le renderer CPU (`--cpu`) reste le fallback et ne doit jamais cesser de marcher.

## Tech Stack

| Élément | Version | Rôle |
|---|---|---|
| Python | 3.14.7 | — |
| Pyxel | 2.9.9 | fenêtre, entrées, HUD, framebuffer indexé 8 bits |
| moderngl | 5.13.0 | OpenGL 4.1 hors écran (Metal sur macOS) |
| numpy | 2.5.4 | matrices, packing, readback |
| pytest | 9.1.1 | tests |

Mesures de référence sur cette machine (Apple M1 Pro) :

| Élément | Mesure |
|---|---|
| Contexte GL | `OpenGL 4.1 Metal`, renderer `Apple M1 Pro` |
| Readback 1280×800 | 1,04 ms |
| Readback 1920×1200 | 1,93 ms |
| Readback 2560×1600 | 3,20 ms |
| Palette | 256 entrées vérifiées (indices 0-255) |

## Architecture

```
ChunkMeshes (existant) → geometry.py → VBO par chunk
                                        │
        ┌───────────────────────────────┴───────────────────────────────┐
        │                        GlRenderer                             │
        │  1. shadow pass    → depth map 2048² (soleil)                 │
        │  2. sky pass       → dégradé, soleil/lune, étoiles, nuages    │
        │  3. terrain pass   → textures procédurales, lumière, AO,      │
        │                      ombres, brouillard                       │
        │  4. water pass     → vagues, reflets, transparence, sous-marin│
        │  5. weather pass   → pluie/neige (points GPU)                 │
        │  6. post pass      → vignette, courbe, tramage, palette 256   │
        └───────────────────────────────┬───────────────────────────────┘
                                        │ glReadPixels R8 (1 octet/px)
                                        ▼
                        pyxel.screen.data_ptr()  →  HUD Pyxel par-dessus
```

### Passes

1. **Shadow** : rendu de la profondeur depuis le soleil dans une texture
   2048×2048. Filtrage PCF 3×3 au sampling.
2. **Sky** : plein écran ; direction du rayon → dégradé horizon/zénith, disque
   solaire + halo, lune, étoiles (hash), nuages (bruit fBm animé).
3. **Terrain** : un draw call par chunk visible (frustum culling côté CPU).
   Fragment : texture procédurale par type de bloc et par face (hash 8×8),
   lumière directionnelle + ambiante, AO par sommet, ombre, brouillard distance
   et hauteur.
4. **Eau** : maillage séparé ; sommets déplacés par deux sinus croisés ; normales
   analytiques ; reflet du ciel par approximation de Fresnel ; transparence par
   tramage ordonné ; teinte et brouillard sous-marin si la caméra est dans l'eau.
5. **Météo** : particules instanciées (pluie/neige) autour de la caméra, recyclées
   par modulo ; masquées sous les toits (option simple : test de hauteur).
6. **Post** : vignette, légère courbe de contraste, tramage Bayer optionnel, puis
   **quantification** vers l'indice de palette le plus proche.

### Palette et quantification

Pyxel affiche un framebuffer **8 bits indexé**. On étend `pyxel.colors` à **256
entrées** au démarrage (vérifié, non documenté) avec une palette dessinée pour le
jeu : rampes ciel jour/nuit, herbe, terre, pierre, sable, bois, feuillage, eau,
lave, neige.

Le post pass convertit la couleur linéaire en indice via un LUT 3D de 32³ entrées
(construit une fois au démarrage) : plus rapide qu'un plus-proche-voisin sur 256
couleurs par pixel. En cas d'échec de l'extension de palette, repli 16 couleurs
avec LUT 16 (et message).

### Géométrie et cache

- Un VBO par chunk : `position(vec3)`, `face(float)`, `bloc(float)`, `ao(float)`.
- Cache côté GPU invalidé par `invalidate(x, y)` (même logique que le cache CPU).
- Les chunks hors du cône de vue ne sont pas envoyés (frustum culling CPU).
- LOD conservé : détail près, fusionné loin (moins de triangles).

## Résolution et budget

| Configuration | Cible | Marge mesurée |
|---|---|---|
| 1280×800 (défaut bas) | ≤ 4 ms | readback 1,0 ms |
| **1920×1200 (défaut)** | **≤ 6 ms** | readback 1,9 ms |
| 2560×1600 (haute) | ≤ 10 ms | readback 3,2 ms |

Le GPU rend la scène en quelques ms ; le readback est le coût fixe. On garde
`--cpu` pour les machines sans GL.

## Interface

```python
class GlRenderer:
    def __init__(self, world, meshes, width, height,
                 view_distance=96, detail_radius=24,
                 shadows=True, weather=False) -> None: ...
    def draw(self, camera, selection=None, time=0.0, weather=0.0) -> None: ...
    def invalidate(self, x, y) -> None: ...
    def close(self) -> None: ...
    quads: int
    chunks_visibles: int
```

Contrat :

- `draw()` écrit **tout** `pyxel.screen`.
- `draw()` ne modifie ni `World` ni `ChunkMeshes`.
- Contexte créé dans `__init__`, jamais à l'import.
- En cas d'échec GL, exception explicite ; `main` bascule CPU ou demande `--cpu`.

## Commands

```bash
.venv/bin/python main.py                       # GPU, 1920x1200
.venv/bin/python main.py --res 2560x1600       # haute résolution
.venv/bin/python main.py --cpu                 # fallback CPU
.venv/bin/python main.py --no-shadows          # désactive les ombres
.venv/bin/python -m pytest -q                  # sans GPU
.venv/bin/python -m pytest -q -m gpu           # intégration GL
.venv/bin/python tools/bench.py --renderer gpu --res 1920x1200
```

## Project Structure

```
pycraft/gl/
  __init__.py        # exporte GlRenderer
  context.py         # contexte moderngl, détection palette, close()
  palette.py         # palette 256, LUT 32³, repli 16
  geometry.py        # packing chunk → VBO, cache GPU
  renderer_gl.py     # passes, uniforms, readback
  shaders/
    sky.vert/frag
    terrain.vert/frag
    water.vert/frag
    shadow.vert/frag
    weather.vert/frag
    post.vert/frag
    common.glsl      # hash, bruit, bayer, quantize
tests/
  test_gl_math.py    # matrices view/proj (sans GL)
  test_gl_palette.py # LUT, quantification (sans GL)
  test_gl_geometry.py# packing (sans GL)
  test_gl_render.py  # intégration @pytest.mark.gpu
```

## Code Style

- Python : conventions existantes (français commenté, types, fonctions pures).
- GLSL : anglais, uniforms nommés, constantes `#define`, pas de nombre magique.
- Un fichier de shader = une passe ; `common.glsl` partagé.

## Testing Strategy

- **Sans GL** : matrices, `quantize`, LUT, packing, invalidation, détection de
  palette simulée. Rapides, exécutés par défaut.
- **GL (`@pytest.mark.gpu`)** : contexte, rendu 128×80 d'un bloc connu, readback :
  au moins 3 couleurs distinctes, ciel au-dessus, sol en dessous. Skippé sinon.
- **Captures** : PNG de contrôle aux checkpoints (jour, nuit, eau, pluie).
- **Perf** : bench GPU, cible 1920×1200 ≤ 6 ms.

## Boundaries

**Toujours :**
- Garder `--cpu` fonctionnel et testé.
- Détecter la palette 256 au démarrage, replier en 16 sinon.
- Libérer les ressources GL (`close()`), même en cas d'erreur.
- Écrire la frame dans `pyxel.screen`.
- Mesurer avant d'affirmer une performance.

**Demander avant :**
- Ajouter une dépendance au-delà de moderngl/numpy/pytest.
- Changer la résolution par défaut ou le budget de frame.
- Ajouter un effet qui change l'architecture (SSAO, ray tracing, upscale temporel).
- Modifier ce document.

**Jamais :**
- Créer un contexte GL à l'import.
- Rendre la suite de tests dépendante du GPU.
- Casser ou supprimer le renderer CPU.
- Afficher autre chose que la frame finale dans le framebuffer Pyxel.

## Success Criteria

1. Scène rendue par le GPU à **1920×1200**, **≤ 6 ms** (rendu + readback + blit),
   p95 mesuré par le bench.
2. **Ombres portées visibles** : un bloc isolé projette une ombre au sol.
3. **Eau animée** : vagues en mouvement, reflet du ciel, transparence.
4. **Ciel complet** : dégradé ≥ 8 teintes, soleil + halo, étoiles la nuit.
5. **Brouillard** distance + hauteur, cohérent avec le ciel.
6. **Météo** activable (pluie) sans chute de frame > 2 ms.
7. Une modification de bloc est visible à la frame suivante.
8. Shaders compilés au démarrage ; en cas d'erreur, message lisible + bascule CPU.
9. Palette 256 détectée ; repli 16 sans plantage.
10. `--cpu` et `pytest -q` toujours verts.

## Risks and Mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Contexte CGL indisponible ailleurs | High | Bascule CPU + message, `--cpu` documenté |
| Erreur GLSL | High | Validation au démarrage, log du shader fautif |
| Shadow map mal réglée (acné, peter-panning) | Med | Biais + normal offset, test visuel dédié |
| Readback lent | Med | Mesuré 1,9 ms en 1920×1200 ; résolution réglable |
| Palette non étendue | Med | Détection + repli 16 |
| Transparence de l'eau | Med | Eau après l'opaque, sans écriture de profondeur |
| Effets qui coûtent plus que prévu | Med | Chaque effet a un interrupteur (`--no-shadows`, `--weather off`) |

## Open Questions

- **Ombre** : 2048² fixe, ou 1024² près / 2048² loin (cascade) ?
- **Textures** : procédurales (hash) ou atlas 256×256 chargé depuis une image ?
- **Pluie** : particules GPU instanciées, ou écran-space (plus simple, moins joli) ?
