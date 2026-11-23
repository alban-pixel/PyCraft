"""What the screenshot needs besides OpenGL: the jitter of its passes, its size on a graphics card
that can't draw 4K, its file's name, and the PNG it is written to (with zlib: no dependency)."""
import os
import struct
import time
import zlib


def _radical_inverse(i, base):
    result, f = 0.0, 1.0 / base
    while i:
        result += f * (i % base)
        i //= base
        f /= base
    return result


def halton_offsets(n):
    """n points in [-0.5, 0.5) x [-0.5, 0.5), spread evenly however many are taken (Halton 2, 3)."""
    return [(_radical_inverse(i, 2) - 0.5, _radical_inverse(i, 3) - 0.5) for i in range(1, n + 1)]


def fit_size(size, max_texture, max_viewport):
    """The largest size with size's shape that the graphics card can draw (both sides even)."""
    width, height = size
    scale = min(1.0, max_texture / width, max_texture / height, max_viewport[0] / width, max_viewport[1] / height)
    return int(width * scale) // 2 * 2, int(height * scale) // 2 * 2


def screenshot_path(folder, when):
    """A new file in folder (made if missing), named after the time: a second one taken in the
    same second gets _2, then _3..."""
    os.makedirs(folder, exist_ok=True)
    stem = os.path.join(folder, time.strftime("%Y-%m-%d_%H.%M.%S", when))
    path, n = stem + ".png", 1
    while os.path.exists(path):
        n += 1
        path = f"{stem}_{n}.png"
    return path


def _chunk(kind, data):
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path, rgb):
    """An (height, width, 3) uint8 array as an 8-bit RGB PNG."""
    height, width, _ = rgb.shape
    rows = bytearray()
    for row in rgb:
        rows += b"\0" + row.tobytes()  # (filter 0: the row as it is)
    data = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + _chunk(b"IDAT", zlib.compress(bytes(rows), 6)) + _chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(data)
