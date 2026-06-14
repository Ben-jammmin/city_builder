import itertools
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_ROOT = PROJECT_ROOT / "assets"


class GeneratedAssetPackTests(unittest.TestCase):
    def test_generated_asset_pack_contains_required_pngs(self) -> None:
        expected = {
            "preview.png",
            "terrain/grass.png",
            "terrain/water.png",
            "terrain/forest.png",
            "terrain/hill.png",
            "zones/residential.png",
            "zones/residential_tier2.png",
            "zones/commercial.png",
            "zones/commercial_tier2.png",
            "zones/industrial.png",
            "civic/power_plant.png",
            "civic/large_power_plant.png",
            "civic/water_tower.png",
            "civic/large_water_tower.png",
            "civic/police.png",
            "civic/fire.png",
            "civic/school.png",
            "civic/train_station.png",
            "civic/airport.png",
        }
        expected.update(f"terrain/grass_{index}.png" for index in range(4))
        expected.update(f"terrain/forest_{index}.png" for index in range(2))
        expected.update(f"pedestrians/pedestrian_{index}.png" for index in range(3))

        for stage, variant in itertools.product(range(1, 5), range(4)):
            expected.add(f"buildings/residential_{stage}_{variant}.png")
            expected.add(f"buildings/residential_tier2_{stage}_{variant}.png")
            expected.add(f"buildings/commercial_{stage}_{variant}.png")
            expected.add(f"buildings/commercial_tier2_{stage}_{variant}.png")
            expected.add(f"buildings/industrial_{stage}_{variant}.png")

        for bits in itertools.product("01", repeat=4):
            mask = "".join(bits)
            expected.add(f"roads/road_{mask}.png")
            expected.add(f"utilities/power_{mask}.png")
            expected.add(f"utilities/water_{mask}.png")

        missing = [name for name in sorted(expected) if not (ASSETS_ROOT / name).is_file()]

        self.assertEqual(missing, [])

    def test_generated_pngs_have_png_signature(self) -> None:
        for path in ASSETS_ROOT.rglob("*.png"):
            with self.subTest(path=path.relative_to(ASSETS_ROOT)):
                self.assertEqual(path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")


if __name__ == "__main__":
    unittest.main()
