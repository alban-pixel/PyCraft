"""Contexte OpenGL hors écran et transfert de la frame vers Pyxel.

Le framebuffer de rendu est une texture **R8** (1 octet par pixel) : chaque pixel
contient un indice de la palette Pyxel. La frame est lue avec `glReadPixels`,
remise à l'endroit (OpenGL lit de bas en haut) puis copiée dans `pyxel.screen`.

**Ordre d'initialisation obligatoire** : le contexte doit être créé **avant**
`pyxel.init()`. Créé après, il prend la place du contexte de SDL et la fenêtre
Pyxel devient noire (vérifié). Une fois Pyxel initialisé, les objets GL peuvent
en revanche être créés et modifiés normalement.
"""

from __future__ import annotations

import ctypes

import moderngl
import numpy as np
import pyxel


class GlContext:
    """Contexte moderngl + cible de rendu indexée, prête pour Pyxel."""

    def __init__(self, width: int, height: int) -> None:
        self.width = int(width)
        self.height = int(height)
        self.ctx = moderngl.create_standalone_context()
        self.color_tex = self.ctx.texture((self.width, self.height), 1, dtype="f1")
        self.color_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.fbo = self.ctx.framebuffer(color_attachments=[self.color_tex])

    # ------------------------------------------------------------------
    def clear_index(self, index: int) -> None:
        """Remplit la cible d'un indice de palette uniforme."""
        self.fbo.use()
        self.fbo.clear(index / 255.0, 0.0, 0.0, 1.0)

    def read_indices(self) -> bytes:
        """Lit la frame en indices, lignes remises dans l'ordre Pyxel (haut→bas)."""
        brut = self.fbo.read(components=1, dtype="f1")
        image = np.frombuffer(brut, dtype=np.uint8).reshape(self.height, self.width)
        return np.ascontiguousarray(image[::-1]).tobytes()

    def blit_to_pyxel(self) -> None:
        """Copie la frame dans le framebuffer de Pyxel."""
        data = self.read_indices()
        ctypes.memmove(pyxel.screen.data_ptr(), data, len(data))

    def close(self) -> None:
        self.fbo.release()
        self.color_tex.release()
        self.ctx.release()
