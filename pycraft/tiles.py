"""The game's own textures, drawn by code: 16x16 pixels per tile, a tile per number T_... of
blocks.py. A texture pack replaces some of them (packs.py); these fill in whatever it lacks. Also
the tiles as one atlas image, a tile resized to another size, and the color of each block seen
from afar."""
import numpy as np

# The tile numbers (T_...), block numbers and tables that the drawing below refers to
from pycraft.blocks import *  # noqa: F401,F403


def _noisy(rng, base, var):
    shade = 1 + rng.uniform(-var, var, (TILE, TILE, 1))
    return np.array(base, dtype=float) * shade


def _masonry(rng, base, mortar, row_h, brick_w, var, random_offsets=False):
    img = _noisy(rng, base, var)
    for row in range(TILE // row_h):
        offset = rng.integers(0, brick_w) if random_offsets else (row % 2) * brick_w // 2
        ys = slice(row * row_h, (row + 1) * row_h)
        # Each brick/stone gets its own brightness
        for start in range(-brick_w, TILE, brick_w):
            xs = slice(max(0, start + offset), max(0, start + offset + brick_w))
            img[ys, xs] *= rng.uniform(0.85, 1.1)
        img[row * row_h + row_h - 1, :] = mortar
        for x in range(TILE):
            if (x + offset) % brick_w == brick_w - 1:
                img[ys, x] = mortar
    return img


def _ore(rng, stone, color, count):
    img = stone.copy()
    for _ in range(count):
        y, x = rng.integers(1, TILE - 2, 2)
        img[y:y + 2, x:x + 2] = _noisy(rng, color, 0.15)[:2, :2]
    return img


def _bark(rng, base, var, streak):
    """Log side: vertical streaks of darker and lighter bark."""
    return _noisy(rng, base, var) * rng.uniform(1 - streak, 1 + streak * 0.6, (1, TILE, 1))


def _rings(rng, inner, bark_side):
    """Log top: growth rings, with the bark around the edge."""
    ys, xs = np.mgrid[0:TILE, 0:TILE]
    ring = np.maximum(abs(xs - 7.5), abs(ys - 7.5))
    top = _noisy(rng, inner, 0.05)
    top[(ring.astype(int) % 3) == 0] *= 0.8
    top[ring > 6.5] = bark_side[ring > 6.5]
    return top


def _side_with_top(rng, below, top, lo=2, hi=6):
    """A side texture: the 'below' texture with a ragged strip of 'top' along the upper edge."""
    side = below.copy()
    strip = np.zeros((TILE, TILE), dtype=bool)
    for x in range(TILE):
        depth = rng.integers(lo, hi)
        side[:depth, x] = top[:depth, x]
        strip[:depth, x] = True
    return side, strip


def _planks(rng, base):
    """Four boards, with gaps between them, a joint in each and some grain."""
    planks = _noisy(rng, base, 0.06)
    for row in range(4):
        planks[row * 4 + 3, :] *= 0.65  # gap between boards
        joint = rng.integers(0, TILE)
        planks[row * 4:row * 4 + 3, joint] *= 0.75
        planks[row * 4 + rng.integers(0, 3), rng.integers(0, TILE, 5)] *= 0.85  # grain
    return planks


def _blobs(rng, share, cells=4):
    """A mask of soft round patches covering about 'share' of the tile (moss, stains)."""
    coarse = rng.random((cells + 1, cells + 1))
    t = np.linspace(0, cells, TILE, endpoint=False)
    i, f = t.astype(int), t % 1
    f = f * f * (3 - 2 * f)
    rows = coarse[i] * (1 - f)[:, None] + coarse[i + 1] * f[:, None]  # blend the coarse grid in y...
    field = rows[:, i] * (1 - f) + rows[:, i + 1] * f  # ...then in x
    field += rng.uniform(-0.12, 0.12, (TILE, TILE))
    return field > np.quantile(field, 1 - share)


def _speckled(rng, base, var, specks):
    """A rock with grains of other colors: specks is a list of (color, share of the texels)."""
    img = _noisy(rng, base, var)
    for color, share in specks:
        grains = rng.random((TILE, TILE)) < share
        img[grains] = _noisy(rng, color, 0.08)[grains]
    return img


def _bevel(img, light=1.12, dark=0.78):
    """A raised square: lit along the top and left edges, shaded along the bottom and right ones."""
    img = img.copy()
    img[0, :] *= light
    img[:, 0] *= light
    img[-1, :] *= dark
    img[:, -1] *= dark
    return img


def _wool_weave(rng):
    """The pattern of woven threads shared by every color of wool, as brightness around 1."""
    ys, xs = np.mgrid[0:TILE, 0:TILE]
    across = (xs // 4 + ys // 4) % 2 == 0  # squares of 4x4 texels, threads across then down, in turn
    weave = np.where(np.where(across, ys, xs) % 2 == 0, 1.05, 0.93)
    return weave[..., None] * (1 + rng.uniform(-0.04, 0.04, (TILE, TILE, 1)))


def _paint(img, seen, ys, xs, color, rng, var=0.1):
    """Paint texels (ys, xs) of a plant tile in a slightly noisy color, and make them visible."""
    ys, xs = (a.ravel() for a in np.broadcast_arrays(np.clip(ys, 0, TILE - 1), np.clip(xs, 0, TILE - 1)))
    img[ys, xs] = np.array(color, dtype=float) * (1 + rng.uniform(-var, var, (ys.size, 1)))
    seen[ys, xs] = True


def _stalk(x, height, lean=0.0):
    """Texels (ys, xs) of a stalk or blade one texel thick, growing up from the bottom row and bending
    sideways, lean texels at its tip."""
    t = np.arange(height)
    return TILE - 1 - t, np.rint(x + lean * (t / max(height - 1, 1)) ** 2).astype(int)


def _blob(cx, cy, rx, ry):
    """Texels (ys, xs) inside an ellipse: a flower's head, a tuft of leaves."""
    ys, xs = np.mgrid[0:TILE, 0:TILE]
    return np.nonzero(((xs - cx) / rx) ** 2 + ((ys - cy) / ry) ** 2 <= 1)


def _plant_tiles(rng, tiles, alpha, tint):
    """The plants' tiles: stalks, leaves and flowers drawn on a see-through background."""
    def new(t, tinted=False):
        img, seen = np.zeros((TILE, TILE, 3)), np.zeros((TILE, TILE), dtype=bool)
        tiles[t], alpha[t] = img, seen
        if tinted:  # colored by the biome, like the grass
            tint[t] = np.ones((TILE, TILE), dtype=bool)
        return img, seen

    roots = np.linspace(1.1, 0.7, TILE)[:, None, None]  # darker toward the ground
    img, seen = new(T_TALL_GRASS, tinted=True)
    for x in rng.choice(np.arange(1, 15), 11, replace=False):  # blades of different heights
        _paint(img, seen, *_stalk(x, rng.integers(7, 16), rng.uniform(-2.5, 2.5)), (190, 190, 190), rng, 0.15)
    img *= roots

    img, seen = new(T_FERN, tinted=True)
    for x, height, lean in ((7, 15, 0.5), (5, 11, -4.5), (10, 12, 4.5)):  # three fronds
        ys, xs = _stalk(x, height, lean)
        _paint(img, seen, ys, xs, (180, 180, 180), rng, 0.08)
        for i in range(2, height - 1, 2):  # leaflets on both sides, shorter toward the tip
            n = np.arange(1 + (height - i) // 5)
            for side in (-1, 1):
                _paint(img, seen, ys[i] - (n + 1) // 2, xs[i] + side * (n + 1), (210, 210, 210), rng, 0.12)
    img *= roots

    img, seen = new(T_DEAD_BUSH)
    _paint(img, seen, np.arange(11, TILE), 7, (110, 78, 46), rng)
    for twig in range(6):  # thin twigs wandering up and outward
        steps = rng.integers(4, 10)
        side = 1 if twig % 2 else -1
        xs = 7 + np.cumsum(np.where(rng.random(steps) < 0.6, side, 0))
        _paint(img, seen, rng.integers(10, 14) - np.arange(1, steps + 1), xs, (128, 92, 56), rng, 0.15)

    stem, leaf = (62, 112, 40), (74, 130, 46)

    def flower(t, height, x=7):
        img, seen = new(t)
        _paint(img, seen, *_stalk(x, height, rng.uniform(-0.6, 0.6)), stem, rng)
        y = rng.integers(11, 14)
        _paint(img, seen, [y, y - 1], [x + 1, x + 2], leaf, rng)  # a leaf on the stem
        return img, seen

    img, seen = flower(T_POPPY, 11)
    _paint(img, seen, *_blob(7.5, 4.5, 3.2, 2.6), (200, 34, 30), rng, 0.12)
    _paint(img, seen, [4, 4], [7, 8], (40, 30, 22), rng)
    img, seen = flower(T_DANDELION, 9)
    _paint(img, seen, *_blob(7.5, 6, 2.3, 2.0), (245, 208, 40), rng, 0.12)
    img, seen = flower(T_BLUE_ORCHID, 10, 6)
    _paint(img, seen, *_stalk(10, 8, 0.5), stem, rng)
    _paint(img, seen, *_blob(6, 5, 1.9, 1.6), (70, 160, 232), rng, 0.12)
    _paint(img, seen, *_blob(10.5, 7, 1.6, 1.4), (70, 160, 232), rng, 0.12)
    img, seen = flower(T_CORNFLOWER, 11)
    _paint(img, seen, *_blob(7.5, 4.5, 2.6, 1.8), (66, 96, 222), rng, 0.12)
    _paint(img, seen, [3, 2, 3, 2, 3], [5, 6, 8, 9, 10], (92, 120, 240), rng)  # the frayed petals
    img, seen = flower(T_OXEYE_DAISY, 10)
    _paint(img, seen, *_blob(7.5, 5, 3.4, 2.4), (236, 236, 228), rng, 0.05)
    _paint(img, seen, *_blob(7.5, 5, 1.2, 0.9), (230, 185, 40), rng)
    img, seen = flower(T_ALLIUM, 13)
    _paint(img, seen, *_blob(7.5, 3.5, 3.2, 3.0), (165, 85, 205), rng, 0.2)

    img, seen = new(T_OAK_SAPLING)
    ys, xs = _blob(7.5, 5.5, 4.5, 4.0)
    some = rng.random(ys.size) < 0.7  # a sparse tuft of leaves
    _paint(img, seen, ys[some], xs[some], (70, 120, 42), rng, 0.2)
    _paint(img, seen, np.arange(8, TILE), 7, (100, 75, 45), rng)  # the trunk


def build_atlas(seed=7):
    """The generated tiles as a (256, 256, 4) uint8 atlas of 16x16 tiles (see tiles_to_atlas)."""
    return tiles_to_atlas(build_tiles(seed))


def tiles_to_atlas(tiles):
    """Tiles of any size, brought down to 16x16 and laid out in a 16x16 grid: a (256, 256, 4)
    uint8 atlas, the layout of the icons Pyxel draws."""
    small = tiles if tiles.shape[1] == TILE else np.stack([resize_tile(t, TILE) for t in tiles])
    grid = small.reshape(ATLAS_TILES, ATLAS_TILES, TILE, TILE, 4)
    return grid.transpose(0, 2, 1, 3, 4).reshape(TILE * ATLAS_TILES, TILE * ATLAS_TILES, 4)


def resize_tile(tile, n):
    """A (s, s, 4) tile made (n, n, 4). Bigger: each texel repeated (nearest). Smaller: each texel
    is a block of texels, its alpha the most common kind among them (see-through, tinted by the
    biome or plain; ties go to the more opaque) and its color their average, over the texels of
    that kind."""
    s = tile.shape[0]
    if s == n:
        return tile.copy()
    if n > s or s % n:
        idx = (np.arange(n) * s) // n  # nearest texel
        return tile[idx][:, idx].copy()
    k = s // n
    blocks_ = tile.reshape(n, k, n, k, 4).transpose(0, 2, 1, 3, 4).reshape(n, n, k * k, 4)
    alpha = blocks_[..., 3]
    kinds = np.array([0, TINT_ALPHA, 255])
    counts = np.stack([(alpha == a).sum(-1) for a in kinds], -1)  # (n, n, 3)
    # Prefer the more opaque kind on ties: argmax over reversed counts
    pick = 2 - np.argmax(counts[..., ::-1], axis=-1)
    out_a = kinds[pick]
    same = alpha == out_a[..., None]
    rgb = blocks_[..., :3].astype(np.float64)
    out_rgb = (rgb * same[..., None]).sum(2) / np.maximum(same.sum(-1, keepdims=True), 1)
    out = np.empty((n, n, 4), np.uint8)
    out[..., :3] = np.clip(np.rint(out_rgb), 0, 255)
    out[..., 3] = out_a
    return out


def build_tiles(seed=7):
    """Return the generated tiles as a (256, 16, 16, 4) uint8 RGBA array, one per tile number.

    Alpha 0 = see-through, TINT_ALPHA = colored by the biome (the texture itself is grey there)."""
    rng = np.random.default_rng(seed)
    tiles, alpha = {}, {}
    tint = {}  # tile -> mask of texels colored by the biome
    full = np.ones((TILE, TILE), dtype=bool)

    grey_grass = _noisy(rng, (204, 204, 204), 0.18)
    tiles[T_GRASS_TOP], tint[T_GRASS_TOP] = grey_grass, full

    dirt = _noisy(rng, (134, 96, 67), 0.12)
    dirt[rng.random((TILE, TILE)) < 0.12] *= 0.72
    tiles[T_DIRT] = dirt
    tiles[T_GRASS_SIDE], tint[T_GRASS_SIDE] = _side_with_top(rng, dirt, grey_grass)

    stone = _noisy(rng, (125, 125, 125), 0.08)
    for _ in range(10):
        y, x = rng.integers(0, TILE - 1, 2)
        stone[y, x:x + 2] *= 0.75
    tiles[T_STONE] = stone
    tiles[T_COAL] = _ore(rng, stone, (30, 30, 30), 6)
    tiles[T_IRON] = _ore(rng, stone, (216, 175, 147), 6)
    tiles[T_GOLD] = _ore(rng, stone, (250, 215, 60), 5)
    tiles[T_DIAMOND] = _ore(rng, stone, (95, 225, 215), 5)
    tiles[T_BEDROCK] = _noisy(rng, (70, 70, 70), 0.6)
    deepslate = _noisy(rng, (78, 78, 84), 0.1) * rng.uniform(0.85, 1.1, (TILE, 1, 1))  # layered
    tiles[T_DEEPSLATE] = deepslate

    tiles[T_COBBLE] = _masonry(rng, (122, 122, 122), (72, 72, 72), 4, 5, 0.12, random_offsets=True)
    tiles[T_BRICK] = _masonry(rng, (150, 74, 58), (178, 170, 160), 4, 8, 0.08)

    tiles[T_PLANKS] = _planks(rng, (162, 130, 78))

    # Logs and leaves of the five kinds of trees. Oak, jungle and acacia leaves take the biome color.
    for side_t, top_t, bark, inner, streak in [
            (T_LOG_SIDE, T_LOG_TOP, (102, 81, 51), (176, 143, 90), 0.28),
            (T_SPRUCE_LOG_SIDE, T_SPRUCE_LOG_TOP, (60, 42, 24), (120, 88, 52), 0.3),
            (T_JUNGLE_LOG_SIDE, T_JUNGLE_LOG_TOP, (88, 68, 28), (165, 118, 72), 0.25),
            (T_ACACIA_LOG_SIDE, T_ACACIA_LOG_TOP, (104, 98, 88), (175, 92, 50), 0.2)]:
        tiles[side_t] = _bark(rng, bark, 0.05, streak)
        tiles[top_t] = _rings(rng, inner, tiles[side_t])
    birch = _noisy(rng, (216, 214, 204), 0.04)
    for _ in range(9):  # black marks on the white bark
        y, x = rng.integers(0, TILE, 2)
        birch[y, x:x + rng.integers(2, 5)] = (40, 40, 36)
    tiles[T_BIRCH_LOG_SIDE] = birch
    tiles[T_BIRCH_LOG_TOP] = _rings(rng, (200, 180, 130), birch)

    for leaves_t, color, holes, tinted in [(T_LEAVES, (204, 204, 204), 0.18, True),
                                           (T_JUNGLE_LEAVES, (204, 204, 204), 0.12, True),
                                           (T_ACACIA_LEAVES, (204, 204, 204), 0.22, True),
                                           (T_SPRUCE_LEAVES, (46, 78, 46), 0.16, False),
                                           (T_BIRCH_LEAVES, (110, 150, 66), 0.18, False)]:
        tiles[leaves_t] = _noisy(rng, color, 0.25)
        alpha[leaves_t] = rng.random((TILE, TILE)) >= holes
        if tinted:
            tint[leaves_t] = full

    tiles[T_SAND] = _noisy(rng, (219, 207, 163), 0.05)
    tiles[T_RED_SAND] = _noisy(rng, (190, 102, 46), 0.06)
    sandstone_top = _noisy(rng, (216, 201, 150), 0.04)
    tiles[T_SANDSTONE_TOP] = sandstone_top
    side = _noisy(rng, (210, 193, 140), 0.04)
    side[[3, 4, 11]] *= 0.9  # horizontal layers
    side[:2] = sandstone_top[:2]
    tiles[T_SANDSTONE_SIDE] = side
    tiles[T_TERRACOTTA] = _noisy(rng, (152, 94, 67), 0.04)
    tiles[T_ORANGE_TERRACOTTA] = _noisy(rng, (162, 84, 38), 0.04)
    tiles[T_WHITE_TERRACOTTA] = _noisy(rng, (210, 178, 161), 0.04)
    tiles[T_CLAY] = _noisy(rng, (160, 166, 180), 0.04)
    tiles[T_MUD] = _noisy(rng, (62, 56, 56), 0.1)

    # Moss over dark lava rock: olive clumps, the rock showing through in gaps
    moss = _noisy(rng, (96, 120, 52), 0.14)
    for _ in range(26):  # the bumps of a thick carpet
        y, x = rng.integers(0, TILE - 2, 2)
        moss[y:y + 2, x:x + 2] *= rng.uniform(0.7, 1.3)
    moss[rng.random((TILE, TILE)) < 0.12] *= 0.45
    tiles[T_MOSS] = moss

    gravel = _noisy(rng, (128, 123, 118), 0.12)
    for _ in range(22):  # pebbles
        y, x = rng.integers(0, TILE - 1, 2)
        gravel[y:y + 2, x:x + 2] *= rng.uniform(0.6, 1.3)
    tiles[T_GRAVEL] = gravel

    tiles[T_SNOW] = _noisy(rng, (240, 245, 250), 0.04)
    ice = _noisy(rng, (160, 198, 245), 0.05)
    ys, xs = np.mgrid[0:TILE, 0:TILE]
    ice[(xs + 2 * ys) % 11 == 0] *= 1.12  # streaks
    tiles[T_ICE] = ice

    podzol = _noisy(rng, (110, 78, 38), 0.12)
    podzol[rng.random((TILE, TILE)) < 0.2] *= 0.65
    tiles[T_PODZOL_TOP] = podzol
    tiles[T_PODZOL_SIDE], _ = _side_with_top(rng, dirt, podzol, 2, 4)

    cactus = _noisy(rng, (78, 128, 40), 0.08)
    cactus[:, [0, 15]] *= 0.7
    cactus[:, [4, 11]] *= 0.82  # ridges
    cactus[rng.integers(0, TILE, 10), rng.choice([2, 7, 9, 13], 10)] = (220, 220, 180)  # spines
    tiles[T_CACTUS_SIDE] = cactus
    top = _noisy(rng, (100, 150, 52), 0.06)
    top[(np.maximum(abs(xs - 7.5), abs(ys - 7.5)) > 6.5)] *= 0.75
    tiles[T_CACTUS_TOP] = top

    ring = np.maximum(abs(xs - 7.5), abs(ys - 7.5))
    glass = np.full((TILE, TILE, 3), (215, 235, 240), dtype=float)
    glass_alpha = (ring > 6.5)  # frame
    for i in range(3):  # a few diagonal shine streaks
        glass_alpha |= (xs - ys == 4 + i) & (xs < 10)
    tiles[T_GLASS], alpha[T_GLASS] = glass, glass_alpha

    tiles[T_WATER], tint[T_WATER] = _noisy(rng, (204, 204, 204), 0.1), full
    # Plants get their own random numbers, so the tiles made before and after them stay as they were
    _plant_tiles(np.random.default_rng(seed + 1), tiles, alpha, tint)

    # --- Building blocks (made after the older tiles, which then stay exactly as they were) ---
    for planks_t, color in [(T_SPRUCE_PLANKS, (115, 85, 52)), (T_BIRCH_PLANKS, (196, 179, 123)),
                            (T_JUNGLE_PLANKS, (160, 115, 81)), (T_ACACIA_PLANKS, (169, 92, 51))]:
        tiles[planks_t] = _planks(rng, color)

    moss_green = (84, 108, 50)
    bricks = _masonry(rng, (124, 124, 124), (84, 84, 84), 8, 16, 0.05)
    tiles[T_STONE_BRICKS] = bricks
    mossy = bricks.copy()
    patches = _blobs(rng, 0.35)
    mossy[patches] = _noisy(rng, moss_green, 0.18)[patches]
    tiles[T_MOSSY_STONE_BRICKS] = mossy
    cracked = bricks.copy()
    for _ in range(3):  # cracks: short zigzags across the bricks
        y, x = rng.integers(1, TILE - 1), rng.integers(0, 6)
        for _ in range(rng.integers(6, 11)):
            cracked[y, x] *= 0.55
            y, x = int(np.clip(y + rng.integers(-1, 2), 0, TILE - 1)), x + 1
            if x >= TILE:
                break
    tiles[T_CRACKED_STONE_BRICKS] = cracked
    cobble = _masonry(rng, (122, 122, 122), (72, 72, 72), 4, 5, 0.12, random_offsets=True)
    patches = _blobs(rng, 0.3)
    cobble[patches] = _noisy(rng, moss_green, 0.2)[patches]
    tiles[T_MOSSY_COBBLE] = cobble
    smooth = _noisy(rng, (158, 158, 158), 0.03)
    smooth[ring > 6.5] *= 0.82  # a darker rim
    tiles[T_SMOOTH_STONE] = smooth

    # Rocks, raw and polished: the polished ones are smoother squares with a raised edge
    for raw_t, polished_t, base, specks in [
            (T_GRANITE, T_POLISHED_GRANITE, (152, 106, 88), [((184, 134, 112), 0.18), ((104, 70, 62), 0.12)]),
            (T_DIORITE, T_POLISHED_DIORITE, (190, 190, 192), [((120, 120, 122), 0.16), ((236, 236, 236), 0.12)]),
            (T_ANDESITE, T_POLISHED_ANDESITE, (136, 136, 137), [((108, 108, 110), 0.18), ((164, 164, 164), 0.12)])]:
        tiles[raw_t] = _speckled(rng, base, 0.06, specks)
        tiles[polished_t] = _bevel(_speckled(rng, base, 0.03, [(color, share / 3) for color, share in specks]))

    def cut(top_color, side_color):  # cut sandstone: two smooth slabs, one above the other
        img = _noisy(rng, side_color, 0.03)
        img[[0, 8]] = _noisy(rng, top_color, 0.03)[[0, 8]] * 1.06
        img[[7, 15]] *= 0.84
        return img

    tiles[T_CUT_SANDSTONE] = cut((216, 201, 150), (212, 197, 145))
    def chiseled(top, color):  # a carved band in the middle, with a pattern of nested squares
        img = _noisy(rng, color, 0.03)
        img[[2, 13]] *= 0.82
        inside = (ys > 2) & (ys < 13)
        middle = np.maximum(abs(xs - 7.5), abs(ys - 7.5) * 1.6)
        img[inside & (middle.astype(int) % 3 == 1)] *= 0.8
        img[:2] = top[:2]
        img[14:] = top[14:]
        return img

    tiles[T_CHISELED_SANDSTONE] = chiseled(sandstone_top, (212, 197, 145))
    red_top = _noisy(rng, (181, 98, 33), 0.04)
    tiles[T_RED_SANDSTONE_TOP] = red_top
    red_side = _noisy(rng, (172, 90, 30), 0.04)
    red_side[[3, 4, 11]] *= 0.88  # horizontal layers
    red_side[:2] = red_top[:2]
    tiles[T_RED_SANDSTONE_SIDE] = red_side
    tiles[T_CUT_RED_SANDSTONE] = cut((181, 98, 33), (174, 92, 31))

    # Blocks of ore: metal plates, diamond facets, coal lumps
    def plate(base):
        img = _noisy(rng, base, 0.03)
        img[(xs + ys) % 8 == 3] *= 1.1  # diagonal shine
        img[[7, 8], 1:-1] *= np.array([0.86, 1.08])[:, None, None]  # a seam between two plates
        return _bevel(img, 1.15, 0.7)

    for block_t, base in [(T_IRON_BLOCK, (216, 216, 216)), (T_GOLD_BLOCK, (246, 206, 58)),
                          (T_DIAMOND_BLOCK, (98, 219, 212))]:
        tiles[block_t] = plate(base)
    coal = _noisy(rng, (30, 30, 32), 0.2)
    coal[rng.random((TILE, TILE)) < 0.12] = (58, 58, 62)  # glints
    tiles[T_COAL_BLOCK] = coal
    obsidian = _noisy(rng, (22, 16, 34), 0.25)
    obsidian[_blobs(rng, 0.15, cells=6)] = (60, 40, 94)  # purple streaks in the glass
    tiles[T_OBSIDIAN] = obsidian

    shelf = tiles[T_PLANKS].copy()  # two rows of books between the boards
    for y0 in (2, 9):
        x = 1
        while x < TILE - 1:
            width = min(rng.integers(1, 4), TILE - 1 - x)
            book = rng.choice([(120, 36, 30), (44, 70, 120), (52, 96, 46), (130, 98, 46), (92, 50, 90),
                               (150, 140, 120)])
            height = rng.integers(4, 6)
            shelf[y0 + 5 - height:y0 + 5, x:x + width] = _noisy(rng, book, 0.08)[:height, :width]
            shelf[y0 + 5 - height:y0 + 5, x] *= 0.8  # the spine's edge
            x += width
        shelf[y0:y0 + 5, [0, TILE - 1]] *= 0.6
    tiles[T_BOOKSHELF] = shelf

    hay = _bark(rng, (196, 162, 44), 0.1, 0.3)  # straw lying up and down
    hay[[3, 4, 11, 12]] = _noisy(rng, (128, 78, 30), 0.1)[[3, 4, 11, 12]]  # the bindings
    tiles[T_HAY_SIDE] = hay
    hay_top = _noisy(rng, (204, 172, 56), 0.16)  # the cut ends of the straw
    hay_top[ring > 6.5] *= 0.75
    tiles[T_HAY_TOP] = hay_top

    pumpkin = _bark(rng, (222, 132, 24), 0.05, 0.15)
    pumpkin[:, [0, 5, 10, 15]] *= 0.72  # the grooves between the ribs
    tiles[T_PUMPKIN_SIDE] = pumpkin
    pumpkin_top = _noisy(rng, (214, 126, 22), 0.05)
    pumpkin_top[(abs(xs - 7.5) + abs(ys - 7.5)).astype(int) % 4 == 0] *= 0.8
    pumpkin_top[6:10, 6:10] = _noisy(rng, (96, 82, 34), 0.1)[:4, :4]  # the stem
    tiles[T_PUMPKIN_TOP] = pumpkin_top

    melon = _noisy(rng, (106, 146, 30), 0.06)
    stripes = (xs + np.rint(1.2 * np.sin(ys * 0.8)).astype(int)) % 5 < 2  # wavy pale stripes
    melon[stripes] = _noisy(rng, (164, 186, 58), 0.06)[stripes]
    tiles[T_MELON_SIDE] = melon
    melon_top = _noisy(rng, (110, 150, 32), 0.06)
    pale = np.hypot(xs - 7.5, ys - 7.5).astype(int) % 4 < 2
    melon_top[pale] = _noisy(rng, (160, 182, 56), 0.06)[pale]
    melon_top[7:9, 7:9] = (86, 76, 30)
    tiles[T_MELON_TOP] = melon_top

    # Wool: one woven pattern, in 16 colors
    weave = _wool_weave(rng)
    wools = [(T_WHITE_WOOL, (233, 236, 236)), (T_ORANGE_WOOL, (240, 118, 20)),
             (T_MAGENTA_WOOL, (190, 68, 180)), (T_LIGHT_BLUE_WOOL, (58, 176, 218)),
             (T_YELLOW_WOOL, (248, 198, 40)), (T_LIME_WOOL, (112, 186, 26)),
             (T_PINK_WOOL, (238, 141, 172)), (T_GRAY_WOOL, (63, 68, 72)),
             (T_LIGHT_GRAY_WOOL, (142, 142, 135)), (T_CYAN_WOOL, (21, 138, 145)),
             (T_PURPLE_WOOL, (122, 42, 172)), (T_BLUE_WOOL, (53, 57, 158)),
             (T_BROWN_WOOL, (114, 72, 41)), (T_GREEN_WOOL, (84, 110, 28)),
             (T_RED_WOOL, (160, 39, 35)), (T_BLACK_WOOL, (22, 22, 27))]
    for wool_t, color in wools:
        tiles[wool_t] = np.array(color, dtype=float) * weave

    tiles[T_DEEPSLATE_BRICKS] = _masonry(rng, (72, 72, 78), (42, 42, 46), 4, 8, 0.08)
    tiles[T_POLISHED_DEEPSLATE] = _bevel(_noisy(rng, (74, 74, 78), 0.04), 1.2, 0.75)
    tiles[T_MUD_BRICKS] = _masonry(rng, (138, 106, 80), (100, 78, 62), 4, 8, 0.06)
    quartz = _noisy(rng, (236, 230, 222), 0.02)
    quartz[ring > 6.5] *= 0.92
    tiles[T_QUARTZ] = quartz
    for terracotta_t, color in [(T_YELLOW_TERRACOTTA, (186, 133, 35)), (T_RED_TERRACOTTA, (143, 61, 46)),
                                (T_BROWN_TERRACOTTA, (77, 51, 36)), (T_LIGHT_GRAY_TERRACOTTA, (135, 107, 98))]:
        tiles[terracotta_t] = _noisy(rng, color, 0.04)

    # --- The other full blocks of the classic block set ---
    tiles[T_COARSE_DIRT] = _speckled(rng, (119, 86, 59), 0.12, [((88, 63, 44), 0.18), ((150, 114, 84), 0.1)])
    mycelium = _speckled(rng, (112, 98, 108), 0.1, [((152, 132, 150), 0.16), ((82, 70, 82), 0.1)])
    tiles[T_MYCELIUM_TOP] = mycelium
    tiles[T_MYCELIUM_SIDE], _ = _side_with_top(rng, dirt, mycelium, 2, 4)
    farmland = _noisy(rng, (92, 62, 40), 0.1)  # tilled earth: furrows across
    farmland[ys % 4 == 0] *= 0.7
    farmland[ys % 4 == 1] *= 1.12
    tiles[T_FARMLAND] = farmland
    packed = _noisy(rng, (140, 178, 228), 0.04)
    packed[(xs - 2 * ys) % 13 == 0] *= 1.12
    packed[(3 * xs + ys) % 17 == 0] *= 0.86  # cracks in the old, packed ice
    tiles[T_PACKED_ICE] = packed
    for sponge_t, color in [(T_SPONGE, (196, 192, 74)), (T_WET_SPONGE, (160, 162, 62))]:
        sponge = _noisy(rng, color, 0.08)
        for _ in range(14):  # the pores
            y, x = rng.integers(0, TILE - 1, 2)
            sponge[y:y + 2, x:x + 2] *= 0.62
        tiles[sponge_t] = sponge
    netherrack = _speckled(rng, (112, 54, 52), 0.14, [((78, 30, 30), 0.22), ((146, 82, 78), 0.12)])
    tiles[T_NETHERRACK] = netherrack
    tiles[T_EMERALD_ORE] = _ore(rng, stone, (64, 206, 96), 4)
    tiles[T_LAPIS_ORE] = _ore(rng, stone, (36, 68, 190), 7)
    tiles[T_REDSTONE_ORE] = _ore(rng, stone, (210, 24, 20), 7)
    tiles[T_NETHER_QUARTZ_ORE] = _ore(rng, netherrack, (236, 228, 214), 8)
    soul = _noisy(rng, (84, 64, 51), 0.12)
    for _ in range(6):  # dark hollows in the sand, like faces
        y, x = rng.integers(1, TILE - 3, 2)
        soul[y, x:x + 3:2] *= 0.5  # two eyes...
        soul[y + 2, x:x + 3] *= 0.6  # ...and a mouth
    tiles[T_SOUL_SAND] = soul
    tiles[T_NETHER_BRICKS] = _masonry(rng, (70, 35, 41), (32, 17, 21), 4, 8, 0.08)
    end = _speckled(rng, (220, 222, 164), 0.05, [((196, 196, 136), 0.22), ((240, 242, 192), 0.1)])
    end[rng.random((TILE, TILE)) < 0.05] *= 0.8  # pits
    tiles[T_END_STONE] = end
    prismarine = _noisy(rng, (98, 156, 150), 0.08)
    prismarine[_blobs(rng, 0.35)] *= np.array([0.82, 0.9, 0.86])  # darker, greener patches
    prismarine[_blobs(rng, 0.2)] *= 1.12
    tiles[T_PRISMARINE] = prismarine
    tiles[T_PRISMARINE_BRICKS] = _masonry(rng, (100, 170, 156), (68, 118, 108), 4, 8, 0.05)
    dark = _noisy(rng, (52, 92, 76), 0.08)
    dark[[0, 7, 8, 15]] *= 0.65  # four square panels
    dark[:, [0, 7, 8, 15]] *= 0.65
    tiles[T_DARK_PRISMARINE] = dark
    tiles[T_BROWN_MUSHROOM] = _speckled(rng, (142, 106, 82), 0.08, [((170, 136, 110), 0.08)])
    red_cap = _noisy(rng, (184, 38, 36), 0.08)
    for _ in range(5):  # white spots
        y, x = rng.integers(0, TILE - 3, 2)
        red_cap[y:y + 3, x:x + 3] = _noisy(rng, (226, 222, 212), 0.05)[:3, :3]
    tiles[T_RED_MUSHROOM] = red_cap
    tiles[T_MUSHROOM_STEM] = _bark(rng, (206, 200, 184), 0.04, 0.08)
    slime = _noisy(rng, (112, 192, 92), 0.05)
    slime[ring > 6.5] *= 0.8
    slime[(ring > 2.5) & (ring < 4.5)] *= 0.86  # the denser core inside
    tiles[T_SLIME] = slime

    carved = _bevel(_noisy(rng, (124, 124, 124), 0.05))
    circle = np.hypot(xs - 7.5, ys - 7.5)
    carved[(circle > 3.5) & (circle < 5)] *= 0.72  # a carved ring
    carved[circle < 2] *= 1.1
    tiles[T_CHISELED_STONE_BRICKS] = carved
    chiseled_quartz = quartz.copy()
    chiseled_quartz[[2, 3, 12, 13]] *= 0.88  # carved bands, and lines between them
    chiseled_quartz[5:11, [4, 7, 8, 11]] *= 0.9
    tiles[T_CHISELED_QUARTZ] = chiseled_quartz
    pillar = _noisy(rng, (234, 228, 219), 0.02)
    pillar[:, [1, 14]] *= 0.88  # fluting down the pillar
    pillar[:, [5, 10]] *= 0.94
    tiles[T_QUARTZ_PILLAR_SIDE] = pillar
    pillar_top = _noisy(rng, (234, 228, 219), 0.02)
    pillar_top[(ring > 6.5) | ((ring > 3) & (ring < 4))] *= 0.88
    tiles[T_QUARTZ_PILLAR_TOP] = pillar_top
    tiles[T_CHISELED_RED_SANDSTONE] = chiseled(red_top, (174, 92, 31))
    lapis = _speckled(rng, (36, 64, 140), 0.08, [((62, 98, 192), 0.15), ((24, 40, 100), 0.1)])
    tiles[T_LAPIS_BLOCK] = _bevel(lapis, 1.2, 0.7)
    tiles[T_EMERALD_BLOCK] = plate((44, 178, 88))
    redstone = _speckled(rng, (170, 22, 12), 0.1, [((222, 52, 30), 0.15), ((110, 10, 8), 0.12)])
    tiles[T_REDSTONE_BLOCK] = _bevel(redstone, 1.2, 0.7)
    tiles[T_DARK_OAK_LOG_SIDE] = _bark(rng, (62, 47, 29), 0.05, 0.3)
    tiles[T_DARK_OAK_LOG_TOP] = _rings(rng, (86, 62, 38), tiles[T_DARK_OAK_LOG_SIDE])
    tiles[T_DARK_OAK_PLANKS] = _planks(rng, (68, 45, 22))
    tiles[T_DARK_OAK_LEAVES] = _noisy(rng, (44, 86, 32), 0.25)
    alpha[T_DARK_OAK_LEAVES] = rng.random((TILE, TILE)) >= 0.14
    for terracotta_t, color in [(T_MAGENTA_TERRACOTTA, (150, 88, 109)), (T_LIGHT_BLUE_TERRACOTTA, (113, 108, 137)),
                                (T_LIME_TERRACOTTA, (103, 117, 53)), (T_PINK_TERRACOTTA, (161, 78, 78)),
                                (T_GRAY_TERRACOTTA, (57, 42, 35)), (T_CYAN_TERRACOTTA, (86, 91, 91)),
                                (T_PURPLE_TERRACOTTA, (118, 70, 86)), (T_BLUE_TERRACOTTA, (74, 59, 91)),
                                (T_GREEN_TERRACOTTA, (76, 83, 42)), (T_BLACK_TERRACOTTA, (37, 22, 16))]:
        tiles[terracotta_t] = _noisy(rng, color, 0.04)
    # Stained glass: the glass' frame and shine, in the colors of the wools
    for (_, color), glass_t in zip(wools, [T_WHITE_STAINED_GLASS, T_ORANGE_STAINED_GLASS, T_MAGENTA_STAINED_GLASS,
                                           T_LIGHT_BLUE_STAINED_GLASS, T_YELLOW_STAINED_GLASS, T_LIME_STAINED_GLASS,
                                           T_PINK_STAINED_GLASS, T_GRAY_STAINED_GLASS, T_LIGHT_GRAY_STAINED_GLASS,
                                           T_CYAN_STAINED_GLASS, T_PURPLE_STAINED_GLASS, T_BLUE_STAINED_GLASS,
                                           T_BROWN_STAINED_GLASS, T_GREEN_STAINED_GLASS, T_RED_STAINED_GLASS,
                                           T_BLACK_STAINED_GLASS]):
        tiles[glass_t] = np.minimum(np.array(color, dtype=float) * 1.1 + 24, 255) * np.ones((TILE, TILE, 1))
        alpha[glass_t] = glass_alpha

    # Machines: they only look the part (no redstone, no crafting)
    planks = tiles[T_PLANKS]
    table_top = planks.copy()
    table_top[[0, 15]] *= 0.7  # a crafting grid on the table
    table_top[:, [0, 15]] *= 0.7
    table_top[[5, 10], 1:-1] *= 0.75
    table_top[1:-1, [5, 10]] *= 0.75
    tiles[T_CRAFTING_TABLE_TOP] = table_top
    table_side = planks.copy()
    table_side[:3] = table_top[:3] * 0.85  # the edge of the table top
    table_side[3] *= 0.6
    saw = table_side.copy()
    saw[5:7, 3:12] = (150, 150, 154)  # a saw...
    saw[7, 3:12:2] = (120, 120, 124)  # ...its teeth...
    saw[4:8, 11:14] = (92, 60, 34)  # ...and its handle
    tiles[T_CRAFTING_TABLE_SIDE] = saw
    tools = table_side.copy()
    tools[5:8, 3:8] = (140, 140, 146)  # a hammer
    tools[8:14, 5] = (92, 60, 34)
    tools[5:12, 11] = (150, 150, 154)  # a file
    tools[12:14, 10:13] = (92, 60, 34)
    tiles[T_CRAFTING_TABLE_FRONT] = tools
    furnace = _noisy(rng, (112, 112, 112), 0.08)
    furnace[ring > 6.5] *= 0.75  # a darker rim
    tiles[T_FURNACE_SIDE] = furnace
    furnace_top = _noisy(rng, (122, 122, 122), 0.06)
    furnace_top[ring > 6.5] *= 0.8
    tiles[T_FURNACE_TOP] = furnace_top
    front = furnace.copy()
    front[2:4, 4:12] = (52, 52, 52)  # the vent...
    front[8, 3:13] *= 1.2
    front[9:14, 4:12] = (28, 26, 26)  # ...and the door of the fire
    tiles[T_FURNACE_FRONT] = front
    front = furnace.copy()
    front[(circle > 3) & (circle < 4.3)] *= 0.7  # the dispenser's round mouth
    front[circle <= 3] = (24, 24, 24)
    tiles[T_DISPENSER_FRONT] = front
    front = furnace.copy()
    front[ring == 2.5] *= 0.7  # the dropper's square mouth
    front[ring < 2.5] = (24, 24, 24)
    tiles[T_DROPPER_FRONT] = front
    note = _noisy(rng, (106, 70, 50), 0.06)  # a wooden box with a grille
    note[ring > 6.5] *= 0.7
    note[(ring < 5.5) & (xs % 3 == 1) & (ys % 3 == 1)] *= 0.4
    tiles[T_NOTE_BLOCK] = note
    jukebox = _noisy(rng, (110, 72, 52), 0.06)
    jukebox[ring > 6.5] *= 0.7
    jukebox[(ring > 5) & (ring < 6)] *= 0.85
    tiles[T_JUKEBOX_SIDE] = jukebox
    jukebox_top = jukebox.copy()
    jukebox_top[7:9, 3:13] = (20, 16, 14)  # the slot for the discs
    tiles[T_JUKEBOX_TOP] = jukebox_top
    tnt = _noisy(rng, (206, 56, 32), 0.06)
    tnt[:, ::4] *= 0.8  # the sticks
    tnt[5:11] = _noisy(rng, (226, 222, 214), 0.03)[5:11]  # the label, and its letters
    for dy, row in enumerate(["111.1..1.111", ".1..11.1..1.", ".1..1.11..1.", ".1..1..1..1."]):
        for dx, c in enumerate(row):
            if c == "1":
                tnt[6 + dy, 2 + dx] = (30, 24, 22)
    tiles[T_TNT_SIDE] = tnt
    tnt_top = _noisy(rng, (196, 54, 32), 0.06)
    tnt_top[np.hypot(xs % 5 - 2, ys % 5 - 2) > 2.1] *= 0.6  # the ends of the sticks
    tnt_top[7:9, 7:9] = (40, 40, 40)  # the fuse
    tiles[T_TNT_TOP] = tnt_top
    piston = _noisy(rng, (116, 116, 116), 0.1)  # stone, with the wooden head on top
    piston[:4] = planks[:4]
    piston[4] *= 0.6
    piston[5:, 6:10] *= 0.82  # the rod inside
    tiles[T_PISTON_SIDE] = piston
    head = planks.copy()
    head[ring > 6.5] *= 0.75
    head[ring < 2.5] = (150, 150, 150)  # the iron in the middle of the head
    tiles[T_PISTON_TOP] = head
    sticky = head.copy()
    glue = ring < 4.5
    sticky[glue] = _noisy(rng, (112, 192, 92), 0.08)[glue]
    tiles[T_STICKY_PISTON_TOP] = sticky
    bottom = _noisy(rng, (110, 110, 110), 0.1)
    bottom[ring > 6.5] *= 0.75
    bottom[ring < 2.5] = (40, 40, 40)
    tiles[T_PISTON_BOTTOM] = bottom
    command = _bevel(_noisy(rng, (180, 128, 90), 0.05), 1.15, 0.7)
    screen = (ring > 2.5) & (ring < 5.5)
    command[screen] = (64, 62, 60)  # a frame of circuits...
    command[screen & ((xs + ys) % 3 == 0)] = (120, 190, 170)  # ...with their lights
    tiles[T_COMMAND_BLOCK] = command

    # Lamps (see GLOWING)
    glow = _noisy(rng, (196, 142, 76), 0.12)
    bright = _blobs(rng, 0.4, cells=6)
    glow[bright] = _noisy(rng, (255, 226, 140), 0.06)[bright]
    glow[rng.random((TILE, TILE)) < 0.08] *= 0.6  # cracks between the crystals
    tiles[T_GLOWSTONE] = glow
    lantern = _noisy(rng, (214, 230, 222), 0.04)
    lantern[ring.astype(int) % 3 == 1] = (160, 206, 196)  # nested squares of light
    lantern[ring < 1.5] = (250, 252, 246)
    tiles[T_SEA_LANTERN] = lantern
    lamp = _noisy(rng, (236, 184, 108), 0.08)
    lamp[_blobs(rng, 0.3)] *= 1.1
    lamp[[0, 5, 10, 15]] = (84, 54, 34)  # the lamp's frame
    lamp[:, [0, 5, 10, 15]] = (84, 54, 34)
    tiles[T_REDSTONE_LAMP] = lamp
    lamp_off = lamp * 0.55  # the same lamp, unlit
    lamp_off[[0, 5, 10, 15]] = (70, 46, 30)
    lamp_off[:, [0, 5, 10, 15]] = (70, 46, 30)
    tiles[T_REDSTONE_LAMP_OFF] = lamp_off

    # Redstone parts: a stick in the middle of the tile, as the boxes of shapes.py take it. Their
    # own random numbers, so the tiles drawn after them stay as they were
    rrng = np.random.default_rng(seed + 101)
    stick = np.zeros((TILE, TILE), bool)
    stick[6:, 7:9] = True
    lever = np.zeros((TILE, TILE, 3))
    lever[stick] = _noisy(rrng, (120, 92, 56), 0.12)[stick]
    lever[6, 7:9] = (150, 118, 74)
    tiles[T_LEVER], alpha[T_LEVER] = lever, stick
    for t, flame in ((T_REDSTONE_TORCH_ON, (255, 40, 24)), (T_REDSTONE_TORCH_OFF, (96, 28, 22))):
        torch = lever.copy()
        torch[6:8, 7:9] = flame  # the tip
        torch[5, 7:9] = flame
        lit = stick.copy()
        lit[5, 7:9] = True
        tiles[t], alpha[t] = torch, lit
    dust = np.zeros((TILE, TILE, 3))  # grey: colored by its power (see shapes.py)
    cross = (np.abs(xs - 7.5) < 3) | (np.abs(ys - 7.5) < 3)
    cross &= rrng.random((TILE, TILE)) < 0.85
    dust[cross] = _noisy(rrng, (210, 210, 210), 0.12)[cross]
    tiles[T_REDSTONE_DUST], alpha[T_REDSTONE_DUST], tint[T_REDSTONE_DUST] = dust, cross, cross
    for t, line in ((T_REPEATER_OFF, (110, 30, 24)), (T_REPEATER_ON, (240, 40, 28))):
        rep = _noisy(rrng, (160, 160, 160), 0.05)  # smooth stone, with its line of dust
        rep[1:15, 7:9] = line
        rep[[0, 15]] *= 0.8
        rep[:, [0, 15]] *= 0.8
        tiles[t] = rep
    inner = _noisy(rrng, (116, 116, 116), 0.1)  # inside the piston, once its head is out
    inner[(np.abs(xs - 7.5) < 2) & (np.abs(ys - 7.5) < 2)] = (60, 54, 48)
    tiles[T_PISTON_INNER] = inner
    # The furnace's front with a fire in its door, drawn with its own random numbers as well
    frng = np.random.default_rng(seed + 202)
    lit_front = tiles[T_FURNACE_FRONT].copy()
    fire = _noisy(frng, (236, 110, 24), 0.12)
    fire[3:, :] = _noisy(frng, (255, 176, 40), 0.1)[3:, :]  # the heart of the fire is yellower
    lit_front[10:14, 5:11] = fire[:4, :6]
    lit_front[13, 4:12] = (200, 70, 16)  # embers along the bottom
    tiles[T_FURNACE_FRONT_ON] = lit_front
    face = tiles[T_PUMPKIN_SIDE].copy()  # a pumpkin with a carved face, lit from inside
    candle = (255, 208, 84)
    for x in (3, 10):  # the eyes...
        face[5:7, x:x + 3] = candle
        face[4, x + 1] = candle
    face[9:12, 3:13] = candle  # ...and the mouth, with its teeth
    face[9, [6, 9]] = tiles[T_PUMPKIN_SIDE][9, [6, 9]]
    face[11, [4, 11]] = tiles[T_PUMPKIN_SIDE][11, [4, 11]]
    tiles[T_JACK_O_LANTERN] = face

    cage = np.full((TILE, TILE, 3), (44, 50, 58), dtype=float) * (1 + rng.uniform(-0.1, 0.1, (TILE, TILE, 1)))
    tiles[T_SPAWNER], alpha[T_SPAWNER] = cage, (xs % 5 == 0) | (ys % 5 == 0) | (ring > 6.5)  # the bars

    out = np.zeros((ATLAS_TILES * ATLAS_TILES, TILE, TILE, 4))
    for t, img in tiles.items():
        a = np.where(alpha.get(t, full), 255.0, 0.0)
        a[(a > 0) & tint.get(t, ~full)] = TINT_ALPHA
        out[t, ..., :3] = img
        out[t, ..., 3] = a
    return np.clip(out, 0, 255).astype(np.uint8)


def block_colors(tiles):
    """Average color (0-1) of each block's top face, for the distant terrain. Tinted texels count as
    white: the distant terrain multiplies them by the biome color itself. tiles: (256, N, N, 4)."""
    colors = np.zeros((NUM_BLOCKS, 3))
    for block in range(1, NUM_BLOCKS):
        cell = tiles[int(BLOCK_TILES[block][2])].astype(float)
        seen = cell[..., 3] > 0
        if not seen.any():
            seen = np.ones_like(seen)  # nothing to see (a pack's clear glass): all its texels
        rgb = cell[..., :3][seen] / 255
        if (cell[..., 3][seen] == TINT_ALPHA).all():
            rgb = rgb / 0.8  # grey texels, about 204/255
        colors[block] = rgb.mean(axis=0)
    return colors
