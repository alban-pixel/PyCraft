# Comment PyCraft fait de la 3D dans Pyxel

PyCraft n'utilise aucun moteur 3D. Pyxel ne sait dessiner que des triangles
(`pyxel.tri`), des rectangles (`pyxel.rect`) et des sprites (`pyxel.blt`) en 2D.
Toute la perspective est donc calculée à la main, en Python.

Ce document explique les cinq idées qui rendent le jeu possible, dans l'ordre où
une image est construite.

---

## 1. Le monde : un tableau d'octets

Le monde fait 256 × 256 × 32 = 2 097 152 blocs, stockés dans **un seul
`bytearray`**. Chaque case contient le numéro du type de bloc (0 = air,
1 = herbe, 2 = terre, 3 = pierre…).

```python
def index(x, y, z):
    return (z * sy + y) * sx + x
```

Pourquoi un tableau plat plutôt qu'un dictionnaire `(x, y, z) -> bloc` ?
Le dictionnaire est plus lisible, mais chaque accès coûte ~0,3 µs et le rendu en
fait des dizaines de milliers par frame. Le tableau plat est ~3× plus rapide et
tient en 2 Mo.

Le monde est découpé en **chunks** de 16 × 16 colonnes. C'est l'unité de cache :
quand on casse un bloc, seuls les chunks voisins sont recalculés.

---

## 2. La caméra et la projection

La caméra a une position `(x, y, z)`, un lacet (`yaw`) et une inclinaison
(`pitch`). On construit trois vecteurs orthonormés :

```
avant  = (cos(pitch)·cos(yaw), cos(pitch)·sin(yaw), sin(pitch))
droite = (sin(yaw), -cos(yaw), 0)
haut   = (-sin(pitch)·cos(yaw), -sin(pitch)·sin(yaw), cos(pitch))
```

Pour projeter un point du monde, on le translate par rapport à la caméra, puis on
le projette sur ces trois axes : `(xc, yc, zc)`.

Si `zc` est la profondeur, l'écran se calcule par une **projection en trou
d'épingle** :

```
focale = (largeur / 2) / tan(fov / 2)
x_écran = largeur / 2 + focale · xc / zc
y_écran = hauteur / 2 - focale · yc / zc
```

Le signe moins sur `y` vient de ce que Pyxel compte les ordonnées vers le bas.

Codé en numpy, ce calcul s'applique à toutes les faces d'un coup
(`(N, 4, 3) @ (3,)`), ce qui est ~10× plus rapide qu'une boucle Python.

---

## 3. Le clipping du plan proche

Un point dont `zc` est négatif est **derrière** la caméra : sa projection n'a
aucun sens. Si on la calcule quand même, on obtient un triangle géant qui avale
l'écran — c'est le bug classique du débutant (et celui qu'on a rencontré).

La solution est l'algorithme de **Sutherland–Hodgman** : on découpe le polygone
contre le plan `zc = near`, en interpolant les sommets qui traversent le plan.

```python
for a, b in edges:
    if a_inside: out.append(a)
    if a_inside != b_inside:
        t = (near - a.z) / (b.z - a.z)
        out.append(lerp(a, b, t))
```

Une face à cheval est ainsi remplacée par un polygone plus petit, correctement
projeté.

---

## 4. Le tri du peintre

Il n'y a pas de z-buffer : on ne stocke pas la profondeur de chaque pixel.
À la place, on trie les faces **de la plus lointaine à la plus proche** et on les
dessine dans cet ordre. Les faces proches recouvrent les lointaines.

C'est l'**algorithme du peintre**. Il est correct pour des faces opaques qui ne
s'intersectent pas, ce qui est le cas de cubes alignés sur une grille.

Coût : ~0,1 ms pour 3 000 faces (`np.argsort`).

---

## 5. Le maillage : détail et fusion

Dessiner chaque face de chaque bloc serait trop lent : le monde complet expose
~120 000 faces. Deux optimisations :

**a) Ne garder que les faces visibles.** Une face entre deux blocs pleins ne se
voit jamais. On ne l'émet pas.

**b) Fusionner les faces coplanaires (*greedy meshing*).** Toutes les faces du
dessus d'une plaine sont sur le même plan, avec le même type de bloc : elles
forment un seul grand rectangle. Le maillage passe de ~120 000 à ~50 000 quads,
et jusqu'à 100× moins sur une zone plate.

**c) Deux niveaux de détail (LOD).** Près de la caméra, on garde une face par
bloc (meilleur rendu). Au-delà de 24 blocs, on utilise le maillage fusionné.

Les quads fusionnés sont agrandis de **0,02 bloc** dans leur plan : sans ça, un
grand quad bordé de petits laisse des fissures d'un pixel (T-junctions).

---

## 6. Couleurs, ciel et brouillard

Pyxel utilise une palette de 16 couleurs. PyCraft la remplace au démarrage par
une palette « Minecraft » (`pyxel.colors[i] = 0xRRGGBB`) : herbe verte, terre
brune, pierre grise, sable, eau.

Le brouillard mélange la couleur de chaque face avec celle du ciel selon la
distance, puis cherche la couleur la plus proche dans la palette (distance RGB).
Il masque la limite de la distance de vue et la transition entre les deux LOD.

---

## 7. Les chiffres

Mesures réelles sur Mac arm64, fenêtre 1280×800, monde 256×256×32 :

| Étape | Mesure |
|---|---|
| Génération du monde | ~113 ms |
| Maillage d'un chunk (détail) | 2,5–3,9 ms |
| Rendu 1280×800, distance 96 | **3,44 ms** (p95 3,46) |
| Rendu 1920×1200, distance 120 | **5,29 ms** (p95 5,56) |

Le coût dominant n'est ni le GPU ni le tri, mais **le nombre d'appels
`pyxel.tri`** (~0,6 µs chacun) et la boucle Python qui les émet. La résolution,
elle, est presque gratuite : +0,7 ms de 320×200 à 1280×800, car SDL2/Metal
rasterise côté GPU.

C'est pourquoi on convertit les coordonnées numpy en listes Python avant la
boucle de dessin : accéder à un scalaire numpy coûte ~100 ns, contre ~20 ns pour
un flottant Python.

---

## 8. Ce qu'on n'a pas fait (et pourquoi)

- **Z-buffer** : imposerait un rendu pixel par pixel en Python, trop lent.
- **Raycasting par pixel** : plus proche de Minecraft (surplombs, cavernes),
  mais 2× plus de code et une marge CPU divisée.
- **Threads** : le GIL empêche tout gain sur du Python pur (mesuré : 6,5 ms en
  1 thread comme en 8). Le seule usage utile serait un maillage d'arrière-plan,
  inutile ici (un chunk = 3 ms).
- **Shaders** : Pyxel n'expose pas le GPU programmable. Il rasterise, c'est tout.
