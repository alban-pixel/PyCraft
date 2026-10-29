"""Texture / Resource Pack Manager for PyCraft.

Manages built-in and user-installed resource packs located in `resourcepacks/`.
Supports loading packs from directories and .zip files with pack.mcmeta metadata,
live hot-reloading into Pyxel image bank 0 and ModernGL texture 0 without restarting.
"""
import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

from blocks import ATLAS_TILES, TILE, build_atlas


@dataclass
class ResourcePackInfo:
    """Metadata describing a resource pack."""
    pack_id: str
    name: str
    description: str
    pack_format: int
    is_builtin: bool
    path: Optional[str] = None


class TexturePackManager:
    """Discovers, parses, and activates resource packs."""

    def __init__(self, packs_dir: str):
        self.packs_dir = packs_dir
        os.makedirs(self.packs_dir, exist_ok=True)
        self.active_pack_id = "default"
        self._ensure_sample_pack()

    def _ensure_sample_pack(self):
        """Creates a sample resource pack structure if folder is empty."""
        sample_dir = os.path.join(self.packs_dir, "sample_pack")
        if not os.path.exists(sample_dir):
            try:
                os.makedirs(sample_dir, exist_ok=True)
                mcmeta = {
                    "pack": {
                        "pack_format": 1,
                        "description": "Example PyCraft Resource Pack"
                    }
                }
                with open(os.path.join(sample_dir, "pack.mcmeta"), "w", encoding="utf-8") as f:
                    json.dump(mcmeta, f, indent=2)
            except OSError:
                pass

    def list_packs(self) -> List[ResourcePackInfo]:
        """Return all available packs (built-in + scanned in resourcepacks/)."""
        packs = [
            ResourcePackInfo(
                pack_id="default",
                name="Default (PyCraft 1.8)",
                description="Iconic standard Minecraft 1.8 procedural pixel art.",
                pack_format=1,
                is_builtin=True,
            ),
            ResourcePackInfo(
                pack_id="faithful",
                name="Faithful 16x",
                description="Sharper contrast, well-defined brick joints and vivid ores.",
                pack_format=1,
                is_builtin=True,
            ),
            ResourcePackInfo(
                pack_id="retro",
                name="Retro Classic (Alpha)",
                description="Nostalgic vibrant alpha green terrain and saturated colors.",
                pack_format=1,
                is_builtin=True,
            ),
            ResourcePackInfo(
                pack_id="dark_mode",
                name="Dark Mode / Obsidian",
                description="Sleek dark stone, deep obsidian hues, and low-contrast stone.",
                pack_format=1,
                is_builtin=True,
            ),
        ]

        # Scan resourcepacks directory
        if os.path.exists(self.packs_dir):
            for entry in sorted(os.listdir(self.packs_dir)):
                full_path = os.path.join(self.packs_dir, entry)
                pack_info = self._inspect_pack(full_path, entry)
                if pack_info:
                    packs.append(pack_info)

        return packs

    def _inspect_pack(self, path: str, filename: str) -> Optional[ResourcePackInfo]:
        """Inspect a file or directory to determine if it is a valid resource pack."""
        # Skip sample_pack if it's unconfigured
        if filename == "sample_pack":
            pass

        if os.path.isdir(path):
            mcmeta_path = os.path.join(path, "pack.mcmeta")
            desc = "Custom User Resource Pack"
            p_format = 1
            if os.path.exists(mcmeta_path):
                try:
                    with open(mcmeta_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    desc = data.get("pack", {}).get("description", desc)
                    p_format = data.get("pack", {}).get("pack_format", 1)
                except Exception:
                    pass
            pack_name = filename.replace("_", " ").title()
            return ResourcePackInfo(
                pack_id=f"dir_{filename}",
                name=pack_name,
                description=desc,
                pack_format=p_format,
                is_builtin=False,
                path=path,
            )

        if zipfile.is_zipfile(path):
            pack_id = f"zip_{os.path.splitext(filename)[0]}"
            pack_name = os.path.splitext(filename)[0].replace("_", " ").title()
            desc = "Zipped Resource Pack"
            p_format = 1
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    if "pack.mcmeta" in zf.namelist():
                        meta_bytes = zf.read("pack.mcmeta")
                        data = json.loads(meta_bytes.decode("utf-8"))
                        desc = data.get("pack", {}).get("description", desc)
                        p_format = data.get("pack", {}).get("pack_format", 1)
            except Exception:
                pass
            return ResourcePackInfo(
                pack_id=pack_id,
                name=pack_name,
                description=desc,
                pack_format=p_format,
                is_builtin=False,
                path=path,
            )

        return None

    def build_pack_atlas(self, pack_id: str) -> np.ndarray:
        """Construct the 256x256 RGBA atlas array for the specified pack."""
        if pack_id == "faithful":
            # Higher contrast, punchier colors, enhanced brick and ore definitions
            base = build_atlas(seed=1337).astype(np.float32)
            # Enhance contrast: stretch away from middle grey
            mean = 128.0
            enhanced = (base[..., :3] - mean) * 1.25 + mean
            base[..., :3] = np.clip(enhanced, 0, 255)
            return base.astype(np.uint8)

        elif pack_id == "retro":
            # Alpha/Beta vibrant saturated greens and classic nostalgic colors
            base = build_atlas(seed=42).astype(np.float32)
            # Boost green channel for grass/leaves (top left area)
            base[:32, :32, 1] = np.clip(base[:32, :32, 1] * 1.35, 0, 255)
            # Boost water saturation
            base[..., 0] = np.clip(base[..., 0] * 1.05, 0, 255)
            return base.astype(np.uint8)

        elif pack_id == "dark_mode":
            # Sleek dark theme
            base = build_atlas(seed=777).astype(np.float32)
            # Darken stones and terrains by 30%
            base[..., :3] = np.clip(base[..., :3] * 0.72, 0, 255)
            return base.astype(np.uint8)

        # Check if it's a custom directory/zip pack
        for pack in self.list_packs():
            if pack.pack_id == pack_id and pack.path:
                custom_atlas = self._load_custom_atlas(pack.path)
                if custom_atlas is not None:
                    return custom_atlas

        # Default fallback
        return build_atlas(seed=7)

    def _load_custom_atlas(self, path: str) -> Optional[np.ndarray]:
        """Try loading an atlas image from a folder or zip pack."""
        # Try importing PIL if available
        try:
            from PIL import Image
        except ImportError:
            Image = None

        target_size = (TILE * ATLAS_TILES, TILE * ATLAS_TILES)

        if os.path.isdir(path) and Image:
            for candidate in ["textures/atlas.png", "textures/terrain.png", "terrain.png", "pack.png"]:
                c_path = os.path.join(path, candidate)
                if os.path.exists(c_path):
                    try:
                        im = Image.open(c_path).convert("RGBA")
                        if im.size != target_size:
                            im = im.resize(target_size, Image.NEAREST)
                        return np.array(im, dtype=np.uint8)
                    except Exception:
                        pass

        if zipfile.is_zipfile(path) and Image:
            try:
                with zipfile.ZipFile(path, "r") as zf:
                    for candidate in ["textures/atlas.png", "textures/terrain.png", "terrain.png", "pack.png"]:
                        if candidate in zf.namelist():
                            with zf.open(candidate) as f:
                                im = Image.open(f).convert("RGBA")
                                if im.size != target_size:
                                    im = im.resize(target_size, Image.NEAREST)
                                return np.array(im, dtype=np.uint8)
            except Exception:
                pass

        return None
