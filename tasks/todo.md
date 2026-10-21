# `gpu-render` — tâches

Plan : [plan.md](plan.md) · Spec : [SPEC-gpu-render.md](../SPEC-gpu-render.md) ·
Carte : [CAPABILITIES.md](../CAPABILITIES.md).

## Phase 1 — Fondations

- [ ] **T1 · Contexte GL et frame dans Pyxel**
  - [ ] contexte moderngl + FBO R8
  - [ ] readback + memmove dans `pyxel.screen`
  - [ ] frame affichée en fenêtre réelle (capture)
  - [ ] readback ≤ 1,5 ms en 1920×1200
- [ ] **T2 · Palette 256 et quantification**
  - [ ] palette du jeu + LUT 32³
  - [ ] `quantize` exact (10 000 couleurs aléatoires)
  - [ ] détection 256 / repli 16 testé
- [ ] **T3 · Matrices et packing**
  - [ ] matrices cohérentes avec `Camera.project`
  - [ ] packing interleaved (position, face, bloc, ao)
  - [ ] cache + invalidation

### Checkpoint Fondations
- [ ] frame affichée · palette exacte · géométrie packée · revue humaine

## Phase 2 — Cœur visuel

- [ ] **T4 · Terrain pass**
  - [ ] monde rendu par le GPU en 1920×1200
  - [ ] frame ≤ 6 ms
  - [ ] capture ciel/terrain validée
- [ ] **T5 · Ciel complet**
  - [ ] ≥ 8 indices dans le dégradé
  - [ ] soleil + halo, étoiles la nuit
- [ ] **T6 · Ombres portées**
  - [ ] ombre visible d'un bloc isolé
  - [ ] pas d'acné
  - [ ] coût ≤ 2 ms

### Checkpoint Cœur visuel
- [ ] terrain + ciel + ombres · ≤ 6 ms · captures · revue humaine

## Phase 3 — Eau et finition

- [ ] **T7 · Eau animée**
  - [ ] vagues animées
  - [ ] transparence sans artefact
  - [ ] teinte sous-marine
- [ ] **T8 · Brouillard + textures**
  - [ ] fondu lointain vers le ciel
  - [ ] textures procédurales près
- [ ] **T9 · Post + palette jour/nuit**
  - [ ] vignette + courbe
  - [ ] palette interpolée sur 60 s
- [ ] **T10 · Intégration et fallback**
  - [ ] `--gpu` par défaut, `--cpu` intact
  - [ ] erreur GL → message + fallback
  - [ ] bench GPU + README
- [ ] **T11 · Météo**
  - [ ] pluie visible dehors, pas sous un toit
  - [ ] ≤ 2 ms

### Checkpoint Module
- [ ] critères `SPEC-gpu-render.md` validés
- [ ] `pytest -q` vert · push
