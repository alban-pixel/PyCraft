"""
NSI-Game — base de jeu Pyxel (moteur rétro pour Python)

Lancement :
    source .venv/bin/activate
    python main.py

Commandes :
    Flèches / ZQSD / WASD : déplacer le vaisseau
    Espace                 : tirer
    R                      : recommencer
    Échap                  : quitter
"""

import pyxel

# ---------------------------------------------------------------
# Constantes du jeu
# ---------------------------------------------------------------
ECRAN_LARGEUR = 200
ECRAN_HAUTEUR = 180
TITRE = "NSI-Game"

# Couleurs Pyxel (palette 16 couleurs) : 0=noir ... 15=blanc
NOIR = 0
BLEU_NUIT = 1
BORDEAUX = 2
VERT = 3
BRUN = 4
BLEU = 5
GRIS = 6
BLANC = 7
ROUGE = 8
ORANGE = 9
JAUNE = 10
VERT_CLAIR = 11
BLEU_CLAIR = 12
GRIS_CLAIR = 13
ROSE = 14
PEAU = 15

LARGEUR_VAISSEAU = 13
HAUTEUR_VAISSEAU = 8
VITESSE_VAISSEAU = 1.5

VITESSE_TIR = 3
LARGEUR_TIR = 1
HAUTEUR_TIR = 4

NOMBRE_ETOILES = 30


# ---------------------------------------------------------------
# Classes
# ---------------------------------------------------------------
class Etoile:
    """Une étoile qui descend pour donner l'impression d'avancer."""

    def __init__(self, x):
        self.x = x
        self.y = 0
        self.vitesse = 0

    def update(self):
        self.y += self.vitesse
        if self.y > ECRAN_HAUTEUR:
            self.y = 0


class Tir:
    """Un projectile tiré par le vaisseau."""

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def update(self):
        self.y -= VITESSE_TIR

    @property
    def hors_ecran(self):
        return self.y + HAUTEUR_TIR < 0


class Jeu:
    """État complet de la partie."""

    def __init__(self):
        self.vaisseau_x = (ECRAN_LARGEUR - LARGEUR_VAISSEAU) // 2
        self.vaisseau_y = ECRAN_HAUTEUR - HAUTEUR_VAISSEAU - 10
        self.tirs = []
        self.etoiles = [
            Etoile(pyxel.rndi(0, ECRAN_LARGEUR - 1)) for _ in range(NOMBRE_ETOILES)
        ]
        for etoile in self.etoiles:
            etoile.vitesse = pyxel.rndf(0.3, 1.2)
        self.score = 0

    # ----- mise à jour (logique) -----
    def update(self):
        self.deplacer_vaisseau()
        self.deplacer_tirs()
        for etoile in self.etoiles:
            etoile.update()

    def deplacer_vaisseau(self):
        if pyxel.btn(pyxel.KEY_LEFT) or pyxel.btn(pyxel.KEY_A) or pyxel.btn(pyxel.KEY_Q):
            self.vaisseau_x -= VITESSE_VAISSEAU
        if pyxel.btn(pyxel.KEY_RIGHT) or pyxel.btn(pyxel.KEY_D):
            self.vaisseau_x += VITESSE_VAISSEAU

        # On garde le vaisseau dans l'écran
        self.vaisseau_x = max(
            0, min(self.vaisseau_x, ECRAN_LARGEUR - LARGEUR_VAISSEAU)
        )

        # Tir avec une touche (btnp = appui ponctuel)
        if pyxel.btnp(pyxel.KEY_SPACE):
            self.tirer()

    def tirer(self):
        x = self.vaisseau_x + LARGEUR_VAISSEAU // 2 - LARGEUR_TIR // 2
        self.tirs.append(Tir(x, self.vaisseau_y - HAUTEUR_TIR))

    def deplacer_tirs(self):
        for tir in self.tirs:
            tir.update()
        self.tirs = [tir for tir in self.tirs if not tir.hors_ecran]

    # ----- dessin (affichage) -----
    def draw(self):
        pyxel.cls(BLEU_NUIT)
        self.dessiner_etoiles()
        self.dessiner_vaisseau()
        self.dessiner_tirs()
        pyxel.text(5, 5, f"SCORE {self.score}", BLANC)

    def dessiner_etoiles(self):
        for etoile in self.etoiles:
            couleur = GRIS if etoile.vitesse < 0.8 else GRIS_CLAIR
            pyxel.pset(etoile.x, etoile.y, couleur)

    def dessiner_vaisseau(self):
        # pixel art simple : un triangle pointant vers le haut
        x = int(self.vaisseau_x)
        y = self.vaisseau_y
        pointe_x = x + LARGEUR_VAISSEAU // 2
        pyxel.tri(
            x,
            y + HAUTEUR_VAISSEAU,
            pointe_x,
            y,
            x + LARGEUR_VAISSEAU,
            y + HAUTEUR_VAISSEAU,
            BLEU_CLAIR,
        )
        pyxel.line(x, y + HAUTEUR_VAISSEAU - 1, x + LARGEUR_VAISSEAU, y + HAUTEUR_VAISSEAU - 1, BLEU)
        pyxel.rect(x + LARGEUR_VAISSEAU // 2 - 1, y + 2, 2, 4, BLANC)
        # flammes du réacteur
        flamme = ROUGE if pyxel.frame_count % 4 < 2 else JAUNE
        pyxel.rect(
            x + LARGEUR_VAISSEAU // 2 - 2, y + HAUTEUR_VAISSEAU, 4, 2, flamme
        )

    def dessiner_tirs(self):
        for tir in self.tirs:
            pyxel.rect(tir.x, tir.y, LARGEUR_TIR, HAUTEUR_TIR, JAUNE)


# ---------------------------------------------------------------
# Cycle de vie Pyxel
# ---------------------------------------------------------------
jeu = None


def recommencer():
    global jeu
    jeu = Jeu()


def update():
    if pyxel.btnp(pyxel.KEY_R):
        recommencer()
    jeu.update()


def draw():
    jeu.draw()


# ---------------------------------------------------------------
# Point d'entrée
# ---------------------------------------------------------------
def main():
    pyxel.init(
        ECRAN_LARGEUR,
        ECRAN_HAUTEUR,
        title=TITRE,
        fps=30,
        quit_key=pyxel.KEY_ESCAPE,
    )
    recommencer()
    pyxel.run(update, draw)


if __name__ == "__main__":
    main()
