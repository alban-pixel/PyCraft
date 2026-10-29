"""Procedural terrain generation, 5D climate vector, 3D density field, cave carvers, and presets.

Implements the deterministic procedural generation system:
- 5D continuous climate vector: (Continentalness, Erosion, Weirdness, Temperature, Humidity).
- 3D density function D(x, y, z) >= 0 -> solid block, else air.
- Sea level at Y = 63.
- 3D spaghetti cave carvers based on dual-frequency noise thresholding.
- World Presets: Standard, Superflat, Amplified, Floating Islands, Caves Only.
- Deterministic seed evaluation (string or integer).
"""
from dataclasses import dataclass
import hashlib
import math
from typing import Dict, Optional, Tuple

import numpy as np

from blocks import (
    AIR, BEDROCK, COAL_ORE, DIAMOND_ORE, DIRT, GOLD_ORE, GRASS,
    IRON_ORE, LEAVES, LOG, SAND, SNOW, STONE, WATER,
)

SEA_LEVEL = 63


@dataclass(frozen=True, slots=True)
class ClimateSample:
    continentalness: float  # [-1.0, 1.0]: Ocean <-> Inland
    erosion: float          # [-1.0, 1.0]: Flat <-> Mountainous
    weirdness: float        # [-1.0, 1.0]: Rare biome variations
    temperature: float      # [-1.0, 1.0]: Cold <-> Hot
    humidity: float         # [-1.0, 1.0]: Arid <-> Wet

    @property
    def biome(self) -> str:
        """Classify biome from the 5D climate vector."""
        if self.continentalness < -0.2:
            return "ocean"
        if self.temperature < -0.4:
            return "snowy_tundra"
        if self.temperature > 0.5 and self.humidity < -0.3:
            return "desert"
        if self.erosion < -0.4:
            return "mountains"
        if self.humidity > 0.2:
            return "forest"
        return "plains"


class WorldPreset:
    STANDARD = "standard"
    SUPERFLAT = "superflat"
    AMPLIFIED = "amplified"
    FLOATING_ISLANDS = "floating_islands"
    CAVES_ONLY = "caves_only"

    ALL = [STANDARD, SUPERFLAT, AMPLIFIED, FLOATING_ISLANDS, CAVES_ONLY]


def parse_seed(seed_input) -> int:
    """Parse integer or string seed into a deterministic 64-bit integer seed."""
    if isinstance(seed_input, int):
        return seed_input & 0xFFFFFFFF
    if not seed_input:
        return 1
    # Hash string to 32-bit unsigned integer
    digest = hashlib.sha256(str(seed_input).encode("utf-8")).digest()
    return int.from_bytes(digest[:4], byteorder="big")


class ProceduralGenerator:
    """Procedural world generator using 3D multi-octave gradient density fields."""

    def __init__(self, seed: int = 1, preset: str = WorldPreset.STANDARD):
        self.seed = parse_seed(seed)
        self.preset = preset
        self.rng = np.random.default_rng(self.seed)

    def sample_climate(self, x: float, z: float) -> ClimateSample:
        """Sample 5D climate vector at horizontal coordinate (x, z)."""
        s = self.seed
        c = math.sin((x * 0.003 + s * 1.3)) * math.cos(z * 0.003)
        e = math.cos((x * 0.005 - s * 0.7)) * math.sin(z * 0.005)
        w = math.sin((x * 0.008 + z * 0.008 + s * 2.1))
        t = math.cos((x * 0.002 + s * 0.4))
        h = math.sin((z * 0.002 + s * 0.9))
        return ClimateSample(c, e, w, t, h)

    def evaluate_density(self, x: float, y: float, z: float) -> float:
        """Evaluate 3D density function D(x, y, z). D >= 0 -> solid."""
        if self.preset == WorldPreset.SUPERFLAT:
            return 1.0 if y <= 4 else -1.0

        if self.preset == WorldPreset.CAVES_ONLY:
            # Solid world perforated by continuous 3D cave carver
            if y <= 1 or y >= 120:
                return 1.0  # Bedrock / ceiling
            c1 = math.sin(x * 0.08) * math.cos(y * 0.08) * math.sin(z * 0.08)
            c2 = math.cos(x * 0.06 + 1.2) * math.sin(y * 0.06) * math.cos(z * 0.06)
            is_cave = (abs(c1) < 0.25) and (abs(c2) < 0.25)
            return -1.0 if is_cave else 1.0

        if self.preset == WorldPreset.FLOATING_ISLANDS:
            # Islands floating around Y = 60..90
            center_dist = abs(y - 75.0)
            if center_dist > 25.0:
                return -1.0
            n = (math.sin(x * 0.04) + math.cos(z * 0.04)) * 8.0
            island_thickness = 15.0 - (center_dist + n)
            return island_thickness

        # Standard or Amplified terrain
        amp_scale = 2.2 if self.preset == WorldPreset.AMPLIFIED else 1.0
        climate = self.sample_climate(x, z)

        # Baseline height based on continentalness and erosion
        base_h = SEA_LEVEL + 4.0 + (climate.continentalness * 24.0) - (climate.erosion * 16.0)
        base_h = max(10.0, base_h * amp_scale)

        # 3D surface perturbation
        n1 = math.sin(x * 0.03) * math.cos(z * 0.03) * 6.0 * amp_scale
        n2 = math.cos(x * 0.07 + 10.0) * math.sin(z * 0.07 + 10.0) * 3.0
        target_height = base_h + n1 + n2

        density = target_height - y

        # 3D Cave carvers: active below surface
        if y < target_height - 3 and y > 2:
            cave_n1 = math.sin(x * 0.07 + y * 0.05) * math.cos(z * 0.07)
            cave_n2 = math.cos(x * 0.07) * math.sin(z * 0.07 + y * 0.05)
            if abs(cave_n1) < 0.12 and abs(cave_n2) < 0.12:
                density = -1.0  # Carved out cave tunnel

        return density

    def generate_column_blocks(self, cx: int, cz: int, height: int = 128) -> np.ndarray:
        """Generate a 16 x height x 16 numpy array of block IDs for chunk (cx, cz)."""
        voxels = np.zeros((16, height, 16), dtype=np.uint8)
        x0, z0 = cx * 16, cz * 16

        if self.preset == WorldPreset.SUPERFLAT:
            voxels[:, 0, :] = BEDROCK
            voxels[:, 1:3, :] = DIRT
            voxels[:, 3, :] = GRASS
            return voxels

        for lx in range(16):
            wx = x0 + lx
            for lz in range(16):
                wz = z0 + lz
                climate = self.sample_climate(wx, wz)
                surface_y = -1

                for y in range(height - 1, -1, -1):
                    d = self.evaluate_density(wx, y, wz)
                    if d >= 0:
                        if surface_y < 0:
                            surface_y = y
                        # Top layer
                        if y == surface_y:
                            if climate.biome == "desert":
                                voxels[lx, y, lz] = SAND
                            elif climate.biome == "snowy_tundra" or y > 100:
                                voxels[lx, y, lz] = SNOW
                            elif y < SEA_LEVEL + 1:
                                voxels[lx, y, lz] = SAND
                            else:
                                voxels[lx, y, lz] = GRASS
                        elif y > surface_y - 4:
                            voxels[lx, y, lz] = SAND if climate.biome == "desert" else DIRT
                        else:
                            voxels[lx, y, lz] = STONE
                    elif y < SEA_LEVEL and self.preset != WorldPreset.CAVES_ONLY:
                        voxels[lx, y, lz] = WATER
                    else:
                        voxels[lx, y, lz] = AIR

                voxels[lx, 0, lz] = BEDROCK

        # Ore generation in stone
        stone_mask = voxels == STONE
        roll = self.rng.random(voxels.shape)
        voxels[stone_mask & (roll < 0.015)] = COAL_ORE
        voxels[stone_mask & (roll > 0.990)] = IRON_ORE
        voxels[stone_mask & (roll > 0.996)] = GOLD_ORE
        voxels[stone_mask & (roll > 0.9985)] = DIAMOND_ORE

        return voxels
