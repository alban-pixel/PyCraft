"""Asset Ingestion & Extraction Utility for PyCraft Vanilla 1.8 Parity.

Extracts authentic 1.8 textures (.png) from 1.8.jar and sound assets (.ogg) from
hash-addressed assets/objects/ into local project directories. Includes procedural
fallback generation and strict zero-.jar distribution compliance enforcement.

Zero runtime dependency: Once assets are extracted or synthesized, PyCraft runs
entirely from pycraft-gpu/assets/vanilla/ without inspecting external paths.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import sys
import time
import zipfile
from dataclasses import dataclass, field
from typing import Any

DEFAULT_MINECRAFT_PATHS = {
    "Darwin": os.path.expanduser("~/Library/Application Support/minecraft"),
    "Linux": os.path.expanduser("~/.minecraft"),
    "Windows": os.path.expandvars(r"%APPDATA%\.minecraft"),
}

DEFAULT_OUTPUT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "assets", "vanilla")
)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FORBIDDEN_EXTENSIONS = {".jar", ".class", ".exe", ".dll", ".dylib", ".so"}


@dataclass
class ExtractionStats:
    textures_extracted: int = 0
    mcmeta_extracted: int = 0
    textures_bytes: int = 0
    sounds_extracted: int = 0
    sounds_skipped_music: int = 0
    sounds_bytes: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class VanillaAssetExtractor:
    def __init__(
        self,
        minecraft_dir: str | None = None,
        output_dir: str = DEFAULT_OUTPUT_DIR,
        skip_music: bool = False,
        verify_sha1: bool = True,
        repo_root: str = REPO_ROOT,
    ) -> None:
        self.minecraft_dir = minecraft_dir or self.auto_detect_minecraft_dir()
        self.output_dir = os.path.abspath(output_dir)
        self.textures_dir = os.path.join(self.output_dir, "textures")
        self.sounds_dir = os.path.join(self.output_dir, "sounds")
        self.skip_music = skip_music
        self.verify_sha1 = verify_sha1
        self.repo_root = os.path.abspath(repo_root)
        self.stats = ExtractionStats()

    @staticmethod
    def auto_detect_minecraft_dir() -> str | None:
        system = platform.system()
        candidate = DEFAULT_MINECRAFT_PATHS.get(system)
        if candidate and os.path.isdir(candidate):
            return candidate
        for path in DEFAULT_MINECRAFT_PATHS.values():
            if os.path.isdir(path):
                return path
        return None

    def validate_reference_files(self) -> tuple[bool, str]:
        """Check if 1.8.jar and assets index exist in the minecraft directory."""
        if not self.minecraft_dir or not os.path.isdir(self.minecraft_dir):
            return False, f"Minecraft directory not found: {self.minecraft_dir}"

        jar_path = os.path.join(self.minecraft_dir, "versions", "1.8", "1.8.jar")
        if not os.path.isfile(jar_path):
            return False, f"1.8.jar not found at: {jar_path}"

        index_path = os.path.join(self.minecraft_dir, "assets", "indexes", "1.8.json")
        if not os.path.isfile(index_path):
            return False, f"1.8.json index not found at: {index_path}"

        objects_dir = os.path.join(self.minecraft_dir, "assets", "objects")
        if not os.path.isdir(objects_dir):
            return False, f"assets/objects directory not found at: {objects_dir}"

        return True, "Valid"

    def clean_output_dir(self) -> None:
        """Remove target directories to ensure clean re-extraction."""
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.textures_dir, exist_ok=True)
        os.makedirs(self.sounds_dir, exist_ok=True)

    def extract_textures(self) -> None:
        """Extract all 1,058 texture and mcmeta files from 1.8.jar into textures/."""
        if not self.minecraft_dir:
            return
        jar_path = os.path.join(self.minecraft_dir, "versions", "1.8", "1.8.jar")
        prefix = "assets/minecraft/textures/"

        os.makedirs(self.textures_dir, exist_ok=True)
        with zipfile.ZipFile(jar_path, "r") as zf:
            for item in zf.infolist():
                if item.is_dir() or not item.filename.startswith(prefix):
                    continue

                rel_subpath = item.filename[len(prefix):]
                dest_path = os.path.join(self.textures_dir, rel_subpath)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                data = zf.read(item.filename)
                with open(dest_path, "wb") as f:
                    f.write(data)

                self.stats.textures_bytes += len(data)
                if dest_path.endswith(".mcmeta"):
                    self.stats.mcmeta_extracted += 1
                else:
                    self.stats.textures_extracted += 1

    def extract_sounds(self) -> None:
        """Extract sound objects using 1.8.json index into sounds/."""
        if not self.minecraft_dir:
            return
        index_path = os.path.join(self.minecraft_dir, "assets", "indexes", "1.8.json")
        objects_dir = os.path.join(self.minecraft_dir, "assets", "objects")

        with open(index_path, "r", encoding="utf-8") as f:
            index_data = json.load(f)

        objects = index_data.get("objects", {})
        os.makedirs(self.sounds_dir, exist_ok=True)

        # 1. Extract sounds.json
        sound_json_entry = objects.get("minecraft/sounds.json")
        if sound_json_entry:
            h = sound_json_entry["hash"]
            src_path = os.path.join(objects_dir, h[:2], h)
            if os.path.exists(src_path):
                dest_path = os.path.join(self.sounds_dir, "sounds.json")
                shutil.copyfile(src_path, dest_path)

        # 2. Extract .ogg audio files
        sound_prefix = "minecraft/sounds/"
        for key, entry in objects.items():
            if not key.startswith(sound_prefix) or not key.endswith(".ogg"):
                continue

            rel_subpath = key[len(sound_prefix):]

            # Optional skip music to reduce disk footprint
            if self.skip_music and (rel_subpath.startswith("music/") or rel_subpath.startswith("records/")):
                self.stats.sounds_skipped_music += 1
                continue

            h = entry["hash"]
            src_path = os.path.join(objects_dir, h[:2], h)
            if not os.path.isfile(src_path):
                self.stats.warnings.append(f"Missing sound object on disk: {key} ({h})")
                continue

            dest_path = os.path.join(self.sounds_dir, rel_subpath)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)

            with open(src_path, "rb") as f_in:
                data = f_in.read()

            if self.verify_sha1:
                digest = hashlib.sha1(data).hexdigest()
                if digest != h:
                    self.stats.errors.append(f"SHA-1 mismatch on {key}: expected {h}, got {digest}")
                    continue

            with open(dest_path, "wb") as f_out:
                f_out.write(data)

            self.stats.sounds_extracted += 1
            self.stats.sounds_bytes += len(data)

    def enforce_no_jars(self) -> None:
        """Assert zero .jar or prebuilt Minecraft binaries exist in the repository."""
        violations = []
        for root, dirs, files in os.walk(self.repo_root):
            # Skip virtual environments and version control metadata
            if any(part in root for part in [".venv", "venv", ".git", ".pytest_cache"]):
                continue

            for f in files:
                _, ext = os.path.splitext(f)
                if ext.lower() in FORBIDDEN_EXTENSIONS:
                    violations.append(os.path.join(root, f))

        if violations:
            raise RuntimeError(
                "Distribution constraint violation! Forbidden binaries found in repository:\n"
                + "\n".join(f"  - {v}" for v in violations)
            )

    def generate_procedural_fallbacks(self) -> None:
        """Synthesize fallback 16x16 block textures, 256x256 GUI sheets, and sounds.json."""
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            raise RuntimeError("PIL (Pillow) is required for procedural fallback generation.")

        os.makedirs(os.path.join(self.textures_dir, "blocks"), exist_ok=True)
        os.makedirs(os.path.join(self.textures_dir, "gui", "container"), exist_ok=True)
        os.makedirs(os.path.join(self.textures_dir, "items"), exist_ok=True)
        os.makedirs(os.path.join(self.textures_dir, "particle"), exist_ok=True)
        os.makedirs(os.path.join(self.textures_dir, "colormap"), exist_ok=True)
        os.makedirs(self.sounds_dir, exist_ok=True)

        # 1. Procedural Block Textures (16x16)
        block_colors = {
            "stone.png": (125, 125, 125),
            "dirt.png": (134, 96, 67),
            "grass_top.png": (180, 180, 180),  # Tintable grayscale
            "grass_side.png": (134, 96, 67),
            "cobblestone.png": (100, 100, 100),
            "planks_oak.png": (162, 130, 78),
            "log_oak.png": (103, 82, 49),
            "log_oak_top.png": (153, 125, 78),
            "leaves_oak.png": (180, 180, 180),
            "sand.png": (219, 207, 153),
            "bedrock.png": (50, 50, 50),
            "glass.png": (220, 240, 255),
            "water_still.png": (40, 80, 220),
            "lava_still.png": (230, 90, 20),
            "furnace_front_off.png": (110, 110, 110),
            "furnace_front_on.png": (240, 140, 30),
            "furnace_side.png": (110, 110, 110),
            "furnace_top.png": (110, 110, 110),
            "crafting_table_top.png": (162, 130, 78),
            "crafting_table_side.png": (140, 110, 60),
        }
        for name, col in block_colors.items():
            img = Image.new("RGBA", (16, 16), col + (255,))
            draw = ImageDraw.Draw(img)
            draw.rectangle([0, 0, 15, 15], outline=(col[0] // 2, col[1] // 2, col[2] // 2, 255))
            dest = os.path.join(self.textures_dir, "blocks", name)
            img.save(dest)
            self.stats.textures_extracted += 1

        # 2. Procedural GUI Sheets (256x256)
        # icons.png
        icons = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        d_icons = ImageDraw.Draw(icons)
        # Crosshair at (0, 0, 15x15)
        d_icons.line([(7, 1), (7, 13)], fill=(255, 255, 255, 255), width=1)
        d_icons.line([(1, 7), (13, 7)], fill=(255, 255, 255, 255), width=1)
        # Hearts at (52, 0, 9x9 full red, 16, 0, 9x9 empty)
        d_icons.rectangle([53, 1, 60, 8], fill=(220, 20, 20, 255), outline=(0, 0, 0, 255))
        d_icons.rectangle([17, 1, 24, 8], fill=(40, 40, 40, 255), outline=(0, 0, 0, 255))
        # Food drumstick at (52, 27, 9x9)
        d_icons.rectangle([53, 28, 60, 35], fill=(180, 120, 50, 255), outline=(0, 0, 0, 255))
        # Armor at (34, 9, 9x9)
        d_icons.rectangle([35, 10, 42, 17], fill=(180, 180, 180, 255), outline=(0, 0, 0, 255))
        # Oxygen bubble at (16, 18, 9x9)
        d_icons.ellipse([17, 19, 24, 26], fill=(100, 180, 255, 255), outline=(0, 0, 0, 255))
        # Experience bar at (0, 64, 182x5) empty, (0, 69, 182x5) full
        d_icons.rectangle([0, 64, 181, 68], fill=(30, 30, 30, 255), outline=(0, 0, 0, 255))
        d_icons.rectangle([0, 69, 181, 73], fill=(128, 255, 32, 255), outline=(0, 0, 0, 255))
        icons.save(os.path.join(self.textures_dir, "gui", "icons.png"))

        # widgets.png
        widgets = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        d_widgets = ImageDraw.Draw(widgets)
        # 182x22 hotbar frame at (0, 0)
        d_widgets.rectangle([0, 0, 181, 21], fill=(140, 140, 140, 200), outline=(50, 50, 50, 255))
        for slot in range(9):
            x = slot * 20
            d_widgets.rectangle([x + 1, 1, x + 21, 21], outline=(200, 200, 200, 255))
        # 24x24 hotbar selector at (0, 22)
        d_widgets.rectangle([0, 22, 23, 45], outline=(255, 255, 255, 255), width=2)
        # 200x20 button textures at (0, 66) normal, (0, 86) hover
        d_widgets.rectangle([0, 66, 199, 85], fill=(120, 120, 120, 255), outline=(0, 0, 0, 255))
        d_widgets.rectangle([0, 86, 199, 105], fill=(160, 160, 200, 255), outline=(0, 0, 0, 255))
        widgets.save(os.path.join(self.textures_dir, "gui", "widgets.png"))

        # options_background.png (16x16)
        dirt_bg = Image.new("RGBA", (16, 16), (64, 46, 32, 255))
        dirt_bg.save(os.path.join(self.textures_dir, "gui", "options_background.png"))

        # container/inventory.png (176x166 frame on 256x256)
        inv = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
        d_inv = ImageDraw.Draw(inv)
        d_inv.rectangle([0, 0, 175, 165], fill=(198, 198, 198, 255), outline=(60, 60, 60, 255))
        # 3D player preview window at (25, 7, 51x72)
        d_inv.rectangle([25, 7, 75, 78], fill=(0, 0, 0, 255), outline=(50, 50, 50, 255))
        inv.save(os.path.join(self.textures_dir, "gui", "container", "inventory.png"))

        # container/crafting_table.png, furnace.png, generic_54.png
        for cont_name in ["crafting_table.png", "furnace.png", "generic_54.png"]:
            c_img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
            d_c = ImageDraw.Draw(c_img)
            d_c.rectangle([0, 0, 175, 165], fill=(198, 198, 198, 255), outline=(60, 60, 60, 255))
            c_img.save(os.path.join(self.textures_dir, "gui", "container", cont_name))

        # 3. Empty armor slot silhouettes
        for slot in ["helmet", "chestplate", "leggings", "boots"]:
            sil = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
            d_sil = ImageDraw.Draw(sil)
            d_sil.rectangle([3, 3, 12, 12], outline=(150, 150, 150, 180))
            sil.save(os.path.join(self.textures_dir, "items", f"empty_armor_slot_{slot}.png"))

        # 4. Colormaps (grass.png, foliage.png)
        cmap = Image.new("RGB", (256, 256), (95, 159, 53))
        cmap.save(os.path.join(self.textures_dir, "colormap", "grass.png"))
        cmap.save(os.path.join(self.textures_dir, "colormap", "foliage.png"))

        # 5. Fallback sounds.json mapping
        canonical_events = {
            "gui.button.press": {"category": "master", "sounds": ["random/click"]},
            "random.click": {"category": "block", "sounds": ["random/click"]},
            "dig.stone": {"category": "block", "sounds": ["dig/stone1", "dig/stone2"]},
            "dig.grass": {"category": "block", "sounds": ["dig/grass1", "dig/grass2"]},
            "dig.wood": {"category": "block", "sounds": ["dig/wood1", "dig/wood2"]},
            "step.stone": {"category": "neutral", "sounds": ["step/stone1", "step/stone2"]},
            "step.grass": {"category": "neutral", "sounds": ["step/grass1", "step/grass2"]},
            "step.wood": {"category": "neutral", "sounds": ["step/wood1", "step/wood2"]},
            "game.player.hurt": {"category": "player", "sounds": ["damage/hit1"]},
            "game.player.die": {"category": "player", "sounds": ["damage/hit1"]},
            "random.eat": {"category": "player", "sounds": ["random/eat1"]},
            "random.burp": {"category": "player", "sounds": ["random/burp"]},
            "random.explode": {"category": "block", "sounds": ["random/explode1"]},
        }
        with open(os.path.join(self.sounds_dir, "sounds.json"), "w", encoding="utf-8") as f:
            json.dump(canonical_events, f, indent=2)

    def run(self, force_fallback: bool = False, clean: bool = False) -> ExtractionStats:
        t0 = time.time()
        print("=== PyCraft Vanilla 1.8 Asset Ingestion ===")

        if clean:
            print("Cleaning destination directory...")
            self.clean_output_dir()

        is_valid, reason = self.validate_reference_files()
        if not is_valid or force_fallback:
            print(f"Reference files unavailable or fallback requested ({reason}). Generating procedural fallbacks...")
            self.generate_procedural_fallbacks()
        else:
            print(f"Reading reference installation: {self.minecraft_dir}")
            print("Extracting textures from 1.8.jar...")
            self.extract_textures()
            print("Extracting sounds from assets/objects/...")
            self.extract_sounds()

        print("Enforcing zero .jar distribution constraint...")
        self.enforce_no_jars()

        elapsed = time.time() - t0
        print(f"Extraction complete in {elapsed:.3f}s:")
        print(f"  Textures: {self.stats.textures_extracted} PNGs, {self.stats.mcmeta_extracted} MCMETA ({self.stats.textures_bytes / 1024 / 1024:.2f} MB)")
        print(f"  Sounds:   {self.stats.sounds_extracted} OGGs ({self.stats.sounds_bytes / 1024 / 1024:.2f} MB)")
        if self.stats.sounds_skipped_music:
            print(f"  Music skipped: {self.stats.sounds_skipped_music} files")
        if self.stats.warnings:
            print(f"  Warnings: {len(self.stats.warnings)}")
        if self.stats.errors:
            print(f"  Errors:   {len(self.stats.errors)}")

        return self.stats


def main() -> None:
    parser = argparse.ArgumentParser(description="PyCraft Vanilla 1.8 Asset Extractor & Fallback Generator")
    parser.add_argument("--minecraft-dir", type=str, default=None, help="Path to .minecraft directory")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUTPUT_DIR, help="Target assets/vanilla directory")
    parser.add_argument("--skip-music", action="store_true", help="Skip large background music files")
    parser.add_argument("--generate-fallback", action="store_true", help="Force synthetic fallback generation")
    parser.add_argument("--verify-sha1", action="store_true", default=True, help="Verify SHA-1 checksums of audio files")
    parser.add_argument("--clean", action="store_true", help="Clean destination directory before extraction")
    parser.add_argument("--enforce-no-jars", action="store_true", default=True, help="Enforce zero .jar distribution rule")
    args = parser.parse_args()

    extractor = VanillaAssetExtractor(
        minecraft_dir=args.minecraft_dir,
        output_dir=args.output_dir,
        skip_music=args.skip_music,
        verify_sha1=args.verify_sha1,
    )
    stats = extractor.run(force_fallback=args.generate_fallback, clean=args.clean)
    if stats.errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
