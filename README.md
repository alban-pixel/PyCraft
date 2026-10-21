# PyCraft

Un monde de blocs en 3D, en vue première personne, rendu avec les primitives
**2D** de [Pyxel](https://github.com/kitao/pyxel) — projet NSI.

> État : en construction. Le monde et le rendu arrivent tâche par tâche
> (voir [tasks/plan.md](tasks/plan.md)).

## Installation

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
```

## Lancer

```bash
.venv/bin/python main.py
.venv/bin/python main.py --res 1920x1200 --dist 120
```

## Options

| Option | Défaut | Rôle |
|---|---|---|
| `--res LxH` | `1280x800` | résolution de la fenêtre (min 160x120, max 3840x2160) |
| `--dist N` | `96` | distance de vue en blocs |
| `--detail N` | `24` | rayon du maillage détaillé (LOD) |
| `--no-lod` | — | tout en maillage détaillé (plus joli, plus lent) |
| `--seed N` | `0` | graine du monde |

## Benchmark

```bash
.venv/bin/python tools/bench.py --res 1280x800 --dist 96
.venv/bin/python tools/bench.py --res 1920x1200 --dist 120 --frames 120
```

Mesures sur Mac arm64 (monde 256×256×32) :

| Configuration | Frame moyenne | p95 | fps max |
|---|---|---|---|
| 1280×800, distance 96 | **3,44 ms** | 3,46 ms | 291 |
| 1920×1200, distance 120 | **5,29 ms** | 5,56 ms | 189 |

## Tests

```bash
.venv/bin/python -m pytest -q
```

## Structure

```
main.py          → point d'entrée (arguments, boucle Pyxel)
pycraft/         → monde, maillage, caméra, rendu, joueur, HUD
tests/           → tests unitaires (sans fenêtre)
tools/           → benchmark
docs/            → intention, idées, documentation technique
SPEC.md          → spécification approuvée
```

## Documents

- [SPEC.md](SPEC.md) — spécification (objectif, commandes, critères de succès)
- [docs/intent/pycraft.md](docs/intent/pycraft.md) — intention du projet
- [docs/ideas/pycraft.md](docs/ideas/pycraft.md) — direction technique et mesures
- [tasks/plan.md](tasks/plan.md) — plan d'implémentation
