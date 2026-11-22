"""The terrain made from the Earth's data."""
import numpy as np
import pytest

from pycraft import terrain as T
from pycraft.blocks import AIR, DEEPSLATE, SNOW, STONE, WATER
from pycraft.earth import Place, biomes
from pycraft.earth.generator import EarthGenerator
from pycraft.world import World
from tests.earthtiles import write_ground


@pytest.fixture
def alps(tmp_path):
    return Place(45.9237, 6.8694, str(tmp_path))


def points(half=200, step=7.0):
    g = np.arange(-half, half, step)
    return np.meshgrid(g, g, indexing="ij")


def test_flat_height(alps):
    write_ground(alps.root, alps, lambda x, z: 1000.0)
    s = EarthGenerator(7, alps).sample(*points())
    assert np.abs(s["height"] - (T.SEA_LEVEL + 1000)).max() < 1.0
    assert (s["water"] == -1).all() and not s["river"].any()


def test_true_place_of_a_ridge(alps):
    """A wall 300 blocks to the east is 300 blocks to the east."""
    write_ground(alps.root, alps, lambda x, z: np.where(x > 300, 2000.0, 1000.0))
    h = EarthGenerator(7, alps).sample(np.array([280.0, 320.0]), np.zeros(2))["height"]
    assert h[0] < T.SEA_LEVEL + 1100 and h[1] > T.SEA_LEVEL + 1900


def test_near_and_far_agree(alps):
    write_ground(alps.root, alps, lambda x, z: 1500 + 0.3 * x, half=2500)
    gen = EarthGenerator(7, alps)
    x, z = points()
    assert np.abs(gen.sample(x, z, spacing=1)["height"] - gen.sample(x, z, spacing=8)["height"]).max() < 8


def test_steep_ground_is_rougher(alps):
    gen = EarthGenerator(7, alps)
    flat = gen.fine_relief(*points(), np.full((58, 58), 1000.0), np.zeros((58, 58)))
    steep = gen.fine_relief(*points(), np.full((58, 58), 1000.0), np.full((58, 58), 2.0))
    assert flat.std() > 0 and steep.std() > 4 * flat.std()
    assert (gen.fine_relief(*points(), np.full((58, 58), -3.0), np.ones((58, 58))) == 0).all()


@pytest.mark.parametrize("metres, low, high", [(-50, 455, 466), (-10905, 8, 20), (0.0, 505, 511)])
def test_sea(alps, metres, low, high):
    write_ground(alps.root, alps, lambda x, z: metres)
    s = EarthGenerator(7, alps).sample(*points())
    assert (s["water"] == T.SEA_LEVEL).all()
    assert s["height"].min() >= low and s["height"].max() <= high
    assert np.isin(s["biome"], (T.OCEAN, T.DEEP_OCEAN)).all()


def test_everest_fits(alps):
    write_ground(alps.root, alps, lambda x, z: 8849.0)
    h = EarthGenerator(7, alps).sample(*points())["height"]
    assert (h > 9350).all() and (h < T.WORLD_HEIGHT - 64).all()


F = False
RULES = [  # t, rain, altitude, sea depth, relief, plains -> biome
    (-9, 800, 0, 20, 0, F, T.FROZEN_OCEAN), (-7, 800, 0, 20, 0, F, T.OCEAN), (10, 800, 0, 61, 0, F, T.DEEP_OCEAN),
    (10, 800, 1.5, 0, 0, F, T.BEACH), (10, 800, 1.6, 0, 0, F, T.FOREST),
    (-6.1, 800, 3000, 0, 0, F, T.SNOWY_PEAKS), (-5.9, 800, 3000, 0, 0, F, T.ROCKY),
    (-9.9, 200, 5000, 0, 0, F, T.ROCKY), (-10.1, 200, 5000, 0, 0, F, T.SNOWY_PEAKS),  # dry: a higher snow line
    (-3.4, 800, 2500, 0, 0, F, T.ALPINE), (-0.9, 800, 2500, 0, 0, F, T.TAIGA),
    (-14.1, 800, 100, 0, 0, F, T.SNOWY_TUNDRA), (-9.1, 240, 100, 0, 0, F, T.SNOWY_TUNDRA),
    (-9.1, 260, 100, 0, 0, F, T.SNOWY_TAIGA), (-4.9, 800, 100, 0, 0, F, T.TAIGA), (3.1, 800, 100, 0, 0, F, T.BIRCH_FOREST),
    (20, 260, 100, 0, 0, F, T.DESERT), (20, 260, 100, 0, 251, F, T.BADLANDS),
    (20, 280, 100, 0, 0, F, T.SAVANNA), (17, 250, 100, 0, 0, F, T.PLAINS),
    (20, 1500, 100, 0, 0, F, T.JUNGLE), (20, 1499, 100, 0, 0, F, T.SAVANNA),
    (7.9, 800, 100, 0, 0, F, T.BIRCH_FOREST), (8.1, 800, 100, 0, 0, F, T.FOREST),
    (8.1, 800, 100, 0, 0, True, T.PLAINS), (7.9, 800, 100, 0, 0, True, T.PLAINS)]


@pytest.mark.parametrize("t, rain, altitude, depth, relief, plains, wanted", RULES)
def test_biome_rules(t, rain, altitude, depth, relief, plains, wanted):
    one = [np.array([float(v)]) for v in (t, rain, altitude, depth, relief)]
    got = biomes.biome(*one, np.array([plains]))
    assert got.dtype == np.uint8 and T.BIOME_NAMES[got[0]] == T.BIOME_NAMES[wanted]


def test_game_climate():
    t, h = biomes.game_climate(np.array([19.0, -1.0]), np.array([700.0, 3000.0]))
    assert np.allclose(t, [0.35, 0.35 - 20 * 0.0433]) and np.allclose(h, [0.0, 0.6])


def test_real_climate_is_used(tmp_path):
    for lat, lon, wanted in ((27.2, 2.47, {T.DESERT, T.BADLANDS}), (-3.1, -60.0, {T.JUNGLE}), (62.03, 129.73, {T.SNOWY_TAIGA, T.SNOWY_TUNDRA})):
        place = Place(lat, lon, str(tmp_path / str(lat)))
        write_ground(place.root, place, lambda x, z: 150.0)
        assert set(np.unique(EarthGenerator(7, place).sample(*points())["biome"])) <= wanted


def test_chunk_borders(alps):
    write_ground(alps.root, alps, lambda x, z: 1500 + 0.8 * x + 60 * np.sin(z / 40))
    gen = EarthGenerator(7, alps)
    a, b = gen.columns([(0, 0)])[0], gen.columns([(1, 0)])[0]
    both = gen.columns([(0, 0), (1, 0)])
    assert (a.height == both[0].height).all() and (b.height == both[1].height).all()
    assert (a.surface == both[0].surface).all()
    assert np.abs(a.height[-1] - b.height[0]).max() <= 6


def test_columns_build(alps):
    write_ground(alps.root, alps, lambda x, z: 1000.0)
    world = World(7, alps)
    y = world.surface_y(8, 8)
    assert abs(y - (T.SEA_LEVEL + 1000)) <= 1
    assert world.get(8, y, 8) not in (AIR, WATER) and world.get(8, y - 12, 8) in (STONE, AIR)
    assert world.get(8, y + 40, 8) == AIR
    deep = world.section(0, (y - 400) // 16, 0)
    assert (deep == DEEPSLATE) if isinstance(deep, int) else (deep == DEEPSLATE).any()


def test_column_tiles_are_enough(tmp_path):
    """The ground of a chunk is the same with just its tiles on disk as with everything around."""
    ground = lambda x, z: 1500 + 0.5 * x + 80 * np.sin(x / 90) + 60 * np.cos(z / 70)  # noqa: E731
    few, all_ = Place(45.9237, 6.8694, str(tmp_path / "few")), Place(45.9237, 6.8694, str(tmp_path / "all"))
    write_ground(all_.root, all_, ground, half=5000)
    gen = EarthGenerator(7, all_)
    for cx, cz in ((0, 0), (40, -70), (66, 68)):
        keys = gen.column_tiles(cx, cz)
        write_ground(few.root, few, ground, keys=keys)
        around = [(cx + i, cz + j) for i in range(-2, 3) for j in range(-2, 3)]
        for a, b in zip(gen.columns(around), EarthGenerator(7, few).columns(around)):
            assert (a.height == b.height).all() and (a.biome == b.biome).all()


def test_level_tiles_are_enough(tmp_path):
    ground = lambda x, z: 1500 + 0.1 * x + 80 * np.sin(x / 900)  # noqa: E731
    few, all_ = Place(45.9237, 6.8694, str(tmp_path / "few")), Place(45.9237, 6.8694, str(tmp_path / "all"))
    write_ground(all_.root, all_, ground, half=30000, zooms=(12, 8))
    gen = EarthGenerator(7, all_)
    write_ground(few.root, few, ground, keys=gen.level_tiles(-4000, -4000, 4000, 4000, 32))
    x, z = points(4000, 32.0)
    a, b = gen.sample(x, z, spacing=32), EarthGenerator(7, few).sample(x, z, spacing=32)
    assert (a["height"] == b["height"]).all() and (a["biome"] == b["biome"]).all()


def test_shift_and_clouds(alps):
    write_ground(alps.root, alps, lambda x, z: 5000.0)
    write_ground(alps.root, alps, lambda x, z: 5000.0, half=21000, zooms=(9,))
    gen = EarthGenerator(7, alps)
    assert gen.shift(np.full((16, 16), T.SEA_LEVEL + 5000)) == 4936 and gen.shift(np.full((16, 16), 500)) == 0
    assert abs(gen.cloud_height - (T.SEA_LEVEL + 5300)) < 5


def test_clouds_are_above_the_summits_around(alps):
    """From a valley, the summit 10 km away shows under the clouds."""
    write_ground(alps.root, alps, lambda x, z: 1000 + 3800 * np.exp(-(x ** 2 + (z - 10000) ** 2) / 3e6), half=21000,
                 zooms=(9,))
    gen = EarthGenerator(7, alps)
    assert T.SEA_LEVEL + 4800 < gen.cloud_height < T.SEA_LEVEL + 5200
    assert {k[0] for k in gen.sky_tiles()} == {9}


def test_cloud_height_is_read_once(alps):
    """It is asked for at each frame."""
    write_ground(alps.root, alps, lambda x, z: 3000.0)
    gen = EarthGenerator(7, alps)
    first = gen.cloud_height
    gen.reader = None
    assert gen.cloud_height == first


def test_snow_is_deep_and_rock_shows_on_the_walls(alps):
    """Far away a slope shows mostly the sides of its columns: thin snow would look like bare rock."""
    s = {"biome": np.full((1, 3), T.SNOWY_PEAKS), "water": np.full((1, 3), -1), "temperature": np.full((1, 3), -1.0),
         "humidity": np.zeros((1, 3)), "moss": np.zeros((1, 3), bool)}
    surface, filler, depth = T._surface(s, np.full((1, 3), 4000), np.array([[0, 2, 3]]), np.zeros((1, 3)))
    assert surface.tolist() == [[SNOW, SNOW, STONE]] and filler.tolist() == [[SNOW, SNOW, STONE]]
    assert (depth[0, :2] >= 4).all()
    del s["moss"]  # a normal world: as it was
    surface, filler, _ = T._surface(s, np.full((1, 3), 4000), np.array([[0, 2, 3]]), np.zeros((1, 3)))
    assert surface.tolist() == [[SNOW] * 3] and filler.tolist() == [[STONE] * 3]


def test_clouds_are_never_lower_than_usual(alps):
    write_ground(alps.root, alps, lambda x, z: -3000.0)
    assert EarthGenerator(7, alps).cloud_height == T.SEA_LEVEL + 940


def test_spawn_is_dry(alps):
    write_ground(alps.root, alps, lambda x, z: np.where(x > 120, 40.0, -30.0))
    world = World(7, alps)
    x, y, z = world.find_spawn()
    assert x > 115 and y == world.surface_y(int(np.floor(x)), int(np.floor(z))) + 1


def test_spawn_in_the_middle_of_the_sea(alps):
    write_ground(alps.root, alps, lambda x, z: -3000.0)
    assert World(7, alps).find_spawn() == [0.5, T.SEA_LEVEL + 1.0, 0.5]
