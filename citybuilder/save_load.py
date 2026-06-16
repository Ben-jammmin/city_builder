"""Save and load the game state to/from a JSON file on disk."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .city_map import CityMap
from .models import BuildingType, CityStats, RecreationType, TerrainType, Tile, ZoneType

SAVE_VERSION = 4


def save_game(city_map: CityMap, stats: CityStats, path: str | Path) -> None:
    save_path = Path(path)
    save_path.write_text(json.dumps(to_save_data(city_map, stats), indent=2), encoding="utf-8")


def load_game(path: str | Path) -> tuple[CityMap, CityStats]:
    save_path = Path(path)
    data = json.loads(save_path.read_text(encoding="utf-8"))
    return from_save_data(data)


def to_save_data(city_map: CityMap, stats: CityStats) -> dict[str, Any]:
    return {
        "version": SAVE_VERSION,
        "map": {
            "width": city_map.width,
            "height": city_map.height,
            "tiles": [
                [tile_to_data(city_map.get(x, y)) for y in range(city_map.height)]
                for x in range(city_map.width)
            ],
        },
        "stats": stats_to_data(stats),
    }


def from_save_data(data: dict[str, Any]) -> tuple[CityMap, CityStats]:
    file_version = data.get("version", 0)
    if file_version != SAVE_VERSION:
        import warnings
        warnings.warn(
            f"Save file version {file_version} does not match current version {SAVE_VERSION}. "
            "Some data may be missing or defaulted.",
            UserWarning,
            stacklevel=3,
        )

    map_data = data["map"]
    city_map = CityMap(map_data["width"], map_data["height"])
    tiles = map_data["tiles"]

    for x in range(city_map.width):
        for y in range(city_map.height):
            city_map.tiles[x][y] = tile_from_data(tiles[x][y])

    stats = stats_from_data(data["stats"])
    return city_map, stats


def tile_to_data(tile: Tile) -> dict[str, Any]:
    return {
        "terrain": tile.terrain.value,
        "zone": tile.zone.value,
        "zone_level": tile.zone_level,
        "recreation_type": tile.recreation_type.value,
        "building": tile.building.value,
        "has_road": tile.has_road,
        "has_power_line": tile.has_power_line,
        "has_water_pipe": tile.has_water_pipe,
        "development": tile.development,
        "residents": tile.residents,
        "jobs": tile.jobs,
        "land_value": tile.land_value,
        "fire_risk": tile.fire_risk,
        "crime_risk": tile.crime_risk,
    }


def tile_from_data(data: dict[str, Any]) -> Tile:
    return Tile(
        terrain=TerrainType(data.get("terrain", TerrainType.GRASS.value)),
        zone=ZoneType(data.get("zone", ZoneType.EMPTY.value)),
        zone_level=data.get("zone_level", 1),
        recreation_type=RecreationType(data.get("recreation_type", RecreationType.PARK.value)),
        building=BuildingType(data.get("building", BuildingType.NONE.value)),
        has_road=data.get("has_road", False),
        has_power_line=data.get("has_power_line", False),
        has_water_pipe=data.get("has_water_pipe", False),
        development=data.get("development", 0.0),
        residents=data.get("residents", 0),
        jobs=data.get("jobs", 0),
        land_value=data.get("land_value", 1.0),
        fire_risk=data.get("fire_risk", 0),
        crime_risk=data.get("crime_risk", 0),
    )


def stats_to_data(stats: CityStats) -> dict[str, Any]:
    return {
        "money": stats.money,
        "population": stats.population,
        "jobs": stats.jobs,
        "tax_rate": stats.tax_rate,
        "year": stats.year,
        "month": stats.month,
        "paused": stats.paused,
        "last_revenue": stats.last_revenue,
        "last_expenses": stats.last_expenses,
        "last_population_delta": stats.last_population_delta,
        "last_job_delta": stats.last_job_delta,
        "demand_residential": stats.demand_residential,
        "demand_commercial": stats.demand_commercial,
        "demand_industrial": stats.demand_industrial,
        "power_capacity": stats.power_capacity,
        "power_usage": stats.power_usage,
        "power_satisfaction": stats.power_satisfaction,
        "unpowered_zones": stats.unpowered_zones,
        "water_capacity": stats.water_capacity,
        "water_usage": stats.water_usage,
        "water_satisfaction": stats.water_satisfaction,
        "unwatered_zones": stats.unwatered_zones,
        "service_score": stats.service_score,
        "fire_coverage_percent": stats.fire_coverage_percent,
        "fire_uncovered_zones": stats.fire_uncovered_zones,
        "average_fire_risk": stats.average_fire_risk,
        "police_coverage_percent": stats.police_coverage_percent,
        "police_uncovered_zones": stats.police_uncovered_zones,
        "average_crime_risk": stats.average_crime_risk,
        "education_coverage_percent": stats.education_coverage_percent,
        "health_coverage_percent": stats.health_coverage_percent,
        "milestone_pop": stats.milestone_pop,
        "rev_residential": stats.rev_residential,
        "rev_commercial": stats.rev_commercial,
        "rev_industrial": stats.rev_industrial,
        "exp_roads": stats.exp_roads,
        "exp_utilities": stats.exp_utilities,
        "exp_buildings": stats.exp_buildings,
        "exp_recreation": stats.exp_recreation,
        "messages": stats.messages,
    }


def stats_from_data(data: dict[str, Any]) -> CityStats:
    return CityStats(
        money=data.get("money", 0),
        population=data.get("population", 0),
        jobs=data.get("jobs", 0),
        tax_rate=data.get("tax_rate", 9),
        year=data.get("year", 1),
        month=data.get("month", 1),
        paused=data.get("paused", True),
        last_revenue=data.get("last_revenue", 0),
        last_expenses=data.get("last_expenses", 0),
        last_population_delta=data.get("last_population_delta", 0),
        last_job_delta=data.get("last_job_delta", 0),
        demand_residential=data.get("demand_residential", 50),
        demand_commercial=data.get("demand_commercial", 50),
        demand_industrial=data.get("demand_industrial", 50),
        power_capacity=data.get("power_capacity", 0),
        power_usage=data.get("power_usage", 0),
        power_satisfaction=data.get("power_satisfaction", 0),
        unpowered_zones=data.get("unpowered_zones", 0),
        water_capacity=data.get("water_capacity", 0),
        water_usage=data.get("water_usage", 0),
        water_satisfaction=data.get("water_satisfaction", 0),
        unwatered_zones=data.get("unwatered_zones", 0),
        service_score=data.get("service_score", 0),
        fire_coverage_percent=data.get("fire_coverage_percent", 0),
        fire_uncovered_zones=data.get("fire_uncovered_zones", 0),
        average_fire_risk=data.get("average_fire_risk", 0),
        police_coverage_percent=data.get("police_coverage_percent", 0),
        police_uncovered_zones=data.get("police_uncovered_zones", 0),
        average_crime_risk=data.get("average_crime_risk", 0),
        education_coverage_percent=data.get("education_coverage_percent", 0),
        health_coverage_percent=data.get("health_coverage_percent", 0),
        milestone_pop=data.get("milestone_pop", 0),
        rev_residential=data.get("rev_residential", 0),
        rev_commercial=data.get("rev_commercial", 0),
        rev_industrial=data.get("rev_industrial", 0),
        exp_roads=data.get("exp_roads", 0),
        exp_utilities=data.get("exp_utilities", 0),
        exp_buildings=data.get("exp_buildings", 0),
        exp_recreation=data.get("exp_recreation", 0),
        messages=data.get("messages", ["Loaded city."]),
    )
