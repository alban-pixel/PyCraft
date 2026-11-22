"""The Earth's tiles: a cache on disk, filled by one process and read by all the others.

The game, the terrain builders and the distant terrain's sampler only read files (TileReader): none
of them ever waits for the network. A process of its own downloads the tiles, mends them (clean.py)
and writes them (Downloader). The game asks for tiles and learns which ones landed (TileStore)."""
import collections
import multiprocessing
import os
import queue
import threading
import time
import traceback
import urllib.request

import numpy as np

from pycraft.earth import clean
from pycraft.earth.grid import TILE

URL = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
VERSION = "dem-v1"  # changes with the way tiles are mended: the same cache always gives the same ground
STEPS = 2  # heights are stored in half metres
TRIES = 3
OFFLINE_AFTER = 3  # tiles failed in a row: the network is gone
OFFLINE_SECONDS = 30.0  # and is not tried again before this long
MAX_FILES = 16000  # about 2 GB
KEEP_SECONDS = 86400.0  # a tile used in the last day is never deleted


def tile_path(root, key):
    z, x, y = key
    return os.path.join(root, VERSION, str(z), str(x), f"{y}.npy")


def save_tile(root, key, heights):
    path = tile_path(root, key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}-{threading.get_ident()}.tmp"
    with open(tmp, "wb") as f:
        np.save(f, np.round(np.asarray(heights, np.float64) * STEPS).astype(np.int16))
    os.replace(tmp, path)  # a reader never sees half a tile


def load_tile(root, key):
    """The heights of a tile on disk in metres, or None. A file that can't be read is deleted, so
    it is downloaded again."""
    path = tile_path(root, key)
    try:
        data = np.load(path)
        if data.shape == (TILE, TILE) and data.dtype == np.int16:
            return data.astype(np.float32) / STEPS
    except FileNotFoundError:
        return None
    except (OSError, ValueError, EOFError):
        pass
    try:
        os.remove(path)
    except OSError:
        pass
    return None


def _weights(f):
    """Catmull-Rom weights of the 4 values around a point, f (0-1) of the way from the 2nd to the 3rd."""
    return (((-0.5 * f + 1) * f - 0.5) * f, (1.5 * f - 2.5) * f * f + 1,
            ((-1.5 * f + 2) * f + 0.5) * f, (0.5 * f - 0.5) * f * f)


class TileReader:
    """Heights at any point of the map, from the tiles on disk. Where a tile is missing, the nearest
    coarser one there takes its place. Several threads can read at once."""

    def __init__(self, root, capacity=96):
        self.root, self.capacity = root, capacity
        self.lock = threading.Lock()
        self.cache = collections.OrderedDict()  # key -> (tile with the border it is read with, tiles missing from it)

    def heights(self, px, py, zoom):
        px, py = np.asarray(px, np.float64) - 0.5, np.asarray(py, np.float64) - 0.5
        shape = px.shape
        px, py = px.ravel(), py.ravel()
        i, j = np.floor(px).astype(np.int64), np.floor(py).astype(np.int64)
        wx, wy = _weights((px - i).astype(np.float32)), _weights((py - j).astype(np.float32))
        tx, ty = i // TILE, j // TILE
        out = np.zeros(px.shape, np.float32)
        groups, where = np.unique(tx * (1 << 20) + ty, return_inverse=True)
        for g in range(len(groups)):
            pick = np.flatnonzero(where == g) if len(groups) > 1 else slice(None)
            x0, y0 = int(tx[pick][0]), int(ty[pick][0])
            tile = self._bordered(zoom, x0, y0)
            col, row = i[pick] - x0 * TILE + 1, j[pick] - y0 * TILE + 1
            total = 0.0
            for b in range(4):
                line = 0.0
                for a in range(4):
                    line = line + tile[row + b - 1, col + a - 1] * wx[a][pick]
                total = total + line * wy[b][pick]
            out[pick] = total
        return out.reshape(shape)

    def _bordered(self, zoom, tx, ty):
        """A tile with one more pixel before it and two after, from its neighbors."""
        key = (zoom, tx, ty)
        with self.lock:
            found = self.cache.get(key)
            if found is not None:
                self.cache.move_to_end(key)
        if found is not None and not any(os.path.exists(tile_path(self.root, k)) for k in found[1]):
            return found[0]
        n = 2 ** zoom
        missing = []

        def tile(x, y):
            where = (zoom, x % n, min(max(y, 0), n - 1))
            data = load_tile(self.root, where)
            if data is None:
                missing.append(where)
                return self._from_parent(where)
            try:
                os.utime(tile_path(self.root, where))  # used: not the next one to be deleted
            except OSError:
                pass
            return data

        out = np.empty((TILE + 3, TILE + 3), np.float32)
        spans = ((-1, slice(0, 1), slice(TILE - 1, TILE)), (0, slice(1, TILE + 1), slice(0, TILE)),
                 (1, slice(TILE + 1, TILE + 3), slice(0, 2)))
        for dy, to_row, from_row in spans:
            for dx, to_col, from_col in spans:
                out[to_row, to_col] = tile(tx + dx, ty + dy)[from_row, from_col]
        with self.lock:
            self.cache[key] = (out, missing)
            while len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
        return out

    def _from_parent(self, key):
        """A missing tile, enlarged from the nearest coarser one on disk (flat at 0 without any)."""
        z, tx, ty = key
        for up in range(1, z + 1):
            parent = load_tile(self.root, (z - up, tx >> up, ty >> up))
            if parent is None:
                continue
            scale = 2 ** up
            u = np.clip(((tx % scale) * TILE + np.arange(TILE) + 0.5) / scale - 0.5, 0, TILE - 1)
            v = np.clip(((ty % scale) * TILE + np.arange(TILE) + 0.5) / scale - 0.5, 0, TILE - 1)
            j, i = np.minimum(u.astype(int), TILE - 2), np.minimum(v.astype(int), TILE - 2)
            fu, fv = (u - j)[None, :].astype(np.float32), (v - i)[:, None].astype(np.float32)
            return ((parent[np.ix_(i, j)] * (1 - fv) + parent[np.ix_(i + 1, j)] * fv) * (1 - fu)
                    + (parent[np.ix_(i, j + 1)] * (1 - fv) + parent[np.ix_(i + 1, j + 1)] * fv) * fu)
        return np.zeros((TILE, TILE), np.float32)


def http_get(url):
    with urllib.request.urlopen(url, timeout=15) as answer:
        return answer.read()


class Downloader:
    """Gets tiles, mends them and writes them. Several threads can use one at once."""

    def __init__(self, root, get=http_get, url=URL, pause=0.3, offline_seconds=OFFLINE_SECONDS):
        self.root, self.get, self.url = root, get, url
        self.pause, self.offline_seconds = pause, offline_seconds
        self.lock = threading.Lock()
        self.raw = collections.OrderedDict()  # tiles as they came: the ones around are mended with them too
        self.in_flight = {}  # key -> lock: a tile wanted by two threads is fetched once
        self.failures = 0  # in a row
        self.offline_since = 0.0

    @property
    def offline(self):
        return self.failures >= OFFLINE_AFTER

    def reset(self):
        """Try the network again now."""
        self.offline_since = 0.0

    def fetch_one(self, key):
        """Put a tile on disk; False when that failed."""
        if os.path.exists(tile_path(self.root, key)):
            return True
        if self.offline and time.monotonic() - self.offline_since < self.offline_seconds:
            return False
        try:
            save_tile(self.root, key, clean.clean(key, self._raw))
        except (OSError, ValueError, SyntaxError):  # (ssl's errors are OSErrors; Pillow raises the others)
            with self.lock:
                self.failures += 1
                if self.offline:
                    self.offline_since = time.monotonic()
            return False
        self.failures = 0
        return True

    def _raw(self, key):
        with self.lock:
            if key in self.raw:
                self.raw.move_to_end(key)
                return self.raw[key]
            flight = self.in_flight.setdefault(key, threading.Lock())
        with flight:
            with self.lock:
                if key in self.raw:
                    return self.raw[key]
            z, x, y = key
            for attempt in range(TRIES):
                try:
                    heights = clean.decode(self.get(self.url.format(z=z, x=x, y=y)))
                    if heights.shape != (TILE, TILE):
                        raise ValueError("not a tile")
                    break
                except (OSError, ValueError, SyntaxError) as error:
                    if attempt == TRIES - 1:
                        raise error
                    time.sleep(self.pause * (attempt + 1))
            with self.lock:
                self.in_flight.pop(key, None)
                self.raw[key] = heights
                while len(self.raw) > 64:
                    self.raw.popitem(last=False)
            return heights


def _delete_old(root):
    """Keep the cache under its size: the tiles used longest ago go first."""
    files = []
    for folder, _, names in os.walk(os.path.join(root, VERSION)):
        for name in names:
            path = os.path.join(folder, name)
            try:
                used = os.path.getmtime(path)
                if name.endswith(".tmp"):  # left by a game that was closed while writing
                    used = 0.0 if used < time.time() - KEEP_SECONDS else used
                    if not used:
                        os.remove(path)
                    continue
                files.append((used, path))
            except OSError:
                pass
    limit = time.time() - KEEP_SECONDS
    for used, path in sorted(files)[:max(len(files) - MAX_FILES, 0)]:
        if used < limit:
            try:
                os.remove(path)
            except OSError:
                pass


def _downloader(root, url, tasks, results, threads):
    """Main loop of the downloader's process. Messages: ("want", [keys]), ("retry",), ("stop",).
    Answers: ("tile", key, whether it is on disk, whether the network is gone)."""
    down = Downloader(root, url=url)
    stack, there = [], threading.Condition()  # the newest wish first: what the player sees now

    def work():
        while True:
            with there:
                while not stack:
                    there.wait()
                key = stack.pop()
            try:
                ok = down.fetch_one(key)
            except Exception:  # noqa: BLE001 - reported by the game
                results.put(("error", traceback.format_exc()))
                ok = False
            results.put(("tile", key, ok, down.offline))

    for _ in range(threads):
        threading.Thread(target=work, daemon=True).start()
    threading.Thread(target=_delete_old, args=(root,), daemon=True).start()
    parent = multiprocessing.parent_process()
    while True:
        try:
            msg = tasks.get(timeout=1.0)
        except queue.Empty:
            if parent is not None and not parent.is_alive():
                return  # the game is gone
            continue
        if msg[0] == "stop":
            return
        if msg[0] == "retry":
            down.reset()
        else:
            with there:
                stack.extend(reversed(msg[1]))
                there.notify_all()


class TileStore:
    """The game's side: asks for tiles, and knows which ones are there."""

    def __init__(self, root, url=URL, start=True, threads=16):
        self.root = os.fspath(root)
        self.have = set()  # on disk
        self.failed = set()  # this session: coarser tiles take their place
        self.asked = set()
        self.offline = False
        self.changes = 0  # counts the answers: what wasn't ready may be, once it has changed
        self.sent = []  # without a process (tests): what would have been asked of it
        self.process = None
        if start:
            ctx = multiprocessing.get_context("spawn")
            self.tasks, self.results = ctx.Queue(), ctx.Queue()
            self.process = ctx.Process(target=_downloader, args=(self.root, url, self.tasks, self.results, threads),
                                       daemon=True, name="earth tiles")
            self.process.start()

    def _there(self, key):
        if key in self.have:
            return True
        if key not in self.asked and os.path.exists(tile_path(self.root, key)):
            self.have.add(key)
            return True
        return False

    def missing(self, keys):
        """The tiles neither on disk nor given up."""
        return [k for k in keys if not self._there(k) and k not in self.failed]

    def ready(self, keys):
        """Whether the ground there can be made: each tile is on disk, or won't come this session."""
        return not self.missing(keys)

    def complete(self, keys):
        return all(self._there(k) for k in keys)

    def progress(self, keys):
        return sum(self._there(k) for k in keys) / max(len(keys), 1)

    def want(self, keys):
        new = [k for k in dict.fromkeys(self.missing(keys)) if k not in self.asked]
        if new:
            self.asked.update(new)
            if self.process is not None:
                self.tasks.put(("want", new))
            else:
                self.sent.append(new)

    def landed(self, key, ok, offline=False):
        self.offline = offline
        self.changes += 1
        if ok:
            self.have.add(key)
            self.failed.discard(key)
        else:
            self.failed.add(key)

    def poll(self):
        """Take in the downloader's answers."""
        while self.process is not None:
            try:
                msg = self.results.get_nowait()
            except queue.Empty:
                return
            if msg[0] == "error":
                raise RuntimeError("the Earth's downloader failed:\n" + msg[1])
            self.landed(*msg[1:])

    def retry(self):
        """Ask again for what failed."""
        self.asked -= self.failed
        self.failed.clear()
        self.offline = False
        if self.process is not None:
            self.tasks.put(("retry",))

    def close(self):
        if self.process is not None:
            self.tasks.put(("stop",))
            self.process.join(2)
            if self.process.is_alive():
                self.process.terminate()
            self.process = None
