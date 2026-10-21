import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import blocks
from player import Player
from world import World


def test_player_health_and_damage():
    p = Player(5.0, 5.0, 5.0)
    assert p.health == 20
    assert p.max_health == 20
    assert not p.is_dead

    # Take damage
    dmg = p.take_damage(6)
    assert dmg is True
    assert p.health == 14
    assert p.hurt_timer > 0

    # Healing
    p.heal(4)
    assert p.health == 18

    # Overheal should cap at max_health
    p.heal(10)
    assert p.health == 20

    # Lethal damage
    p.take_damage(25)
    assert p.health == 0
    assert p.is_dead is True


def test_player_respawn():
    p = Player(10.0, 8.0, 10.0)
    p.take_damage(30)
    assert p.is_dead is True

    p.respawn((10.0, 8.0, 10.0))
    assert not p.is_dead
    assert p.health == 20
    assert p.air == p.max_air
    assert p.pos[0] == 10.0
    assert p.pos[1] == 8.0
    assert p.pos[2] == 10.0


def test_creative_mode_invulnerability():
    p = Player(5.0, 5.0, 5.0)
    p.mode = "creative"

    # Damage in creative should be ignored
    took_dmg = p.take_damage(10)
    assert took_dmg is False
    assert p.health == 20
    assert not p.is_dead


def test_drowning_mechanic():
    w = World(size=(16, 32, 16), seed=1, generate=False)
    # Solid bottom so player rests on ground
    for x in range(16):
        for z in range(16):
            w.set(x, 4, z, blocks.STONE)
    # Submerge player completely in water (body at y=5, head at y=6)
    for y in range(5, 8):
        w.set(5, y, 5, blocks.WATER)

    p = Player(5.5, 5.0, 5.5)
    p.on_ground = True

    # In survival mode, air should deplete when head is submerged
    assert p.air == 10.0
    p.update(w, dt=0.5)
    assert p.air < 10.0

    # Exhaust air completely and simulate drowning damage
    p.air = 0.0
    p.drown_timer = 0.0
    p.health = 20
    events = p.update(w, dt=1.05)
    # Drowning should inflict damage and trigger hurt sound event
    assert p.health == 18
    assert "hurt" in events


def test_fall_damage_mechanic():
    w = World(size=(16, 32, 16), seed=1, generate=False)
    # Solid floor at y=2 (surface is y=3)
    for x in range(16):
        for z in range(16):
            w.set(x, 2, z, blocks.STONE)

    # Spawn at y=9.0 (surface is y=3.0, so fall distance is 6.0 blocks)
    p = Player(5.5, 9.0, 5.5)
    p.fall_start_y = 9.0
    p.on_ground = False

    # Simulate realistic falling at 60 fps until landing
    events = set()
    dt = 1.0 / 60.0
    for _ in range(60):
        ev = p.update(w, dt=dt)
        events.update(ev)
        if p.on_ground:
            break

    assert p.on_ground is True
    # Fallen from 9.0 to 3.0 -> 6.0 blocks fallen. Damage = round(6.0 - 3.0) = 3
    # 20 - 3 = 17 health remaining
    assert p.health == 17
    assert "hurt" in events
