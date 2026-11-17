from main import DEFAULT_SETTINGS, fit_text, next_pack, parse_settings
from packs import PackInfo

A = PackInfo("A", "/packs/a", "", "1.8")
B = PackInfo("B", "/packs/b.zip", "", "1.13")


def test_next_pack_cycles():
    packs = [A, B]
    assert next_pack(None, packs, 1) == A.path
    assert next_pack(A.path, packs, 1) == B.path
    assert next_pack(B.path, packs, 1) is None
    assert next_pack(None, packs, -1) == B.path
    assert next_pack(A.path, packs, -1) is None


def test_next_pack_unknown_current():
    assert next_pack("/gone", [A, B], 1) in (None, A.path, B.path)
    assert next_pack("/gone", [], 1) is None


def test_parse_settings_drops_missing_pack(tmp_path):
    assert parse_settings({"texture_pack": str(tmp_path / "gone.zip")})["texture_pack"] is None
    assert parse_settings({"texture_pack": 12})["texture_pack"] is None
    assert parse_settings({"texture_pack": str(tmp_path)})["texture_pack"] == str(tmp_path)
    assert parse_settings({}) == {**DEFAULT_SETTINGS}


def test_fit_text_keeps_the_end():
    assert fit_text("short", 10) == "short"
    long = "/a/very/long/path/to/resourcepacks"
    fitted = fit_text(long, 20)
    assert len(fitted) == 20 and fitted.startswith("...") and fitted.endswith("resourcepacks")
