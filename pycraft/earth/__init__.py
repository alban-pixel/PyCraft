"""The real Earth: its relief, its climate and its ground, as a world to play in."""
from typing import NamedTuple


class Place(NamedTuple):
    """Where a world is on Earth: its block (0, 0), and the folder of the tiles it is made from."""
    lat: float
    lon: float
    root: str
