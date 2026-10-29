"""Player metabolism, hunger, saturation, exhaustion, and polynomial experience system.

Implements the deterministic physiological engine:
- Triple gauge coupling: Health (20 HP), Hunger (20 units), Saturation (0..20), Exhaustion (0..4.0).
- Exhaustion accumulation:
    Walk: +0.0/m, Sprint: +0.1/m, Jump: +0.05, Sprint-Jump: +0.20,
    Mine Block: +0.005, Attack: +0.10, Heal 1 HP: +6.0.
- Exhaustion threshold: when E >= 4.0 -> deducts 1 from saturation (or hunger), E -= 4.0.
- Regenerations:
    Saturated regen (Hunger=20, Sat>0): +1 HP every 10 ticks (0.5s).
    Standard regen (Hunger>=18): +1 HP every 80 ticks (4.0s).
- Sprint disabled when Hunger <= 6.
- Starvation damage: 1 HP every 80 ticks when Hunger == 0.
- Nutritional foods table with food level and saturation points.
- 3-tier polynomial experience system (Levels 0-15, 16-30, 31+).
"""
from dataclasses import dataclass
import math
from typing import Dict, Tuple

EXHAUSTION_SPRINT_PER_M = 0.10
EXHAUSTION_JUMP = 0.05
EXHAUSTION_SPRINT_JUMP = 0.20
EXHAUSTION_MINE = 0.005
EXHAUSTION_ATTACK = 0.10
EXHAUSTION_HEAL_PER_HP = 6.0

TICKS_SATURATED_REGEN = 10  # 0.5s at 20 Hz
TICKS_STANDARD_REGEN = 80   # 4.0s at 20 Hz
TICKS_STARVATION = 80       # 4.0s at 20 Hz


@dataclass(frozen=True, slots=True)
class FoodItem:
    food: int
    saturation: float


# Nutritional food table
FOOD_PROPERTIES: Dict[int, FoodItem] = {
    109: FoodItem(food=3, saturation=1.8),   # ITEM_RAW_PORK
    110: FoodItem(food=8, saturation=12.8),  # ITEM_COOKED_PORK
    111: FoodItem(food=4, saturation=2.4),   # Apple
    112: FoodItem(food=5, saturation=6.0),   # Bread
    113: FoodItem(food=6, saturation=14.4),  # Golden Carrot
    114: FoodItem(food=4, saturation=9.6),   # Golden Apple
    115: FoodItem(food=4, saturation=0.8),   # Rotten Flesh
    # 1.8 Food items
    120: FoodItem(food=2, saturation=1.2),   # ITEM_RAW_MUTTON
    121: FoodItem(food=6, saturation=9.6),   # ITEM_COOKED_MUTTON
    122: FoodItem(food=3, saturation=1.8),   # ITEM_RAW_RABBIT
    123: FoodItem(food=5, saturation=6.0),   # ITEM_COOKED_RABBIT
    124: FoodItem(food=10, saturation=12.0), # ITEM_RABBIT_STEW
}


class Metabolism:
    """Manages player physiological health, hunger, saturation, exhaustion, and experience."""

    def __init__(self, max_health: int = 20):
        self.max_health = max_health
        self.health = max_health
        self.max_food = 20
        self.food = 20
        self.saturation = 5.0
        self.exhaustion = 0.0

        # Regeneration / Starvation timers (in ticks)
        self.regen_timer = 0
        self.starvation_timer = 0

        # Experience
        self.xp_total = 0

    @property
    def can_sprint(self) -> bool:
        """Sprint is disabled when food level is 6 or less."""
        return self.food > 6

    def add_exhaustion(self, amount: float) -> None:
        """Add exhaustion and deplete saturation/food when threshold 4.0 is reached."""
        self.exhaustion += amount
        while self.exhaustion >= 4.0:
            self.exhaustion -= 4.0
            if self.saturation > 0.0:
                self.saturation = max(0.0, self.saturation - 1.0)
            elif self.food > 0:
                self.food = max(0, self.food - 1)

    def eat(self, item_id: int) -> bool:
        """Eat food item if hungry or golden fruit. Returns True if consumed."""
        food_prop = FOOD_PROPERTIES.get(item_id)
        if not food_prop:
            return False

        # Can only eat if hungry (food < 20), except golden apple/carrot
        if self.food >= self.max_food and item_id not in (113, 114):
            return False

        self.food = min(self.max_food, self.food + food_prop.food)
        # Saturation is capped at the current food level
        self.saturation = min(float(self.food), self.saturation + food_prop.saturation)
        return True

    def tick(self, difficulty: str = "normal") -> Tuple[int, int]:
        """Process 1 tick (20 Hz) of metabolism.

        Returns:
            (hp_healed, hp_damaged)
        """
        healed = 0
        damaged = 0

        # 1. Fast Saturated Regeneration
        if self.food == 20 and self.saturation > 0.0 and self.health < self.max_health:
            self.regen_timer += 1
            if self.regen_timer >= TICKS_SATURATED_REGEN:
                self.regen_timer = 0
                self.health = min(self.max_health, self.health + 1)
                self.add_exhaustion(EXHAUSTION_HEAL_PER_HP)
                healed += 1

        # 2. Standard Regeneration
        elif self.food >= 18 and self.health < self.max_health:
            self.regen_timer += 1
            if self.regen_timer >= TICKS_STANDARD_REGEN:
                self.regen_timer = 0
                self.health = min(self.max_health, self.health + 1)
                self.add_exhaustion(EXHAUSTION_HEAL_PER_HP)
                healed += 1
        else:
            self.regen_timer = 0

        # 3. Starvation Damage
        if self.food == 0:
            self.starvation_timer += 1
            if self.starvation_timer >= TICKS_STARVATION:
                self.starvation_timer = 0
                can_damage = True
                if difficulty == "easy" and self.health <= 10:
                    can_damage = False
                elif difficulty == "normal" and self.health <= 1:
                    can_damage = False

                if can_damage:
                    self.health = max(0, self.health - 1)
                    damaged += 1
        else:
            self.starvation_timer = 0

        return healed, damaged

    # -------------------------------------------------------------------------
    # Experience Level Mathematics (3-tier polynomial)
    # -------------------------------------------------------------------------

    @staticmethod
    def get_xp_for_level(level: int) -> int:
        """Return total XP required to reach a given level."""
        if level <= 0:
            return 0
        if level <= 16:
            return level * level + 6 * level
        if level <= 31:
            return int(2.5 * level * level - 40.5 * level + 360)
        return int(4.5 * level * level - 162.5 * level + 2220)

    @staticmethod
    def get_xp_to_next_level(level: int) -> int:
        """Return XP delta required to advance from level to level + 1."""
        if level < 0:
            return 7
        if level <= 15:
            return 2 * level + 7
        if level <= 30:
            return 5 * level - 38
        return 9 * level - 158

    @property
    def level(self) -> int:
        """Current experience level based on total XP."""
        # Find level using analytical root or iterative climb
        lvl = 0
        while self.get_xp_for_level(lvl + 1) <= self.xp_total:
            lvl += 1
        return lvl

    @property
    def level_progress(self) -> float:
        """Fraction of progress [0.0, 1.0) towards the next level."""
        lvl = self.level
        xp_current_lvl = self.get_xp_for_level(lvl)
        xp_next_lvl = self.get_xp_for_level(lvl + 1)
        needed = xp_next_lvl - xp_current_lvl
        if needed <= 0:
            return 0.0
        return max(0.0, min(1.0, (self.xp_total - xp_current_lvl) / float(needed)))

    def add_xp(self, amount: int) -> int:
        """Add XP points. Returns the new level."""
        if amount > 0:
            self.xp_total += amount
        return self.level
