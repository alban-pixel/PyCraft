# PyCraft (Branche Gemini)

Jeu vidéo 3D rétro style Minecraft en mode créatif, développé en Python avec **[Pyxel](https://github.com/kitao/pyxel)** et rendu 3D off-screen via **ModernGL (OpenGL)**.

Le monde 3D est calculé et rastérisé sur GPU dans un tampon hors-écran qui convertit directement les couleurs en indices de la palette étendue Pyxel (256 couleurs) via un tramage ordonné de Bayer. L'image finale est ensuite copiée dans l'écran Pyxel (`pyxel.screen`), qui gère les particules 3D, le HUD, les menus, le son et les contrôles.

---

## Prérequis

- Python 3.10+ (testé sous Python 3.14 macOS arm64)
- Carte graphique compatible OpenGL 3.3+ (macOS, Windows, Linux)

---

## Installation

```bash
# Créer et activer l'environnement virtuel
python3 -m venv .venv
source .venv/bin/activate          # macOS / Linux
# (.venv\Scripts\activate sous Windows)

# Installer les dépendances
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
| Souris / Flèches | Regarder autour de soi |
| **WASD / ZQSD** | Déplacement (support natif QWERTY & AZERTY) |
| Espace | Sauter / Nager / Monter en vol |
| Ctrl gauche | Courir (Sprint) |
| Shift gauche | Descendre en vol |
| F | Activer / Désactiver le vol |
| Clic gauche | Casser un bloc (maintenir pour répéter) |
| Clic droit | Poser un bloc |
| 1 à 9 / Molette souris | Sélectionner l'emplacement de la barre d'accès rapide |
| E | Ouvrir l'inventaire complet des blocs |
| Échap | Menu pause & Paramètres (résolution, FPS, FOV, musique) |
| Tab | Capturer / Libérer le curseur de la souris |
| F3 | Informations de débogage (FPS, position XYZ, bloc visé, graine) |
| H | Afficher / masquer l'aide à l'écran |

---

## Améliorations apportées sur la branche `gemini`

1. **Prise en charge native AZERTY / ZQSD** :
   - Déplacement fluide via `Z` (avancer), `Q` (gauche), `S` (reculer), `D` (droite) sans reconfiguration.
   - Navigation clavier dans tous les menus (Titre, Pause, Paramètres) avec `Z` et `S`.

2. **Système de particules 3D d'impact** :
   - À chaque bloc détruit, des éclats 3D dynamiques de la couleur du bloc explosent avec vélocité et gravité réalistes.
   - Projection vectorielle 3D $\to$ 2D affichée directement via les primitives Pyxel.

3. **Culling du Frustum de Vue (View Frustum Culling)** :
   - Extraction des 6 plans de clipping normalisés de la matrice Vue-Projection ($VP$).
   - Élimination des chunks situés hors du champ de vision de la caméra avant l'envoi au GPU, réduisant significativement les appels de rendu.

4. **Nouveaux blocs et génération enrichie** :
   - 17 blocs posables au total, incluant **Minerai d'Or**, **Minerai de Diamant**, **Glowstone** (pierre lumineuse) et **Neige**.
   - Génération procédurale des filons de diamant en profondeur ($y < 12$), d'or ($y < 18$) et de calottes neigeuses sur les hauts sommets ($y > 33$).

5. **Menu Paramètres complet et persistant** :
   - Choix de la résolution dynamique (320x180 à 960x540) avec redimensionnement immédiat (`pyxel.resize` + buffers ModernGL).
   - Cadence d'images ajustable (30, 60, 75, 120, 144, 165, 240 FPS).
   - Champ de vision (FOV) réglable (60°, 70°, 80°, 90°).
   - Sauvegarde automatique dans `settings.json`.

6. **Affichage du bloc ciblé (Target Raycast)** :
   - En mode F3, le nom du bloc visé et ses coordonnées voxel exactes sont affichés en temps réel.

7. **Point d'entrée racine & Suite de tests automatisés** :
   - Le script racine `main.py` lance directement PyCraft.
   - Suite de tests unitaires complète avec `pytest` couvrant le monde voxel, les blocs, le joueur et le renderer.

---

## Lancer les tests

```bash
.venv/bin/pytest -v
```
