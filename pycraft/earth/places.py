"""Famous places to start from on the real Earth."""
import math
from typing import NamedTuple


class Spot(NamedTuple):
    """Where the player starts, and what they look at first."""
    name: str
    lat: float
    lon: float
    look_lat: float
    look_lon: float


PLACES = [Spot("Mont Blanc", 45.9237, 6.8694, 45.8326, 6.8652), Spot("Everest", 27.9957, 86.8285, 27.9881, 86.9250),
          Spot("K2", 35.7447, 76.5136, 35.8808, 76.5155), Spot("Matterhorn", 45.9836, 7.7846, 45.9766, 7.6585),
          Spot("Grand Canyon", 36.0617, -112.1077, 36.1500, -112.1100),
          Spot("Yosemite", 37.7308, -119.5738, 37.7460, -119.5330),
          Spot("Mount Fuji", 35.4986, 138.7686, 35.3606, 138.7274),
          Spot("Geirangerfjord", 62.1255, 7.1650, 62.1050, 7.0940),
          Spot("Kilimanjaro", -2.9000, 37.2500, -3.0674, 37.3556),
          Spot("Torres del Paine", -51.0700, -73.0000, -50.9423, -72.9876),
          Spot("Reunion", -21.1300, 55.4700, -21.0983, 55.4797), Spot("Na Pali", 22.1500, -159.6460, 22.1700, -159.6400)]


def slot(lat, lon):
    """Name of the save of the world that starts there: each place has its own."""
    return f"{lat:+08.4f}{lon:+09.4f}"


def yaw_to(grid, lat, lon, x=0.0, z=0.0):
    """The way to look, from block (x, z), to see a place (degrees, like Player.yaw: 0 is south)."""
    px, pz = grid.block(lat, lon)
    return math.degrees(math.atan2(px - x, pz - z)) % 360
