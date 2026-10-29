import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

import blocks
from main import App


def test_app_initialization(headless_app):
    app = headless_app
    assert app.headless is True
    assert app.state == "title"
    assert app.player is not None
    assert app.world is not None
    assert app.renderer is not None
    assert len(app.hotbar) == 9
    assert len(app.inventory) == 27


def test_app_start_game(headless_app):
    app = headless_app
    # Start game by switching state to "playing"
    app.start_game(new_world=False)
    assert app.state == "playing"
    assert app.player.mode in ("survival", "creative")


def test_app_survival_mode_toggle(headless_app):
    app = headless_app
    app.set_state("playing")
    app.player.mode = "survival"

    # Toggle mode
    app.player.toggle_mode()
    assert app.player.mode == "creative"
    app.player.toggle_mode()
    assert app.player.mode == "survival"


def test_app_give_item_and_inventory(headless_app):
    app = headless_app
    # Clear hotbar and inventory
    for i in range(9):
        app.hotbar[i] = [0, 0]
    for i in range(27):
        app.inventory[i] = [0, 0]

    # Add 10 logs
    app.add_to_inventory(blocks.LOG, 10)
    assert app.hotbar[0] == [blocks.LOG, 10]

    # Check ingredient check and consumption
    assert app.has_ingredients({blocks.LOG: 5}) is True
    assert app.has_ingredients({blocks.LOG: 20}) is False

    app.consume_ingredients({blocks.LOG: 3})
    assert app.hotbar[0] == [blocks.LOG, 7]


def test_app_quick_craft(headless_app):
    app = headless_app
    # Clear hotbar and inventory
    for i in range(9):
        app.hotbar[i] = [0, 0]
    for i in range(27):
        app.inventory[i] = [0, 0]

    # Give 2 logs
    app.add_to_inventory(blocks.LOG, 2)
    recipes = app.quick_recipes()
    # First quick recipe is Planks x4 ({LOG: 1} -> (PLANKS, 4))
    r_name, r_ingr, r_out = recipes[0]
    assert r_name == "Planks x4"
    assert app.has_ingredients(r_ingr) is True

    app.consume_ingredients(r_ingr)
    app.add_to_inventory(r_out[0], r_out[1])

    # Should now have 1 LOG and 4 PLANKS
    assert sum(s[1] for s in app.hotbar if s[0] == blocks.LOG) == 1
    assert sum(s[1] for s in app.hotbar if s[0] == blocks.PLANKS) == 4


def test_app_mob_spawning_and_combat(headless_app):
    app = headless_app
    px, py, pz = app.player.pos
    # Spawn a zombie nearby
    zombie = app.entity_mgr.spawn("zombie", px + 1.0, py, pz + 1.0)
    assert zombie in app.entity_mgr.entities
    assert zombie.is_alive is True

    # Deal lethal damage
    zombie.take_damage(99)
    assert not zombie.is_alive
    events, drops = app.entity_mgr.update(app.world, dt=0.1, player_pos=app.player.pos, daylight=0.0)
    assert zombie not in app.entity_mgr.entities
    assert len(drops) > 0


def test_app_game_over_and_respawn(headless_app):
    app = headless_app
    app.set_state("playing")
    app.player.mode = "survival"

    # Kill player
    app.player.take_damage(99)
    assert app.player.health <= 0

    # Simulate game update when dead -> transitions to game_over
    app.update()
    assert app.state == "game_over"

    # Simulate respawn
    app.respawn_player()
    assert app.state == "playing"
    assert app.player.health == 20
    assert not app.player.is_dead


def test_app_fluid_tick_in_game(headless_app):
    app = headless_app
    app.set_state("playing")
    app.player.health = 20

    # Place water block within world bounds
    px = max(1, min(int(app.player.pos[0]), app.world.size[0] - 2))
    py = max(1, min(int(app.player.pos[1]) + 1, app.world.size[1] - 2))
    pz = max(1, min(int(app.player.pos[2]), app.world.size[2] - 2))
    app.world.set(px, py, pz, blocks.WATER)
    app.world.trigger_water(px, py, pz)
    assert (px, py, pz) in app.world.active_water

    # Advance fluid timer
    app.fluid_timer = 0.5
    app.update()
    # Water should have ticked and reset fluid_timer
    assert app.fluid_timer < 0.5


def test_app_save_with_inhomogeneous_tool_durability(headless_app, tmp_path):
    app = headless_app
    app.set_state("playing")
    app.save_dir = str(tmp_path)
    app.world_name = "test_world"

    # Set up inhomogeneous hotbar: some 2-element slots, some 3-element slots (with durability)
    app.hotbar = [
        [blocks.ITEM_IRON_PICKAXE, 1, 240],
        [blocks.DIRT, 32],
        [blocks.ITEM_DIAMOND_SWORD, 1, 1500],
        [0, 0],
        [0, 0],
        [0, 0],
        [0, 0],
        [0, 0],
        [0, 0],
    ]
    app.inventory = [[0, 0]] * 27
    app.inventory[0] = [blocks.ITEM_WOOD_PICKAXE, 1, 45]
    app.inventory[1] = [blocks.COBBLESTONE, 64]

    # Verify snapshot succeeds without ValueError (inhomogeneous shape)
    snap = app.snapshot()
    assert snap["hotbar"].shape == (9, 3)
    assert snap["inventory"].shape == (27, 3)
    assert snap["hotbar"][0].tolist() == [blocks.ITEM_IRON_PICKAXE, 1, 240]
    assert snap["hotbar"][1].tolist() == [blocks.DIRT, 32, 0]

    # Test save execution
    app.save()

    # Reset state to title
    app.set_state("title")

