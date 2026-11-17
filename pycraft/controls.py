"""The keys of the game: what each action is called, the key or mouse button that does it, and the
names the keys have in the menus and in the settings file. The player can give every action
another key (Settings, Keys)."""
import pyxel

ACTIONS = [  # (name in the settings file, name in the menus, default key)
    ("forward", "Move forward", "W"),
    ("back", "Move back", "S"),
    ("left", "Move left", "A"),
    ("right", "Move right", "D"),
    ("jump", "Jump, swim, fly up", "SPACE"),
    ("down", "Fly down", "LEFT SHIFT"),
    ("sprint", "Sprint, fly fast", "LEFT CTRL"),
    ("fly", "Fly on/off", "F"),
    ("zoom", "Zoom", "C"),
    ("break", "Break a block", "MOUSE LEFT"),
    ("place", "Place, use a block", "MOUSE RIGHT"),
    ("pick", "Pick the block", "MOUSE MIDDLE"),
    ("inventory", "All the blocks", "E"),
    ("chat", "Chat, commands", "T"),
    ("mouse", "Free the mouse", "TAB"),
    ("info", "Info", "F3"),
    ("help", "Show the controls", "H"),
]
LABELS = {action: label for action, label, _ in ACTIONS}
DEFAULTS = {action: key for action, _, key in ACTIONS}


def _key_names():
    """Name -> Pyxel key of every key or mouse button an action can have. Left out: Escape (the
    menu), 1 to 9 (the hotbar), the arrows (they look around and move through the menus), Enter
    and the slash (the chat)."""
    names = {chr(ord("A") + i): pyxel.KEY_A + i for i in range(26)}
    names["0"] = pyxel.KEY_0
    names.update({f"F{i}": getattr(pyxel, f"KEY_F{i}") for i in range(1, 13)})
    names.update({f"NUM {i}": getattr(pyxel, f"KEY_KP_{i}") for i in range(10)})
    for name, key in (
            ("SPACE", "SPACE"), ("TAB", "TAB"), ("BACKSPACE", "BACKSPACE"), ("DELETE", "DELETE"),
            ("INSERT", "INSERT"), ("HOME", "HOME"), ("END", "END"), ("PAGE UP", "PAGEUP"), ("PAGE DOWN", "PAGEDOWN"),
            ("LEFT SHIFT", "LSHIFT"), ("RIGHT SHIFT", "RSHIFT"), ("LEFT CTRL", "LCTRL"), ("RIGHT CTRL", "RCTRL"),
            ("LEFT ALT", "LALT"), ("RIGHT ALT", "RALT"), ("CAPS LOCK", "CAPSLOCK"),
            ("-", "MINUS"), ("=", "EQUALS"), ("[", "LEFTBRACKET"), ("]", "RIGHTBRACKET"), (";", "SEMICOLON"),
            ("'", "QUOTE"), (",", "COMMA"), (".", "PERIOD"), ("\\", "BACKSLASH"), ("`", "BACKQUOTE"),
            ("NUM ENTER", "KP_ENTER"), ("NUM +", "KP_PLUS"), ("NUM -", "KP_MINUS"), ("NUM *", "KP_MULTIPLY"),
            ("NUM /", "KP_DIVIDE"), ("NUM .", "KP_PERIOD")):
        names[name] = getattr(pyxel, "KEY_" + key)
    for name, button in (("MOUSE LEFT", "LEFT"), ("MOUSE RIGHT", "RIGHT"), ("MOUSE MIDDLE", "MIDDLE"),
                         ("MOUSE 4", "X1"), ("MOUSE 5", "X2")):
        names[name] = getattr(pyxel, "MOUSE_BUTTON_" + button)
    return names


KEYS = _key_names()
NAMES = {key: name for name, key in KEYS.items()}
NO_KEY = "-"  # how an action without a key shows


class Controls:
    def __init__(self, saved=None):
        """saved: {action: key name} from the settings file. A name that isn't a key, or a key an
        earlier action already has, is left out: that action keeps its default key if it is free."""
        saved = saved if isinstance(saved, dict) else {}
        self.keys = {}
        for action, _, default in ACTIONS:
            name = saved.get(action, default)
            if name == NO_KEY:
                self.keys[action] = None
                continue
            for name in (name, default):
                key = KEYS.get(name) if isinstance(name, str) else None
                if key is not None and key not in self.keys.values():
                    break
            else:
                key = None
            self.keys[action] = key

    def held(self, action):
        key = self.keys[action]
        return key is not None and bool(pyxel.btn(key))

    def pressed(self, action, hold=0, repeat=0):
        """True on the frame the action's key goes down (and again every `repeat` frames once it
        has been held for `hold` frames)."""
        key = self.keys[action]
        return key is not None and bool(pyxel.btnp(key, hold=hold, repeat=repeat))

    def name(self, action):
        return NAMES.get(self.keys[action], NO_KEY)

    def is_default(self):
        return all(self.name(action) == default for action, _, default in ACTIONS)

    def reset(self):
        self.keys = {action: KEYS[default] for action, _, default in ACTIONS}

    def bind(self, action, key):
        """Give an action a key. If another action had it, the two swap keys: returns that
        action, or None."""
        other = next((a for a, k in self.keys.items() if k == key and a != action), None)
        if other is not None:
            self.keys[other] = self.keys[action]
        self.keys[action] = key
        return other

    @staticmethod
    def key_pressed():
        """The key or mouse button that went down this frame, among those an action can have."""
        for key in NAMES:
            if pyxel.btnp(key):
                return key
        return None

    def to_settings(self):
        return {action: self.name(action) for action, _, _ in ACTIONS}
