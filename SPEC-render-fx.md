# Spec — module `render-fx`

> Module 2/9 de [CAPABILITIES.md](../CAPABILITIES.md). Dépend de `gpu-render` (✅).
> Produit de référence : [SPEC.md](../SPEC.md) — objectif « rendu de type
> *shader pack* Minecraft, quantifié sur une palette de 256 couleurs ».

## Objectif

Le module `gpu-render` a rendu le jeu **jouable et correct**. `render-fx` doit le
rendre **impressionnant** : c'est la couche qui fait la différence entre « un
voxel qui tourne » et « un rendu qu'on a envie de montrer ».

Trois principes non négociables :

1. **Rétro assumé.** Aucune couleur hors palette : tout passe par la LUT 256.
   Le pixel art est un choix esthétique, pas une limite subie.
2. **Budget tenu.** 1280×800 ≤ 4 ms de GPU, 1920×1200 ≤ 6 ms. Une animation qui
   coûte 3 ms doit en valoir la peine.
3. **Le CPU reste valide.** `--cpu` doit continuer à afficher une scène cohérente
   (moins belle, mais correcte), et les tests CPU existants doivent passer.

## Périmètre

### Dans le périmètre

| # | Sujet | Pourquoi |
|---|---|---|
| 1 | Contour du bloc visé en GPU | ✅ fait — régression corrigée |
| 2 | Textures par type de bloc | le bruit unique 8×8 rend tous les blocs identiques |
| 3 | Ombres complètes | les chunks hors champ ne projettent rien |
| 4 | Résolution interne réduite + upscale | le levier rétro le plus fort, et le plus rapide |
| 5 | Lumière horaire | aube/crepuscule colorés, ciel et brouillard cohérents |
| 6 | AO de contact | les coins s'assombrissent, la profondeur apparaît |
| 7 | Tramage fin | tue le *banding* de la palette dans le ciel |
| 8 | Eau : normales animées + reflet | l'eau est aujourd'hui une couleur qui oscille |
| 9 | Particules | casser un bloc ne produit rien |
| 10 | Main / bloc tenu | vue première personne sans bras |
| 11 | HUD : icônes et écran titre | la hotbar est faite de rectangles unis |

### Hors périmètre (appartient à un autre module)

- Couleurs **par biome** et nouveaux blocs → `world-sim`.
- Rendu des créatures → `mobs`.
- Cœurs, barre de faim, overlay de dégâts → `survival`.
- UI d'inventaire et de craft → `inventory-craft`.
- Palette de blocs du mode créatif → `creative`.

Un élément de cette liste qui serait implémenté ici serait à refaire : il faut
laisser la place aux modules qui suivent.

## Contrats

- `GlRenderer.draw(camera, selection=None, time=0.0)` — signature inchangée.
- Nouveaux réglages exposés par le renderer (pas de variable globale) :
  `scale` (facteur de résolution interne, défaut 1.0), `fx` (dict de drapeaux).
- Nouvelles options CLI : `--scale N` (0.25 à 1.0), `--no-fx` (coupe tout le
  post-traitement pour comparer).
- Les shaders restent dans `pycraft/gl/shaders/` et sont chargés par `_lire()`.

## Critères d'acceptation

Chaque critère doit être vérifiable par un test GPU (`-m gpu`) ou une mesure :

1. Deux blocs de matériaux différents (herbe / pierre) produisent des motifs
   **distincts** sur la même face, à la même distance.
2. Une tour située **derrière** la caméra projette une ombre devant elle.
3. À `scale=0.5`, l'image est pixelisée par blocs de 2×2 et la frame est plus
   rapide qu'à `scale=1.0`.
4. À 6 h et à 18 h, la teinte du ciel diffère de celle de midi ; le brouillard
   suit la couleur du ciel.
5. Les coins intérieurs sont plus sombres que les faces planes (AO).
6. Le ciel ne présente pas plus de N paliers de couleur d'affilée (tramage).
7. L'eau à `t=0` et `t=1.3` diffère sur plus de pixels qu'aujourd'hui, et sa
   couleur suit celle du ciel.
8. Casser un bloc émet des particules visibles pendant K frames.
9. Le bloc tenu est visible en bas à droite et suit la sélection de la hotbar.
10. La hotbar affiche des icônes de blocs distinctes, pas des aplats.
11. Budget : 1280×800 ≤ 4 ms, 1920×1200 ≤ 6 ms (mesure `tools/bench.py`).

## Risques

| Risque | Parade |
|---|---|
| Le coût des passes ajoutées dépasse le budget | mesurer après **chaque** tâche, pas à la fin |
| L'upscale nearest casse la lisibilité du HUD | HUD dessiné par Pyxel **après** l'upscale, jamais réduit |
| AO calculée côté shader = coûteuse | la calculer une fois dans le mesher, la stocker dans `ao` (déjà dans le vertex format) |
| Textures procédurales « bruit » → aspect TV statique | motifs structurés par matériau (briques, planches, feuilles), pas de bruit pur |
| Le mode `--cpu` diverge | les tests CPU existants sont la garde ; ne pas toucher `renderer.py` hors partage de helpers |
