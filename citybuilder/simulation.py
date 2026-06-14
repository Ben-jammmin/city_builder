from __future__ import annotations

from .city_map import CityMap
from .models import BuildingType, CityStats, ZoneType
from .settings import (
    BUILDING_MAINTENANCE,
    POWER_LINE_MAINTENANCE,
    POWER_PLANT_CAPACITY,
    ROAD_MAINTENANCE,
    SERVICE_RADIUS,
    WATER_PIPE_MAINTENANCE,
    WATER_TOWER_CAPACITY,
    ZONE_MAINTENANCE,
)


class Simulation:
    def __init__(self, city_map: CityMap, stats: CityStats) -> None:
        self.city_map = city_map
        self.stats = stats
        self.elapsed = 0.0

    def update(self, dt: float, seconds_per_month: float) -> None:
        if self.stats.paused:
            return
        self.elapsed += dt
        while self.elapsed >= seconds_per_month:
            self.elapsed -= seconds_per_month
            self.simulate_month()

    def simulate_month(self) -> None:
        previous_population = self.stats.population
        previous_jobs = self.stats.jobs

        self._update_systems()
        self._update_system_totals()
        self._update_demand()
        self._update_all_tiles()

        population = 0
        jobs = 0
        for _, _, tile in self.city_map.iter_tiles():
            population += tile.residents
            jobs += tile.jobs

        self.stats.population = population
        self.stats.jobs = jobs
        self.stats.last_population_delta = population - previous_population
        self.stats.last_job_delta = jobs - previous_jobs
        self._update_system_totals()

        revenue = int(population * self.stats.tax_rate * 0.16 + jobs * self.stats.tax_rate * 0.08)
        expenses = int(
            self.city_map.road_count() * ROAD_MAINTENANCE
            + self.city_map.zoned_count() * ZONE_MAINTENANCE
            + self.city_map.power_line_count() * POWER_LINE_MAINTENANCE
            + self.city_map.water_pipe_count() * WATER_PIPE_MAINTENANCE
            + sum(
                self.city_map.building_count(building) * BUILDING_MAINTENANCE[building.value]
                for building in BUILDING_MAINTENANCE_BY_TYPE
            )
        )
        self.stats.last_revenue = revenue
        self.stats.last_expenses = expenses
        self.stats.money += revenue - expenses
        self.stats.advance_month()
        self._add_monthly_message(revenue, expenses)

    def _update_all_tiles(self) -> None:
        for x, y, tile in self.city_map.iter_tiles():
            if tile.zone == ZoneType.EMPTY:
                tile.residents = 0
                tile.jobs = 0
                continue

            connected = self.city_map.has_adjacent_road(x, y)
            tile.land_value = self._land_value_for(x, y)

            if connected and tile.powered and tile.watered:
                growth = self._growth_for(tile.zone) * tile.land_value * self._utility_capacity_factor()
                tile.development = min(1.0, tile.development + growth)
            else:
                tile.development = max(0.0, tile.development - 0.04)

            if self.stats.tax_rate >= 16:
                tile.development = max(0.0, tile.development - 0.03)

            self._apply_capacity(tile)

    def _growth_for(self, zone: ZoneType) -> float:
        tax_factor = max(0.15, 1.2 - self.stats.tax_rate / 18)
        demand_factor = self.stats.demand_for(zone) / 100
        return (0.06 + 0.24 * demand_factor) * tax_factor

    def _land_value_for(self, x: int, y: int) -> float:
        value = 1.0
        tile = self.city_map.get(x, y)
        if tile.police_coverage:
            value += 0.04
        if tile.fire_coverage:
            value += 0.04
        if tile.education_coverage:
            value += 0.06
        for _, _, neighbor in self.city_map.neighbors8(x, y):
            if neighbor.zone == ZoneType.COMMERCIAL:
                value += 0.03
            elif neighbor.zone == ZoneType.INDUSTRIAL:
                value -= 0.025
            elif neighbor.has_road:
                value += 0.015
        return max(0.65, min(1.25, value))

    def _apply_capacity(self, tile) -> None:
        tile.residents = 0
        tile.jobs = 0
        if tile.zone == ZoneType.RESIDENTIAL:
            tile.residents = int(10 * tile.development * tile.land_value)
        elif tile.zone == ZoneType.COMMERCIAL:
            tile.jobs = int(7 * tile.development * tile.land_value)
        elif tile.zone == ZoneType.INDUSTRIAL:
            tile.jobs = int(11 * tile.development)

    def _update_systems(self) -> None:
        power_network = self._connected_network(BuildingType.POWER_PLANT, "has_power_line")
        water_network = self._connected_network(BuildingType.WATER_TOWER, "has_water_pipe")
        service_tiles = self._service_tiles()

        for x, y, tile in self.city_map.iter_tiles():
            tile.powered = self._tile_touches_network(x, y, power_network)
            tile.watered = self._tile_touches_network(x, y, water_network)
            tile.police_coverage = (x, y) in service_tiles["police"]
            tile.fire_coverage = (x, y) in service_tiles["fire"]
            tile.education_coverage = (x, y) in service_tiles["school"]

        self.stats.powered_tiles = len(power_network)
        self.stats.watered_tiles = len(water_network)

    def _connected_network(self, source_building: BuildingType, line_attr: str) -> set[tuple[int, int]]:
        starts = [
            (x, y)
            for x, y, tile in self.city_map.iter_tiles()
            if tile.building == source_building
        ]
        network = set(starts)
        frontier = list(starts)

        while frontier:
            x, y = frontier.pop()
            for nx, ny, neighbor in self.city_map.neighbors4(x, y):
                if (nx, ny) in network:
                    continue
                if getattr(neighbor, line_attr) or neighbor.building == source_building:
                    network.add((nx, ny))
                    frontier.append((nx, ny))

        return network

    def _tile_touches_network(self, x: int, y: int, network: set[tuple[int, int]]) -> bool:
        if (x, y) in network:
            return True
        return any((nx, ny) in network for nx, ny, _ in self.city_map.neighbors4(x, y))

    def _service_tiles(self) -> dict[str, set[tuple[int, int]]]:
        coverage = {"police": set(), "fire": set(), "school": set()}
        building_to_key = {
            BuildingType.POLICE: "police",
            BuildingType.FIRE: "fire",
            BuildingType.SCHOOL: "school",
        }

        for x, y, tile in self.city_map.iter_tiles():
            key = building_to_key.get(tile.building)
            if key is None:
                continue
            for tx, ty, _ in self.city_map.iter_tiles():
                distance = abs(tx - x) + abs(ty - y)
                if distance <= SERVICE_RADIUS:
                    coverage[key].add((tx, ty))
        return coverage

    def _update_demand(self) -> None:
        population = self.stats.population
        jobs = self.stats.jobs
        service_bonus = self.stats.service_score * 0.18
        utility_bonus = self._utility_capacity_factor() * 14
        tax_penalty = self.stats.tax_rate * 2

        self.stats.demand_residential = self._clamp_percent(
            45 + jobs * 0.45 - population * 0.18 + service_bonus + utility_bonus - tax_penalty
        )
        self.stats.demand_commercial = self._clamp_percent(
            40 + population * 0.22 - jobs * 0.10 + service_bonus - self.stats.tax_rate * 1.4
        )
        self.stats.demand_industrial = self._clamp_percent(
            38 + population * 0.18 - jobs * 0.08 + utility_bonus - self.stats.tax_rate * 1.1
        )

    def _update_system_totals(self) -> None:
        self.stats.power_capacity = self.city_map.building_count(BuildingType.POWER_PLANT) * POWER_PLANT_CAPACITY
        self.stats.water_capacity = self.city_map.building_count(BuildingType.WATER_TOWER) * WATER_TOWER_CAPACITY
        self.stats.power_usage = int(self.stats.population * 0.8 + self.stats.jobs * 0.6)
        self.stats.water_usage = int(self.stats.population * 0.7 + self.stats.jobs * 0.5)

        zoned_tiles = 0
        service_points = 0
        for _, _, tile in self.city_map.iter_tiles():
            if tile.zone == ZoneType.EMPTY:
                continue
            zoned_tiles += 1
            service_points += int(tile.police_coverage) + int(tile.fire_coverage) + int(tile.education_coverage)
        if zoned_tiles == 0:
            self.stats.service_score = 0
        else:
            self.stats.service_score = int(service_points / (zoned_tiles * 3) * 100)

    def _utility_capacity_factor(self) -> float:
        power_factor = self._capacity_factor(self.stats.power_capacity, self.stats.power_usage)
        water_factor = self._capacity_factor(self.stats.water_capacity, self.stats.water_usage)
        return min(power_factor, water_factor)

    def _capacity_factor(self, capacity: int, usage: int) -> float:
        if usage <= 0:
            return 1.0 if capacity > 0 else 0.0
        return max(0.25, min(1.0, capacity / usage))

    def _clamp_percent(self, value: float) -> int:
        return max(0, min(100, int(value)))

    def _add_monthly_message(self, revenue: int, expenses: int) -> None:
        if self.stats.money < 0:
            self.stats.add_message("Budget is negative. Raise taxes or slow building.")
        elif self.stats.power_capacity == 0:
            self.stats.add_message("Build a power plant and power lines.")
        elif self.stats.water_capacity == 0:
            self.stats.add_message("Build a water tower and water pipes.")
        elif self.stats.power_usage > self.stats.power_capacity:
            self.stats.add_message("Power demand is higher than capacity.")
        elif self.stats.water_usage > self.stats.water_capacity:
            self.stats.add_message("Water demand is higher than capacity.")
        elif self.stats.last_population_delta > 0:
            self.stats.add_message("New residents moved in.")
        elif self.stats.last_job_delta > 0:
            self.stats.add_message("Businesses are hiring.")
        elif revenue < expenses and self.city_map.road_count() > 0:
            self.stats.add_message("Maintenance is higher than revenue.")


BUILDING_MAINTENANCE_BY_TYPE = tuple(
    BuildingType(building_name) for building_name in BUILDING_MAINTENANCE
)
