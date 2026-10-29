"""Unit tests verifying Everest-scale mountain heights (sy=256) and the 3-tier hierarchical LOD gradient."""
import numpy as np
import pytest

from blocks import AIR, BEDROCK, DIRT, GRASS, SAND, SNOW, STONE, WATER
from lod import CHUNK, LODChunkBuilder, LODManager
from world import World


def test_world_height_limit_256():
    """Verify default world height is 256 with Y in [0, 256]."""
    world = World(seed=42, generate=False)
    assert world.sy == 256
    assert world.size[1] == 256


def test_everest_scale_mountain_peaks_and_snow_caps():
    """Verify procedural generation creates massive Everest massifs rising to Y > 180."""
    world = World(seed=1337, generate=False)

    # Scan a sample area to find Everest summits
    peak_h = 0
    for x in range(0, 1600, 16):
        for z in range(0, 1600, 16):
            h = world.compute_terrain_height(x, z)
            if h > peak_h:
                peak_h = h

    # Everest peaks must rise high into the sky (above 180, up to ~240)
    assert peak_h >= 180, f"Expected Everest peaks >= 180m, found {peak_h}m"
    assert peak_h < 256

    # Test alpine snow line at high altitudes
    snow_block = world.get_surface_block_type(0, 150, 0)
    assert snow_block == SNOW

    # Test stone slope at mid-high altitude
    stone_block = world.get_surface_block_type(0, 75, 0)
    assert stone_block == STONE

    # Test lowlands grass
    grass_block = world.get_surface_block_type(0, 30, 0)
    assert grass_block == GRASS


def test_lod_gradient_three_tiers():
    """Verify geometry generated for LOD 1 (2x2), LOD 2 (4x4), and LOD 3 (16x16)."""
    world = World(seed=123, generate=False)

    # Build Level 1 (2x2 micro-columns)
    verts_lod1 = LODChunkBuilder.build_chunk_lod1(world, 0, 0)
    assert verts_lod1 is not None
    # 8x8 = 64 sub-cells -> at least 64 quads * 6 vertices = 384 vertices
    assert len(verts_lod1) >= 384

    # Build Level 2 (4x4 sub-cells)
    verts_lod2 = LODChunkBuilder.build_chunk_lod2(world, 0, 0)
    assert verts_lod2 is not None
    # 4x4 = 16 sub-cells -> at least 16 quads * 6 vertices = 96 vertices
    assert len(verts_lod2) >= 96
    # LOD 1 must have more vertices (higher detail) than LOD 2
    assert len(verts_lod1) > len(verts_lod2)

    # Build Level 3 (16x16 macro-box)
    verts_lod3 = LODChunkBuilder.build_chunk_lod3(world, 0, 0)
    assert verts_lod3 is not None
    # 1 quad top + skirts <= 5 quads * 6 vertices = 30 vertices
    assert len(verts_lod3) <= 30
    assert len(verts_lod2) > len(verts_lod3)


def test_lod_gradient_seamless_footprints():
    """Verify that every LOD tier stays strictly inside its chunk boundaries."""
    world = World(seed=999, generate=False)
    cx, cz = 3, 4
    x_min_expected, x_max_expected = cx * CHUNK, (cx + 1) * CHUNK
    z_min_expected, z_max_expected = cz * CHUNK, (cz + 1) * CHUNK

    for builder in [LODChunkBuilder.build_chunk_lod1, LODChunkBuilder.build_chunk_lod2, LODChunkBuilder.build_chunk_lod3]:
        verts = builder(world, cx, cz)
        assert verts is not None
        assert np.min(verts[:, 0]) >= x_min_expected
        assert np.max(verts[:, 0]) <= x_max_expected
        assert np.min(verts[:, 2]) >= z_min_expected
        assert np.max(verts[:, 2]) <= z_max_expected
