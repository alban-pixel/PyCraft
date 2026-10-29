"""Deterministic Redstone Logic Engine with Java Edition quasi-connectivity.

Implements canonical Minecraft redstone rules:
- Scalar power potential S in [0, 15] with 1 per block dissipation.
- Strongly powered vs weakly powered blocks.
- Fixed 20 Hz tick mapping: 1 redstone tick = 2 game ticks = 0.10 s.
- Components:
    - Redstone Wire: dissipates by 1 per block.
    - Repeater: 1-4 redstone ticks delay, diode, amplifies to 15, locking latch.
    - Comparator: comparison (A >= B -> A), subtraction (max(0, A - B)), container reading.
    - Observer: 1-tick pulse on block update in front.
    - Piston: 12 block push limit, immovable blocks (Bedrock, Obsidian), Java quasi-connectivity (QC).
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple


class Direction(Enum):
    NORTH = (0, 0, -1)
    SOUTH = (0, 0, 1)
    EAST = (1, 0, 0)
    WEST = (-1, 0, 0)
    UP = (0, 1, 0)
    DOWN = (0, -1, 0)


@dataclass
class RedstoneRepeater:
    direction: Tuple[int, int, int]
    delay_ticks: int = 1  # 1 to 4 redstone ticks (2, 4, 6, 8 game ticks)
    locked: bool = False
    powered: bool = False
    countdown: int = 0


@dataclass
class RedstoneComparator:
    direction: Tuple[int, int, int]
    subtract_mode: bool = False  # False = Compare, True = Subtract
    output_power: int = 0


@dataclass
class RedstoneObserver:
    facing: Tuple[int, int, int]  # Direction it observes
    pulse_countdown: int = 0


@dataclass
class RedstonePiston:
    direction: Tuple[int, int, int]
    extended: bool = False
    is_sticky: bool = False


class RedstoneSimulator:
    """Manages redstone wire networks, signal propagation, and deterministic components."""

    def __init__(self, world):
        self.world = world
        # Wire and component power states: (x, y, z) -> power [0, 15]
        self.signals: Dict[Tuple[int, int, int], int] = {}
        # Strongly powered solid blocks: (x, y, z) -> power [0, 15]
        self.strongly_powered: Dict[Tuple[int, int, int], int] = {}
        # Weakly powered solid blocks: (x, y, z) -> power [0, 15]
        self.weakly_powered: Dict[Tuple[int, int, int], int] = {}

        # Component registries
        self.wires: Set[Tuple[int, int, int]] = set()
        self.repeaters: Dict[Tuple[int, int, int], RedstoneRepeater] = {}
        self.comparators: Dict[Tuple[int, int, int], RedstoneComparator] = {}
        self.observers: Dict[Tuple[int, int, int], RedstoneObserver] = {}
        self.pistons: Dict[Tuple[int, int, int], RedstonePiston] = {}

        # Redstone tick accumulator (1 redstone tick = 2 game ticks)
        self.game_tick_counter = 0

    def get_signal(self, x: int, y: int, z: int) -> int:
        return self.signals.get((x, y, z), 0)

    def set_power_source(self, x: int, y: int, z: int, power: int = 15, strong: bool = True) -> None:
        """Set a permanent or switchable power source (e.g. Redstone Torch, Lever, Block of Redstone)."""
        power = max(0, min(15, power))
        self.signals[(x, y, z)] = power
        if strong:
            self.strongly_powered[(x, y, z)] = power
        else:
            self.weakly_powered[(x, y, z)] = power
        self.propagate()

    def remove_power_source(self, x: int, y: int, z: int) -> None:
        self.signals.pop((x, y, z), None)
        self.strongly_powered.pop((x, y, z), None)
        self.weakly_powered.pop((x, y, z), None)
        self.propagate()

    def add_wire(self, x: int, y: int, z: int) -> None:
        """Register a redstone dust wire position."""
        self.wires.add((x, y, z))

    def add_repeater(self, x: int, y: int, z: int, direction: Tuple[int, int, int], delay_ticks: int = 1) -> None:
        self.repeaters[(x, y, z)] = RedstoneRepeater(direction=direction, delay_ticks=delay_ticks)

    def add_comparator(self, x: int, y: int, z: int, direction: Tuple[int, int, int], subtract_mode: bool = False) -> None:
        self.comparators[(x, y, z)] = RedstoneComparator(direction=direction, subtract_mode=subtract_mode)

    def add_observer(self, x: int, y: int, z: int, facing: Tuple[int, int, int]) -> None:
        self.observers[(x, y, z)] = RedstoneObserver(facing=facing)

    def add_piston(self, x: int, y: int, z: int, direction: Tuple[int, int, int], is_sticky: bool = False) -> None:
        self.pistons[(x, y, z)] = RedstonePiston(direction=direction, is_sticky=is_sticky)

    def propagate(self) -> None:
        """Propagate redstone signals across connected wires with 1-per-meter dissipation."""
        # Find all wire locations (where signals exist or wires are placed)
        # BFS from all sources
        visited: Dict[Tuple[int, int, int], int] = {}
        queue: List[Tuple[Tuple[int, int, int], int]] = []

        # Enqueue all active sources
        for pos, pwr in list(self.strongly_powered.items()) + list(self.weakly_powered.items()):
            if pwr > 0:
                visited[pos] = pwr
                queue.append((pos, pwr))

        # Also repeater outputs
        for (rx, ry, rz), rep in self.repeaters.items():
            if rep.powered:
                out_pos = (rx + rep.direction[0], ry, rz + rep.direction[2])
                visited[out_pos] = 15
                queue.append((out_pos, 15))

        # Also comparator outputs
        for (cx, cy, cz), comp in self.comparators.items():
            if comp.output_power > 0:
                out_pos = (cx + comp.direction[0], cy, cz + comp.direction[2])
                visited[out_pos] = comp.output_power
                queue.append((out_pos, comp.output_power))

        # Also observer outputs
        for (ox, oy, oz), obs in self.observers.items():
            if obs.pulse_countdown > 0:
                # Output is on rear (opposite of facing)
                rear_pos = (ox - obs.facing[0], oy - obs.facing[1], oz - obs.facing[2])
                visited[rear_pos] = 15
                queue.append((rear_pos, 15))

        # 3D Wire Propagation with 1 loss per block (diode components do not conduct reverse signal)
        diode_positions = set(self.repeaters.keys()) | set(self.comparators.keys())
        valid_destinations = (
            self.wires | diode_positions | set(self.pistons.keys()) | set(self.strongly_powered.keys()) | set(self.weakly_powered.keys())
        ) if self.wires else None

        while queue:
            (x, y, z), pwr = queue.pop(0)
            if pwr <= 1:
                continue

            for dx, dy, dz in [(1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1), (0, 1, 0), (0, -1, 0)]:
                nx, ny, nz = x + dx, y + dy, z + dz
                if (nx, ny, nz) in diode_positions:
                    continue
                if valid_destinations is not None and (nx, ny, nz) not in valid_destinations:
                    continue
                target_pwr = pwr - 1
                if target_pwr > visited.get((nx, ny, nz), 0):
                    visited[(nx, ny, nz)] = target_pwr
                    queue.append(((nx, ny, nz), target_pwr))

        # Update signals dictionary
        self.signals = visited

    def tick_redstone(self) -> None:
        """Step one redstone tick (0.10s = 2 game ticks). Updates repeaters, comparators, and pistons."""
        # 1. Update Observers
        for (ox, oy, oz), obs in self.observers.items():
            if obs.pulse_countdown > 0:
                obs.pulse_countdown -= 1

        # 2. Update Repeaters
        for (rx, ry, rz), rep in self.repeaters.items():
            if rep.locked:
                continue
            # Input comes from behind (opposite of direction)
            in_x = rx - rep.direction[0]
            in_z = rz - rep.direction[2]
            input_power = self.get_signal(in_x, ry, in_z)
            should_power = (input_power > 0)

            if should_power != rep.powered:
                if rep.countdown <= 0:
                    rep.countdown = rep.delay_ticks
                rep.countdown -= 1
                if rep.countdown == 0:
                    rep.powered = should_power
            else:
                rep.countdown = 0

        # 3. Update Comparators
        for (cx, cy, cz), comp in self.comparators.items():
            in_x = cx - comp.direction[0]
            in_z = cz - comp.direction[2]
            input_a = self.get_signal(in_x, cy, in_z)

            # Side inputs (orthogonal to direction)
            side1_x = cx + comp.direction[2]
            side1_z = cz - comp.direction[0]
            side2_x = cx - comp.direction[2]
            side2_z = cz + comp.direction[0]
            side_b = max(self.get_signal(side1_x, cy, side1_z), self.get_signal(side2_x, cy, side2_z))

            if comp.subtract_mode:
                comp.output_power = max(0, input_a - side_b)
            else:
                comp.output_power = input_a if input_a >= side_b else 0

        # 4. Update Pistons with Quasi-Connectivity (QC)
        for (px, py, pz), piston in self.pistons.items():
            # Standard direct power
            direct_power = False
            for dx, dy, dz in [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]:
                if self.get_signal(px + dx, py + dy, pz + dz) > 0:
                    direct_power = True
                    break

            # Quasi-Connectivity: powered if space directly above (py + 1) or diagonal-above is powered
            qc_power = direct_power or (self.get_signal(px, py + 1, pz) > 0) or (self.get_signal(px, py + 2, pz) > 0)

            should_extend = qc_power
            if should_extend and not piston.extended:
                self._extend_piston(px, py, pz, piston)
            elif not should_extend and piston.extended:
                self._retract_piston(px, py, pz, piston)

        # Refresh wire network
        self.propagate()

    def _extend_piston(self, px: int, py: int, pz: int, piston: RedstonePiston) -> bool:
        """Push up to 12 blocks in the piston's direction. Stops on bedrock/obsidian."""
        dx, dy, dz = piston.direction
        blocks_to_push = []

        curr_x, curr_y, curr_z = px + dx, py + dy, pz + dz
        for _ in range(12):
            if not self.world.inside(curr_x, curr_y, curr_z):
                return False
            b = self.world.get(curr_x, curr_y, curr_z)
            if b == 0:  # AIR ends the push chain
                break
            if b in (14, 22):  # BEDROCK (14) or OBSIDIAN (22) cannot be pushed
                return False
            blocks_to_push.append(((curr_x, curr_y, curr_z), b))
            curr_x += dx
            curr_y += dy
            curr_z += dz
        else:
            # 13th block is non-air -> exceeds push limit of 12!
            b = self.world.get(curr_x, curr_y, curr_z)
            if b != 0:
                return False

        # Move blocks from back to front
        for (bx, by, bz), block_id in reversed(blocks_to_push):
            self.world.set(bx + dx, by + dy, bz + dz, block_id)
            self.world.set(bx, by, bz, 0)

        piston.extended = True
        return True

    def _retract_piston(self, px: int, py: int, pz: int, piston: RedstonePiston) -> None:
        """Retract piston arm. If sticky, pulls 1 block back."""
        piston.extended = False
        if piston.is_sticky:
            dx, dy, dz = piston.direction
            # Block 2 steps away is pulled to 1 step away
            target_x, target_y, target_z = px + dx * 2, py + dy * 2, pz + dz * 2
            if self.world.inside(target_x, target_y, target_z):
                b = self.world.get(target_x, target_y, target_z)
                if b not in (0, 14, 22):  # Not AIR, Bedrock, or Obsidian
                    self.world.set(px + dx, py + dy, pz + dz, b)
                    self.world.set(target_x, target_y, target_z, 0)
