"""The tiles of the blocks as the graphics card takes them (texture arrays with mipmaps and the
biome color mask), the average color of each tile for the distant terrain, and the clouds' texture."""

import moderngl
import numpy as np

from pycraft.blocks import ALL_LEAVES, ATLAS_TILES, BLOCK_TILES, TINT_ALPHA


LEAF_TILES = {int(t) for b in ALL_LEAVES for t in BLOCK_TILES[b]}
def tile_averages(tiles):
    """(256, 2, 4) float array: for each tile, the average of its texels that keep their own
    color (rgb) and the share of texels the biome colors (a), then the average of those (rgb).
    Far away, a block is smaller than a pixel: the distant terrain uses these instead of the texture.
    The holes in leaves count as the leaves behind them, in the shade; the holes of other tiles
    (plants, glass) are left out, as they are never drawn. tiles: (256, N, N, 4)."""
    out = np.zeros((ATLAS_TILES * ATLAS_TILES, 2, 4), np.float32)
    rgb, alpha = tiles[..., :3].astype(np.float64) / 255, tiles[..., 3]  # (float64: same result at any size)
    for t in range(ATLAS_TILES * ATLAS_TILES):
        c, a = rgb[t].reshape(-1, 3), alpha[t].ravel()
        tinted = a == TINT_ALPHA
        hole = a < 128
        c = np.where(hole[:, None], c * 0.4, c)  # see-through texels: the shaded leaves inside
        tinted |= hole & (t in LEAF_TILES)
        seen = ~hole | (t in LEAF_TILES)
        plain = ~tinted & seen
        if plain.any():
            out[t, 0, :3] = c[plain].mean(axis=0)
        if tinted.any():
            out[t, 1, :3] = c[tinted].mean(axis=0)
        out[t, 0, 3] = tinted.sum() / max(seen.sum(), 1)
    return out
def split_tiles(tiles):
    """The tiles (256, N, N, 4), alpha 0 / TINT_ALPHA / 255, as the graphics card takes them: their
    colors with alpha 0 or 255, and a mask (256, N, N) of the texels the biome colors (255). The
    holes of every tile but leaves (whose holes are drawn) take the average color of the tile, so
    the mipmaps don't darken the edges of flowers and glass."""
    alpha = tiles[..., 3]
    rgba = tiles.copy()
    rgba[..., 3] = np.where(alpha > 0, 255, 0)
    mask = np.where(alpha == TINT_ALPHA, 255, 0).astype(np.uint8)
    for t in range(len(tiles)):
        hole = alpha[t] == 0
        if not hole.any() or hole.all():
            continue
        # The holes take the share of tinted texels around them, so the mipmaps keep the tint whole
        mask[t][hole] = np.rint(mask[t][~hole].astype(np.float64).mean())
        if t not in LEAF_TILES:
            rgba[t][hole, :3] = np.rint(tiles[t][~hole][:, :3].astype(np.float64).mean(axis=0))
    return rgba, mask
def make_tile_textures(ctx, tiles):
    """Two texture arrays, a layer per tile, with mipmaps: the colors (unit ATLAS_UNIT) and the
    biome color mask (TINT_UNIT). Sharp up close (nearest texel), smooth far off (the mipmaps,
    blended between levels, and anisotropic filtering for the ground seen at a grazing angle)."""
    n = tiles.shape[1]
    rgba, mask = split_tiles(tiles)
    textures = (ctx.texture_array((n, n, len(tiles)), 4, np.ascontiguousarray(rgba).tobytes()),
                ctx.texture_array((n, n, len(tiles)), 1, np.ascontiguousarray(mask).tobytes()))
    for tex in textures:
        tex.build_mipmaps()
        tex.filter = (moderngl.NEAREST_MIPMAP_LINEAR, moderngl.NEAREST)
        try:
            tex.anisotropy = 8.0
        except (moderngl.Error, AttributeError):
            pass
    return textures
def cloud_texture(size=512, seed=3):
    """Tileable noise for the clouds: random noise with its fine detail filtered out (in the frequency
    domain, so it wraps around), then spread evenly over 0-1, so the cover is the share of clear sky."""
    rng = np.random.default_rng(seed)
    f = np.fft.fftfreq(size)
    k = np.hypot(*np.meshgrid(f, f, indexing="ij"))
    k[0, 0] = 1.0
    noise = np.real(np.fft.ifft2(np.fft.fft2(rng.standard_normal((size, size))) / k ** 1.4))
    ranks = np.argsort(np.argsort(noise.ravel()))
    return (ranks / (ranks.size - 1)).reshape(size, size).astype("f4")
