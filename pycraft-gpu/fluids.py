"""Cellular automata for fluids: Water & Lava discrete levels (0-7), slope routing, infinite sources, and reactions.

Implements deterministic Minecraft fluid physics:
- Discrete levels: Level 0 (source), 1-7 (flowing).
- Water spreads up to 7 blocks horizontally; Lava spreads up to 3 blocks in Overworld.
- Manhattan shortest-path slope search (radius 4) to prioritize drop holes.
- Fluid dissipation / receding when sources are removed or cutoff.
- Infinite water source creation (2 adjacent level 0 sources with solid block beneath).
- Hydrothermal reactions:
    - Water meets Lava source (level 0) -> Obsidian.
    - Water meets Flowing Lava (level > 0) -> Cobblestone.
    - Lava meets Water source/flowing -> Stone.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from blocks import (
    AIR, COBBLESTONE, OBSIDIAN, STONE, WATER,
)

try:
    from blocks import LAVA
except ImportError:
    LAVA = 23

WATER_MAX_SPREAD = 7
LAVA_MAX_SPREAD = 3
SLOPE_SEARCH_RADIUS = 4
MAX_CELLS_PER_TICK = 500


@dataclass(slots=True)
class FluidVoxel:
    fluid_type: int  # WATER or LAVA
    level: int       # 0 = source, 1..7 = flowing
    falling: bool = False


class FluidAutomata:
    """Deterministic cellular automata simulating fluid levels, dissipation, and reactions."""

    def __init__(self, world):
        self.world = world
        self.fluid_voxels: Dict[Tuple[int, int, int], FluidVoxel] = {}
        self.active_cells: Set[Tuple[int, int, int]] = set()

    def get_level(self, x: int, y: int, z: int) -> int:
        voxel = self.fluid_voxels.get((x, y, z))
        return voxel.level if voxel is not None else 0

    def add_fluid(self, x: int, y: int, z: int, fluid_type: int, level: int = 0, falling: bool = False) -> None:
        """Register a fluid block (e.g. newly placed source or existing block)."""
        self.fluid_voxels[(x, y, z)] = FluidVoxel(fluid_type=fluid_type, level=level, falling=falling)
        self.active_cells.add((x, y, z))
        self._wake_neighbors(x, y, z)

    def remove_fluid(self, x: int, y: int, z: int) -> None:
        """Remove a fluid block and wake surrounding cells for receding/dissipation."""
        self.fluid_voxels.pop((x, y, z), None)
        self._wake_neighbors(x, y, z)

    def trigger_cell(self, x: int, y: int, z: int) -> None:
        """Wake up a specific cell and its immediate neighbors."""
        self.active_cells.add((x, y, z))
        self._wake_neighbors(x, y, z)

    def _wake_neighbors(self, x: int, y: int, z: int) -> None:
        for dx, dy, dz in [(0, 0, 0), (0, 1, 0), (0, -1, 0), (1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1)]:
            nx, ny, nz = x + dx, y + dy, z + dz
            if self.world.inside(nx, ny, nz):
                self.active_cells.add((nx, ny, nz))

    def check_hydrothermal_reaction(self, x: int, y: int, z: int) -> Optional[int]:
        """Check if water and lava meet at (x, y, z). Returns the transformed block or None."""
        curr_b = self.world.get(x, y, z)
        neighbors = [
            (x + 1, y, z), (x - 1, y, z),
            (x, y + 1, z), (x, y - 1, z),
            (x, y, z + 1), (x, y, z - 1)
        ]

        if curr_b == WATER:
            for nx, ny, nz in neighbors:
                if self.world.inside(nx, ny, nz) and self.world.get(nx, ny, nz) == LAVA:
                    voxel = self.fluid_voxels.get((nx, ny, nz))
                    is_source = (voxel is None or voxel.level == 0)
                    return OBSIDIAN if is_source else COBBLESTONE

        elif curr_b == LAVA:
            voxel = self.fluid_voxels.get((x, y, z))
            is_source = (voxel is None or voxel.level == 0)
            for nx, ny, nz in neighbors:
                if self.world.inside(nx, ny, nz) and self.world.get(nx, ny, nz) == WATER:
                    return OBSIDIAN if is_source else COBBLESTONE

        return None

    def _compute_target_level(self, x: int, y: int, z: int, fluid_type: int) -> Optional[Tuple[int, bool]]:
        """Compute the flowing level and falling flag for (x, y, z). Returns None if it should dissipate."""
        # 1. Downward flow from block above
        if self.world.inside(x, y + 1, z) and self.world.get(x, y + 1, z) == fluid_type:
            return (1, True)

        # 2. Horizontal flow from 4 neighbors
        min_level = 999
        max_spread = WATER_MAX_SPREAD if fluid_type == WATER else LAVA_MAX_SPREAD
        for dx, dz in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
            nx, nz = x + dx, z + dz
            if self.world.inside(nx, y, nz) and self.world.get(nx, y, nz) == fluid_type:
                v = self.fluid_voxels.get((nx, y, nz))
                lvl = v.level if v is not None else 0
                if lvl < max_spread and lvl < min_level:
                    min_level = lvl

        if min_level < max_spread:
            return (min_level + 1, False)
        return None

    def _find_flow_directions(self, x: int, y: int, z: int, fluid_type: int) -> List[Tuple[int, int]]:
        """Find horizontal directions (dx, dz) to spread using slope routing (Manhattan search radius 4)."""
        cardinals = [(1, 0), (-1, 0), (0, 1), (0, -1)]
        valid_dirs = []
        for dx, dz in cardinals:
            nx, nz = x + dx, z + dz
            if self.world.inside(nx, y, nz):
                b = self.world.get(nx, y, nz)
                if b == AIR:
                    valid_dirs.append((dx, dz))
                elif b == fluid_type:
                    curr_lvl = self.get_level(x, y, z)
                    target_lvl = curr_lvl + 1
                    if self.get_level(nx, y, nz) > target_lvl:
                        valid_dirs.append((dx, dz))
        if not valid_dirs:
            return []

        # Slope detection: search for a drop (open space beneath) within Manhattan radius 4
        dir_dist = {}
        for dx, dz in valid_dirs:
            queue = [(x + dx, z + dz, 1)]
            visited = {(x, z), (x + dx, z + dz)}
            min_dist = 999
            while queue:
                cx, cz, dist = queue.pop(0)
                # If there's an opening below at y - 1, water will naturally fall
                if y > 1 and self.world.inside(cx, y - 1, cz) and self.world.get(cx, y - 1, cz) in (AIR, fluid_type):
                    min_dist = dist
                    break
                if dist < SLOPE_SEARCH_RADIUS:
                    for ddx, ddz in cardinals:
                        nx, nz = cx + ddx, cz + ddz
                        if (nx, nz) not in visited and self.world.inside(nx, y, nz):
                            visited.add((nx, nz))
                            nb = self.world.get(nx, y, nz)
                            if nb in (AIR, fluid_type):
                                queue.append((nx, nz, dist + 1))
            dir_dist[(dx, dz)] = min_dist

        min_found = min(dir_dist.values())
        if min_found <= SLOPE_SEARCH_RADIUS:
            return [d for d, dist in dir_dist.items() if dist == min_found]
        return valid_dirs

    def tick(self) -> Set[Tuple[int, int]]:
        """Simulate one step of fluid cellular automata. Returns set of modified (cx, cz) chunks."""
        if not self.active_cells:
            return set()

        # Limit processed cells per tick to prevent frame spikes
        cells_to_process = list(self.active_cells)[:MAX_CELLS_PER_TICK]
        for c in cells_to_process:
            self.active_cells.discard(c)

        modified_chunks = set()

        for x, y, z in cells_to_process:
            if not self.world.inside(x, y, z):
                continue

            # 1. Hydrothermal reactions
            reaction = self.check_hydrothermal_reaction(x, y, z)
            if reaction is not None:
                self.world.set(x, y, z, reaction)
                self.remove_fluid(x, y, z)
                modified_chunks.add((x // 16, z // 16))
                continue

            curr_b = self.world.get(x, y, z)

            # 2. Check infinite water source creation:
            # If current block is AIR or flowing water (level > 0), and underneath is SOLID, and has >= 2 adjacent WATER sources
            voxel = self.fluid_voxels.get((x, y, z))
            is_flowing = (curr_b == WATER and voxel is not None and voxel.level > 0)
            if (curr_b == AIR or is_flowing) and self.world.is_solid(x, y - 1, z):
                adjacent_sources = 0
                for dx, dz in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    nx, nz = x + dx, z + dz
                    if self.world.inside(nx, y, nz) and self.world.get(nx, y, nz) == WATER:
                        v = self.fluid_voxels.get((nx, y, nz))
                        if v is None or v.level == 0:
                            adjacent_sources += 1
                if adjacent_sources >= 2:
                    self.world.set(x, y, z, WATER)
                    self.add_fluid(x, y, z, WATER, level=0)
                    modified_chunks.add((x // 16, z // 16))
                    continue

            # 3. Flowing fluid recalculation & dissipation
            if curr_b in (WATER, LAVA):
                if voxel is None:
                    voxel = FluidVoxel(fluid_type=curr_b, level=0)
                    self.fluid_voxels[(x, y, z)] = voxel

                # Non-source fluids must have an active parent feed, otherwise they dissipate
                if voxel.level > 0:
                    target_state = self._compute_target_level(x, y, z, curr_b)
                    if target_state is None:
                        # Dissipate into AIR
                        self.world.set(x, y, z, AIR)
                        self.remove_fluid(x, y, z)
                        modified_chunks.add((x // 16, z // 16))
                        continue
                    else:
                        new_lvl, new_falling = target_state
                        if new_lvl != voxel.level or new_falling != voxel.falling:
                            voxel.level = new_lvl
                            voxel.falling = new_falling
                            self._wake_neighbors(x, y, z)

                # 4. Downward flow priority
                if y > 1 and self.world.get(x, y - 1, z) == AIR:
                    self.world.set(x, y - 1, z, curr_b)
                    self.fluid_voxels[(x, y - 1, z)] = FluidVoxel(fluid_type=curr_b, level=1, falling=True)
                    self.active_cells.add((x, y - 1, z))
                    modified_chunks.add((x // 16, z // 16))
                    continue

                # 5. Horizontal flow if downward is blocked or solid
                max_level = WATER_MAX_SPREAD if curr_b == WATER else LAVA_MAX_SPREAD
                if voxel.level < max_level:
                    dirs = self._find_flow_directions(x, y, z, curr_b)
                    for dx, dz in dirs:
                        nx, nz = x + dx, z + dz
                        if self.world.inside(nx, y, nz):
                            spread_lvl = voxel.level + 1
                            target_b = self.world.get(nx, y, nz)
                            if target_b == AIR or (target_b == curr_b and self.get_level(nx, y, nz) > spread_lvl):
                                self.world.set(nx, y, nz, curr_b)
                                self.fluid_voxels[(nx, y, nz)] = FluidVoxel(fluid_type=curr_b, level=spread_lvl)
                                self.active_cells.add((nx, y, nz))
                                modified_chunks.add((nx // 16, nz // 16))

        return modified_chunks
