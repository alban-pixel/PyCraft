# Implementation Plan — module `render-fx`

> Module 2/9 de [CAPABILITIES.md](../CAPABILITIES.md).
> Spec : [SPEC-render-fx.md](../SPEC-render-fx.md).
> Plans précédents archivés : [v1 CPU](../docs/archive/plan-v1-cpu.md),
> [v2 gpu-render](../docs/archive/plan-v2-gpu-render.md).

## Overview

Élever le rendu du « ça marche » au « ça impressionne », **sans quitter la
palette 256**. Douze tâches (T1 déjà livrée), chacune livrable et mesurable seule : aucune ne
dépend d'une autre sauf mention explicite.

Chaque tâche suit le cycle : test GPU rouge → implémentation → suite complète →
mesure de la frame → commit.

## Architecture Decisions

- **Résolution interne `scale`** : le renderer rend dans un FBO `width*scale`,
  puis upscale nearest vers la taille finale. Le HUD Pyxel est dessiné
  **après**, donc jamais pixelisé par l'upscale.
- **AO dans le mesher**, pas dans le shader : le format de sommet contient déjà
  `in_ao` ; ajouter l'occlusion de contact au calcul CPU coûte 0 ms GPU.
- **Motifs par matériau dans le fragment shader**, sélectionnés par une
  uniform `int u_material[16]` : aucun atlas de texture à charger, tout reste
  procédural et reproductible.
- **Particules = nuage de points GPU** (un VBO de N particules, mis à jour côté
  CPU) : quelques centaines de points, coût négligeable.
- **Main / bloc tenu** : géométrie écrite à chaque image dans un petit VBO
  (cube + bras), rendue avec la matrice de projection seule (espace écran).
- **`--no-fx`** coupe post-traitement, tramage et particules : sert de référence
  de comparaison et de plan de secours si les perfs dérapent.
- **Le renderer CPU n'évolue pas** au-delà du partage de helpers ; `--cpu`
  reste le fallback de référence et ses tests sont la garde de non-régression.

## Tasks

### T1 — Contour du bloc visé en GPU ✅
- [x] `pycraft/cube.py` : arêtes partagées CPU/GPU
- [x] shaders `lignes.vert/frag`, passe `gl.LINES` après l'eau
- [x] 2 tests GPU (contour présent, aucune ligne sans sélection)
- **Commit** : `f945496`

### T2 — Textures par type de bloc
- [ ] `u_material[16]` : un identifiant de motif par index de couleur
- [ ] Motifs : herbe (brins verticaux), pierre (éclats), terre (grains),
      planches (lignes horizontales), sable (points), briques (appareil)
- [ ] Variation par bloc (hash sur les coordonnées de bloc) pour éviter le
      copier-coller visuel entre blocs voisins
- [ ] Test GPU : herbe et pierre → distributions de couleurs différentes
- **Critère** : deux matériaux ne partagent pas le même motif

### T3 — Ombres complètes ✅
- [x] `_chunks_autour(centre, rayon)` : chunks sans culling de frustum
- [x] La shadow map est centrée sur la cible de lumière (caméra + 20 blocs)
      et caste tout chunk dans un rayon de 70, plus seulement les visibles
- [x] Test GPU : une tour derrière la caméra projette une ombre devant elle
- **Mesure** : 3,63 ms à 1280×800 (budget 4 ms)

### T4 — Résolution interne réduite + upscale ✅
- [x] `scale` dans `GlRenderer`, FBO de scène à `width*scale`
- [x] Upscale nearest gratuit par la passe de post-traitement
- [x] `--scale N` dans `main.py`
- [x] La shadow map suit la résolution interne (2048 → 1024 à `scale=0.5`)
- [x] Test GPU : ≥ 90 % de blocs 2×2 uniformes à `scale=0.5`
- **Mesure** : 3,58 → 3,29 ms à 1280×800. Pas de division par 4 : la frame
  est limitée par la géométrie et le CPU, pas par le remplissage

### T5 — Lumière horaire ✅
- [x] Le soleil **tourne** (`sun_vector`) : il se lève à l'est, se couche à
      l'ouest, en 120 s — les ombres tournent avec lui
- [x] Ciel, brouillard, teinte et eau suivent l'heure (chaleur à l'aube et au
      crépuscule)
- [x] Rampes de bleu explicites dans la palette (les bleus intermédiaires
      tombaient sur la famille cyan → liserés verts dans le ciel)
- [x] Étoiles uniquement la nuit profonde, nuages non étirés à l'horizon
- [x] Test GPU : la scène de 15 s diffère de celle de 45 s, ombres comprises

### T6 — AO de contact
- [ ] Occlusion de contact dans `mesher.build_detail` (arêtes et coins)
- [ ] Poids plus fort sur les arêtes intérieures que sur les faces
- [ ] Test GPU : un coin intérieur est plus sombre qu'une face plane
- **Critère** : 0 ms GPU ajoutée (mesurée)

### T7 — Tramage fin
- [ ] Bayer 8×8 sur le ciel, le brouillard et les dégradés du post
- [ ] Test GPU : le ciel ne contient pas de bande de plus de N pixels d'une
      même couleur
- **Critère** : plus de *banding* visible dans un ciel dégagé

### T8 — Eau : normales animées + reflet ✅
- [x] Normales perturbées par deux vagues sinus croisées (fréquence ~4/bloc)
- [x] Fresnel + couleur de ciel horaire + reflet spéculaire du soleil
- [x] Eau opaque : en transparence, les ombres du fond se lisaient comme des
      bandes diagonales à travers la palette
- [x] **Bug corrigé** : la passe d'ombres réutilisait la clé de cache « opaque »
      et y stockait le maillage complet, eau comprise — le shader de terrain
      dessinait donc des quads d'eau. Clé `"shadow"` distincte
- [x] Test GPU : l'eau a un reflet (max/moyenne 1,49) et ondule
- **Mesure** : 2,78 ms à 1280×800 (moins de quads dessinés qu'avant)

### T9 — Particules
- [ ] `Particles` : position, vitesse, durée de vie, couleur de bloc
- [ ] Émission à la casse et à la pose ; gravité simple
- [ ] Rendu en `gl.POINTS` dans le FBO de scène
- [ ] Test GPU : casser un bloc change la frame suivante hors du bloc
- **Critère** : visible à l'œil, ≤ 0,3 ms de GPU

### T10 — Main / bloc tenu
- [ ] Cube + bras en bas à droite, matrice écran
- [ ] Couleur = bloc sélectionné dans la hotbar
- [ ] Léger balancement à la marche et au clic
- [ ] Test GPU : changer de slot change la couleur du bloc tenu
- **Critère** : le bloc tenu est identifiable sans le HUD

### T11 — HUD : icônes et écran titre vivant
- [ ] Icônes de blocs dessinées (motif 8×8) au lieu d'aplats
- [ ] Barre de sélection animée
- [ ] Écran titre : le monde tourne en fond, logo et ombre portée
- [ ] Tests Pyxel headless : chaque icône contient ≥ 2 couleurs
- **Critère** : on reconnaît le bloc sans lire son numéro

### T12 — `tools/bench.py` : `--renderer gpu` réellement pris en compte
- [ ] Construire `GlRenderer` quand `--renderer gpu` (aujourd'hui : CPU
      seulement, l'option n'est qu'une étiquette)
- [ ] Afficher le temps de readback séparément du temps de rendu
- [ ] Vérifier le budget des tâches T4/T6/T8 avec ce bench
- **Critère** : `--renderer cpu` et `--renderer gpu` donnent des chiffres distincts

## Ordre d'exécution

```
T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9 → T10 → T11 → T12
```

T12 en dernier pour mesurer tout le reste avec un bench fiable ; en cas de
dérapage de perf, le bench sert d'arbitre.

## Definition of Done

- [ ] `pytest -q` et `pytest -q -m gpu` verts
- [ ] budget tenu à 1280×800 et 1920×1200
- [ ] `--cpu` affiche toujours une scène correcte
- [ ] `--no-fx` et `--scale` documentés dans le README
- [ ] captures avant/après dans `docs/images/`
