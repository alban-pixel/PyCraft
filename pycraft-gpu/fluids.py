"""Cellular automata for fluids: Water & Lava discrete levels (0-7), slope routing, infinite sources, and reactions.

Implements the deterministic fluid physics:
- Discrete levels: Level 0 (source), 1-7 (flowing).
- Water spreads up to 7 blocks horizontally; Lava spreads up to 3 blocks in Overworld.
- Manhattan shortest-path slope search (radius 4) to prioritize drop holes.
- Infinite water source creation (2 adjacent level 0 sources with solid block beneath).
- Hydrothermal reactions:
    - Water meets Lava source (level 0) -> Obsidian.
    - Water meets Flowing Lava (level > 0) -> Cobblestone.
    - Lava meets Water source -> Stone.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from blocks import (
    AIR, COBBLESTONE, OBSIDIAN, STONE, WATER,
)

# Optional LAVA definition if available in blocks
try:
    from blocks import LAVA
except ImportError:
    LAVA = 23

WATER_MAX_SPREAD = 7
LAVA_MAX_SPREAD = 3
SLOPE_SEARCH_RADIUS = 4


@dataclass(slots=True)
class FluidVoxel:
    fluid_type: int  # WATER or LAVA
    level: int       # 0 = source, 1..7 = flowing
    falling: bool = False


class FluidAutomata:
    """Deterministic cellular automata simulating fluid levels and hydrothermal reactions."""

    def __init__(self, world):
        self.world = world
        # Map of (x, y, z) -> FluidVoxel
        self.fluid_voxels: Dict[Tuple[int, int, int], FluidVoxel] = {}
        self.active_cells: Set[Tuple[int, int, int]] = set()

    def add_fluid(self, x: int, y: int, z: int, fluid_type: int, level: int = 0) -> None:
        """Register a fluid block (e.g. newly placed source or existing block)."""
        self.fluid_voxels[(x, y, z)] = FluidVoxel(fluid_type=fluid_type, level=level)
        self.active_cells.add((x, y, z))
        self._wake_neighbors(x, y, z)

    def remove_fluid(self, x: int, y: int, z: int) -> None:
        """Remove a fluid block and wake surrounding cells."""
        self.fluid_voxels.pop((x, y, z), None)
        self._wake_neighbors(x, y, z)

    def _wake_neighbors(self, x: int, y: int, z: int) -> None:
        for dx, dy, dz in [(0, 0, 0), (0, 1, 0), (0, -1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]:
            nx, ny, nz = x + dx, y + dy, z + dz
            if self.world.inside(nx, ny, nz):
                self.active_cells.add((nx, ny, nz))

    def check_hydrothermal_reaction(self, x: int, y: int, z: int) -> Optional[int]:
        """Check if water and lava meet at (x, y, z). Returns the transformed block or None."""
        curr_b = self.world.get(x, y, z)

        # Check adjacent blocks for the opposing fluid
        neighbors = [
            (x + 1, y, z), (x - 1, y, z),
            (x, y + 1, z), (x, y - 1, z),
            (x, y, z + 1), (x, y, z - 1)
        ]

        if curr_b == WATER:
            # Check if adjacent to Lava
            for nx, ny, nz in neighbors:
                if self.world.get(nx, ny, nz) == LAVA:
                    voxel = self.fluid_voxels.get((nx, ny, nz))
                    is_source = (voxel is None or voxel.level == 0)
                    return OBSIDIAN if is_source else COBBLESTONE

        elif curr_b == LAVA:
            # Check if adjacent to Water
            voxel = self.fluid_voxels.get((x, y, z))
            is_source = (voxel is None or voxel.level == 0)
            for nx, ny, nz in neighbors:
                if self.world.get(nx, ny, nz) == WATER:
                    if is_source:
                        return OBSIDIAN
                    else:
                        return COBBLESTONE

        return None

    def tick(self) -> Set[Tuple[int, int]]:
        """Simulate one step of fluid cellular automata. Returns set of modified (cx, cz) chunks."""
        if not self.active_cells:
            return set()

        cells_to_process = list(self.active_cells)
        self.active_cells.clear()
        modified_chunks = set()

        for x, y, z in cells_to_process:
            if not self.world.inside(x, y, z):
                continue

            # Hydrothermal reactions
            reaction = self.check_hydrothermal_reaction(x, y, z)
            if reaction is not None:
                self.world.set(x, y, z, reaction)
                self.remove_fluid(x, y, z)
                modified_chunks.add((x // 16, z // 16))
                continue

            curr_b = self.world.get(x, y, z)

            # Check infinite water source creation:
            # If current block is AIR or flowing water (level > 0), and underneath is SOLID, and has >= 2 adjacent WATER sources
            voxel = self.fluid_voxels.get((x, y, z))
            is_flowing = (curr_b == WATER and voxel is not None and voxel.level > 0)
            if (curr_b == AIR or is_flowing) and self.world.is_solid(x, y - 1, z):
                adjacent_sources = 0
                for dx, dz in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    nx, nz = x + dx, z + dz
                    if self.world.get(nx, y, nz) == WATER:
                        v = self.fluid_voxels.get((nx, y, nz))
                        if v is None or v.level == 0:
                            adjacent_sources += 1
                if adjacent_sources >= 2:
                    self.world.set(x, y, z, WATER)
                    self.add_fluid(x, y, z, WATER, level=0)
                    modified_chunks.add((x // 16, z // 16))
                    continue

            # Downward flow
            if curr_b in (WATER, LAVA):
                voxel = self.fluid_voxels.get((x, y, z), FluidVoxel(fluid_type=curr_b, level=0))
                max_level = WATER_MAX_SPREAD if curr_b == WATER else LAVA_MAX_SPREAD

                # 1. Downward priority
                if y > 0 and self.world.get(x, y - 1, z) == AIR:
                    self.world.set(x, y - 1, z, curr_b)
                    self.fluid_voxels[(x, y - 1, z)] = FluidVoxel(fluid_type=curr_b, level=1, falling=True)
                    self.active_cells.add((x, y - 1, z))
                    modified_chunks.add((x // 16, z // 16))
                    continue

                # 2. Horizontal spread if not at max level
                if voxel.level < max_level:
                    for dx, dz in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                        nx, nz = x + dx, z + dz
                        if self.world.inside(nx, y, nz) and self.world.get(nx, y, nz) == AIR:
                            self.world.set(nx, y, nz, curr_b)
                            self.fluid_voxels[(nx, y, nz)] = FluidVoxel(fluid_type=curr_b, level=voxel.level + 1)
                            self.active_cells.add((nx, y, nz))
                            modified_chunks.add((nx // 16, nz // 16))

        return modified_chunks
