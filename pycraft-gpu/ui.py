"""The HUD and menus, drawn at a scale: at high resolutions each of their pixels covers several pixels
of the screen, so the text stays readable. The game lays them out in "UI pixels" (the screen size
divided by the scale) and draws them with these functions instead of Pyxel's own: plain shapes and
text, and the parts the menus are made of (panels, buttons, setting rows, bars, tooltips)."""
import pyxel

TEXT_KEY = 255  # background of the image text is written into: left out when it is copied
AUTO_HEIGHT = 270  # "Auto" interface size: about 270 to 450 UI pixels high, whatever the resolution
MIN_HEIGHT = 180  # the menus need at least this many UI pixels in height
CHAR_W, CHAR_H = 4, 6  # Pyxel's font, spacing included (letters are 3 x 5)
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

# Colors of the theme (Pyxel's 16)
BLACK, NAVY, BLUE, LIGHT_BLUE, WHITE, YELLOW, GREY, LIME = 0, 1, 5, 12, 7, 10, 13, 11
TEXT, TEXT_DIM, TEXT_HOT, VALUE = WHITE, GREY, YELLOW, 6


def text_width(s):
    return len(s) * CHAR_W - 1


class Ui:
    def __init__(self):
        self.scale = 1
        self.choice = "auto"  # the interface size setting: "auto" or a scale
        self.text_image = pyxel.Image(512, 8)

    @staticmethod
    def auto_scale(height):
        return max(1, height // AUTO_HEIGHT)

    @staticmethod
    def max_scale(height):
        return max(1, height // MIN_HEIGHT)

    def set_screen_size(self, width, height, choice=None):
        if choice is not None:
            self.choice = choice
        if self.choice == "auto":
            self.scale = self.auto_scale(height)
        else:
            self.scale = max(1, min(int(self.choice), self.max_scale(height)))

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

    def mouse_in(self, x, y, w, h):
        return x <= self.mouse_x < x + w and y <= self.mouse_y < y + h

    def to_screen(self, x, y):
        """Screen position of the middle of UI pixel (x, y)."""
        return x * self.scale + self.scale // 2, y * self.scale + self.scale // 2

    # --- Shapes and text ---------------------------------------------------------------------

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

    def shade(self, x, y, w, h, amount=0.6, col=BLACK):
        """Darken a rectangle: every other screen pixel or so is painted (see-through)."""
        pyxel.dither(amount)
        self.rect(x, y, w, h, col)
        pyxel.dither(1.0)

    def text(self, x, y, s, col, shadow=False, size=1):
        """Text with its top-left corner at (x, y); size 2 draws it twice as big."""
        if shadow:
            self.text(x + size, y + size, s, BLACK, size=size)
        if self.scale == 1 and size == 1:
            pyxel.text(x, y, s, col)
            return
        w = len(s) * CHAR_W
        img = self.text_image
        img.rect(0, 0, w, CHAR_H, TEXT_KEY)
        img.text(0, 0, s, col)
        self.blt(x, y, img, 0, 0, w, CHAR_H, TEXT_KEY, scale=size)

    def center_text(self, y, s, col, shadow=False, size=1, cx=None):
        cx = self.width // 2 if cx is None else cx
        self.text(cx - text_width(s) * size // 2, y, s, col, shadow, size)

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

    # --- Widgets ------------------------------------------------------------------------------

    def panel(self, x, y, w, h, title=None):
        """A see-through dark panel with a frame and a soft shadow; the title goes in a 2x heading.
        Returns the y where its content starts."""
        self.shade(x + w, y + 2, 2, h, 0.4)  # shadow, right and below
        self.shade(x + 2, y + h, w - 2, 2, 0.4)
        self.shade(x, y, w, h, 0.78)
        self.rectb(x, y, w, h, BLUE)
        self.hline(x + 1, x + w - 2, y + 1, NAVY)  # a lighter inner edge on top
        if title is None:
            return y + 4
        self.center_text(y + 5, title, TEXT, shadow=True, size=2, cx=x + w // 2)
        self.hline(x + 4, x + w - 5, y + 19, BLUE)
        return y + 23

    def button(self, x, y, w, h, label, hot=False, enabled=True):
        """A raised button; hot: under the mouse or chosen with the keyboard."""
        if not enabled:
            self.shade(x, y, w, h, 0.5, NAVY)
            self.rectb(x, y, w, h, NAVY)
            self.center_text(y + (h - 5) // 2, label, TEXT_DIM, cx=x + w // 2)
            return
        self.rect(x, y, w, h, BLUE if hot else NAVY)
        self.hline(x + 1, x + w - 2, y + 1, LIGHT_BLUE if hot else BLUE)  # light from above
        self.hline(x + 1, x + w - 2, y + h - 2, NAVY if hot else BLACK)
        self.rectb(x, y, w, h, WHITE if hot else BLACK)
        self.center_text(y + (h - 5) // 2, label, TEXT_HOT if hot else TEXT, shadow=True, cx=x + w // 2)

    def setting_row(self, x, y, w, h, label, value, hot=False, arrows=True):
        """A setting: its name on the left, its value on the right (between arrows when hot)."""
        if hot:
            self.rect(x, y, w, h, NAVY)
            self.rectb(x, y, w, h, LIGHT_BLUE)
        ty = y + (h - 5) // 2
        self.text(x + 5, ty, label, TEXT_HOT if hot else TEXT, shadow=True)
        vx, vw = self.value_box(x, w)
        self.center_text(ty, value, TEXT_HOT if hot else VALUE, shadow=True, cx=vx + vw // 2)
        if hot and arrows:
            self.text(vx, ty, "<", TEXT_HOT)
            self.text(vx + vw - 3, ty, ">", TEXT_HOT)

    @staticmethod
    def value_box(x, w):
        """Left and width of the value part of a setting row (its arrows at either end)."""
        vw = min(96, w // 2)
        return x + w - vw - 4, vw

    def bar(self, x, y, w, h, fraction, col=LIME):
        """A progress bar."""
        self.rect(x, y, w, h, BLACK)
        self.rectb(x, y, w, h, GREY)
        inner = round((w - 4) * min(max(fraction, 0.0), 1.0))
        if inner > 0:
            self.rect(x + 2, y + 2, inner, h - 4, col)
            self.hline(x + 2, x + 1 + inner, y + 2, WHITE)  # a shine along the top

    def tooltip(self, x, y, s, col=TEXT):
        """A small label next to the mouse pointer (or at (x, y)), kept inside the screen."""
        w, h = text_width(s) + 6, 11
        x = min(max(x + 10, 1), self.width - w - 1)
        y = min(max(y - 2, 1), self.height - h - 1)
        self.rect(x, y, w, h, BLACK)
        self.rectb(x, y, w, h, BLUE)
        self.text(x + 3, y + 3, s, col)

    def toast(self, y, s, col=TEXT_HOT):
        """A notice in a small dark box, centered."""
        w = text_width(s) + 10
        x = (self.width - w) // 2
        self.shade(x, y, w, 11, 0.7)
        self.rectb(x, y, w, 11, NAVY)
        self.text(x + 5, y + 3, s, col, shadow=True)
