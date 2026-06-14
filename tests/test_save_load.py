import tempfile
import unittest
from pathlib import Path

from citybuilder.city_map import CityMap
from citybuilder.models import BuildingType, CityStats, ZoneType
from citybuilder.save_load import from_save_data, load_game, save_game, to_save_data


class SaveLoadTests(unittest.TestCase):
    def test_save_data_round_trips_map_and_stats(self) -> None:
        city_map = CityMap(4, 4)
        city_map.place_zone(1, 1, ZoneType.RESIDENTIAL)
        city_map.get(1, 1).development = 0.5
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
            messages=["Saved city."],
        )

        data = to_save_data(city_map, stats)
        loaded_map, loaded_stats = from_save_data(data)

        self.assertEqual(loaded_map.width, 4)
        self.assertEqual(loaded_map.height, 4)
        self.assertEqual(loaded_map.get(1, 1).zone, ZoneType.RESIDENTIAL)
        self.assertEqual(loaded_map.get(1, 1).development, 0.5)
        self.assertTrue(loaded_map.get(1, 2).has_road)
        self.assertTrue(loaded_map.get(1, 2).has_power_line)
        self.assertTrue(loaded_map.get(1, 2).has_water_pipe)
        self.assertEqual(loaded_map.get(3, 3).building, BuildingType.SCHOOL)
        self.assertEqual(loaded_stats.money, 12345)
        self.assertEqual(loaded_stats.population, 42)
        self.assertEqual(loaded_stats.tax_rate, 7)
        self.assertEqual(loaded_stats.demand_residential, 80)
        self.assertEqual(loaded_stats.power_capacity, 220)
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
        self.assertEqual(city_map.get(0, 0).building, BuildingType.NONE)
        self.assertFalse(city_map.get(0, 0).has_power_line)
        self.assertEqual(stats.money, 500)
        self.assertEqual(stats.demand_residential, 50)


if __name__ == "__main__":
    unittest.main()
