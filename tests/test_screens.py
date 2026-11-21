import itertools

from pycraft import blocks as B
from pycraft import items as I
from pycraft.furnace import FurnaceState
from pycraft.inventory import EMPTY, Inventory
from pycraft.screens.containers import SLOT, Screen

W, H = 480, 270


def center(screen, region, i):
    x, y = screen.layout(W, H)[region][i]
    return x + SLOT // 2, y + SLOT // 2


def press(screen, region, i, button="left", shift=False):
    screen.click(*center(screen, region, i), W, H, button, shift)


def screens():
    return [Screen(Inventory(), "inventory"), Screen(Inventory(), "table"),
            Screen(Inventory(), "furnace", furnace=FurnaceState())]


def test_layout_counts():
    inv, table, furnace = screens()
    lay = inv.layout(W, H)
    assert (len(lay["grid"]), len(lay["result"]), len(lay["main"]), len(lay["hotbar"])) == (4, 1, 27, 9)
    assert len(table.layout(W, H)["grid"]) == 9
    lay = furnace.layout(W, H)
    assert all(len(lay[k]) == 1 for k in ("input", "fuel", "output")) and "grid" not in lay
    for screen in (inv, table, furnace):
        px, py, pw, ph = screen.panel(W, H)
        rects = [(x, y) for spots in screen.layout(W, H).values() for x, y in spots]
        for x, y in rects:
            assert px <= x and x + SLOT <= px + pw and py <= y and y + SLOT <= py + ph
        for (ax, ay), (bx, by) in itertools.combinations(rects, 2):
            assert abs(ax - bx) >= SLOT or abs(ay - by) >= SLOT


def test_layout_fits_small_screen():
    px, py, pw, ph = Screen(Inventory(), "table").panel(320, 180)
    assert px >= 0 and py >= 0 and px + pw <= 320 and py + ph <= 180


def test_slot_at_roundtrip():
    for screen in screens():
        for region, spots in screen.layout(W, H).items():
            for i in range(len(spots)):
                assert screen.slot_at(*center(screen, region, i), W, H) == (region, i)
        assert screen.slot_at(0, 0, W, H) is None


def test_craft_planks_through_clicks():
    screen = Screen(Inventory(), "inventory")
    screen.inv.slots[9] = (B.LOG, 1, 0)
    press(screen, "main", 0)
    assert screen.cursor == (B.LOG, 1, 0)
    press(screen, "grid", 3)
    assert screen.grid[3] == (B.LOG, 1, 0) and screen.result() == (B.PLANKS, 4, 0)
    press(screen, "result", 0)
    assert screen.cursor == (B.PLANKS, 4, 0) and screen.grid == [EMPTY] * 4 and screen.result() == EMPTY


def test_shift_result_crafts_all():
    screen = Screen(Inventory(), "table")
    screen.grid[4] = (B.LOG, 5, 0)
    press(screen, "result", 0, shift=True)
    assert screen.inv.slots[0] == (B.PLANKS, 20, 0) and screen.grid[4] == EMPTY


def test_shift_hotbar_and_main():
    screen = Screen(Inventory(), "inventory")
    screen.inv.slots[2] = (B.DIRT, 5, 0)
    press(screen, "hotbar", 2, shift=True)
    assert screen.inv.slots[9] == (B.DIRT, 5, 0) and screen.inv.slots[2] == EMPTY
    press(screen, "main", 0, shift=True)
    assert screen.inv.slots[0] == (B.DIRT, 5, 0)


def test_shift_grid_to_inventory():
    screen = Screen(Inventory(), "table")
    screen.grid[0] = (B.STONE, 3, 0)
    press(screen, "grid", 0, shift=True)
    assert screen.grid[0] == EMPTY and screen.inv.slots[0] == (B.STONE, 3, 0)


def test_furnace_shift_routes():
    furnace = FurnaceState()
    screen = Screen(Inventory(), "furnace", furnace=furnace)
    screen.inv.slots[9] = (B.IRON_ORE, 4, 0)
    screen.inv.slots[10] = (I.COAL, 2, 0)
    screen.inv.slots[11] = (B.DIRT, 2, 0)
    press(screen, "main", 0, shift=True)
    press(screen, "main", 1, shift=True)
    press(screen, "main", 2, shift=True)
    assert furnace.slots[0] == (B.IRON_ORE, 4, 0) and furnace.slots[1] == (I.COAL, 2, 0)
    assert screen.inv.slots[0] == (B.DIRT, 2, 0)  # neither: across to the hotbar
    furnace.slots[2] = (I.IRON_INGOT, 3, 0)
    press(screen, "output", 0, shift=True)
    assert furnace.slots[2] == EMPTY and screen.inv.slots[1] == (I.IRON_INGOT, 3, 0)


def test_output_take_only():
    furnace = FurnaceState()
    screen = Screen(Inventory(), "furnace", furnace=furnace)
    screen.cursor = (B.DIRT, 3, 0)
    press(screen, "output", 0)
    assert furnace.slots[2] == EMPTY and screen.cursor == (B.DIRT, 3, 0)
    furnace.slots[2] = (I.IRON_INGOT, 2, 0)
    screen.cursor = (I.IRON_INGOT, 5, 0)
    press(screen, "output", 0)
    assert furnace.slots[2] == EMPTY and screen.cursor == (I.IRON_INGOT, 7, 0)


def test_fuel_slot_takes_only_fuel():
    furnace = FurnaceState()
    screen = Screen(Inventory(), "furnace", furnace=furnace)
    screen.cursor = (B.DIRT, 3, 0)
    press(screen, "fuel", 0)
    assert furnace.slots[1] == EMPTY and screen.cursor == (B.DIRT, 3, 0)
    screen.cursor = (B.PLANKS, 3, 0)
    press(screen, "fuel", 0)
    assert furnace.slots[1] == (B.PLANKS, 3, 0)


def test_close_returns_grid():
    screen = Screen(Inventory(), "table")
    screen.grid[0] = (B.STONE, 3, 0)
    screen.cursor = (B.DIRT, 2, 0)
    assert screen.close() == 0 and screen.message == ""
    assert screen.inv.slots[0] == (B.STONE, 3, 0) and screen.inv.slots[1] == (B.DIRT, 2, 0)
    assert screen.grid == [EMPTY] * 9 and screen.cursor == EMPTY


def test_close_full_inventory_loses_items():
    screen = Screen(Inventory(), "inventory")
    screen.inv.slots = [(B.STONE, 64, 0)] * 36
    screen.grid[0] = (B.DIRT, 3, 0)
    assert screen.close() == 3 and "3" in screen.message
