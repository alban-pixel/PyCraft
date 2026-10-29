"""Entities system: Pig (passive) and Zombie (hostile) mobs with 3D physics, AI and combat."""
import math
import random

from blocks import (
    AIR, ITEM_RAW_PORK, ITEM_STICK, SOLID,
)

GRAVITY = 24.0
JUMP_SPEED = 7.0


class Entity:
    def __init__(self, kind, x, y, z):
        self.kind = kind
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

        if kind == "pig":
            self.max_health = self.health = 10
            self.width = 0.7
            self.height = 0.85
            self.speed = 2.2
        else:  # "zombie"
            self.max_health = self.health = 20
            self.width = 0.6
            self.height = 1.85
            self.speed = 2.6

    @property
    def aabb(self):
        hw = self.width / 2
        px, py, pz = self.pos
        return (px - hw, py, pz - hw, px + hw, py + self.height, pz + hw)

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
        if self.kind == "pig":
            self.panic_timer = 3.5

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

        # Zombie burns in daylight if open to sky
        if self.kind == "zombie" and daylight > 0.4:
            ix, iy, iz = int(px), int(py + 1.8), int(pz)
            if world.inside(ix, iy, iz):
                open_sky = True
                for y_above in range(iy, world.size[1]):
                    if world.get(ix, y_above, iz) != AIR:
                        open_sky = False
                        break
                if open_sky:
                    self.on_fire = True
                    self.take_damage(2 * dt)
                    events.append("zombie_burn")

        # Steering
        desired_vx, desired_vz = 0.0, 0.0
        if self.kind == "zombie":
            if dist_to_player < 16.0 and abs(ply - py) < 6.0:
                # Track player
                dx, dz = plx - px, plz - pz
                angle = math.atan2(dx, dz)
                self.yaw = math.degrees(angle)
                dist = math.hypot(dx, dz)
                if dist > 0.8:
                    desired_vx = (dx / dist) * self.speed
                    desired_vz = (dz / dist) * self.speed

                # Attack player
                if dist < 1.25 and abs(ply - py) < 1.5 and self.attack_cooldown <= 0:
                    self.attack_cooldown = 1.0
                    events.append("zombie_attack")
            else:
                self._wander(dt)
                desired_vx = self.target_dir[0] * self.speed * 0.5
                desired_vz = self.target_dir[1] * self.speed * 0.5
        elif self.kind == "pig":
            if self.panic_timer > 0:
                self.panic_timer -= dt
                # Flee from player
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

        # Blend velocities (friction/acceleration)
        self.vel[0] += (desired_vx - self.vel[0]) * min(1.0, 8.0 * dt)
        self.vel[2] += (desired_vz - self.vel[2]) * min(1.0, 8.0 * dt)

        # Gravity & Jump over 1-block obstacles
        if not self.on_ground:
            self.vel[1] = max(self.vel[1] - GRAVITY * dt, -25.0)
        elif self.against_wall and (abs(desired_vx) > 0.2 or abs(desired_vz) > 0.2):
            self.vel[1] = JUMP_SPEED

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
    def __init__(self):
        self.entities = []
        self.spawn_timer = 0.0

    def spawn(self, kind, x, y, z):
        ent = Entity(kind, x, y, z)
        self.entities.append(ent)
        return ent

    def update(self, world, dt, player_pos, daylight):
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
                if ent.kind == "pig":
                    dead_drops.append((ITEM_RAW_PORK, ent.pos))
                else:
                    dead_drops.append((ITEM_STICK, ent.pos))

        self.entities = [e for e in self.entities if e.is_alive]
        return events, dead_drops

    def _try_spawn(self, world, player_pos, daylight):
        sx, sy, sz = world.size
        px, py, pz = player_pos
        pigs = sum(1 for e in self.entities if e.kind == "pig")
        zombies = sum(1 for e in self.entities if e.kind == "zombie")

        # Pick random location 14 to 32 blocks from player
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(14.0, 28.0)
        x = int(px + math.cos(angle) * dist)
        z = int(pz + math.sin(angle) * dist)

        if not (2 < x < sx - 2 and 2 < z < sz - 2):
            return

        # Find ground level
        for y in range(sy - 3, 2, -1):
            if world.is_solid(x, y - 1, z) and world.get(x, y, z) == AIR and world.get(x, y + 1, z) == AIR:
                if daylight > 0.35 and pigs < 8:
                    if world.get(x, y - 1, z) in (1, 2):  # Grass or dirt
                        self.spawn("pig", x + 0.5, y, z + 0.5)
                elif daylight < 0.25 and zombies < 6:
                    self.spawn("zombie", x + 0.5, y, z + 0.5)
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
