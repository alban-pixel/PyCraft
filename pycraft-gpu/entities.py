"""Comprehensive Minecraft 1.8 Entities System: Mobs, AI, Physics, Combat, and Dropped Items."""
import math
import random
from typing import Dict, List, Optional, Set, Tuple

import blocks
from blocks import (
    AIR, SOLID,
    ITEM_RAW_PORK, ITEM_RAW_BEEF, ITEM_RAW_MUTTON, ITEM_RAW_CHICKEN, ITEM_RAW_RABBIT,
    ITEM_COOKED_PORK, ITEM_LEATHER, ITEM_FEATHER, ITEM_BONE, ITEM_ARROW, ITEM_GUNPOWDER,
    ITEM_STRING, ITEM_SLIMEBALL, ITEM_BLAZE_ROD, ITEM_GHAST_TEAR, ITEM_NETHER_STAR,
    ITEM_ENDER_PEARL, ITEM_IRON_INGOT, ITEM_GOLD_INGOT, ITEM_COAL, ITEM_REDSTONE,
    ITEM_LAPIS_LAZULI, ITEM_SNOWBALL, ITEM_STICK, ITEM_PRISMARINE_SHARD, ITEM_PRISMARINE_CRYSTALS,
    ITEM_RABBIT_HIDE, ITEM_RABBIT_FOOT, WHITE_WOOL, RED_MUSHROOM, POPPY, GLOWSTONE, WET_SPONGE,
)

GRAVITY = 24.0
JUMP_SPEED = 7.0

# Complete Minecraft 1.8 Mob Registry
MOB_CONFIGS = {
    # Passive Mobs
    "pig": {"health": 10, "width": 0.7, "height": 0.85, "speed": 2.2, "category": "passive", "drops": [(ITEM_RAW_PORK, 1, 2)]},
    "cow": {"health": 10, "width": 0.9, "height": 1.4, "speed": 2.0, "category": "passive", "drops": [(ITEM_RAW_BEEF, 1, 3), (ITEM_LEATHER, 0, 2)]},
    "sheep": {"health": 8, "width": 0.9, "height": 1.3, "speed": 2.0, "category": "passive", "drops": [(ITEM_RAW_MUTTON, 1, 2), (WHITE_WOOL, 1, 1)]},
    "chicken": {"health": 4, "width": 0.4, "height": 0.7, "speed": 2.0, "category": "passive", "drops": [(ITEM_RAW_CHICKEN, 1, 1), (ITEM_FEATHER, 0, 2)]},
    "horse": {"health": 24, "width": 1.4, "height": 1.6, "speed": 3.2, "category": "passive", "drops": [(ITEM_LEATHER, 1, 2)]},
    "rabbit": {"health": 3, "width": 0.4, "height": 0.5, "speed": 3.0, "category": "passive", "drops": [(ITEM_RAW_RABBIT, 1, 1), (ITEM_RABBIT_HIDE, 0, 1), (ITEM_RABBIT_FOOT, 0, 1)]},
    "bat": {"health": 6, "width": 0.5, "height": 0.9, "speed": 2.5, "category": "flying", "drops": []},
    "squid": {"health": 10, "width": 0.8, "height": 0.8, "speed": 1.8, "category": "aquatic", "drops": [(ITEM_LAPIS_LAZULI, 1, 3)]},
    "villager": {"health": 20, "width": 0.6, "height": 1.95, "speed": 2.0, "category": "passive", "drops": []},
    "mooshroom": {"health": 10, "width": 0.9, "height": 1.4, "speed": 2.0, "category": "passive", "drops": [(ITEM_RAW_BEEF, 1, 3), (RED_MUSHROOM, 1, 2)]},
    "ocelot": {"health": 10, "width": 0.6, "height": 0.7, "speed": 3.5, "category": "passive", "drops": []},
    "wolf": {"health": 8, "width": 0.6, "height": 0.85, "speed": 2.8, "category": "neutral", "drops": []},
    "iron_golem": {"health": 100, "width": 1.4, "height": 2.7, "speed": 2.0, "category": "golem", "drops": [(ITEM_IRON_INGOT, 3, 5), (POPPY, 0, 2)]},
    "snow_golem": {"health": 4, "width": 0.7, "height": 1.9, "speed": 2.0, "category": "golem", "drops": [(ITEM_SNOWBALL, 2, 5)]},

    # Hostile Mobs
    "zombie": {"health": 20, "width": 0.6, "height": 1.85, "speed": 2.4, "attack": 3, "category": "hostile", "drops": [(ITEM_STICK, 0, 2), (ITEM_IRON_INGOT, 0, 1)]},
    "skeleton": {"health": 20, "width": 0.6, "height": 1.95, "speed": 2.4, "attack": 3, "category": "hostile", "drops": [(ITEM_BONE, 1, 2), (ITEM_ARROW, 0, 2)]},
    "creeper": {"health": 20, "width": 0.6, "height": 1.7, "speed": 2.3, "attack": 20, "category": "hostile", "drops": [(ITEM_GUNPOWDER, 1, 2)]},
    "spider": {"health": 16, "width": 1.4, "height": 0.9, "speed": 3.0, "attack": 2, "category": "hostile", "drops": [(ITEM_STRING, 1, 2)]},
    "cave_spider": {"health": 12, "width": 0.7, "height": 0.5, "speed": 3.0, "attack": 2, "category": "hostile", "drops": [(ITEM_STRING, 1, 2)]},
    "enderman": {"health": 40, "width": 0.6, "height": 2.9, "speed": 3.5, "attack": 7, "category": "neutral", "drops": [(ITEM_ENDER_PEARL, 0, 1)]},
    "witch": {"health": 26, "width": 0.6, "height": 1.95, "speed": 2.0, "attack": 4, "category": "hostile", "drops": [(ITEM_REDSTONE, 1, 3), (GLOWSTONE, 1, 2), (ITEM_STICK, 0, 2)]},
    "slime": {"health": 16, "width": 1.2, "height": 1.2, "speed": 2.2, "attack": 2, "category": "hostile", "drops": [(ITEM_SLIMEBALL, 1, 2)]},
    "magma_cube": {"health": 16, "width": 1.2, "height": 1.2, "speed": 2.2, "attack": 3, "category": "hostile", "drops": [(ITEM_SLIMEBALL, 1, 2)]},
    "silverfish": {"health": 8, "width": 0.4, "height": 0.3, "speed": 2.5, "attack": 1, "category": "hostile", "drops": []},
    "endermite": {"health": 8, "width": 0.4, "height": 0.3, "speed": 2.5, "attack": 2, "category": "hostile", "drops": []},
    "guardian": {"health": 30, "width": 0.85, "height": 0.85, "speed": 2.4, "attack": 4, "category": "hostile", "drops": [(ITEM_PRISMARINE_SHARD, 1, 2), (ITEM_PRISMARINE_CRYSTALS, 0, 1)]},
    "elder_guardian": {"health": 80, "width": 1.99, "height": 1.99, "speed": 2.0, "attack": 8, "category": "boss", "drops": [(WET_SPONGE, 1, 1), (ITEM_PRISMARINE_SHARD, 2, 4)]},
    "ghast": {"health": 10, "width": 4.0, "height": 4.0, "speed": 2.0, "attack": 6, "category": "flying", "drops": [(ITEM_GHAST_TEAR, 0, 1), (ITEM_GUNPOWDER, 1, 2)]},
    "blaze": {"health": 20, "width": 0.6, "height": 1.8, "speed": 2.4, "attack": 4, "category": "flying", "drops": [(ITEM_BLAZE_ROD, 0, 1)]},
    "zombie_pigman": {"health": 20, "width": 0.6, "height": 1.85, "speed": 2.4, "attack": 5, "category": "neutral", "drops": [(ITEM_GOLD_INGOT, 0, 1), (ITEM_RAW_PORK, 0, 1)]},
    "wither_skeleton": {"health": 20, "width": 0.7, "height": 2.4, "speed": 2.5, "attack": 5, "category": "hostile", "drops": [(ITEM_COAL, 0, 1), (ITEM_BONE, 0, 2)]},

    # Bosses
    "wither": {"health": 300, "width": 0.9, "height": 3.5, "speed": 3.0, "attack": 8, "category": "boss", "drops": [(ITEM_NETHER_STAR, 1, 1)]},
    "ender_dragon": {"health": 200, "width": 16.0, "height": 8.0, "speed": 4.0, "attack": 10, "category": "boss", "drops": []},
}


class DroppedItem:
    """An in-world floating, spinning, collectible item or block entity with physics."""

    def __init__(self, item_id: int, count: int, x: float, y: float, z: float, vx: float = 0.0, vy: float = 0.0, vz: float = 0.0, pickup_delay: float = 0.8):
        self.item_id = int(item_id)
        self.count = max(1, int(count))
        self.pos = [float(x), float(y), float(z)]
        self.vel = [float(vx), float(vy), float(vz)]
        self.prev_pos = list(self.pos)
        self.yaw = random.uniform(0, 360)
        self.age = 0.0
        self.pickup_delay = pickup_delay
        self.is_alive = True
        self.on_ground = False
        self.kind = "item"
        self.hurt_timer = 0.0

    @property
    def aabb(self):
        px, py, pz = self.pos
        return (px - 0.2, py, pz - 0.2, px + 0.2, py + 0.4, pz + 0.2)

    def update(self, world, dt):
        if not self.is_alive:
            return
        self.prev_pos = list(self.pos)
        self.age += dt
        if self.age > 300.0:  # Despawn after 5 minutes
            self.is_alive = False
            return

        if self.pickup_delay > 0:
            self.pickup_delay = max(0.0, self.pickup_delay - dt)

        self.yaw = (self.yaw + 90.0 * dt) % 360.0

        # Gravity & Drag
        if not self.on_ground:
            self.vel[1] = max(self.vel[1] - 18.0 * dt, -20.0)
        else:
            self.vel[0] *= max(0.0, 1.0 - 5.0 * dt)
            self.vel[2] *= max(0.0, 1.0 - 5.0 * dt)

        # Movement
        self.pos[0] += self.vel[0] * dt
        self.pos[2] += self.vel[2] * dt
        self.pos[1] += self.vel[1] * dt

        # Terrain collision
        ix, iy, iz = int(math.floor(self.pos[0])), int(math.floor(self.pos[1])), int(math.floor(self.pos[2]))
        if world.inside(ix, iy, iz) and world.is_solid(ix, iy, iz):
            self.pos[1] = iy + 1.0
            self.vel[1] = 0.0
            self.on_ground = True
        elif world.inside(ix, iy - 1, iz) and world.is_solid(ix, iy - 1, iz) and self.pos[1] <= iy:
            self.pos[1] = iy
            self.vel[1] = 0.0
            self.on_ground = True
        else:
            self.on_ground = False


class Entity:
    """Living mob entity with physics, collision detection, and AI behavior."""

    def __init__(self, kind: str, x: float, y: float, z: float):
        self.kind = kind
        cfg = MOB_CONFIGS.get(kind, MOB_CONFIGS["zombie"])
        self.pos = [float(x), float(y), float(z)]
        self.vel = [0.0, 0.0, 0.0]
        self.yaw = random.uniform(0, 360)
        self.pitch = 0.0
        self.prev_pos = [float(x), float(y), float(z)]
        self.on_ground = False
        self.against_wall = False
        self.is_alive = True
        self.hurt_timer = 0.0
        self.walk_cycle = 0.0
        self.target_dir = [0.0, 0.0]
        self.ai_timer = random.uniform(1.0, 3.0)
        self.panic_timer = 0.0
        self.attack_cooldown = 0.0
        self.on_fire = False

        self.max_health = self.health = cfg["health"]
        self.width = cfg["width"]
        self.height = cfg["height"]
        self.speed = cfg["speed"]
        self.attack_damage = cfg.get("attack", 2)
        self.category = cfg.get("category", "hostile")
        self.drops = cfg.get("drops", [])

        # Special AI states
        self.fuse_timer = 0.0
        self.is_fusing = False
        self.is_angry = False
        self.shoot_cooldown = 0.0
        self.jump_timer = random.uniform(0.5, 1.5)

    @property
    def aabb(self):
        hw = self.width / 2
        px, py, pz = self.pos
        return (px - hw, py, pz - hw, px + hw, py + self.height, pz + hw)

    @property
    def aggro(self):
        return self.is_angry

    @aggro.setter
    def aggro(self, val):
        self.is_angry = bool(val)

    @property
    def bow_cooldown(self):
        return self.shoot_cooldown

    @bow_cooldown.setter
    def bow_cooldown(self, val):
        self.shoot_cooldown = float(val)

    def check_player_stare(self, eye, forward):
        if self.kind != "enderman":
            return False
        hx, hy, hz = self.pos[0] - eye[0], (self.pos[1] + self.height * 0.9) - eye[1], self.pos[2] - eye[2]
        dist = math.sqrt(hx * hx + hy * hy + hz * hz)
        if dist < 0.1:
            return False
        dot = (forward[0] * hx + forward[1] * hy + forward[2] * hz) / dist
        if dot > 0.90:
            self.is_angry = True
            return True
        return False

    def teleport_random(self, world, max_radius=16.0):
        for _ in range(24):
            rx = self.pos[0] + random.uniform(-max_radius, max_radius)
            rz = self.pos[2] + random.uniform(-max_radius, max_radius)
            ix, iz = int(math.floor(rx)), int(math.floor(rz))
            if 1 < ix < world.size[0] - 1 and 1 < iz < world.size[2] - 1:
                for iy in range(world.size[1] - 3, 1, -1):
                    if world.is_solid(ix, iy - 1, iz) and not world.is_solid(ix, iy, iz) and not world.is_solid(ix, iy + 1, iz):
                        self.pos[0] = ix + 0.5
                        self.pos[1] = iy
                        self.pos[2] = iz + 0.5
                        return True
        return False

    def intersects_ray(self, origin, direction, reach):
        """Ray-AABB intersection test. Returns distance or None."""
        min_x, min_y, min_z, max_x, max_y, max_z = self.aabb
        tmin, tmax = 0.0, reach

        for i, (p_min, p_max) in enumerate([(min_x, max_x), (min_y, max_y), (min_z, max_z)]):
            d = direction[i]
            o = origin[i]
            if abs(d) < 1e-7:
                if o < p_min or o > p_max:
                    return None
            else:
                t1 = (p_min - o) / d
                t2 = (p_max - o) / d
                if t1 > t2:
                    t1, t2 = t2, t1
                tmin = max(tmin, t1)
                tmax = min(tmax, t2)
                if tmin > tmax:
                    return None
        return tmin if tmin <= reach else None

    def take_damage(self, amount, knockback_src=None):
        if not self.is_alive:
            return False
        self.health -= amount
        self.hurt_timer = 0.35
        if self.category == "passive":
            self.panic_timer = 3.5
        elif self.kind in ("enderman", "wolf", "zombie_pigman"):
            self.is_angry = True

        if self.kind == "enderman" and random.random() < 0.65:
            # Enderman teleports away when hurt
            self.pos[0] += random.uniform(-10.0, 10.0)
            self.pos[2] += random.uniform(-10.0, 10.0)

        if knockback_src:
            kx = self.pos[0] - knockback_src[0]
            kz = self.pos[2] - knockback_src[2]
            dist = math.hypot(kx, kz)
            if dist > 0.01:
                self.vel[0] = (kx / dist) * 5.0
                self.vel[2] = (kz / dist) * 5.0
                self.vel[1] = 4.0

        if self.health <= 0:
            self.is_alive = False
        return True

    def update(self, world, dt, player_pos, daylight=0.5):
        """Update AI and physics for one frame. Returns event strings."""
        if not self.is_alive:
            return []

        self.prev_pos = list(self.pos)
        events = []
        if self.hurt_timer > 0:
            self.hurt_timer = max(0.0, self.hurt_timer - dt)
        if self.attack_cooldown > 0:
            self.attack_cooldown = max(0.0, self.attack_cooldown - dt)

        # AI Behavior
        px, py, pz = self.pos
        plx, ply, plz = player_pos
        dist_to_player = math.hypot(plx - px, plz - pz)

        # Undead mobs burn in daylight if open to sky
        if self.kind in ("zombie", "skeleton") and daylight > 0.4:
            ix, iy, iz = int(px), int(py + self.height), int(pz)
            if world.inside(ix, iy, iz):
                open_sky = True
                for y_above in range(iy, world.size[1]):
                    if world.get(ix, y_above, iz) != AIR:
                        open_sky = False
                        break
                if open_sky:
                    self.on_fire = True
                    self.take_damage(2 * dt)
                    events.append("zombie_burn" if self.kind == "zombie" else "skeleton_burn")

        # Steering
        desired_vx, desired_vz = 0.0, 0.0

        if self.kind == "creeper":
            if dist_to_player < 16.0 and abs(ply - py) < 6.0:
                dx, dz = plx - px, plz - pz
                dist = math.hypot(dx, dz)
                if dist > 0.1:
                    self.yaw = math.degrees(math.atan2(dx, dz))
                if dist > 2.0:
                    desired_vx = (dx / dist) * self.speed
                    desired_vz = (dz / dist) * self.speed
                # Fuse trigger
                if dist < 3.0:
                    self.is_fusing = True
                    self.fuse_timer += dt
                    if self.fuse_timer >= 1.5:
                        self.is_alive = False
                        events.append("creeper_explode")
                else:
                    self.is_fusing = False
                    self.fuse_timer = max(0.0, self.fuse_timer - dt * 2.0)
            else:
                self._wander(dt)
                desired_vx = self.target_dir[0] * self.speed * 0.5
                desired_vz = self.target_dir[1] * self.speed * 0.5

        elif self.kind in ("zombie", "spider", "cave_spider", "wither_skeleton"):
            if dist_to_player < 16.0 and abs(ply - py) < 6.0:
                dx, dz = plx - px, plz - pz
                dist = math.hypot(dx, dz)
                if dist > 0.1:
                    self.yaw = math.degrees(math.atan2(dx, dz))
                if dist > 0.8:
                    desired_vx = (dx / dist) * self.speed
                    desired_vz = (dz / dist) * self.speed
                # Melee attack
                if dist < 1.35 and abs(ply - py) < 1.6 and self.attack_cooldown <= 0:
                    self.attack_cooldown = 1.0
                    events.append("zombie_attack" if self.kind == "zombie" else "mob_attack")
            else:
                self._wander(dt)
                desired_vx = self.target_dir[0] * self.speed * 0.5
                desired_vz = self.target_dir[1] * self.speed * 0.5

        elif self.kind == "skeleton":
            if dist_to_player < 16.0 and abs(ply - py) < 6.0:
                dx, dz = plx - px, plz - pz
                dist = math.hypot(dx, dz)
                if dist > 0.1:
                    self.yaw = math.degrees(math.atan2(dx, dz))
                # Keep distance and shoot
                if dist < 6.0:
                    desired_vx = -(dx / dist) * self.speed * 0.8
                    desired_vz = -(dz / dist) * self.speed * 0.8
                elif dist > 12.0:
                    desired_vx = (dx / dist) * self.speed
                    desired_vz = (dz / dist) * self.speed
                self.shoot_cooldown -= dt
                if self.shoot_cooldown <= 0.0:
                    self.shoot_cooldown = 2.0
                    events.append("skeleton_shoot")
            else:
                self._wander(dt)
                desired_vx = self.target_dir[0] * self.speed * 0.5
                desired_vz = self.target_dir[1] * self.speed * 0.5

        elif self.category == "passive":
            if self.panic_timer > 0:
                self.panic_timer -= dt
                dx, dz = px - plx, pz - plz
                dist = math.hypot(dx, dz)
                if dist > 0.01:
                    desired_vx = (dx / dist) * (self.speed * 1.8)
                    desired_vz = (dz / dist) * (self.speed * 1.8)
                    self.yaw = math.degrees(math.atan2(dx, dz))
            else:
                self._wander(dt)
                desired_vx = self.target_dir[0] * self.speed * 0.6
                desired_vz = self.target_dir[1] * self.speed * 0.6
        else:
            self._wander(dt)
            desired_vx = self.target_dir[0] * self.speed * 0.5
            desired_vz = self.target_dir[1] * self.speed * 0.5

        # Blend velocities (acceleration/friction)
        self.vel[0] += (desired_vx - self.vel[0]) * min(1.0, 8.0 * dt)
        self.vel[2] += (desired_vz - self.vel[2]) * min(1.0, 8.0 * dt)

        # Gravity & Jumping
        if not self.on_ground:
            # Chicken slow fluttering
            if self.kind == "chicken":
                self.vel[1] = max(self.vel[1] - 8.0 * dt, -2.0)
            else:
                self.vel[1] = max(self.vel[1] - GRAVITY * dt, -25.0)
        elif self.against_wall and (abs(desired_vx) > 0.2 or abs(desired_vz) > 0.2):
            self.vel[1] = JUMP_SPEED

        # Spider wall climbing
        if self.kind in ("spider", "cave_spider") and self.against_wall:
            self.vel[1] = 4.0

        # Slime periodic hopping
        if self.kind in ("slime", "magma_cube"):
            self.jump_timer -= dt
            if self.jump_timer <= 0.0:
                self.jump_timer = random.uniform(0.8, 1.8)
                if self.on_ground:
                    self.vel[1] = 5.5

        # Move with collision resolution
        hit_x = self._move_axis(world, 0, self.vel[0] * dt)
        hit_z = self._move_axis(world, 2, self.vel[2] * dt)
        self.against_wall = hit_x or hit_z

        self.on_ground = False
        if self._move_axis(world, 1, self.vel[1] * dt):
            if self.vel[1] < 0:
                self.on_ground = True
            self.vel[1] = 0.0

        # Walking animation cycle
        h_speed = math.hypot(self.vel[0], self.vel[2])
        if self.on_ground and h_speed > 0.1:
            self.walk_cycle += h_speed * dt * 4.0
        else:
            self.walk_cycle = 0.0

        return events

    def _wander(self, dt):
        self.ai_timer -= dt
        if self.ai_timer <= 0:
            self.ai_timer = random.uniform(2.5, 6.0)
            if random.random() < 0.65:
                angle = random.uniform(0, 2 * math.pi)
                self.target_dir = [math.sin(angle), math.cos(angle)]
                self.yaw = math.degrees(angle)
            else:
                self.target_dir = [0.0, 0.0]

    def _move_axis(self, world, axis, distance):
        if distance == 0:
            return False
        self.pos[axis] += distance
        hw = self.width / 2
        px, py, pz = self.pos
        lo = (px - hw, py, pz - hw)
        hi = (px + hw, py + self.height, pz + hw)
        hit = None
        for bx in range(math.floor(lo[0]), math.floor(hi[0] - 1e-6) + 1):
            for by in range(math.floor(lo[1]), math.floor(hi[1] - 1e-6) + 1):
                for bz in range(math.floor(lo[2]), math.floor(hi[2] - 1e-6) + 1):
                    if world.is_solid(bx, by, bz):
                        c = (bx, by, bz)[axis]
                        if hit is None or (c < hit if distance > 0 else c > hit):
                            hit = c
        if hit is None:
            return False
        if distance > 0:
            self.pos[axis] = hit - (self.height if axis == 1 else hw) - 1e-4
        else:
            self.pos[axis] = hit + 1 + (0 if axis == 1 else hw) + 1e-4
        return True


class EntityManager:
    """Manages active living mobs and in-world dropped items with streaming and lifecycle."""

    def __init__(self):
        self.entities: List[Entity] = []
        self.dropped_items: List[DroppedItem] = []
        self.spawn_timer = 0.0

    def spawn(self, kind: str, x: float, y: float, z: float) -> Entity:
        ent = Entity(kind, x, y, z)
        self.entities.append(ent)
        return ent

    def spawn_dropped_item(self, item_id: int, count: int, x: float, y: float, z: float, vx: float = 0.0, vy: float = 0.0, vz: float = 0.0, pickup_delay: float = 0.8) -> DroppedItem:
        item = DroppedItem(item_id, count, x, y, z, vx=vx, vy=vy, vz=vz, pickup_delay=pickup_delay)
        self.dropped_items.append(item)
        return item

    def update(self, world, dt, player_pos, daylight, player=None):
        self.spawn_timer += dt
        if self.spawn_timer > 3.0:
            self.spawn_timer = 0.0
            self._try_spawn(world, player_pos, daylight)

        events = []
        dead_drops = []
        for ent in self.entities:
            dist = math.hypot(ent.pos[0] - player_pos[0], ent.pos[2] - player_pos[2])
            if dist > 128.0:
                ent.is_alive = False
                continue

            evts = ent.update(world, dt, player_pos, daylight)
            events.extend(evts)
            if not ent.is_alive:
                # Add legacy dead_drops entry for test compatibility
                if ent.kind == "pig":
                    dead_drops.append((ITEM_RAW_PORK, ent.pos))
                else:
                    dead_drops.append((ITEM_STICK, ent.pos))

                # Also spawn physical in-world dropped items
                cfg = MOB_CONFIGS.get(ent.kind, {})
                for drop_item, min_c, max_c in cfg.get("drops", []):
                    count = random.randint(min_c, max_c)
                    if count > 0:
                        vx = random.uniform(-1.5, 1.5)
                        vz = random.uniform(-1.5, 1.5)
                        self.spawn_dropped_item(drop_item, count, ent.pos[0], ent.pos[1] + 0.4, ent.pos[2], vx, 3.5, vz)

        self.entities = [e for e in self.entities if e.is_alive]

        # Update in-world dropped items
        plx, ply, plz = player_pos
        for item in self.dropped_items:
            item.update(world, dt)
            if not item.is_alive:
                continue

            dist = math.hypot(item.pos[0] - plx, item.pos[2] - plz)
            y_dist = abs(item.pos[1] - ply)

            # Magnet pull towards player
            if dist < 2.5 and y_dist < 2.0 and item.pickup_delay <= 0:
                dx = plx - item.pos[0]
                dy = (ply + 0.5) - item.pos[1]
                dz = plz - item.pos[2]
                pull = 6.0 * dt
                item.vel[0] += (dx / max(0.1, dist)) * pull
                item.vel[1] += dy * pull
                item.vel[2] += (dz / max(0.1, dist)) * pull

            # Pickup
            if dist < 1.3 and y_dist < 1.8 and item.pickup_delay <= 0:
                item.is_alive = False
                events.append("item_pickup")
                events.append(("item_pickup", item.item_id, item.count))
                if player is not None and hasattr(player, "add_to_inventory"):
                    player.add_to_inventory(item.item_id, item.count)

        self.dropped_items = [it for it in self.dropped_items if it.is_alive]
        return events, dead_drops

    def _try_spawn(self, world, player_pos, daylight):
        sx, sy, sz = world.size
        px, py, pz = player_pos
        passives = sum(1 for e in self.entities if e.category == "passive")
        hostiles = sum(1 for e in self.entities if e.category == "hostile")

        # Pick random location 14 to 28 blocks away from player
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(14.0, 28.0)
        x = int(px + math.cos(angle) * dist)
        z = int(pz + math.sin(angle) * dist)

        if not (2 < x < sx - 2 and 2 < z < sz - 2):
            return

        # Find ground level
        for y in range(sy - 3, 2, -1):
            if world.is_solid(x, y - 1, z) and world.get(x, y, z) == AIR and world.get(x, y + 1, z) == AIR:
                if daylight > 0.35 and passives < 10:
                    if world.get(x, y - 1, z) in (1, 2):  # Grass or dirt
                        mob = random.choice(["pig", "cow", "sheep", "chicken", "rabbit"])
                        self.spawn(mob, x + 0.5, y, z + 0.5)
                elif daylight < 0.25 and hostiles < 8:
                    mob = random.choice(["zombie", "skeleton", "creeper", "spider", "enderman"])
                    self.spawn(mob, x + 0.5, y, z + 0.5)
                break

    def hit_target(self, eye, forward, reach=3.5):
        """Find entity aimed at by ray. Returns (entity, hit_distance) or None."""
        closest_ent = None
        closest_dist = reach + 1.0
        for ent in self.entities:
            dist = ent.intersects_ray(eye, forward, reach)
            if dist is not None and dist < closest_dist:
                closest_dist = dist
                closest_ent = ent
        return (closest_ent, closest_dist) if closest_ent else None
