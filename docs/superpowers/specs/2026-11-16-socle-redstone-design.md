# Chantier 2 — Socle et redstone

> Design du 16 novembre 2026, branche `gpu-renderer-dev`. Il réunit le socle commun
> et le chantier redstone de [`docs/roadmap.md`](../../roadmap.md) : les blocs de
> redstone sont les premiers à se servir du socle. Le registre d'objets attend la
> survie, le seul chantier qui s'en sert. Le joueur a dit « fonce » sur cette
> proposition. Les choix ci-dessous sont les miens.

## Intention

Le joueur veut un levier qui marche, et un piston qui sort sa tête au lieu de rester
un cube (ou d'en créer un « fantôme » à côté). Pour ça, il faut au jeu :

- un **état par bloc** (orientation, allumé ou éteint, puissance) ;
- des **formes non cubiques** ;
- une **horloge de ticks** ;
- un moteur de redstone.

## Objectifs

- État `uint8` par bloc, à côté du numéro de bloc, sauvegardé (format v3, les v2 se
  chargent toujours).
- Formes faites de **boîtes** (en 1/16 de bloc), qui peuvent être tournées selon
  6 orientations et inclinées (levier, torche murale), avec des UV prises en partie
  de la tuile.
- Horloge à **20 ticks par seconde**, indépendante des FPS. Des mises à jour de
  blocs sont planifiées ; un bloc qui change prévient ses voisins.
- Blocs de redstone :
  - **levier**, **bouton**, **plaque de pression** ;
  - **poudre de redstone** (puissance 0 à 15), **torche de redstone** (inverseur),
    **répéteur** (1 à 4 crans de retard) ;
  - **lampe**, **piston** et **piston collant** (pousse jusqu'à 12 blocs ; le collant
    tire en revenant), **TNT** (explose 4 s après avoir été alimentée) ;
  - le **bloc de redstone** existant, qui devient une source.
- Un onglet **Redstone** dans l'inventaire. Le clic droit sur un levier, un bouton
  ou un répéteur agit sur ce bloc au lieu de poser.
- Viser et casser selon la forme : on vise la poudre au sol, pas tout le cube, et le
  contour suit la forme.
- Les packs de textures fournissent aussi les nouvelles tuiles.

## Non-objectifs

- Le registre d'objets, les piles et les drops : ce sera la survie.
- Comparateur, observateur, trémie, rails, distributeur actif, portes : plus tard.
- Poudre qui grimpe aux murs *dessinée* : elle se connecte en escalier dans la
  logique, mais seule la partie au sol est dessinée.
- L'animation du piston (il sort d'un coup) et les entités (TNT amorcée qui tombe,
  joueur poussé par un piston).
- La lumière de bloc : la torche et la lampe brillent, mais n'éclairent rien
  (chantier 5).
- Le détail du « quasi-connectivity » et des mises à jour de Minecraft. Le but est
  un comportement prévisible et proche, pas un clone exact.

## Anti-objectifs

- Un monde ou une sauvegarde v2 qui ne se charge plus.
- Des FPS qui baissent : la simulation ne travaille que là où des blocs changent.
- Un circuit qui fige le jeu : une horloge à torches qui boucle sans fin reste
  bornée par tick (plafond de mises à jour par tick, le reste au tick suivant).

## Approches envisagées

| | Approche | Bilan |
|---|---|---|
| A | Numéros de bloc 16 bits, l'état codé dedans | Change chaque table, chaque échange avec les processus, et double la mémoire des sections. Écarté. |
| **B** | **Octet de bloc, plus un tableau d'état `uint8` par section, seulement là où il sert** | **Retenu.** Les sections sans état ne coûtent rien, et les tables par numéro de bloc restent. |
| C | État dans un dictionnaire `(x, y, z) → état` | Simple, mais le maillage vectorisé d'une section ne peut pas le lire en bloc. Écarté. |

Pour les formes : soit des modèles JSON à la Minecraft, soit des boîtes décrites en
Python. **Python retenu** : ce sont une dizaine de formes, et on peut les tester.
Les modèles JSON des packs restent pour plus tard.

## Conception

### État par bloc (`world.py`)

- `World.states : dict[(cx, cy, cz)] -> np.ndarray (16, 16, 16) uint8`, créé à la
  première écriture d'un état non nul.
- `World.get_state(x, y, z) -> int` ; `World.set(x, y, z, block, state=0)` écrit
  les deux.
- **Orientation** : un même codage partout, `FACING = [UP, DOWN, EAST(+x), WEST(-x),
  SOUTH(+z), NORTH(-z)]`, avec 0 = vers le haut. Ainsi un piston ou un levier d'une
  sauvegarde v2 (état 0) regarde vers le haut, comme il était dessiné.
- **Sauvegarde v3** : `state_keys`, `states` et `ticks` (les mises à jour en
  attente) s'ajoutent. Une v2 se charge sans état. Les fours, distributeurs et
  citrouilles gardent leurs numéros tournés : pas de migration.
- **Processus de maillage** : `("set", x, y, z, block, state)`, et le message
  `"world"` transmet aussi les états des sections modifiées.

### Formes (`shapes.py`, nouveau)

- Un modèle est une liste de `Box(lo, hi, tiles, shear=None, kind=None)`, avec `lo`
  et `hi` en 1/16 de bloc dans une orientation de référence (vers le haut), et une
  tuile par face.
- `model(block, state, neighbors) -> list[Box]` : la poudre lit ses voisins pour ses
  connexions. Le modèle est tourné selon l'orientation de l'état.
- **UV automatiques** : chaque face de boîte prend le morceau de tuile qui
  correspond à sa position dans le bloc, comme les modèles de Minecraft. Une tige
  centrale de 2 px montre donc la colonne centrale de la tuile.
- Le **vertex** gagne un champ `uv` (`4u1` : u et v en 1/16, et deux octets libres).
  Le shader prend `v_uv = in_uv.xy / 16` au lieu des coins, et les cubes et les
  plantes écrivent leurs UV comme avant.
- Le maillage (`builder.mesh_section`) : les blocs marqués `SHAPED` passent par
  leurs boîtes. Une face sur le bord du bloc est cachée si le voisin est opaque.
  Pas d'occlusion ambiante pour ces faces. Ces blocs ne sont ni `OPAQUE` ni
  `OCCLUDES`.
- **Teinte** : la poudre prend une couleur rouge selon sa puissance. On passe par le
  canal de teinte du vertex, et sa tuile est grise et entièrement teintée, comme les
  textures de poudre de Minecraft.
- **Boîte de sélection** : `selection_box(block, state)` ; `World.raycast` teste la
  boîte pour les blocs `SHAPED`, et le contour la dessine.
- **Collision** : les blocs à forme ne sont pas solides, sauf la base du piston
  sorti et la tête du piston, qui comptent comme pleins (`SOLID`).
- **Terrain lointain** : `edited_tops` ignore les blocs à forme non solides, comme
  les plantes.

### Horloge et mises à jour (`sim.py`, nouveau)

- `Simulation(world, changed)` : `changed(x, y, z)` prévient le renderer.
  - `tick()` est appelé 20 fois par seconde par `main.update` (accumulateur de
    temps) ;
  - `schedule(pos, delay)` ;
  - `notify(pos)` réévalue le bloc et ses 6 voisins au tick suivant ;
  - au plus **4096 mises à jour par tick**, le reste attend le suivant.
- `set_block(x, y, z, block, state)` : écrit le bloc, appelle `changed`, puis
  `notify` sur les voisins.
- Les mises à jour en attente sont sauvegardées (`ticks`).

### Redstone (`redstone.py`, nouveau)

- **Puissance forte et faible** (version simplifiée de Minecraft) :
  - un levier, un bouton ou une plaque activés donnent 15 au bloc où ils sont fixés
    (puissance forte) et à leurs voisins directs ;
  - une torche allumée donne 15 au bloc au-dessus d'elle (puissance forte) et à
    ses voisins, sauf au bloc qui la porte ;
  - un répéteur donne 15 au bloc devant lui (puissance forte) ;
  - le bloc de redstone donne 15 autour de lui ;
  - la poudre donne sa puissance (puissance faible) au bloc sous elle et au bloc
    vers lequel elle pointe.
- Un bloc plein **fortement** alimenté alimente la poudre voisine. Alimenté
  faiblement, il n'alimente que les composants voisins.
- **Poudre** : sa puissance vaut le maximum entre ce que lui donnent les sources et
  la puissance de la poudre voisine moins 1. Elle se connecte aussi en escalier :
  diagonale haute si le bloc au-dessus n'est pas opaque, diagonale basse si le
  voisin n'est pas opaque. Le recalcul se fait par parcours en largeur sur le réseau
  de poudre touché.
- **Composants** :
  - la lampe s'allume tout de suite et s'éteint après 2 ticks ;
  - la torche s'inverse après 2 ticks, et grille si elle bascule plus de 8 fois en
    60 ticks ; elle se rallume quand on la touche ;
  - le répéteur (entrée derrière lui, sortie devant) attend son retard × 2 ticks ;
  - le piston sort ou rentre après 0 tick ;
  - le TNT explose 80 ticks après avoir été alimenté.
- **Piston** : il pousse jusqu'à 12 blocs. Il ne peut pas pousser la bedrock,
  l'obsidienne, un piston sorti ni une tête. Une plante, une poudre ou un levier sur
  le chemin sont détruits. Une nouvelle tête, `PISTON_HEAD` (état : orientation et
  collant), occupe la case devant. En rentrant, le collant tire le bloc qui est
  devant sa tête.
- **TNT** : il retire les blocs dans une sphère de rayon 4, sauf la bedrock,
  l'obsidienne et l'eau, et allume les TNT touchés (explosion après 10 à 30 ticks).
- **Support** : un levier, un bouton ou une torche dont le bloc porteur disparaît
  se cassent, de même qu'une poudre, une plaque ou un répéteur sans sol.

### Blocs et tuiles (`blocks.py`)

- Nouveaux numéros (à la suite, pour garder ceux des sauvegardes) : `LEVER`,
  `STONE_BUTTON`, `STONE_PRESSURE_PLATE`, `REDSTONE_WIRE`, `REDSTONE_TORCH`,
  `REPEATER`, `REDSTONE_LAMP_OFF` et `PISTON_HEAD`. On reste loin des 256.
- Blocs existants qui changent :
  - `PISTON` et `STICKY_PISTON` lisent leur état ;
  - le `REDSTONE_LAMP` existant devient la lampe allumée ; l'inventaire pose
    `REDSTONE_LAMP_OFF` ;
  - `TNT` explose ;
  - `REDSTONE_BLOCK` alimente ce qui l'entoure.
- Nouvelles tuiles générées : levier, poudre (croix grise), torche allumée et
  éteinte, répéteur éteint et allumé, lampe éteinte, intérieur du piston. On passe
  à environ 204 tuiles, sous les 256.
- Packs : les nouvelles tuiles reçoivent leurs noms 1.8 et 1.13 dans
  `packs.TILE_FILES`.

### Pose et interaction (`main.py`)

- Le clic droit sur un levier le bascule, sur un bouton l'enfonce (20 ticks), et
  sur un répéteur change son retard.
- Pose selon le bloc :
  - levier, bouton et torche se fixent sur la face visée (une torche ne va pas au
    plafond) ;
  - poudre, plaque et répéteur demandent un sol plein, et le répéteur sort vers
    où regarde le joueur ;
  - le piston fait face au joueur, haut et bas compris ;
  - les autres blocs se posent comme avant.
- Pour la plaque de pression, chaque tick regarde si le joueur est dessus.

## Vérification

- **Tests `pytest` sans GL** :
  - état et sauvegarde v2/v3 ;
  - formes : nombre de faces, rotations, UV, sélection ;
  - circuits : levier → poudre → lampe, chute de 1 par bloc, torche inverseuse,
    horloge de torches bornée, répéteur, piston qui pousse, tire, et qui bloque à
    13 blocs, TNT ;
  - support cassé ;
  - plafond de mises à jour.
- **Captures sans fenêtre** : un petit circuit posé par script, levier éteint puis
  allumé, piston rentré puis sorti.

## Laissé au builder

- Les dessins des nouvelles tuiles générées, les coordonnées exactes des boîtes et
  les noms de fichiers dans les packs.
- Le découpage des modules et des commits.
