from __future__ import annotations

from .city_map import CityMap
from .models import BuildingType, CityStats, Tile, ZoneType
from .settings import (
    AIRPORT_DEMAND_BOOST,
    BASE_GROWTH_RATE,
    BUILDING_MAINTENANCE,
    COMMERCIAL_CAPACITY,
    COMMERCIAL_NEIGHBOR_BONUS,
    CRIME_RISK_BASE,
    CRIME_RISK_COMMERCIAL,
    CRIME_RISK_COMMERCIAL_NEIGHBOR,
    CRIME_RISK_COVERAGE_REDUCTION,
    CRIME_RISK_DEVELOPMENT_FACTOR,
    CRIME_RISK_HIGH_TAX,
    CRIME_RISK_INDUSTRIAL,
    CRIME_RISK_NO_COVERAGE,
    CRIME_RISK_NO_ROAD,
    CRIME_RISK_RESIDENTIAL,
    DEMAND_GROWTH_MULTIPLIER,
    DEVELOPMENT_DECLINE_RATE,
    EDUCATION_COVERAGE_BONUS,
    FIRE_RADIUS,
    FIRE_RISK_BASE,
    FIRE_RISK_COMMERCIAL,
    FIRE_RISK_COVERAGE_REDUCTION,
    FIRE_RISK_DEVELOPMENT_FACTOR,
    FIRE_RISK_INDUSTRIAL,
    FIRE_RISK_INDUSTRIAL_NEIGHBOR,
    FIRE_RISK_NO_COVERAGE,
    FIRE_RISK_NO_ROAD,
    FIRE_RISK_NO_WATER,
    FIRE_RISK_RESIDENTIAL,
    HIGH_TAX_DECLINE_RATE,
    HIGH_TAX_THRESHOLD,
    HIGH_RISK_THRESHOLD,
    INDUSTRIAL_CAPACITY,
    INDUSTRIAL_NEIGHBOR_PENALTY,
    JOBS_TAX_COEFFICIENT,
    LAND_VALUE_MAX,
    LAND_VALUE_MIN,
    MIN_CAPACITY_FACTOR,
    MIN_TAX_FACTOR,
    POLICE_RADIUS,
    POPULATION_TAX_COEFFICIENT,
    POWER_CONSUMPTION_PER_JOB,
    POWER_CONSUMPTION_PER_RESIDENT,
    POWER_LINE_MAINTENANCE,
    POWER_PLANT_CAPACITY,
    RESIDENTIAL_CAPACITY,
    ROAD_MAINTENANCE,
    ROAD_NEIGHBOR_BONUS,
    SERVICE_BONUS_MULTIPLIER,
    SERVICE_COVERAGE_BONUS,
    SERVICE_RADIUS,
    SERVICE_SCORE_DIVISOR,
    TAX_FACTOR_BASELINE,
    TAX_PENALTY_COMMERCIAL,
    TAX_PENALTY_INDUSTRIAL,
    TAX_PENALTY_RESIDENTIAL,
    TAX_RATE_PENALTY_FACTOR,
    TRAIN_STATION_DEMAND_BOOST,
    UTILITY_BONUS_MULTIPLIER,
    WATER_CONSUMPTION_PER_JOB,
    WATER_CONSUMPTION_PER_RESIDENT,
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

        revenue = int(population * self.stats.tax_rate * POPULATION_TAX_COEFFICIENT + jobs * self.stats.tax_rate * JOBS_TAX_COEFFICIENT)
        expenses = int(
            self.city_map.road_count() * ROAD_MAINTENANCE
            + self.city_map.zoned_count() * ZONE_MAINTENANCE
            + self.city_map.power_line_count() * POWER_LINE_MAINTENANCE
            + self.city_map.water_pipe_count() * WATER_PIPE_MAINTENANCE
            + sum(
                self.city_map.building_count(BuildingType(building_name)) * cost
                for building_name, cost in BUILDING_MAINTENANCE.items()
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
                tile.fire_risk = 0
                tile.crime_risk = 0
                continue

            connected = self.city_map.has_adjacent_road(x, y)
            tile.land_value = self._land_value_for(x, y)

            if connected and tile.powered and tile.watered:
                growth = self._growth_for(tile.zone) * tile.land_value * self._utility_capacity_factor()
                tile.development = min(1.0, tile.development + growth)
            else:
                tile.development = max(0.0, tile.development - DEVELOPMENT_DECLINE_RATE)

            if self.stats.tax_rate >= HIGH_TAX_THRESHOLD:
                tile.development = max(0.0, tile.development - HIGH_TAX_DECLINE_RATE)

            tile.fire_risk = self._fire_risk_for(x, y)
            tile.crime_risk = self._crime_risk_for(x, y)
            self._apply_capacity(tile)

    def _growth_for(self, zone: ZoneType) -> float:
        tax_factor = max(MIN_TAX_FACTOR, TAX_FACTOR_BASELINE - self.stats.tax_rate / TAX_RATE_PENALTY_FACTOR)
        demand_factor = self.stats.demand_for(zone) / 100
        return (BASE_GROWTH_RATE + DEMAND_GROWTH_MULTIPLIER * demand_factor) * tax_factor

    def _land_value_for(self, x: int, y: int) -> float:
        value = 1.0
        tile = self.city_map.get(x, y)
        if tile.police_coverage:
            value += SERVICE_COVERAGE_BONUS
        if tile.fire_coverage:
            value += SERVICE_COVERAGE_BONUS
        if tile.education_coverage:
            value += EDUCATION_COVERAGE_BONUS
        for _, _, neighbor in self.city_map.neighbors8(x, y):
            if neighbor.zone == ZoneType.COMMERCIAL:
                value += COMMERCIAL_NEIGHBOR_BONUS
            elif neighbor.zone == ZoneType.INDUSTRIAL:
                value -= INDUSTRIAL_NEIGHBOR_PENALTY
            elif neighbor.has_road:
                value += ROAD_NEIGHBOR_BONUS
        return max(LAND_VALUE_MIN, min(LAND_VALUE_MAX, value))

    def _apply_capacity(self, tile: Tile) -> None:
        tile.residents = 0
        tile.jobs = 0
        if tile.zone == ZoneType.RESIDENTIAL:
            tile.residents = int(RESIDENTIAL_CAPACITY * tile.development * tile.land_value)
        elif tile.zone == ZoneType.COMMERCIAL:
            tile.jobs = int(COMMERCIAL_CAPACITY * tile.development * tile.land_value)
        elif tile.zone == ZoneType.INDUSTRIAL:
            tile.jobs = int(INDUSTRIAL_CAPACITY * tile.development)

    def _fire_risk_for(self, x: int, y: int) -> int:
        tile = self.city_map.get(x, y)
        if tile.zone == ZoneType.EMPTY:
            return 0

        risk = FIRE_RISK_BASE + int(tile.development * FIRE_RISK_DEVELOPMENT_FACTOR)
        if tile.zone == ZoneType.INDUSTRIAL:
            risk += FIRE_RISK_INDUSTRIAL
        elif tile.zone == ZoneType.COMMERCIAL:
            risk += FIRE_RISK_COMMERCIAL
        else:
            risk += FIRE_RISK_RESIDENTIAL

        industrial_neighbors = sum(
            1 for _, _, neighbor in self.city_map.neighbors8(x, y) if neighbor.zone == ZoneType.INDUSTRIAL
        )
        risk += industrial_neighbors * FIRE_RISK_INDUSTRIAL_NEIGHBOR

        if tile.fire_coverage:
            risk -= FIRE_RISK_COVERAGE_REDUCTION
        else:
            risk += FIRE_RISK_NO_COVERAGE
        if not tile.watered:
            risk += FIRE_RISK_NO_WATER
        if not self.city_map.has_adjacent_road(x, y):
            risk += FIRE_RISK_NO_ROAD

        return self._clamp_percent(risk)

    def _crime_risk_for(self, x: int, y: int) -> int:
        tile = self.city_map.get(x, y)
        if tile.zone == ZoneType.EMPTY:
            return 0

        risk = CRIME_RISK_BASE + int(tile.development * CRIME_RISK_DEVELOPMENT_FACTOR)
        if tile.zone == ZoneType.COMMERCIAL:
            risk += CRIME_RISK_COMMERCIAL
        elif tile.zone == ZoneType.INDUSTRIAL:
            risk += CRIME_RISK_INDUSTRIAL
        else:
            risk += CRIME_RISK_RESIDENTIAL

        commercial_neighbors = sum(
            1 for _, _, neighbor in self.city_map.neighbors8(x, y) if neighbor.zone == ZoneType.COMMERCIAL
        )
        risk += commercial_neighbors * CRIME_RISK_COMMERCIAL_NEIGHBOR

        if tile.police_coverage:
            risk -= CRIME_RISK_COVERAGE_REDUCTION
        else:
            risk += CRIME_RISK_NO_COVERAGE
        if not self.city_map.has_adjacent_road(x, y):
            risk += CRIME_RISK_NO_ROAD
        if self.stats.tax_rate >= HIGH_TAX_THRESHOLD:
            risk += CRIME_RISK_HIGH_TAX

        return self._clamp_percent(risk)

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

        self.stats.powered_tiles = sum(1 for _, _, tile in self.city_map.iter_tiles() if tile.powered)
        self.stats.unpowered_zones = sum(
            1
            for _, _, tile in self.city_map.iter_tiles()
            if tile.zone != ZoneType.EMPTY and not tile.powered
        )
        self.stats.watered_tiles = sum(1 for _, _, tile in self.city_map.iter_tiles() if tile.watered)
        self.stats.unwatered_zones = sum(
            1
            for _, _, tile in self.city_map.iter_tiles()
            if tile.zone != ZoneType.EMPTY and not tile.watered
        )

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
            BuildingType.POLICE: ("police", POLICE_RADIUS),
            BuildingType.FIRE: ("fire", FIRE_RADIUS),
            BuildingType.SCHOOL: ("school", SERVICE_RADIUS),
        }

        # Use BFS from each service building for efficient coverage calculation
        for x, y, tile in self.city_map.iter_tiles():
            service_info = building_to_key.get(tile.building)
            if service_info is None:
                continue
            key, radius = service_info
            self._coverage_from_building(x, y, key, radius, coverage)
        return coverage

    def _coverage_from_building(self, start_x: int, start_y: int, key: str, radius: int, coverage: dict) -> None:
        """Use Manhattan distance to find all tiles within radius of a service building."""
        visited = set()
        frontier = [(start_x, start_y)]
        visited.add((start_x, start_y))
        coverage[key].add((start_x, start_y))

        while frontier:
            next_frontier = []
            for x, y in frontier:
                for nx, ny, _ in self.city_map.neighbors4(x, y):
                    if (nx, ny) not in visited:
                        distance = abs(nx - start_x) + abs(ny - start_y)
                        if distance <= radius:
                            visited.add((nx, ny))
                            coverage[key].add((nx, ny))
                            next_frontier.append((nx, ny))
            frontier = next_frontier

    def _update_demand(self) -> None:
        population = self.stats.population
        jobs = self.stats.jobs
        service_bonus = self.stats.service_score * SERVICE_BONUS_MULTIPLIER
        utility_bonus = self._utility_capacity_factor() * UTILITY_BONUS_MULTIPLIER
        tax_penalty = self.stats.tax_rate * TAX_PENALTY_RESIDENTIAL
        
        # Add demand boost from transport buildings
        train_boost = self.city_map.building_count(BuildingType.TRAIN_STATION) * TRAIN_STATION_DEMAND_BOOST
        airport_boost = self.city_map.building_count(BuildingType.AIRPORT) * AIRPORT_DEMAND_BOOST
        transport_bonus = train_boost + airport_boost

        self.stats.demand_residential = self._clamp_percent(
            45 + jobs * 0.45 - population * 0.18 + service_bonus + utility_bonus - tax_penalty + transport_bonus * 0.3
        )
        self.stats.demand_commercial = self._clamp_percent(
            40 + population * 0.22 - jobs * 0.10 + service_bonus - self.stats.tax_rate * TAX_PENALTY_COMMERCIAL + transport_bonus
        )
        self.stats.demand_industrial = self._clamp_percent(
            38 + population * 0.18 - jobs * 0.08 + utility_bonus - self.stats.tax_rate * TAX_PENALTY_INDUSTRIAL + transport_bonus * 0.7
        )

    def _update_system_totals(self) -> None:
        self.stats.power_capacity = self.city_map.building_count(BuildingType.POWER_PLANT) * POWER_PLANT_CAPACITY
        self.stats.water_capacity = self.city_map.building_count(BuildingType.WATER_TOWER) * WATER_TOWER_CAPACITY
        self.stats.power_usage = int(self.stats.population * POWER_CONSUMPTION_PER_RESIDENT + self.stats.jobs * POWER_CONSUMPTION_PER_JOB)
        self.stats.water_usage = int(self.stats.population * WATER_CONSUMPTION_PER_RESIDENT + self.stats.jobs * WATER_CONSUMPTION_PER_JOB)
        self.stats.power_satisfaction = self._supply_percent(self.stats.power_capacity, self.stats.power_usage)
        self.stats.water_satisfaction = self._supply_percent(self.stats.water_capacity, self.stats.water_usage)

        zoned_tiles = 0
        service_points = 0
        fire_covered_zones = 0
        total_fire_risk = 0
        police_covered_zones = 0
        total_crime_risk = 0
        for _, _, tile in self.city_map.iter_tiles():
            if tile.zone == ZoneType.EMPTY:
                continue
            zoned_tiles += 1
            service_points += int(tile.police_coverage) + int(tile.fire_coverage) + int(tile.education_coverage)
            fire_covered_zones += int(tile.fire_coverage)
            total_fire_risk += tile.fire_risk
            police_covered_zones += int(tile.police_coverage)
            total_crime_risk += tile.crime_risk
        if zoned_tiles == 0:
            self._reset_coverage_stats()
        else:
            self._update_coverage_stats(zoned_tiles, service_points, fire_covered_zones, total_fire_risk, police_covered_zones, total_crime_risk)

    def _utility_capacity_factor(self) -> float:
        power_factor = self._capacity_factor(self.stats.power_capacity, self.stats.power_usage)
        water_factor = self._capacity_factor(self.stats.water_capacity, self.stats.water_usage)
        return min(power_factor, water_factor)

    def _capacity_factor(self, capacity: int, usage: int) -> float:
        if usage <= 0:
            return 1.0 if capacity > 0 else 0.0
        return max(MIN_CAPACITY_FACTOR, min(1.0, capacity / usage))

    def _reset_coverage_stats(self) -> None:
        """Reset all coverage and risk statistics when no zones exist."""
        self.stats.service_score = 0
        self.stats.fire_coverage_percent = 0
        self.stats.fire_uncovered_zones = 0
        self.stats.average_fire_risk = 0
        self.stats.police_coverage_percent = 0
        self.stats.police_uncovered_zones = 0
        self.stats.average_crime_risk = 0

    def _update_coverage_stats(self, zoned_tiles: int, service_points: int, fire_covered: int, total_fire_risk: int, police_covered: int, total_crime_risk: int) -> None:
        """Calculate and update coverage and risk statistics."""
        self.stats.service_score = int(service_points / (zoned_tiles * SERVICE_SCORE_DIVISOR) * 100)
        self.stats.fire_coverage_percent = int(fire_covered / zoned_tiles * 100)
        self.stats.fire_uncovered_zones = zoned_tiles - fire_covered
        self.stats.average_fire_risk = int(total_fire_risk / zoned_tiles)
        self.stats.police_coverage_percent = int(police_covered / zoned_tiles * 100)
        self.stats.police_uncovered_zones = zoned_tiles - police_covered
        self.stats.average_crime_risk = int(total_crime_risk / zoned_tiles)

    def _supply_percent(self, capacity: int, usage: int) -> int:
        if usage <= 0:
            return 100 if capacity > 0 else 0
        return self._clamp_percent(capacity / usage * 100)

    def _clamp_percent(self, value: float) -> int:
        return max(0, min(100, int(value)))

    def _add_monthly_message(self, revenue: int, expenses: int) -> None:
        if self.stats.money < 0:
            self.stats.add_message("Budget is negative. Raise taxes or slow building.")
        elif self.stats.power_capacity == 0:
            self.stats.add_message("Build a power plant and power lines.")
        elif self.stats.unpowered_zones > 0:
            self.stats.add_message("Some zones are not connected to power.")
        elif self.stats.water_capacity == 0:
            self.stats.add_message("Build a water tower and water pipes.")
        elif self.stats.unwatered_zones > 0:
            self.stats.add_message("Some zones are not connected to water.")
        elif self.stats.power_usage > self.stats.power_capacity:
            self.stats.add_message("Power demand is higher than capacity.")
        elif self.stats.water_usage > self.stats.water_capacity:
            self.stats.add_message("Water demand is higher than capacity.")
        elif self.stats.fire_uncovered_zones > 0:
            self.stats.add_message("Some zones are outside fire station coverage.")
        elif self.stats.average_fire_risk >= HIGH_RISK_THRESHOLD:
            self.stats.add_message("City fire risk is high. Add fire stations or water.")
        elif self.stats.police_uncovered_zones > 0:
            self.stats.add_message("Some zones are outside police station coverage.")
        elif self.stats.average_crime_risk >= HIGH_RISK_THRESHOLD:
            self.stats.add_message("City crime risk is high. Add police stations.")
        elif self.stats.last_population_delta > 0:
            self.stats.add_message("New residents moved in.")
        elif self.stats.last_job_delta > 0:
            self.stats.add_message("Businesses are hiring.")
        elif revenue < expenses and self.city_map.road_count() > 0:
            self.stats.add_message("Maintenance is higher than revenue.")



