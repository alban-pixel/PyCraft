"""The block icons of the hotbar and the inventory: the tiles shrunk to 16x16 pixels and 48 colors
of Pyxel's palette that suit them."""
import numpy as np

from pycraft.blocks import ATLAS_TILES, BLOCK_TILES, PLACEABLE, TILE, TINT_ALPHA, T_REDSTONE_DUST, T_WATER
from pycraft.render import FIXED_COLORS, oklab_to_srgb, srgb_to_oklab


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


def icon_palette(atlas):
    """The block icons for pyxel.blt: 48 colors that suit them and every pixel as the index of its
    nearest one, 16-63 (0 where transparent). Texels that take the biome color get a typical green
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
    points, weight = [], []
    for t in sorted({int(BLOCK_TILES[b][0]) for b in PLACEABLE}):  # the tiles drawn as icons
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
    points, weight = np.concatenate(points), np.concatenate(weight)
    centers = _kmeans(points, weight, _spread(points, weight, FIXED_COLORS - 16), 20)
    colors = np.rint(oklab_to_srgb(centers) * 255).astype(np.uint8)
    pixels = lab.reshape(-1, 3)
    nearest = np.argmin(((pixels[:, None] - srgb_to_oklab(colors / 255)[None]) ** 2).sum(-1), axis=1)
    indices = (16 + nearest).reshape(seen.shape).astype(np.uint8)
    indices[~seen] = 0
    return [int(r) << 16 | int(g) << 8 | int(b) for r, g, b in colors], indices
