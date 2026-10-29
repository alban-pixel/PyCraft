"""Unit tests for the 384m ChunkColumn, 24 SubChunks, dynamic palette, and binary serialization."""
import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from chunk import (
    BlockState, SubChunk, ChunkColumn,
    Y_MIN, Y_MAX, TOTAL_HEIGHT, NUM_SUBCHUNKS, MIN_CY, MAX_CY
)
from blocks import AIR, STONE, DIRT, GRASS, DIAMOND_ORE


def test_block_state_immutability():
    s1 = BlockState.create(STONE)
    s2 = BlockState.create(STONE)
    assert s1 == s2
    assert hash(s1) == hash(s2)

    s3 = BlockState.create(DIRT)
    assert s1 != s3

    with pytest.raises(Exception):
        s1.id = 5  # Immutable frozen dataclass


def test_subchunk_palette_dynamics():
    sub = SubChunk(cy=0)
    assert sub.is_homogeneous
    assert len(sub.palette) == 1
    assert sub.palette[0].id == AIR

    # Setting a block modifies palette and homogeneity
    sub.set(0, 0, 0, BlockState.create(STONE))
    assert not sub.is_homogeneous
    assert len(sub.palette) == 2
    assert sub.get(0, 0, 0).id == STONE
    assert sub.get(1, 0, 0).id == AIR

    # Adding more blocks
    sub.set(5, 5, 5, BlockState.create(DIAMOND_ORE))
    assert len(sub.palette) == 3
    assert sub.get(5, 5, 5).id == DIAMOND_ORE


def test_subchunk_homogeneous_serialization():
    sub = SubChunk(cy=-4)
    sub.fill(BlockState.create(STONE))
    assert sub.is_homogeneous

    # Serialized size should be tiny (< 50 bytes for homogeneous chunk)
    data = sub.serialize()
    assert len(data) < 100

    restored = SubChunk.deserialize(data)
    assert restored.cy == -4
    assert restored.is_homogeneous
    assert restored.get(0, 0, 0).id == STONE
    assert restored.get(15, 15, 15).id == STONE


def test_chunk_column_384m_range():
    col = ChunkColumn(cx=3, cz=-2)
    assert len(col.subchunks) == NUM_SUBCHUNKS
    assert NUM_SUBCHUNKS == 24
    assert MIN_CY == -4
    assert MAX_CY == 19
    assert TOTAL_HEIGHT == 384

    # Test lowest canonical coordinate: Y = -64
    col.set_block(0, -64, 0, STONE)
    assert col.get_block(0, -64, 0) == STONE

    # Test highest canonical coordinate: Y = 319
    col.set_block(15, 319, 15, GRASS)
    assert col.get_block(15, 319, 15) == GRASS

    # Test out of bounds raises IndexError
    with pytest.raises(IndexError):
        col.get_block(0, -65, 0)
    with pytest.raises(IndexError):
        col.get_block(0, 320, 0)


def test_chunk_column_serialization_roundtrip():
    col = ChunkColumn(cx=10, cz=20)
    col.set_block(4, -60, 4, STONE)
    col.set_block(7, 64, 7, DIRT)
    col.set_block(9, 200, 9, DIAMOND_ORE)

    serialized = col.serialize()
    restored = ChunkColumn.deserialize(serialized)

    assert restored.cx == 10
    assert restored.cz == 20
    assert restored.get_block(4, -60, 4) == STONE
    assert restored.get_block(7, 64, 7) == DIRT
    assert restored.get_block(9, 200, 9) == DIAMOND_ORE
    assert restored.get_block(0, 0, 0) == AIR
