"""Fixtures partagées.

Pyxel ne peut être initialisé qu'une seule fois par processus : la fixture de
session ci-dessous centralise l'init headless pour tous les tests qui en ont
besoin.
"""

import pytest


@pytest.fixture(scope="session")
def pyxel_headless():
    import pyxel

    pyxel.init(320, 200, headless=True, fps=1000)
    return pyxel
