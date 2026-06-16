"""City simulation — runs every month to update growth, demand, utilities, and disasters."""
from __future__ import annotations

import random

from .city_map import CityMap
from .models import BuildingType, CityStats, Tile, ZoneType
from .settings import (
    AIRPORT_DEMAND_BOOST,
    BASE_GROWTH_RATE,
    BUILDING_MAINTENANCE,
    COMMERCIAL_CAPACITY,
    COMMERCIAL_NEIGHBOR_BONUS,
    CONGESTION_DEMAND_PENALTY,
    EDUCATION_GROWTH_BONUS,
    HEALTH_GROWTH_BONUS,
    HEALTH_RADIUS,
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
    POWER_CAPACITY_BY_BUILDING,
    POWER_LINE_MAINTENANCE,
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
    WATER_CAPACITY_BY_BUILDING,
    WATER_PIPE_MAINTENANCE,
    ZONE_MAINTENANCE,
    ZONE_LEVEL_CAPACITY_MULTIPLIERS,
    ZONE_LEVEL_GROWTH_MULTIPLIERS,
    PARK_LAND_VALUE_BONUS,
    RECREATION_LAND_VALUE,
    FIRE_UPDATE_INTERVAL,
    FIRE_IGNITION_PROB,
    FIRE_SPREAD_INTERVAL,
    FIRE_SPREAD_CHANCE,
    FIRE_BURN_RATE,
    FIRE_SUPPRESS_TIME,
    FIRE_NATURAL_EXTINGUISH,
    FIRE_EMERGENCY_COST,
    CRIME_INCIDENT_PROB,
    CRIME_DAMAGE_RATE,
    CRIME_CLEANUP_COST,
    POPULATION_MILESTONES,
    ROAD_TRAFFIC_CAPACITY,
)
from .models import POWER_SOURCE_BUILDINGS, WATER_SOURCE_BUILDINGS


class Simulation:
    def __init__(self, city_map: CityMap, stats: CityStats) -> None:
        self.city_map = city_map
        self.stats = stats
        self.elapsed = 0.0
        self._fires: dict[tuple[int, int], float] = {}  # (x,y) -> seconds burning
        self._fire_elapsed = 0.0

    def refresh_systems(self) -> None:
        """Refresh sidebar-facing city systems without advancing the calendar."""
        self._update_systems()
        for x, y, tile in self.city_map.iter_tiles():
            if tile.zone in (ZoneType.EMPTY, ZoneType.PARK):
                tile.land_value = 1.0
                tile.fire_risk = 0
                tile.crime_risk = 0
                continue
            tile.land_value = self._land_value_for(x, y)
            tile.fire_risk = self._fire_risk_for(x, y)
            tile.crime_risk = self._crime_risk_for(x, y)
        self._update_system_totals()
        self._update_demand()

    def update(self, dt: float, seconds_per_month: float) -> None:
        if self.stats.paused:
            return
        self.elapsed += dt
        self._fire_elapsed += dt
        while self._fire_elapsed >= FIRE_UPDATE_INTERVAL:
            self._fire_elapsed -= FIRE_UPDATE_INTERVAL
            self._update_fires(FIRE_UPDATE_INTERVAL)
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
        com_jobs = 0
        ind_jobs = 0
        for _, _, tile in self.city_map.iter_tiles():
            population += tile.residents
            jobs += tile.jobs
            if tile.zone == ZoneType.COMMERCIAL:
                com_jobs += tile.jobs
            elif tile.zone == ZoneType.INDUSTRIAL:
                ind_jobs += tile.jobs

        self.stats.population = population
        self.stats.jobs = jobs
        self.stats.last_population_delta = population - previous_population
        self.stats.last_job_delta = jobs - previous_jobs
        self._update_system_totals()

        tax = self.stats.tax_rate
        rev_res = int(population * tax * POPULATION_TAX_COEFFICIENT)
        rev_com = int(com_jobs * tax * JOBS_TAX_COEFFICIENT)
        rev_ind = int(ind_jobs * tax * JOBS_TAX_COEFFICIENT)
        revenue = rev_res + rev_com + rev_ind
        self.stats.rev_residential = rev_res
        self.stats.rev_commercial = rev_com
        self.stats.rev_industrial = rev_ind

        exp_roads = int(self.city_map.road_count() * ROAD_MAINTENANCE)
        exp_utilities = int(
            self.city_map.zone_maintenance_units() * ZONE_MAINTENANCE
            + self.city_map.power_line_count() * POWER_LINE_MAINTENANCE
            + self.city_map.water_pipe_count() * WATER_PIPE_MAINTENANCE
        )
        exp_buildings = int(sum(
            self.city_map.building_count(BuildingType(name)) * cost
            for name, cost in BUILDING_MAINTENANCE.items()
        ))
        exp_recreation = int(self.city_map.recreation_maintenance_cost())
        expenses = exp_roads + exp_utilities + exp_buildings + exp_recreation
        self.stats.exp_roads = exp_roads
        self.stats.exp_utilities = exp_utilities
        self.stats.exp_buildings = exp_buildings
        self.stats.exp_recreation = exp_recreation

        self.stats.last_revenue = revenue
        self.stats.last_expenses = expenses
        self.stats.money += revenue - expenses
        self.stats.advance_month()
        self._update_traffic()
        self._check_fire_ignition()
        self._check_crime_incidents()
        self._check_milestones()
        self._add_monthly_message(revenue, expenses)

    def _update_all_tiles(self) -> None:
        for x, y, tile in self.city_map.iter_tiles():
            if tile.zone in (ZoneType.EMPTY, ZoneType.PARK):
                tile.residents = 0
                tile.jobs = 0
                tile.land_value = 1.0
                tile.fire_risk = 0
                tile.crime_risk = 0
                continue

            connected = self.city_map.has_adjacent_road(x, y)
            tile.land_value = self._land_value_for(x, y)

            if connected and tile.powered and tile.watered:
                growth = (
                    self._growth_for(tile.zone)
                    * self._zone_growth_multiplier(tile.zone_level)
                    * tile.land_value
                    * self._utility_capacity_factor()
                )
                if tile.education_coverage:
                    growth *= (1.0 + EDUCATION_GROWTH_BONUS)
                if tile.health_coverage:
                    growth *= (1.0 + HEALTH_GROWTH_BONUS)
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
            elif neighbor.zone == ZoneType.PARK:
                value += RECREATION_LAND_VALUE.get(neighbor.recreation_type.value, PARK_LAND_VALUE_BONUS)
            elif neighbor.has_road:
                value += ROAD_NEIGHBOR_BONUS
        return max(LAND_VALUE_MIN, min(LAND_VALUE_MAX, value))

    def _apply_capacity(self, tile: Tile) -> None:
        tile.residents = 0
        tile.jobs = 0
        if tile.zone == ZoneType.RESIDENTIAL:
            tile.residents = int(
                RESIDENTIAL_CAPACITY
                * self._zone_capacity_multiplier(tile.zone_level)
                * tile.development
                * tile.land_value
            )
        elif tile.zone == ZoneType.COMMERCIAL:
            tile.jobs = int(
                COMMERCIAL_CAPACITY
                * self._zone_capacity_multiplier(tile.zone_level)
                * tile.development
                * tile.land_value
            )
        elif tile.zone == ZoneType.INDUSTRIAL:
            tile.jobs = int(INDUSTRIAL_CAPACITY * tile.development)

    def _zone_capacity_multiplier(self, level: int) -> float:
        return ZONE_LEVEL_CAPACITY_MULTIPLIERS.get(level, 1.0)

    def _zone_growth_multiplier(self, level: int) -> float:
        return ZONE_LEVEL_GROWTH_MULTIPLIERS.get(level, 1.0)

    def _fire_risk_for(self, x: int, y: int) -> int:
        tile = self.city_map.get(x, y)
        if tile.zone in (ZoneType.EMPTY, ZoneType.PARK):
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
        if tile.zone in (ZoneType.EMPTY, ZoneType.PARK):
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
        power_network = self._connected_network(POWER_SOURCE_BUILDINGS, "has_power_line")
        water_network = self._connected_network(WATER_SOURCE_BUILDINGS, "has_water_pipe")
        service_tiles = self._service_tiles()

        for x, y, tile in self.city_map.iter_tiles():
            tile.powered = self._tile_touches_network(x, y, power_network)
            tile.watered = self._tile_touches_network(x, y, water_network)
            tile.police_coverage = (x, y) in service_tiles["police"]
            tile.fire_coverage = (x, y) in service_tiles["fire"]
            tile.education_coverage = (x, y) in service_tiles["school"]
            tile.health_coverage = (x, y) in service_tiles["health"]

        self.stats.unpowered_zones = sum(
            1
            for _, _, tile in self.city_map.iter_tiles()
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK) and not tile.powered
        )
        self.stats.unwatered_zones = sum(
            1
            for _, _, tile in self.city_map.iter_tiles()
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK) and not tile.watered
        )
        self.stats.powered_tiles = sum(1 for _, _, tile in self.city_map.iter_tiles() if tile.powered)
        self.stats.watered_tiles = sum(1 for _, _, tile in self.city_map.iter_tiles() if tile.watered)

    def _connected_network(self, source_buildings: set[BuildingType], line_attr: str) -> set[tuple[int, int]]:
        starts = [
            (x, y)
            for x, y, tile in self.city_map.iter_tiles()
            if tile.building in source_buildings
        ]
        network = set(starts)
        frontier = list(starts)

        while frontier:
            x, y = frontier.pop()
            for nx, ny, neighbor in self.city_map.neighbors4(x, y):
                if (nx, ny) in network:
                    continue
                if getattr(neighbor, line_attr) or neighbor.building in source_buildings:
                    network.add((nx, ny))
                    frontier.append((nx, ny))

        return network

    def _tile_touches_network(self, x: int, y: int, network: set[tuple[int, int]]) -> bool:
        if (x, y) in network:
            return True
        return any((nx, ny) in network for nx, ny, _ in self.city_map.neighbors4(x, y))

    def _service_tiles(self) -> dict[str, set[tuple[int, int]]]:
        coverage = {"police": set(), "fire": set(), "school": set(), "health": set()}
        building_to_key = {
            BuildingType.POLICE: ("police", POLICE_RADIUS),
            BuildingType.FIRE: ("fire", FIRE_RADIUS),
            BuildingType.SCHOOL: ("school", SERVICE_RADIUS),
            BuildingType.HOSPITAL: ("health", HEALTH_RADIUS),
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

    def _update_traffic(self) -> None:
        for _, _, tile in self.city_map.iter_tiles():
            if tile.has_road:
                tile.traffic_load = 0
        _mult = {ZoneType.RESIDENTIAL: 5, ZoneType.COMMERCIAL: 10, ZoneType.INDUSTRIAL: 15}
        for x, y, tile in self.city_map.iter_tiles():
            m = _mult.get(tile.zone, 0)
            if m == 0 or tile.development < 0.1:
                continue
            traffic = int(tile.development * m)
            road_nbrs = [(nx, ny) for nx, ny, t in self.city_map.neighbors4(x, y) if t.has_road]
            if road_nbrs:
                per_road = max(1, traffic // len(road_nbrs))
                for nx, ny in road_nbrs:
                    nt = self.city_map.get(nx, ny)
                    nt.traffic_load = min(99, nt.traffic_load + per_road)

    def _update_demand(self) -> None:
        population = self.stats.population
        jobs = self.stats.jobs
        service_bonus = self.stats.service_score * SERVICE_BONUS_MULTIPLIER
        utility_bonus = self._utility_capacity_factor() * UTILITY_BONUS_MULTIPLIER
        res_tax_penalty = self.stats.tax_rate * TAX_PENALTY_RESIDENTIAL
        com_tax_penalty = self.stats.tax_rate * TAX_PENALTY_COMMERCIAL
        ind_tax_penalty = self.stats.tax_rate * TAX_PENALTY_INDUSTRIAL

        train_boost = self.city_map.building_count(BuildingType.TRAIN_STATION) * TRAIN_STATION_DEMAND_BOOST
        airport_boost = self.city_map.building_count(BuildingType.AIRPORT) * AIRPORT_DEMAND_BOOST
        transport_bonus = train_boost + airport_boost

        rec_res_bonus, rec_com_bonus = self.city_map.recreation_demand_bonus()

        congested = sum(
            1 for _, _, t in self.city_map.iter_tiles()
            if t.has_road and t.traffic_load > ROAD_TRAFFIC_CAPACITY
        )
        congestion_penalty = min(25, congested * CONGESTION_DEMAND_PENALTY)

        self.stats.demand_residential = self._clamp_percent(
            45
            + jobs * 0.45
            - population * 0.18
            + service_bonus
            + utility_bonus
            - res_tax_penalty
            + transport_bonus * 0.3
            + rec_res_bonus * 0.4
        )
        self.stats.demand_commercial = self._clamp_percent(
            40
            + population * 0.22
            - jobs * 0.10
            + service_bonus
            - com_tax_penalty
            + transport_bonus
            + rec_com_bonus * 0.5
            - congestion_penalty
        )
        self.stats.demand_industrial = self._clamp_percent(
            38
            + population * 0.18
            - jobs * 0.08
            + utility_bonus
            - ind_tax_penalty
            + transport_bonus * 0.7
        )

    def _update_system_totals(self) -> None:
        self.stats.power_capacity = self._capacity_from_buildings(POWER_CAPACITY_BY_BUILDING)
        self.stats.water_capacity = self._capacity_from_buildings(WATER_CAPACITY_BY_BUILDING)
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
        education_covered_zones = 0
        health_covered_zones = 0
        for _, _, tile in self.city_map.iter_tiles():
            if tile.zone in (ZoneType.EMPTY, ZoneType.PARK):
                continue
            zoned_tiles += 1
            service_points += (
                int(tile.police_coverage) + int(tile.fire_coverage)
                + int(tile.education_coverage) + int(tile.health_coverage)
            )
            fire_covered_zones += int(tile.fire_coverage)
            total_fire_risk += tile.fire_risk
            police_covered_zones += int(tile.police_coverage)
            total_crime_risk += tile.crime_risk
            education_covered_zones += int(tile.education_coverage)
            health_covered_zones += int(tile.health_coverage)
        if zoned_tiles == 0:
            self._reset_coverage_stats()
        else:
            self._update_coverage_stats(
                zoned_tiles, service_points,
                fire_covered_zones, total_fire_risk,
                police_covered_zones, total_crime_risk,
                education_covered_zones, health_covered_zones,
            )

    def _utility_capacity_factor(self) -> float:
        power_factor = self._capacity_factor(self.stats.power_capacity, self.stats.power_usage)
        water_factor = self._capacity_factor(self.stats.water_capacity, self.stats.water_usage)
        return min(power_factor, water_factor)

    def _capacity_from_buildings(self, capacity_by_building: dict[str, int]) -> int:
        return sum(
            capacity_by_building.get(tile.building.value, 0)
            for _, _, tile in self.city_map.iter_tiles()
        )

    def _capacity_factor(self, capacity: int, usage: int) -> float:
        if usage <= 0:
            return 1.0 if capacity > 0 else MIN_CAPACITY_FACTOR
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
        self.stats.education_coverage_percent = 0
        self.stats.health_coverage_percent = 0

    def _update_coverage_stats(
        self,
        zoned_tiles: int,
        service_points: int,
        fire_covered: int,
        total_fire_risk: int,
        police_covered: int,
        total_crime_risk: int,
        edu_covered: int,
        health_covered: int,
    ) -> None:
        """Calculate and update coverage and risk statistics."""
        self.stats.service_score = min(100, int(service_points / (zoned_tiles * SERVICE_SCORE_DIVISOR) * 100))
        self.stats.fire_coverage_percent = int(fire_covered / zoned_tiles * 100)
        self.stats.fire_uncovered_zones = zoned_tiles - fire_covered
        self.stats.average_fire_risk = int(total_fire_risk / zoned_tiles)
        self.stats.police_coverage_percent = int(police_covered / zoned_tiles * 100)
        self.stats.police_uncovered_zones = zoned_tiles - police_covered
        self.stats.average_crime_risk = int(total_crime_risk / zoned_tiles)
        self.stats.education_coverage_percent = int(edu_covered / zoned_tiles * 100)
        self.stats.health_coverage_percent = int(health_covered / zoned_tiles * 100)

    def _supply_percent(self, capacity: int, usage: int) -> int:
        if usage <= 0:
            return 100 if capacity > 0 else 0
        return self._clamp_percent(capacity / usage * 100)

    def _clamp_percent(self, value: float) -> int:
        return max(0, min(100, int(value)))

    # ------------------------------------------------------------------ #
    # Fire disaster                                                        #
    # ------------------------------------------------------------------ #

    def _ignite_tile(self, x: int, y: int) -> None:
        if (x, y) in self._fires:
            return
        self._fires[(x, y)] = 0.0
        self.city_map.get(x, y).on_fire = True

    def _extinguish_tile(self, x: int, y: int) -> None:
        self._fires.pop((x, y), None)
        self.city_map.get(x, y).on_fire = False

    def _update_fires(self, tick: float) -> None:
        to_extinguish: list[tuple[int, int]] = []
        to_spread: list[tuple[int, int]] = []

        for pos in list(self._fires):
            x, y = pos
            self._fires[pos] += tick
            burn_time = self._fires[pos]
            tile = self.city_map.get(x, y)

            # Tile was bulldozed — clear fire
            if tile.zone in (ZoneType.EMPTY, ZoneType.PARK):
                to_extinguish.append(pos)
                continue

            tile.development = max(0.0, tile.development - FIRE_BURN_RATE)

            if tile.development <= 0.0:
                to_extinguish.append(pos)
                continue

            if tile.fire_coverage and burn_time >= FIRE_SUPPRESS_TIME:
                to_extinguish.append(pos)
                self.stats.add_message("Fire contained by fire station.")
                continue

            if burn_time >= FIRE_NATURAL_EXTINGUISH:
                to_extinguish.append(pos)
                continue

            # Spread check on interval boundary
            prev = int((burn_time - tick) / FIRE_SPREAD_INTERVAL)
            curr = int(burn_time / FIRE_SPREAD_INTERVAL)
            if curr > prev:
                to_spread.append(pos)

        for pos in to_extinguish:
            self._extinguish_tile(*pos)

        for x, y in to_spread:
            for nx, ny, neighbor in self.city_map.neighbors4(x, y):
                if (nx, ny) in self._fires:
                    continue
                if neighbor.zone in (ZoneType.EMPTY, ZoneType.PARK):
                    continue
                if neighbor.development < 0.1:
                    continue
                chance = FIRE_SPREAD_CHANCE * (1.4 if not neighbor.fire_coverage else 0.5)
                if random.random() < chance:
                    self._ignite_tile(nx, ny)

    def _check_fire_ignition(self) -> None:
        candidates = [
            (x, y)
            for x, y, tile in self.city_map.iter_tiles()
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK)
            and tile.fire_risk >= HIGH_RISK_THRESHOLD
            and not tile.fire_coverage
            and tile.development > 0.15
            and (x, y) not in self._fires
        ]
        if not candidates:
            return
        total_prob = min(0.55, len(candidates) * FIRE_IGNITION_PROB)
        if random.random() < total_prob:
            x, y = random.choice(candidates)
            self._ignite_tile(x, y)
            self.stats.money -= FIRE_EMERGENCY_COST
            self.stats.add_message(f"Fire outbreak! Emergency services: ${FIRE_EMERGENCY_COST}.")

    # ------------------------------------------------------------------ #
    # Crime incident                                                       #
    # ------------------------------------------------------------------ #

    def _check_crime_incidents(self) -> None:
        candidates = [
            (x, y)
            for x, y, tile in self.city_map.iter_tiles()
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK)
            and tile.crime_risk >= HIGH_RISK_THRESHOLD
            and not tile.police_coverage
            and tile.development > 0.15
        ]
        if not candidates:
            return
        total_prob = min(0.50, len(candidates) * CRIME_INCIDENT_PROB)
        if random.random() >= total_prob:
            return
        x, y = random.choice(candidates)
        tile = self.city_map.get(x, y)
        tile.development = max(0.0, tile.development - CRIME_DAMAGE_RATE)
        self.stats.money -= CRIME_CLEANUP_COST
        self.stats.add_message(f"Crime incident! Property damage. Cleanup: ${CRIME_CLEANUP_COST}.")

    # ------------------------------------------------------------------ #
    # City milestones                                                      #
    # ------------------------------------------------------------------ #

    def _check_milestones(self) -> None:
        for pop, title, grant in POPULATION_MILESTONES:
            if self.stats.population >= pop and self.stats.milestone_pop < pop:
                self.stats.milestone_pop = pop
                self.stats.money += grant
                self.stats.add_message(
                    f"Milestone: {title}! ({pop:,} residents) State grant: ${grant:,}."
                )
                break  # one milestone per month

    def _add_monthly_message(self, revenue: int, expenses: int) -> None:
        messages: list[str] = []
        if self.stats.money < 0:
            messages.append("Budget is negative. Raise taxes or slow building.")
        else:
            if self.stats.power_capacity == 0:
                messages.append("Build a power plant and power lines.")
            elif self.stats.unpowered_zones > 0:
                messages.append("Some zones are not connected to power.")
            if self.stats.water_capacity == 0:
                messages.append("Build a water tower and water pipes.")
            elif self.stats.unwatered_zones > 0:
                messages.append("Some zones are not connected to water.")
            if self.stats.power_capacity > 0 and self.stats.power_usage > self.stats.power_capacity:
                messages.append("Power demand is higher than capacity.")
            if self.stats.water_capacity > 0 and self.stats.water_usage > self.stats.water_capacity:
                messages.append("Water demand is higher than capacity.")
            if self.stats.fire_uncovered_zones > 0:
                messages.append("Some zones are outside fire station coverage.")
            if self.stats.average_fire_risk >= HIGH_RISK_THRESHOLD:
                messages.append("City fire risk is high. Add fire stations or water.")
            if self.stats.police_uncovered_zones > 0:
                messages.append("Some zones are outside police station coverage.")
            if self.stats.average_crime_risk >= HIGH_RISK_THRESHOLD:
                messages.append("City crime risk is high. Add police stations.")
            if self.stats.education_coverage_percent < 50 and self.stats.population >= 500:
                messages.append("Build schools — education coverage boosts zone growth.")
            if self.stats.health_coverage_percent < 50 and self.stats.population >= 1000:
                messages.append("Build hospitals — health coverage grows your city faster.")

        if not messages:
            if self.stats.last_population_delta > 0:
                messages.append("New residents moved in.")
            if self.stats.last_job_delta > 0:
                messages.append("Businesses are hiring.")
            if revenue < expenses and self.city_map.road_count() > 0:
                messages.append("Maintenance is higher than revenue.")

        for message in reversed(messages[:3]):
            if message not in self.stats.messages[-5:]:
                self.stats.add_message(message)
