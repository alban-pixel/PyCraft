import json
import os
import zipfile

import packs
from packs import PackInfo, clean_name, find_packs, open_pack
from tests.packfactory import make_pack, png, solid


def test_finds_dir_and_zip(tmp_path):
    root = str(tmp_path / "resourcepacks")
    make_pack(root, "Old", "1.8", {"stone": solid((1, 2, 3))})
    make_pack(root, "New", "1.13", {"stone": solid((1, 2, 3))}, zip=True)
    found = find_packs([root], [])
    assert [(p.name, p.layout) for p in found] == [("New", "1.13"), ("Old", "1.8")]
    assert all(isinstance(p, PackInfo) for p in found)


def test_ignores_non_packs(tmp_path):
    root = tmp_path / "resourcepacks"
    (root / "empty_folder").mkdir(parents=True)
    (root / "broken.zip").write_bytes(os.urandom(300))
    (root / "notes.txt").write_text("hello")
    make_pack(str(root), "NoTextures", "1.8", {})
    assert find_packs([str(root)], []) == []


def test_missing_dir_is_fine(tmp_path):
    assert find_packs([str(tmp_path / "nowhere")], [str(tmp_path / "nothing.jar")]) == []


def test_description_from_mcmeta(tmp_path):
    root = str(tmp_path)
    make_pack(root, "A", "1.8", {"stone": solid((1, 2, 3))}, description="§aHello §lworld")
    path = make_pack(root, "B", "1.8", {"stone": solid((1, 2, 3))})
    with open(os.path.join(path, "pack.mcmeta"), "w") as f:
        f.write("{not json")
    found = {p.name: p.description for p in find_packs([root], [])}
    assert found == {"A": "Hello world", "B": ""}


def test_description_component(tmp_path):
    root = str(tmp_path)
    make_pack(root, "A", "1.8", {"stone": solid((1, 2, 3))}, description={"text": "Hi"})
    make_pack(root, "B", "1.8", {"stone": solid((1, 2, 3))}, description=[{"text": "A"}, "B"])
    found = {p.name: p.description for p in find_packs([root], [])}
    assert found == {"A": "Hi", "B": "AB"}


def test_jar_name(tmp_path):
    jar = tmp_path / "versions" / "1.8" / "1.8.jar"
    jar.parent.mkdir(parents=True)
    with zipfile.ZipFile(jar, "w") as z:
        z.writestr("assets/minecraft/textures/blocks/stone.png", png(solid((1, 2, 3))))
    (found,) = find_packs([], [str(jar)])
    assert (found.name, found.layout) == ("Minecraft 1.8", "1.8")


def test_open_pack_reads(tmp_path):
    for zipped in (False, True):
        path = make_pack(str(tmp_path / str(zipped)), "P", "1.13", {"stone": solid((1, 2, 3))}, zip=zipped)
        (info,) = find_packs([os.path.dirname(path)], [])
        with open_pack(info) as files:
            assert "stone" in files.names()
            assert files.read("stone").startswith(b"\x89PNG")
            assert files.read("absent") is None


def test_clean_name():
    assert clean_name("§6Faithful §r32x™") == "Faithful 32x"


def test_minecraft_dir_exists_or_none():
    d = packs.minecraft_dir()
    assert d is None or os.path.isdir(d)


def test_same_name_folder_and_zip(tmp_path):
    root = str(tmp_path)
    make_pack(root, "Same", "1.8", {"stone": solid((1, 2, 3))})
    make_pack(root, "Same", "1.8", {"stone": solid((1, 2, 3))}, zip=True)
    assert sorted(p.name for p in find_packs([root], [])) == ["Same", "Same (zip)"]
