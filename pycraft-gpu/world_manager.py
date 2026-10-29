"""World save manager: handles multiple world saves, metadata, creation, deletion, and migration."""
import json
import os
import re
import shutil
import time
from typing import Any, Dict, List, Optional


class WorldManager:
    """Manages the saves directory, world metadata, and multi-world persistence."""

    def __init__(self, saves_dir: str):
        self.saves_dir = saves_dir
        os.makedirs(self.saves_dir, exist_ok=True)

    @staticmethod
    def sanitize_folder_name(name: str) -> str:
        """Create a safe filesystem folder name from a world title."""
        safe = re.sub(r"[^\w\s-]", "", name).strip().lower()
        safe = re.sub(r"[-\s]+", "_", safe)
        return safe or "world"

    def get_unique_folder_name(self, base_name: str) -> str:
        """Generate a unique folder name in the saves directory."""
        slug = self.sanitize_folder_name(base_name)
        folder = slug
        counter = 1
        while os.path.exists(os.path.join(self.saves_dir, folder)):
            folder = f"{slug}_{counter}"
            counter += 1
        return folder

    def list_worlds(self) -> List[Dict[str, Any]]:
        """List all saved worlds sorted by last played time (newest first)."""
        worlds = []
        if not os.path.exists(self.saves_dir):
            return worlds

        for entry in os.listdir(self.saves_dir):
            world_dir = os.path.join(self.saves_dir, entry)
            save_file = os.path.join(world_dir, "world.npz")
            meta_file = os.path.join(world_dir, "meta.json")
            if not os.path.isdir(world_dir):
                continue
            if not os.path.exists(save_file) and not os.path.exists(meta_file):
                continue

            mtime = os.path.getmtime(save_file) if os.path.exists(save_file) else os.path.getmtime(meta_file)
            meta = {
                "id": entry,
                "folder": entry,
                "name": entry.replace("_", " ").title(),
                "mode": "survival",
                "preset": "standard",
                "seed": 1,
                "last_played": mtime,
                "save_path": save_file,
            }

            if os.path.exists(meta_file):
                try:
                    with open(meta_file, "r", encoding="utf-8") as f:
                        loaded_meta = json.load(f)
                    if isinstance(loaded_meta, dict):
                        meta.update(loaded_meta)
                        meta["id"] = entry
                        meta["folder"] = entry
                        meta["save_path"] = save_file
                except Exception:
                    pass

            worlds.append(meta)

        worlds.sort(key=lambda w: w.get("last_played", 0.0), reverse=True)
        return worlds

    def get_world_metadata(self, folder_or_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve metadata for a specific world by folder name or id."""
        world_dir = os.path.join(self.saves_dir, folder_or_id)
        if not os.path.isdir(world_dir):
            return None
        meta_file = os.path.join(world_dir, "meta.json")
        save_file = os.path.join(world_dir, "world.npz")
        meta = {
            "id": folder_or_id,
            "folder": folder_or_id,
            "name": folder_or_id.replace("_", " ").title(),
            "mode": "survival",
            "preset": "standard",
            "seed": 1,
            "last_played": time.time(),
            "save_path": save_file,
        }
        if os.path.exists(meta_file):
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    meta.update(loaded)
                    meta["id"] = folder_or_id
                    meta["folder"] = folder_or_id
                    meta["save_path"] = save_file
            except Exception:
                pass
        return meta

    def create_world(self, name: str, mode: str = "survival", seed: Any = 1, preset: str = "standard"):
        """Create a new world directory and metadata, returning (world_id, world_dir)."""
        from generator import parse_seed
        seed_val = parse_seed(seed)
        meta = self.create_world_entry(name, mode, str(preset), seed_val)
        world_dir = os.path.join(self.saves_dir, meta["folder"])
        return meta["folder"], world_dir

    def load_world(self, folder_or_id: str):
        """Load world voxels and snapshot dict for a saved world."""
        from world import World
        world_dir = os.path.join(self.saves_dir, folder_or_id)
        save_file = os.path.join(world_dir, "world.npz")
        if os.path.exists(save_file):
            return World.load(save_file)
        meta = self.get_world_metadata(folder_or_id) or {}
        seed = meta.get("seed", 1)
        preset = meta.get("preset", "standard")
        return World(seed=seed, preset=preset), {}

    def create_world_entry(self, name: str, mode: str, preset: str, seed: int) -> Dict[str, Any]:
        """Create metadata and directory for a new world."""
        folder = self.get_unique_folder_name(name)
        world_dir = os.path.join(self.saves_dir, folder)
        os.makedirs(world_dir, exist_ok=True)
        save_path = os.path.join(world_dir, "world.npz")

        meta = {
            "folder": folder,
            "name": name,
            "mode": mode,
            "preset": preset,
            "seed": seed,
            "last_played": time.time(),
            "save_path": save_path,
        }
        self.save_metadata(folder, meta)
        return meta

    def save_metadata(self, folder: str, meta: Dict[str, Any]) -> None:
        """Write meta.json for a world."""
        world_dir = os.path.join(self.saves_dir, folder)
        meta_file = os.path.join(world_dir, "meta.json")
        try:
            with open(meta_file, "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except OSError:
            pass

    def delete_world(self, folder: str) -> bool:
        """Delete a world directory and all its files."""
        world_dir = os.path.join(self.saves_dir, folder)
        if os.path.exists(world_dir) and os.path.isdir(world_dir):
            try:
                shutil.rmtree(world_dir)
                return True
            except OSError:
                return False
        return False

    def migrate_legacy_save(self, legacy_save_path: str) -> Optional[Dict[str, Any]]:
        """Migrate single legacy world.npz to saves/default_world/."""
        if not os.path.exists(legacy_save_path):
            return None

        dest_folder = "default_world"
        world_dir = os.path.join(self.saves_dir, dest_folder)
        dest_save = os.path.join(world_dir, "world.npz")

        if not os.path.exists(dest_save):
            os.makedirs(world_dir, exist_ok=True)
            try:
                shutil.copy2(legacy_save_path, dest_save)
            except OSError:
                return None

            meta = {
                "folder": dest_folder,
                "name": "Default World",
                "mode": "survival",
                "preset": "standard",
                "seed": 1,
                "last_played": os.path.getmtime(dest_save),
                "save_path": dest_save,
            }
            self.save_metadata(dest_folder, meta)
            return meta
        return None
