"""The HUD and menus, drawn at a scale: at high resolutions each of their pixels covers several pixels
of the screen, so the text stays readable. The game lays them out in "UI pixels" (the screen size
divided by the scale) and draws them with these functions instead of Pyxel's own: plain shapes and
text, and the parts the menus are made of (panels, buttons, tabs, setting rows, sliders, key caps,
slots, bars, tooltips).

The look: dark stone panels, grey buttons with a light edge on top and a dark one below, warm
white text, and amber for whatever is chosen. Its 16 colors take the place of Pyxel's own 16."""
import pyxel

TEXT_KEY = 255  # background of the image text is written into: left out when it is copied
AUTO_HEIGHT = 270  # "Auto" interface size: about 270 to 450 UI pixels high, whatever the resolution
MIN_HEIGHT = 180  # the menus need at least this many UI pixels in height
BASE_WIDTH, BASE_HEIGHT = 320, 180  # the menus and the mouse speed are designed for this size
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

# The interface's 16 colors (the first 16 of the palette; the block icons and the 3D view have the rest)
PALETTE = [
    0x000000,  # 0 BLACK: outlines, shadows
    0x17161A,  # 1 COAL: panels
    0x26242B,  # 2 SLATE: rows and slots, a little lighter than the panel
    0x3D3A44,  # 3 IRON: frames, the dark edge of a button
    0x55525E,  # 4 STONE: buttons
    0x74717E,  # 5 PEBBLE: the light edge of a button, a button under the mouse
    0xA3A0AB,  # 6 SILVER: the light edge of a button under the mouse
    0xF4F0E6,  # 7 WHITE: text
    0x8F8A80,  # 8 ASH: text that matters less
    0xE39A2E,  # 9 AMBER: what is chosen
    0xFFD070,  # 10 GOLD: text of what is chosen
    0x8A5418,  # 11 RUST: amber in the shade
    0x74C25C,  # 12 LEAF: progress, "on"
    0x3C7A35,  # 13 MOSS: leaf in the shade
    0xD4513F,  # 14 BRICK: warnings
    0xD9CFB8,  # 15 CREAM: values
]
(BLACK, COAL, SLATE, IRON, STONE, PEBBLE, SILVER, WHITE, ASH, AMBER, GOLD, RUST, LEAF, MOSS, BRICK,
 CREAM) = range(16)
TEXT, TEXT_DIM, TEXT_HOT, VALUE = WHITE, ASH, GOLD, CREAM


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

    def bevel(self, x, y, w, h, face, light, dark, outline=BLACK):
        """A raised block: its face, a light edge on top and on the left, a dark one below and on
        the right, inside an outline. (Swap light and dark for something sunk in.)"""
        self.rect(x, y, w, h, outline)
        self.rect(x + 1, y + 1, w - 2, h - 2, face)
        self.hline(x + 1, x + w - 2, y + 1, light)
        self.vline(x + 1, y + 1, y + h - 2, light)
        self.hline(x + 1, x + w - 2, y + h - 2, dark)
        self.vline(x + w - 2, y + 1, y + h - 2, dark)

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

    def right_text(self, x, y, s, col, shadow=False):
        """Text that ends at x."""
        self.text(x - text_width(s), y, s, col, shadow)

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
                    self.rect(x0 + dx, y0 + dy, 1, 1, BLACK if c == "1" else WHITE)

    # --- Widgets ------------------------------------------------------------------------------

    def panel(self, x, y, w, h, title=None):
        """A dark stone panel with a frame and a soft shadow; the title goes in a band along the
        top. Returns the y where its content starts."""
        self.shade(x + 2, y + h, w, 2, 0.5)  # shadow, below and on the right
        self.shade(x + w, y + 2, 2, h - 2, 0.5)
        self.rect(x, y, w, h, BLACK)
        self.rect(x + 1, y + 1, w - 2, h - 2, COAL)
        self.rectb(x + 1, y + 1, w - 2, h - 2, IRON)
        if title is None:
            return y + 5
        self.rect(x + 2, y + 2, w - 4, 12, SLATE)
        self.hline(x + 2, x + w - 3, y + 14, IRON)
        self.center_text(y + 5, title, TEXT_HOT, shadow=True, cx=x + w // 2)
        return y + 18

    def glass(self, x, y, w, h, amount=0.7):
        """A see-through dark box, for what lies over the world while playing."""
        self.shade(x, y, w, h, amount, COAL)

    def button(self, x, y, w, h, label, hot=False, enabled=True):
        """A raised stone button; hot: under the mouse or chosen with the keyboard."""
        ty = y + (h - 5) // 2
        if not enabled:
            self.rect(x, y, w, h, BLACK)
            self.rect(x + 1, y + 1, w - 2, h - 2, SLATE)
            self.center_text(ty, label, IRON, cx=x + w // 2)
            return
        if hot:
            self.bevel(x, y, w, h, PEBBLE, SILVER, STONE, AMBER)
        else:
            self.bevel(x, y, w, h, STONE, PEBBLE, IRON)
        self.center_text(ty, label, TEXT_HOT if hot else TEXT, shadow=True, cx=x + w // 2)

    def tab(self, x, y, w, h, label, active=False, hot=False):
        """A tab standing on the line drawn at y + h: the active one is taller, has the panel's
        own color and hides the line under it, so it opens onto what the panel shows."""
        if active:
            self.rect(x, y, w, h + 1, IRON)
            self.rect(x + 1, y + 1, w - 2, h, COAL)
            self.hline(x + 1, x + w - 2, y + 1, AMBER)
        else:
            self.rect(x, y + 2, w, h - 2, IRON)
            self.rect(x + 1, y + 3, w - 2, h - 3, SLATE)
        col = TEXT_HOT if active else TEXT if hot else TEXT_DIM
        self.center_text(y + (h - 4) // 2 + (1 if active else 2), label, col, shadow=active, cx=x + w // 2)

    def row(self, x, y, w, h, label, hot=False):
        """The background and the name of a line of the settings; hot: lit, with an amber mark."""
        if hot:
            self.rect(x, y, w, h, SLATE)
            self.rect(x, y, 2, h, AMBER)
        self.text(x + 6, y + (h - 5) // 2, label, TEXT_HOT if hot else TEXT, shadow=hot)

    def setting_row(self, x, y, w, h, label, value, hot=False):
        """A setting with a few values: its name on the left, its value on the right (between
        arrows when hot)."""
        self.row(x, y, w, h, label, hot)
        ty = y + (h - 5) // 2
        vx, vw = self.value_box(x, w)
        self.center_text(ty, value, TEXT_HOT if hot else VALUE, cx=vx + vw // 2)
        if hot:
            self.text(vx, ty, "<", AMBER)
            self.text(vx + vw - 3, ty, ">", AMBER)

    def slider_row(self, x, y, w, h, label, value, fraction, hot=False):
        """A setting on a scale: its name, a track with a knob, and its value in figures."""
        self.row(x, y, w, h, label, hot)
        ty = y + (h - 5) // 2
        sx, sw = self.slider_box(x, w)
        self.rect(sx, y + h // 2 - 2, sw, 4, BLACK)
        self.rect(sx + 1, y + h // 2 - 1, sw - 2, 2, IRON)
        knob = sx + 1 + round((sw - 5) * min(max(fraction, 0.0), 1.0))
        if knob > sx + 1:
            self.rect(sx + 1, y + h // 2 - 1, knob - sx - 1, 2, AMBER if hot else RUST)
        self.bevel(knob, y + h // 2 - 4, 4, 8, GOLD if hot else SILVER, WHITE, AMBER if hot else PEBBLE)
        self.right_text(x + w - 5, ty, value, TEXT_HOT if hot else VALUE)

    def key_row(self, x, y, w, h, label, key, hot=False, listening=False):
        """An action and the key that does it, drawn as a key cap; listening: it waits for the
        player to press its new key."""
        self.row(x, y, w, h, label, hot or listening)
        kw = min(60, w // 2 - 4)
        kx = x + w - kw - 3
        if listening:
            self.rect(kx, y + 1, kw, h - 2, AMBER)
            self.rect(kx + 1, y + 2, kw - 2, h - 4, BLACK)
            self.center_text(y + (h - 5) // 2, "press a key", TEXT_HOT, cx=kx + kw // 2)
            return
        if hot:
            self.bevel(kx, y + 1, kw, h - 2, PEBBLE, SILVER, STONE, AMBER)
        else:
            self.bevel(kx, y + 1, kw, h - 2, STONE, PEBBLE, IRON)
        self.center_text(y + (h - 5) // 2, key, TEXT_HOT if hot else TEXT, shadow=True, cx=kx + kw // 2)

    @staticmethod
    def value_box(x, w):
        """Left and width of the value part of a setting row (its arrows at either end)."""
        vw = min(100, w // 2)
        return x + w - vw - 4, vw

    @staticmethod
    def slider_box(x, w):
        """Left and width of the track of a slider row (the value in figures comes after it)."""
        vw = min(100, w // 2)
        return x + w - vw - 4, vw - 32

    def slot(self, x, y, size, hot=False, chosen=False):
        """A place for a block's icon, sunk into its panel."""
        self.rect(x, y, size, size, AMBER if chosen else SILVER if hot else BLACK)
        self.rect(x + 1, y + 1, size - 2, size - 2, IRON if hot else SLATE)
        if not hot:
            self.hline(x + 1, x + size - 2, y + size - 2, IRON)
            self.vline(x + size - 2, y + 1, y + size - 2, IRON)

    def bar(self, x, y, w, h, fraction, col=LEAF, dark=MOSS):
        """A progress bar."""
        self.rect(x, y, w, h, BLACK)
        self.rect(x + 1, y + 1, w - 2, h - 2, SLATE)
        inner = round((w - 4) * min(max(fraction, 0.0), 1.0))
        if inner > 0:
            self.rect(x + 2, y + 2, inner, h - 4, col)
            self.hline(x + 2, x + 1 + inner, y + h - 3, dark)  # in the shade along the bottom

    def tooltip(self, x, y, s, col=TEXT):
        """A small label next to the mouse pointer (or at (x, y)), kept inside the screen."""
        w, h = text_width(s) + 8, 11
        x = min(max(x + 10, 1), self.width - w - 1)
        y = min(max(y - 2, 1), self.height - h - 1)
        self.rect(x, y, w, h, BLACK)
        self.rect(x + 1, y + 1, w - 2, h - 2, COAL)
        self.rectb(x + 1, y + 1, w - 2, h - 2, AMBER)
        self.text(x + 4, y + 3, s, col)

    def toast(self, y, s, col=TEXT_HOT):
        """A notice in a small dark box, centered."""
        w = text_width(s) + 12
        x = (self.width - w) // 2
        self.glass(x, y, w, 11, 0.8)
        self.rect(x, y, 2, 11, AMBER)
        self.text(x + 7, y + 3, s, col, shadow=True)
