"""Tests for extended chunk vertical height (Y=-64..512) and Everest mountain generation."""
import math
import pytest
from chunk import (
    CHUNK_SIZE, CHUNK_SUBCHUNKS, CHUNK_Y_MAX, CHUNK_Y_MIN,
    DEFAULT_SUBCHUNKS, ChunkColumn, SubChunk, serialize_subchunk
)
from generator import WorldPreset
from world import World
import blocks


def test_chunk_extended_constants():
    assert CHUNK_Y_MIN == -64
    assert CHUNK_Y_MAX == 512
    assert CHUNK_SUBCHUNKS == 36
    assert DEFAULT_SUBCHUNKS == 24


def test_homogeneous_subchunk_serialization_compression():
    sub = SubChunk(cy=0)
    assert sub.is_homogeneous is True
    assert len(sub.palette) == 1
    data = serialize_subchunk(sub)
    assert len(data) < 32


def test_everest_preset_peaks_and_stratification():
    world = World(seed=1337, preset=WorldPreset.EVEREST, generate=False)
    assert world.sy == 512
    assert world.size[1] == 512

    max_peak = max(world.compute_terrain_height(x, z) for x in range(0, 2000, 32) for z in range(0, 2000, 32))
    assert max_peak > 400

    # Altitudinal zoning
    assert world.get_surface_block_type(0, 450, 0) == blocks.SNOW
    assert world.get_surface_block_type(0, 300, 0) == blocks.SNOW
    assert world.get_surface_block_type(0, 150, 0) == blocks.STONE
    assert world.get_surface_block_type(0, 23, 0) == blocks.SAND
    assert world.get_surface_block_type(0, 20, 0) == blocks.WATER
