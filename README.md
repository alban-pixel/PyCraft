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
