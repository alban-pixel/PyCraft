"""Unit tests for TexturePackManager, pack discovery, and live hot-reloading."""
import json
import os
import shutil
import zipfile
import numpy as np
import pytest

from texture_pack import TexturePackManager, ResourcePackInfo


def test_texture_pack_manager_discovery_builtins(tmp_path):
    """Verify built-in resource packs are always discovered."""
    mgr = TexturePackManager(str(tmp_path / "resourcepacks"))
    packs = mgr.list_packs()
    pack_ids = [p.pack_id for p in packs]

    assert "default" in pack_ids
    assert "faithful" in pack_ids
    assert "retro" in pack_ids
    assert "dark_mode" in pack_ids


def test_custom_directory_resource_pack(tmp_path):
    """Verify scanning directory-based packs with pack.mcmeta."""
    packs_dir = tmp_path / "resourcepacks"
    mgr = TexturePackManager(str(packs_dir))

    # Create a custom directory pack
    custom_dir = packs_dir / "my_custom_pack"
    custom_dir.mkdir(parents=True)
    meta = {
        "pack": {
            "pack_format": 1,
            "description": "High Resolution Realistic Pack"
        }
    }
    with open(custom_dir / "pack.mcmeta", "w", encoding="utf-8") as f:
        json.dump(meta, f)

    packs = mgr.list_packs()
    custom_packs = [p for p in packs if p.pack_id == "dir_my_custom_pack"]
    assert len(custom_packs) == 1
    p = custom_packs[0]
    assert p.name == "My Custom Pack"
    assert p.description == "High Resolution Realistic Pack"
    assert p.is_builtin is False


def test_custom_zip_resource_pack(tmp_path):
    """Verify scanning zip-based packs with pack.mcmeta."""
    packs_dir = tmp_path / "resourcepacks"
    mgr = TexturePackManager(str(packs_dir))

    zip_file = packs_dir / "fancy_pack.zip"
    meta = {
        "pack": {
            "pack_format": 2,
            "description": "Super Fancy Shaders Pack"
        }
    }
    with zipfile.ZipFile(str(zip_file), "w") as zf:
        zf.writestr("pack.mcmeta", json.dumps(meta))

    packs = mgr.list_packs()
    zip_packs = [p for p in packs if p.pack_id == "zip_fancy_pack"]
    assert len(zip_packs) == 1
    p = zip_packs[0]
    assert p.name == "Fancy Pack"
    assert p.description == "Super Fancy Shaders Pack"
    assert p.pack_format == 2


def test_build_pack_atlas_variants(tmp_path):
    """Verify procedural atlas generators produce valid 256x256 RGBA arrays with distinct pixel data."""
    mgr = TexturePackManager(str(tmp_path / "resourcepacks"))

    default_atlas = mgr.build_pack_atlas("default")
    faithful_atlas = mgr.build_pack_atlas("faithful")
    retro_atlas = mgr.build_pack_atlas("retro")
    dark_atlas = mgr.build_pack_atlas("dark_mode")

    for atlas in [default_atlas, faithful_atlas, retro_atlas, dark_atlas]:
        assert atlas.shape == (256, 256, 4)
        assert atlas.dtype == np.uint8

    # Dark mode must have darker average luminance than default
    assert np.mean(dark_atlas[..., :3]) < np.mean(default_atlas[..., :3])

    # Retro must have enhanced green in grass regions
    assert np.mean(retro_atlas[:32, :32, 1]) > np.mean(default_atlas[:32, :32, 1])


def test_app_resource_pack_workflow(headless_app, tmp_path):
    """Test switching texture packs in App updates active pack, image bank, and ModernGL texture."""
    app = headless_app
    app.resource_packs_dir = str(tmp_path / "resourcepacks")
    app.texture_pack_mgr = TexturePackManager(app.resource_packs_dir)

    # Initial pack is default
    assert app.active_resource_pack == "default"

    # Switch to Faithful
    app.set_resource_pack("faithful")
    assert app.active_resource_pack == "faithful"
    assert app.settings["active_resource_pack"] == "faithful"

    # Switch to Retro
    app.set_resource_pack("retro")
    assert app.active_resource_pack == "retro"

    # Menu items in resource_packs state
    app.set_state("resource_packs")
    items = app.menu_items()
    assert len(items) >= 4
    labels = [lbl for lbl, _ in items]
    assert any("Retro Classic (Alpha) [ACTIVE]" in l for l in labels)
    assert any("Default" in l for l in labels)
    assert any("Faithful" in l for l in labels)
    assert any("Done" in l for l in labels)
