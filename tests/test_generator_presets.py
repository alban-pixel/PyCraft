"""Unit tests for the procedural terrain generator, 5D climate vector, and presets."""
import os
import sys
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu")))

from generator import (
    ProceduralGenerator, WorldPreset, ClimateSample, parse_seed, SEA_LEVEL
)
from blocks import AIR, BEDROCK, DIRT, GRASS, STONE, SAND, SNOW, WATER, COAL_ORE


def test_seed_parsing():
    s1 = parse_seed(12345)
    assert s1 == 12345

    s2 = parse_seed("MinecraftSeed2026")
    assert isinstance(s2, int)
    assert s2 > 0

    s3 = parse_seed("MinecraftSeed2026")
    assert s2 == s3  # Deterministic string seed hash


def test_climate_vector_and_biomes():
    # Cold sample -> snowy_tundra
    cold = ClimateSample(0.0, 0.0, 0.0, -0.8, 0.0)
    assert cold.biome == "snowy_tundra"

    # Ocean sample -> ocean
    ocean = ClimateSample(-0.5, 0.0, 0.0, 0.0, 0.0)
    assert ocean.biome == "ocean"

    # Hot and dry -> desert
    desert = ClimateSample(0.1, 0.0, 0.0, 0.8, -0.6)
    assert desert.biome == "desert"


def test_superflat_preset():
    gen = ProceduralGenerator(seed=42, preset=WorldPreset.SUPERFLAT)
    col = gen.generate_column_blocks(cx=0, cz=0, height=64)

    # Layer 0: Bedrock
    assert np.all(col[:, 0, :] == BEDROCK)
    # Layer 1-2: Dirt
    assert np.all(col[:, 1:3, :] == DIRT)
    # Layer 3: Grass
    assert np.all(col[:, 3, :] == GRASS)
    # Above: Air
    assert np.all(col[:, 4:, :] == AIR)


def test_amplified_preset_heights():
    gen_std = ProceduralGenerator(seed=999, preset=WorldPreset.STANDARD)
    gen_amp = ProceduralGenerator(seed=999, preset=WorldPreset.AMPLIFIED)

    # Amplified terrain density should extend to higher Y values than standard
    d_std = gen_std.evaluate_density(100.0, 110.0, 100.0)
    d_amp = gen_amp.evaluate_density(100.0, 110.0, 100.0)
    assert d_amp > d_std


def test_caves_only_preset():
    gen = ProceduralGenerator(seed=123, preset=WorldPreset.CAVES_ONLY)
    col = gen.generate_column_blocks(cx=0, cz=0, height=64)

    # In caves only, bedrock at 0
    assert np.all(col[:, 0, :] == BEDROCK)
    # Stone present in bulk
    assert np.sum(col == STONE) > 1000
    # Air tunnels carved inside
    assert np.sum(col[1:15, 10:50, 1:15] == AIR) > 50
