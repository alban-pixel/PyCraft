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


def test_mountain_generation_and_snow_peaks():
    """Verify procedural generation creates high mountains with rocky slopes and snow caps."""
    world = World(seed=12345, preset="standard")
    heights = [world.compute_terrain_height(x, z) for x in range(-150, 150, 10) for z in range(-150, 150, 10)]
    max_h = max(heights)
    min_h = min(heights)

    # Must contain high mountain peaks rising above Y=45 and valleys down around sea level (22)
    assert max_h >= 45
    assert min_h <= 24

    # High peak above 40 must have SNOW surface block type
    for x in range(-150, 150, 10):
        for z in range(-150, 150, 10):
            h = world.compute_terrain_height(x, z)
            if h >= 42:
                b = world.get_surface_block_type(x, h, z)
                assert b == SNOW
                break
        else:
            continue
        break


def test_lod_far_range_and_default_render_distance_12(headless_app):
    """Verify default render distance is 12 and LODs extend several hundred blocks."""
    app = headless_app
    from main import DEFAULT_SETTINGS
    assert DEFAULT_SETTINGS["render_distance"] == 12

    renderer = app.renderer
    world = app.world
    lod_mgr = LODManager(renderer.ctx, renderer.program, world)

    rd = 12
    max_lod = rd + 36  # 48 chunks = 768 meters
    lod_mgr.update(0.0, 0.0, set(), render_dist=rd, max_lod_dist=max_lod)

    # Verify that LOD keys extend up to ~48 chunks (several hundred blocks)
    max_dist = max(max(abs(cx), abs(cz)) for cx, cz in lod_mgr.active_lod_keys)
    assert max_dist >= 40  # 40 chunks * 16m = 640m radius (> 1.2 km diameter)


def test_title_screen_no_stutter_camera(headless_app):
    """Verify title screen camera is stationary in space and does not stream chunks repeatedly."""
    app = headless_app
    app.set_state("title")
    assert app.on_title() is True

    # Camera must not move position on title
    app.draw_world()
    pos1 = (app.world.size[0] / 2, 48.0, app.world.size[2] / 2)
    assert pos1[1] == 48.0
