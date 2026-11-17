import pyxel

from pycraft.controls import ACTIONS, DEFAULTS, KEYS, NO_KEY, Controls


def test_defaults():
    c = Controls()
    assert c.is_default()
    assert c.to_settings() == DEFAULTS
    assert c.keys["forward"] == pyxel.KEY_W and c.keys["break"] == pyxel.MOUSE_BUTTON_LEFT


def test_every_default_is_a_key_and_no_two_actions_share_one():
    keys = [KEYS[default] for _, _, default in ACTIONS]
    assert len(set(keys)) == len(keys)


def test_keys_left_to_the_game_cannot_be_given():
    for key in (pyxel.KEY_ESCAPE, pyxel.KEY_1, pyxel.KEY_9, pyxel.KEY_UP, pyxel.KEY_RETURN, pyxel.KEY_SLASH):
        assert key not in KEYS.values()


def test_saved_keys_are_read_back():
    c = Controls({"forward": "Z", "zoom": "MOUSE 4"})
    assert c.name("forward") == "Z" and c.name("zoom") == "MOUSE 4"
    assert c.name("back") == "S"
    assert Controls(c.to_settings()).to_settings() == c.to_settings()


def test_bad_names_keep_the_default():
    c = Controls({"forward": "NOT A KEY", "back": 12, "left": None, "jump": "ESCAPE"})
    assert c.is_default()
    assert Controls("nonsense").is_default()


def test_a_key_given_twice_in_the_file_goes_to_the_first_action():
    c = Controls({"forward": "S"})  # S is also the default of "back"
    assert c.name("forward") == "S"
    assert c.name("back") == NO_KEY  # its own key is taken: it has none until the player gives it one


def test_bind_swaps_with_the_action_that_had_the_key():
    c = Controls()
    assert c.bind("forward", pyxel.KEY_Z) is None
    assert c.name("forward") == "Z"
    assert c.bind("fly", pyxel.KEY_Z) == "forward"
    assert c.name("fly") == "Z" and c.name("forward") == "F"
    assert len(set(c.keys.values())) == len(c.keys)
    c.reset()
    assert c.is_default()


def test_an_action_without_a_key_is_never_held():
    c = Controls({"zoom": NO_KEY})
    assert c.keys["zoom"] is None and c.name("zoom") == NO_KEY
    assert Controls(c.to_settings()).keys["zoom"] is None
