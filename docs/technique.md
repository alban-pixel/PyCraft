# PyCraft — Technique

> Comment le moteur fonctionne réellement, tel qu'implémenté dans le paquet `pycraft/`
> (développé sur les branches `SWE-2`, `m1-pro`, `claude` et `gpu-renderer-dev`, toutes
> réunies dans `main`). Pour le jeu lui-même (contrôles, réglages, limites), voir le
> [`README.md`](../README.md).
>
> Document rédigé le 4 novembre 2026, mis à jour le 15 novembre 2026 pour la branche
> `claude` (terrain lointain refait). L'approche initiale (rendu 2D par
> `pyxel.tri`, voir `SPEC.md` et `tasks/`) a été abandonnée au profit du GPU.

## Vue d'ensemble

Pyxel ne sert **pas** à dessiner le monde : il gère la fenêtre, les entrées,
les menus, le HUD, les sons et la musique. Le monde 3D est rendu par OpenGL
(`moderngl`) dans une image hors écran de la taille de la fenêtre, puis un
derner shader la quantifie dans la palette de 256 couleurs de Pyxel (un octet
par pixel, index de palette) et la copie dans `pyxel.screen`. Pyxel dessine le
HUD par-dessus.

```
terrain.py  génération procédurale du monde (bruit, biomes, grottes, arbres)
world.py    sections 16×16×16 créées à la demande, accès blocs, sauvegarde
builder.py  processus workers : génération + recherche des faces visibles
lod.py      processus d'échantillonnage du terrain lointain (branche `claude`)
render/     OpenGL : maillages de blocs (chunks), terrain lointain (far), ombres (shadows),
            palette, shaders GLSL (shaders), et le Renderer qui les assemble
controls.py actions du jeu et touche de chacune (modifiables dans les réglages)
ui.py       HUD et menus : panneaux, boutons, onglets, curseurs, thème de 16 couleurs
app.py      application Pyxel (`python -m pycraft`) : boucle, états, partie, monde ; ses écrans
            sont des classes dont App hérite : screens/ (menus, réglages, inventaire, HUD, chat),
            play.py (jouer), sound.py (sons, musique)
settings.py valeurs, défauts et onglets des réglages ; sky.py ciel et lumière ; icons.py icônes
```

## Terrain

Tout est une fonction de `(x, z)` calculée sur des tableaux NumPy entiers —
le même code sert au monde jouable et au terrain lointain.

1. **Continents** : bruit très lisse → océans profonds, plateaux, plaines.
2. **Chaînes de montagnes** : suivent la ligne zéro d'un second bruit (donc de
   longues crêtes), relief « ridged » empilé — chaque couche fine pondérée par
   la précédente, comme de l'érosion.
3. **Collines**, puis **rivières** (ligne zéro d'un troisième bruit, chenal
   creusé par la distance au gradient), **lacs**, **badlands** en mesas.
4. **Iceland** : grabens (vallées effondrées entre deux parois, plancher en
   champ de lave hummocky), volcans tables (tuyas), strata de lave en
   terrasses, et un bloc **moss** qui verdit les roches froides et humides.
5. **Climat** : température + humidité → 18 biomes ; la température chute avec
   l'altitude (forêt → alpage → neige → glacier). Une seule limite des neiges
   (`SNOW_LINE`) vaut en plaine comme en montagne : en dessous, tout est enneigé
   et l'eau gèle ; au-dessus, rien. Les zones de température font
   une quinzaine de km. L'humidité vient de la mer : elle baisse vers
   l'intérieur des terres (continentalité) et derrière une chaîne de montagnes
   (ombre pluviométrique, vent venant de −x). La mer ne gèle qu'en eau peu
   profonde, le long des côtes ; `sample()` renvoie ce masque `ice`, que
   suivent les blocs et le terrain lointain. `python tools/biomes.py` mesure la
   logique de la carte des biomes (voir `docs/superpowers/plans/2026-11-23-biomes-logiques.md`).

Les couches lisses sont calculées tous les 8 blocs et interpolées — la
génération d'une colonne est ~3× plus rapide.

## La vraie Terre (`pycraft/earth/`)

`World(seed, earth=Place)` remplace le générateur par `EarthGenerator`, qui hérite de
`TerrainGenerator` : grottes, minerais, arbres et blocs restent ceux du jeu, et seuls `climate()` et
`sample()` changent, donc les blocs proches et le terrain lointain suivent sans autre changement.

- **Grille** (`grid.py`) : la carte Web Mercator des tuiles, mise à l'échelle pour qu'un bloc fasse un
  mètre à la latitude du lieu. +x est l'est, +z le sud.
- **Tuiles** (`tiles.py`) : un seul processus télécharge, nettoie (`clean.py`) et écrit sur le disque
  (`TileStore`, `Downloader`). Tous les autres ne font que lire des fichiers (`TileReader`), donc rien
  n'attend le réseau. Là où une tuile manque, la plus proche tuile grossière est agrandie.
- **Nettoyage** : aux zooms 13 et 14, un pixel trop loin du sol vu trois zooms plus haut est remplacé ;
  aux autres, seulement les pixels isolés (la première règle rabotait l'Everest de 1 500 m au
  zoom 8). Le fond de la mer vient du zoom 8, et une table rend leur hauteur aux grands sommets.
- **Pas de gel** : `World.ready` dit si les tuiles d'un chunk sont là. `Chunks` et `FarTerrain` ne
  demandent que ce qui est prêt, et `Playing.keep_to_ready_ground` retient le joueur au bord.
- **Climat** (`climate.npz`) : température (ramenée au niveau de la mer) et pluie de CHELSA, tous les
  1/6 de degré, faites par `tools/make_climate.py`. `biomes.py` en tire le biome.
- **Sauvegardes** : une par lieu, `earth/<lat><lon>.npz` ; `world2.npz` n'est jamais touché.
- Temps de `columns()` pour 64 chunks, sur le même ordinateur : 21 ms, contre 36 ms pour le monde normal.

## Blocs près de la caméra

- Le monde est stocké en **sections 16×16×16**, créées à la demande ; seules
  les modifications du joueur sont sauvegardées (`world2.npz`).
- Chaque colonne 16×16 possède un **mesh** des faces visibles de ses sections,
  construit par des **processus workers** (3 sur `SWE-2`, `cpu_count − 4` sur
  `m1-pro`) — chacun avec sa copie du monde, car les threads Python se
  bloqueraient sur le GIL pour ce travail.
- Le jeu demande les colonnes **les plus proches d'abord** ; chaque colonne
  compte ses modifications (« version ») : un mesh construit sur des blocs
  périmés est jeté et redemandé. Casser/poser un bloc reconstruit sa section
  immédiatement.
- **Ambient occlusion** : pendant le maillage, chaque coin de face compte les
  blocs voisins — plus il y en a, plus le coin est sombre.
- Sur `m1-pro`, l'**emballage** du mesh pour la carte (consolidation des faces,
  buffer d'indices, tri eau en dernier) tourne sur un pool de threads : numpy
  libère le GIL dans ses grosses boucles, donc ça avance pendant que le thread
  du jeu continue. Seuls les appels OpenGL restent sur le thread du jeu.

## Terrain lointain (clipmap LOD)

Jusqu'à ~8 km, le terrain est un **clipmap de colonnes sémantiques** : chaque
niveau est deux fois plus grossier et deux fois plus large que le précédent,
avec un trou là où un niveau plus fin (ou les blocs) est dessiné. La
simplification se fait **dans l'espace voxel avant tout maillage** — on
agrège des sous-échantillons en un « record » par cellule, jamais des
triangles. Les bords fusionnent en fondu stochastique (hash déterministe par
cellule) sur ~24 colonnes.

- Le réglage **LOD quality** choisit `(espacement, grille, niveaux)` :
  `low` = colonne tous les 2 blocs, grille 128, 7 niveaux ; `medium` = grille
  256 ; `high` = colonne par bloc, 8 niveaux ; `ultra` = grille 512.
- **Record d'une cellule** : hauteur moyenne du sol, bloc de surface
  majoritaire (les sous-colonnes hautes pèsent plus — une tour dépasse la
  plaine), couverture de canopée continue + espèce de feuilles majoritaire +
  hauteur de couronne, couverture d'eau/glace + surface d'eau pondérée,
  profondeur, teinte moyennée en **Oklab**, drapeau émissif.
- **Cascade mip** : une cellule dont les quatre filles du niveau fin sont
  connues (tags toriques à jour) est agrégée depuis leurs records — gratuit,
  et c'est ce qui fait remonter le détail réel (édits inclus) vers les
  niveaux grossiers. Sinon, l'empreinte de la cellule est échantillonnée sur
  une sous-grille 2×2 auprès du générateur.
- **Edits du joueur** : `world.edited_tops` reconstruit le vrai sommet des
  colonnes modifiées (surface, remplissage, eau, couronne, teinte) ; ils sont
  injectés à tous les niveaux pendant l'échantillonnage, et `block_changed`
  marque la cellule L0 « dirty » — la modification remonte la cascade, job
  après job, là où les records ont vraiment changé (une tour posée à 170 blocs
  apparaît à quatre niveaux en 1,5 s environ). Un bloc inconnu du shader
  passe par la sentinelle `surf=255` + sa couleur résolue dans la teinte.
- **Plantes et arbres** : les plantes n'ont pas de géométrie lointaine mais
  leur couleur tachette le sol ; la canopée devient une couverture continue
  (fini le popping forêt), assombrie par porosité, avec dégradé vertical.
- **Eau** : colonne séparée voir-through comme entre les blocs, alpha
  proportionnel à la couverture mouillée de la cellule ; la glace est un
  solide de la colonne du sol.
- Textures **qui bouclent** (wrap) : quand la caméra avance, seuls les
  nouveaux bords sont échantillonnés, par bandes de 4 à 16 cellules. Le
  climat (champ kilométrique) n'est évalué qu'une fois par cellule sous
  32 blocs d'espacement.
- Sur `m1-pro`, toute la production de records et de texels tourne sur **son
  propre thread** (numpy libère le GIL) et les écritures de textures
  atterrissent sur le thread du jeu quand le futur se termine.

### Sur `claude` : un processus, et des murs qui se rejoignent

Trois défauts venaient de là : des trous dans les montagnes lointaines, des
versants en bandes ondulées, des murs de colonnes séparées par du ciel. Leurs
causes, et ce qui les remplace :

- **Le thread d'échantillonnage n'avançait pas.** Le thread du jeu passe son
  temps dans des appels OpenGL, qui gardent le GIL : le thread du sampler
  attendait un appel entier à chacune de ses milliers d'étapes. Sur un PC qui
  ne tient pas sa cadence, le premier remplissage prenait des minutes et le
  monde au-delà des blocs restait vide. Le sampler vit maintenant dans **son
  propre processus** (`lod.py`), avec sa copie du monde (les blocs modifiés
  lui sont envoyés un par un). Il y répartit un niveau sur quelques threads
  (de 2 à 6, par paquets de 32 768 points) et **partage un niveau entier avec
  les workers de `builder.py` qui n'ont rien à construire**, par deux files
  communes. Le jeu envoie un job (origines voulues, bandes à produire,
  édits), reçoit les texels niveau par niveau, le plus fin d'abord, et
  n'écrit que dans les textures.
- **La grille d'un niveau ne bouge que quand ses cellules sont arrivées.**
  Avant, l'origine avançait d'abord et les nouvelles bandes montraient
  l'ancien contenu de la texture torique. Un niveau à plus d'une demi-grille
  de la caméra (téléportation) est refait en entier ; tant qu'il est à plus
  d'un huitième de grille, il n'est pas dessiné et les niveaux plus grossiers
  couvrent son terrain.
- **La pente est décidée par le sampler**, comme dans le générateur
  (différence de hauteur maximale avec les quatre voisins de la sous-grille).
  Une cellule raide est de la roche sans arbres à tous les niveaux. Avant, le
  shader la devinait à partir des voisins, et un mur s'arrêtait à la hauteur
  d'une couronne d'arbre que le voisin ne dessinait pas.
- **Les murs descendent jusqu'au vrai sommet voisin** : `drawn_top` donne la
  hauteur qu'une cellule dessine vraiment (sol, plus la couronne là où elle
  en a une). Le côté d'une colonne descend jusqu'au plus bas de : son voisin
  du même niveau, la cellule plus grossière là où ce niveau prend le relais,
  et les deux cellules plus fines le long du côté. Les faces se recouvrent
  de 1 % de l'espacement, ce qui supprime les pixels isolés aux jonctions.
- **Sous les blocs qui s'estompent**, les colonnes restent entières (elles ne
  disparaissent que sous les chunks vraiment dessinés) : il y a toujours du
  sol derrière un bloc absent. Les couronnes montent sur 48 blocs au-delà
  de cette limite, au lieu d'un mur de feuilles.
- **Ordre de dessin** : ciel, blocs opaques, terrain lointain, nuages
  lointains, eau des blocs, nuages proches. Les blocs occupent la moitié
  proche du tampon de profondeur et le terrain lointain la moitié lointaine :
  la carte rejette les pixels du terrain lointain déjà couverts par des
  blocs, et dessiner les colonnes entières sous les blocs ne coûte presque
  rien (jusqu'à 34 ms par image à 1280x720 sinon).
- Les cellules à refaire sont de deux sortes : celles d'un bloc modifié
  (prioritaires, 256 par job) et celles qui viennent d'entrer dans la grille
  d'un niveau plus fin (jusqu'à 4096 par job, refaites seulement quand leurs
  quatre filles sont connues).
- L'écran de chargement attend aussi que tous les niveaux soient arrivés, et
  F3 affiche les niveaux dessinés.
- **Tuiles** : le temps de carte du terrain lointain part surtout dans les
  sommets des colonnes, donc on en envoie le moins possible. La grille de
  chaque niveau est découpée en 16×16 tuiles ; une tuile n'est dessinée que si
  la boîte qui va du pied de sa colonne la plus basse au sommet de la plus
  haute touche le champ, et si le niveau plus fin ne dessine pas toutes ses
  cellules (liste dans un tableau uniforme, un appel de dessin par niveau,
  les plus proches d'abord). Les hauteurs min/max par tuile sont gardées côté
  CPU et recalculées seulement quand la grille bouge ou reçoit des cellules.
  Avec des boîtes hautes comme le monde, presque rien n'était éliminé dès
  que la caméra regardait vers le bas.
- **Deux côtés par colonne** : ceux tournés vers la caméra. Une shadow map
  reçoit les deux côtés tournés à l'opposé de la lumière : avec les sommets
  ils arrêtent la même lumière que les quatre, et aussi celle qui passe sous
  le terrain au bord d'une grille (les côtés tournés vers la lumière la
  laissaient passer).
- **Bouches de grottes** : les parois d'une grotte ne sont maillées que près
  du joueur (sections sous le sol le plus bas du chunk), et le terrain
  lointain est une coque creuse : par une bouche de grotte, l'œil traversait
  la montagne jusqu'au ciel, ce que le dos des colonnes lointaines cachait
  avant. Une seconde passe dessine donc les deux autres côtés des colonnes
  autour des blocs, étirés jusqu'au bas du monde au bord de cette zone : un
  mur sous le sol, tout autour. (Garder les faces de grotte là où les blocs
  s'effacent ne marche pas : les blocs gagnent toujours le test de
  profondeur, elles se verraient à travers le sol.)
- **Eau** : dessinée par tuiles aussi (celles du champ qui en contiennent),
  au lieu d'une liste de toutes les cellules mouillées.
- Mesures du 15-16 novembre, versions lancées l'une après l'autre (les temps
  varient de quelques ms d'un lancement à l'autre sur ce portable) : passe du
  terrain lointain à 2560x1440, 4,0 → 2,2 ms en medium et 14 → 5,1 ms en
  ultra ; image fixe en ultra à 1280x720 (graphismes rapides, 64 chunks),
  11,3 → 7 ms ; vue sur l'océan en ultra, fancy, 256 chunks, 17,6 → 10,7 ms
  de carte. Dans une vraie fenêtre avec ces derniers réglages : marche
  29 → 13 ms par image, vol rapide 34 → 15 à 19 ms.

Vérification : 16 vues de 4 mondes sont rendues deux fois, la seconde avec
les murs prolongés jusqu'en bas ; aucun pixel de ciel de la première n'est
couvert dans la seconde, à toutes les qualités.

## Lumière et ciel

- Le soleil le jour, la lune la nuit ; un cycle complet dure 8 minutes.
- **Trois shadow maps** (blocs proches, terrain lointain < 1 km, < 8 km),
  redessinées seulement quand la scène change (soleil déplacé, caméra loin,
  blocs modifiés) ; sur `claude`, du terrain qui arrive ne redessine une
  carte qu'au plus toutes les 0,1 s (blocs) ou 0,5 s (terrain lointain). Les montagnes projettent des ombres de kilomètres au
  lever/coucher.
- Le ciel : soleil, lune, étoiles la nuit, halo autour du soleil, brume bleue
  sur les montagnes lointaines. **Nuages** : couche de bruit bouclable ~940
  blocs au-dessus de la mer, dérivant avec le vent, dessinée deux fois (loin
  après le terrain lointain, près à la fin) et projetant leur ombre.

## Textures et packs

- Les tuiles sont un tableau `(256, N, N, 4)` : 256 numéros de tuile (le numéro est un octet
  dans le vertex), N pixels par côté. Leur alpha côté CPU vaut 0 (trou), 200 (`TINT_ALPHA` :
  texel teint par le biome) ou 255. Les textures générées (`tiles.build_tiles`) font 16 px.
- Sur la carte, elles deviennent **deux tableaux de textures** (`texture_array`, une couche par
  tuile) mipmappés par le GPU : les couleurs (alpha 0/255, et les trous remplis par la couleur
  moyenne de la tuile pour éviter les halos, sauf pour les feuilles dont les trous sont dessinés)
  et un **masque de teinte** R8. Le shader multiplie la couleur par `mix(1, teinte, masque)` :
  juste à tous les niveaux de mipmap. La découpe (alpha < 0,5) lit toujours le niveau 0, pour
  que les plantes ne s'effacent pas au loin. Filtrage : plus proche voisin de près, mipmaps
  mélangés et anisotrope ×8 de loin. Comme chaque tuile a sa couche, rien ne bave d'une tuile
  à l'autre.
- Le terrain lointain lit les mêmes tableaux avec `textureGrad`, à partir des dérivées d'une
  coordonnée de texture continue (la position monde projetée sur la face).
- **Packs** (`packs.py`) : un dossier, un zip ou le `.jar` d'une version de Minecraft
  installée ; format 1.8 (`textures/blocks/`) ou 1.13+ (`textures/block/`). Une table donne,
  pour chaque tuile, les noms de fichier à essayer dans les deux formats. La taille N est la
  plus fréquente du pack (puissance de 2, de 16 à 256) ; les textures grises de l'herbe, des
  feuilles et de l'eau sont marquées teintes et ramenées à une luminosité moyenne de 204/255,
  celle des textures générées ; la surcouche du côté de l'herbe est posée par-dessus.
- Changer de pack (`Renderer.set_tiles`) remplace les textures et refait le terrain lointain
  (moyennes de tuiles, couleurs envoyées au processus d'échantillonnage) ; les maillages des
  blocs ne changent pas, ils ne contiennent que des numéros de tuile. Les icônes sont réduites
  à 16 px et leurs 48 couleurs de palette recalculées (`Palette.set_fixed`).

## État, formes et redstone

- **État par bloc** : à côté du numéro de bloc (un octet), un octet d'état par bloc
  (`World.states`), seulement dans les sections qui en ont un non nul. Orientation codée
  `0 = haut, 1 = bas, 2 = est, 3 = ouest, 4 = sud, 5 = nord` (`blocks.FACING_VECTORS`), donc
  un bloc d'avant les états regarde vers le haut. Sauvegarde v3 (`state_keys`, `states`,
  `ticks`) ; une v2 se charge sans état.
- **Formes** (`shapes.py`) : des boîtes en 1/16, décrites vers le haut puis tournées (6
  orientations, et 4 sens autour de la verticale), éventuellement inclinées (levier, torche
  murale). Chaque face prend le morceau de tuile qui correspond à sa position, comme les modèles
  de Minecraft. Le vertex porte ses UV (`in_uv`, en 1/16). Une face au bord de la case est
  cachée par un voisin opaque. Visée et contour suivent la boîte de sélection.
- **Horloge** (`sim.py`) : 20 ticks par seconde, mises à jour planifiées et voisins prévenus à
  chaque changement ; au plus 4096 blocs regardés par tick. Les mises à jour en attente sont
  sauvegardées.
- **Redstone** (`redstone.py`) : puissance forte (vers le bloc porteur d'un levier, au-dessus
  d'une torche, devant un répéteur) et faible (poudre). La poudre est recalculée par réseau
  (parcours en largeur puis propagation du plus fort). Torche, répéteur et lampe attendent leur
  délai (`Simulation.after`). Pistons : jusqu'à 12 blocs, tête `PISTON_HEAD` ; TNT : 80 ticks,
  rayon 4, en chaîne.

## Objets et survie

- **Objets** (`items.py`) : un entier. 0 à 255 : le bloc du même numéro ; 256 et plus : bâton,
  lingots, gemmes, outils... Une case vaut `(objet, nombre, usure)`, `(0, 0, 0)` si vide ; 64 par
  pile, un outil par case. Les blocs tournés ou allumés donnent l'objet de leur bloc de base
  (`base_item`).
- **Casse** : temps de Minecraft, `1 / (vitesse / dureté / (30 ou 100) × 20)` secondes, 30 si le
  bloc est récoltable avec cet outil. `survival.BreakProgress` cumule une fraction, pas un temps :
  changer d'outil en cours de route continue à la nouvelle vitesse. Drops dans `items.drops`, avec
  un `random.Random` pour les tirages.
- **Inventaire** (`inventory.py`) : 36 cases (0-8 la barre) et des fonctions de clic pures sur des
  listes de cases, réutilisées par les écrans (`screens.py`) pour la grille, le four et le curseur.
  `screens.Screen` réunit inventaire, grille et four dans une seule liste pour les Maj+clic.
- **Recettes** (`recipes.py`) : avec forme (motif placé n'importe où, symétrie gauche-droite) ou
  sans forme ; la première qui correspond gagne. Cuisson et combustibles à part.
- **Four** (`furnace.py`) : le contenu vit dans `Furnaces`, par position, pas dans l'octet d'état ;
  `tick` tourne dans `sim.every_tick` et passe le bloc de `FURNACE*` à `FURNACE_ON*` (même
  orientation).
- **Vie** (`survival.Health`) : 20 PV, chute `ceil(hauteur − 3)` (mesurée par `Player.fall_distance`),
  300 ticks d'air puis 2 PV/s, +1 PV toutes les 4 s.
- **Icônes d'objets** : générées par `items.build_item_tiles`, ou lues dans `textures/items/` (1.8)
  et `textures/item/` (1.13) du pack. Elles vont dans la banque d'images Pyxel 2 et partagent les 48
  couleurs d'icônes avec les blocs.
- **Sauvegarde** : clés `mode`, `inventory` (36 × 3), `health`, `air`, `spawn`, `furnaces` (n × 12) ;
  une sauvegarde sans `inventory` passe en Créatif avec sa `hotbar`.

## De la frame au pixel Pyxel

1. La scène est rendue en **pleine couleur** (HDR-ish, éclairage par face :
   lumière du ciel + lumière directe si orientée vers le soleil et non ombrée).
2. Un shader la quantifie en **256 couleurs** : les 16 premières sont celles de
   Pyxel (HUD), les 48 suivantes servent les icônes de blocs, les 192 dernières
   s'adaptent au contenu de l'écran par **k-means** (échantillon de 4096 pixels
   toutes les 2 frames, calculé sur le GPU).
3. Chaque pixel est **dithéré** entre les deux couleurs de palette dont le
   mélange approche le plus sa couleur (table 32×32×32 recalculée quand la
   palette change ; une palette stable = pas de scintillement).
4. Le résultat est copié dans `pyxel.screen`, puis Pyxel dessine HUD et menus.

## Cadence et résolution

Pyxel ne permet pas de changer le FPS une fois la fenêtre ouverte : le jeu
démarre Pyxel à un taux très élevé et **rythme lui-même** (`App.run` +
`pyxel.flip`). Le mouvement utilise le temps réel entre frames — même vitesse
à tout FPS. La résolution change via `pyxel.resize`, et le renderer recrée son
image hors écran à la nouvelle taille.

## Différences entre branches

| | `SWE-2` | `m1-pro` | `claude` (PC : Ryzen AI 9 H 365, Radeon 880M) |
|---|---|---|---|
| Workers de terrain/mesh | 3 processus | `max(3, cpu_count − 4)` processus | `max(3, min(cpu_count − 4, 8))` processus |
| Répartition des requêtes de colonnes | un seul worker | tous les workers | tous les workers |
| Emballage des meshes pour la carte | sur le thread du jeu | pool de 2 threads | pool de 2 threads |
| Échantillonnage du terrain lointain | par batch, sur le thread du jeu | thread dédié | processus dédié (`lod.py`), aidé par les workers inactifs |
| Pente des colonnes lointaines | devinée par le shader | devinée par le shader | calculée par l'échantillonneur |
| Ordre de dessin | terrain lointain, puis blocs | terrain lointain, puis blocs | blocs, puis terrain lointain derrière eux |
| Tuiles des blocs dans le shader du terrain lointain | tableau constant | tableau constant | petite texture entière |
| Lecture de l'image indexée | copie, puis lignes retournées | copie, puis lignes retournées | directement dans l'écran de Pyxel |

Sur `claude`, `cpu_count` compte les threads matériels : 20 sur le Ryzen AI 9 H 365 (10 cœurs),
et 16 workers n'y faisaient pas mieux que 8. Le tableau constant `BLOCK_TILES`, indexé par pixel
selon le bloc, est recopié par le pilote AMD dans la mémoire scratch de chaque pixel : le terrain
lointain prenait 73 ms de carte par image à 2560x1440, 9 ms avec la texture. Le 9 novembre, sur
ce PC, une image fixe passait ainsi de 87 à 26 ms à 2560x1440 (graphismes rapides) et le vol
rapide de 198 à 26 ms.

Le 15 novembre (terrain lointain refait ; le PC mesure plus vite ce jour-là, d'où la comparaison
avec la version précédente relancée le même jour, sans fenêtre et sans limite de cadence) :

| 2560x1440 | avant (0c91c47) | après |
|---|---|---|
| Graphismes rapides, LOD medium, 64 chunks : image fixe | 13,5 ms (carte 7,7) | 10,8 ms (carte 6,5) |
| — monde complet après | 14,9 s dans le test, des minutes en jeu | 3,5 s |
| Fancy, LOD high, 512 chunks : image fixe | 23,5 ms (carte 16,0) | 20,0 ms (carte 12,9) |
| — monde complet après | 23,5 s dans le test | 6,9 s |

À 1280x720, LOD medium et 64 chunks, une image fixe prend 7 ms en graphismes rapides et 9 en
fancy ; le vol rapide (42 blocs/s) environ moitié plus. Premier remplissage par le sampler seul :
0,8 s en low, 3,3 s en medium, 3,4 s en high, 9,4 s en ultra.

## Limites connues

- L'eau ne coule pas : elle reste où la génération ou le joueur l'a mise.
- Pas de mode survie (vie, faim, mobs, craft).
- Les grottes ne reçoivent pas de lumière du ciel mais restent éclairées —
  pas vraiment sombres.
- Le terrain lointain simplifie la sémantique des colonnes : une construction
  petite devant la cellule qui la contient finit diluée dans le vote
  majoritaire (sa couleur reste dans la teinte, sa forme disparaît).
- Les nuages sont plats : vus de leur hauteur, une fine ligne.
- En vol rapide, on peut distancer les meshes de blocs un instant ; le terrain
  lointain comble le vide en attendant.
