"""First-person player: walking, jumping, swimming, flying, health/survival, and collisions."""
import math

import pyxel

from blocks import WATER
from metabolism import Metabolism, EXHAUSTION_JUMP, EXHAUSTION_SPRINT_JUMP, EXHAUSTION_SPRINT_PER_M


def _btn(key):
    try:
        return pyxel.btn(key)
    except BaseException:
        return False


def _btnp(key):
    try:
        return pyxel.btnp(key)
    except BaseException:
        return False

HALF_WIDTH = 0.3
HEIGHT = 1.8
EYE_HEIGHT = 1.62
WALK_SPEED = 4.3
SPRINT_SPEED = 6.5
SWIM_SPEED = 2.6
FLY_SPEED = 11.0
GRAVITY = 28.0
WATER_GRAVITY = 8.0
JUMP_SPEED = 8.4  # about 1.25 blocks high
SWIM_UP_SPEED = 4.0
MAX_FALL_SPEED = 40.0
MAX_SINK_SPEED = 3.0
STEP_DISTANCE = 1.7  # blocks walked between footstep sounds


class Player:
    def __init__(self, x, y, z, mode="survival"):
        self.pos = [x, y, z]  # feet position
        self.vel_y = 0.0
        self.yaw = 0.0  # degrees, 0 looks toward +z
        self.pitch = 0.0  # degrees, positive looks up
        self.on_ground = False
        self.flying = False
        self.in_water = False
        self.against_wall = False
        self.walked = 0.0
        self.mode = mode  # "survival" or "creative"

        # Health & Survival
        self.max_health = 20
        self.health = 20
        self.max_air = 10.0
        self.air = 10.0
        self.drown_timer = 0.0
        self.fall_start_y = float(y)
        self.hurt_timer = 0.0
        self.swing_progress = 0.0

        # Deterministic sub-frame interpolation & metabolism
        self.prev_pos = [float(x), float(y), float(z)]
        self.metabolism = Metabolism(max_health=self.max_health)

    @property
    def is_dead(self):
        return self.health <= 0

    def eye(self):
        return (self.pos[0], self.pos[1] + EYE_HEIGHT, self.pos[2])

    def forward(self):
        yaw, pitch = math.radians(self.yaw), math.radians(self.pitch)
        return (math.sin(yaw) * math.cos(pitch), math.sin(pitch), math.cos(yaw) * math.cos(pitch))

    def look(self, d_yaw, d_pitch):
        self.yaw = (self.yaw + d_yaw) % 360
        self.pitch = max(-89.0, min(89.0, self.pitch + d_pitch))

    def head_in_water(self, world):
        x, y, z = self.eye()
        return world.get(math.floor(x), math.floor(y), math.floor(z)) == WATER

    def overlaps(self, x, y, z):
        """True if block (x, y, z) intersects the player's body."""
        px, py, pz = self.pos
        return (x < px + HALF_WIDTH and x + 1 > px - HALF_WIDTH and y < py + HEIGHT and y + 1 > py
                and z < pz + HALF_WIDTH and z + 1 > pz - HALF_WIDTH)

    def _overlaps_world(self, world):
        px, py, pz = self.pos
        lo = (px - HALF_WIDTH, py, pz - HALF_WIDTH)
        hi = (px + HALF_WIDTH, py + HEIGHT, pz + HALF_WIDTH)
        for bx in range(math.floor(lo[0]), math.floor(hi[0] - 1e-6) + 1):
            for by in range(math.floor(lo[1]), math.floor(hi[1] - 1e-6) + 1):
                for bz in range(math.floor(lo[2]), math.floor(hi[2] - 1e-6) + 1):
                    if world.is_solid(bx, by, bz):
                        return True
        return False

    def swing(self):
        """Trigger hand/tool swing animation."""
        self.swing_progress = 1.0

    def take_damage(self, amount):
        """Apply damage in survival mode. Returns True if damage was taken."""
        if self.mode == "creative" or self.health <= 0:
            return False
        self.health = max(0, self.health - amount)
        self.metabolism.health = self.health
        self.hurt_timer = 0.35
        return True

    def heal(self, amount):
        if self.health > 0:
            self.health = min(self.max_health, self.health + amount)
            self.metabolism.health = self.health

    def respawn(self, spawn_pos):
        self.pos = list(spawn_pos)
        self.prev_pos = list(spawn_pos)
        self.health = self.max_health
        self.metabolism.health = self.max_health
        self.metabolism.food = 20
        self.metabolism.saturation = 5.0
        self.metabolism.exhaustion = 0.0
        self.air = self.max_air
        self.vel_y = 0.0
        self.fall_start_y = float(self.pos[1])
        self.hurt_timer = 0.0
        self.flying = False

    def toggle_mode(self):
        if self.mode == "survival":
            self.mode = "creative"
        else:
            self.mode = "survival"
            self.flying = False

    def tick_metabolism(self):
        """Process 1 tick (20 Hz) of metabolism."""
        events = set()
        if self.mode == "survival":
            healed, damaged = self.metabolism.tick()
            if healed > 0:
                self.health = self.metabolism.health
            if damaged > 0:
                self.health = self.metabolism.health
                events.add("hurt")
        return events

    def update(self, world, dt, tick_metabolism=False):
        """Move the player for one frame. Returns the set of sound events."""
        events = set()
        self.prev_pos = list(self.pos)

        if self.hurt_timer > 0:
            self.hurt_timer = max(0.0, self.hurt_timer - dt)
        if self.swing_progress > 0:
            self.swing_progress = max(0.0, self.swing_progress - dt * 4.5)

        # Metabolism tick in survival mode
        if tick_metabolism:
            events.update(self.tick_metabolism())

        # Flying toggle (Creative mode only)
        if _btnp(pyxel.KEY_F):
            if self.mode == "creative":
                self.flying = not self.flying
                self.vel_y = 0.0

        px, py, pz = self.pos
        was_in_water = self.in_water
        self.in_water = world.get(math.floor(px), math.floor(py + 0.4), math.floor(pz)) == WATER
        if self.in_water and not was_in_water and self.vel_y < -4:
            events.add("splash")

        # Drowning in survival mode
        if self.mode == "survival":
            if self.head_in_water(world):
                self.air = max(0.0, self.air - dt)
                if self.air <= 0.0:
                    self.drown_timer += dt
                    if self.drown_timer >= 1.0:
                        self.drown_timer = 0.0
                        if self.take_damage(2):
                            events.add("hurt")
            else:
                self.air = min(self.max_air, self.air + dt * 4.0)
                self.drown_timer = 0.0

        # Horizontal movement relative to look orientation
        yaw = math.radians(self.yaw)
        fx, fz = math.sin(yaw), math.cos(yaw)
        rx, rz = -fz, fx
        move_f = (_btn(pyxel.KEY_W) or _btn(pyxel.KEY_Z)) - _btn(pyxel.KEY_S)
        move_r = _btn(pyxel.KEY_D) - (_btn(pyxel.KEY_A) or _btn(pyxel.KEY_Q))
        dx, dz = fx * move_f + rx * move_r, fz * move_f + rz * move_r
        length = math.hypot(dx, dz)
        is_sprint = _btn(pyxel.KEY_LCTRL) and (self.mode == "creative" or self.metabolism.can_sprint)
        if length:
            if self.flying:
                speed = FLY_SPEED
            elif self.in_water:
                speed = SWIM_SPEED
            elif is_sprint:
                speed = SPRINT_SPEED
                if self.mode == "survival":
                    self.metabolism.add_exhaustion(length * dt * EXHAUSTION_SPRINT_PER_M)
            else:
                speed = WALK_SPEED
            dx, dz = dx / length * speed * dt, dz / length * speed * dt

        if self.flying:
            self.vel_y = (_btn(pyxel.KEY_SPACE) - _btn(pyxel.KEY_LSHIFT)) * FLY_SPEED
            self.fall_start_y = self.pos[1]
        elif self.in_water:
            if _btn(pyxel.KEY_SPACE):
                self.vel_y = JUMP_SPEED * 0.75 if self.against_wall else SWIM_UP_SPEED
            self.vel_y = max(self.vel_y - WATER_GRAVITY * dt, -MAX_SINK_SPEED)
            self.fall_start_y = self.pos[1]
        else:
            if self.on_ground:
                if _btn(pyxel.KEY_SPACE):
                    self.vel_y = JUMP_SPEED
                    events.add("jump")
                    if self.mode == "survival":
                        self.metabolism.add_exhaustion(EXHAUSTION_SPRINT_JUMP if is_sprint else EXHAUSTION_JUMP)
            else:
                # Track highest point when falling
                if self.pos[1] > self.fall_start_y:
                    self.fall_start_y = self.pos[1]
            self.vel_y = max(self.vel_y - GRAVITY * dt, -MAX_FALL_SPEED)

        was_on_ground = self.on_ground
        hit_x = self._move_axis(world, 0, dx)
        hit_z = self._move_axis(world, 2, dz)

        # Auto-step up to 0.60m for slabs/stairs/steps
        if (hit_x or hit_z) and was_on_ground and not self.flying and not self.in_water and (dx != 0 or dz != 0):
            step_h = 0.60
            orig_x, orig_y, orig_z = self.pos
            self.pos[1] += step_h
            if not self._overlaps_world(world):
                step_x = self._move_axis(world, 0, dx)
                step_z = self._move_axis(world, 2, dz)
                self._move_axis(world, 1, -step_h - 1e-4)
                if self.pos[1] > orig_y + 1e-4:
                    hit_x = False
                    hit_z = False
                    self.on_ground = True
                else:
                    self.pos = [orig_x, orig_y, orig_z]
            else:
                self.pos[1] = orig_y

        self.against_wall = hit_x or hit_z
        self.on_ground = False
        if self._move_axis(world, 1, self.vel_y * dt):
            if self.vel_y < 0:
                self.on_ground = True
                # Fall damage check
                if not was_on_ground and not self.flying and not self.in_water:
                    fallen = self.fall_start_y - self.pos[1]
                    if fallen > 3.5 and self.mode == "survival":
                        damage = int(round(fallen - 3.0))
                        if damage > 0 and self.take_damage(damage):
                            events.add("hurt")
                self.fall_start_y = self.pos[1]
            self.vel_y = 0.0

        if self.on_ground and not self.flying:
            self.walked += math.hypot(self.pos[0] - px, self.pos[2] - pz)
            if self.walked > STEP_DISTANCE:
                self.walked = 0.0
                events.add("step")
        return events

    def _move_axis(self, world, axis, distance):
        """Move along one axis, then push back out of any block. Returns True on a collision."""
        if distance == 0:
            return False
        self.pos[axis] += distance
        px, py, pz = self.pos
        lo = (px - HALF_WIDTH, py, pz - HALF_WIDTH)
        hi = (px + HALF_WIDTH, py + HEIGHT, pz + HALF_WIDTH)
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
            self.pos[axis] = hit - (HEIGHT if axis == 1 else HALF_WIDTH) - 1e-4
        else:
            self.pos[axis] = hit + 1 + (0 if axis == 1 else HALF_WIDTH) + 1e-4
        return True
