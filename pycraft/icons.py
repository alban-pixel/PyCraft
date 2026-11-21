"""The block and item icons of the hotbar and the inventories: the tiles shrunk to 16x16 pixels and 48 colors
of Pyxel's palette that suit them."""
import numpy as np

from pycraft import items
from pycraft.blocks import ATLAS_TILES, BLOCK_TILES, PLACEABLE, TILE, TINT_ALPHA, T_REDSTONE_DUST, T_WATER
from pycraft.render import FIXED_COLORS, oklab_to_srgb, srgb_to_oklab
from pycraft.tiles import tiles_to_atlas


ICON_GREEN, ICON_BLUE = (0.5, 0.72, 0.33), (0.25, 0.45, 0.95)  # grass/leaves and water in the inventory
ICON_RED = (0.9, 0.12, 0.08)  # redstone dust in the inventory


def _kmeans(points, weight, centers, rounds):
    """Move the centers to the weighted average of the points nearest to each, a few times."""
    for _ in range(rounds):
        nearest = np.argmin(((points[:, None] - centers[None]) ** 2).sum(-1), axis=1)
        for k in range(len(centers)):
            members = nearest == k
            if members.any():
                centers[k] = np.average(points[members], axis=0, weights=weight[members])
    return centers


def _spread(points, weight, count):
    """Starting centers far apart: each next one is the point worst served by those before it."""
    centers = [points[np.argmax(weight)]]
    gap = ((points - centers[0]) ** 2).sum(-1)
    for _ in range(count - 1):
        centers.append(points[np.argmax(gap * weight)])
        gap = np.minimum(gap, ((points - centers[-1]) ** 2).sum(-1))
    return np.array(centers)


def item_atlas(item_tiles):
    """The item icons laid out as the block icons are (16 per row), padded with empty tiles: (256, 256, 4)."""
    padded = np.zeros((ATLAS_TILES * ATLAS_TILES, TILE, TILE, 4), dtype=np.uint8)
    padded[:len(item_tiles)] = item_tiles
    return tiles_to_atlas(padded)


def _summaries(lab, seen, tiles):
    """Each of these tiles of an atlas summed up in at most 4 colors: (colors, their share of the tile)."""
    points, weight = [], []
    for t in tiles:
        ty, tx = divmod(t, ATLAS_TILES)
        cell = (slice(ty * TILE, (ty + 1) * TILE), slice(tx * TILE, (tx + 1) * TILE))
        texels = lab[cell][seen[cell]]
        if len(texels) == 0:
            continue  # nothing to see (a pack's clear glass): no colors to keep for it
        ones = np.ones(len(texels))
        summary = _kmeans(texels, ones, _spread(texels, ones, 4), 8)
        share = np.bincount(np.argmin(((texels[:, None] - summary[None]) ** 2).sum(-1), axis=1), minlength=4)
        points.append(summary[share > 0])
        weight.append(share[share > 0] / len(texels))
    return points, weight


def icon_palette(atlas, item_atlas=None):
    """The icons for pyxel.blt: 48 colors that suit them and every pixel as the index of its
    nearest one, 16-63 (0 where transparent). Returns (colors, block indices, item indices), the
    last None without an item atlas (items.build_item_tiles laid out by item_atlas): the item icons
    share the 48 colors with the blocks'. Texels that take the biome color get a typical green
    (blue for water).
    Each icon is first summed up in 4 colors (its main color, darker and lighter texels, specks),
    and the 48 colors are a k-means of those, every icon counting the same: a tile of a rare color
    (a wool, a block of diamond) keeps its own color instead of the many greys and browns taking
    most of the palette."""
    rgb = atlas[..., :3].astype(float) / 255
    tint = np.broadcast_to(np.array(ICON_GREEN), rgb.shape).copy()
    ty, tx = divmod(T_WATER, ATLAS_TILES)
    tint[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE] = ICON_BLUE
    ty, tx = divmod(T_REDSTONE_DUST, ATLAS_TILES)
    tint[ty * TILE:(ty + 1) * TILE, tx * TILE:(tx + 1) * TILE] = ICON_RED
    rgb = np.where((atlas[..., 3] == TINT_ALPHA)[..., None], rgb * tint, rgb)
    seen = atlas[..., 3] >= 128
    lab = srgb_to_oklab(rgb.reshape(-1, 3)).reshape(rgb.shape)
    # (the tiles drawn as icons)
    points, weight = _summaries(lab, seen, sorted({int(BLOCK_TILES[b][0]) for b in PLACEABLE}))
    if item_atlas is not None:
        item_seen = item_atlas[..., 3] >= 128
        item_rgb = item_atlas[..., :3].astype(float) / 255
        item_lab = srgb_to_oklab(item_rgb.reshape(-1, 3)).reshape(item_rgb.shape)
        more_points, more_weight = _summaries(item_lab, item_seen, range(items.NUM_ITEMS))
        points, weight = points + more_points, weight + more_weight
    points, weight = np.concatenate(points), np.concatenate(weight)
    centers = _kmeans(points, weight, _spread(points, weight, FIXED_COLORS - 16), 20)
    colors = np.rint(oklab_to_srgb(centers) * 255).astype(np.uint8)
    palette = srgb_to_oklab(colors / 255)

    def index(lab_image, visible):
        pixels = lab_image.reshape(-1, 3)
        nearest = np.argmin(((pixels[:, None] - palette[None]) ** 2).sum(-1), axis=1)
        out = (16 + nearest).reshape(visible.shape).astype(np.uint8)
        out[~visible] = 0
        return out

    item_indices = None if item_atlas is None else index(item_lab, item_seen)
    return [int(r) << 16 | int(g) << 8 | int(b) for r, g, b in colors], index(lab, seen), item_indices
