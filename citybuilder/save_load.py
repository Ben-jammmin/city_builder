"""
save_load.py — Saves and loads the game state to/from JSON files on disk.

Save format
-----------
Each save is a plain JSON file at  saves/slot_N.json  (N = 1-5).
The top-level object has three keys:
  "version" : integer schema version (checked on load)
  "map"     : {width, height, tiles[x][y][...]} — the full city grid
  "stats"   : flat dict of all CityStats fields

Slot metadata (year, population, money) can be read without loading the
full map — used by the save/load overlay to show a summary of each slot.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .city_map import CityMap
from .models import BuildingType, CityStats, RecreationType, TerrainType, Tile, ZoneType
from .settings import NUM_SAVE_SLOTS, SAVE_DIR

# Increment this whenever the save format changes in a way that breaks
# backwards compatibility.  A mismatch on load emits a UserWarning.
SAVE_VERSION = 4


# ── Path helpers ───────────────────────────────────────────────────────────────

def _saves_dir() -> Path:
    """Returns the absolute path to the saves/ directory (next to the project root)."""
    return Path(__file__).resolve().parent.parent / SAVE_DIR


def slot_path(slot: int) -> Path:
    """Returns the file path for a given save slot, creating the folder if needed."""
    d = _saves_dir()
    d.mkdir(exist_ok=True)
    return d / f"slot_{slot}.json"


# ── Slot metadata (lightweight preview for the overlay) ───────────────────────

def slot_metadata(slot: int) -> dict | None:
    """
    Reads just the stats block of a save file to get a quick summary.
    Returns None if the slot is empty or the file is unreadable.
    """
    p = _saves_dir() / f"slot_{slot}.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        stats = data.get("stats", {})
        m = data.get("map", {})
        return {
            "slot": slot,
            "year": stats.get("year", 1),
            "month": stats.get("month", 1),
            "population": stats.get("population", 0),
            "money": stats.get("money", 0),
            "map_size": f"{m.get('width', 0)}x{m.get('height', 0)}",
        }
    except Exception:
        return None


def list_saves() -> list[dict | None]:
    """Returns a list of metadata dicts (or None for empty slots) for all save slots."""
    return [slot_metadata(i) for i in range(1, NUM_SAVE_SLOTS + 1)]


def most_recent_slot() -> int | None:
    """Returns the slot number of the most-recently modified save, or None if no saves exist."""
    saves_dir = _saves_dir()
    best_slot: int | None = None
    best_mtime = 0.0
    for slot in range(1, NUM_SAVE_SLOTS + 1):
        p = saves_dir / f"slot_{slot}.json"
        if p.exists():
            mtime = p.stat().st_mtime    # file modification time in seconds
            if mtime > best_mtime:
                best_mtime = mtime
                best_slot = slot
    return best_slot


# ── High-level save / load ─────────────────────────────────────────────────────

def save_game(city_map: CityMap, stats: CityStats, path: str | Path) -> None:
    """Serialises the full game state and writes it to path as pretty-printed JSON."""
    save_path = Path(path)
    save_path.write_text(json.dumps(to_save_data(city_map, stats), indent=2), encoding="utf-8")


def load_game(path: str | Path) -> tuple[CityMap, CityStats]:
    """Reads a JSON save file and returns a restored (CityMap, CityStats) pair."""
    save_path = Path(path)
    data = json.loads(save_path.read_text(encoding="utf-8"))
    return from_save_data(data)


# ── Serialisation ──────────────────────────────────────────────────────────────

def to_save_data(city_map: CityMap, stats: CityStats) -> dict[str, Any]:
    """Converts a live game state into a JSON-serialisable dict."""
    return {
        "version": SAVE_VERSION,
        "map": {
            "width": city_map.width,
            "height": city_map.height,
            # 2-D list: outer index is x, inner is y.
            "tiles": [
                [tile_to_data(city_map.get(x, y)) for y in range(city_map.height)]
                for x in range(city_map.width)
            ],
        },
        "stats": stats_to_data(stats),
    }


def from_save_data(data: dict[str, Any]) -> tuple[CityMap, CityStats]:
    """Reconstructs a (CityMap, CityStats) pair from a save dict."""
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

    # Restore every tile from its serialised form.
    for x in range(city_map.width):
        for y in range(city_map.height):
            city_map.tiles[x][y] = tile_from_data(tiles[x][y])

    stats = stats_from_data(data["stats"])
    return city_map, stats


# ── Tile serialisation ─────────────────────────────────────────────────────────

def tile_to_data(tile: Tile) -> dict[str, Any]:
    """Converts a single Tile to a JSON-safe dict. Enums are stored as their string value."""
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
        "on_fire": tile.on_fire,
        "fire_burn_time": tile.fire_burn_time,
    }


def tile_from_data(data: dict[str, Any]) -> Tile:
    """
    Reconstructs a Tile from a save dict.
    Uses .get() with defaults so old saves can load into newer game versions.
    """
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
        on_fire=data.get("on_fire", False),
        fire_burn_time=data.get("fire_burn_time", 0.0),
    )


# ── CityStats serialisation ────────────────────────────────────────────────────

def stats_to_data(stats: CityStats) -> dict[str, Any]:
    """Converts a CityStats object to a flat JSON-safe dict."""
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
    """Reconstructs a CityStats from a save dict, using sensible defaults for missing fields."""
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
