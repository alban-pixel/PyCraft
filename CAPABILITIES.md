# Capability Map : PyCraft v2 — jeu complet, rendu GPU

> Approuvée le 21 octobre 2026. Index des specs de modules.
> `SPEC.md` décrit le produit ; chaque module a sa spec `SPEC-<id>.md`.

## Objectif de l'initiative

Passer de la démo voxel actuelle (rendu CPU, créatif minimal) à un **jeu
complet** — survie **et** créatif — avec un rendu de type *shader pack* Minecraft,
quantifié sur une palette indexée de 256 couleurs Pyxel (rendu rétro assumé ; 16 couleurs en repli).

## Carte

| Module id | Responsabilité | Dépend de |
|---|---|---|
| `gpu-render` | renderer GLSL (OpenGL 4.1 via moderngl), framebuffer indexé 256 couleurs, readback dans Pyxel, eau, brouillard, ciel | world, mesher |
| `render-fx` | cycle jour/nuit, AO cuit, tramage fin, post-traitement, HUD enrichi | gpu-render |
| `world-sim` | blocs variés, biomes, structures, eau qui coule, météo, horloge | world |
| `audio` | sons procéduraux (pas, casse, pose), ambiance, musique | — |
| `survival` | vie, faim, dégâts, mort/respawn, règles de jeu | player, world-sim |
| `inventory-craft` | inventaire 9 slots, items, craft, recettes | world |
| `mobs` | spawn, IA simple, combat | survival, world |
| `persistence` | sauvegarde/chargement monde + joueur + inventaire | world, survival, inventory-craft |
| `creative` | vol, palette de blocs, casse instantanée | player, inventory-craft |

## Ordre de construction

```
gpu-render → render-fx → world-sim → audio → survival → inventory-craft → mobs → persistence → creative
```

Règles :

- aucune dépendance circulaire ; un module ne connaît que ceux qui le précèdent ;
- le renderer CPU actuel reste disponible (`--cpu`) et doit continuer à passer
  les mêmes tests de scène ;
- une capacité coupée (ex. `mobs`) ne casse pas les autres.

## Interfaces aux frontières

- `gpu-render` expose `GlRenderer.draw(camera, selection)` et
  `GlRenderer.invalidate(x, y)` ; il écrit directement dans `pyxel.screen`.
- `world-sim` étend `World` sans changer `get/set/is_solid`.
- `survival` et `inventory-craft` exposent un état sérialisable (dict) pour
  `persistence`.

## État

| Module | Spec | Plan | Build |
|---|---|---|---|
| gpu-render | `SPEC-gpu-render.md` ✅ | `tasks/plan.md` (11 tâches) | ✅ T1–T11 |
| render-fx | — | — | — |
| world-sim | — | — | — |
| audio | — | — | — |
| survival | — | — | — |
| inventory-craft | — | — | — |
| mobs | — | — | — |
| persistence | — | — | — |
| creative | — | — | — |
