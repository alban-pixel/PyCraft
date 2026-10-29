"""Unit tests for multi-version architecture and release tools."""
import os
import subprocess
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

from version import (
    CURRENT_VERSION, MC_1_8_9, MC_1_12_2, MC_1_16_5, MC_1_18_2,
    VERSION_REGISTRY, VersionManager,
)


def test_version_registry_capabilities():
    """Verify registry has correct metadata and capabilities for all milestone versions."""
    assert CURRENT_VERSION == MC_1_8_9

    v18 = VERSION_REGISTRY[MC_1_8_9]
    assert v18.height_range == (0, 256)
    assert v18.combat_style == "1.8_spam_click"
    assert v18.has_offhand is False
    assert v18.has_elytra is False
    assert v18.has_netherite is False

    v112 = VERSION_REGISTRY[MC_1_12_2]
    assert v112.combat_style == "1.9_attack_cooldown"
    assert v112.has_offhand is True
    assert v112.has_elytra is True

    v116 = VERSION_REGISTRY[MC_1_16_5]
    assert v116.has_netherite is True

    v118 = VERSION_REGISTRY[MC_1_18_2]
    assert v118.height_range == (-64, 320)
    assert v118.has_caves_and_cliffs_terrain is True


def test_version_manager_query_and_switching():
    """Verify VersionManager correctly answers capability queries and switches versions."""
    vm = VersionManager(MC_1_8_9)
    assert vm.get_world_height() == 256
    assert vm.is_1_8_combat() is True
    assert vm.has_offhand() is False

    # Switch to 1.18
    assert vm.set_version(MC_1_18_2) is True
    assert vm.get_world_height() == 384
    assert vm.get_height_range() == (-64, 320)
    assert vm.is_1_8_combat() is False
    assert vm.has_offhand() is True
    assert vm.has_elytra() is True

    # Invalid version doesn't switch
    assert vm.set_version("non_existent_version") is False
    assert vm.active_version == MC_1_18_2


def test_release_script_cli_list():
    """Verify scripts/release.py runs with --list without errors."""
    script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts", "release.py"))
    res = subprocess.run(
        [sys.executable, script_path, "--list"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert res.returncode == 0
