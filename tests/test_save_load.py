import tempfile
import unittest
from pathlib import Path

from citybuilder.city_map import CityMap
from citybuilder.models import BuildingType, CityStats, TerrainType, ZoneType
from citybuilder.save_load import from_save_data, load_game, save_game, to_save_data


class SaveLoadTests(unittest.TestCase):
    def test_save_data_round_trips_map_and_stats(self) -> None:
        city_map = CityMap(4, 4)
        city_map.get(0, 0).terrain = TerrainType.HILL
        city_map.place_zone(1, 1, ZoneType.RESIDENTIAL, level=2)
        city_map.get(1, 1).development = 0.5
        city_map.get(1, 1).fire_risk = 44
        city_map.get(1, 1).crime_risk = 38
        city_map.place_road(1, 2)
        city_map.place_power_line(1, 2)
        city_map.place_water_pipe(1, 2)
        city_map.place_building(3, 3, BuildingType.SCHOOL)
        stats = CityStats(
            money=12345,
            population=42,
            jobs=12,
            tax_rate=7,
            year=2,
            month=8,
            demand_residential=80,
            power_capacity=220,
            power_satisfaction=91,
            unpowered_zones=2,
            water_capacity=180,
            water_satisfaction=88,
            unwatered_zones=3,
            fire_coverage_percent=75,
            fire_uncovered_zones=1,
            average_fire_risk=34,
            police_coverage_percent=60,
            police_uncovered_zones=2,
            average_crime_risk=41,
            messages=["Saved city."],
        )

        data = to_save_data(city_map, stats)
        loaded_map, loaded_stats = from_save_data(data)

        self.assertEqual(loaded_map.width, 4)
        self.assertEqual(loaded_map.height, 4)
        self.assertEqual(loaded_map.get(0, 0).terrain, TerrainType.HILL)
        self.assertEqual(loaded_map.get(1, 1).zone, ZoneType.RESIDENTIAL)
        self.assertEqual(loaded_map.get(1, 1).zone_level, 2)
        self.assertEqual(loaded_map.get(1, 1).development, 0.5)
        self.assertEqual(loaded_map.get(1, 1).fire_risk, 44)
        self.assertEqual(loaded_map.get(1, 1).crime_risk, 38)
        self.assertTrue(loaded_map.get(1, 2).has_road)
        self.assertTrue(loaded_map.get(1, 2).has_power_line)
        self.assertTrue(loaded_map.get(1, 2).has_water_pipe)
        self.assertEqual(loaded_map.get(3, 3).building, BuildingType.SCHOOL)
        self.assertEqual(loaded_stats.money, 12345)
        self.assertEqual(loaded_stats.population, 42)
        self.assertEqual(loaded_stats.tax_rate, 7)
        self.assertEqual(loaded_stats.demand_residential, 80)
        self.assertEqual(loaded_stats.power_capacity, 220)
        self.assertEqual(loaded_stats.power_satisfaction, 91)
        self.assertEqual(loaded_stats.unpowered_zones, 2)
        self.assertEqual(loaded_stats.water_capacity, 180)
        self.assertEqual(loaded_stats.water_satisfaction, 88)
        self.assertEqual(loaded_stats.unwatered_zones, 3)
        self.assertEqual(loaded_stats.fire_coverage_percent, 75)
        self.assertEqual(loaded_stats.fire_uncovered_zones, 1)
        self.assertEqual(loaded_stats.average_fire_risk, 34)
        self.assertEqual(loaded_stats.police_coverage_percent, 60)
        self.assertEqual(loaded_stats.police_uncovered_zones, 2)
        self.assertEqual(loaded_stats.average_crime_risk, 41)
        self.assertEqual(loaded_stats.messages, ["Saved city."])

    def test_save_game_writes_json_file_and_load_game_reads_it(self) -> None:
        city_map = CityMap(2, 2)
        city_map.place_building(0, 0, BuildingType.POWER_PLANT)
        stats = CityStats(money=999)

        with tempfile.TemporaryDirectory() as temp_dir:
            save_path = Path(temp_dir) / "savegame.json"
            save_game(city_map, stats, save_path)
            loaded_map, loaded_stats = load_game(save_path)

        self.assertEqual(loaded_map.get(0, 0).building, BuildingType.POWER_PLANT)
        self.assertEqual(loaded_stats.money, 999)

    def test_old_save_data_defaults_missing_new_fields(self) -> None:
        old_data = {
            "map": {
                "width": 1,
                "height": 1,
                "tiles": [[{"zone": "commercial", "has_road": False}]],
            },
            "stats": {"money": 500, "tax_rate": 10},
        }

        city_map, stats = from_save_data(old_data)

        self.assertEqual(city_map.get(0, 0).zone, ZoneType.COMMERCIAL)
        self.assertEqual(city_map.get(0, 0).zone_level, 1)
        self.assertEqual(city_map.get(0, 0).terrain, TerrainType.GRASS)
        self.assertEqual(city_map.get(0, 0).building, BuildingType.NONE)
        self.assertFalse(city_map.get(0, 0).has_power_line)
        self.assertEqual(stats.money, 500)
        self.assertEqual(stats.demand_residential, 50)


if __name__ == "__main__":
    unittest.main()
