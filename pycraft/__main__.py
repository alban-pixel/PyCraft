"""`python -m pycraft` starts the game."""
from pycraft.app import main

if __name__ == "__main__":  # (the worker processes import this module too: they must not start a game)
    main()
