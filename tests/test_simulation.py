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

    def test_zone_growth_takes_more_than_one_year_to_max_out(self) -> None:
        city_map = CityMap(5, 5)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        self.add_basic_power_and_water(city_map)
        city_map.place_zone(1, 2, ZoneType.RESIDENTIAL)

        for _ in range(12):
            simulation.simulate_month()

        self.assertGreater(city_map.get(1, 2).development, 0.0)
        self.assertLess(city_map.get(1, 2).development, 1.0)

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
        self.assertEqual(stats.power_satisfaction, 100)
        self.assertEqual(stats.water_satisfaction, 100)

    def test_large_utility_buildings_provide_more_capacity(self) -> None:
        city_map = CityMap(4, 4)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        city_map.place_building(0, 0, BuildingType.LARGE_POWER_PLANT)
        city_map.place_building(1, 0, BuildingType.LARGE_WATER_TOWER)

        simulation._update_system_totals()

        self.assertEqual(stats.power_capacity, 650)
        self.assertEqual(stats.water_capacity, 520)

    def test_dense_residential_and_commercial_zones_have_more_capacity(self) -> None:
        standard_map = CityMap(5, 5)
        dense_map = CityMap(5, 5)
        standard_stats = CityStats()
        dense_stats = CityStats()
        standard_sim = Simulation(standard_map, standard_stats)
        dense_sim = Simulation(dense_map, dense_stats)

        for city_map in (standard_map, dense_map):
            self.add_basic_power_and_water(city_map)
            city_map.place_zone(1, 2, ZoneType.RESIDENTIAL)
            city_map.place_zone(2, 2, ZoneType.COMMERCIAL)
            city_map.get(1, 2).development = 1.0
            city_map.get(2, 2).development = 1.0
            city_map.get(1, 2).land_value = 1.0
            city_map.get(2, 2).land_value = 1.0
        dense_map.place_zone(1, 2, ZoneType.RESIDENTIAL, level=2)
        dense_map.place_zone(2, 2, ZoneType.COMMERCIAL, level=2)
        dense_map.get(1, 2).development = 1.0
        dense_map.get(2, 2).development = 1.0
        dense_map.get(1, 2).land_value = 1.0
        dense_map.get(2, 2).land_value = 1.0

        standard_sim._apply_capacity(standard_map.get(1, 2))
        standard_sim._apply_capacity(standard_map.get(2, 2))
        dense_sim._apply_capacity(dense_map.get(1, 2))
        dense_sim._apply_capacity(dense_map.get(2, 2))

        self.assertGreater(dense_map.get(1, 2).residents, standard_map.get(1, 2).residents)
        self.assertGreater(dense_map.get(2, 2).jobs, standard_map.get(2, 2).jobs)

    def test_unpowered_zones_are_reported(self) -> None:
        city_map = CityMap(4, 4)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        city_map.place_building(0, 0, BuildingType.POWER_PLANT)
        city_map.place_zone(3, 3, ZoneType.RESIDENTIAL)

        simulation.simulate_month()

        self.assertEqual(stats.unpowered_zones, 1)
        self.assertFalse(city_map.get(3, 3).powered)
        self.assertIn("not connected to power", stats.messages[-1])

    def test_power_satisfaction_reports_capacity_shortage(self) -> None:
        city_map = CityMap(3, 3)
        stats = CityStats(population=1000, jobs=0)
        simulation = Simulation(city_map, stats)
        city_map.place_building(0, 0, BuildingType.POWER_PLANT)

        simulation._update_system_totals()

        self.assertEqual(stats.power_capacity, 220)
        self.assertEqual(stats.power_usage, 800)
        self.assertEqual(stats.power_satisfaction, 27)

    def test_unwatered_zones_are_reported(self) -> None:
        city_map = CityMap(4, 4)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        city_map.place_building(0, 0, BuildingType.POWER_PLANT)
        city_map.place_power_line(1, 0)
        city_map.place_building(3, 0, BuildingType.WATER_TOWER)
        city_map.place_zone(1, 1, ZoneType.RESIDENTIAL)

        simulation.simulate_month()

        self.assertEqual(stats.unpowered_zones, 0)
        self.assertEqual(stats.unwatered_zones, 1)
        self.assertTrue(city_map.get(1, 1).powered)
        self.assertFalse(city_map.get(1, 1).watered)
        self.assertIn("not connected to water", stats.messages[-1])

    def test_water_satisfaction_reports_capacity_shortage(self) -> None:
        city_map = CityMap(3, 3)
        stats = CityStats(population=1000, jobs=0)
        simulation = Simulation(city_map, stats)
        city_map.place_building(0, 0, BuildingType.WATER_TOWER)

        simulation._update_system_totals()

        self.assertEqual(stats.water_capacity, 180)
        self.assertEqual(stats.water_usage, 700)
        self.assertEqual(stats.water_satisfaction, 25)

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

    def test_fire_station_reports_covered_and_uncovered_zones(self) -> None:
        city_map = CityMap(12, 12)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        self.add_basic_power_and_water(city_map)
        city_map.place_building(4, 4, BuildingType.FIRE)
        city_map.place_zone(1, 2, ZoneType.RESIDENTIAL)
        city_map.place_zone(11, 11, ZoneType.RESIDENTIAL)

        simulation.simulate_month()

        self.assertTrue(city_map.get(1, 2).fire_coverage)
        self.assertFalse(city_map.get(11, 11).fire_coverage)
        self.assertEqual(stats.fire_coverage_percent, 50)
        self.assertEqual(stats.fire_uncovered_zones, 1)

    def test_fire_station_reduces_tile_fire_risk(self) -> None:
        protected_map = CityMap(8, 8)
        exposed_map = CityMap(8, 8)
        protected_stats = CityStats()
        exposed_stats = CityStats()
        protected_sim = Simulation(protected_map, protected_stats)
        exposed_sim = Simulation(exposed_map, exposed_stats)

        for city_map in (protected_map, exposed_map):
            self.add_basic_power_and_water(city_map)
            city_map.place_zone(1, 2, ZoneType.INDUSTRIAL)
            city_map.get(1, 2).development = 0.8
        protected_map.place_building(4, 4, BuildingType.FIRE)

        protected_sim.simulate_month()
        exposed_sim.simulate_month()

        self.assertLess(
            protected_map.get(1, 2).fire_risk,
            exposed_map.get(1, 2).fire_risk,
        )

    def test_uncovered_fire_zones_add_advisor_message(self) -> None:
        city_map = CityMap(6, 6)
        stats = CityStats(messages=[])
        simulation = Simulation(city_map, stats)
        self.add_basic_power_and_water(city_map)
        city_map.place_zone(1, 2, ZoneType.RESIDENTIAL)

        simulation.simulate_month()

        self.assertEqual(stats.fire_uncovered_zones, 1)
        self.assertIn("outside fire station coverage", stats.messages[-1])

    def test_advisor_reports_multiple_active_issues(self) -> None:
        city_map = CityMap(3, 3)
        stats = CityStats(messages=[])
        simulation = Simulation(city_map, stats)
        stats.power_capacity = 100
        stats.water_capacity = 100
        stats.unpowered_zones = 2
        stats.unwatered_zones = 3
        stats.fire_uncovered_zones = 4

        simulation._add_monthly_message(revenue=0, expenses=100)

        self.assertIn("Some zones are not connected to power.", stats.messages)
        self.assertIn("Some zones are not connected to water.", stats.messages)
        self.assertIn("Some zones are outside fire station coverage.", stats.messages)
        self.assertEqual(stats.messages[-1], "Some zones are not connected to power.")

    def test_parks_do_not_report_fire_or_crime_risk(self) -> None:
        city_map = CityMap(3, 3)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        city_map.place_zone(1, 1, ZoneType.PARK)

        self.assertEqual(simulation._fire_risk_for(1, 1), 0)
        self.assertEqual(simulation._crime_risk_for(1, 1), 0)

    def test_police_station_reports_covered_and_uncovered_zones(self) -> None:
        city_map = CityMap(12, 12)
        stats = CityStats()
        simulation = Simulation(city_map, stats)
        self.add_basic_power_and_water(city_map)
        city_map.place_building(4, 4, BuildingType.POLICE)
        city_map.place_zone(1, 2, ZoneType.RESIDENTIAL)
        city_map.place_zone(11, 11, ZoneType.RESIDENTIAL)

        simulation.simulate_month()

        self.assertTrue(city_map.get(1, 2).police_coverage)
        self.assertFalse(city_map.get(11, 11).police_coverage)
        self.assertEqual(stats.police_coverage_percent, 50)
        self.assertEqual(stats.police_uncovered_zones, 1)

    def test_police_station_reduces_tile_crime_risk(self) -> None:
        protected_map = CityMap(8, 8)
        exposed_map = CityMap(8, 8)
        protected_stats = CityStats()
        exposed_stats = CityStats()
        protected_sim = Simulation(protected_map, protected_stats)
        exposed_sim = Simulation(exposed_map, exposed_stats)

        for city_map in (protected_map, exposed_map):
            self.add_basic_power_and_water(city_map)
            city_map.place_zone(1, 2, ZoneType.COMMERCIAL)
            city_map.get(1, 2).development = 0.8
        protected_map.place_building(4, 4, BuildingType.POLICE)

        protected_sim.simulate_month()
        exposed_sim.simulate_month()

        self.assertLess(
            protected_map.get(1, 2).crime_risk,
            exposed_map.get(1, 2).crime_risk,
        )

    def test_uncovered_police_zones_add_advisor_message(self) -> None:
        city_map = CityMap(6, 6)
        stats = CityStats(messages=[])
        simulation = Simulation(city_map, stats)
        self.add_basic_power_and_water(city_map)
        city_map.place_building(4, 4, BuildingType.FIRE)
        city_map.place_zone(1, 2, ZoneType.RESIDENTIAL)

        simulation.simulate_month()

        self.assertEqual(stats.police_uncovered_zones, 1)
        self.assertIn("outside police station coverage", stats.messages[-1])

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
