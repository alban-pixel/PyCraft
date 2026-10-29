import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pycraft-gpu"))

from main import App


@pytest.fixture(scope="session")
def headless_app():
    # Pyxel Rust backend only allows one pyxel.init() per Python process.
    # A session-scoped fixture guarantees a single App instance across all tests.
    app = App(headless=True)
    return app
