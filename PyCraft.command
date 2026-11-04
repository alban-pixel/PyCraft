#!/bin/bash
# Double-click to run PyCraft GPU: creates a venv and installs dependencies on first launch.
cd "$(dirname "$0")/pycraft-gpu" || exit 1

if [ ! -d .venv ]; then
    echo "First launch: creating the virtual environment..."
    python3 -m venv .venv || { echo "python3 not found — install Xcode Command Line Tools."; read -r; exit 1; }
    .venv/bin/pip install -r requirements.txt || { echo "Dependency install failed."; read -r; exit 1; }
fi

exec .venv/bin/python main.py
