import itertools
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = PROJECT_ROOT / "assets"

ROAD_TILES = [
    "straight_SE", "straight_SW",
    "corner_N", "corner_E", "corner_S", "corner_W",
    "intersect_NE", "intersect_NW", "intersect_SE", "intersect_SW",
    "deadend_NE", "deadend_NW", "deadend_SE", "deadend_SW",
    "xing",
]

CIVIC_BUILDINGS = [
    "power_plant", "large_power_plant",
    "water_tower", "large_water_tower",
    "police", "fire", "school", "hospital",
    "train_station", "airport",
]


class AssetPackTests(unittest.TestCase):
    def test_required_assets_exist(self) -> None:
        expected: set[str] = set()

        # Terrain
        expected.add("terrain/grass.png")
        expected.add("terrain/water.png")

        # Roads (named tiles used by _road_asset_name())
        for name in ROAD_TILES:
            expected.add(f"roads/{name}.png")

        # Civic buildings
        for name in CIVIC_BUILDINGS:
            expected.add(f"civic/{name}.png")

        # Pedestrians
        for i in range(3):
            expected.add(f"pedestrians/pedestrian_{i}.png")

        # Zone buildings: 4 stages × 4 variants × 5 types
        zone_prefixes = [
            "residential", "residential_tier2",
            "commercial", "commercial_tier2",
            "industrial",
        ]
        for prefix in zone_prefixes:
            for stage, variant in itertools.product(range(1, 5), range(4)):
                expected.add(f"buildings/{prefix}_{stage}_{variant}.png")

        missing = [name for name in sorted(expected) if not (ASSETS_ROOT / name).is_file()]
        self.assertEqual(missing, [], f"{len(missing)} required asset(s) missing")

    def test_all_pngs_have_valid_signature(self) -> None:
        for path in ASSETS_ROOT.rglob("*.png"):
            with self.subTest(path=path.relative_to(ASSETS_ROOT)):
                self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
