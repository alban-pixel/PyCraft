# PyCraft — Feuille de route vers un jeu de survie complet

> Plan établi le 16 novembre 2026, sur la branche `gpu-renderer-dev`. **Chantier 1
> (packs de textures) fait le 16 novembre 2026** : voir
> [`superpowers/specs/2026-11-16-packs-de-textures-design.md`](superpowers/specs/2026-11-16-packs-de-textures-design.md).
> Les autres ne sont pas commencés. État actuel du moteur : [`technique.md`](technique.md) et
> [`pycraft-gpu/README.md`](../pycraft-gpu/README.md).

## Objectif

Faire de PyCraft un jeu abouti dans le genre de Minecraft, au niveau de
fonctionnalités des versions autour de la 1.8 : mode survie, craft, mobs,
physique des liquides, redstone fonctionnelle, meilleure interface, et un
gestionnaire de packs de textures pour charger un pack au format Minecraft au
lieu de dessiner chaque texture par code.

## Point de départ

Ce que le jeu est aujourd'hui, et ce que ça implique pour la suite :

- **Créatif uniquement.** 184 numéros de blocs, tous des cubes pleins ou des
  plantes en deux quads croisés. Pas d'objets, pas de piles, pas de vie.
- **Un octet par bloc, sans état.** `world.py` stocke des sections 16×16×16 en
  `uint8`. Il reste 72 numéros libres, loin de ce qu'il faut pour la puissance de
  la poudre, les orientations, les niveaux de liquide ou les portes.
- **Le maillage ne connaît que deux formes.** `builder.py` produit des cubes et
  des plantes croisées. Poudre, répéteur, levier, torche, dalle, escalier, porte
  demandent de nouvelles formes.
- **Pas d'horloge de simulation.** Rien ne « tique » : l'eau ne coule pas, les
  machines (piston, lampe, TNT, four) ne sont que des textures.
- **Pas de lumière de bloc.** Les lampes brillent mais n'éclairent rien, et les
  grottes ne sont pas sombres.
- **Textures générées par code.** `build_atlas()` dans `blocks.py` dessine 196
  tuiles de 16×16 dans un atlas de 256×256. L'atlas ne sert que dans le
  processus principal (texture GPU, icônes Pyxel, moyennes par tuile et couleurs
  du terrain lointain) : les processus de maillage n'utilisent que les numéros
  de tuile. Changer de pack ne demande donc pas de régénérer le monde.
- **Interface.** Tout passe par `ui.py`, avec la police 3×5 de Pyxel et ses 16
  couleurs fixes.

## Le socle commun

Les chantiers 2 à 5 ont tous besoin des mêmes fondations. Elles sont posées une
seule fois, avec le chantier 1, pour ne changer le format des sauvegardes
qu'une fois :

- un **état par bloc** (puissance, orientation, niveau de liquide, ouvert/fermé) ;
- des **formes non cubiques** dans le maillage ;
- une **horloge de ticks** à pas fixe, indépendante de la fréquence d'images ;
- un **registre d'objets** distinct des blocs (outils, lingots, nourriture).

Reste à décider : élargir les blocs à 16 bits, ou garder l'octet et ajouter un
tableau d'état à côté.

## Les chantiers

Chacun laisse le jeu jouable une fois terminé, et sera conçu séparément avant
d'être codé.

| # | Chantier | Contenu |
|---|---|---|
| 1 | **Packs de textures** | Lecture d'un pack au format Minecraft (dossier ou zip) déposé par le joueur, table de correspondance tuile → fichier, textures générées gardées comme pack par défaut, choix du pack dans les réglages. Fournit aussi les icônes d'objets. |
| 2 | **Survie** | Inventaire avec piles, temps de casse, drops, outils et durabilité, craft, four, vie, faim, dégâts de chute, mort et réapparition. L'interface est refaite ici, avec les nouveaux écrans. |
| 3 | **Liquides** | Eau et lave qui coulent, sources et niveaux, interaction eau/lave. |
| 4 | **Redstone** | Poudre, torche, levier, bouton, plaque de pression, répéteur, lampe, pistons, TNT. |
| 5 | **Mobs et lumière** | Lumière de bloc (grottes sombres, torches qui éclairent), animaux, monstres qui apparaissent dans le noir, combat. |
| 6 | **Le reste** | Agriculture, portes, escaliers, dalles, lits, coffres. |

**Pourquoi cet ordre.** Les packs sont le chantier le plus court, règlent les
textures tout de suite et fournissent les icônes d'objets dont la survie a
besoin. L'alternative est de commencer par la redstone, comme dans la demande
d'origine : elle force à construire le socle d'entrée, mais les textures
actuelles restent plus longtemps et les objets de survie n'ont pas d'icônes tant
que les packs ne sont pas là.

## Cadre

- **Identité propre.** Le jeu garde son nom et son propre style d'interface
  plutôt qu'une copie à l'identique.
- **Aucun fichier de Mojang dans le dépôt.** Le gestionnaire lit les packs que
  le joueur fournit ; il n'en télécharge et n'en embarque aucun.
- **Mobs originaux.** Mêmes rôles (animaux, monstre nocturne, tireur, monstre
  qui explose), mais des créatures propres au jeu, pas les personnages de
  Minecraft.

## Hors périmètre pour l'instant

Nether, End, enchantements, potions, villageois, multijoueur. Chacun est un
projet à lui seul, à reconsidérer une fois les six chantiers terminés.

## Questions ouvertes

- ~~Par quel chantier commencer~~ : les packs de textures, faits.
- ~~Quelles textures sont « buggy »~~ : ce sont les blocs incomplets. Le piston
  ne se sépare pas en deux (base et tête) et en crée un « fantôme » à côté, et le
  levier n'existe pas. Un pack ne les corrige pas : il leur faut l'état par bloc
  et les formes non cubiques du **socle**, puis la redstone (chantier 4). Le socle
  sera conçu à part, avant la survie.
- **Ce que « meilleure interface » veut dire** au-delà des écrans de survie :
  ce qui gêne dans l'interface actuelle.
