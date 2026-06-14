import sys
import types
import unittest

sys.modules.setdefault("pygame", types.SimpleNamespace())

from citybuilder.asset_loader import ImageAssetStore
from citybuilder.models import BuildingType, TerrainType, ZoneType
from citybuilder.sprites import (
    civic_asset_name,
    connection_mask,
    pedestrian_asset_name,
    road_asset_name,
    terrain_asset_names,
    utility_asset_name,
    zone_asset_name,
    zone_asset_names,
    zone_building_asset_name,
    zone_building_asset_names,
)


class SpriteAssetNameTests(unittest.TestCase):
    def test_connection_mask_uses_cardinal_order(self) -> None:
        self.assertEqual(
            connection_mask({"north": True, "east": False, "south": True, "west": False}),
            "1010",
        )

    def test_asset_names_match_documented_paths(self) -> None:
        self.assertEqual(terrain_asset_names(TerrainType.GRASS, 5), ("terrain/grass_1", "terrain/grass"))
        self.assertEqual(zone_asset_name(ZoneType.COMMERCIAL), "zones/commercial")
        self.assertEqual(zone_asset_name(ZoneType.RESIDENTIAL, 2), "zones/residential_tier2")
        self.assertEqual(zone_asset_names(ZoneType.COMMERCIAL, 2), ("zones/commercial_tier2", "zones/commercial"))
        self.assertEqual(zone_building_asset_name(ZoneType.INDUSTRIAL, 4, 6), "buildings/industrial_4_2")
        self.assertEqual(zone_building_asset_name(ZoneType.RESIDENTIAL, 3, 5, 2), "buildings/residential_tier2_3_1")
        self.assertEqual(
            zone_building_asset_names(ZoneType.COMMERCIAL, 2, 4, 2),
            ("buildings/commercial_tier2_2_0", "buildings/commercial_2_0"),
        )
        self.assertEqual(civic_asset_name(BuildingType.TRAIN_STATION), "civic/train_station")
        self.assertEqual(civic_asset_name(BuildingType.LARGE_POWER_PLANT), "civic/large_power_plant")
        self.assertEqual(road_asset_name({"north": False, "east": True, "south": False, "west": True}), "roads/road_0101")
        self.assertEqual(utility_asset_name("power", {"north": True, "east": True, "south": False, "west": False}), "utilities/power_1100")
        self.assertEqual(pedestrian_asset_name(5), "pedestrians/pedestrian_2")

    def test_asset_store_rejects_absolute_and_parent_paths(self) -> None:
        store = ImageAssetStore("assets")

        self.assertIsNone(store.path_for("../outside"))
        self.assertIsNone(store.path_for("C:/outside"))
        self.assertEqual(store.path_for("terrain/grass_0").as_posix(), "assets/terrain/grass_0.png")


if __name__ == "__main__":
    unittest.main()
