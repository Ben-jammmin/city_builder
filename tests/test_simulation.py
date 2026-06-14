import unittest

from citybuilder.city_map import CityMap
from citybuilder.models import BuildingType, CityStats, ZoneType
from citybuilder.simulation import Simulation


class SimulationTests(unittest.TestCase):
    def add_basic_power_and_water(self, city_map: CityMap) -> None:
        city_map.place_building(0, 1, BuildingType.POWER_PLANT)
        city_map.place_building(2, 1, BuildingType.WATER_TOWER)
        city_map.place_road(1, 1)
        city_map.place_power_line(1, 1)
        city_map.place_water_pipe(1, 1)

    def test_paused_update_does_not_advance_time_or_budget(self) -> None:
        city_map = CityMap(4, 4)
        stats = CityStats(paused=True)
        simulation = Simulation(city_map, stats)

        simulation.update(dt=10.0, seconds_per_month=1.0)

        self.assertEqual(stats.month, 1)
        self.assertEqual(stats.money, 25000)
        self.assertEqual(simulation.elapsed, 0.0)

    def test_update_can_process_multiple_months(self) -> None:
        city_map = CityMap(4, 4)
        stats = CityStats(paused=False)
        simulation = Simulation(city_map, stats)

        simulation.update(dt=2.5, seconds_per_month=1.0)

        self.assertEqual(stats.month, 3)
        self.assertAlmostEqual(simulation.elapsed, 0.5)

    def test_road_connected_residential_zone_grows_population(self) -> None:
        city_map = CityMap(5, 5)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        self.add_basic_power_and_water(city_map)
        city_map.place_zone(1, 2, ZoneType.RESIDENTIAL)

        for _ in range(8):
            simulation.simulate_month()

        tile = city_map.get(1, 2)
        self.assertGreater(tile.development, 0.0)
        self.assertGreater(stats.population, 0)
        self.assertGreaterEqual(stats.last_revenue, 0)
        self.assertGreater(stats.last_expenses, 0)
        self.assertTrue(tile.powered)
        self.assertTrue(tile.watered)

    def test_road_without_utilities_does_not_grow_zone(self) -> None:
        city_map = CityMap(4, 4)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        city_map.place_road(1, 1)
        city_map.place_zone(1, 2, ZoneType.RESIDENTIAL)

        simulation.simulate_month()

        self.assertEqual(city_map.get(1, 2).development, 0.0)

    def test_unconnected_zone_loses_development(self) -> None:
        city_map = CityMap(3, 3)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        city_map.place_zone(1, 1, ZoneType.RESIDENTIAL)
        tile = city_map.get(1, 1)
        tile.development = 0.5

        simulation.simulate_month()

        self.assertLess(tile.development, 0.5)

    def test_commercial_and_industrial_zones_create_jobs_when_connected(self) -> None:
        city_map = CityMap(6, 6)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        self.add_basic_power_and_water(city_map)
        city_map.place_zone(1, 0, ZoneType.COMMERCIAL)
        city_map.place_zone(1, 2, ZoneType.INDUSTRIAL)

        for _ in range(10):
            simulation.simulate_month()

        self.assertGreater(stats.jobs, 0)
        self.assertGreater(city_map.get(1, 0).jobs, 0)
        self.assertGreater(city_map.get(1, 2).jobs, 0)

    def test_low_tax_city_grows_faster_than_high_tax_city(self) -> None:
        low_tax_map = CityMap(4, 4)
        high_tax_map = CityMap(4, 4)
        low_tax_stats = CityStats(tax_rate=5)
        high_tax_stats = CityStats(tax_rate=18)
        low_tax_sim = Simulation(low_tax_map, low_tax_stats)
        high_tax_sim = Simulation(high_tax_map, high_tax_stats)

        for city_map in (low_tax_map, high_tax_map):
            self.add_basic_power_and_water(city_map)
            city_map.place_zone(1, 2, ZoneType.RESIDENTIAL)

        for _ in range(6):
            low_tax_sim.simulate_month()
            high_tax_sim.simulate_month()

        self.assertGreater(
            low_tax_map.get(1, 2).development,
            high_tax_map.get(1, 2).development,
        )

    def test_negative_budget_adds_warning_message(self) -> None:
        city_map = CityMap(3, 3)
        stats = CityStats(money=-5, messages=[])
        simulation = Simulation(city_map, stats)

        simulation.simulate_month()

        self.assertIn("Budget is negative", stats.messages[-1])

    def test_power_and_water_capacity_are_reported(self) -> None:
        city_map = CityMap(4, 4)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        self.add_basic_power_and_water(city_map)

        simulation.simulate_month()

        self.assertGreater(stats.power_capacity, 0)
        self.assertGreater(stats.water_capacity, 0)
        self.assertGreater(stats.powered_tiles, 0)
        self.assertGreater(stats.watered_tiles, 0)

    def test_service_buildings_raise_service_score_for_zones(self) -> None:
        city_map = CityMap(8, 8)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        self.add_basic_power_and_water(city_map)
        city_map.place_building(4, 4, BuildingType.POLICE)
        city_map.place_building(5, 4, BuildingType.FIRE)
        city_map.place_building(4, 5, BuildingType.SCHOOL)
        city_map.place_zone(1, 2, ZoneType.RESIDENTIAL)

        simulation.simulate_month()

        tile = city_map.get(1, 2)
        self.assertTrue(tile.police_coverage)
        self.assertTrue(tile.fire_coverage)
        self.assertTrue(tile.education_coverage)
        self.assertEqual(stats.service_score, 100)

    def test_demand_values_stay_in_percent_range(self) -> None:
        city_map = CityMap(4, 4)
        stats = CityStats(population=1000, jobs=400, tax_rate=20)
        simulation = Simulation(city_map, stats)

        simulation.simulate_month()

        self.assertGreaterEqual(stats.demand_residential, 0)
        self.assertLessEqual(stats.demand_residential, 100)
        self.assertGreaterEqual(stats.demand_commercial, 0)
        self.assertLessEqual(stats.demand_commercial, 100)
        self.assertGreaterEqual(stats.demand_industrial, 0)
        self.assertLessEqual(stats.demand_industrial, 100)


if __name__ == "__main__":
    unittest.main()
