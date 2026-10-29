"""Unit tests for Distant Horizons / Voxy inspired seamless LOD terrain rendering."""
import numpy as np
import pytest

from blocks import AIR, BEDROCK, DIRT, GRASS, SAND, SNOW, STONE, WATER
from lod import CHUNK, LODChunkBuilder, LODManager, make_quad
from world import World


def test_world_column_height_and_surface_type():
    world = World(size=(64, 64, 64), generate=False)
    # Put a stone column at (10, 10) up to height 25, dirt at 26, grass at 27
    for y in range(26):
        world.set(10, y, 10, STONE)
    world.set(10, 26, 10, DIRT)
    world.set(10, 27, 10, GRASS)

    h = world.get_column_height(10, 10)
    assert h == 28
    b_type = world.get_surface_block_type(10, h, 10)
    assert b_type == GRASS


def test_lod_chunk_builder_lod1():
    world = World(size=(64, 64, 64), generate=False)
    # Populate chunk (0, 0)
    for x in range(16):
        for z in range(16):
            world.set(x, 15, z, GRASS)

    verts = LODChunkBuilder.build_chunk_lod1(world, 0, 0)
    assert verts is not None
    assert verts.ndim == 2
    assert verts.shape[1] == 7  # (pos: 3, uv: 2, shade: 1, kind: 1)

    # Check that vertex positions stay strictly within chunk X and Z bounds [0, 16]
    xs = verts[:, 0]
    zs = verts[:, 2]
    assert np.min(xs) >= 0.0
    assert np.max(xs) <= 16.0
    assert np.min(zs) >= 0.0
    assert np.max(zs) <= 16.0


def test_lod_chunk_builder_lod2():
    world = World(size=(64, 64, 64), generate=False)
    for x in range(16):
        for z in range(16):
            world.set(x + 32, 20, z + 32, SNOW)

    verts = LODChunkBuilder.build_chunk_lod2(world, 2, 2)
    assert verts is not None
    assert verts.ndim == 2
    assert verts.shape[1] == 7

    # Check footprint for chunk (2, 2) -> [32, 48]
    xs = verts[:, 0]
    zs = verts[:, 2]
    assert np.min(xs) == 32.0
    assert np.max(xs) == 48.0
    assert np.min(zs) == 32.0
    assert np.max(zs) == 48.0


def test_seamless_boundary_alignment():
    """Verify that adjacent chunk boundaries align on the exact mathematical grid plane."""
    world = World(size=(64, 64, 64), generate=False)
    # Chunk (0, 0) boundary X=16
    verts_0 = LODChunkBuilder.build_chunk_lod1(world, 0, 0)
    # Chunk (1, 0) boundary X=16
    verts_1 = LODChunkBuilder.build_chunk_lod1(world, 1, 0)

    assert verts_0 is not None and verts_1 is not None
    # Maximum X in chunk (0, 0) must be exactly 16.0
    assert np.max(verts_0[:, 0]) == 16.0
    # Minimum X in chunk (1, 0) must be exactly 16.0
    assert np.min(verts_1[:, 0]) == 16.0
    # Boundary touches with 0.0 distance
    assert np.min(verts_1[:, 0]) - np.max(verts_0[:, 0]) == 0.0


def test_lod_manager_streaming_and_render(headless_app):
    """Verify LODManager creates, streams, and renders distant chunks without errors."""
    app = headless_app
    renderer = app.renderer
    assert hasattr(renderer, "lod")

    lod_mgr = renderer.lod
    near_chunks = {(0, 0), (1, 0), (0, 1), (1, 1)}

    # Update LODs around player at (8, 8)
    lod_mgr.update(8.0, 8.0, near_chunks, render_dist=2, max_lod_dist=6)

    # Chunks in near_chunks must NOT be in LOD keys
    for k in near_chunks:
        assert k not in lod_mgr.active_lod_keys

    # Distant chunks must be populated
    assert len(lod_mgr.active_lod_keys) > 0
    assert lod_mgr.vertex_count > 0

    # Rendering LODs must succeed with unified depth buffer
    with renderer.ctx:
        renderer.fbo.use()
        lod_mgr.render()


def test_smooth_ambient_occlusion_vertex_shading(headless_app):
    """Verify that block corners have smooth AO applied."""
    app = headless_app
    renderer = app.renderer
    world = app.world

    # Rebuild chunk (0, 0)
    renderer._build_chunk(0, 0)
    chunk = renderer.chunks.get((0, 0))
    assert chunk is not None
    vbo, vao = chunk

    # Read vertex data from VBO
    raw_bytes = vbo.read()
    verts = np.frombuffer(raw_bytes, dtype=np.float32).reshape(-1, 7)
    shades = verts[:, 5]  # index 5 is in_shade

    # With AO enabled, shades vary between occluded corners and open faces
    unique_shades = np.unique(np.round(shades, 2))
    assert len(unique_shades) >= 3
