# `gpu-render` — tâches

Plan : [plan.md](plan.md) · Spec : [SPEC-gpu-render.md](../SPEC-gpu-render.md) ·
Carte : [CAPABILITIES.md](../CAPABILITIES.md).

## Phase 1 — Fondations

- [x] **T1 · Contexte GL et frame dans Pyxel**
  - [x] contexte moderngl + FBO R8
  - [x] readback + memmove dans `pyxel.screen`
  - [x] frame affichée en fenêtre réelle (capture)
  - [x] readback ≤ 1,5 ms en 1920×1200
- [x] **T2 · Palette 256 et quantification**
  - [x] palette du jeu + LUT 32³
  - [x] `quantize` exact (10 000 couleurs aléatoires)
  - [x] détection 256 / repli 16 testé
- [x] **T3 · Matrices et packing**
  - [x] matrices cohérentes avec `Camera.project`
  - [x] packing interleaved (position, face, bloc, ao)
  - [x] cache + invalidation

### Checkpoint Fondations
- [x] frame affichée · palette exacte · géométrie packée · revue humaine

## Phase 2 — Cœur visuel

- [x] **T4 · Terrain pass**
  - [x] monde rendu par le GPU en 1920×1200
  - [x] frame ≤ 6 ms
  - [x] capture ciel/terrain validée
- [x] **T5 · Ciel complet**
  - [x] ≥ 8 indices dans le dégradé
  - [x] soleil + halo, étoiles la nuit
- [x] **T6 · Ombres portées**
  - [x] ombre visible d'un bloc isolé
  - [x] pas d'acné
  - [x] coût ≤ 2 ms

### Checkpoint Cœur visuel
- [x] terrain + ciel + ombres · ≤ 6 ms · captures · revue humaine

## Phase 3 — Eau et finition

- [x] **T7 · Eau animée**
  - [x] vagues animées
  - [x] transparence sans artefact
  - [x] teinte sous-marine
- [x] **T8 · Brouillard + textures**
  - [x] fondu lointain vers le ciel
  - [x] textures procédurales près
- [x] **T9 · Post + palette jour/nuit**
  - [x] vignette + courbe
  - [x] palette interpolée sur 60 s
- [x] **T10 · Intégration et fallback**
  - [x] `--gpu` par défaut, `--cpu` intact
  - [x] erreur GL → message + fallback
  - [x] bench GPU + README
- [x] **T11 · Météo**
  - [x] pluie visible dehors, pas sous un toit
  - [x] ≤ 2 ms

### Checkpoint Module
- [x] critères `SPEC-gpu-render.md` validés
- [x] `pytest -q` vert · push
