"""The HUD and menus, drawn at a scale: at high resolutions each of their pixels covers several pixels
of the screen, so the text stays readable. The game lays them out in "UI pixels" (the screen size
divided by the scale) and draws them with these functions instead of Pyxel's own."""
import pyxel

TEXT_KEY = 255  # background of the image text is written into: left out when it is copied
CURSOR = [  # mouse pointer: 1 outline, 2 inside
    "1.......",
    "11......",
    "121.....",
    "1221....",
    "12221...",
    "122221..",
    "1222221.",
    "1221111.",
    "111.....",
]


class Ui:
    def __init__(self):
        self.scale = 1
        self.text_image = pyxel.Image(512, 8)

    def set_screen_size(self, width, height):
        # About 270 to 450 UI pixels high: the HUD looks about the same size at every resolution
        self.scale = max(1, height // 270)

    @property
    def width(self):
        return pyxel.width // self.scale

    @property
    def height(self):
        return pyxel.height // self.scale

    @property
    def mouse_x(self):
        return pyxel.mouse_x // self.scale

    @property
    def mouse_y(self):
        return pyxel.mouse_y // self.scale

    def to_screen(self, x, y):
        """Screen position of the middle of UI pixel (x, y)."""
        return x * self.scale + self.scale // 2, y * self.scale + self.scale // 2

    def rect(self, x, y, w, h, col):
        s = self.scale
        pyxel.rect(x * s, y * s, w * s, h * s, col)

    def rectb(self, x, y, w, h, col):
        s = self.scale
        for i in range(s):  # a border one UI pixel thick
            pyxel.rectb(x * s + i, y * s + i, w * s - 2 * i, h * s - 2 * i, col)

    def hline(self, x1, x2, y, col):
        self.rect(min(x1, x2), y, abs(x2 - x1) + 1, 1, col)

    def vline(self, x, y1, y2, col):
        self.rect(x, min(y1, y2), 1, abs(y2 - y1) + 1, col)

    def text(self, x, y, s, col):
        if self.scale == 1:
            pyxel.text(x, y, s, col)
            return
        w = len(s) * 4
        img = self.text_image
        img.rect(0, 0, w, 6, TEXT_KEY)
        img.text(0, 0, s, col)
        self.blt(x, y, img, 0, 0, w, 6, TEXT_KEY)

    def blt(self, x, y, img, u, v, w, h, colkey, scale=1):
        """Like pyxel.blt with (x, y) the top-left corner; scale multiplies the UI's own."""
        s = self.scale * scale
        # Pyxel scales around the middle of the image
        pyxel.blt(x * self.scale + w * (s - 1) / 2, y * self.scale + h * (s - 1) / 2, img, u, v, w, h, colkey,
                  scale=s)

    def cursor(self):
        x0, y0 = self.mouse_x, self.mouse_y
        for dy, row in enumerate(CURSOR):
            for dx, c in enumerate(row):
                if c != ".":
                    self.rect(x0 + dx, y0 + dy, 1, 1, 0 if c == "1" else 7)
