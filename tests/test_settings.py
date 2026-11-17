from pycraft.settings import DEFAULT_SETTINGS, RANGES, SETTING_TABS, parse_settings


def test_every_setting_is_on_one_tab():
    on_tabs = [key for keys in SETTING_TABS.values() for key in keys]
    assert sorted(on_tabs) == sorted(DEFAULT_SETTINGS)


def test_defaults_are_valid():
    assert parse_settings(dict(DEFAULT_SETTINGS, resolution=list(DEFAULT_SETTINGS["resolution"]))) == DEFAULT_SETTINGS
    for key, (low, high, step) in RANGES.items():
        assert low <= DEFAULT_SETTINGS[key] <= high and (DEFAULT_SETTINGS[key] - low) % step == 0


def test_values_on_a_scale():
    assert parse_settings({"fov": 90})["fov"] == 90
    for bad in (45, 115, 72, 90.0, "90", True, None):
        assert parse_settings({"fov": bad})["fov"] == DEFAULT_SETTINGS["fov"]
    assert parse_settings({"sensitivity": 300, "music_volume": 0})["sensitivity"] == 300
    assert parse_settings({"music_volume": 0})["music_volume"] == 0


def test_choices_and_switches():
    s = parse_settings({"autosave": 0, "day_length": 60, "crosshair": "dot", "invert_y": True, "show_help": False})
    assert (s["autosave"], s["day_length"], s["crosshair"], s["invert_y"], s["show_help"]) == (0, 60, "dot", True, False)
    s = parse_settings({"autosave": True, "day_length": 15, "crosshair": "star", "invert_y": 1, "show_help": "no"})
    assert s == DEFAULT_SETTINGS  # (True is not "1 minute")


def test_a_file_from_before_the_volumes():
    assert parse_settings({"music": False})["music_volume"] == 0
    assert parse_settings({"music": True})["music_volume"] == DEFAULT_SETTINGS["music_volume"]
    assert parse_settings({"music": False, "music_volume": 30})["music_volume"] == 30
    assert "music" not in parse_settings({"music": False})


def test_keys_are_kept_as_they_are_for_the_controls_to_check():
    assert parse_settings({"keys": {"forward": "Z"}})["keys"] == {"forward": "Z"}
    assert parse_settings({"keys": ["W"]})["keys"] == {}
