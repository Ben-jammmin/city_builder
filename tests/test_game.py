import sys
import types
import unittest

sys.modules.setdefault("pygame", types.SimpleNamespace())

from citybuilder.city_map import CityMap
from citybuilder.game import Game
from citybuilder.models import BuildingType, CityStats, TerrainType, Tool, ZoneType


class GamePlacementMessageTests(unittest.TestCase):
    def test_water_pipe_on_building_reports_blocked_without_crashing(self) -> None:
        game = Game.__new__(Game)
        game.map = CityMap(3, 3)
        game.stats = CityStats()
        game.map.place_building(1, 1, BuildingType.WATER_TOWER)

        game._place_water_pipe((1, 1))

        self.assertEqual(game.stats.messages[-1], "Tile occupied by zone/building.")
        self.assertFalse(game.map.get(1, 1).has_water_pipe)

    def test_zone_on_water_reports_water_message(self) -> None:
        game = Game.__new__(Game)
        game.map = CityMap(3, 3)
        game.stats = CityStats()
        game.map.get(1, 1).terrain = TerrainType.WATER

        game._place_zone((1, 1), ZoneType.RESIDENTIAL)

        self.assertEqual(game.stats.messages[-1], "Cannot build on water.")

    def test_building_on_water_reports_water_message(self) -> None:
        game = Game.__new__(Game)
        game.map = CityMap(3, 3)
        game.stats = CityStats()
        game.active_tool = Tool.FIRE
        game.map.get(1, 1).terrain = TerrainType.WATER

        game._place_building((1, 1))

        self.assertEqual(game.stats.messages[-1], "Cannot build on water.")

    def test_road_on_zone_reports_blocked_without_erasing_zone(self) -> None:
        game = Game.__new__(Game)
        game.map = CityMap(3, 3)
        game.stats = CityStats()
        game.map.place_zone(1, 1, ZoneType.RESIDENTIAL)

        game._place_road((1, 1))

        self.assertEqual(game.stats.messages[-1], "Tile occupied by zone/building.")
        self.assertEqual(game.map.get(1, 1).zone, ZoneType.RESIDENTIAL)
        self.assertFalse(game.map.get(1, 1).has_road)


if __name__ == "__main__":
    unittest.main()
