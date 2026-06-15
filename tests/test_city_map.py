import unittest

from citybuilder.city_map import CityMap
from citybuilder.models import BuildingType, TerrainType, ZoneType


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

        placed = city_map.place_zone(1, 1, ZoneType.RESIDENTIAL, level=2)

        self.assertTrue(placed)
        self.assertEqual(city_map.get(1, 1).zone, ZoneType.RESIDENTIAL)
        self.assertEqual(city_map.get(1, 1).zone_level, 2)
        self.assertEqual(city_map.zoned_count(), 1)

    def test_place_zone_allows_upgrading_same_zone_to_new_level(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_zone(1, 1, ZoneType.RESIDENTIAL)

        self.assertTrue(city_map.place_zone(1, 1, ZoneType.RESIDENTIAL, level=2))
        self.assertEqual(city_map.get(1, 1).zone_level, 2)
        self.assertFalse(city_map.place_zone(1, 1, ZoneType.RESIDENTIAL, level=2))

    def test_zone_maintenance_excludes_parks(self) -> None:
        city_map = CityMap(4, 4)
        city_map.place_zone(0, 0, ZoneType.RESIDENTIAL, level=2)
        city_map.place_zone(1, 0, ZoneType.COMMERCIAL)
        city_map.place_zone(2, 0, ZoneType.PARK)

        self.assertEqual(city_map.zone_maintenance_units(), 3)
        self.assertEqual(city_map.park_count(), 1)

    def test_place_zone_rejects_out_of_bounds_road_and_same_zone(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_road(0, 0)
        city_map.place_power_line(2, 0)
        city_map.place_zone(1, 1, ZoneType.COMMERCIAL)

        self.assertFalse(city_map.place_zone(-1, 0, ZoneType.RESIDENTIAL))
        self.assertFalse(city_map.place_zone(0, 0, ZoneType.RESIDENTIAL))
        self.assertFalse(city_map.place_zone(2, 0, ZoneType.RESIDENTIAL))
        self.assertFalse(city_map.place_zone(1, 1, ZoneType.COMMERCIAL))

    def test_place_road_rejects_existing_zone_or_building(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_zone(1, 1, ZoneType.RESIDENTIAL)
        city_map.place_building(2, 2, BuildingType.SCHOOL)

        self.assertFalse(city_map.place_road(1, 1))
        self.assertFalse(city_map.place_road(2, 2))
        self.assertEqual(city_map.get(1, 1).zone, ZoneType.RESIDENTIAL)
        self.assertEqual(city_map.get(2, 2).building, BuildingType.SCHOOL)
        self.assertEqual(city_map.road_count(), 0)

    def test_place_road_can_share_existing_utility_tile(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_power_line(1, 1)
        city_map.place_water_pipe(1, 1)

        self.assertTrue(city_map.place_road(1, 1))
        self.assertTrue(city_map.get(1, 1).has_road)
        self.assertTrue(city_map.get(1, 1).has_power_line)
        self.assertTrue(city_map.get(1, 1).has_water_pipe)
        self.assertEqual(city_map.road_count(), 1)

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

    def test_water_terrain_blocks_construction(self) -> None:
        city_map = CityMap(4, 4)
        water_tile = city_map.get(1, 1)
        water_tile.terrain = TerrainType.WATER

        self.assertFalse(city_map.can_place_zone(1, 1, ZoneType.RESIDENTIAL))
        self.assertFalse(city_map.can_place_road(1, 1))
        self.assertFalse(city_map.can_place_power_line(1, 1))
        self.assertFalse(city_map.can_place_water_pipe(1, 1))
        self.assertFalse(city_map.can_place_building(1, 1, BuildingType.FIRE))
        self.assertFalse(city_map.place_zone(1, 1, ZoneType.RESIDENTIAL))
        self.assertFalse(city_map.place_road(1, 1))
        self.assertFalse(city_map.place_power_line(1, 1))
        self.assertFalse(city_map.place_water_pipe(1, 1))
        self.assertFalse(city_map.place_building(1, 1, BuildingType.FIRE))
        self.assertTrue(water_tile.is_empty)

    def test_can_place_helpers_accept_clear_buildable_land(self) -> None:
        city_map = CityMap(4, 4)

        self.assertTrue(city_map.can_place_zone(1, 1, ZoneType.RESIDENTIAL))
        self.assertTrue(city_map.can_place_road(1, 1))
        self.assertTrue(city_map.can_place_power_line(1, 1))
        self.assertTrue(city_map.can_place_water_pipe(1, 1))
        self.assertTrue(city_map.can_place_building(1, 1, BuildingType.SCHOOL))

    def test_building_on_forest_clears_it_to_grass(self) -> None:
        city_map = CityMap(4, 4)
        city_map.get(1, 1).terrain = TerrainType.FOREST
        city_map.get(2, 2).terrain = TerrainType.FOREST

        # Roads can be placed on forest
        self.assertTrue(city_map.place_road(1, 1))
        self.assertEqual(city_map.get(1, 1).terrain, TerrainType.GRASS)
        
        # Zones require bulldozing terrain first
        self.assertFalse(city_map.place_zone(2, 2, ZoneType.RESIDENTIAL))
        self.assertTrue(city_map.bulldoze(2, 2))  # Clear forest to grass
        self.assertTrue(city_map.place_zone(2, 2, ZoneType.RESIDENTIAL))
        self.assertEqual(city_map.get(2, 2).terrain, TerrainType.GRASS)

    def test_bulldoze_preserves_terrain(self) -> None:
        city_map = CityMap(3, 3)
        city_map.get(1, 1).terrain = TerrainType.HILL
        city_map.place_road(1, 1)

        self.assertTrue(city_map.bulldoze(1, 1))

        self.assertEqual(city_map.get(1, 1).terrain, TerrainType.HILL)
        self.assertTrue(city_map.get(1, 1).is_empty)

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

    def test_road_connections_report_cardinal_neighbor_roads(self) -> None:
        city_map = CityMap(5, 5)
        city_map.place_road(2, 2)
        city_map.place_road(2, 1)
        city_map.place_road(3, 2)
        city_map.place_road(2, 3)

        self.assertEqual(
            city_map.road_connections(2, 2),
            {"north": True, "east": True, "south": True, "west": False},
        )

    def test_road_connections_ignore_diagonal_roads_and_empty_tiles(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_road(1, 1)
        city_map.place_road(0, 0)

        self.assertEqual(
            city_map.road_connections(1, 1),
            {"north": False, "east": False, "south": False, "west": False},
        )
        self.assertEqual(
            city_map.road_connections(2, 2),
            {"north": False, "east": False, "south": False, "west": False},
        )

    def test_power_connections_link_lines_to_lines_and_power_plants(self) -> None:
        city_map = CityMap(4, 4)
        city_map.place_building(1, 0, BuildingType.POWER_PLANT)
        city_map.place_power_line(1, 1)
        city_map.place_power_line(2, 1)

        self.assertEqual(
            city_map.power_connections(1, 1),
            {"north": True, "east": True, "south": False, "west": False},
        )

    def test_large_power_plants_connect_to_power_lines(self) -> None:
        city_map = CityMap(4, 4)
        city_map.place_building(1, 0, BuildingType.LARGE_POWER_PLANT)
        city_map.place_power_line(1, 1)

        self.assertTrue(city_map.power_connections(1, 1)["north"])

    def test_power_connections_ignore_roads_zones_and_empty_tiles(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_power_line(1, 1)
        city_map.place_road(1, 0)
        city_map.place_zone(2, 1, ZoneType.RESIDENTIAL)

        self.assertEqual(
            city_map.power_connections(1, 1),
            {"north": False, "east": False, "south": False, "west": False},
        )

    def test_water_connections_link_pipes_to_pipes_and_water_towers(self) -> None:
        city_map = CityMap(4, 4)
        city_map.place_building(1, 0, BuildingType.WATER_TOWER)
        city_map.place_water_pipe(1, 1)
        city_map.place_water_pipe(2, 1)

        self.assertEqual(
            city_map.water_connections(1, 1),
            {"north": True, "east": True, "south": False, "west": False},
        )

    def test_large_water_towers_connect_to_water_pipes(self) -> None:
        city_map = CityMap(4, 4)
        city_map.place_building(1, 0, BuildingType.LARGE_WATER_TOWER)
        city_map.place_water_pipe(1, 1)

        self.assertTrue(city_map.water_connections(1, 1)["north"])

    def test_water_connections_ignore_roads_zones_and_empty_tiles(self) -> None:
        city_map = CityMap(3, 3)
        city_map.place_water_pipe(1, 1)
        city_map.place_road(1, 0)
        city_map.place_zone(2, 1, ZoneType.RESIDENTIAL)

        self.assertEqual(
            city_map.water_connections(1, 1),
            {"north": False, "east": False, "south": False, "west": False},
        )


if __name__ == "__main__":
    unittest.main()
