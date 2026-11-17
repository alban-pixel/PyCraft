# Socle et redstone — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** État par bloc, formes en boîtes, horloge de ticks et redstone (levier, bouton, plaque, poudre, torche, répéteur, lampe, pistons, TNT).

**Architecture:** un tableau d'état `uint8` par section, à côté des numéros de bloc. Les formes sont des boîtes décrites dans `shapes.py`, maillées par `builder.py` avec des UV par vertex. `sim.py` tourne à 20 Hz et `redstone.py` porte la logique, en Python pur, testable sans GL.

**Tech Stack:** Python, numpy, moderngl, Pyxel, pytest.

**Spec:** [`docs/superpowers/specs/2026-11-16-socle-redstone-design.md`](../specs/2026-11-16-socle-redstone-design.md)

## Global Constraints

- Les sauvegardes v2 se chargent toujours ; on écrit en v3 (`SAVE_VERSION = 3`).
- Codage des orientations : `FACING = [UP, DOWN, EAST, WEST, SOUTH, NORTH]`, soit les vecteurs `(0,1,0), (0,-1,0), (1,0,0), (-1,0,0), (0,0,1), (0,0,-1)`, avec 0 = haut.
- Les nouveaux numéros de bloc viennent après les existants. Les numéros de tuile restent ≤ 255.
- Au plus 4096 mises à jour par tick ; 20 ticks par seconde.
- Les tests tournent depuis `pycraft-gpu/` avec `.venv/bin/python -m pytest tests -q`.

## Review Focus

1. **Sauvegarde v2 avec pistons et lampes posés** : ils se chargent, le piston regarde vers le haut, et rien ne plante (tâche 1).
2. **Pack de textures sans les nouvelles tuiles** : les tuiles générées les remplacent (tâche 3).
3. **Horloge de torches** : bornée, le jeu ne fige pas (tâche 5).
4. **Piston face à 12 ou 13 blocs, ou face à de la bedrock** : il pousse ou refuse sans corrompre le monde (tâche 6).
5. **Bloc porteur cassé sous un levier, une poudre ou une torche** : l'élément casse, sans élément flottant (tâche 5).

---

### Task 1: État par bloc, sauvegarde v3, processus

**Files:** `world.py`, `builder.py` (messages `set` et `world`), `renderer.py` (`Chunks.block_changed`, `Builders.set_world`), `lod.py` (le `set_world` du sampler ignore les états) ; tests dans `tests/test_state.py`.

**Produces:**
- `World.states` ;
- `World.get_state(x, y, z) -> int` ;
- `World.set(x, y, z, block, state=0)` ;
- `World.state_section(cx, cy, cz) -> np.ndarray | None` ;
- `blocks.FACING_VECTORS` ;
- `Builders.block_changed(x, y, z, block, state)`.

- [ ] Tests :
  - `test_state_roundtrip` ;
  - `test_set_clears_state` (un `set` sans état remet 0) ;
  - `test_save_v3_keeps_states` ;
  - `test_load_v2_save` (un fichier v2 écrit à la main se charge, avec des états à 0) ;
  - `test_state_only_where_needed` (pas de tableau d'état tant qu'aucun état n'est non nul).
- [ ] Implémenter, puis lancer les tests et une capture en jeu pour vérifier que rien ne change. Commit.

### Task 2: UV par vertex

**Files:** `builder.py` (`VERTEX` gagne `("uv", "u1", 4)`, et `_quads` reçoit les UV), `renderer.py` (format `"3f 4u1 4f1 4u1"`, `in_uv` et `v_uv = vec2(in_uv.xy) / 16.0`).

**Produces:**
- `builder._quads(pos, blocks, tiles, face, tints, i, k, ao, uv=None)` : `uv` de forme `(n, 4, 2)`, en 1/16 ; par défaut, les coins de tuile.

- [ ] Test `test_cube_uvs_are_tile_corners` (un cube de pierre maillé donne des UV dans {0, 16}, dans l'ordre des coins).
- [ ] Implémenter, puis comparer une capture en jeu à la référence (identique). Commit.

### Task 3: Formes, nouveaux blocs et tuiles, visée

**Files:** `shapes.py` (nouveau), `blocks.py` (numéros, noms, tuiles, drapeaux `SHAPED`, `ATTACHED`, `NEEDS_FLOOR`, tuiles dessinées), `builder.py` (maillage des boîtes), `world.py` (`raycast` avec boîtes, `edited_tops`), `renderer.py` (contour), `packs.py` (noms) ; tests dans `tests/test_shapes.py`.

**Produces:**
- `shapes.Box` ;
- `shapes.model(block, state, around) -> list[Box]`, où `around(dx, dy, dz) -> (block, state)` ;
- `shapes.selection_box(block, state) -> (lo, hi)` en blocs ;
- `shapes.box_quads(boxes, x, y, z) -> (pos, uv, tiles, face, kind)` ;
- `world.raycast` retourne les mêmes `(hit, previous)` ;
- `blocks.SHAPED`.

- [ ] Tests :
  - `test_lever_faces` (deux boîtes ; 6 faces chacune, moins les faces cachées) ;
  - `test_rotation_down_is_upside_down` ;
  - `test_auto_uv_matches_position` ;
  - `test_wire_connects_to_neighbors` ;
  - `test_raycast_hits_wire_box_not_cell` (un rayon rasant au-dessus de la poudre passe) ;
  - `test_shaped_ignored_by_edited_tops` ;
  - `test_new_tiles_mapped_in_packs`.
- [ ] Implémenter, puis faire une capture : levier, torche, poudre, répéteur et piston sorti posés à la main. Commit.

### Task 4: Horloge de ticks

**Files:** `sim.py` (nouveau), `main.py` (accumulateur, `Simulation` créée avec le monde, `ticks` sauvegardés) ; tests dans `tests/test_sim.py`.

**Produces:**
- `Simulation(world, changed)`, avec :
  - `.tick()` ;
  - `.schedule(pos, delay)` ;
  - `.notify(pos)` ;
  - `.set_block(x, y, z, block, state=0)` ;
  - `.pending() -> np.ndarray (n, 4)` ;
  - `.load_pending(arr)` ;
- `Simulation.handlers` : `{block: fn(sim, x, y, z, block, state)}`, la réaction d'un bloc à une mise à jour ;
- `MAX_UPDATES = 4096`.

- [ ] Tests :
  - `test_schedule_fires_after_delay` ;
  - `test_set_block_notifies_neighbors` ;
  - `test_update_cap` ;
  - `test_pending_roundtrip`.
- [ ] Implémenter. Commit.

### Task 5: Puissance de redstone

**Files:** `redstone.py` (nouveau), et l'enregistrement de ses handlers ; tests dans `tests/test_redstone.py`.

**Produces:**
- `redstone.power_at(world, x, y, z) -> int` (puissance reçue par un composant) ;
- `redstone.strong_power(world, x, y, z) -> int` ;
- `redstone.update_wire(sim, x, y, z)` ;
- `redstone.install(sim)`, qui enregistre les handlers ;
- `redstone.toggle_lever(sim, x, y, z)` ;
- `redstone.press_button(sim, x, y, z)` ;
- `redstone.cycle_repeater(sim, x, y, z)` ;
- `redstone.set_plate(sim, x, y, z, pressed)`.

- [ ] Tests (petits mondes construits par le test, avec `sim.tick()` répété) :
  - `test_lever_powers_lamp_next_to_it` ;
  - `test_wire_line_decays_and_lights_lamp_at_15_blocks` ;
  - `test_wire_too_long_no_lamp` (17 blocs) ;
  - `test_torch_inverter` ;
  - `test_torch_clock_is_bounded` (il y a des mises à jour à chaque tick, mais jamais au-delà du plafond) ;
  - `test_repeater_delay` ;
  - `test_button_releases_after_20_ticks` ;
  - `test_lever_breaks_without_support` ;
  - `test_wire_breaks_without_floor` ;
  - `test_redstone_block_powers_lamp`.
- [ ] Implémenter. Commit.

### Task 6: Pistons et TNT

**Files:** `redstone.py` (ou `machines.py`) ; tests dans `tests/test_pistons.py`.

**Produces:**
- `push(sim, x, y, z, facing) -> bool` ;
- `retract(sim, x, y, z, facing, sticky)` ;
- `explode(sim, x, y, z, radius=4)`.

- [ ] Tests :
  - `test_piston_extends_with_head` ;
  - `test_piston_pushes_12` ;
  - `test_piston_blocked_at_13` ;
  - `test_piston_blocked_by_bedrock` ;
  - `test_sticky_pulls_back` ;
  - `test_piston_breaks_plant_in_the_way` ;
  - `test_head_removed_on_retract` ;
  - `test_tnt_explodes_after_80_ticks` ;
  - `test_tnt_spares_bedrock`.
- [ ] Implémenter. Commit.

### Task 7: Pose, interaction et inventaire

**Files:** `main.py` (pose orientée, clic droit sur un bloc interactif, onglet Redstone, plaque du joueur à chaque tick) ; tests sur les fonctions pures, dans `tests/test_placement.py`.

**Produces:**
- `placement(block, hit, previous, look, world) -> (block, state) | None`, une fonction pure de `main.py` ;
- `INTERACTIVE = {LEVER, STONE_BUTTON, REPEATER}`.

- [ ] Tests :
  - `test_lever_on_wall_faces_out` ;
  - `test_torch_not_on_ceiling` ;
  - `test_wire_needs_floor` ;
  - `test_repeater_faces_look` ;
  - `test_piston_faces_player`.
- [ ] Implémenter. Capture sans fenêtre : un circuit levier → poudre → lampe et piston, avant et après bascule. Commit.

### Task 8: Docs, revue finale

- [ ] README : liste des blocs, commandes, limites ; `technique.md` : sections État, Formes, Ticks, Redstone ; `roadmap.md` : chantier fait.
- [ ] Suite complète verte, puis revue finale de la branche et corrections. Commit, puis push quand le joueur le demande.
