# PyCraft — tâches

Plan détaillé : [plan.md](plan.md). Intention : [../docs/intent/pycraft.md](../docs/intent/pycraft.md).
Direction : faces projetées + chunks + greedy meshing + LOD, **1280×800** (max 1920×1200),
**60 fps**, 100 % Python + numpy.

## Phase 0 — Fondations

- [x] **T1 · Spike perf verrouillé**
  - [x] 1920×1200 + dist 120 : frame ≤ 16 ms
  - [x] 1280×800 + dist 96 : frame ≤ 8 ms
  - [x] aucune fissure T-junction sur capture
  - [x] chiffres consignés dans `docs/ideas/pycraft.md`
- [x] **T2 · Squelette du dépôt**
  - [x] git init + remote PyCraft
  - [x] `pyxel`, `numpy`, `pytest` installés ; `.gitignore` complet
  - [x] `import pycraft` OK, pytest vert
  - [x] premier commit
- [x] **T3 · Monde de voxels**
  - [x] bytearray 256×256×32, get/set/solid
  - [x] génération seedée < 150 ms, spawn sûr
  - [x] ≥ 5 tests

### Checkpoint Fondations
- [x] tests verts · perf validée · revue humaine

## Phase 1 — Rendu

- [x] **T4 · Caméra + projection numpy + clipping**
  - [x] point devant → centre ; derrière → exclu
  - [x] face à cheval sur le plan proche → **découpée**
  - [x] horizon à H/2 si pitch=0
  - [x] tests unitaires
- [x] **T5 · Mesher détail par chunk**
  - [x] chunk 16×16 < 5 ms, monde < 300 ms
  - [x] seul le chunk modifié est reconstruit
  - [x] bloc isolé = 6 faces
- [x] **T6 · Greedy meshing + LOD**
  - [x] ≥ 3× moins de quads en terrain plat
  - [x] aucune fissure détail/fusionné
  - [x] pas de saut visuel en déplacement continu
  - [x] chunk plat = 1 quad de dessus
- [x] **T7 · Ciel, brouillard, palette, texture**
  - [x] horizon cohérent en rotation
  - [x] fondu cache la bascule LOD
  - [x] mouchetures stables (pas de scintillement)

### Checkpoint Rendu
- [x] 1280×800 @ 60 fps · 1920×1200 @ 30 fps · aucun artefact · revue humaine

## Phase 2 — Interaction

- [x] **T8 · Déplacement + collisions**
  - [x] pas de traversée de mur
  - [x] glissement le long des murs
  - [x] caméra bornée ; tests unitaires
- [x] **T9 · Raycast DDA + surbrillance**
  - [x] 3 cas de test corrects
  - [x] contour du bloc visé ; < 0,5 ms/frame
- [x] **T10 · Casser / poser + hotbar**
  - [x] mise à jour en une frame
  - [x] jamais de bloc dans le joueur
  - [x] hotbar 1/2/3 ; rebuild chunk < 5 ms

### Checkpoint Interaction
- [x] jouable · 60 fps · revue humaine

## Phase 3 — Finition

- [x] **T11 · Monde riche**
  - [x] 3 seeds distinctes
  - [x] relief + eau/sable au spawn
  - [x] génération + maillage < 1 s
- [x] **T12 · HUD + écran titre + F3**
  - [x] titre, aide `H`, réticule centré
  - [x] F3 : fps + quads
- [x] **T13 · Réglages résolution/distance/LOD**
  - [x] `--res`, `--dist`, `--lod`, `--detail`
  - [x] garde-fou si fenêtre > écran
- [x] **T14 · Doc + push**
  - [x] README avec captures
  - [x] `docs/technique.md`
  - [x] pytest vert, push `origin/main`

### Checkpoint Livraison
- [x] 5 min sans crash · 60 fps · push fait · revue finale
