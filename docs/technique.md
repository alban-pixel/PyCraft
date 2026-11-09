# PyCraft — Technique

> Comment le moteur fonctionne réellement, tel qu'implémenté dans `pycraft-gpu/`
> (branches `SWE-2` puis `m1-pro`). Pour le jeu lui-même (contrôles, réglages,
> limites), voir [`pycraft-gpu/README.md`](../pycraft-gpu/README.md).
>
> Document rédigé le 4 novembre 2026. L'approche initiale (rendu 2D par
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
renderer.py OpenGL : maillages de blocs, clipmap lointain, ombres, ciel, palette
main.py     application Pyxel : écrans, entrées, casser/poser, jour/nuit, son
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
   l'altitude (forêt → alpage → neige → glacier).

Les couches lisses sont calculées tous les 8 blocs et interpolées — la
génération d'une colonne est ~3× plus rapide.

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
  marque la cellule L0 « dirty » — la modification remonte la cascade, cadre
  par cadre, là où les records ont vraiment changé. Un bloc inconnu du shader
  passe par la sentinelle `surf=255` + sa couleur résolue dans la teinte.
- **Plantes et arbres** : les plantes n'ont pas de géométrie lointaine mais
  leur couleur tachette le sol ; la canopée devient une couverture continue
  (fini le popping forêt), assombrie par porosité, avec dégradé vertical.
- **Eau** : colonne séparée voir-through comme entre les blocs, alpha
  proportionnel à la couverture mouillée de la cellule ; la glace est un
  solide de la colonne du sol.
- Textures **qui bouclent** (wrap) : quand la caméra avance, seuls les
  nouveaux bords sont échantillonnés — par bandes, quelques-unes par frame.
- Les resamples « dirty » d'un niveau sont regroupés en runs contigus (ligne
  ou colonne, le moins cher), plafonnés par frame et **priorisés près du
  bord du niveau plus fin** — là où le niveau prend le relais cellule par
  cellule. Le climat (champ kilométrique) n'est évalué qu'une fois par
  cellule sous 32 blocs d'espacement.
- Sur `m1-pro`, toute la production de records et de texels (sampling,
  cascade, injection des édits) tourne sur **son propre thread** (même
  raison : numpy libère le GIL) — un saut de caméra ne fige plus la frame.
  Le job travaille niveau par niveau sur son instantané (monde, colonnes
  éditées copiées, records, ensembles dirty) et les écritures de textures
  atterrissent sur le thread du jeu quand le futur se termine.

## Lumière et ciel

- Le soleil le jour, la lune la nuit ; un cycle complet dure 8 minutes.
- **Trois shadow maps** (blocs proches, terrain lointain < 1 km, < 8 km),
  redessinées seulement quand la scène change (soleil déplacé, caméra loin,
  blocs modifiés). Les montagnes projettent des ombres de kilomètres au
  lever/coucher.
- Le ciel : soleil, lune, étoiles la nuit, halo autour du soleil, brume bleue
  sur les montagnes lointaines. **Nuages** : couche de bruit bouclable ~940
  blocs au-dessus de la mer, dérivant avec le vent, dessinée deux fois (loin
  avec le terrain lointain, près après les blocs) et projetant leur ombre.

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
| Échantillonnage du terrain lointain | par batch, sur le thread du jeu | thread dédié | thread dédié |
| Tuiles des blocs dans le shader du terrain lointain | tableau constant | tableau constant | petite texture entière |
| Lecture de l'image indexée | copie, puis lignes retournées | copie, puis lignes retournées | directement dans l'écran de Pyxel |

Sur `claude`, `cpu_count` compte les threads matériels : 20 sur le Ryzen AI 9 H 365 (10 cœurs),
et 16 workers n'y faisaient pas mieux que 8. Le tableau constant `BLOCK_TILES`, indexé par pixel
selon le bloc, est recopié par le pilote AMD dans la mémoire scratch de chaque pixel : le terrain
lointain prenait 73 ms de carte par image à 2560x1440, 9 ms avec la texture. Sur ce PC, une image
fixe passe de 87 à 26 ms à 2560x1440 (graphismes rapides), le vol rapide de 198 à 26 ms, et le
chargement d'un monde de 13 s à moins d'une seconde.

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
