# Chantier 2 — Survie

> Design du 16 novembre 2026, branche `gpu-renderer-dev`, validé par le joueur
> (« valide, fonce »). La faim est **reportée** au chantier des animaux. Les objets
> au sol attendent les entités (chantier 5) : ce qu'on casse va dans l'inventaire.

## Intention

Faire de PyCraft un jeu de survie. On commence sans rien : on casse avec le temps
qu'il faut, on ramasse, on fabrique des outils, on cuit au four, et on peut mourir.
Le mode Créatif d'aujourd'hui reste disponible.

## Objectifs

- Un **registre d'objets** : les blocs (numéros 0 à 255) plus des objets à partir
  de 256. Les cases contiennent des piles.
- **Mode** choisi à la création du monde (Survie ou Créatif) et sauvegardé.
- **Casse** avec un temps qui dépend de la dureté et de l'outil, le bon niveau
  d'outil exigé, et les **drops** de Minecraft 1.8.
- **Outils** : pioche, hache et pelle en bois, pierre, fer, or et diamant, avec leur
  usure.
- **Craft** : une grille 2×2 dans l'inventaire et 3×3 dans l'établi, environ
  70 recettes.
- **Four** : cuisson, combustibles, contenu sauvegardé, four allumé.
- **Vie** : 10 cœurs, chute, noyade, régénération lente, mort et réapparition.
- **Interface** : écrans inventaire, établi et four ; cœurs et bulles dans le HUD.
- **Icônes d'objets** générées, et lues dans les packs.

## Non-objectifs

- La faim et la nourriture (la pomme existe, mais ne se mange pas encore).
- Les objets au sol (lâcher, ramasser, contenu éparpillé à la mort).
- Épées, houes, armures, coffres, arcs, teintures, laine, livres, poudre à canon.
  Le TNT ne se fabrique donc pas (Créatif seulement).
- Les fissures sur les blocs : la progression de la casse est une barre sous le
  viseur. Les dessiner sur les faces demande un passage de rendu à part.

## Décisions

### Objets (`items.py`)

- Un objet est un entier. **0 à 255** : le bloc du même numéro (`AIR` = case vide).
  **256 et plus** : des objets qui ne sont pas des blocs.
- Objets créés :
  - `STICK`, `COAL`, `CHARCOAL`, `IRON_INGOT`, `GOLD_INGOT`, `DIAMOND`, `EMERALD`,
    `LAPIS`, `QUARTZ`, `FLINT`, `APPLE`, `CLAY_BALL`, `BRICK` ;
  - puis 15 outils : `{WOODEN, STONE, IRON, GOLDEN, DIAMOND}_{PICKAXE, AXE, SHOVEL}`.
- La poudre de redstone est l'objet du bloc `REDSTONE_WIRE`. Les blocs tournés
  (four ouest…) et allumés donnent l'objet de leur bloc de base.
- Piles de 64 au plus ; un outil par case. Une case vaut
  `(objet, nombre, usure)`.
- Outils :

  | Matériau | Vitesse | Durabilité | Niveau |
  |---|---|---|---|
  | bois | 2 | 59 | 0 |
  | pierre | 4 | 131 | 1 |
  | fer | 6 | 250 | 2 |
  | or | 12 | 32 | 0 |
  | diamant | 8 | 1561 | 3 |

- **Temps de casse** (règle de Minecraft) :
  - vitesse = celle de l'outil s'il convient au bloc, sinon 1 ;
  - dégât par tick = vitesse / dureté / (30 si le bloc est récoltable, 100 sinon) ;
  - secondes = 1 / (dégât par tick × 20) ;
  - une dureté de 0 casse tout de suite ; une dureté de −1 ne se casse pas.
- **Dureté** (par groupes, valeurs de Minecraft) :
  - 0 : plantes, pièces de redstone fines, TNT, bloc de slime ;
  - 0,1 : mousse ;
  - 0,2 : feuilles, neige, blocs de champignon ;
  - 0,3 : verre, verre teinté, glowstone, lampes ;
  - 0,4 : cactus, netherrack ;
  - 0,5 : terre, terre grossière, sable, sable rouge, glace, glace compacte, terre
    labourée, boue, levier, bouton, plaque, piston ;
  - 0,6 : herbe, mycélium, podzol, gravier, argile, éponges, sable des âmes ;
  - 0,8 : grès (tous), quartz, bloc musical ;
  - 1 : citrouille, melon ;
  - 1,25 : terres cuites ;
  - 1,5 : pierre, pierres taillées et polies, granite, diorite, andésite, prismarines,
    bibliothèque, pierre lisse ;
  - 2 : pierre taillée, pierre moussue, briques, bûches, planches, briques du Nether,
    juke-box ;
  - 2,5 : établi ;
  - 3 : minerais, deepslate et ses variantes, pierre de l'End ;
  - 3,5 : four, distributeur, droppeur ;
  - 5 : blocs de métal, de diamant, d'émeraude, de lapis, de redstone et de charbon,
    générateur de monstres ;
  - 50 : obsidienne ;
  - −1 : bedrock, bloc de commande ;
  - 0,5 : tout bloc oublié dans ces groupes.
- **Outil efficace** :
  - pioche : groupes 0,8 / 1,25 / 1,5 / 2 (sauf bois) / 3 / 3,5 / 5 / 50, plus
    netherrack, glace, glace compacte, lampes ;
  - hache : bûches, planches, établi, bibliothèque, citrouille, melon, juke-box,
    bloc musical ;
  - pelle : terre, herbe, sable, sable rouge, gravier, argile, neige, mycélium,
    podzol, terre labourée, boue, sable des âmes, terre grossière.
- **Récoltable** :
  - les blocs « pioche » sauf la glace demandent une pioche ;
  - minerai de fer et de lapis, bloc de fer et de lapis : pioche de niveau 1 au moins ;
  - minerai d'or, de diamant, d'émeraude et de redstone, blocs d'or, de diamant et
    d'émeraude : niveau 2 au moins ;
  - obsidienne : niveau 3 ;
  - tout le reste se récolte à la main.
- **Drops** (`drops(block, tool, rng) -> list[(objet, nombre)]`, vide si le bloc
  n'est pas récoltable) :
  - pierre → pierre taillée ; herbe, mycélium, podzol, terre labourée → terre ;
  - charbon → `COAL` ; diamant → `DIAMOND` ; émeraude → `EMERALD` ;
  - lapis → `LAPIS` × 4 à 8 ; redstone → `REDSTONE_WIRE` × 4 à 5 ;
    quartz → `QUARTZ` ;
  - gravier → `FLINT` une fois sur 10, sinon gravier ;
  - argile → `CLAY_BALL` × 4 ;
  - feuilles → pousse de chêne une fois sur 20 ; feuilles de chêne et de chêne noir
    → aussi `APPLE` une fois sur 200 ;
  - rien pour : verre, verre teinté, glace, glace compacte, hautes herbes,
    fougères, buisson mort, générateur, tête de piston ;
  - lampe allumée → lampe éteinte ; four allumé ou tourné → `FURNACE` ; distributeur
    ou droppeur tourné → leur base ; citrouille-lanterne tournée → sa base ;
  - tout le reste → lui-même × 1.

### Recettes (`recipes.py`)

- **Avec forme** (motif de lettres, symétrie gauche-droite acceptée, le motif peut
  se placer n'importe où dans la grille) ou **sans forme** (ensemble
  d'ingrédients).
- `PLANKS_ANY` désigne n'importe quelles planches ; `LOGS` les bûches. La liste :
  - chaque bûche → 4 planches de son bois (6 bois) ;
  - 2 planches en colonne → 4 bâtons ;
  - 2×2 planches → établi ;
  - anneau de 8 pierres taillées → four ;
  - outils : pioche `XXX/.S./.S.`, hache `XX/XS/.S`, pelle `X/S/S`, avec
    `X` ∈ planches, pierre taillée, lingot de fer, lingot d'or, diamant (soit 15
    recettes) ;
  - redstone sur bâton → torche de redstone ;
  - bâton sur pierre taillée → levier ;
  - 1 pierre → bouton ; 2 pierres en ligne → plaque ;
  - `TRT/SSS` (torche de redstone, poudre, pierre) → répéteur ;
  - `.R./RGR/.R.` (glowstone au centre) → lampe éteinte ;
  - `PPP/CIC/CRC` (planches, pierre taillée, lingot de fer, poudre) → piston ;
  - bloc de slime sur piston → piston collant (règle maison : pas de boule de
    slime) ;
  - 9 ↔ bloc pour le charbon, le fer, l'or, le diamant, l'émeraude, le lapis et la
    redstone (14 recettes) ;
  - 2×2 → 4 pour : pierre → pierres taillées ; sable → grès (× 1) ; sable rouge →
    grès rouge (× 1) ; grès → grès taillé ; grès rouge → grès rouge taillé ;
    granite, diorite et andésite → polis ; deepslate → deepslate polie ; deepslate
    polie → briques de deepslate ;
  - 2×2 `BRICK` → bloc de briques ; 4 `CLAY_BALL` → argile ; 2×2 `QUARTZ` → bloc de
    quartz ;
  - 8 planches autour d'une poudre → bloc musical ; 8 planches autour d'un diamant
    → juke-box ; `CCC/C.C/CRC` → droppeur.
- **Cuisson** :
  - minerai de fer → lingot de fer ; minerai d'or → lingot d'or ;
  - sable et sable rouge → verre ;
  - pierre taillée → pierre ; pierre → pierre lisse ;
  - `CLAY_BALL` → `BRICK` ; argile → terre cuite ;
  - toute bûche → `CHARCOAL` ; éponge mouillée → éponge ;
  - minerais de charbon, de diamant, d'émeraude, de lapis, de redstone et de quartz
    → leur objet.
- **Combustibles** (objets cuits par unité) :
  - `COAL`, `CHARCOAL` : 8 ; bloc de charbon : 80 ;
  - planches, bûches, établi, bibliothèque : 1,5 ;
  - outils en bois : 1 ; `STICK` : 0,5.
- Un objet cuit en **200 ticks** (10 s).

### Inventaire (`inventory.py`)

- `Inventory` : 36 cases, de 0 à 8 la barre d'action, de 9 à 35 le reste.
  - `add(item, count) -> reste` : complète les piles existantes, puis remplit les
    cases vides en commençant par la barre ;
  - `remove_from(slot, n)` ;
  - `damage_tool(slot, amount) -> cassé?`.
- `click(slots, cursor, i, button, shift)` est une fonction pure, sur le modèle de
  Minecraft :
  - clic gauche, curseur vide : on prend la pile ;
  - clic gauche, curseur plein : on dépose tout dans une case vide, on complète une
    pile du même objet, ou on échange avec un objet différent ;
  - clic droit, curseur vide : on prend la moitié (arrondie au-dessus) ;
  - clic droit, curseur plein : on dépose 1 dans une case vide ou une pile du même
    objet ;
  - Maj + clic gauche : la pile passe de la barre au reste, ou l'inverse.
- Case de **résultat** : un clic prend le résultat si le curseur est vide, ou s'il
  tient le même objet avec de la place, et retire 1 de chaque ingrédient. Maj +
  clic fabrique autant qu'il se peut, directement dans l'inventaire.
- En **fermant** un écran, la grille de craft et le curseur reviennent dans
  l'inventaire ; s'il n'y a plus de place, ils sont perdus et un message le dit.

### Vie (`survival.py`)

- 20 PV.
- **Chute** : dégâts = `ceil(hauteur de chute − 3)` en atterrissant au sol. Pas de
  dégâts dans l'eau ni en vol.
- **Noyade** : 300 ticks d'air quand la tête est sous l'eau, puis 2 PV par seconde ;
  l'air revient à l'air libre.
- **Régénération** : +1 PV toutes les 4 s.
- À 0 PV, état `dead` : écran « You died! » et un bouton **Respawn**, qui ramène au
  point de départ avec 20 PV.
- **En Créatif** : aucun dégât, casse instantanée, objets infinis, vol autorisé.
- **En Survie** : la touche F (vol) ne fait rien, et le vol est coupé.

### Four (`furnace.py`)

- `Furnaces` : un dictionnaire `pos -> FurnaceState`, avec les cases entrée,
  combustible et sortie, les ticks de flamme restants, le total de la flamme et la
  progression de la cuisson.
- `tick()` est appelé à chaque tick de la simulation (`sim.every_tick`) :
  - le four brûle un combustible si l'entrée peut cuire et que la sortie a de la
    place ;
  - il avance la cuisson ;
  - il allume ou éteint le bloc en passant de `FURNACE*` à `FURNACE_ON*` (même
    orientation).
- **Casser un four** met son contenu dans l'inventaire du joueur.
- Nouveaux blocs : `FURNACE_ON`, `FURNACE_ON_WEST`, `FURNACE_ON_SOUTH`,
  `FURNACE_ON_NORTH` (tuile `T_FURNACE_FRONT_ON`, fichier de pack
  `furnace_front_on`), hors inventaire.

### Écrans (`screens.py`)

- Cases de 18 px UI (icône de 16 + 1 de bord). Le nombre s'affiche en bas à
  droite, avec une ombre, quand il dépasse 1. Une barre d'usure s'affiche sous un
  outil abîmé.
- **Inventaire de Survie** (E) : grille de craft 2×2, une flèche et le résultat en
  haut à droite ; 3 rangées de 9 ; la barre de 9 en dessous.
- **Établi** (clic droit sur un établi) : grille 3×3, flèche, résultat ; puis
  l'inventaire.
- **Four** (clic droit sur un four) : entrée en haut, flamme au milieu, combustible
  en bas, flèche de progression, sortie ; puis l'inventaire.
- La pile du curseur suit la souris, et une bulle donne le nom de l'objet survolé.
  E ou Échap ferme l'écran.
- **Créatif** : l'écran d'aujourd'hui (onglets de blocs) ; un clic met une pile de
  l'objet dans la case choisie de la barre.
- **HUD Survie** : 10 cœurs à gauche au-dessus de la barre ; 10 bulles à droite
  quand la tête est sous l'eau ; le nombre sur chaque case de la barre ; la barre
  de progression de la casse sous le viseur.
- **Titre** : « New world » ouvre un choix **Survival / Creative / Back**.
- Commande `/gamemode survival|creative`.

### Icônes

- Les tuiles d'objets sont générées par `items.build_item_tiles() -> (64, 16, 16, 4)`.
  La tuile d'un objet est son numéro moins 256.
- Les icônes d'objets vont dans la banque d'images Pyxel 2, avec la même
  disposition que les blocs, et les 48 couleurs d'icônes sont calculées sur les
  deux jeux.
- Packs : `packs.ITEM_FILES[item] = (noms 1.8 dans textures/items/, noms 1.13 dans
  textures/item/)`. Une icône absente du pack reprend l'icône générée. Les icônes
  d'objets sont réduites à 16 px.

### Sauvegarde

- Nouvelles clés :
  - `mode` (0 Survie, 1 Créatif) ;
  - `inventory` (36 × 3) ;
  - `health` et `air` ;
  - `spawn` ;
  - `furnaces` (n × 13 : position, puis 3 cases × (objet, nombre), puis flamme
    restante, flamme totale, cuisson).
- **Ancienne sauvegarde** (sans `mode`) : elle passe en **Créatif**, et sa barre
  `hotbar` devient 9 cases d'une pile de 1.

## Vérification

- Tests `pytest`, sans GL : registre, temps de casse, récoltabilité, drops (avec un
  `rng` fixé), toutes les recettes (chaque recette se fabrique depuis sa grille),
  symétrie, cuisson et combustible, clics d'inventaire, résultat de craft,
  dégâts de chute, noyade, régénération, mort, four complet sur 1000 ticks,
  sauvegarde et chargement, conversion des anciennes sauvegardes, `/gamemode`.
- Captures sans fenêtre : écran inventaire, établi, four en cuisson, HUD avec les
  cœurs.
