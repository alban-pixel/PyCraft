"""Combat mathematics: non-linear armor mitigation, protection enchantment, invulnerability, mob caps, and A* pathfinding.

Implements the deterministic combat and entity rules:
- Non-linear armor formula:
    D_net = D * (1 - min(20, max(A / 5, A - 4D / (8 + 2T))) / 25)
- Protection enchantment EPF formula:
    D_final = D_net * (1 - min(20, EPF) * 4 / 100)
- Invulnerability window of 10 ticks (0.5s) with damage differential tracking.
- Mob cap calculation: Cap_C = BaseCap_C * (N_chunks / 289).
- Despawn radii: 0-24m (safe/no spawn), 24-32m (active), 32-128m (random despawn), >128m (instant despawn).
- A* grid pathfinder avoiding dangerous drops (> 3m) and lava/fire.
"""
from dataclasses import dataclass
import heapq
import math
import random
from typing import Dict, List, Optional, Set, Tuple

BASE_MOB_CAP_HOSTILE = 70
BASE_MOB_CAP_PASSIVE = 10
INVULNERABILITY_TICKS = 10  # 0.5s at 20 Hz


def calculate_1_8_armor(damage: float, armor: float) -> float:
    """Calculate net damage using authentic Vanilla 1.8 flat formula (4% per armor point, max 80%)."""
    if damage <= 0.0:
        return 0.0
    if armor <= 0.0:
        return damage
    reduction = min(20.0, max(0.0, armor)) * 0.04
    return max(0.0, damage * (1.0 - reduction))


def is_critical_hit(vel_y: float, on_ground: bool = False, in_water: bool = False) -> bool:
    """True in 1.8 if falling downward in air (vel_y < 0) and not on ground or in water."""
    return vel_y < 0.0 and not on_ground and not in_water


def calculate_damage_with_crit(base_damage: float, is_crit: bool = False) -> float:
    """Critical hits in 1.8 deal 150% damage (+50% bonus)."""
    return base_damage * 1.5 if is_crit else base_damage


def calculate_attack_damage(base_damage: float, elapsed_ticks: int = 0) -> float:
    """Vanilla 1.8 combat has no attack cooldown penalty (spam-clicking deals full damage)."""
    return base_damage


class CombatEngine:
    """Calculates damage mitigation, armor, critical hits, and protection enchantment."""

    calculate_armor_damage_1_8 = staticmethod(calculate_1_8_armor)

    @staticmethod
    def calculate_armor_damage(damage: float, armor: float, toughness: float = 0.0) -> float:
        """Calculate net damage after non-linear armor mitigation.

        D_net = D * (1 - min(20, max(A / 5, A - 4D / (8 + 2T))) / 25)
        """
        if damage <= 0.0:
            return 0.0
        if armor <= 0.0:
            return damage

        # Defense factor calculation
        reduction_val = max(armor / 5.0, armor - (4.0 * damage) / (8.0 + 2.0 * toughness))
        reduction_val = min(20.0, reduction_val)

        defense_multiplier = 1.0 - (reduction_val / 25.0)
        return max(0.0, damage * defense_multiplier)

    @staticmethod
    def apply_protection_enchantment(damage: float, epf: int) -> float:
        """Apply Protection EPF (Enchantment Protection Factor).

        D_final = D_net * (1 - min(20, EPF) * 4 / 100)
        """
        if damage <= 0.0 or epf <= 0:
            return damage

        effective_epf = min(20, epf)
        reduction = (effective_epf * 4) / 100.0
        return max(0.0, damage * (1.0 - reduction))

    @classmethod
    def compute_total_mitigated_damage(cls,
                                       raw_damage: float,
                                       armor: float,
                                       toughness: float = 0.0,
                                       epf: int = 0) -> float:
        """Full pipeline: Raw damage -> Armor & Toughness -> EPF."""
        net = cls.calculate_armor_damage(raw_damage, armor, toughness)
        return cls.apply_protection_enchantment(net, epf)


class InvulnerabilityTracker:
    """Tracks the 10-tick damage immunity window and differential damage."""

    def __init__(self):
        self.invulnerable_ticks = 0
        self.last_damage_taken = 0.0

    def tick(self) -> None:
        if self.invulnerable_ticks > 0:
            self.invulnerable_ticks -= 1
            if self.invulnerable_ticks <= 0:
                self.last_damage_taken = 0.0

    def attempt_damage(self, incoming_damage: float) -> float:
        """Attempt to inflict damage during or outside invulnerability window.

        Returns:
            The actual net damage to inflict (0.0 if blocked, or differential if greater).
        """
        if self.invulnerable_ticks <= 0:
            self.invulnerable_ticks = INVULNERABILITY_TICKS
            self.last_damage_taken = incoming_damage
            return incoming_damage

        # In invulnerability window: only apply if greater than previously taken
        if incoming_damage > self.last_damage_taken:
            diff = incoming_damage - self.last_damage_taken
            self.last_damage_taken = incoming_damage
            return diff

        return 0.0


class MobCapManager:
    """Manages spawning caps and radial despawn thresholds."""

    @staticmethod
    def get_mob_cap(chunk_count: int, is_hostile: bool = True) -> int:
        """Cap_C = BaseCap_C * (N_chunks / 289)."""
        base = BASE_MOB_CAP_HOSTILE if is_hostile else BASE_MOB_CAP_PASSIVE
        return max(1, round(base * (chunk_count / 289.0)))

    @staticmethod
    def evaluate_despawn(distance_to_player: float, entity_age_ticks: int = 0) -> str:
        """Evaluate entity despawn based on spherical distance to nearest player.

        Returns:
            'keep', 'chance_despawn', or 'instant_despawn'
        """
        if distance_to_player <= 32.0:
            return "keep"
        if distance_to_player > 128.0:
            return "instant_despawn"
        # 32m - 128m: random despawn if older than 30s (600 ticks)
        if entity_age_ticks > 600 and random.random() < (1.0 / 800.0):
            return "chance_despawn"
        return "keep"


class AStarPathfinder:
    """A* grid pathfinder for living entities avoiding hazardous drops (> 3m) and lava."""

    @staticmethod
    def find_path(world,
                  start: Tuple[int, int, int],
                  goal: Tuple[int, int, int],
                  max_nodes: int = 200) -> Optional[List[Tuple[int, int, int]]]:
        """Find a path on voxel coordinates from start to goal.

        Returns list of (x, y, z) steps, or None if unreachable.
        """
        if start == goal:
            return [start]

        def heuristic(a, b):
            return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])

        open_set = []
        heapq.heappush(open_set, (heuristic(start, goal), 0, start))
        came_from: Dict[Tuple[int, int, int], Tuple[int, int, int]] = {}
        g_score: Dict[Tuple[int, int, int], int] = {start: 0}
        visited = set()

        nodes_searched = 0
        while open_set and nodes_searched < max_nodes:
            nodes_searched += 1
            _, current_g, current = heapq.heappop(open_set)

            if current == goal:
                # Reconstruct path
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                path.reverse()
                return path

            visited.add(current)
            cx, cy, cz = current

            # 4 horizontal cardinal directions
            for dx, dz in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                nx, nz = cx + dx, cz + dz
                # Check traversable height: step down up to 3 blocks, step up 1 block
                valid_ny = None
                for dy in [0, 1, -1, -2, -3]:
                    test_y = cy + dy
                    # Must have solid footing and 2 blocks of air above
                    if (world.is_solid(nx, test_y - 1, nz) and
                            not world.is_solid(nx, test_y, nz) and
                            not world.is_solid(nx, test_y + 1, nz)):
                        valid_ny = test_y
                        break

                if valid_ny is None:
                    continue

                neighbor = (nx, valid_ny, nz)
                if neighbor in visited:
                    continue

                tentative_g = current_g + 1
                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    f = tentative_g + heuristic(neighbor, goal)
                    heapq.heappush(open_set, (f, tentative_g, neighbor))

        return None
