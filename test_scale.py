"""
Large-scale simulation: build a proper city grid on 64x48 and run 30 years,
checking whether 10K population is achievable and the economy stays healthy.

Layout: 5 residential districts, each with commercial + industrial support.
Dense zones (level 2) throughout. Multiple large power plants and water towers.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from citybuilder.city_map import CityMap
from citybuilder.models import BuildingType, CityStats, ZoneType
from citybuilder.simulation import Simulation
from citybuilder.settings import MAP_WIDTH, MAP_HEIGHT


def place_utility_road(city_map, x, y):
    city_map.place_road(x, y)
    city_map.place_power_line(x, y)
    city_map.place_water_pipe(x, y)


def build_large_city(city_map: CityMap) -> None:
    """
    Grid layout on 64x48:
    - Vertical utility spine at x=0: power lines top-to-bottom
    - Vertical utility spine at x=63: water pipes top-to-bottom
    - Horizontal utility road rows every 4 tiles (y=1, 5, 9, 13, 17, 21, 25, 29, 33, 37, 41, 45)
    - Zone strips (3 tiles deep) between road rows, at x=2-61
    - Pattern: 3 zone rows (res/com/ind) then road, repeat
    - Services distributed across the map
    - Multiple large power plants and water towers along x=0 and x=63
    """

    W, H = city_map.width, city_map.height

    # ---- Utility sources along top row ----
    # Large power plants at x=0, spaced out vertically
    # Large water towers at x=63, spaced out vertically
    power_plants_placed = 0
    water_towers_placed = 0

    # Place power/water sources first (buildings go on separate spots from spines)
    for row_i, pp_y in enumerate(range(0, H, 8)):
        if city_map.can_place_building(0, pp_y, BuildingType.LARGE_POWER_PLANT):
            city_map.place_building(0, pp_y, BuildingType.LARGE_POWER_PLANT)
            power_plants_placed += 1

    for row_i, wt_y in enumerate(range(0, H, 8)):
        if city_map.can_place_building(W - 1, wt_y, BuildingType.LARGE_WATER_TOWER):
            city_map.place_building(W - 1, wt_y, BuildingType.LARGE_WATER_TOWER)
            water_towers_placed += 1

    # ---- Vertical utility spines on x=0 and x=63 ----
    for y in range(H):
        if city_map.get(0, y).building == BuildingType.NONE:
            city_map.place_power_line(0, y)
        if city_map.get(W - 1, y).building == BuildingType.NONE:
            city_map.place_water_pipe(W - 1, y)

    # ---- Horizontal utility road rows every 4 tiles ----
    road_ys = list(range(1, H - 1, 4))  # y=1,5,9,13,...
    for road_y in road_ys:
        for x in range(W):
            place_utility_road(city_map, x, road_y)

    # ---- Zone strips between road rows ----
    # Each gap has 3 non-road rows: place zones at x=2..62
    zone_rows = []
    for road_y in road_ys:
        for offset in (2, 3):  # 2 zone rows per gap (flanked by roads)
            zy = road_y + offset
            if zy < H - 1:
                zone_rows.append(zy)

    # Cycle: res, res, com, ind, res, res, com, ind ...
    zone_pattern = [ZoneType.RESIDENTIAL, ZoneType.RESIDENTIAL,
                    ZoneType.COMMERCIAL, ZoneType.INDUSTRIAL]
    for i, zy in enumerate(zone_rows):
        zone_type = zone_pattern[i % len(zone_pattern)]
        level = 2 if zone_type != ZoneType.INDUSTRIAL else 1
        for x in range(2, W - 1):
            city_map.place_zone(x, zy, zone_type, level=level)

    # ---- Services: police + fire + school distributed across map ----
    service_spots = [
        (1, 2, BuildingType.POLICE),
        (1, 6, BuildingType.FIRE),
        (1, 10, BuildingType.SCHOOL),
        (1, 14, BuildingType.POLICE),
        (1, 18, BuildingType.FIRE),
        (1, 22, BuildingType.SCHOOL),
        (1, 26, BuildingType.POLICE),
        (1, 30, BuildingType.FIRE),
        (1, 34, BuildingType.SCHOOL),
        (1, 38, BuildingType.POLICE),
        (1, 42, BuildingType.FIRE),
        (1, 46, BuildingType.HOSPITAL),
        (30, 2, BuildingType.POLICE),
        (30, 6, BuildingType.FIRE),
        (30, 14, BuildingType.POLICE),
        (30, 18, BuildingType.FIRE),
        (30, 26, BuildingType.SCHOOL),
        (30, 38, BuildingType.POLICE),
        (30, 42, BuildingType.HOSPITAL),
    ]
    for sx, sy, btype in service_spots:
        if city_map.can_place_building(sx, sy, btype):
            city_map.place_building(sx, sy, btype)

    print(f"  Built: {power_plants_placed} large power plants, {water_towers_placed} large water towers")
    print(f"  Zone rows: {len(zone_rows)}, zone columns: {W - 3} = {len(zone_rows) * (W - 3)} zone tiles")


def run_large_simulation(years: int = 30, seed: int = 42) -> None:
    import random
    random.seed(seed)

    city_map = CityMap(MAP_WIDTH, MAP_HEIGHT)
    stats = CityStats()
    stats.paused = False

    print("Building city...")
    build_large_city(city_map)

    sim = Simulation(city_map, stats)
    sim.refresh_systems()

    months = years * 12
    print(f"\n{'Yr':>3} {'Pop':>7} {'Jobs':>7} {'$':>10} {'Rev':>6} {'Exp':>6}  Net  DmR DmC DmI Flags")
    print("-" * 90)

    issues: list[str] = []
    went_bankrupt = False
    peak_pop = 0

    for i in range(1, months + 1):
        sim.simulate_month()
        s = stats
        net = s.last_revenue - s.last_expenses
        peak_pop = max(peak_pop, s.population)

        if s.money < 0 and not went_bankrupt:
            went_bankrupt = True
            issues.append(f"Yr{s.year}/Mo{s.month}: bankrupt ${s.money:,}")

        # Print once per year
        if i % 12 == 0:
            flags = []
            if s.money < 0:
                flags.append("BANKRUPT")
            if s.unpowered_zones > 0:
                flags.append(f"UNPOWER={s.unpowered_zones}")
            if s.unwatered_zones > 0:
                flags.append(f"UNWATER={s.unwatered_zones}")

            print(f"{s.year:>3} {s.population:>7,} {s.jobs:>7,} {s.money:>10,} "
                  f"{s.last_revenue:>6,} {s.last_expenses:>6,} {net:>+6,} "
                  f"{s.demand_residential:>3} {s.demand_commercial:>3} {s.demand_industrial:>3} "
                  f"{' '.join(flags)}")

    print("\n" + "=" * 80)
    s = stats
    print(f"Final: Year {s.year} | Pop {s.population:,} | Jobs {s.jobs:,} | ${s.money:,}")
    print(f"Peak pop: {peak_pop:,}")
    print(f"Demand R={s.demand_residential}% C={s.demand_commercial}% I={s.demand_industrial}%")
    print(f"Power {s.power_usage:,}/{s.power_capacity:,}  Water {s.water_usage:,}/{s.water_capacity:,}")
    print(f"Rev ${s.last_revenue:,}/mo  Exp ${s.last_expenses:,}/mo  Net {s.last_revenue - s.last_expenses:+,}/mo")

    if issues:
        print("\nISSUES:")
        for iss in issues:
            print(f"  ! {iss}")
    elif s.population >= 10_000:
        print(f"\n10K POPULATION ACHIEVED at year {s.year}!")
    else:
        print(f"\nPop is {s.population:,} after {years} years. Still growing: {s.demand_residential >= 50}.")


if __name__ == "__main__":
    run_large_simulation(years=30)
