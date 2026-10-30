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
    app.set_resource_pack("default")
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


def test_custom_directory_resource_pack_compilation(tmp_path):
    """Verify Minecraft resource pack directory with blocks/*.png compiles to atlas."""
    from PIL import Image

    packs_dir = tmp_path / "resourcepacks"
    mgr = TexturePackManager(str(packs_dir))

    pack_dir = packs_dir / "ocd_style_pack"
    pack_dir.mkdir(parents=True)
    with open(pack_dir / "pack.mcmeta", "w", encoding="utf-8") as f:
        json.dump({"pack": {"pack_format": 1, "description": "OCD Blocks"}}, f)

    # Add 64x64 pack icon (which must NOT become the whole atlas)
    icon = Image.new("RGBA", (64, 64), (128, 0, 128, 255))
    icon.save(pack_dir / "pack.png")

    blocks_dir = pack_dir / "assets" / "minecraft" / "textures" / "blocks"
    blocks_dir.mkdir(parents=True)

    # Add custom dirt texture (pure green for testing distinction)
    dirt_img = Image.new("RGBA", (16, 16), (42, 210, 42, 255))
    dirt_img.save(blocks_dir / "dirt.png")

    # Add animated water texture (16x64 strip)
    water_anim = Image.new("RGBA", (16, 64), (10, 20, 200, 255))
    # Make top 16x16 frame distinguishable
    water_top = Image.new("RGBA", (16, 16), (50, 100, 250, 255))
    water_anim.paste(water_top, (0, 0))
    water_anim.save(blocks_dir / "water_still.png")

    packs = mgr.list_packs()
    custom_pack = next(p for p in packs if "ocd_style_pack" in p.pack_id)
    atlas = mgr.build_pack_atlas(custom_pack.pack_id)

    assert atlas.shape == (256, 256, 4)
    # Dirt tile is tile 2 (x=32..48, y=0..16)
    dirt_tile = atlas[0:16, 32:48]
    assert np.all(dirt_tile[..., 0] == 42)
    assert np.all(dirt_tile[..., 1] == 210)
    assert np.all(dirt_tile[..., 2] == 42)

    # Water tile is tile 12 (x=192..208, y=0..16)
    water_tile = atlas[0:16, 192:208]
    assert np.all(water_tile[..., 0] == 50)
    assert np.all(water_tile[..., 2] == 250)


def test_custom_zip_resource_pack_compilation(tmp_path):
    """Verify Minecraft resource pack .zip with individual block PNGs compiles to atlas."""
    from PIL import Image
    import io

    packs_dir = tmp_path / "resourcepacks"
    mgr = TexturePackManager(str(packs_dir))

    zip_path = packs_dir / "test_zip_pack.zip"
    with zipfile.ZipFile(str(zip_path), "w") as zf:
        zf.writestr("pack.mcmeta", json.dumps({"pack": {"pack_format": 1, "description": "Zip Pack"}}))

        # Pack icon
        icon_buf = io.BytesIO()
        Image.new("RGBA", (64, 64), (200, 100, 50, 255)).save(icon_buf, format="PNG")
        zf.writestr("pack.png", icon_buf.getvalue())

        # Stone block PNG (16x16 bright cyan)
        stone_buf = io.BytesIO()
        Image.new("RGBA", (16, 16), (0, 255, 255, 255)).save(stone_buf, format="PNG")
        zf.writestr("assets/minecraft/textures/blocks/stone.png", stone_buf.getvalue())

    packs = mgr.list_packs()
    custom_zip = next(p for p in packs if "test_zip_pack" in p.pack_id)
    atlas = mgr.build_pack_atlas(custom_zip.pack_id)

    assert atlas.shape == (256, 256, 4)
    # Stone tile is tile 3 (x=48..64, y=0..16)
    stone_tile = atlas[0:16, 48:64]
    assert np.all(stone_tile[..., 0] == 0)
    assert np.all(stone_tile[..., 1] == 255)
    assert np.all(stone_tile[..., 2] == 255)


def test_pack_icon_only_does_not_override_atlas(tmp_path):
    """A resource pack containing ONLY pack.png must not replace the 256x256 atlas."""
    from PIL import Image

    packs_dir = tmp_path / "resourcepacks"
    mgr = TexturePackManager(str(packs_dir))

    pack_dir = packs_dir / "icon_only_pack"
    pack_dir.mkdir(parents=True)
    with open(pack_dir / "pack.mcmeta", "w", encoding="utf-8") as f:
        json.dump({"pack": {"pack_format": 1, "description": "Icon Only"}}, f)

    icon = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
    icon.save(pack_dir / "pack.png")

    packs = mgr.list_packs()
    custom_pack = next(p for p in packs if "icon_only_pack" in p.pack_id)
    atlas = mgr.build_pack_atlas(custom_pack.pack_id)

    # Must fall back to default procedural atlas, NOT a 256x256 red square
    default_atlas = mgr.build_pack_atlas("default")
    assert np.array_equal(atlas, default_atlas)


def test_minecraft_1_8_stone_and_dye_aliases(tmp_path):
    """Verify standard 1.8 stone prefixes and dye aliases are recognized."""
    import io
    from PIL import Image
    from texture_pack import T_GRANITE, T_DIORITE, T_ANDESITE, T_LAPIS_ITEM

    packs_dir = tmp_path / "resourcepacks"
    mgr = TexturePackManager(str(packs_dir))
    zip_path = packs_dir / "pack_1_8.zip"

    with zipfile.ZipFile(str(zip_path), "w") as zf:
        zf.writestr("pack.mcmeta", json.dumps({"pack": {"pack_format": 1, "description": "1.8 Pack"}}))
        for filename, col in [
            ("assets/minecraft/textures/blocks/stone_granite.png", (200, 100, 100, 255)),
            ("assets/minecraft/textures/blocks/stone_diorite.png", (220, 220, 220, 255)),
            ("assets/minecraft/textures/blocks/stone_andesite.png", (140, 140, 140, 255)),
            ("assets/minecraft/textures/items/dye_powder_blue.png", (30, 30, 200, 255)),
        ]:
            buf = io.BytesIO()
            Image.new("RGBA", (16, 16), col).save(buf, format="PNG")
            zf.writestr(filename, buf.getvalue())

    atlas = mgr.build_pack_atlas("zip_pack_1_8")
    assert atlas is not None

    for tid, expected_rgb in [
        (T_GRANITE, (200, 100, 100)),
        (T_DIORITE, (220, 220, 220)),
        (T_ANDESITE, (140, 140, 140)),
        (T_LAPIS_ITEM, (30, 30, 200)),
    ]:
        tx = (tid % 16) * 16
        ty = (tid // 16) * 16
        tile = atlas[ty:ty+16, tx:tx+16]
        assert np.all(tile[..., 0] == expected_rgb[0])
        assert np.all(tile[..., 1] == expected_rgb[1])
        assert np.all(tile[..., 2] == expected_rgb[2])


def test_chest_entity_normal_extraction(tmp_path):
    """Verify chest front, side, and top are extracted from entity/chest/normal.png."""
    import io
    from PIL import Image
    from texture_pack import T_CHEST_FRONT, T_CHEST_SIDE, T_CHEST_TOP

    packs_dir = tmp_path / "resourcepacks"
    mgr = TexturePackManager(str(packs_dir))
    zip_path = packs_dir / "chest_pack.zip"

    # Create a 64x64 chest entity texture with distinct pattern
    chest_img = Image.new("RGBA", (64, 64), (10, 20, 30, 255))
    with zipfile.ZipFile(str(zip_path), "w") as zf:
        zf.writestr("pack.mcmeta", json.dumps({"pack": {"pack_format": 1, "description": "Chest Pack"}}))
        buf = io.BytesIO()
        chest_img.save(buf, format="PNG")
        zf.writestr("assets/minecraft/textures/entity/chest/normal.png", buf.getvalue())

    atlas = mgr.build_pack_atlas("zip_chest_pack")
    def_atlas = mgr.build_pack_atlas("default")

    # Front, side, and top should be updated from the normal.png model
    for tid in [T_CHEST_FRONT, T_CHEST_SIDE, T_CHEST_TOP]:
        tx = (tid % 16) * 16
        ty = (tid // 16) * 16
        tile = atlas[ty:ty+16, tx:tx+16]
        def_tile = def_atlas[ty:ty+16, tx:tx+16]
        assert not np.array_equal(tile, def_tile)

