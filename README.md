# PyCraft (Branche Gemini)

Jeu vidéo 3D rétro style Minecraft complet avec modes **Survie** et **Créatif**, développé en Python avec **[Pyxel](https://github.com/kitao/pyxel)** et rendu 3D off-screen via **ModernGL (OpenGL 3.3+)**.

Le monde voxel 3D est calculé et rastérisé sur GPU dans un tampon hors-écran qui convertit directement les couleurs en indices de la palette étendue Pyxel (256 couleurs) via un tramage ordonné de Bayer. L'image finale est ensuite copiée dans l'écran Pyxel (`pyxel.screen`), qui gère les entités/mobs 3D articulés, les particules d'impact, la vue subjective avec bras animé, l'overlay de fissures de minage, le HUD (cœurs, bulles d'oxygène, stacks), l'artisanat 2x2 et 3x3, le son rétro et les menus.

---

## Fonctionnalités Principales

- 🎮 **Modes Survie & Créatif** : Choix du mode à la création du monde, basculement instantané à tout moment avec `F4`.
- ❤️ **Mécaniques de Survie** :
  - 10 cœurs (20 HP) avec animation de clignotement rouge lors des dégâts ("oof").
  - Jauge de bulles d'oxygène lors des immersions sous l'eau avec dégâts de noyade progressifs.
  - Dégâts de chute réalistes pour les chutes supérieures à 3 blocs.
  - Écran Game Over avec bouton de réapparition (*Respawn*) au point d'apparition du monde.
  - Aliments consommables (porc cru et porc cuit) avec son de mastication et régénération de cœurs.
- 🎒 **Inventaire & Stacks** :
  - Gestion des piles d'objets (jusqu'à 64 par case) sur la hotbar (9 cases) et le sac à dos (27 cases).
  - La pose de bloc décrémente la pile ; le minage et les drops de créatures ajoutent les ressources dans les stacks.
- 🔨 **Système d'Artisanat (Crafting)** :
  - Grille 2x2 accessible dans l'inventaire (`E`).
  - Bloc **Table de Craft** (`CRAFTING_TABLE`) posable ouvrant une grille 3x3 complète.
  - Panneau latéral "Quick-Craft" permettant de fabriquer instantanément les recettes disponibles en 1 clic (idéal pour les démonstrations orales).
  - Recettes : planches, bâtons, table de craft, côtelettes cuites, pioches et épées en Bois, Pierre, Fer et Diamant.
- ⚔️ **Outils, Minage Progressif & Combat** :
  - Outils avec multiplicateurs d'efficacité et dégâts d'attaque (Épée en diamant inflige 8 HP par coup).
  - Minage progressif avec temps de casse selon la dureté du bloc et texture de fissures 3D superposée.
- 🐷🧟 **Créatures & Entités 3D Articulées** :
  - **Cochon (passif)** : flâne pacifiquement, s'enfuit en panique quand on le frappe, lâche du porc cru à sa mort.
  - **Zombie (hostile)** : détecte et traque le joueur à vue, inflige des dégâts de contact, et prend feu à la lumière du soleil le jour.
  - Rendu 3D temps réel des créatures avec membres animés (cycle de marche) et AABB pour la détection des coups.
- 🖐️ **Vue subjective immersive (First-Person View)** :
  - Bras/outil du joueur visible en bas à droite de l'écran, avec balancement naturel lors de la marche et coup lors d'un clic.
- 🌊 **Simulation dynamique des fluides** :
  - Automate cellulaire d'écoulement de l'eau : chute verticale prioritaire et étalement horizontal sur les surfaces planes.
- 🖱️ **Contrôles ultra-fluides & Correction matérielle macOS** :
  - Capture matérielle de la souris via l'API CoreGraphics de macOS (`CGAssociateMouseAndMouseCursorPosition` et deltas matériels `CGGetLastMouseDelta`), éliminant définitivement les micro-blocages et rollbacks de souris.
  - Prise en charge native simultanée **AZERTY (ZQSD)** et **QWERTY (WASD)**.

---

## Prérequis

- Python 3.10+ (testé sous Python 3.14 macOS arm64 / Apple Silicon)
- Carte graphique compatible OpenGL 3.3+ (macOS, Linux, Windows)

---

## Installation

```bash
# 1. Cloner ou se placer dans le projet
git checkout gemini

# 2. Créer et activer l'environnement virtuel
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# (.venv\Scripts\activate sous Windows)

# 3. Installer les dépendances
pip install -r requirements.txt pytest
```

---

## Lancer le jeu

```bash
# Depuis la racine du projet
source .venv/bin/activate
python main.py
```

*(Ou directement `.venv/bin/python main.py`)*

---

## Commandes

| Touche | Action |
|---|---|
| **Souris / Flèches** | Regarder autour de soi (capture fluide sans accroc) |
| **WASD / ZQSD** | Déplacement (support natif complet QWERTY & AZERTY) |
| **Espace** | Sauter / Nager vers le haut / Monter en vol |
| **Ctrl gauche** | Courir (Sprint) |
| **Shift gauche** | Descendre en vol |
| **F** | Activer / Désactiver le vol (*Mode Créatif uniquement*) |
| **F4** | Basculer instantanément entre mode **Survie** et **Créatif** |
| **F11 / Alt+Entrée** | Activer / Désactiver le **Plein écran** (Fullscreen) |
| **Clic gauche** | Casser un bloc (minage progressif) / Frapper une créature |
| **Clic droit** | Poser un bloc / Manger un aliment / Ouvrir la Table de Craft |
| **1 à 9 / Molette** | Sélectionner la case active de la barre d'accès rapide |
| **E** | Ouvrir l'inventaire et la grille de fabrication 2x2 |
| **Échap** | Menu pause & Paramètres (résolution, FPS, FOV, musique) |
| **Tab** | Capturer / Libérer le curseur de la souris |
| **F3** | Informations de débogage (FPS, coordonnées XYZ, bloc visé, graine) |
| **H** | Afficher / masquer l'aide des touches à l'écran |

---

## Recettes de Fabrication (Crafting)

| Produit | Ingrédients | Type de grille |
|---|---|---|
| **Planches (x4)** | 1 Bûche de bois | 2x2 ou 3x3 |
| **Bâtons (x4)** | 2 Planches superposées | 2x2 ou 3x3 |
| **Table de Craft** | 4 Planches (carré 2x2) | 2x2 ou 3x3 |
| **Porc Cuit** | 1 Porc Cru | 2x2 ou 3x3 |
| **Épée (Bois / Pierre / Fer / Diamant)** | 2 Matériaux verticaux + 1 Bâton | 3x3 (sur Table de Craft) |
| **Pioche (Bois / Pierre / Fer / Diamant)** | 3 Matériaux en haut + 2 Bâtons au centre | 3x3 (sur Table de Craft) |

*Astuce orale NSI* : Cliquez directement sur les boutons de recettes rapides à gauche de l'écran d'inventaire pour fabriquer en un seul clic !

---

## Architecture Technique

- `main.py` : Lanceur racine, boucle de jeu Pyxel, gestion d'états (Titre, Jeu, Inventaire, Game Over, Paramètres), HUD et SFX.
- `pycraft-gpu/renderer.py` : Moteur de rendu ModernGL 3D, compilation des shaders, VBO/VAO des chunks voxels, frustum culling et rendu des créatures 3D.
- `pycraft-gpu/player.py` : Physique du joueur (gravité, saut, collision AABB 3 axes, natation, noyade, dégâts de chute).
- `pycraft-gpu/world.py` : Modèle de monde voxel numpy, automate cellulaire des fluides (`tick_fluids`), raycasting DDA 3D et persistance `.npz`.
- `pycraft-gpu/entities.py` : Gestionnaire d'entités, IA des cochons et des zombies, système de détection des coups et butin (*drops*).
- `pycraft-gpu/crafting.py` : Moteur de reconnaissance de patrons matriciels 2x2 et 3x3 et consommation d'ingrédients.
- `pycraft-gpu/blocks.py` : Atlas de textures 16x16, propriétés des blocs (solidité, dureté, couleurs de particules, multiplicateurs d'outils).

---

## Tests Automatisés

Le projet comprend une suite complète de 48 tests unitaires automatisés validant la physique, les blocs, la simulation de fluides, le calcul matriciel, l'artisanat, les créatures, le plein écran, le scaling haute résolution (High DPI) et la boucle de jeu :

```bash
.venv/bin/pytest -v
```
