import unittest

from citybuilder.city_map import CityMap
from citybuilder.models import TerrainType
from citybuilder.terrain import generate_terrain, starter_area_tiles, terrain_counts


class TerrainTests(unittest.TestCase):
    def terrain_grid(self, city_map: CityMap) -> list[list[TerrainType]]:
        return [
            [city_map.get(x, y).terrain for y in range(city_map.height)]
            for x in range(city_map.width)
        ]

    def test_generate_terrain_is_repeatable_with_seed(self) -> None:
        first_map = CityMap(24, 18)
        second_map = CityMap(24, 18)

        generate_terrain(first_map, seed=123)
        generate_terrain(second_map, seed=123)

        self.assertEqual(self.terrain_grid(first_map), self.terrain_grid(second_map))

    def test_generate_terrain_adds_basic_land_types(self) -> None:
        city_map = CityMap(32, 24)

        generate_terrain(city_map, seed=7)
        counts = terrain_counts(city_map)

        self.assertGreater(counts[TerrainType.GRASS], 0)
        self.assertGreater(counts[TerrainType.WATER], 0)
        self.assertGreater(counts[TerrainType.FOREST], 0)
        self.assertGreater(counts[TerrainType.HILL], 0)

    def test_generate_terrain_keeps_starter_area_clear(self) -> None:
        for seed in range(10):
            city_map = CityMap(32, 24)

            generate_terrain(city_map, seed=seed)

            for x, y in starter_area_tiles(city_map):
                self.assertEqual(city_map.get(x, y).terrain, TerrainType.GRASS)


if __name__ == "__main__":
    unittest.main()
