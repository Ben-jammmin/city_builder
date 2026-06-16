"""
terrain.py — Procedural map generation.

Fills a fresh CityMap with natural terrain: rivers, lakes, forests, and hills.
Four map styles are supported:
  "default"  — river + lakes + forests + hills (most varied)
  "flat"     — open grassland with a single lake, good for beginners
  "hilly"    — double hill pass for rugged terrain
  "coastal"  — ocean fills the southern edge

After generation, a small starter area near the top-left is always cleared to
flat grass so the player has room to begin building immediately.
"""
from __future__ import annotations

import random
import math

from .city_map import CityMap
from .models import TerrainType

# ── Starter area constants ─────────────────────────────────────────────────────
# The top-left rectangle that is guaranteed to be clear grass at game start.
START_AREA_LEFT = 2
START_AREA_TOP = 2
START_AREA_WIDTH = 12
START_AREA_HEIGHT = 10


def generate_terrain(city_map: CityMap, seed: int | None = None,
                     style: str = "default") -> None:
    """
    Main entry point — fills city_map with terrain according to the chosen style.

    seed: an integer for reproducible maps; None gives a random map each time.
    style: one of "default", "flat", "hilly", or "coastal".
    """
    rng = random.Random(seed)
    # Start with a blank slate of grass.
    _fill_with_grass(city_map)

    if style == "flat":
        if city_map.width >= 8 and city_map.height >= 8:
            _add_lake(city_map, rng)          # one small lake for interest
        _add_forests_with_noise(city_map, rng)
        # no hills, no river — genuinely flat

    elif style == "hilly":
        _add_main_water_features(city_map, rng)
        _add_forests_with_noise(city_map, rng)
        _add_hills_with_noise(city_map, rng)  # double hill pass for extra elevation
        _add_hills_with_noise(city_map, rng)

    elif style == "coastal":
        _add_coastal_water(city_map, rng)
        _add_forests_with_noise(city_map, rng)
        _add_hills_with_noise(city_map, rng)

    else:  # "default"
        _add_main_water_features(city_map, rng)
        _add_forests_with_noise(city_map, rng)
        _add_hills_with_noise(city_map, rng)

    # Always guarantee a clear building zone near the start.
    clear_starter_area(city_map)


def terrain_counts(city_map: CityMap) -> dict[TerrainType, int]:
    """Returns a dict of {TerrainType: tile_count} for debugging / stats display."""
    counts = {terrain: 0 for terrain in TerrainType}
    for _, _, tile in city_map.iter_tiles():
        counts[tile.terrain] += 1
    return counts


def starter_area_tiles(city_map: CityMap) -> list[tuple[int, int]]:
    """Returns the list of (x, y) coordinates in the starter area rectangle."""
    right = min(city_map.width, START_AREA_LEFT + START_AREA_WIDTH)
    bottom = min(city_map.height, START_AREA_TOP + START_AREA_HEIGHT)
    return [
        (x, y)
        for x in range(START_AREA_LEFT, right)
        for y in range(START_AREA_TOP, bottom)
    ]


def clear_starter_area(city_map: CityMap) -> None:
    """Overwrites all terrain in the starter area with GRASS."""
    for x, y in starter_area_tiles(city_map):
        city_map.get(x, y).terrain = TerrainType.GRASS


# ── Internal generation helpers ────────────────────────────────────────────────

def _fill_with_grass(city_map: CityMap) -> None:
    """Sets every tile to GRASS as the blank starting state."""
    for _, _, tile in city_map.iter_tiles():
        tile.terrain = TerrainType.GRASS


def _simple_noise(x: int, y: int, seed: int) -> float:
    """
    Generates a deterministic pseudo-random float in [0, 1) for tile (x, y).

    Uses a hash-style sine trick: multiply inputs by large primes, pass through
    sin, and take the fractional part. This gives spatially varying but
    repeatable values without a full Perlin noise implementation.
    """
    n = math.sin(x * 12.9898 + y * 78.233 + seed) * 43758.5453
    return n - math.floor(n)


def _add_main_water_features(city_map: CityMap, rng: random.Random) -> None:
    """Adds a winding river and several lakes to the map."""
    if city_map.width < 8 or city_map.height < 8:
        return

    _add_winding_river(city_map, rng)

    # Scale lake count to map size.
    lake_count = max(1, city_map.width * city_map.height // 600)
    for _ in range(lake_count):
        _add_lake(city_map, rng)


def _add_winding_river(city_map: CityMap, rng: random.Random) -> None:
    """
    Carves a river from the left edge to the right edge of the map.

    The river starts at a random y position in the middle half of the map.
    A dy_momentum value builds up so the river bends gradually rather than
    changing direction sharply each column.
    """
    # Start in the middle vertical band so the river has room to meander.
    y = rng.randrange(city_map.height // 4, city_map.height * 3 // 4)
    dy_momentum = 0    # positive = drifting south, negative = drifting north

    for x in range(city_map.width):
        # 60% chance of changing momentum each column — creates gentle curves.
        if rng.random() < 0.6:
            dy_momentum += rng.choice((-1, 0, 0, 1))
            dy_momentum = max(-2, min(2, dy_momentum))  # clamp to avoid diagonal rivers

        y += dy_momentum
        y = max(1, min(city_map.height - 2, y))  # keep river away from map edges

        # Variable river width (1-3 tiles) for a natural look.
        river_width = rng.choice((1, 2, 2, 3))
        start_dy = -(river_width // 2)

        for dy in range(start_dy, start_dy + river_width):
            river_y = y + dy
            if city_map.in_bounds(x, river_y):
                city_map.get(x, river_y).terrain = TerrainType.WATER


def _add_lake(city_map: CityMap, rng: random.Random) -> None:
    """
    Places a roughly circular lake at a random location.

    Noise is added to the radius threshold so the lake edge is organic
    rather than a perfect circle.
    """
    center_x = rng.randrange(city_map.width)
    center_y = rng.randrange(city_map.height)
    radius = rng.randint(3, 7)
    noise_seed = rng.randint(0, 99999)

    for x in range(max(0, center_x - radius), min(city_map.width, center_x + radius + 1)):
        for y in range(max(0, center_y - radius), min(city_map.height, center_y + radius + 1)):
            distance = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
            # Add noise to the edge so the lake boundary isn't a perfect circle.
            noise = _simple_noise(x, y, noise_seed)
            edge_threshold = radius - (noise * 1.5)

            if distance <= edge_threshold:
                city_map.get(x, y).terrain = TerrainType.WATER


def _add_forests_with_noise(city_map: CityMap, rng: random.Random) -> None:
    """
    Scatters forested clusters across the map.

    Each cluster has a random centre and radius. Tiles inside a cluster
    are converted to FOREST if they pass a distance-and-noise threshold,
    creating soft, organic edges rather than hard circles.
    """
    # Scale number of clusters to map area.
    forest_count = max(5, city_map.width * city_map.height // 300)

    for _ in range(forest_count):
        center_x = rng.randrange(city_map.width)
        center_y = rng.randrange(city_map.height)
        radius = rng.randint(3, 8)

        for x in range(max(0, center_x - radius), min(city_map.width, center_x + radius + 1)):
            for y in range(max(0, center_y - radius), min(city_map.height, center_y + radius + 1)):
                tile = city_map.get(x, y)

                # Don't overwrite water with forest.
                if tile.terrain == TerrainType.WATER:
                    continue

                distance = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
                noise_val = _simple_noise(x, y, 123)

                # Blend distance and noise: tiles near the centre are more likely
                # to be forest; the noise makes the boundary ragged/natural.
                threshold = radius - (distance * 0.3) + (noise_val * radius * 0.4)

                if distance < threshold and rng.random() < 0.8:
                    tile.terrain = TerrainType.FOREST


def _add_coastal_water(city_map: CityMap, rng: random.Random) -> None:
    """
    Creates an ocean coastline along the southern edge of the map.

    Tiles near the bottom are almost always water; further inland the
    boundary is irregular, controlled by noise.
    """
    coast_depth = max(4, city_map.height // 7)
    for x in range(city_map.width):
        for y in range(city_map.height - coast_depth - 3, city_map.height):
            # depth_from_bottom = 0 at the very bottom row, increases inland.
            depth_from_bottom = city_map.height - 1 - y
            noise = _simple_noise(x, y, 17) * 3.0
            # Tiles closer to the edge than (coast_depth * 0.55 + noise) become water.
            if depth_from_bottom < coast_depth * 0.55 + noise:
                city_map.get(x, y).terrain = TerrainType.WATER
    # A couple of inland lakes add variety beyond just the coastline.
    for _ in range(rng.randint(1, 2)):
        _add_lake(city_map, rng)


def _add_hills_with_noise(city_map: CityMap, rng: random.Random) -> None:
    """
    Scatters hill clusters across the map, using the same noise technique
    as forests but skipping water tiles.
    """
    hill_count = max(3, city_map.width * city_map.height // 500)

    for _ in range(hill_count):
        center_x = rng.randrange(city_map.width)
        center_y = rng.randrange(city_map.height)
        radius = rng.randint(2, 6)

        for x in range(max(0, center_x - radius), min(city_map.width, center_x + radius + 1)):
            for y in range(max(0, center_y - radius), min(city_map.height, center_y + radius + 1)):
                tile = city_map.get(x, y)

                if tile.terrain == TerrainType.WATER:
                    continue

                distance = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
                noise_val = _simple_noise(x, y, 234)

                # Hills use a slightly tighter threshold than forests.
                threshold = radius - (distance * 0.25) + (noise_val * radius * 0.3)

                if distance < threshold and rng.random() < 0.7:
                    tile.terrain = TerrainType.HILL
