"""Fabric Mod Loader for discovering and initializing mods."""
from dataclasses import dataclass, field
import importlib
import json
import logging
import os
import sys
from typing import Dict, List, Optional

logger = logging.getLogger("fabric_api.mod_loader")


@dataclass
class ModContainer:
    """Metadata container for an active Fabric mod."""

    id: str
    name: str = ""
    version: str = "1.0.0"
    entrypoints: Dict[str, List[str]] = field(default_factory=dict)
    path: str = ""


class ModLoader:
    """Discovers mods in mods/ directory, parses fabric.mod.json, and runs initializers."""

    def __init__(self) -> None:
        self.loaded_mods: Dict[str, ModContainer] = {}

    def load_mods(self, mods_dir: str) -> None:
        """Scan a directory for mods, parse manifests, and initialize them."""
        if not os.path.isdir(mods_dir):
            return

        for item in sorted(os.listdir(mods_dir)):
            item_path = os.path.join(mods_dir, item)
            if not os.path.isdir(item_path):
                continue

            manifest_path = os.path.join(item_path, "fabric.mod.json")
            if not os.path.isfile(manifest_path):
                continue

            try:
                with open(manifest_path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
            except Exception as e:
                logger.warning("Failed to parse %s: %s", manifest_path, e)
                continue

            if not isinstance(data, dict):
                continue

            mod_id = data.get("id")
            if not mod_id or not isinstance(mod_id, str):
                logger.warning("Skipping %s: missing or invalid 'id' field", manifest_path)
                continue

            name = data.get("name", mod_id)
            version = data.get("version", "1.0.0")
            entrypoints = data.get("entrypoints", {})

            container = ModContainer(
                id=mod_id,
                name=name,
                version=version,
                entrypoints=entrypoints if isinstance(entrypoints, dict) else {},
                path=item_path,
            )
            self.loaded_mods[mod_id] = container

            # Ensure mod path is in sys.path for import resolution
            if item_path not in sys.path:
                sys.path.insert(0, item_path)

            # Process main entrypoints
            for ep_str in container.entrypoints.get("main", []):
                try:
                    if "." in ep_str:
                        mod_name, cls_name = ep_str.rsplit(".", 1)
                        module = importlib.import_module(mod_name)
                        initializer_cls = getattr(module, cls_name)
                        instance = initializer_cls()
                        if hasattr(instance, "on_initialize"):
                            instance.on_initialize()
                except Exception as e:
                    logger.error("Failed to execute entrypoint %s for mod %s: %s", ep_str, mod_id, e)
