"""T1 : contexte OpenGL, readback et transfert vers le framebuffer Pyxel."""

import pytest

pytestmark = pytest.mark.gpu

moderngl = pytest.importorskip("moderngl")


def test_contexte_et_readback():
    from pycraft.gl.context import GlContext

    gl = GlContext(64, 32)
    try:
        gl.clear_index(3)
        data = gl.read_indices()
        assert len(data) == 64 * 32
        assert set(data) == {3}
    finally:
        gl.close()


def test_indices_differents():
    from pycraft.gl.context import GlContext

    gl = GlContext(16, 8)
    try:
        for index in (0, 1, 15, 200, 255):
            gl.clear_index(index)
            data = gl.read_indices()
            assert set(data) == {index}, f"indice {index} non préservé"
    finally:
        gl.close()


def test_lecture_est_bien_orientee():
    """OpenGL lit de bas en haut ; Pyxel affiche de haut en bas."""
    from pycraft.gl.context import GlContext

    gl = GlContext(4, 2)
    try:
        # Texture : première ligne (bas en GL) = 1, dernière ligne (haut) = 2
        gl.color_tex.write(bytes([1] * 4 + [2] * 4))
        data = gl.read_indices()
        assert data[0] == 2  # première ligne Pyxel = haut de l'image
        assert data[4] == 1
    finally:
        gl.close()


def test_transfert_dans_pyxel(pyxel_headless):
    from pycraft.gl.context import GlContext

    gl = GlContext(320, 200)
    try:
        gl.clear_index(7)
        gl.blit_to_pyxel()
        assert pyxel_headless.pget(0, 0) == 7
        assert pyxel_headless.pget(319, 199) == 7
    finally:
        gl.close()
