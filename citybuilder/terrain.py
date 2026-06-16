"""Procedural map generation — fills the city grid with rivers, lakes, forests, and hills."""
from __future__ import annotations

import random
import math

from .city_map import CityMap
from .models import TerrainType


START_AREA_LEFT = 2
START_AREA_TOP = 2
START_AREA_WIDTH = 12
START_AREA_HEIGHT = 10


def generate_terrain(city_map: CityMap, seed: int | None = None,
                     style: str = "default") -> None:
    rng = random.Random(seed)
    _fill_with_grass(city_map)

    if style == "flat":
        if city_map.width >= 8 and city_map.height >= 8:
            _add_lake(city_map, rng)          # one small lake for interest
        _add_forests_with_noise(city_map, rng)
        # no hills, no river

    elif style == "hilly":
        _add_main_water_features(city_map, rng)
        _add_forests_with_noise(city_map, rng)
        _add_hills_with_noise(city_map, rng)  # double hill pass
        _add_hills_with_noise(city_map, rng)

    elif style == "coastal":
        _add_coastal_water(city_map, rng)
        _add_forests_with_noise(city_map, rng)
        _add_hills_with_noise(city_map, rng)

    else:  # "default"
        _add_main_water_features(city_map, rng)
        _add_forests_with_noise(city_map, rng)
        _add_hills_with_noise(city_map, rng)

    clear_starter_area(city_map)


def terrain_counts(city_map: CityMap) -> dict[TerrainType, int]:
    counts = {terrain: 0 for terrain in TerrainType}
    for _, _, tile in city_map.iter_tiles():
        counts[tile.terrain] += 1
    return counts


def starter_area_tiles(city_map: CityMap) -> list[tuple[int, int]]:
    right = min(city_map.width, START_AREA_LEFT + START_AREA_WIDTH)
    bottom = min(city_map.height, START_AREA_TOP + START_AREA_HEIGHT)
    return [
        (x, y)
        for x in range(START_AREA_LEFT, right)
        for y in range(START_AREA_TOP, bottom)
    ]


def clear_starter_area(city_map: CityMap) -> None:
    for x, y in starter_area_tiles(city_map):
        city_map.get(x, y).terrain = TerrainType.GRASS


def _fill_with_grass(city_map: CityMap) -> None:
    for _, _, tile in city_map.iter_tiles():
        tile.terrain = TerrainType.GRASS


def _simple_noise(x: int, y: int, seed: int) -> float:
    """Generate pseudo-random noise for a tile position."""
    n = math.sin(x * 12.9898 + y * 78.233 + seed) * 43758.5453
    return n - math.floor(n)


def _add_main_water_features(city_map: CityMap, rng: random.Random) -> None:
    """Add rivers and lakes with more natural generation."""
    if city_map.width < 8 or city_map.height < 8:
        return

    # Add a winding river
    _add_winding_river(city_map, rng)
    
    # Add a few lakes
    lake_count = max(1, city_map.width * city_map.height // 600)
    for _ in range(lake_count):
        _add_lake(city_map, rng)


def _add_winding_river(city_map: CityMap, rng: random.Random) -> None:
    """Add a river that winds naturally across the map."""
    y = rng.randrange(city_map.height // 4, city_map.height * 3 // 4)
    dy_momentum = 0
    
    for x in range(city_map.width):
        # Smooth changes in direction for natural curves
        if rng.random() < 0.6:
            dy_momentum += rng.choice((-1, 0, 0, 1))
            dy_momentum = max(-2, min(2, dy_momentum))
        
        y += dy_momentum
        y = max(1, min(city_map.height - 2, y))
        
        # Variable river width for natural look
        river_width = rng.choice((1, 2, 2, 3))
        start_dy = -(river_width // 2)
        
        for dy in range(start_dy, start_dy + river_width):
            river_y = y + dy
            if city_map.in_bounds(x, river_y):
                city_map.get(x, river_y).terrain = TerrainType.WATER


def _add_lake(city_map: CityMap, rng: random.Random) -> None:
    """Add a natural-looking lake at a random location."""
    center_x = rng.randrange(city_map.width)
    center_y = rng.randrange(city_map.height)
    radius = rng.randint(3, 7)
    noise_seed = rng.randint(0, 99999)

    for x in range(max(0, center_x - radius), min(city_map.width, center_x + radius + 1)):
        for y in range(max(0, center_y - radius), min(city_map.height, center_y + radius + 1)):
            distance = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
            noise = _simple_noise(x, y, noise_seed)
            edge_threshold = radius - (noise * 1.5)
            
            if distance <= edge_threshold:
                city_map.get(x, y).terrain = TerrainType.WATER


def _add_forests_with_noise(city_map: CityMap, rng: random.Random) -> None:
    """Add forests using noise-based generation for more natural clustering."""
    forest_count = max(5, city_map.width * city_map.height // 300)
    
    for _ in range(forest_count):
        center_x = rng.randrange(city_map.width)
        center_y = rng.randrange(city_map.height)
        radius = rng.randint(3, 8)
        
        # Use varying density and noise
        for x in range(max(0, center_x - radius), min(city_map.width, center_x + radius + 1)):
            for y in range(max(0, center_y - radius), min(city_map.height, center_y + radius + 1)):
                tile = city_map.get(x, y)
                
                if tile.terrain == TerrainType.WATER:
                    continue
                
                distance = math.sqrt((x - center_x) ** 2 + (y - center_y) ** 2)
                noise_val = _simple_noise(x, y, 123)
                
                # Blend distance and noise for natural edges
                threshold = radius - (distance * 0.3) + (noise_val * radius * 0.4)
                
                if distance < threshold and rng.random() < 0.8:
                    tile.terrain = TerrainType.FOREST


def _add_coastal_water(city_map: CityMap, rng: random.Random) -> None:
    """Fill the southern edge of the map with ocean water, fading inland."""
    coast_depth = max(4, city_map.height // 7)
    for x in range(city_map.width):
        for y in range(city_map.height - coast_depth - 3, city_map.height):
            depth_from_bottom = city_map.height - 1 - y   # 0 at bottom edge, grows inland
            noise = _simple_noise(x, y, 17) * 3.0
            if depth_from_bottom < coast_depth * 0.55 + noise:
                city_map.get(x, y).terrain = TerrainType.WATER
    # Add a couple of inland lakes for variety
    for _ in range(rng.randint(1, 2)):
        _add_lake(city_map, rng)


def _add_hills_with_noise(city_map: CityMap, rng: random.Random) -> None:
    """Add hills using noise-based generation for natural clustering."""
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
                
                # Blend distance and noise for natural edges
                threshold = radius - (distance * 0.25) + (noise_val * radius * 0.3)
                
                if distance < threshold and rng.random() < 0.7:
                    tile.terrain = TerrainType.HILL
