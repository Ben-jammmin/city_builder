"""Headless 20-year (240-month) simulation stress test — no pygame required.

Run directly:  python tests/test_20year.py
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from citybuilder.city_map import CityMap
from citybuilder.models import BuildingType, CityStats, RecreationType, ZoneType
from citybuilder.simulation import Simulation


def main() -> None:
    SEED = 42
    random.seed(SEED)

    W, H = 24, 24
    city_map = CityMap(W, H)
    stats = CityStats()

    # Row y=0: power plant at x=0, water tower at x=1 (buildings)
    city_map.place_building(0, 0, BuildingType.POWER_PLANT)
    city_map.place_building(1, 0, BuildingType.WATER_TOWER)

    # Row y=1: road + power_line + water_pipe
    for x in range(W):
        t = city_map.get(x, 1)
        t.has_road = True
        t.has_power_line = True
        t.has_water_pipe = True

    # Row y=2: zones
    for x in range(2, 8):
        city_map.place_zone(x, 2, ZoneType.RESIDENTIAL, 1)
    for x in range(8, 14):
        city_map.place_zone(x, 2, ZoneType.COMMERCIAL, 1)
    for x in range(14, 20):
        city_map.place_zone(x, 2, ZoneType.INDUSTRIAL, 1)
    city_map.place_zone(20, 2, ZoneType.PARK, 1, RecreationType.PARK)
    city_map.place_zone(21, 2, ZoneType.PARK, 1, RecreationType.PLAYGROUND)

    # Row y=4: second road+power+water
    for x in range(W):
        t = city_map.get(x, 4)
        t.has_road = True
        t.has_power_line = True
        t.has_water_pipe = True

    # Row y=3: dense zones
    for x in range(2, 8):
        city_map.place_zone(x, 3, ZoneType.RESIDENTIAL, 2)
    for x in range(8, 14):
        city_map.place_zone(x, 3, ZoneType.COMMERCIAL, 2)
    for x in range(14, 20):
        city_map.place_zone(x, 3, ZoneType.INDUSTRIAL, 1)

    # Service buildings at y=5
    city_map.place_building(2, 5, BuildingType.POLICE)
    city_map.place_building(6, 5, BuildingType.FIRE)
    city_map.place_building(10, 5, BuildingType.SCHOOL)
    city_map.place_building(14, 5, BuildingType.HOSPITAL)
    city_map.place_building(0, 5, BuildingType.LARGE_POWER_PLANT)
    city_map.place_building(1, 5, BuildingType.LARGE_WATER_TOWER)

    # Road at y=7 for service building access
    for x in range(W):
        t = city_map.get(x, 7)
        t.has_road = True

    # More zones at y=6
    for x in range(2, 8):
        city_map.place_zone(x, 6, ZoneType.RESIDENTIAL, 1)
    for x in range(8, 14):
        city_map.place_zone(x, 6, ZoneType.COMMERCIAL, 1)

    # Connect power+water from y=4 down to y=7 via column x=0
    for y in range(4, 8):
        t = city_map.get(0, y)
        if not t.has_power_line and t.building == BuildingType.NONE:
            t.has_power_line = True
        if not t.has_water_pipe and t.building == BuildingType.NONE:
            t.has_water_pipe = True

    # Power+water lines at y=7
    for x in range(W):
        t = city_map.get(x, 7)
        if not t.has_power_line:
            t.has_power_line = True
        if not t.has_water_pipe:
            t.has_water_pipe = True

    sim = Simulation(city_map, stats)

    ERRORS: list[str] = []

    def check(month_num: int) -> None:
        for x, y, tile in city_map.iter_tiles():
            label = f"[month {month_num}] ({x},{y})"
            if not (0.0 <= tile.development <= 1.0):
                ERRORS.append(f"{label} development out of range: {tile.development}")
            if tile.residents < 0:
                ERRORS.append(f"{label} negative residents: {tile.residents}")
            if tile.jobs < 0:
                ERRORS.append(f"{label} negative jobs: {tile.jobs}")
            if not (0 <= tile.fire_risk <= 100):
                ERRORS.append(f"{label} fire_risk out of range: {tile.fire_risk}")
            if not (0 <= tile.crime_risk <= 100):
                ERRORS.append(f"{label} crime_risk out of range: {tile.crime_risk}")
            if math.isnan(tile.land_value) or math.isinf(tile.land_value):
                ERRORS.append(f"{label} land_value is NaN/inf: {tile.land_value}")
            if tile.land_value < 0:
                ERRORS.append(f"{label} negative land_value: {tile.land_value}")
        if stats.population < 0:
            ERRORS.append(f"[month {month_num}] negative population: {stats.population}")
        if stats.jobs < 0:
            ERRORS.append(f"[month {month_num}] negative jobs: {stats.jobs}")
        if math.isnan(stats.money) or math.isinf(stats.money):
            ERRORS.append(f"[month {month_num}] money is NaN/inf: {stats.money}")
        if len(stats.messages) > 5:
            ERRORS.append(f"[month {month_num}] messages overflow: {len(stats.messages)}")
        if not (1 <= stats.month <= 12):
            ERRORS.append(f"[month {month_num}] invalid month value: {stats.month}")
        if stats.year < 1:
            ERRORS.append(f"[month {month_num}] year too small: {stats.year}")

    print(f"Running 20-year headless simulation (240 months)...")
    print(f"Map: {W}x{H}, Seed: {SEED}\n")

    snapshot_months = {1, 12, 24, 60, 120, 180, 240}

    for m in range(1, 241):
        try:
            sim.simulate_month()
        except Exception as exc:
            ERRORS.append(f"[month {m}] simulate_month() raised {type(exc).__name__}: {exc}")
            print(f"  EXCEPTION at month {m}: {exc}")
            break

        check(m)

        if m in snapshot_months or ERRORS:
            fires_active = sum(1 for _, _, t in city_map.iter_tiles() if t.on_fire)
            print(
                f"  Month {m:3d} ({stats.year}-{stats.month:02d}): pop={stats.population:6d} "
                f"jobs={stats.jobs:5d} money={stats.money:+9,d} fires={fires_active} "
                f"demand R/C/I={stats.demand_residential:.2f}/{stats.demand_commercial:.2f}/"
                f"{stats.demand_industrial:.2f}"
            )

        if ERRORS:
            print(f"\n  [STOPPING: {len(ERRORS)} error(s) found]")
            break

    print("\n" + "=" * 60)
    if ERRORS:
        print(f"FAILED — {len(ERRORS)} invariant violation(s):")
        for e in ERRORS[:20]:
            print(f"  {e}")
        if len(ERRORS) > 20:
            print(f"  ... and {len(ERRORS) - 20} more")
        sys.exit(1)
    else:
        fires_still_burning = sum(1 for _, _, t in city_map.iter_tiles() if t.on_fire)
        print("PASSED — no invariant violations over 240 months")
        print(f"Final state: pop={stats.population} jobs={stats.jobs} money={stats.money:+,}")
        print(f"Year: {stats.year}-{stats.month:02d}, messages: {stats.messages}")
        print(f"Fires still active: {fires_still_burning}")
        print(f"Unpowered zones: {stats.unpowered_zones}, Unwatered: {stats.unwatered_zones}")
        print(f"Revenue last month: {stats.last_revenue}, Expenses: {stats.last_expenses}")


if __name__ == "__main__":
    main()
