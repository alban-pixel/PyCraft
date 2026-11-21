"""Small synthetic texture packs for the tests: our own PNGs, never Mojang's."""
import io
import json
import os
import zipfile

import numpy as np
from PIL import Image

FOLDERS = {"1.8": "assets/minecraft/textures/blocks", "1.13": "assets/minecraft/textures/block"}
ITEM_FOLDERS = {"1.8": "assets/minecraft/textures/items", "1.13": "assets/minecraft/textures/item"}


def png(pixels):
    """PNG bytes of an (h, w, 3 or 4) uint8 array."""
    buf = io.BytesIO()
    Image.fromarray(np.asarray(pixels, np.uint8)).save(buf, "PNG")
    return buf.getvalue()


def solid(color, size=16):
    """A square texture of one color (RGB or RGBA)."""
    color = tuple(color) + ((255,) if len(color) == 3 else ())
    return np.tile(np.array(color, np.uint8), (size, size, 1))


def make_pack(root, name, layout, textures, zip=False, description="test", raw=None, items=None):
    """Write a pack under root: textures maps a file name (without .png) to an array, raw maps a
    file name to bytes written as they are, items maps an item texture's name to an array.
    Returns the pack's path (a folder or a .zip)."""
    files = {"pack.mcmeta": json.dumps({"pack": {"pack_format": 1, "description": description}}).encode()}
    for tex, pixels in textures.items():
        files[f"{FOLDERS[layout]}/{tex}.png"] = png(pixels)
    for tex, data in (raw or {}).items():
        files[f"{FOLDERS[layout]}/{tex}.png"] = data
    for tex, pixels in (items or {}).items():
        files[f"{ITEM_FOLDERS[layout]}/{tex}.png"] = png(pixels)
    os.makedirs(root, exist_ok=True)
    if zip:
        path = os.path.join(root, name + ".zip")
        with zipfile.ZipFile(path, "w") as z:
            for rel, data in files.items():
                z.writestr(rel, data)
        return path
    path = os.path.join(root, name)
    for rel, data in files.items():
        full = os.path.join(path, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(data)
    return path
