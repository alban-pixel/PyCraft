# PyCraft — Minecraft 3D dans Pyxel (2D)

> Synthèse d'idéation du 21 octobre 2026. Direction retenue : **faces projetées
> (algorithme du peintre)**, 100 % Python.
> Intention source : [docs/intent/pycraft.md](../intent/pycraft.md)

## Problem Statement

**How Might We** faire ressentir un monde Minecraft en vraie 3D — caméra libre,
blocs qu'on casse et pose — avec un moteur qui ne sait dessiner que des rectangles
et des triangles 2D, à 30 fps en Python ?

## Recommended Direction

Un monde de voxels en **`bytearray` plat** (256×256×32), découpé en **chunks de
16×16 colonnes**. Chaque chunk possède un maillage précalculé, reconstruit
seulement quand un bloc y change.

Deux niveaux de maillage (**LOD**) :
- **détail** (rayon proche) : une face par bloc, avec mouchetures de texture ;
- **fusionné** (loin) : *greedy meshing* — les faces coplanaires de même matière
  et même hauteur sont fusionnées en grands quads.

Rendu par **projection vectorisée numpy** de tous les quads visibles, tri par
distance, puis dessin en `pyxel.tri` depuis des **listes Python** (l'accès aux
scalaires numpy coûte cher dans la boucle de dessin).

### Mesures qui fondent ces choix (Pyxel 2.9.9, Mac arm64, fenêtre réelle)

| Étape | 320×200 | 1280×800 | 1920×1200 |
|---|---|---|---|
| Boucle naïve (dict + voisins) | 7,0 ms | 7,3 ms | — |
| Chunks + numpy (7 000 faces) | 8,8 ms | 9,8 ms | — |
| + greedy meshing (1 000 quads) | — | **1,6 ms** | — |
| Monde 256², distance 120 | — | — | **5,2 ms** (193 fps max) |

- La **résolution est presque gratuite** : +0,7 ms de 320×200 à 1280×800, car
  SDL2/Metal (GPU) fait le remplissage. Le coût est côté Python.
- Le **tri** coûte 0,1–0,5 ms ; le **gather** 0,1–0,4 ms.
- **Threads inutiles** : 6,5 ms en 1 thread comme en 8 (GIL). Mesuré, pas supposé.
- Le GPU n'est pas pilotable depuis Pyxel (pas de shaders) : il rasterise, c'est tout.

### Cible retenue

| Réglage | Valeur par défaut | Maximum mesuré |
|---|---|---|
| Résolution | **1280×800** | 1920×1200 |
| Render distance | **96 blocs** | 120 (monde 256²) |
| LOD détail | 24 blocs | 32 |
| FPS | 60 | > 190 en pointe |

## Key Assumptions to Validate

- [ ] **Perf en fenêtre réelle** : 1920×1200 + distance 120 tiennent à 60 fps
      (5,2 ms mesurés en prototype ; à confirmer avec LOD et monde complet).
- [ ] **Pas de fissures visibles** entre quads fusionnés (T-junctions) au LOD lointain.
- [ ] **Tri par centroïde suffisant** : pas d'artefacts visibles entre faces
      adjacentes d'un monde aligné sur la grille → capture d'écran de contrôle.
- [ ] **Palette 16 couleurs lisible** : herbe / terre / pierre / bois / sable se
      distinguent → revue visuelle avant d'ajouter des blocs.
- [ ] **Monde 32×32×12 suffisant** : sensation d'explorer sans streaming.

## MVP Scope

- Monde généré (seed fixe) 32×32, hauteurs 2–12, arbres, relief.
- Caméra 1ʳᵉ personne : ZQSD + flèches (souris si Pyxel le permet proprement).
- Collisions AABB simples avec le terrain.
- Visée par raycast DDA, surbrillance du bloc visé.
- Casser (clic) / poser (clic droit ou touche) 3 types de blocs.
- Ciel dégradé, soleil, brouillard de distance, HUD minimal (réticule, bloc actif).
- **1280×800** par défaut (jusqu'à 1920×1200), 60 fps visés.

## Not Doing (and Why)

- **Raycast par pixel** — 2× plus de code, numpy, marge CPU divisée ; gardé en
  réserve si le rendu low-poly déçoit.
- **Gravité / saut / chute** — la caméra flottante suffit à la démo, les
  collisions verticales coûtent cher en réglages pour zéro gain visuel.
- **Survie, mobs, craft, inventaire complet** — aucun effet « waouh », beaucoup de
  temps.
- **Monde infini / chunks** — hors sujet pour une démo de 3 minutes.
- **Textures bitmap importées** — palette 16 couleurs + mouchetures suffisent,
  pas de pipeline d'assets.
- **Sauvegarde, multijoueur, son** — aucun jury ne les verra.
- **Z-buffer** — le tri du peintre suffit sur une grille alignée ; un z-buffer
  imposerait un rendu logiciel par pixel.

## Open Questions

- Date exacte de rendu (fenêtre de 2–4 semaines) ?
- Push sur `https://github.com/alban-pixel/PyCraft.git` : as-tu les identifiants
  configurés sur cette machine, ou tu pousses toi-même ?
- Souris pour la caméra : Pyxel expose `mouse_x/mouse_y` mais le delta relatif
  reste à vérifier → si ça accroche, flèches uniquement.

## Spike T1 — réglages verrouillés (21/10/2026)

| Configuration | Mesure réelle | Cible | Verdict |
|---|---|---|---|
| 1280×800, distance 96, détail 16 | **3,57 ms** (280 fps max) | ≤ 16,7 ms | ✅ |
| 1920×1200, distance 120, détail 24 | **5,53 ms** (181 fps max) | ≤ 33 ms | ✅ |
| Génération + maillage greedy 256² | ~196 ms | ≤ 1 s | ✅ |

- **Fissures T-junction** : supprimées par recouvrement de **0,02 bloc** des quads
  fusionnés dans leur plan (voir `docs/images/spike_1280x800.png`).
- **Décision** : rayon de détail = 16 blocs, distance de vue par défaut = 96.
- Le maillage détail se construit paresseusement, chunk par chunk.
