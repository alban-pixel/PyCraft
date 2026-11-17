#!/bin/bash
# Double-click to run PyCraft on macOS: on the first launch, makes a virtual environment in .venv
# and installs the game's dependencies; again whenever pyproject.toml changes.
cd "$(dirname "$0")" || exit 1

if [ ! -x .venv/bin/python ]; then
    echo "First launch: creating the virtual environment..."
    python3 -m venv .venv || { echo "python3 not found — install Xcode Command Line Tools."; read -r; exit 1; }
    .venv/bin/python -m pip install --upgrade pip || { echo "Could not update pip."; read -r; exit 1; }
fi
if [ pyproject.toml -nt .venv/.installed ]; then
    .venv/bin/python -m pip install -e . || { echo "Dependency install failed."; read -r; exit 1; }
    touch .venv/.installed
fi

exec .venv/bin/python -m pycraft
