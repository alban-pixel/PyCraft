# Chantier 1 — Packs de textures

> Design du 16 novembre 2026, branche `gpu-renderer-dev`. Premier chantier de
> [`docs/roadmap.md`](../../roadmap.md).

## Intention

Le joueur veut charger des packs de textures externes au format Minecraft au lieu
des textures dessinées par code, avec **le meilleur rendu visuel final** possible :
un pack HD doit rester net de près, et propre de loin.

Les « bugs » de textures signalés (le piston qui ne se sépare pas en deux, qui fait
un « piston fantôme » à côté ; le levier) **ne relèvent pas de ce chantier** : ce
sont des blocs sans état ni forme propre (`PISTON` est un cube plein en un seul
numéro). Ils seront réglés par le socle (état par bloc, formes non cubiques) puis
par la redstone (chantier 4). Un pack ne les corrigera pas.

## Objectifs

- Charger un pack Minecraft déposé par le joueur : **dossier ou `.zip`**, formats
  **1.8** (`assets/minecraft/textures/blocks/`) et **1.13+**
  (`assets/minecraft/textures/block/`, noms renommés).
- **Résolution du pack conservée** : 16, 32, 64, 128 px par tuile.
- Les textures générées restent le **pack par défaut**, et chaque texture absente
  d'un pack retombe sur la tuile générée.
- **Choix du pack dans les réglages**, appliqué sans redémarrer ni régénérer le
  monde, mémorisé dans `settings.json`.
- **Icônes d'inventaire** tirées du pack.
- Couleurs de biome (herbe, feuilles, eau) conservées avec les textures grises des
  packs.

## Non-objectifs

- Les modèles JSON (`blockstates/`, `models/`) et donc les formes du pack : plus
  tard, avec le socle des formes.
- Textures animées (eau, lave, feu) : première image seulement.
- Sons, polices, interface du pack (`gui/`), ciel, soleil, lune, `colormap/` : pas
  dans ce chantier.
- Le socle commun (état par bloc, ticks, objets) : conçu à part, juste après ce
  chantier et avant la survie. Il n'a pas besoin des packs, et les packs n'ont pas
  besoin de lui. Le format de sauvegarde ne change donc pas ici.

## Anti-objectifs

- Embarquer ou télécharger un fichier de Mojang. Le dépôt ne contient ni pack, ni
  texture extraite, ni capture d'atlas issu d'un pack.
- Un pack qui casse le jeu : un zip abîmé, un PNG illisible, une taille bizarre
  donnent un message et le pack par défaut, jamais un plantage.
- Faire baisser les FPS. Un pack 128 px ne doit pas coûter de temps GPU visible à
  la fréquence par défaut.
- Du scintillement de loin : les packs HD sans mipmaps fourmillent, c'est pire
  que les textures actuelles.

## Contraintes

- La 3D est quantifiée en 256 couleurs de Pyxel avec tramage ; le détail HD reste
  visible de près, mais les couleurs passent par la palette.
- Le numéro de tuile est un `u1` dans le vertex (`builder.VERTEX`, `info[0]`) :
  256 tuiles au plus. 196 sont utilisées.
- `GL_MAX_ARRAY_TEXTURE_LAYERS` vaut au moins 256 en OpenGL 3.3.
- Les processus de maillage ne voient que les numéros de tuile. Seul le processus
  principal voit l'atlas, plus le processus d'échantillonnage du terrain lointain,
  qui reçoit `block_colors` par `SamplerProcess.configure`.
- Pas de Pillow aujourd'hui. Les dépendances sont `pyxel`, `numpy`, `moderngl`, et
  `PyCraft.command` installe `requirements.txt` dans `.venv`.
- Sur macOS, ce poste a une installation Minecraft avec `versions/1.8/1.8.jar`.

## Approches envisagées

| | Approche | Bilan |
|---|---|---|
| A | Pack réduit en 16×16 dans l'atlas actuel | Le plus court, mais un pack HD perd tout son détail. Écarté. |
| **B** | **Pack à sa résolution** | **Retenu** (choix du joueur : le meilleur rendu final). |
| C | Modèles JSON complets (formes du pack) | Énorme, et dépend du socle des formes. Reporté. |

Dans B, deux façons de ranger les tuiles sur la carte :

- **Atlas 2D plus grand** (16×16 tuiles de N px). C'est le changement minimal,
  mais les mipmaps d'un atlas mélangent les tuiles voisines : on reste sans
  mipmaps, et ça fourmille de loin.
- **Tableau de textures** (`sampler2DArray`, une couche par tuile). **Retenu.**
  Chaque couche a ses propres mipmaps, sans bavure entre tuiles, donc l'`INSET`
  d'un demi-texel disparaît. C'est un peu plus de travail dans les shaders.

## Conception

### Nouveau module `packs.py`

- `find_packs(dirs)` retourne la liste des packs disponibles : un nom affiché (le
  dossier ou le zip, débarrassé des codes `§x`), un chemin, une description (tirée
  de `pack.mcmeta`), le format (1.8 ou 1.13+, détecté d'après le dossier de
  textures présent) et la résolution.
- Où chercher :
  1. `<user_data_dir>/resourcepacks/`, créé au premier lancement : l'endroit où le
     joueur dépose ses packs ;
  2. *(mon choix)* le dossier `resourcepacks/` de l'installation Minecraft locale,
     s'il existe (`~/Library/Application Support/minecraft` sur macOS,
     `%APPDATA%/.minecraft` sous Windows, `~/.minecraft` sous Linux) ;
  3. *(mon choix)* les `.jar` des versions installées
     (`versions/<v>/<v>.jar`), présentés comme « Minecraft 1.8 » etc. Ce sont des
     fichiers déjà sur la machine du joueur, lus sur place, jamais copiés.
- `load_pack(pack, generated_tiles)` retourne les tuiles finales, un tableau
  `(256, N, N, 4) uint8`, plus la liste des textures manquantes (pour la
  journalisation).
- La lecture des zips se fait avec `zipfile`, sans rien extraire sur le disque, et
  les PNG sont décodés avec **Pillow** (ajouté à `requirements.txt`). Un fichier
  illisible compte comme absent.
- **Pillow dans un `.venv` existant** : `PyCraft.command` ne lance aujourd'hui
  `pip install` qu'à la création du `.venv`. Il relance désormais
  `pip install -r requirements.txt` chaque fois que `requirements.txt` est plus
  récent qu'un fichier témoin `.venv/.requirements-installed`. Dans le jeu,
  `import PIL` est fait au chargement d'un pack, pas au lancement. Sans Pillow, la
  ligne Texture pack montre seulement `Default`, et l'aide dit
  « Install Pillow to use texture packs ».

### Table de correspondance tuile → fichiers

C'est un dictionnaire dans `packs.py` : `T_xxx → (nom_1.8, nom_1.13+)`. Exemples :

| Tuile | 1.8 | 1.13+ |
|---|---|---|
| `T_GRASS_TOP` | `grass_top` | `grass_block_top` |
| `T_GRASS_SIDE` | `grass_side` + `grass_side_overlay` | `grass_block_side` + `grass_block_side_overlay` |
| `T_LOG_SIDE` / `T_LOG_TOP` | `log_oak` / `log_oak_top` | `oak_log` / `oak_log_top` |
| `T_WHITE_WOOL` | `wool_colored_white` | `white_wool` |
| `T_PISTON_TOP` | `piston_top_normal` | `piston_top` |
| `T_WATER` | `water_still` | `water_still` |

- Si le nom de la version du pack manque, on essaie l'autre nom (des packs mêlent
  les deux), puis on retombe sur la tuile générée.
- Les blocs absents de la 1.8 (deepslate, mud, moss, etc.) n'ont pas de nom 1.8 et
  prennent la tuile générée dans un pack 1.8.
- Chaque tuile de `blocks.py` reçoit une entrée. Une tuile sans équivalent
  Minecraft garde la tuile générée, et c'est noté dans la table.

### Normalisation d'une texture

1. **Animée** (hauteur multiple de la largeur) : on garde le premier carré du haut.
2. **Taille** : toutes les tuiles prennent la taille **N du pack**, la plus
   fréquente parmi ses textures de blocs, bornée à **[16, 256]**. On agrandit au
   plus proche voisin et on réduit par moyenne de zone. Les tuiles générées
   (16 px) sont agrandies au plus proche voisin.
3. **Transparence** : alpha < 128 devient 0 (trou), le reste 255. Le mode de rendu
   reste en découpe, comme aujourd'hui.
   **Feuilles** : le jeu dessine leurs trous comme opaques, avec la couleur RVB du
   texel × teinte × 0,4 (les feuilles ombrées de l'intérieur ; seule la passe
   d'ombre les découpe). Dans un pack, les texels transparents contiennent souvent
   du noir ou n'importe quoi. Leur RVB est donc **remplacé par la moyenne des
   texels visibles de la feuille**, et ils restent à alpha 0. On garde ainsi le rendu
   actuel (couronnes pleines et sombres à l'intérieur, cohérentes avec le terrain
   lointain), sans faces internes en plus. *(Mon choix.)*
4. **Teinte de biome** : on reprend `TINT_ALPHA = 200`, que les shaders
   reconnaissent déjà (`0.5 < a < 0.9`).
   - Herbe du dessus, fougère, hautes herbes, feuilles teintées par le biome
     (`LEAVES`, `JUNGLE_LEAVES`, `ACACIA_LEAVES`), eau : tous les texels visibles
     sont marqués teintés. La texture grise du pack est éclaircie pour que sa
     moyenne vaille environ 204/255, la valeur qu'attendent les tuiles générées
     (`block_colors` divise par 0,8), afin que la teinte finale ne soit ni trop
     sombre ni trop claire.
   - Côté de l'herbe : la texture de côté, puis la surcouche (`*_overlay`) posée
     par-dessus. Ses texels opaques sont marqués teintés.
   - Feuilles d'épicéa, de bouleau et de chêne noir : le jeu ne les teinte pas par
     biome. Le gris du pack est multiplié par une couleur fixe (celle de Minecraft
     pour l'épicéa et le bouleau, et pour le chêne noir la moyenne de la tuile
     générée actuelle), et les texels sont marqués non teintés.
   - Si une texture censée être grise ne l'est pas (saturation moyenne élevée,
     pack déjà coloré), on ne la marque pas teintée, pour ne pas la teinter deux
     fois.

### Rendu (`renderer.py`)

- L'atlas 2D devient un **`texture_array`** `(N, N, 256)` RGBA, avec ses mipmaps.
  Filtre : `NEAREST` en agrandissement (pixels nets de près) et
  `NEAREST_MIPMAP_LINEAR` en réduction (pas de fourmillement de loin). Je mets
  l'anisotrope si moderngl le propose (×4 ou ×8), pour les sols en angle rasant.
- **Mipmaps faits sur le CPU**, pas par `build_mipmaps` : une moyenne qui pondère
  par l'alpha, pour éviter les halos noirs autour des trous des plantes et du
  verre. Pour les feuilles, les trous comptent comme les autres texels (leur RVB
  est déjà la moyenne de la feuille), puisqu'ils sont dessinés. Les
  texels teintés restent teintés à chaque niveau, sinon la teinte disparaît de
  loin. Pour le niveau 16→8 et au-delà, un texel est teinté si la majorité de ses
  sources le sont.
- Shaders des blocs : `v_uv` devient `(u, v)` dans la tuile, avec la couche
  `v_tile`. L'`INSET` est supprimé. `texture(atlas, vec3(uv, layer))`.
- Shader du terrain lointain : le `texelFetch` sur l'atlas 2D (`* 16`, codé en dur)
  devient un **`textureLod` sur la couche**, avec le niveau de mipmap calculé à
  partir des dérivées écran de `uv × N`. Un `texelFetch` au niveau 0 fourmillerait
  entre 2 et 6 px par bloc, avant que `far_albedo` ne passe à la moyenne de tuile.
- Ombres (`Shadows`) : elles lisent l'alpha des feuilles. Elles passent au tableau
  elles aussi.
- `tile_averages` et `block_colors` (`blocks.py`) travaillent sur `(256, N, N, 4)`
  au lieu de l'atlas 2D.
- Nouveau `Renderer.set_tiles(tiles)` : il remplace le tableau de textures dans
  `Renderer`, `FarTerrain` et `Shadows` (chacun garde sa propre référence).
  Il recrée `FarTerrain` sans passer par le retour anticipé de `set_lod_quality`
  (le calcul est mis en commun dans une méthode `_rebuild_far`), ce qui renvoie
  `block_colors` au processus d'échantillonnage. Il incrémente `far.version` pour
  que les cartes d'ombre soient redessinées (les trous des feuilles ont changé).
  Les maillages des blocs proches ne sont pas refaits.
- **`Palette`** reçoit une méthode `set_fixed(colors)` : elle remplace les 48
  couleurs des icônes et reconstruit sa table de tramage. Aujourd'hui, ces
  couleurs ne sont fixées qu'une fois, à la construction.

### Icônes (`main.py`)

- `icon_palette` reçoit les tuiles et réduit chacune à 16×16 (moyenne de zone,
  avec l'alpha), puis refait la palette de 48 couleurs par k-means, comme
  aujourd'hui.
- Changer de pack recharge la banque d'images des icônes et les 48 couleurs de
  palette (`Palette.set_fixed`).
- La banque d'icônes garde sa disposition : 16×16 tuiles de 16 px. `icon_palette`
  et `draw_icon` continuent d'utiliser `TILE = 16` et `ATLAS_TILES` pour cette
  banque, indépendamment de N.

### Réglages

- Une ligne **Texture pack** est ajoutée, avec pour valeurs `Default`, puis les
  packs trouvés, triés par nom. Elle se change comme les autres lignes (clic,
  gauche/droite).
- La ligne d'aide montre la description du pack et, pour `Default`, le chemin du
  dossier `resourcepacks/` où déposer ses packs.
- Le pack est appliqué tout de suite. Le chargement d'un pack 128 px doit tenir
  sous ~1 s ; sinon un écran « Loading textures… » s'affiche pendant le
  chargement, dans le thread principal (c'est rare et voulu par le joueur).
- La clé `"texture_pack"` (chemin) va dans `settings.json`. Si le pack n'existe
  plus au lancement, on prend `Default`.
- La liste des packs est relue à chaque ouverture des réglages, pour qu'un pack
  déposé pendant que le jeu tourne apparaisse.

### Erreurs

- Un zip illisible, un pack sans textures de blocs ou une exception au chargement :
  le pack par défaut est appliqué, la ligne d'aide affiche « Pack unreadable: … »,
  et le détail part dans la console.
- Les textures manquantes ne sont pas une erreur : elles sont journalisées une
  seule fois par pack (nombre et noms).

## Vérification

- Tests `pytest` sur `packs.py`, avec de **petits packs synthétiques générés par
  les tests** (aucun fichier de Mojang) : dossier et zip, nommage 1.8 et 1.13+,
  texture animée, tailles mêlées, fichier absent (repli), PNG corrompu, teinte de
  l'herbe et du côté avec surcouche, mipmaps qui gardent la teinte.
- Test manuel avec le `1.8.jar` local, et un pack 1.13+ si le joueur en a un :
  herbe et feuilles qui changent de couleur selon le biome, terrain lointain
  cohérent avec les blocs proches, icônes lisibles, aucun scintillement de loin,
  FPS (F3) inchangés.
- Pack `Default` : rendu identique à aujourd'hui, à l'œil (à l'exception des
  mipmaps, qui adoucissent le lointain).

## Laissé au builder

- La liste exacte des noms de fichiers pour chaque tuile, et le choix d'une
  texture proche quand aucune ne correspond bien.
- Les détails des mipmaps et du seuil de saturation pour détecter un gris.
- Le placement exact de la ligne dans les réglages et la formulation de l'aide.
- Le découpage en commits.

## Mes choix, à vérifier

- Lister aussi l'installation Minecraft locale et ses `.jar` de versions.
- Le tableau de textures avec mipmaps plutôt qu'un atlas plus grand.
- Ajouter Pillow comme dépendance plutôt qu'écrire un décodeur PNG. Le lanceur
  réinstalle quand `requirements.txt` change, et le jeu se passe de Pillow s'il
  manque.
- Les trous des feuilles d'un pack remplis avec la moyenne de la feuille (rendu
  actuel conservé) plutôt que des feuilles vraiment ajourées.
- Une taille de tuile unique par pack, bornée à 256 px.
- Le socle commun conçu juste après ce chantier, et non dedans (le roadmap le
  liait au chantier 1).
