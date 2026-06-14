import unittest

from citybuilder.city_map import CityMap
from citybuilder.models import BuildingType, ZoneType


class CityMapTests(unittest.TestCase):
    def test_new_map_starts_empty(self) -> None:
        city_map = CityMap(4, 3)

        self.assertEqual(city_map.width, 4)
        self.assertEqual(city_map.height, 3)
        self.assertEqual(city_map.road_count(), 0)
        self.assertEqual(city_map.zoned_count(), 0)
        self.assertTrue(city_map.get(0, 0).is_empty)

    def test_place_zone_changes_empty_tile(self) -> None:
        city_map = CityMap(3, 3)

        placed = city_map.place_zone(1, 1, ZoneType.RESIDENTIAL)

        self.assertTrue(placed)
        self.assertEqual(city_map.get(1, 1).zone, ZoneType.RESIDENTIAL)
        self.assertEqual(city_map.zoned_count(), 1)

    def test_place_zone_rejects_out_of_bounds_road_and_same_zone(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_road(0, 0)
        city_map.place_power_line(2, 0)
        city_map.place_zone(1, 1, ZoneType.COMMERCIAL)

        self.assertFalse(city_map.place_zone(-1, 0, ZoneType.RESIDENTIAL))
        self.assertFalse(city_map.place_zone(0, 0, ZoneType.RESIDENTIAL))
        self.assertFalse(city_map.place_zone(2, 0, ZoneType.RESIDENTIAL))
        self.assertFalse(city_map.place_zone(1, 1, ZoneType.COMMERCIAL))

    def test_place_road_clears_existing_zone_and_population(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_zone(1, 1, ZoneType.RESIDENTIAL)
        tile = city_map.get(1, 1)
        tile.development = 0.75
        tile.residents = 8
        tile.jobs = 2

        placed = city_map.place_road(1, 1)

        self.assertTrue(placed)
        self.assertTrue(tile.has_road)
        self.assertEqual(tile.zone, ZoneType.EMPTY)
        self.assertEqual(tile.development, 0.0)
        self.assertEqual(tile.residents, 0)
        self.assertEqual(tile.jobs, 0)
        self.assertEqual(city_map.road_count(), 1)
        self.assertEqual(city_map.zoned_count(), 0)

    def test_place_road_rejects_duplicate_and_out_of_bounds(self) -> None:
        city_map = CityMap(2, 2)

        self.assertTrue(city_map.place_road(0, 0))
        self.assertFalse(city_map.place_road(0, 0))
        self.assertFalse(city_map.place_road(5, 5))

    def test_power_lines_and_water_pipes_can_share_road_tiles(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_road(1, 1)

        self.assertTrue(city_map.place_power_line(1, 1))
        self.assertTrue(city_map.place_water_pipe(1, 1))
        self.assertEqual(city_map.power_line_count(), 1)
        self.assertEqual(city_map.water_pipe_count(), 1)

    def test_utility_lines_reject_zones_and_buildings(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_zone(0, 0, ZoneType.RESIDENTIAL)
        city_map.place_building(1, 1, BuildingType.POLICE)

        self.assertFalse(city_map.place_power_line(0, 0))
        self.assertFalse(city_map.place_water_pipe(1, 1))

    def test_place_building_requires_empty_tile(self) -> None:
        city_map = CityMap(3, 3)

        self.assertTrue(city_map.place_building(1, 1, BuildingType.FIRE))
        self.assertFalse(city_map.place_building(1, 1, BuildingType.SCHOOL))
        self.assertFalse(city_map.place_building(2, 2, BuildingType.NONE))
        self.assertEqual(city_map.building_count(), 1)
        self.assertEqual(city_map.building_count(BuildingType.FIRE), 1)

    def test_bulldoze_clears_road_or_zone(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_road(0, 0)
        city_map.place_zone(1, 1, ZoneType.INDUSTRIAL)
        city_map.place_power_line(2, 2)

        self.assertTrue(city_map.bulldoze(0, 0))
        self.assertTrue(city_map.bulldoze(1, 1))
        self.assertTrue(city_map.bulldoze(2, 2))
        self.assertTrue(city_map.get(0, 0).is_empty)
        self.assertTrue(city_map.get(1, 1).is_empty)
        self.assertTrue(city_map.get(2, 2).is_empty)
        self.assertEqual(city_map.road_count(), 0)
        self.assertEqual(city_map.zoned_count(), 0)
        self.assertEqual(city_map.power_line_count(), 0)

    def test_bulldoze_rejects_empty_or_out_of_bounds_tile(self) -> None:
        city_map = CityMap(2, 2)

        self.assertFalse(city_map.bulldoze(0, 0))
        self.assertFalse(city_map.bulldoze(9, 9))

    def test_neighbors_and_adjacent_roads_use_cardinal_directions(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_road(0, 0)

        self.assertEqual(len(list(city_map.neighbors4(0, 0))), 2)
        self.assertEqual(len(list(city_map.neighbors8(0, 0))), 3)
        self.assertTrue(city_map.has_adjacent_road(1, 0))
        self.assertFalse(city_map.has_adjacent_road(1, 1))


if __name__ == "__main__":
    unittest.main()
