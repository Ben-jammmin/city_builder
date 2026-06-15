"""
Headless 10-year simulation test.

Layout (20-wide grid):
  y=0:  Power plant (x=0), water tower (x=19), power lines x=1-18, water pipes x=1-18
  y=1:  Road + power line + water pipe (x=0-19)    <- utility road row
  y=2:  Residential zones (x=1-18)
  y=3:  Road + power line + water pipe (x=0-19)
  y=4:  Commercial zones (x=1-18)
  y=5:  Road + power line + water pipe (x=0-19)
  y=6:  Industrial zones (x=1-18)
  y=7:  Road + power line + water pipe (x=0-19)
  y=8:  Police (x=1), Fire (x=3)  (road row)

Vertical utility spines on the non-zone edge columns connect all road rows:
  x=0, y=0-8:  power lines (bridging zone rows at y=2, 4, 6)
  x=19, y=0-8: water pipes (bridging zone rows at y=2, 4, 6)

This ensures every utility road row (y=1,3,5,7) is in both the power and water networks,
so every zone row (y=2,4,6) has powered+watered neighbors.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from citybuilder.city_map import CityMap
from citybuilder.models import BuildingType, CityStats, ZoneType
from citybuilder.simulation import Simulation


def build_city(city_map: CityMap) -> None:
    # Row 0: utility sources + horizontal connectors
    city_map.place_building(0, 0, BuildingType.POWER_PLANT)
    city_map.place_building(19, 0, BuildingType.WATER_TOWER)
    for x in range(1, 19):
        city_map.place_power_line(x, 0)
        city_map.place_water_pipe(x, 0)

    # Utility road rows (y=1, 3, 5, 7) — road + power line + water pipe on same tile
    for road_y in (1, 3, 5, 7):
        for x in range(0, 20):
            city_map.place_road(x, road_y)
            city_map.place_power_line(x, road_y)
            city_map.place_water_pipe(x, road_y)

    # Vertical power spine on x=0 (non-zone column, bridges zone rows)
    for y in range(1, 8):
        city_map.place_power_line(0, y)   # redundant on road rows but harmless (returns False silently)

    # Vertical water spine on x=19 (non-zone column, bridges zone rows)
    for y in range(1, 8):
        city_map.place_water_pipe(19, y)

    # Zone rows (1-tile deep, flanked by road rows on each side)
    for x in range(1, 19):
        city_map.place_zone(x, 2, ZoneType.RESIDENTIAL)
        city_map.place_zone(x, 4, ZoneType.COMMERCIAL)
        city_map.place_zone(x, 6, ZoneType.INDUSTRIAL)

    # Service road row
    for x in range(0, 20):
        city_map.place_road(x, 8)
    city_map.place_building(1, 8, BuildingType.POLICE)
    city_map.place_building(3, 8, BuildingType.FIRE)


def run_simulation(months: int = 120, seed: int = 42) -> None:
    import random
    random.seed(seed)

    city_map = CityMap(20, 20)
    stats = CityStats()
    stats.paused = False

    build_city(city_map)

    sim = Simulation(city_map, stats)
    sim.refresh_systems()

    print(f"{'Mo':>3} {'Yr':>3} {'$':>9} {'Pop':>5} {'Jobs':>5} "
          f"{'Rev':>5} {'Exp':>5}  Net  DmR DmC DmI UnPw UnWt Flags")
    print("-" * 100)

    issues: list[str] = []
    went_bankrupt = False
    loss_streak = 0

    for i in range(1, months + 1):
        sim.simulate_month()
        s = stats
        net = s.last_revenue - s.last_expenses

        flags = []
        if s.money < 0 and not went_bankrupt:
            went_bankrupt = True
            issues.append(f"Yr{s.year}/Mo{s.month}: bankrupt ${s.money:,}")
        if s.money < 0:
            flags.append("BANKRUPT")

        if net < -200:
            loss_streak += 1
        else:
            loss_streak = 0
        if loss_streak >= 6:
            flags.append(f"DRAIN")

        if s.demand_residential < 10:
            flags.append("RES-DEAD")
            if not any("RES-DEAD" in iss for iss in issues):
                issues.append(f"Yr{s.year}/Mo{s.month}: res demand={s.demand_residential}%")

        print(f"{i:>3} {s.year:>3} {s.money:>9,} {s.population:>5,} {s.jobs:>5,} "
              f"{s.last_revenue:>5,} {s.last_expenses:>5,} {net:>+5,} "
              f"{s.demand_residential:>3} {s.demand_commercial:>3} {s.demand_industrial:>3} "
              f"{s.unpowered_zones:>4} {s.unwatered_zones:>4} {' '.join(flags)}")

    print("\n" + "=" * 80)
    s = stats
    print(f"Year {s.year} Mo {s.month} | ${s.money:,} | Pop {s.population:,} | Jobs {s.jobs:,}")
    print(f"Demand R={s.demand_residential}% C={s.demand_commercial}% I={s.demand_industrial}%")
    print(f"Power {s.power_usage}/{s.power_capacity}  Water {s.water_usage}/{s.water_capacity}")
    print(f"Unpowered zones: {s.unpowered_zones}  Unwatered: {s.unwatered_zones}")
    print(f"Rev ${s.last_revenue}/mo  Exp ${s.last_expenses}/mo  Net {s.last_revenue - s.last_expenses:+}/mo")
    print(f"Messages: {s.messages[-3:]}")

    if issues:
        print("\nISSUES:")
        for iss in issues:
            print(f"  ! {iss}")
    else:
        print("\nNo critical issues — city survived 10 years.")


if __name__ == "__main__":
    run_simulation(months=120)
