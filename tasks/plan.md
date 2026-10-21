# Implementation Plan — module `gpu-render`

> Module 1/9 de [CAPABILITIES.md](../CAPABILITIES.md). Spec :
> [SPEC-gpu-render.md](../SPEC-gpu-render.md).
> Le plan v1 (rendu CPU) est archivé : [docs/archive/plan-v1-cpu.md](../docs/archive/plan-v1-cpu.md).

## Overview

Remplacer le renderer CPU par un renderer **OpenGL 4.1** (moderngl) qui rend la
scène voxel avec shaders et ombres, quantifie sur une palette **256 couleurs**
et écrit la frame dans le framebuffer de Pyxel. Le renderer CPU reste le fallback
(`--cpu`).

Ce plan couvre **uniquement ce module**. Les modules `render-fx`, `world-sim`,
`audio`, `survival`, `inventory-craft`, `mobs`, `persistence`, `creative` auront
leur propre plan, écrit après celui-ci.

## Architecture Decisions

- **moderngl + OpenGL 4.1 hors écran** (Metal sur macOS) : mesuré, contexte
  fonctionnel, readback 1,9 ms en 1920×1200.
- **Framebuffer R8** (1 octet/pixel) : le shader de post-traitement sort
  directement un **indice de palette** ; pas de conversion RGB côté Python.
- **Palette 256 étendue au démarrage**, avec LUT 32³ pour la quantification et
  **repli 16 couleurs** si l'extension n'est pas honorée (non documentée).
- **Un VBO par chunk**, construit depuis `ChunkMeshes`, invalidé par
  `invalidate(x, y)` ; LOD détail/fusionné conservé.
- **Six passes** : shadow map, ciel, terrain, eau, météo, post.
- **Aucun appel GL à l'import** ; les tests GPU sont marqués `@pytest.mark.gpu`.
- **Interface commune** avec le renderer CPU : `draw(camera, selection)`,
  `invalidate(x, y)`, `close()`, `quads`, `chunks_visibles`.

## Task List

### Phase 1 — Fondations (risque maximal d'abord)

- [ ] **T1 · Contexte GL et frame dans Pyxel**
  - Contexte moderngl, FBO R8, clear, readback, `memmove` dans `pyxel.screen`.
  - Démo : un écran de couleur unie affiché dans la vraie fenêtre.
  - **Acceptance** : la frame s'affiche ; readback ≤ 2,5 ms en 1920×1200 (mesuré 2,18 ms) ; le HUD
    Pyxel se dessine par-dessus ; `--cpu` intact.
  - **Verify** : test GPU (bytes lus = largeur×hauteur, couleur présente) +
    capture réelle de la fenêtre.
  - **Files** : `pycraft/gl/__init__.py`, `pycraft/gl/context.py`, `requirements.txt`, `tests/test_gl_context.py`.
  - **Scope** : M.

- [ ] **T2 · Palette 256 et quantification**
  - Palette du jeu (rampes ciel/herbe/terre/pierre/eau…), LUT 32³, `quantize`.
  - Détection de l'extension, repli 16.
  - **Acceptance** : `quantize` = plus proche voisin exact sur 10 000 couleurs
    aléatoires ; détection renvoie 256 ici ; repli testé en simulation.
  - **Verify** : `pytest -q tests/test_gl_palette.py`.
  - **Files** : `pycraft/gl/palette.py`, `tests/test_gl_palette.py`.
  - **Scope** : S.

- [ ] **T3 · Matrices et packing géométrie**
  - `view_matrix` / `projection_matrix` depuis `Camera` ; packing des quads en
    interleaved float32 (position, face, bloc, ao) ; cache d'invalidation.
  - **Acceptance** : un point projeté par la matrice tombe au même écran que
    `Camera.project` (± 0,5 px) ; 1 quad isolé produit 6 faces packées aux bonnes
    valeurs ; `invalidate` vide le cache.
  - **Verify** : `pytest -q tests/test_gl_math.py tests/test_gl_geometry.py`.
  - **Files** : `pycraft/gl/math.py`, `pycraft/gl/geometry.py`, tests associés.
  - **Scope** : M.

### Checkpoint : Fondations

- [ ] Frame GPU affichée dans Pyxel.
- [ ] Palette 256 + quantification exactes.
- [ ] Géométrie packée et matrices validées.
- [ ] Revue humaine avant le premier vrai rendu.

---

### Phase 2 — Cœur visuel

- [ ] **T4 · Terrain pass**
  - Shaders terrain, boucle de rendu des chunks, illumination simple, sortie
    palette.
  - **Acceptance** : le monde s'affiche via GPU en 1920×1200 ; frame ≤ 6 ms
    (rendu + readback + blit) ; ciel au-dessus, terrain en dessous.
  - **Verify** : test GPU (pixels ciel/terrain) + capture ; `bench --renderer gpu`.
  - **Files** : `pycraft/gl/renderer_gl.py`, `shaders/terrain.*`, `shaders/common.glsl`, `tests/test_gl_render.py`.
  - **Scope** : L.

- [ ] **T5 · Ciel complet**
  - Dégradé horizon/zénith, soleil + halo, étoiles, nuages procéduraux.
  - **Acceptance** : ≥ 8 indices de palette distincts dans le ciel ; soleil
    présent à la position attendue ; nuit = étoiles visibles.
  - **Verify** : test GPU (comptage d'indices) + captures jour/nuit.
  - **Files** : `shaders/sky.*`, `renderer_gl.py`, `tests/test_gl_render.py`.
  - **Scope** : M.

- [ ] **T6 · Ombres portées**
  - Depth FBO 2048², passe shadow, PCF 3×3, biais.
  - **Acceptance** : un bloc isolé projette une ombre visible ; pas d'acné sur
    une surface plane ; coût ≤ 2 ms.
  - **Verify** : test GPU comparant le sol à l'ombre et au soleil.
  - **Files** : `shaders/shadow.*`, `renderer_gl.py`, `tests/test_gl_render.py`.
  - **Scope** : L.

### Checkpoint : Cœur visuel

- [ ] Terrain, ciel et ombres rendus par le GPU.
- [ ] 1920×1200 ≤ 6 ms.
- [ ] Captures validées à la main.
- [ ] Revue humaine.

---

### Phase 3 — Eau, ambiance, intégration

- [ ] **T7 · Eau animée**
  - Séparation des faces d'eau dans le packing ; shader vagues + Fresnel +
    transparence tramée + teinte sous-marine.
  - **Acceptance** : vagues en mouvement ; transparence sans artefact ; teinte
    quand la caméra est sous l'eau ; coût ≤ 1,5 ms.
  - **Verify** : test GPU (pixels d'eau différents à t et t+1) + captures.
  - **Files** : `shaders/water.*`, `geometry.py`, `renderer_gl.py`, tests.
  - **Scope** : L.

- [ ] **T8 · Brouillard et textures procédurales**
  - Fog distance + hauteur, couleur du ciel ; textures par bloc/face (hash).
  - **Acceptance** : le lointain se fond dans le ciel sans coupure ; les blocs
    sont texturés de près ; pas de bandes franches.
  - **Verify** : test GPU (couleur lointaine ≈ ciel) + captures.
  - **Files** : `shaders/terrain.*`, `shaders/common.glsl`.
  - **Scope** : M.

- [ ] **T9 · Post-traitement et palette jour/nuit**
  - Vignette, courbe de contraste, tramage optionnel ; interpolation de la
    palette sur un cycle de 60 s.
  - **Acceptance** : la palette change progressivement ; la vignette est visible ;
    coût ≤ 1 ms.
  - **Verify** : tests purs (interpolation de palette) + captures jour/nuit.
  - **Files** : `shaders/post.*`, `palette.py`, `renderer_gl.py`, tests.
  - **Scope** : M.

- [ ] **T10 · Intégration, fallback et bench**
  - `--gpu/--cpu`, bascule automatique sur erreur GL, `requirements.txt`
    (moderngl), `tools/bench.py --renderer gpu`, README.
  - **Acceptance** : GPU par défaut ; erreur GL → message + fallback CPU ;
    `--cpu` passe les tests ; bench rapporte les deux.
  - **Verify** : `pytest -q`, `bench --renderer cpu` et `gpu`.
  - **Files** : `main.py`, `tools/bench.py`, `requirements.txt`, `README.md`.
  - **Scope** : M.

- [ ] **T11 · Météo (pluie)**
  - Passe météo (particules), activable/désactivable.
  - **Acceptance** : pluie visible en extérieur, absente sous un toit ; coût ≤ 2 ms.
  - **Verify** : test GPU (pixels de pluie) + capture.
  - **Files** : `shaders/weather.*`, `renderer_gl.py`.
  - **Scope** : M.

### Checkpoint : Module livrable

- [ ] Tous les critères de `SPEC-gpu-render.md` validés.
- [ ] `--cpu` intact, `pytest -q` vert.
- [ ] Réglages par défaut documentés.
- [ ] Revue humaine + push.

## Risks and Mitigations

| Risque | Impact | Mitigation |
|---|---|---|
| Contexte GL indisponible | High | T1 en premier ; fallback CPU automatique |
| Erreur de compilation GLSL | High | Validation au démarrage, log du shader |
| Frame écrite mais non affichée | High | T1 vérifie la fenêtre réelle, pas seulement le buffer |
| Acné d'ombre / peter-panning | Med | Biais + normal offset réglés en T6 |
| Artefacts de transparence d'eau | Med | Eau après l'opaque, sans écriture de profondeur |
| Palette non étendue | Med | LUT de repli 16, testé en T2 |
| Budget de frame dépassé | Med | Effets à interrupteurs, bench à chaque checkpoint |
| Dérive du périmètre | Med | Ce plan ne couvre que `gpu-render` |

## Open Questions

- Ombres : 2048² fixe ou cascades 1024²/2048² ?
- Textures : procédurales (hash) ou atlas 256×256 ?
- Pluie : particules GPU ou écran-space ?
