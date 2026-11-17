import math

import pyxel

import blocks as B
import items as I
from player import Player
from survival import BreakProgress, Health
from world import World

STEP = 1 / 60


def run(health, seconds, in_water, creative=False):
    taken = 0
    for _ in range(round(seconds * 60)):
        taken += health.update(STEP, in_water, creative)
    return taken


def test_fall_damage():
    assert Health().fall_damage(3, False, False) == 0
    h = Health()
    assert h.fall_damage(3.5, False, False) == 1 and h.hp == 19
    assert Health().fall_damage(10, False, False) == 7
    assert Health().fall_damage(10, True, False) == 0
    h = Health()
    assert h.fall_damage(10, False, True) == 0 and h.hp == 20


def test_drowning():
    h = Health()
    assert run(h, 15, True) == 0 and h.hp == 20
    assert run(h, 1, True) == 2 and h.hp == 18
    run(h, STEP, False)
    assert h.air == Health.MAX_AIR


def test_no_drowning_in_creative():
    h = Health()
    assert run(h, 30, True, creative=True) == 0 and h.air == Health.MAX_AIR


def test_regen():
    h = Health()
    h.hp = 10
    run(h, 8, False)
    assert h.hp == 12


def test_regen_stops_at_full():
    h = Health()
    h.hp = 19
    run(h, 20, False)
    assert h.hp == 20


def test_death_and_reset():
    h = Health()
    h.damage(25)
    assert h.hp == 0 and h.dead
    run(h, 10, False)
    assert h.hp == 0  # the dead don't heal
    h.reset()
    assert h.hp == 20 and h.air == Health.MAX_AIR and not h.dead


def test_break_progress_stone_by_pickaxe():
    bp = BreakProgress()
    target = (0, 0, 0)
    t, done, fractions = 0.0, False, []
    while t < 1.0 - 1e-9:
        assert not bp.update(target, B.STONE, I.WOODEN_PICKAXE, STEP, False)
        fractions.append(bp.fraction)
        t += STEP
    while t < 1.2 and not done:
        done = bp.update(target, B.STONE, I.WOODEN_PICKAXE, STEP, False)
        t += STEP
    assert done
    assert fractions == sorted(fractions) and 0 < fractions[0] < fractions[-1] < 1


def test_break_progress_resets_on_new_target():
    bp = BreakProgress()
    for _ in range(30):
        bp.update((0, 0, 0), B.STONE, 0, STEP, False)
    assert bp.fraction > 0
    bp.update((1, 0, 0), B.STONE, 0, STEP, False)
    assert bp.fraction < 0.01
    for _ in range(30):
        bp.update((1, 0, 0), B.STONE, 0, STEP, False)
    before = bp.fraction
    bp.update((1, 0, 0), B.DIRT, 0, STEP, False)  # the block changed under the crosshair
    assert bp.fraction < before


def test_instant_and_creative():
    bp = BreakProgress()
    assert bp.update((0, 0, 0), B.TALL_GRASS, 0, STEP, False)
    assert BreakProgress().update((0, 0, 0), B.OBSIDIAN, 0, STEP, True)


def test_bedrock_never_breaks():
    bp = BreakProgress()
    for _ in range(6000):
        assert not bp.update((0, 0, 0), B.BEDROCK, I.DIAMOND_PICKAXE, STEP, False)
    assert bp.fraction == 0


def test_player_fall_distance(monkeypatch):
    monkeypatch.setattr(pyxel, "btn", lambda key: False)
    monkeypatch.setattr(pyxel, "btnp", lambda key: False)
    world = World(3)
    for x in range(-2, 3):
        for z in range(-2, 3):
            world.set(x, 2999, z, B.STONE)
    player = Player(0.5, 3010, 0.5)
    landed = None
    for _ in range(600):
        player.update(world, STEP)
        if player.landed:
            landed = player.landed
            break
    assert landed is not None and 9.5 <= landed[0] <= 10.5 and landed[1] is False
    player.update(world, STEP)
    assert player.landed is None and player.fall_distance == 0


def test_cannot_fly_in_survival(monkeypatch):
    monkeypatch.setattr(pyxel, "btn", lambda key: False)
    monkeypatch.setattr(pyxel, "btnp", lambda key: key == pyxel.KEY_F)
    world = World(3)
    player = Player(0.5, 3010, 0.5)
    player.can_fly = False
    player.flying = True
    player.update(world, STEP)
    assert not player.flying
