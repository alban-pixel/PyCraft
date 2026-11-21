from pycraft import blocks as B
from pycraft import items as I
from pycraft import recipes as R


def grid_for(recipe, size=3):
    g = [[0] * size for _ in range(size)]
    if isinstance(recipe, R.Shaped):
        for y, row in enumerate(recipe.pattern):
            for x, ch in enumerate(row):
                if ch not in ". ":
                    g[y][x] = min(recipe.key[ch])
    else:
        for i, ing in enumerate(recipe.ingredients):
            g[i // size][i % size] = min(ing)
    return g


def test_every_recipe_crafts():
    for recipe in R.RECIPES:
        assert R.match(grid_for(recipe)) == recipe.result, recipe


def test_planks_and_sticks():
    assert R.match([[B.LOG, 0], [0, 0]]) == (B.PLANKS, 4)
    assert R.match([[0, 0], [0, B.SPRUCE_LOG]]) == (B.SPRUCE_PLANKS, 4)
    assert R.match([[B.PLANKS, 0], [B.BIRCH_PLANKS, 0]]) == (I.STICK, 4)
    assert R.match([[0, B.PLANKS], [0, B.PLANKS]]) == (I.STICK, 4)
    assert R.match([[B.PLANKS] * 2] * 2) == (B.CRAFTING_TABLE, 1)


def test_pickaxe_shapes():
    c, s = B.COBBLESTONE, I.STICK
    assert R.match([[c, c, c], [0, s, 0], [0, s, 0]]) == (I.STONE_PICKAXE, 1)
    assert R.match([[0, 0, 0], [c, c, c], [0, s, 0]]) is None
    p = B.PLANKS
    assert R.match([[p, p, 0], [p, s, 0], [0, s, 0]]) == (I.WOODEN_AXE, 1)
    assert R.match([[0, p, p], [0, s, p], [0, s, 0]]) == (I.WOODEN_AXE, 1)
    assert R.match([[c, c], [0, s]]) is None


def test_no_match():
    assert R.match([[0] * 3 for _ in range(3)]) is None
    assert R.match([[B.DIRT, B.SAND, 0], [0, B.GLASS, 0], [0, 0, 0]]) is None
    c, s = B.COBBLESTONE, I.STICK
    assert R.match([[c, c, c], [0, s, 0], [0, 0, 0]]) is None


def test_smelting_and_fuel():
    assert R.smelt_result(B.IRON_ORE) == I.IRON_INGOT
    assert R.smelt_result(B.SAND) == B.GLASS
    assert R.smelt_result(B.DIRT) is None
    assert R.fuel_value(I.COAL) == 8
    assert R.fuel_value(B.COAL_BLOCK) == 80
    assert R.fuel_value(B.PLANKS) == 1.5
    assert R.fuel_value(I.STICK) == 0.5
    assert R.fuel_value(B.STONE) == 0
    assert R.COOK_TICKS == 200


def test_recipe_count():
    assert len(R.RECIPES) >= 60
