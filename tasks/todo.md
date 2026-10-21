# PyCraft — tâches

Plan détaillé : [plan.md](plan.md). Intention : [../docs/intent/pycraft.md](../docs/intent/pycraft.md).
Direction : faces projetées + chunks + greedy meshing + LOD, **1280×800** (max 1920×1200),
**60 fps**, 100 % Python + numpy.

## Phase 0 — Fondations

- [ ] **T1 · Spike perf verrouillé**
  - [ ] 1920×1200 + dist 120 : frame ≤ 16 ms
  - [ ] 1280×800 + dist 96 : frame ≤ 8 ms
  - [ ] aucune fissure T-junction sur capture
  - [ ] chiffres consignés dans `docs/ideas/pycraft.md`
- [ ] **T2 · Squelette du dépôt**
  - [ ] git init + remote PyCraft
  - [ ] `pyxel`, `numpy`, `pytest` installés ; `.gitignore` complet
  - [ ] `import pycraft` OK, pytest vert
  - [ ] premier commit
- [ ] **T3 · Monde de voxels**
  - [ ] bytearray 256×256×32, get/set/solid
  - [ ] génération seedée < 150 ms, spawn sûr
  - [ ] ≥ 5 tests

### Checkpoint Fondations
- [ ] tests verts · perf validée · revue humaine

## Phase 1 — Rendu

- [ ] **T4 · Caméra + projection numpy + clipping**
  - [ ] point devant → centre ; derrière → exclu
  - [ ] face à cheval sur le plan proche → **découpée**
  - [ ] horizon à H/2 si pitch=0
  - [ ] tests unitaires
- [ ] **T5 · Mesher détail par chunk**
  - [ ] chunk 16×16 < 5 ms, monde < 300 ms
  - [ ] seul le chunk modifié est reconstruit
  - [ ] bloc isolé = 6 faces
- [ ] **T6 · Greedy meshing + LOD**
  - [ ] ≥ 3× moins de quads en terrain plat
  - [ ] aucune fissure détail/fusionné
  - [ ] pas de saut visuel en déplacement continu
  - [ ] chunk plat = 1 quad de dessus
- [ ] **T7 · Ciel, brouillard, palette, texture**
  - [ ] horizon cohérent en rotation
  - [ ] fondu cache la bascule LOD
  - [ ] mouchetures stables (pas de scintillement)

### Checkpoint Rendu
- [ ] 1280×800 @ 60 fps · 1920×1200 @ 30 fps · aucun artefact · revue humaine

## Phase 2 — Interaction

- [ ] **T8 · Déplacement + collisions**
  - [ ] pas de traversée de mur
  - [ ] glissement le long des murs
  - [ ] caméra bornée ; tests unitaires
- [ ] **T9 · Raycast DDA + surbrillance**
  - [ ] 3 cas de test corrects
  - [ ] contour du bloc visé ; < 0,5 ms/frame
- [ ] **T10 · Casser / poser + hotbar**
  - [ ] mise à jour en une frame
  - [ ] jamais de bloc dans le joueur
  - [ ] hotbar 1/2/3 ; rebuild chunk < 5 ms

### Checkpoint Interaction
- [ ] jouable · 60 fps · revue humaine

## Phase 3 — Finition

- [ ] **T11 · Monde riche**
  - [ ] 3 seeds distinctes
  - [ ] relief + eau/sable au spawn
  - [ ] génération + maillage < 1 s
- [ ] **T12 · HUD + écran titre + F3**
  - [ ] titre, aide `H`, réticule centré
  - [ ] F3 : fps + quads
- [ ] **T13 · Réglages résolution/distance/LOD**
  - [ ] `--res`, `--dist`, `--lod`, `--detail`
  - [ ] garde-fou si fenêtre > écran
- [ ] **T14 · Doc + push**
  - [ ] README avec captures
  - [ ] `docs/technique.md`
  - [ ] pytest vert, push `origin/main`

### Checkpoint Livraison
- [ ] 5 min sans crash · 60 fps · push fait · revue finale
