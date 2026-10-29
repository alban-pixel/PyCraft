"""Multi-version system architecture for PyCraft.

Defines version metadata, feature toggles, height limits, and combat mechanics
across Minecraft milestones (1.8 The Bountiful Update, 1.12, 1.16 Nether Update, 1.18 Caves & Cliffs).
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass(frozen=True)
class VersionCapabilities:
    """Feature capabilities associated with a specific Minecraft release target."""
    version_id: str
    display_name: str
    protocol_version: int
    height_range: Tuple[int, int]  # (min_y, max_y)
    combat_style: str  # "1.8_spam_click" or "1.9_attack_cooldown"
    has_offhand: bool
    has_elytra: bool
    has_netherite: bool
    has_dual_wielding: bool
    has_caves_and_cliffs_terrain: bool


# Canonical Version Targets
MC_1_8_9 = "1.8.9"
MC_1_12_2 = "1.12.2"
MC_1_16_5 = "1.16.5"
MC_1_18_2 = "1.18.2"

# Current baseline version target
CURRENT_VERSION = MC_1_8_9

VERSION_REGISTRY: Dict[str, VersionCapabilities] = {
    MC_1_8_9: VersionCapabilities(
        version_id=MC_1_8_9,
        display_name="Minecraft 1.8.9 (The Bountiful Update)",
        protocol_version=47,
        height_range=(0, 256),
        combat_style="1.8_spam_click",
        has_offhand=False,
        has_elytra=False,
        has_netherite=False,
        has_dual_wielding=False,
        has_caves_and_cliffs_terrain=False,
    ),
    MC_1_12_2: VersionCapabilities(
        version_id=MC_1_12_2,
        display_name="Minecraft 1.12.2 (World of Color Update)",
        protocol_version=340,
        height_range=(0, 256),
        combat_style="1.9_attack_cooldown",
        has_offhand=True,
        has_elytra=True,
        has_netherite=False,
        has_dual_wielding=True,
        has_caves_and_cliffs_terrain=False,
    ),
    MC_1_16_5: VersionCapabilities(
        version_id=MC_1_16_5,
        display_name="Minecraft 1.16.5 (The Nether Update)",
        protocol_version=754,
        height_range=(0, 256),
        combat_style="1.9_attack_cooldown",
        has_offhand=True,
        has_elytra=True,
        has_netherite=True,
        has_dual_wielding=True,
        has_caves_and_cliffs_terrain=False,
    ),
    MC_1_18_2: VersionCapabilities(
        version_id=MC_1_18_2,
        display_name="Minecraft 1.18.2 (Caves & Cliffs Part II)",
        protocol_version=758,
        height_range=(-64, 320),
        combat_style="1.9_attack_cooldown",
        has_offhand=True,
        has_elytra=True,
        has_netherite=True,
        has_dual_wielding=True,
        has_caves_and_cliffs_terrain=True,
    ),
}


class VersionManager:
    """Manages active game version and capability queries."""

    def __init__(self, active_version: str = CURRENT_VERSION):
        self.active_version = active_version if active_version in VERSION_REGISTRY else CURRENT_VERSION

    @property
    def capabilities(self) -> VersionCapabilities:
        return VERSION_REGISTRY[self.active_version]

    def set_version(self, version_id: str) -> bool:
        if version_id in VERSION_REGISTRY:
            self.active_version = version_id
            return True
        return False

    def get_height_range(self) -> Tuple[int, int]:
        return self.capabilities.height_range

    def get_world_height(self) -> int:
        min_y, max_y = self.capabilities.height_range
        return max_y - min_y

    def is_1_8_combat(self) -> bool:
        return self.capabilities.combat_style == "1.8_spam_click"

    def has_offhand(self) -> bool:
        return self.capabilities.has_offhand

    def has_elytra(self) -> bool:
        return self.capabilities.has_elytra

    def has_netherite(self) -> bool:
        return self.capabilities.has_netherite

    def list_available_versions(self) -> list[str]:
        return list(VERSION_REGISTRY.keys())
