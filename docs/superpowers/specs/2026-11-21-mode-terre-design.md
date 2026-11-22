# Mode Terre

> Design du 21 novembre 2026, écrit à la demande du joueur (« tu peux écrire le plan »). **Pas
> encore relu par lui.** Les choix marqués *(choix)* ont été faits sans lui et peuvent changer.

## Intention

Jouer dans PyCraft sur de vrais paysages de la Terre, à un bloc par mètre, avec leurs vraies
altitudes. L'idée vient d'une vidéo du mod Earth Platform pour Minecraft. Le but est que ce soit
**très beau**, pas de refaire ce mod à l'identique.

Ce que le joueur a dit :

- l'entrée dans un monde peut prendre un peu de temps, si ça évite les gels en jeu ;
- les données fausses doivent être nettoyées ;
- sans internet, une génération normale qui marche suffit, même moins belle ;
- la Terre entière n'est pas obligatoire.

## Objectifs

1. Choisir un lieu célèbre, ou une latitude et une longitude, et y jouer.
2. Vrai relief, vraie mer, neige, roche et végétation selon le vrai climat.
3. Voir jusqu'à 65 km.
4. Aucun gel dû au réseau pendant le jeu.
5. Rejouer hors ligne là où on est déjà allé.

## Non-objectifs

- Villes, routes, bâtiments. Vraies grottes et vrais minerais (ceux du jeu sont gardés).
- Fosses océaniques à leur vraie profondeur : elles sont écrasées à 500 blocs.
- Courbure de la Terre, ombres au-delà de 8 km.
- Carte ou globe de voyage, altitudes IGN à 1 à 5 m en France : après, avec leur propre plan.

À éviter absolument : un monde normal du joueur écrasé par un essai du mode Terre, ou un jeu
normal (sans Terre) qui change d'aspect ou demande internet.

## Ce qui a été mesuré

Le 21 novembre 2026, sur cette machine et sa connexion :

| Mesure | Résultat |
|---|---|
| Tuiles à télécharger pour entrer, vue à 65 km, LOD medium | 28 à 34 tuiles, 2,4 à 4,6 Mo, 0,6 à 0,8 s |
| Les mêmes en LOD ultra | 48 à 81 tuiles, 4 à 11,2 Mo, 0,9 à 1,6 s |
| Lecture bicubique de 65 536 altitudes | 10 ms (générateur actuel complet : 159 ms) |
| Nettoyage d'une tuile | 54 à 85 ms |
| Everest, zoom 14 | −2 135 à 8 749 m avant nettoyage, 5 453 à 8 749 m après |
| Na Pali (Hawaï), zoom 14 | −8 535 à 898 m avant, −50 à 898 m après |
| Mont Blanc, Cervin, Yosemite, Fuji, Paris, K2… | aucun pixel modifié : le nettoyage ne touche pas au bon terrain |

Deux leçons pour le nettoyage :

- **Comparer au zoom grossier ne marche qu'aux zooms 13 et 14.** Aux zooms 8 à 12, ça rabote les
  sommets (Everest : 8 538 → 6 964 m au zoom 8). Là, on ne retire que les pixels isolés.
- **La mer vaut 0 aux zooms fins.** Les vrais fonds sont dans le zoom 8 (Mariannes : −10 891 m).

Le nettoyage ne rend pas ce que les données n'ont pas. L'Everest y culmine à 8 749 ou 8 750 m au lieu de
8 849 m : une petite table de sommets rehausse ceux-là.

## Approches

| Approche | Pour | Contre |
|---|---|---|
| **A. Tuiles téléchargées à la demande, gardées sur disque** (retenue) | toute la Terre, entrée en quelques secondes, rejouable hors ligne | gérer l'attente des tuiles |
| B. Quelques zones préparées, livrées avec le jeu | jamais d'internet | 5 à 10 lieux, dépôt qui grossit |
| C. Une carte mondiale grossière livrée, plus du bruit | simple, hors ligne | paysages méconnaissables |

A est retenue *(choix)* : le coût d'entrée mesuré est faible. Son défaut, l'attente, est traité plus bas.

## Décisions

### Pas de gel

Oui à l'écran de chargement, mais il ne suffit pas seul : en avançant, on sort de ce qu'il a chargé.
Il y a donc quatre protections.

1. **À l'entrée**, un écran « Downloading the Earth… 63 % » attend toutes les tuiles de la vue,
   puis l'écran actuel attend les blocs.
2. **En jeu**, un processus à part télécharge et nettoie. Il garde au moins 2 tuiles d'avance (environ
   4 km) autour du joueur : près de 100 s de vol rapide (42 blocs/s).
3. **Un morceau dont la tuile manque n'est pas généré** : le terrain lointain reste à sa place.
4. **Le joueur qui arrive au bord est retenu** par un mur invisible et un message. `/tp` vers un
   endroit pas prêt repasse par l'écran de chargement.

Le fil du jeu ne fait jamais d'appel réseau, et ne génère jamais de colonne pas prête.

### Sans internet

- **Lieu déjà visité** : il se charge depuis le disque.
- **Nouveau lieu** : un écran propose *Retry*, *Play a generated world* (génération normale, dans sa
  propre sauvegarde) ou *Back*.
- **Coupure en jeu** : une tuile qui échoue après ses essais est remplacée par la plus proche tuile
  grossière du disque, agrandie, avec le petit relief ajouté par bruit. C'est moins beau, mais continu.
  Elle est redemandée à la session suivante. Une construction faite dessus peut alors flotter ou être
  enterrée : c'est accepté.

### Coordonnées

- Mercator local : le bloc (0, 0) est le lieu choisi, +x l'est, +z le sud. Un bloc vaut un mètre à la
  latitude du lieu. À 65 km, l'erreur est de 1 à 2 %.
- **Une sauvegarde par lieu** *(choix)* : `earth/<lat><lon>.npz`. L'échelle est juste partout où on
  joue, et la sauvegarde normale `world2.npz` n'est jamais touchée.
- Niveau de la mer : 512, comme aujourd'hui. `WORLD_HEIGHT` passe de 4 096 à 10 240 (Everest : 9 361).
  Les sections sont créées à la demande, donc ça ne coûte pas de mémoire.
- Fonds marins : vrais jusqu'à 200 m, puis `200 + 300·tanh((p − 200) / 2000)`.

### Données

| Donnée | Source | Licence | Quand |
|---|---|---|---|
| Altitudes | AWS Terrain Tiles (Terrarium), zooms 0 à 14 | par source, crédits obligatoires | en jeu |
| Climat | CHELSA 2.1 (température, pluie) | CC0 | une fois, par un outil ; fichier ≤ 3 Mo dans le dépôt |
| Occupation du sol | ESA WorldCover 2021, 10 m | CC BY 4.0 | en jeu (lot 3) |

Crédits dans `docs/CREDITS.md` et sur l'écran des lieux. Le code est écrit à partir des données
publiques ; aucun code d'Earth Platform (LGPL) n'est traduit. Les requêtes n'envoient que des numéros de
tuiles, sans rien sur le joueur.

### Nettoyage

- Zooms 13 et 14 : référence = zoom −3, filtré deux fois par une médiane 3×3, bilinéaire. Un pixel est
  faux si l'écart dépasse `150 + relief local`. Le défaut est étendu de 3 pixels là où l'écart dépasse
  `60 + relief local / 2`. Un pixel faux prend la valeur de la référence.
- Zooms 0 à 12 : un pixel est faux si son écart à la médiane de ses 8 voisins dépasse
  `400 + 4 × (écart interquartile des voisins)`. Il prend cette médiane.
- Zooms 9 à 14 : un pixel à moins de 0,5 m de zéro, là où le zoom 8 est sous −1 m, prend le zoom 8.
- Sommets : pour chacun, `altitude vraie − altitude lue` est ajoutée avec un poids
  `exp(−(d / 250 m)²)`, seulement si l'écart est entre 0 et 150 m.

### Relief fin

Les données ont un point tous les 5 à 30 m. Entre eux : interpolation bicubique, plus un bruit
`fbm2(x/27, z/27, 3) × clip(0,6 + 1,8 × pente, 0,6, 6)`, à zéro sur l'eau, présent jusqu'à un
espacement de 8 blocs.

### Biomes (lots 1 et 3)

Température au sol `t = t0 − 0,0065 × altitude` (°C), pluie `p` (mm/an), `relief` = écart d'altitude
à 500 m alentour, `haut` = altitude > 900 m. La première règle vraie gagne :

1. mer : `t < −8` océan gelé, profondeur > 60 océan profond, sinon océan ;
2. altitude ≤ 1,5 m : plage ;
3. `haut` et `t < −6 − 4·clip((800 − p)/600, 0, 1)` : pics enneigés ;
4. `haut` et `t < −3,5` : **rocheux** (nouveau biome, pierre et gravier) ;
5. `haut` et `t < −1` : alpage ;
6. `t < −14`, ou `t < −9` et `p < 250` : toundra ; `t < −5` : taïga enneigée ; `t < 3` : taïga ;
7. `p < 10t + 70` : badlands si `relief > 250`, sinon désert ;
8. `p < 20t + 140` : savane si `t ≥ 18`, sinon plaine ;
9. `t ≥ 20` : jungle si `p ≥ 1500`, sinon savane ;
10. `t < 8` : forêt de bouleaux ; sinon forêt. Au lot 1, un bruit lisse y met des plaines.

Valeurs du jeu : `température = 0,35 + 0,0433 × (t − 19)` ; humidité interpolée de
`p = 0, 250, 700, 1500, 3000` vers `−0,8, −0,4, 0, 0,4, 0,6`.

Au lot 3, WorldCover passe avant les règles 2 et 6 à 10 : arbres → la forêt du climat ; herbe,
cultures et bâti → plaine ou savane ; sol nu → désert, badlands ou rocheux ; neige → glacier si la
pente est douce, sinon pics ; zones humides et mangroves → marais ; eau → lac ou rivière.

### Eau

- Lots 1 et 2 : mer seulement, là où l'altitude est ≤ 0. La mer Morte et les Pays-Bas sont donc noyés.
- Lot 3 : l'eau de WorldCover. Niveau = plus basse altitude dans 9 pixels ; fond plus bas de
  `1 + 6f²` blocs, où `f` est la part d'eau alentour. La terre sous 0 m redevient sèche.

### Vue lointaine (lot 2)

- Dans un monde Terre : limite à 65 536 blocs, et 10, 9, 10 et 9 niveaux en low, medium, high et
  ultra. Le monde normal garde sa limite de 8 000 et ses niveaux.
- Un réglage séparé `earth_distance` : 512, 1024, 2048 ou 4096 chunks. 2048 (33 km) par défaut
  *(choix)*.
- Brume `min(1/4500, 1,78 / distance)`, identique à aujourd'hui jusqu'à 8 km. Plan proche du terrain
  lointain à 16 blocs au-delà de 8 km, pour la précision de profondeur.
- Nuages à `max(mer + 940, sol du départ + 1200)`.

### Interface

Titre → *Earth* → liste de 12 lieux (« saved » pour ceux déjà joués) → Survie ou Créatif si
nouveau. Au départ, le joueur est au sol, au sec, tourné vers le sommet du lieu. Commande
`/earth <lat> <lon>` pour tout autre endroit.

## Lots

Chacun est une branche courte et une pull request, et laisse le jeu jouable.

1. **Relief** : données, nettoyage, climat, générateur, chargement, menus. **Le joueur regarde le rendu
   et décide de la suite.**
2. **Horizon** : 65 km.
3. **Sol et eau** : WorldCover, forêts, glaciers, lacs, rivières.

## Réussi si

- Entrée dans un nouveau lieu en moins de 20 s avec une connexion normale.
- 5 minutes de vol rapide en ligne droite : aucune image de plus de 100 ms due au terrain, et le mur
  invisible n'apparaît pas.
- Chamonix → Mont Blanc et le camp de base → Everest se reconnaissent.
- Réseau coupé pendant le jeu : il continue. Tests verts, monde normal identique.

## Reste au développeur

Forme exacte des écrans, tailles de caches, découpage interne des processus.
