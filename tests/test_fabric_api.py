"""Exhaustive tests for Fabric API modding architecture."""
import os
import pytest
from fabric_api.identifier import Identifier
from fabric_api.registry import Registry, Registries
from fabric_api.events import Event, EventBus
from fabric_api.mixin import CallbackInfo, inject, mixin
from fabric_api.mod_loader import ModContainer, ModLoader


def test_identifier_parsing_and_equality():
    id1 = Identifier("minecraft", "dirt")
    assert str(id1) == "minecraft:dirt"
    assert id1.namespace == "minecraft"
    assert id1.path == "dirt"

    id2 = Identifier("my_mod:super_block")
    assert id2.namespace == "my_mod"
    assert id2.path == "super_block"

    id3 = Identifier("stone")
    assert id3.namespace == "minecraft"
    assert id3.path == "stone"

    assert id1 == Identifier("minecraft:dirt")
    assert id1 == "minecraft:dirt"
    assert hash(id1) == hash(Identifier("minecraft:dirt"))


def test_identifier_validation_errors():
    with pytest.raises(ValueError):
        Identifier("Uppercase_Not_Allowed", "block")

    with pytest.raises(ValueError):
        Identifier("minecraft", "space in path")

    with pytest.raises(ValueError):
        Identifier("inv@lid:path")


def test_registry_registration_and_lookup():
    reg = Registry[dict]("test_reg")
    item_id = Identifier("testmod", "ruby_sword")
    sword_data = {"attack_damage": 7.5, "durability": 500}

    reg.register(item_id, sword_data)
    assert reg.get(item_id) == sword_data
    assert reg.get("testmod:ruby_sword") == sword_data
    assert item_id in reg
    assert sword_data in reg
    assert reg.get_id(sword_data) == item_id

    # Unregistered key returns None or default
    assert reg.get("testmod:nonexistent") is None
    assert reg.get("testmod:nonexistent", default={"def": True}) == {"def": True}


def test_registry_freeze():
    reg = Registry[str]("freeze_test")
    reg.register("minecraft:apple", "Apple")
    reg.freeze()

    with pytest.raises(RuntimeError):
        reg.register("minecraft:banana", "Banana")

    reg.unfreeze()
    reg.register("minecraft:banana", "Banana")
    assert reg.get("minecraft:banana") == "Banana"


def test_event_bus_dispatch():
    event = Event("custom_test_event")
    results = []

    def cb1(val):
        results.append(val * 2)

    def cb2(val):
        results.append(val + 10)
        return "handled"

    event.register(cb1)
    event.register(cb2)
    ret = event.invoker(5)

    assert results == [10, 15]
    assert ret == "handled"


def test_mixin_injection():
    class Monster:
        def attack(self, target: str, damage: float) -> str:
            return f"Dealt {damage} to {target}"

    @mixin(Monster)
    class MonsterMixin:
        @inject("attack", at="HEAD", cancellable=True)
        def on_attack(self, target: str, damage: float, ci: CallbackInfo):
            if target == "invincible":
                ci.set_return_value("Blocked!")
                ci.cancel()

    m = Monster()
    assert m.attack("player", 5.0) == "Dealt 5.0 to player"
    assert m.attack("invincible", 5.0) == "Blocked!"


def test_mod_loader(tmp_path):
    mods_dir = tmp_path / "mods"
    mod1_dir = mods_dir / "mod_one"
    mod1_dir.mkdir(parents=True)

    manifest = {
        "schemaVersion": 1,
        "id": "mod_one",
        "name": "Mod One",
        "version": "1.0.0",
        "entrypoints": {
            "main": ["mod1_entry.Mod1Init"]
        }
    }
    import json
    (mod1_dir / "fabric.mod.json").write_text(json.dumps(manifest))
    (mod1_dir / "mod1_entry.py").write_text("""
initialized_flag = False
class Mod1Init:
    def on_initialize(self):
        global initialized_flag
        initialized_flag = True
""")

    loader = ModLoader()
    loader.load_mods(str(mods_dir))

    assert "mod_one" in loader.loaded_mods
    assert loader.loaded_mods["mod_one"].name == "Mod One"
    import mod1_entry
    assert mod1_entry.initialized_flag is True
