"""The biome map of the usual world must be logical: the goals of tools/biomes.py, on a 32 km square
of one world. The goals the generator doesn't meet yet are expected to fail (strict: once one is
met, its test fails until its name leaves NOT_YET, so that it can't slip back)."""
import pytest

from pycraft import terrain as T
from tools.biomes import GOALS, measures, meets, sample_grid

SEED = 424242
# Goals not met yet, with the step of the plan that fixes them (see GOALS)
NOT_YET = {"specks"}


@pytest.fixture(scope="module")
def measured():
    return measures(sample_grid(T.TerrainGenerator(SEED), size=32768, step=64))


@pytest.mark.parametrize("name", [
    pytest.param(name, marks=pytest.mark.xfail(strict=True, reason=f"step {GOALS[name][3]} of the biome plan"))
    if name in NOT_YET else name for name in GOALS])
def test_goal(measured, name):
    what, op, goal, _ = GOALS[name]
    assert meets(name, measured[name]), f"{what}: {measured[name]:.3f}, goal {op} {goal}"


def test_not_yet_are_goals():
    assert NOT_YET <= set(GOALS)
