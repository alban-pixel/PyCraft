"""Benchmark reproductible du rendu.

    python tools/bench.py --res 1280x800 --dist 96 --detail 24
    python tools/bench.py --res 1920x1200 --dist 120 --frames 120 --headless
"""

from __future__ import annotations

import argparse
import pathlib
import statistics
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pyxel

from pycraft.camera import Camera
from pycraft.mesher import ChunkMeshes
from pycraft.renderer import Renderer
from pycraft.world import World


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark PyCraft")
    parser.add_argument("--res", default="1280x800")
    parser.add_argument("--dist", type=int, default=96)
    parser.add_argument("--detail", type=int, default=24)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--frames", type=int, default=60)
    parser.add_argument("--no-lod", action="store_true")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()

    width, height = (int(v) for v in args.res.lower().split("x"))
    pyxel.init(width, height, title=f"PyCraft bench {width}x{height}", fps=1000, headless=args.headless)

    t0 = time.perf_counter()
    monde = World(seed=args.seed)
    maillages = ChunkMeshes(monde)
    x, y, z = monde.spawn_point()
    camera = Camera(x, y, z + 1.55, yaw=0.6, pitch=-0.18, width=width, height=height)
    renderer = Renderer(
        monde,
        maillages,
        width,
        height,
        view_distance=args.dist,
        detail_radius=args.detail,
        use_detail=not args.no_lod,
    )
    chargement = (time.perf_counter() - t0) * 1000

    for _ in range(5):  # préchauffage
        pyxel.cls(12)
        renderer.draw(camera)

    temps: list[float] = []
    for _ in range(args.frames):
        t = time.perf_counter()
        pyxel.cls(12)
        renderer.draw(camera)
        temps.append((time.perf_counter() - t) * 1000)

    moyenne = statistics.mean(temps)
    p95 = sorted(temps)[int(len(temps) * 0.95) - 1]
    print(f"résolution : {width}x{height}  distance : {args.dist}  détail : {args.detail}")
    print(f"monde      : {montant_blocs(monde)} blocs, chargement {chargement:.0f} ms")
    print(f"rendu      : {renderer.quads} quads, {renderer.chunks_visibles} chunks visibles")
    print(f"frame      : moyenne {moyenne:.2f} ms, p95 {p95:.2f} ms, max {max(temps):.2f} ms")
    print(f"équivalent : {1000 / moyenne:.0f} fps max")
    pyxel.quit()


def montant_blocs(monde: World) -> int:
    return sum(1 for b in monde.data if b)


if __name__ == "__main__":
    main()
