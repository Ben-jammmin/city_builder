import unittest
import sys
import types

sys.modules.setdefault("pygame", types.SimpleNamespace())

from citybuilder.models import TerrainType, Tile, Tool, ZoneType
from citybuilder.renderer import Renderer
from citybuilder.city_map import CityMap


class RendererToolBlockedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.renderer = Renderer.__new__(Renderer)

    def test_zones_and_buildings_require_clear_grass(self) -> None:
        forest_tile = Tile(terrain=TerrainType.FOREST)
        hill_tile = Tile(terrain=TerrainType.HILL)
        grass_tile = Tile(terrain=TerrainType.GRASS)

        self.assertTrue(self.renderer._tool_blocked(forest_tile, Tool.RESIDENTIAL))
        self.assertTrue(self.renderer._tool_blocked(hill_tile, Tool.SCHOOL))
        self.assertFalse(self.renderer._tool_blocked(grass_tile, Tool.COMMERCIAL))

    def test_roads_and_utility_lines_allow_non_water_terrain(self) -> None:
        forest_tile = Tile(terrain=TerrainType.FOREST)
        hill_tile = Tile(terrain=TerrainType.HILL)
        water_tile = Tile(terrain=TerrainType.WATER)

        self.assertFalse(self.renderer._tool_blocked(forest_tile, Tool.ROAD))
        self.assertFalse(self.renderer._tool_blocked(hill_tile, Tool.POWER_LINE))
        self.assertTrue(self.renderer._tool_blocked(water_tile, Tool.WATER_PIPE))

    def test_bulldoze_only_blocks_empty_grass(self) -> None:
        empty_grass = Tile(terrain=TerrainType.GRASS)
        empty_hill = Tile(terrain=TerrainType.HILL)
        zoned_grass = Tile(terrain=TerrainType.GRASS, zone=ZoneType.RESIDENTIAL)

        self.assertTrue(self.renderer._tool_blocked(empty_grass, Tool.BULLDOZE))
        self.assertFalse(self.renderer._tool_blocked(empty_hill, Tool.BULLDOZE))
        self.assertFalse(self.renderer._tool_blocked(zoned_grass, Tool.BULLDOZE))

    def test_same_terrain_neighbors_reports_cardinal_matches(self) -> None:
        city_map = CityMap(3, 3)
        city_map.get(1, 1).terrain = TerrainType.WATER
        city_map.get(1, 0).terrain = TerrainType.WATER
        city_map.get(2, 1).terrain = TerrainType.WATER

        self.assertEqual(
            self.renderer._same_terrain_neighbors(city_map, 1, 1, TerrainType.WATER),
            {"north": True, "east": True, "south": False, "west": False},
        )


if __name__ == "__main__":
    unittest.main()
