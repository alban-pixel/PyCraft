"""Texture packs in Minecraft's format: finding them, and loading their block textures into the
game's tiles.

A pack is a folder, a .zip, or the .jar of a Minecraft version installed on this computer. Its
block textures are in assets/minecraft/textures/blocks/ (up to 1.12) or .../block/ (1.13 on,
renamed). The files are read where they are: nothing is extracted or copied, and the game ships
no pack of its own. The generated textures stay the default, and fill in whatever a pack lacks."""
import json
import os
import re
import sys
import zipfile
from dataclasses import dataclass

TEXTURE_DIRS = {"1.8": "assets/minecraft/textures/blocks/", "1.13": "assets/minecraft/textures/block/"}


@dataclass(frozen=True)
class PackInfo:
    name: str  # as shown in the settings
    path: str  # folder, .zip or .jar
    description: str
    layout: str  # "1.8" or "1.13": which texture folder and names it uses


def clean_name(text):
    """Text for the 3x5 font: without Minecraft's formatting codes (§ and a letter), printable
    ASCII only."""
    text = re.sub("§.", "", str(text))
    return " ".join("".join(c for c in text if " " <= c <= "~").split())


def _component_text(value):
    """The text of a pack description: a string, or a JSON text component (object or list)."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_component_text(v) for v in value)
    if isinstance(value, dict):
        return _component_text(value.get("text", "")) + "".join(_component_text(v) for v in value.get("extra", []))
    return ""


def minecraft_dir():
    """The folder of the Minecraft installed on this computer, or None."""
    if sys.platform == "darwin":
        path = os.path.expanduser("~/Library/Application Support/minecraft")
    elif sys.platform == "win32":
        path = os.path.join(os.environ.get("APPDATA", ""), ".minecraft")
    else:
        path = os.path.expanduser("~/.minecraft")
    return path if os.path.isdir(path) else None


def pack_dirs(data_dir):
    """The folders where packs are looked for: the game's own resourcepacks folder (made if
    missing), then the installed Minecraft's."""
    own = os.path.join(data_dir, "resourcepacks")
    try:
        os.makedirs(own, exist_ok=True)
    except OSError:
        pass
    dirs = [own]
    mc = minecraft_dir()
    if mc and os.path.isdir(os.path.join(mc, "resourcepacks")):
        dirs.append(os.path.join(mc, "resourcepacks"))
    return dirs


def minecraft_jars():
    """The .jar of every Minecraft version installed on this computer."""
    mc = minecraft_dir()
    if not mc:
        return []
    versions = os.path.join(mc, "versions")
    try:
        names = sorted(os.listdir(versions))
    except OSError:
        return []
    return [os.path.join(versions, v, v + ".jar") for v in names if os.path.isfile(os.path.join(versions, v, v + ".jar"))]


class PackFiles:
    """The block textures of a pack, read by name (without .png)."""

    def __init__(self, path, layout):
        self.prefix = TEXTURE_DIRS[layout]
        self.zip = None
        if os.path.isdir(path):
            self.root = os.path.join(path, *self.prefix.split("/"))
        else:
            self.zip = zipfile.ZipFile(path)
            self.members = {n[len(self.prefix):-4]: n for n in self.zip.namelist()
                            if n.startswith(self.prefix) and n.endswith(".png")}

    def names(self):
        if self.zip is not None:
            return set(self.members)
        out = set()
        for folder, _, files in os.walk(self.root):
            rel = os.path.relpath(folder, self.root)
            for f in files:
                if f.endswith(".png"):
                    out.add(f[:-4] if rel == "." else f"{rel}/{f[:-4]}".replace(os.sep, "/"))
        return out

    def read(self, name):
        """The PNG's bytes, or None if the pack doesn't have it (or it can't be read)."""
        try:
            if self.zip is not None:
                member = self.members.get(name)
                return None if member is None else self.zip.read(member)
            with open(os.path.join(self.root, *name.split("/")) + ".png", "rb") as f:
                return f.read()
        except (OSError, KeyError, zipfile.BadZipFile, RuntimeError, ValueError):
            return None

    def close(self):
        if self.zip is not None:
            self.zip.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def open_pack(info):
    return PackFiles(info.path, info.layout)


def _inspect(path, name):
    """A PackInfo for this folder, zip or jar, or None if it holds no block textures."""
    try:
        if os.path.isdir(path):
            def count(prefix):
                folder = os.path.join(path, *prefix.split("/"))
                return sum(f.endswith(".png") for _, _, fs in os.walk(folder) for f in fs)
            meta_path = os.path.join(path, "pack.mcmeta")
            meta = open(meta_path, "rb").read() if os.path.isfile(meta_path) else None
        else:
            with zipfile.ZipFile(path) as z:
                names = z.namelist()
                meta = z.read("pack.mcmeta") if "pack.mcmeta" in names else None

            def count(prefix):
                return sum(n.startswith(prefix) and n.endswith(".png") for n in names)
        counts = {layout: count(prefix) for layout, prefix in TEXTURE_DIRS.items()}
    except (OSError, zipfile.BadZipFile, RuntimeError, ValueError):
        return None
    layout = max(counts, key=counts.get)
    if counts[layout] == 0:
        return None
    description = ""
    if meta is not None:
        try:
            description = clean_name(_component_text(json.loads(meta.decode("utf-8-sig"))["pack"]["description"]))
        except (ValueError, KeyError, TypeError, UnicodeDecodeError):
            description = ""
    return PackInfo(clean_name(name) or "Pack", path, description, layout)


def find_packs(dirs, jars):
    """Every pack in these folders (subfolders and .zip files), and these Minecraft .jar files,
    sorted by name."""
    found, seen = [], set()
    candidates = []
    for d in dirs:
        try:
            entries = sorted(os.listdir(d))
        except OSError:
            continue
        for e in entries:
            path = os.path.join(d, e)
            if os.path.isdir(path):
                candidates.append((path, e))
            elif e.lower().endswith(".zip"):
                candidates.append((path, e[:-4]))
    for jar in jars:
        candidates.append((jar, "Minecraft " + os.path.basename(jar)[:-4]))
    for path, name in candidates:
        key = os.path.realpath(path)
        if key in seen:
            continue
        seen.add(key)
        info = _inspect(path, name)
        if info is not None:
            found.append(info)
    return sorted(found, key=lambda p: (p.name.lower(), p.path))
