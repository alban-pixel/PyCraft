"""Shared fixtures and configuration for PyCraft E2E test suite."""
import os
import shutil
import sys
import tempfile
import pytest

# Ensure project root and pycraft-gpu are in sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYCRAFT_GPU_DIR = os.path.join(PROJECT_ROOT, "pycraft-gpu")

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if PYCRAFT_GPU_DIR not in sys.path:
    sys.path.insert(0, PYCRAFT_GPU_DIR)


@pytest.fixture
def project_root() -> str:
    """Return the absolute path to the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def pycraft_gpu_dir() -> str:
    """Return the absolute path to the pycraft-gpu directory."""
    return PYCRAFT_GPU_DIR


@pytest.fixture
def temp_dir():
    """Provide an isolated temporary directory cleaned up after test execution."""
    td = tempfile.mkdtemp(prefix="pycraft_e2e_")
    try:
        yield td
    finally:
        shutil.rmtree(td, ignore_errors=True)
