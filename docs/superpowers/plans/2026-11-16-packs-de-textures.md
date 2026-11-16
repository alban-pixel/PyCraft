# Packs de textures — plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Charger un pack de textures Minecraft (dossier, zip ou jar ; 1.8 ou 1.13+) à sa résolution, avec mipmaps, choisi dans les réglages et appliqué à chaud.

**Architecture:** `packs.py`, un nouveau module en numpy et Pillow sans dépendance GL, découvre les packs et produit un tableau de tuiles `(256, N, N, 4) uint8`, avec le même codage d'alpha que l'atlas actuel (0 trou, 200 teinte de biome, 255 opaque). Le renderer envoie ce tableau à la carte sous forme de deux `TextureArray` mipmappés par le GPU : RGBA (alpha 0 ou 255) et un masque de teinte R8. Les icônes restent un atlas 16 px pour Pyxel.

**Tech Stack:** Python 3, numpy, Pillow (nouveau), moderngl 5.13 (`texture_array`), Pyxel, pytest (dev).

**Spec:** [`docs/superpowers/specs/2026-11-16-packs-de-textures-design.md`](../specs/2026-11-16-packs-de-textures-design.md)

## Global Constraints

- Aucun fichier de Mojang dans le dépôt : les tests fabriquent leurs PNG. Le test sur `1.8.jar` lit le fichier local et est sauté s'il est absent.
- Les tuiles sont numérotées de 0 à 255 (le numéro est un `u1` dans le vertex). 196 sont utilisées.
- La taille N d'un pack est la plus fréquente parmi ses textures, bornée à [16, 256], et arrondie à une puissance de 2.
- Codage d'alpha côté CPU : `0` trou, `TINT_ALPHA = 200` teinté par le biome, `255` opaque. Un alpha source < 128 devient un trou.
- Un pack illisible ou une exception au chargement ne doit jamais planter le jeu : on applique `Default` et on affiche « Pack unreadable: … ».
- Pillow n'est importé qu'au chargement d'un pack. Sans Pillow, seule l'option `Default` est proposée, avec l'aide « Install Pillow to use texture packs ».
- La clé `"texture_pack"` va dans `settings.json` (le chemin du pack, ou `None` pour `Default`).
- Les tests tournent depuis `pycraft-gpu/` avec `.venv/bin/python -m pytest tests -q`.

**Écart au design, décidé à la planification :** les mipmaps sont faits par le GPU (`build_mipmaps`), pas sur le CPU, parce que `TextureArray.write` de moderngl ne sait pas écrire un niveau. Pour que ça marche :

- la teinte quitte l'alpha et passe dans un second tableau (masque R8, mipmappé lui aussi) ;
- les trous des tuiles qui ne sont pas des feuilles reçoivent, avant l'envoi, la couleur moyenne de leurs texels visibles, pour éviter les halos ;
- le shader multiplie par `mix(1, tint, masque)`, ce qui donne une teinte correcte à chaque niveau ;
- le filtrage anisotrope matériel devient possible.

La tâche 5 reporte cet écart dans le design.

## Review Focus

1. **Pack `Default` identique à aujourd'hui.** Mêmes couleurs de près, et le terrain lointain se raccorde toujours aux blocs : tâches 2 et 5, test d'égalité de `tile_averages` et `block_colors`, et capture avant/après.
2. **Pack partiel ou mêlé**, avec quelques textures seulement, des noms 1.8 et 1.13 mélangés, des tailles 16 et 64 : toutes les tuiles prennent N, et les absentes reprennent la tuile générée agrandie (tâche 4).
3. **Pack déjà coloré** (herbe verte au lieu de grise) : pas de double teinte (tâche 4, `test_colored_grass_not_tinted`).
4. **Pack supprimé entre deux lancements**, ou `settings.json` qui pointe vers un chemin absent : démarrage en `Default` sans erreur (tâche 7).
5. **Zip qui contient autre chose** : PNG corrompu, image en mode `P` ou `LA`, dossier `textures/blocks` vide, ou jar sans textures. On replie sur la tuile générée, ou le pack n'est pas listé (tâches 3 et 4).

---

### Task 1: Pillow, lanceur, pytest

**Files:**
- Modify: `pycraft-gpu/requirements.txt`
- Create: `pycraft-gpu/requirements-dev.txt` (`-r requirements.txt` + `pytest>=8`)
- Modify: `PyCraft.command`
- Create: `pycraft-gpu/tests/__init__.py` (vide), `pycraft-gpu/tests/conftest.py` (ajoute `pycraft-gpu/` à `sys.path`)

- [ ] Ajouter `Pillow>=10` dans `requirements.txt`.
- [ ] Dans `PyCraft.command` : après la création éventuelle du `.venv`, si `requirements.txt -nt .venv/.requirements-installed`, lancer `.venv/bin/pip install -r requirements.txt` puis `touch .venv/.requirements-installed`. Garder les messages d'erreur actuels.
- [ ] Installer : `.venv/bin/pip install -r requirements-dev.txt`. Résultat attendu : `import PIL, pytest` fonctionne.
- [ ] Vérifier : `bash -n ../PyCraft.command` ne sort rien.
- [ ] Commit : `Add Pillow and pytest; reinstall requirements when they change`.

### Task 2: Les tuiles comme tableau `(256, N, N, 4)` dans `blocks.py`

**Files:**
- Modify: `pycraft-gpu/blocks.py` (`build_atlas`, `block_colors`)
- Modify: `pycraft-gpu/renderer.py:936-962` (`tile_averages`)
- Test: `pycraft-gpu/tests/test_tiles.py`

**Interfaces:**
- Produces:
  - `blocks.build_tiles(seed=7) -> np.ndarray` `(256, 16, 16, 4) uint8`, c'est-à-dire les tuiles générées. `build_atlas` est gardée et appelle `tiles_to_atlas(build_tiles(seed))`.
  - `blocks.tiles_to_atlas(tiles) -> (256, 256, 4) uint8` : réduit à 16 px (moyenne de zone pondérée par la couverture, alpha recodé à 0 / 200 / 255 par vote majoritaire), puis met les tuiles en grille 16×16. C'est l'atlas des icônes.
  - `blocks.resize_tile(tile, n) -> (n, n, 4)` : plus proche voisin pour agrandir, moyenne de zone pour réduire (même règle d'alpha).
  - `blocks.block_colors(tiles)` et `renderer.tile_averages(tiles)` prennent `(256, N, N, 4)`.

- [ ] Écrire les tests :
  - `test_tiles_match_atlas` : `tiles_to_atlas(build_tiles())` est identique à l'ancien `build_atlas()`, calculé une fois dans le test à partir de l'implémentation actuelle avant le changement. Faire une capture avec `np.save` dans `tmp_path` au moment d'écrire le test, ou comparer les tuiles 16 px réassemblées à la main.
  - `test_resize_roundtrip` : `resize_tile(resize_tile(t, 64), 16)` vaut `t` pour chaque tuile générée.
  - `test_resize_keeps_tint` : une tuile 32×32 dont la moitié gauche a l'alpha 200 et la droite 255, réduite à 16, garde 200 à gauche et 255 à droite.
  - `test_block_colors_size_free` : `block_colors(build_tiles())` et `block_colors` de chaque tuile agrandie à 64 sont égaux (`np.allclose`). Même test pour `tile_averages`.
  - `test_block_colors_unchanged` : `block_colors(build_tiles())` est égal à l'ancienne valeur, enregistrée une fois dans `tests/data/block_colors_default.npy`. C'est un fichier dérivé de nos propres textures, pas de Mojang.
- [ ] Lancer les tests : ils échouent (`build_tiles` n'existe pas).
- [ ] Implémenter. `block_colors` et `tile_averages` indexent `tiles[t]` au lieu de découper l'atlas. Mettre à jour leurs appelants (`main.py`, `renderer.py`) sans changer leur comportement : `main.py` construit `tiles = build_tiles()`, et passe `tiles_to_atlas(tiles)` à `icon_palette` et `tiles` au `Renderer`. Le `Renderer` envoie pour l'instant `tiles_to_atlas(tiles)` à la texture 2D existante.
- [ ] Lancer les tests : ils passent. Lancer aussi `python main.py` 10 s : le jeu démarre et se ressemble.
- [ ] Commit : `Keep the tiles as an array of tiles, any size`.

### Task 3: Découverte des packs (`packs.py`)

**Files:**
- Create: `pycraft-gpu/packs.py`
- Test: `pycraft-gpu/tests/test_packs_find.py`, `pycraft-gpu/tests/packfactory.py` (fabrique des packs synthétiques)

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class PackInfo: name: str; path: str; description: str; layout: str` (`"1.8"` ou `"1.13"`).
  - `pack_dirs(data_dir: str) -> list[str]` : `<data_dir>/resourcepacks` (créé s'il manque), puis `<mc>/resourcepacks`, avec `<mc>` qui vaut `~/Library/Application Support/minecraft` (macOS), `%APPDATA%/.minecraft` (Windows) ou `~/.minecraft` (Linux), s'il existe.
  - `minecraft_jars() -> list[str]` : les `<mc>/versions/*/*.jar`.
  - `find_packs(dirs: list[str], jars: list[str]) -> list[PackInfo]` : sous-dossiers, `.zip` et jars qui contiennent `assets/minecraft/textures/blocks/` (1.8) ou `.../block/` (1.13), avec au moins un `.png` dedans. Triés par nom, sans doublons de chemin. Un jar `versions/1.8/1.8.jar` s'affiche « Minecraft 1.8 ».
  - `open_pack(info) -> PackFiles`, avec `read(rel: str) -> bytes | None` et `names() -> set[str]` (chemins relatifs à `assets/minecraft/textures/<blocks|block>/`, sans `.png`). C'est aussi un gestionnaire de contexte. Un zip n'est jamais extrait.
  - `clean_name(s) -> str` : retire les codes `§x` et garde l'ASCII imprimable (la police 3×5).
  - `packfactory.make_pack(root, layout, textures: dict[str, np.ndarray], zip=False, description="test") -> str`.

- [ ] Écrire les tests :
  - `test_finds_dir_and_zip` : un dossier 1.8 et un zip 1.13 donnent 2 `PackInfo` avec les bons `layout`.
  - `test_ignores_non_packs` : un dossier sans textures, un zip corrompu (octets au hasard) et un `.txt` ne sont pas listés, sans exception.
  - `test_description_from_mcmeta` : `pack.mcmeta` avec `{"pack": {"description": "§aHello §lworld"}}` donne `"Hello world"`. Un `pack.mcmeta` invalide donne `""`.
  - `test_description_component` : une description sous forme d'objet ou de liste JSON (`{"text": "Hi"}`, `[{"text": "A"}, "B"]`) donne `"Hi"` et `"AB"`.
  - `test_jar_name` : un zip factice placé à `versions/1.8/1.8.jar` s'affiche « Minecraft 1.8 ».
  - `test_open_pack_reads` : `names()` contient `"stone"`, `read("stone")` retourne des octets PNG, et `read("absent")` retourne `None`.
- [ ] Lancer les tests : ils échouent.
- [ ] Implémenter. Si les deux dossiers de textures existent dans un pack, prendre celui qui a le plus de PNG.
- [ ] Lancer les tests : ils passent.
- [ ] Commit : `Find texture packs: folders, zips and installed Minecraft versions`.

### Task 4: Chargement et normalisation d'un pack

**Files:**
- Modify: `pycraft-gpu/packs.py`
- Test: `pycraft-gpu/tests/test_packs_load.py`

**Interfaces:**
- Consumes: `PackInfo`, `open_pack`, `blocks.resize_tile`, `blocks.build_tiles`.
- Produces:
  - `TILE_FILES: dict[int, tuple[str | None, str | None]]` : `T_xxx → (nom 1.8, nom 1.13)`. Il y a une entrée par tuile utilisée dans `BLOCK_TILES` ; `(None, None)` signifie « toujours générée » (commentaire « pas d'équivalent »).
  - `SPECIAL` : le côté de l'herbe (`T_GRASS_SIDE`) prend `grass_side` + `grass_side_overlay` en 1.8, et `grass_block_side` + `grass_block_side_overlay` en 1.13. Le côté du podzol et du mycélium : texture simple.
  - `load_pack(info: PackInfo, base: np.ndarray) -> tuple[np.ndarray, list[str]]` : retourne les tuiles `(256, N, N, 4)` et les noms manquants. Lève `PackError(str)` si le pack ne fournit aucune tuile.
  - Constantes : `BIOME_TINTED = {T_GRASS_TOP, T_TALL_GRASS, T_FERN, T_LEAVES, T_JUNGLE_LEAVES, T_ACACIA_LEAVES, T_WATER}` ; `FIXED_LEAF = {T_SPRUCE_LEAVES: (0x61, 0x99, 0x61), T_BIRCH_LEAVES: (0x80, 0xA7, 0x55), T_DARK_OAK_LEAVES: moyenne de la tuile générée}` ; `LEAF_TILES` (les six feuilles).
- Règles (à reprendre du design, section « Normalisation ») :
  - texture animée : on garde le carré du haut ;
  - mode Pillow converti en `RGBA` ;
  - N = la taille la plus fréquente, arrondie à la puissance de 2 la plus proche, dans [16, 256] ;
  - l'alpha source < 128 devient un trou ;
  - tuile de `BIOME_TINTED` : si la saturation moyenne (max−min sur RGB, de 0 à 1) des texels visibles est < 0,15, ses texels visibles passent à l'alpha 200 et sont mis à l'échelle pour que leur moyenne de luminance vaille 204/255. Sinon la tuile reste telle quelle (déjà colorée) ;
  - surcouche du côté de l'herbe : les texels opaques de la surcouche remplacent ceux du côté, avec l'alpha 200 (même test de gris et même mise à l'échelle) ;
  - `FIXED_LEAF` : le RGB est multiplié par la couleur / 255 et l'alpha vaut 255 ;
  - `LEAF_TILES` : le RGB des trous est remplacé par la moyenne des texels visibles ;
  - une tuile absente ou illisible prend `resize_tile(base[t], N)`.

- [ ] Écrire les tests (packs synthétiques de `packfactory`) :
  - `test_every_used_tile_mapped` : chaque tuile qui apparaît dans `BLOCK_TILES` est une clé de `TILE_FILES`.
  - `test_size_is_most_common` : 3 textures en 64 et 1 en 16 donnent `N == 64` ; la tuile 16 et les tuiles absentes sont agrandies au plus proche voisin.
  - `test_animated_takes_first_frame` : un `water_still` 16×64 dont le premier carré est rouge et le reste bleu donne une tuile `T_WATER` rouge.
  - `test_fallback_names` : un pack 1.13 qui contient `log_oak` (le nom 1.8) remplit `T_LOG_SIDE`.
  - `test_missing_uses_generated` : un pack qui n'a que `stone` donne `tiles[T_STONE]` qui vient du pack et `tiles[T_DIRT] == resize_tile(base[T_DIRT], N)`. `missing` contient `"dirt"`.
  - `test_grey_grass_tinted` : `grass_top` gris 128 uniforme donne l'alpha 200 partout et un RGB d'environ 204.
  - `test_colored_grass_not_tinted` : `grass_top` vert (40, 160, 40) donne l'alpha 255.
  - `test_grass_side_overlay` : le côté brun plus une surcouche grise opaque sur les 3 lignes du haut donnent l'alpha 200 sur ces lignes et 255 en dessous.
  - `test_spruce_fixed_color` : `leaves_spruce` gris 255 donne un RGB qui vaut `(0x61, 0x99, 0x61)` aux texels visibles, avec l'alpha 255.
  - `test_leaf_holes_filled` : des feuilles avec des trous de RGB noir donnent un RGB des trous égal à la moyenne des texels visibles.
  - `test_corrupt_png_is_missing` : un `stone.png` corrompu met `"stone"` dans `missing`, sans exception.
  - `test_empty_pack_raises` : un pack sans aucune texture connue lève `PackError`.
  - `test_real_minecraft_jar` (sauté si `~/Library/Application Support/minecraft/versions/1.8/1.8.jar` est absent) : `N == 16`, et `len(missing)` ne dépasse pas le nombre de tuiles sans nom 1.8, plus 5.
- [ ] Lancer les tests : ils échouent.
- [ ] Remplir `TILE_FILES` pour les 196 tuiles. Vérifier les noms 1.8 dans la liste du jar local (`unzip -l`), sans rien copier. Pour la 1.13, utiliser les noms d'aujourd'hui (`oak_planks`, `white_wool`, `terracotta`, `glass`, etc.).
- [ ] Implémenter `load_pack`.
- [ ] Lancer les tests : ils passent.
- [ ] Commit : `Load a texture pack into the tiles, with biome tints and fallbacks`.

### Task 5: Le renderer passe au tableau de textures mipmappé

**Files:**
- Modify: `pycraft-gpu/renderer.py` : `BLOCK_VERTEX_SHADER`, `BLOCK_FRAGMENT_SHADER`, `LOD_FRAGMENT_SHADER` (le passage `texelFetch(atlas...` vers la ligne 636), `far_albedo` (vers la ligne 275, s'il lit l'atlas), `Renderer.__init__` (vers 1862), `FarTerrain.__init__`, `Shadows`.
- Modify: `docs/superpowers/specs/2026-11-16-packs-de-textures-design.md` (reporter l'écart des mipmaps GPU)
- Test: `pycraft-gpu/tests/test_upload.py`, plus une capture sans fenêtre

**Interfaces:**
- Consumes: les tuiles de la tâche 2.
- Produces:
  - `renderer.split_tiles(tiles) -> tuple[np.ndarray, np.ndarray]` : retourne le RGBA `(256, N, N, 4)`, avec l'alpha 0 ou 255 et les trous des tuiles qui ne sont pas des feuilles remplis par la moyenne visible, et le masque `(256, N, N) uint8` (255 où l'alpha vaut 200).
  - `renderer.make_tile_textures(ctx, tiles) -> tuple[TextureArray, TextureArray]` : `ctx.texture_array((N, N, 256), 4)` et `(N, N, 256), 1`, avec `build_mipmaps()`, `filter = (NEAREST_MIPMAP_LINEAR, NEAREST)` et `anisotropy = 8.0`.
  - Unités : on garde `ATLAS_UNIT` pour le RGBA et on ajoute `TINT_UNIT` pour le masque.
  - `Renderer(ctx, world, tiles, width, height, fixed_colors, fov=70)` : `tiles` remplace `atlas`.
- Shaders :
  - Les blocs utilisent `uniform sampler2DArray atlas; uniform sampler2DArray tint_mask;` ; `v_uv = CORNERS[in_info.y]` sans `INSET` ; `tex = texture(atlas, vec3(v_uv, v_tile))` ; `t = texture(tint_mask, vec3(v_uv, v_tile)).r` ; `albedo *= mix(vec3(1), v_tint, t)`. Le test des trous reste `tex.a < 0.5`.
  - Le terrain lointain calcule au début de `main()`, en flux uniforme, `vec2 g = <coordonnée texel continue>` (la position monde projetée sur le plan de la face, pas `fract`), `dx = dFdx(g)` et `dy = dFdy(g)`. Il lit ensuite avec `textureGrad(atlas, vec3(fract(g), tile), dx, dy)`, et de même pour le masque. Le `* 16` disparaît.
  - Les ombres (passe 2) lisent la même `atlas` (`sampler2DArray`).
  - Tous les `tex.a > 0.5 && tex.a < 0.9` sont remplacés par le masque.

- [ ] Écrire les tests :
  - `test_split_tiles` : sur une tuile avec les alphas {0, 200, 255}, le RGBA a l'alpha {0, 255, 255} et le masque {0, 255, 0}. Le RGB d'un trou de verre vaut la moyenne des texels visibles, et celui d'un trou de feuille ne change pas.
  - `test_upload_headless` : avec `moderngl.create_standalone_context()`, `make_tile_textures(ctx, build_tiles())` donne `size == (16, 16)` et `layers == 256`. Sauté si aucun contexte n'est disponible.
- [ ] Avant tout changement de shader, faire une capture de référence sans fenêtre : un script dans le scratchpad lance `App(headless=True)`, fait tourner une trentaine de frames sur la vue du titre et enregistre `pyxel.screen` en PNG.
- [ ] Implémenter.
- [ ] Lancer les tests : ils passent. Refaire la capture et la comparer à la référence en la lisant à l'œil. Attendu : mêmes couleurs de près, lointain un peu plus doux, pas de bord noir autour des fleurs ni du verre.
- [ ] Mettre à jour le design : section « Rendu », mipmaps faits par le GPU avec le masque de teinte séparé, et la raison.
- [ ] Commit : `Draw blocks from a mipmapped texture array, tint in its own mask`.

### Task 6: Changer de tuiles à chaud

**Files:**
- Modify: `pycraft-gpu/renderer.py` (`Renderer.set_lod_quality`, nouveau `set_tiles`, `Palette`)
- Test: `pycraft-gpu/tests/test_upload.py`

**Interfaces:**
- Produces:
  - `Renderer.set_tiles(tiles) -> None` : libère et recrée les deux `TextureArray`, met à jour `self.far.atlas`, `self.far.tint_mask`, `self.shadows.atlas` et `self.shadows.tint_mask`, puis appelle `_rebuild_far(tiles)`.
  - `Renderer._rebuild_far(tiles, spacing=None, size=None, levels=None)` : c'est le corps actuel de `set_lod_quality` sans le retour anticipé. Il recrée `FarTerrain` (`tile_averages` et `block_colors` à partir de `tiles`, ce qui envoie `configure` à l'échantillonneur), avec `version = ancienne + 1`, et libère l'ancien. `set_lod_quality` garde son retour anticipé et appelle `_rebuild_far`.
  - `FarTerrain.__init__(ctx, program, world, atlas_texture, tint_texture, tiles, sampler, spacing, size, levels)` : `self.tiles` remplace `self.atlas_data`.
  - `Palette.set_fixed(colors: list[int]) -> None` : il réécrit les entrées 16 à 63 de `self.lab` à partir de 0xRRGGBB et met `pending = True`, pour que `apply()` reconstruise la table de tramage et incrémente `version`.

- [ ] Écrire le test `test_palette_set_fixed` (contexte autonome, sauté sinon) : après `set_fixed([0xFF0000] * 48)` puis `apply()`, `colors[16] == 0xFF0000` et `version` a augmenté.
- [ ] Lancer le test : il échoue.
- [ ] Implémenter.
- [ ] Lancer le test : il passe. Un script sans fenêtre appelle `set_tiles(resize de build_tiles() à 64)`, fait tourner 30 frames et enregistre une capture identique à la référence de la tâche 5 à la mipmap près.
- [ ] Commit : `Swap the tiles while the game runs`.

### Task 7: Réglage Texture pack dans `main.py`

**Files:**
- Modify: `pycraft-gpu/main.py` (`DEFAULT_SETTINGS`, `load_settings`, `__init__` vers 224-253, `setting_rows` vers 570-581, nouvelle `change_texture_pack`, `icon_palette` inchangé)
- Test: `pycraft-gpu/tests/test_settings_pack.py`

**Interfaces:**
- Consumes: `packs.find_packs`, `pack_dirs`, `minecraft_jars`, `load_pack`, `PackError` ; `Renderer.set_tiles` ; `Palette.set_fixed` ; `blocks.tiles_to_atlas`.
- Produces:
  - `DEFAULT_SETTINGS["texture_pack"] = None`. `load_settings` garde une valeur `str` seulement si `os.path.exists`.
  - `App.apply_pack(path: str | None) -> str` : il charge le pack (ou `build_tiles()` si `None`), appelle `renderer.set_tiles`, recalcule `icon_palette(tiles_to_atlas(tiles))`, réécrit la banque `pyxel.images[0]`, appelle `renderer.palette.set_fixed(icon_colors)` et retourne le message d'aide (`""` si tout va bien). En cas d'exception (`PackError`, `OSError`, `ValueError`, `ImportError`) : il revient à `Default`, met `settings["texture_pack"] = None` et retourne `"Pack unreadable: <raison courte>"`. Le détail part sur `stderr`, et les noms manquants sont imprimés une fois.
  - `next_pack(current: str | None, packs: list[PackInfo], step: int) -> str | None` : fonction pure qui parcourt `[None] + [p.path for p in packs]` de façon circulaire. Un `current` inconnu donne l'élément d'indice `step % len`.
  - La ligne de réglages `("Texture pack", <nom ou "Default">, self.change_texture_pack, <aide>)`. L'aide affiche la description du pack ; pour `Default`, `"Put packs in <data_dir>/resourcepacks"` ; le message d'erreur s'il y en a un ; ou `"Install Pillow to use texture packs"`. La liste des packs est relue quand on entre dans l'écran des réglages (`self.packs`).
  - Au démarrage, `__init__` appelle `apply_pack(self.settings["texture_pack"])` après la création du `Renderer`, qui est construit avec `build_tiles()`.

- [ ] Écrire les tests :
  - `test_next_pack_cycles` : `None → a → b → None` avec `step=1`, et à l'envers avec `step=-1`.
  - `test_next_pack_unknown_current` : un `current` qui n'est pas dans la liste donne un résultat valide.
  - `test_load_settings_drops_missing_pack` : un `settings.json` dont `texture_pack` pointe vers un chemin absent donne `None`. Tester `load_settings` sur un objet sans Pyxel : en faire une fonction libre `parse_settings(saved: dict) -> dict` appelée par la méthode.
- [ ] Lancer les tests : ils échouent.
- [ ] Implémenter. Si `apply_pack` dure plus de 0,3 s, dessiner d'abord « Loading textures... » et appliquer le pack à la frame suivante, comme l'état `generating`.
- [ ] Lancer les tests : ils passent. Puis vérifier sans fenêtre : `App(headless=True)`, `apply_pack(<1.8.jar>)`, 30 frames, capture. Les textures du pack sont visibles, l'herbe est verte, et les icônes de la hotbar sont celles du pack.
- [ ] Commit : `Choose a texture pack in the settings`.

### Task 8: Docs et essai réel

**Files:**
- Modify: `pycraft-gpu/README.md` (ligne Texture pack du tableau des réglages ; section « Texture packs » : où déposer, formats, ce qui n'est pas pris en charge)
- Modify: `docs/technique.md` (section Textures : tableau de textures, masque de teinte, packs)
- Modify: `docs/roadmap.md` (chantier 1 fait ; le piston et le levier relèvent du socle et du chantier 4 ; le socle sera conçu à part)

- [ ] Écrire les docs.
- [ ] Lancer toute la suite : `.venv/bin/python -m pytest tests -q` passe.
- [ ] Lancer le jeu en vrai (`python main.py`), passer du pack `Default` au pack « Minecraft 1.8 » et revenir. Vérifier : pas de plantage, F3 avec des FPS stables, terrain lointain cohérent.
- [ ] Commit : `Document texture packs`.
