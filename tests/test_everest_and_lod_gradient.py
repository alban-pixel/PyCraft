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

    # Build Level 3 (8x8 quadrants)
    verts_lod3 = LODChunkBuilder.build_chunk_lod3(world, 0, 0)
    assert verts_lod3 is not None
    # 2x2 = 4 quadrants -> at least 4 quads * 6 vertices = 24 vertices
    assert len(verts_lod3) >= 24
    # Clean hierarchy: LOD 1 > LOD 2 > LOD 3 >= 24 vertices
    assert len(verts_lod1) > len(verts_lod2) > len(verts_lod3)


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


def test_lod_transition_seams_watertight():
    """Verify that adjacent chunks of different LOD tiers form a watertight seam without vertical gaps."""
    world = World(seed=42, generate=False)

    # LOD 1 chunk at (0, 0) adjacent to LOD 2 chunk at (1, 0)
    verts_lod1 = LODChunkBuilder.build_chunk_lod1(world, 0, 0)
    verts_lod2 = LODChunkBuilder.build_chunk_lod2(world, 1, 0)
    assert verts_lod1 is not None and verts_lod2 is not None

    seam_x = 16.0
    tol = 1e-4

    # Extract seam vertices
    seam1 = verts_lod1[np.abs(verts_lod1[:, 0] - seam_x) < tol]
    seam2 = verts_lod2[np.abs(verts_lod2[:, 0] - seam_x) < tol]
    assert len(seam1) > 0, "LOD 1 must have skirt vertices on outer eastern boundary"
    assert len(seam2) > 0, "LOD 2 must have skirt vertices on outer western boundary"

    h_lod1_min_y = np.min(seam1[:, 1])
    h_lod2_min_y = np.min(seam2[:, 1])
    h_lod1_max_y = np.max(seam1[:, 1])
    h_lod2_max_y = np.max(seam2[:, 1])

    # The skirts must overlap vertically guaranteeing no transparent slits or see-through cracks
    assert max(h_lod1_min_y, h_lod2_min_y) <= min(h_lod1_max_y, h_lod2_max_y)

    # Also test LOD 2 at (1, 0) adjacent to LOD 3 at (2, 0)
    verts_lod3 = LODChunkBuilder.build_chunk_lod3(world, 2, 0)
    assert verts_lod3 is not None
    seam_x2 = 32.0
    seam2_east = verts_lod2[np.abs(verts_lod2[:, 0] - seam_x2) < tol]
    seam3_west = verts_lod3[np.abs(verts_lod3[:, 0] - seam_x2) < tol]
    assert len(seam2_east) > 0
    assert len(seam3_west) > 0
    assert max(np.min(seam2_east[:, 1]), np.min(seam3_west[:, 1])) <= min(np.max(seam2_east[:, 1]), np.max(seam3_west[:, 1]))


def test_lod3_quadrant_slope_and_coast():
    """Verify LOD 3 uses 8x8 quadrants to capture mountain slopes and coastlines without flat monolithic slab bug."""
    world = World(seed=1337, generate=False)

    # In steep mountain terrain, find a chunk with height gradient
    found_gradient = False
    for cx in range(10, 30):
        for cz in range(10, 30):
            verts = LODChunkBuilder.build_chunk_lod3(world, cx, cz)
            assert verts is not None
            ys = verts[:, 1]
            if np.max(ys) - np.min(ys) >= 4.0:
                found_gradient = True
                break
        if found_gradient:
            break
    assert found_gradient, "LOD 3 should produce stepped quadrants on mountain terrain"


def test_lod_manager_anti_double_rendering_and_stale_update(headless_app):
    """Verify near chunks are excluded from LOD rendering and near_chunks changes trigger rebuilds."""
    app = headless_app
    renderer = app.renderer
    lod_mgr = renderer.lod

    near_chunks = {(0, 0), (1, 0), (0, 1), (1, 1)}
    lod_mgr.update(8.0, 8.0, near_chunks, render_dist=2, max_lod_dist=6)
    initial_keys = set(lod_mgr.active_lod_keys)

    # Ensure none of the near chunks are in active_lod_keys
    for c in near_chunks:
        assert c not in initial_keys

    # Chunk (3, 0) is at distance 3 > r_near (2) so it is initially in active LODs
    assert (3, 0) in initial_keys

    # Simulate streaming in near chunk (3, 0) while player stands still at (8.0, 8.0)
    extended_near = near_chunks | {(3, 0)}
    lod_mgr.update(8.0, 8.0, extended_near, render_dist=2, max_lod_dist=6)

    # Chunk (3, 0) must now be removed from active LODs
    assert (3, 0) not in lod_mgr.active_lod_keys
    assert lod_mgr.active_lod_keys != initial_keys

