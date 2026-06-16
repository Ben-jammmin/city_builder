"""
simulation.py — The city brain: runs every in-game month to update growth,
demand, utilities, disasters, and the city budget.

Key concepts used here
-----------------------
BFS (Breadth-First Search)
  _coverage_from_building() spreads outward from each service building
  tile-by-tile, adding every reachable tile within the service radius to
  the covered set.  BFS guarantees that every tile is visited exactly once
  in order of Manhattan distance.

Utility networks
  Power and water spread through a connected graph of lines/pipes.
  _connected_network() finds all tiles reachable from source buildings
  via the relevant infrastructure (flood-fill / BFS).

Growth model
  Each zone tile grows a little every month if it has road access, power,
  and water.  Growth is multiplied by:
    - demand (0-1 scale)
    - land value (0.65-1.25 scale)
    - tax factor (falls off as tax rises)
    - education / health bonuses
  Zones shrink if any required service is missing.

Disasters
  Fire: tiles with high fire risk can spontaneously ignite each month.
        Fires spread to adjacent zones every few seconds of real time.
  Crime: high-crime tiles suffer occasional incidents that set back development.
"""
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
    """Runs the monthly city simulation and the real-time fire sub-system."""

    def __init__(self, city_map: CityMap, stats: CityStats) -> None:
        self.city_map = city_map
        self.stats = stats
        self.elapsed = 0.0    # seconds since the last monthly tick
        # Tracks active fires: maps (x, y) → seconds the tile has been burning.
        self._fires: dict[tuple[int, int], float] = {}
        self._fire_elapsed = 0.0   # seconds since the last fire update tick

    def refresh_systems(self) -> None:
        """
        Recalculates utility coverage and risk values without advancing the calendar.
        Called after the player places or removes any tile, so the UI stays current.
        """
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
        """
        Called every frame with dt (elapsed seconds since last frame).
        Advances the fire sub-system on its own fast timer, and triggers
        simulate_month() once enough real-time seconds have accumulated.
        """
        if self.stats.paused:
            return
        self.elapsed += dt
        self._fire_elapsed += dt

        # Fire updates run at FIRE_UPDATE_INTERVAL regardless of sim speed.
        while self._fire_elapsed >= FIRE_UPDATE_INTERVAL:
            self._fire_elapsed -= FIRE_UPDATE_INTERVAL
            self._update_fires(FIRE_UPDATE_INTERVAL)

        # Monthly tick fires once per seconds_per_month of real time.
        while self.elapsed >= seconds_per_month:
            self.elapsed -= seconds_per_month
            self.simulate_month()

    def simulate_month(self) -> None:
        """
        Advances the in-game calendar by one month.

        Order of operations:
          1. Recalculate utility coverage (power, water, services)
          2. Grow or shrink each zone tile
          3. Count population and jobs
          4. Calculate tax revenue and maintenance expenses
          5. Apply the net income to the budget
          6. Update traffic load
          7. Check for fire ignitions and crime incidents
          8. Check population milestones
          9. Generate advisor messages
        """
        previous_population = self.stats.population
        previous_jobs = self.stats.jobs

        self._update_systems()
        self._update_system_totals()
        self._update_demand()
        self._update_all_tiles()

        # Count totals across all tiles.
        population = 0
        jobs = 0
        com_jobs = 0   # commercial jobs taxed separately from industrial
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

        # ── Revenue ─────────────────────────────────────────────────────
        # Tax is collected per resident and per job; commercial and industrial
        # each have their own per-job coefficient (see settings.py).
        tax = self.stats.tax_rate
        rev_res = int(population * tax * POPULATION_TAX_COEFFICIENT)
        rev_com = int(com_jobs * tax * JOBS_TAX_COEFFICIENT)
        rev_ind = int(ind_jobs * tax * JOBS_TAX_COEFFICIENT)
        revenue = rev_res + rev_com + rev_ind
        self.stats.rev_residential = rev_res
        self.stats.rev_commercial = rev_com
        self.stats.rev_industrial = rev_ind

        # ── Expenses ─────────────────────────────────────────────────────
        exp_roads = int(self.city_map.road_count() * ROAD_MAINTENANCE)
        exp_utilities = int(
            self.city_map.zone_maintenance_units() * ZONE_MAINTENANCE
            + self.city_map.power_line_count() * POWER_LINE_MAINTENANCE
            + self.city_map.water_pipe_count() * WATER_PIPE_MAINTENANCE
        )
        exp_buildings = int(sum(
            # Multiply per-building maintenance cost by how many of that type exist.
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
        # Net income applied to the player's budget.
        self.stats.money += revenue - expenses
        self.stats.advance_month()
        self._update_traffic()
        self._check_fire_ignition()
        self._check_crime_incidents()
        self._check_milestones()
        self._add_monthly_message(revenue, expenses)

    # ── Per-tile growth ────────────────────────────────────────────────────────

    def _update_all_tiles(self) -> None:
        """Updates development, risk scores, and resident/job counts on every tile."""
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
                # Zone can grow: base rate × demand × land value × utility capacity.
                growth = (
                    self._growth_for(tile.zone)
                    * self._zone_growth_multiplier(tile.zone_level)
                    * tile.land_value
                    * self._utility_capacity_factor()
                )
                # Extra bonuses for education and health coverage.
                if tile.education_coverage:
                    growth *= (1.0 + EDUCATION_GROWTH_BONUS)
                if tile.health_coverage:
                    growth *= (1.0 + HEALTH_GROWTH_BONUS)
                # Clamp development at 1.0 (fully built-up).
                tile.development = min(1.0, tile.development + growth)
            else:
                # Missing road, power, or water — zone slowly shrinks.
                tile.development = max(0.0, tile.development - DEVELOPMENT_DECLINE_RATE)

            # Very high tax rates cause an extra development penalty.
            if self.stats.tax_rate >= HIGH_TAX_THRESHOLD:
                tile.development = max(0.0, tile.development - HIGH_TAX_DECLINE_RATE)

            tile.fire_risk = self._fire_risk_for(x, y)
            tile.crime_risk = self._crime_risk_for(x, y)
            self._apply_capacity(tile)

    def _growth_for(self, zone: ZoneType) -> float:
        """
        Calculates the base monthly growth increment for a zone type.

        tax_factor falls from ~1.2 (at 0% tax) toward MIN_TAX_FACTOR (at max tax).
        demand_factor converts the 0-100 demand value to a 0-1 multiplier.
        """
        tax_factor = max(MIN_TAX_FACTOR, TAX_FACTOR_BASELINE - self.stats.tax_rate / TAX_RATE_PENALTY_FACTOR)
        demand_factor = self.stats.demand_for(zone) / 100
        return (BASE_GROWTH_RATE + DEMAND_GROWTH_MULTIPLIER * demand_factor) * tax_factor

    def _land_value_for(self, x: int, y: int) -> float:
        """
        Calculates a tile's land value multiplier based on nearby services and neighbours.

        Starts at 1.0 (neutral). Bonuses from police/fire/education coverage, commercial
        neighbours, and roads are added. Industrial neighbours subtract value.
        Result is clamped between LAND_VALUE_MIN and LAND_VALUE_MAX.
        """
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
                value -= INDUSTRIAL_NEIGHBOR_PENALTY   # industrial zones lower nearby land value
            elif neighbor.zone == ZoneType.PARK:
                # Each recreation type has a different land value bonus.
                value += RECREATION_LAND_VALUE.get(neighbor.recreation_type.value, PARK_LAND_VALUE_BONUS)
            elif neighbor.has_road:
                value += ROAD_NEIGHBOR_BONUS
        return max(LAND_VALUE_MIN, min(LAND_VALUE_MAX, value))

    def _apply_capacity(self, tile: Tile) -> None:
        """
        Converts a tile's development score into actual residents or jobs.

        Capacity is scaled by zone level (dense zones hold more people),
        development (0-1 how built-up the tile is), and land value.
        """
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
            # Industrial capacity is not boosted by land value (raw industry).
            tile.jobs = int(INDUSTRIAL_CAPACITY * tile.development)

    def _zone_capacity_multiplier(self, level: int) -> float:
        """Returns the capacity multiplier for a zone level (level 2 = dense)."""
        return ZONE_LEVEL_CAPACITY_MULTIPLIERS.get(level, 1.0)

    def _zone_growth_multiplier(self, level: int) -> float:
        """Dense zones grow more slowly per month (they just hold more when fully developed)."""
        return ZONE_LEVEL_GROWTH_MULTIPLIERS.get(level, 1.0)

    # ── Risk calculations ──────────────────────────────────────────────────────

    def _fire_risk_for(self, x: int, y: int) -> int:
        """
        Calculates a fire risk percentage (0-100) for a zone tile.

        Risk increases with:
          - development level (more buildings = more fuel)
          - industrial zone type (higher base risk)
          - industrial neighbours (proximity to chemical/production hazards)
          - no fire station coverage
          - no water supply
          - no road access (fire trucks can't reach it)
        """
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

        # Count adjacent industrial tiles; each one adds risk.
        industrial_neighbors = sum(
            1 for _, _, neighbor in self.city_map.neighbors8(x, y) if neighbor.zone == ZoneType.INDUSTRIAL
        )
        risk += industrial_neighbors * FIRE_RISK_INDUSTRIAL_NEIGHBOR

        if tile.fire_coverage:
            risk -= FIRE_RISK_COVERAGE_REDUCTION    # fire station coverage reduces risk
        else:
            risk += FIRE_RISK_NO_COVERAGE
        if not tile.watered:
            risk += FIRE_RISK_NO_WATER
        if not self.city_map.has_adjacent_road(x, y):
            risk += FIRE_RISK_NO_ROAD

        return self._clamp_percent(risk)

    def _crime_risk_for(self, x: int, y: int) -> int:
        """
        Calculates a crime risk percentage (0-100) for a zone tile.

        Similar structure to fire risk: base + zone modifier + neighbour effects
        + service coverage modifier + economic stress from high taxes.
        """
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

        # Commercial areas attract more criminal activity.
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
            risk += CRIME_RISK_HIGH_TAX    # economic strain correlates with crime

        return self._clamp_percent(risk)

    # ── Utility network propagation ────────────────────────────────────────────

    def _update_systems(self) -> None:
        """
        Recalculates which tiles have power, water, police, fire, education,
        and health coverage. Called at the start of each month.
        """
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

        # Update the count of un-served zones for the sidebar display.
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
        """
        Flood-fill (BFS) from all source buildings outward through connected
        infrastructure lines (power lines or water pipes).

        Returns the set of all (x, y) tiles that are part of the network.
        A zone tile is powered/watered if any of its 4 neighbours is in the network.
        """
        # Start the search from every source building on the map.
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
                    continue    # already visited
                # Propagate through tiles that have the relevant line type.
                if getattr(neighbor, line_attr) or neighbor.building in source_buildings:
                    network.add((nx, ny))
                    frontier.append((nx, ny))

        return network

    def _tile_touches_network(self, x: int, y: int, network: set[tuple[int, int]]) -> bool:
        """
        Returns True if the tile at (x, y) is in the network, OR if any
        orthogonal neighbour is in the network. This lets zone tiles receive
        utilities without needing a line/pipe directly on them.
        """
        if (x, y) in network:
            return True
        return any((nx, ny) in network for nx, ny, _ in self.city_map.neighbors4(x, y))

    def _service_tiles(self) -> dict[str, set[tuple[int, int]]]:
        """
        Runs BFS from each police/fire/school/hospital building to find all tiles
        within their service radius. Returns a dict of coverage sets by service type.
        """
        coverage = {"police": set(), "fire": set(), "school": set(), "health": set()}
        building_to_key = {
            BuildingType.POLICE:   ("police", POLICE_RADIUS),
            BuildingType.FIRE:     ("fire",   FIRE_RADIUS),
            BuildingType.SCHOOL:   ("school", SERVICE_RADIUS),
            BuildingType.HOSPITAL: ("health", HEALTH_RADIUS),
        }

        # Use BFS from each service building for efficient coverage calculation.
        for x, y, tile in self.city_map.iter_tiles():
            service_info = building_to_key.get(tile.building)
            if service_info is None:
                continue
            key, radius = service_info
            self._coverage_from_building(x, y, key, radius, coverage)
        return coverage

    def _coverage_from_building(self, start_x: int, start_y: int, key: str, radius: int, coverage: dict) -> None:
        """
        BFS outward from (start_x, start_y), adding every tile within Manhattan
        distance `radius` to coverage[key].

        Manhattan distance = |dx| + |dy| — same as counting steps on a grid.
        """
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

    # ── Traffic simulation ─────────────────────────────────────────────────────

    def _update_traffic(self) -> None:
        """
        Estimates traffic load on road tiles based on adjacent zone development.

        Residential generates 5 units per development point, commercial 10,
        industrial 15. Load is distributed evenly among adjacent road tiles.
        """
        # Reset all road traffic each month.
        for _, _, tile in self.city_map.iter_tiles():
            if tile.has_road:
                tile.traffic_load = 0
        # Traffic generated per development unit by zone type.
        _mult = {ZoneType.RESIDENTIAL: 5, ZoneType.COMMERCIAL: 10, ZoneType.INDUSTRIAL: 15}
        for x, y, tile in self.city_map.iter_tiles():
            m = _mult.get(tile.zone, 0)
            if m == 0 or tile.development < 0.1:
                continue
            traffic = int(tile.development * m)
            road_nbrs = [(nx, ny) for nx, ny, t in self.city_map.neighbors4(x, y) if t.has_road]
            if road_nbrs:
                # Distribute the zone's traffic evenly across adjacent road tiles.
                per_road = max(1, traffic // len(road_nbrs))
                for nx, ny in road_nbrs:
                    nt = self.city_map.get(nx, ny)
                    nt.traffic_load = min(99, nt.traffic_load + per_road)

    # ── Demand calculation ─────────────────────────────────────────────────────

    def _update_demand(self) -> None:
        """
        Recalculates the demand values (0-100) for each zone type.

        Demand drives how fast zones grow. Key factors:
          - Residential demand rises when there are more jobs than people.
          - Commercial demand rises with population (more customers).
          - Industrial demand rises with population (more workers).
          - High taxes, traffic congestion, and low utility capacity all suppress demand.
          - Recreation, transport infrastructure, and services boost demand.
        """
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

        # Recreation tiles contribute to residential and commercial demand.
        rec_res_bonus, rec_com_bonus = self.city_map.recreation_demand_bonus()

        # Count congested road tiles and cap the penalty.
        congested = sum(
            1 for _, _, t in self.city_map.iter_tiles()
            if t.has_road and t.traffic_load > ROAD_TRAFFIC_CAPACITY
        )
        congestion_penalty = min(25, congested * CONGESTION_DEMAND_PENALTY)

        # Residential: more jobs → people want to move in; high population satisfies demand.
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
        # Commercial: more people → more customers; congestion hurts shoppers.
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
        # Industrial: needs workers (population) and utility supply.
        self.stats.demand_industrial = self._clamp_percent(
            38
            + population * 0.18
            - jobs * 0.08
            + utility_bonus
            - ind_tax_penalty
            + transport_bonus * 0.7
        )

    # ── System totals ──────────────────────────────────────────────────────────

    def _update_system_totals(self) -> None:
        """Recalculates city-wide utility and service statistics shown in the sidebar."""
        self.stats.power_capacity = self._capacity_from_buildings(POWER_CAPACITY_BY_BUILDING)
        self.stats.water_capacity = self._capacity_from_buildings(WATER_CAPACITY_BY_BUILDING)
        self.stats.power_usage = int(self.stats.population * POWER_CONSUMPTION_PER_RESIDENT + self.stats.jobs * POWER_CONSUMPTION_PER_JOB)
        self.stats.water_usage = int(self.stats.population * WATER_CONSUMPTION_PER_RESIDENT + self.stats.jobs * WATER_CONSUMPTION_PER_JOB)
        self.stats.power_satisfaction = self._supply_percent(self.stats.power_capacity, self.stats.power_usage)
        self.stats.water_satisfaction = self._supply_percent(self.stats.water_capacity, self.stats.water_usage)

        # Tally service coverage and risk across all non-empty, non-park zones.
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
            # A tile that has all four services earns 4 service points.
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
        """
        Returns a 0-1 factor representing how well the city's utilities meet demand.
        Takes the minimum of power and water factors, so a shortage in either counts.
        """
        power_factor = self._capacity_factor(self.stats.power_capacity, self.stats.power_usage)
        water_factor = self._capacity_factor(self.stats.water_capacity, self.stats.water_usage)
        return min(power_factor, water_factor)

    def _capacity_from_buildings(self, capacity_by_building: dict[str, int]) -> int:
        """Sums the utility capacity provided by all buildings that appear in the dict."""
        return sum(
            capacity_by_building.get(tile.building.value, 0)
            for _, _, tile in self.city_map.iter_tiles()
        )

    def _capacity_factor(self, capacity: int, usage: int) -> float:
        """
        Returns a 0-1 fraction showing how well supply meets demand.
        Returns 1.0 when there is no demand, MIN_CAPACITY_FACTOR when capacity is zero.
        """
        if usage <= 0:
            return 1.0  # no demand means no shortfall
        if capacity <= 0:
            return MIN_CAPACITY_FACTOR
        return max(MIN_CAPACITY_FACTOR, min(1.0, capacity / usage))

    def _reset_coverage_stats(self) -> None:
        """Resets all coverage and risk statistics when no zones exist yet."""
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
        """Calculates and stores percentage-based coverage and risk statistics."""
        # Service score: average fraction of maximum possible service points, as a percent.
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
        """Returns the supply-to-demand ratio as a 0-100 integer percentage."""
        if usage <= 0:
            return 100 if capacity > 0 else 0
        return self._clamp_percent(capacity / usage * 100)

    def _clamp_percent(self, value: float) -> int:
        """Clamps a float to the integer range [0, 100]."""
        return max(0, min(100, int(value)))

    # ── Fire disaster ──────────────────────────────────────────────────────────

    def _ignite_tile(self, x: int, y: int) -> None:
        """Starts a fire on tile (x, y) and records it in the active fires dict."""
        if (x, y) in self._fires:
            return    # already burning
        self._fires[(x, y)] = 0.0
        self.city_map.get(x, y).on_fire = True

    def _extinguish_tile(self, x: int, y: int) -> None:
        """Removes a fire from tile (x, y) and clears the on_fire flag."""
        self._fires.pop((x, y), None)
        self.city_map.get(x, y).on_fire = False

    def _update_fires(self, tick: float) -> None:
        """
        Advances all active fires by one real-time tick.

        For each burning tile:
          - Increment burn time
          - Reduce development (buildings burning away)
          - Extinguish if: fully burned, suppressed by fire station, or burned out naturally
          - Attempt to spread to adjacent zone tiles
        """
        to_extinguish: list[tuple[int, int]] = []
        to_spread: list[tuple[int, int]] = []

        for pos in list(self._fires):
            x, y = pos
            self._fires[pos] += tick
            burn_time = self._fires[pos]
            tile = self.city_map.get(x, y)

            # Tile was bulldozed while on fire — clear the fire record.
            if tile.zone in (ZoneType.EMPTY, ZoneType.PARK):
                to_extinguish.append(pos)
                continue

            # Burn away development each tick.
            tile.development = max(0.0, tile.development - FIRE_BURN_RATE)

            if tile.development <= 0.0:
                # Building fully destroyed.
                to_extinguish.append(pos)
                continue

            # Fire suppression: fire coverage + enough time → extinguish.
            if tile.fire_coverage and burn_time >= FIRE_SUPPRESS_TIME:
                to_extinguish.append(pos)
                self.stats.add_message("Fire contained by fire station.")
                continue

            # Fires burn out naturally after a long time regardless.
            if burn_time >= FIRE_NATURAL_EXTINGUISH:
                to_extinguish.append(pos)
                continue

            # Check whether it's time to attempt spreading based on spread interval.
            prev = int((burn_time - tick) / FIRE_SPREAD_INTERVAL)
            curr = int(burn_time / FIRE_SPREAD_INTERVAL)
            if curr > prev:
                to_spread.append(pos)

        for pos in to_extinguish:
            self._extinguish_tile(*pos)

        for x, y in to_spread:
            for nx, ny, neighbor in self.city_map.neighbors4(x, y):
                if (nx, ny) in self._fires:
                    continue    # already burning
                if neighbor.zone in (ZoneType.EMPTY, ZoneType.PARK):
                    continue    # fire doesn't spread to empty or park tiles
                if neighbor.development < 0.1:
                    continue    # barely-developed tiles don't catch fire easily
                # Fire station coverage greatly reduces the chance of fire spreading.
                chance = FIRE_SPREAD_CHANCE * (1.4 if not neighbor.fire_coverage else 0.5)
                if random.random() < chance:
                    self._ignite_tile(nx, ny)

    def _check_fire_ignition(self) -> None:
        """
        Each month, randomly ignites one high-risk uncovered tile.

        The probability of any ignition scales with the number of at-risk tiles,
        capped at 55% per month so cities don't burn down instantly.
        """
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

    # ── Crime incident ─────────────────────────────────────────────────────────

    def _check_crime_incidents(self) -> None:
        """
        Each month, randomly triggers a crime incident in a high-crime tile.
        The incident sets back development and charges a cleanup fee.
        """
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

    # ── City milestones ────────────────────────────────────────────────────────

    def _check_milestones(self) -> None:
        """
        Awards a title and a one-time state grant when population crosses a threshold.
        Only one milestone can be awarded per month, even if multiple thresholds are crossed.
        """
        for pop, title, grant in POPULATION_MILESTONES:
            if self.stats.population >= pop and self.stats.milestone_pop < pop:
                self.stats.milestone_pop = pop
                self.stats.money += grant
                self.stats.add_message(
                    f"Milestone: {title}! ({pop:,} residents) State grant: ${grant:,}."
                )
                break  # one milestone per month

    # ── Monthly advisor messages ───────────────────────────────────────────────

    def _add_monthly_message(self, revenue: int, expenses: int) -> None:
        """
        Adds 1-3 advisor messages describing the most pressing city issues.
        Priority: budget crisis > utility warnings > service warnings > good news.
        """
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
            # No problems — report positive news instead.
            if self.stats.last_population_delta > 0:
                messages.append("New residents moved in.")
            if self.stats.last_job_delta > 0:
                messages.append("Businesses are hiring.")
            if revenue < expenses and self.city_map.road_count() > 0:
                messages.append("Maintenance is higher than revenue.")

        # Add up to 3 messages, most important first, skipping any already in the feed.
        for message in reversed(messages[:3]):
            if message not in self.stats.messages[-5:]:
                self.stats.add_message(message)
