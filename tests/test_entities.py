import math
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import blocks
from entities import Entity, EntityManager
from world import World


def test_entity_creation_and_aabb():
    pig = Entity("pig", 5.0, 4.0, 5.0)
    assert pig.kind == "pig"
    assert pig.health == 10
    assert pig.is_alive is True
    min_x, min_y, min_z, max_x, max_y, max_z = pig.aabb
    assert min_x < 5.0 < max_x
    assert min_y == 4.0
    assert max_y == 4.0 + pig.height

    zombie = Entity("zombie", 10.0, 5.0, 10.0)
    assert zombie.kind == "zombie"
    assert zombie.health == 20
    assert zombie.height > pig.height


def test_entity_intersects_ray():
    zombie = Entity("zombie", 5.0, 2.0, 5.0)
    # Eye looking directly at zombie from (5.0, 2.5, 2.0) towards +z
    origin = (5.0, 2.5, 2.0)
    forward = (0.0, 0.0, 1.0)
    dist = zombie.intersects_ray(origin, forward, reach=5.0)
    assert dist is not None
    assert 2.5 < dist < 3.5

    # Ray pointing away
    away = (0.0, 1.0, 0.0)
    assert zombie.intersects_ray(origin, away, reach=5.0) is None


def test_entity_damage_and_knockback():
    pig = Entity("pig", 5.0, 2.0, 5.0)
    # Deal damage with knockback from (4.0, 2.0, 5.0)
    hit = pig.take_damage(4, knockback_src=(4.0, 2.0, 5.0))
    assert hit is True
    assert pig.health == 6
    assert pig.hurt_timer > 0
    assert pig.panic_timer > 0
    # Knockback should push pig in +x direction
    assert pig.vel[0] > 0
    assert pig.vel[1] > 0


def test_zombie_attack_player():
    w = World(size=(16, 32, 16), seed=1, generate=False)
    # Solid platform
    for x in range(16):
        for z in range(16):
            w.set(x, 1, z, blocks.STONE)

    zombie = Entity("zombie", 5.0, 2.0, 5.0)
    zombie.attack_cooldown = 0.0

    # Player very close at (5.5, 2.0, 5.0)
    events = zombie.update(w, dt=0.05, player_pos=(5.5, 2.0, 5.0), daylight=0.0)
    assert "zombie_attack" in events
    assert zombie.attack_cooldown > 0.5


def test_zombie_daylight_burn():
    w = World(size=(16, 32, 16), seed=1, generate=False)
    # Clear sky above zombie
    for x in range(16):
        for z in range(16):
            w.set(x, 1, z, blocks.STONE)

    zombie = Entity("zombie", 5.0, 2.0, 5.0)
    # Under bright daylight (> 0.65) and clear sky
    events = zombie.update(w, dt=1.0, player_pos=(15.0, 2.0, 15.0), daylight=0.9)
    assert "zombie_burn" in events
    assert zombie.on_fire is True
    assert zombie.health < 20


def test_entity_manager_targeting_and_drops():
    w = World(size=(16, 32, 16), seed=1, generate=False)
    for x in range(16):
        for z in range(16):
            w.set(x, 1, z, blocks.STONE)

    mgr = EntityManager()
    pig = mgr.spawn("pig", 5.0, 2.0, 8.0)
    zombie = mgr.spawn("zombie", 12.0, 2.0, 12.0)

    # Raycast target test: look towards pig at (5.0, 2.0, 8.0) from (5.0, 2.0, 4.0)
    hit_ent, dist = mgr.hit_target(eye=(5.0, 2.4, 4.0), forward=(0.0, 0.0, 1.0), reach=6.0)
    assert hit_ent is pig
    assert dist < 5.0

    # Kill pig and verify manager drop collection
    pig.take_damage(99)
    assert not pig.is_alive
    events, drops = mgr.update(w, dt=0.1, player_pos=(5.0, 2.0, 4.0), daylight=0.5)

    assert len(drops) == 1
    drop_item, drop_pos = drops[0]
    assert drop_item == blocks.ITEM_RAW_PORK
    # Pig should be removed from active entities
    assert pig not in mgr.entities
