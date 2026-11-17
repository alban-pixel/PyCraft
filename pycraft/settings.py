"""The settings: their values, the defaults, the tabs they are on, reading them from settings.json,
and finding and loading the texture pack they name."""
import os
import sys

from pycraft import packs
from pycraft.render import LOD_QUALITY_NAMES


RESOLUTIONS = [(320, 180), (384, 216), (480, 270), (640, 360), (800, 450), (960, 540), (1280, 720), (1600, 900),
               (1920, 1080), (2560, 1440)]
FRAME_RATES = [30, 60, 75, 120, 144, 165, 240]
RENDER_DISTANCES = [32, 64, 128, 256, 512]  # how far the world is seen, in chunks of 16 blocks
RENDER_SCALES = ["auto", 1.0, 0.75, 0.5]  # share of the resolution the 3D view is drawn at ("auto": follows the FPS)
AUTOSAVES = [0, 1, 2, 5, 10]  # minutes between two automatic saves (0: only when leaving through the menu)
DAY_LENGTHS = [10, 20, 40, 60]  # minutes a full day and night last
CROSSHAIRS = ["cross", "dot", "none"]
RANGES = {  # the settings on a scale: (lowest, highest, step)
    "fov": (50, 110, 5),  # field of view, degrees from the top of the screen to the bottom
    "sensitivity": (10, 300, 10),  # mouse speed, percent
    "look_speed": (30, 240, 10),  # looking around with the arrow keys, degrees per second
    "music_volume": (0, 100, 10),
    "sound_volume": (0, 100, 10),
}
DEFAULT_SETTINGS = {"resolution": (1280, 720), "fps": 60, "render_distance": 256, "lod_quality": "low",
                    "fancy": True, "ui_scale": "auto", "render_scale": "auto", "fov": 70,
                    "sensitivity": 100, "invert_y": False, "look_speed": 120,
                    "music_volume": 50, "sound_volume": 100,
                    "autosave": 2, "day_length": 20, "show_help": True, "crosshair": "cross", "keys": {},
                    "texture_pack": None}  # texture_pack: path of the pack, None for the game's own textures
SETTING_TABS = {  # the tabs of the settings screen and the settings each one holds
    "Video": ["resolution", "ui_scale", "fps", "fov", "render_scale", "render_distance", "lod_quality", "fancy",
              "texture_pack"],
    "Controls": ["sensitivity", "invert_y", "look_speed"],
    "Keys": ["keys"],
    "Sound": ["music_volume", "sound_volume"],
    "Game": ["autosave", "day_length", "show_help", "crosshair"],
}
TAB_NAMES = list(SETTING_TABS)


def parse_settings(saved):
    """The settings from settings.json's contents, with the default for any that is missing or
    not valid."""
    settings = dict(DEFAULT_SETTINGS)
    if not isinstance(saved, dict):
        return settings
    resolution = saved.get("resolution")
    if isinstance(resolution, list) and tuple(resolution) in RESOLUTIONS:
        settings["resolution"] = tuple(resolution)
    ui_scale = saved.get("ui_scale")
    if ui_scale == "auto" or (type(ui_scale) is int and 1 <= ui_scale <= 8):
        settings["ui_scale"] = ui_scale
    choices = {"fps": FRAME_RATES, "render_distance": RENDER_DISTANCES, "lod_quality": LOD_QUALITY_NAMES,
               "render_scale": RENDER_SCALES, "autosave": AUTOSAVES, "day_length": DAY_LENGTHS,
               "crosshair": CROSSHAIRS}
    for key, allowed in choices.items():
        if type(saved.get(key)) is not bool and saved.get(key) in allowed:
            settings[key] = saved[key]
    for key, (low, high, step) in RANGES.items():
        value = saved.get(key)
        if type(value) is int and low <= value <= high and (value - low) % step == 0:
            settings[key] = value
    for key in ("fancy", "invert_y", "show_help"):
        if isinstance(saved.get(key), bool):
            settings[key] = saved[key]
    if saved.get("music") is False and "music_volume" not in saved:
        settings["music_volume"] = 0  # (a file from before the volumes: the music was on or off)
    if isinstance(saved.get("keys"), dict):
        settings["keys"] = dict(saved["keys"])
    pack = saved.get("texture_pack")
    if isinstance(pack, str) and os.path.exists(pack):  # (a pack deleted since: the game's own textures)
        settings["texture_pack"] = pack
    return settings


def load_tiles(path, found, default_tiles):
    """The tiles of the texture pack at path (None: the game's own, default_tiles), looked up among
    the packs found. Returns (tiles, message, path): a pack that can't be read gives the game's own
    tiles, a message for the settings and None."""
    if path is None:
        return default_tiles, "", None
    info = next((p for p in found if p.path == path), None)
    try:
        if info is None:
            listed = packs.find_packs([os.path.dirname(path)], [path] if path.endswith(".jar") else [])
            info = next((p for p in listed if p.path == path), None)
        if info is None:
            raise packs.PackError("no block textures")
        tiles, missing = packs.load_pack(info, default_tiles)
    except Exception as e:  # whatever is in the file, the game goes on with its own textures
        print(f"Texture pack {path} unreadable: {e!r}", file=sys.stderr)
        return default_tiles, fit_text(f"Pack unreadable: {e}", 56, keep="start"), None
    if missing:
        print(f"Texture pack {info.name}: {len(missing)} textures missing, the game's own drawn instead: "
              + ", ".join(missing), file=sys.stderr)
    return tiles, "", path


def next_pack(current, found, step):
    """The texture pack after (step 1) or before (step -1) the current one: None (the game's own
    textures), then the packs found, round and round. Paths."""
    choices = [None] + [p.path for p in found]
    i = choices.index(current) if current in choices else 0
    return choices[(i + step) % len(choices)]


def fit_text(text, n, keep="end"):
    """The text cut to n characters at most, with "..." where it was cut: keeping its end (paths)
    or its start (names)."""
    if len(text) <= n:
        return text
    return "..." + text[len(text) - n + 3:] if keep == "end" else text[:n - 3] + "..."
