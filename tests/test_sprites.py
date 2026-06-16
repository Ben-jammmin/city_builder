import sys
import types
import unittest
from unittest.mock import patch

sys.modules.setdefault("pygame", types.SimpleNamespace())

from citybuilder.asset_loader import ImageAssetStore
from citybuilder.models import BuildingType, TerrainType, ZoneType
from citybuilder.sprites import SpriteAtlas, _diam_pts, tile_variant


class SpriteMathTests(unittest.TestCase):
    def test_tile_variant_is_stable_and_in_expected_range(self) -> None:
        self.assertEqual(tile_variant(0, 0), 0)
        self.assertEqual(tile_variant(1, 0), 1)
        self.assertEqual(tile_variant(0, 1), 1)
        self.assertIn(tile_variant(17, 23), range(4))

    def test_diamond_points_use_two_to_one_iso_shape(self) -> None:
        self.assertEqual(_diam_pts(64, 32), [(32, 0), (64, 16), (32, 32), (0, 16)])

    def test_edge_key_uses_cardinal_order_with_missing_defaults(self) -> None:
        atlas = SpriteAtlas.__new__(SpriteAtlas)

        self.assertEqual(
            atlas._edge_key({"north": True, "east": False, "south": True}),
            (True, False, True, False),
        )

    def test_dense_zone_and_large_civic_buildings_are_taller(self) -> None:
        atlas = SpriteAtlas.__new__(SpriteAtlas)

        self.assertGreater(
            atlas._bh(ZoneType.COMMERCIAL, stage=3, level=2, th=32),
            atlas._bh(ZoneType.COMMERCIAL, stage=3, level=1, th=32),
        )
        self.assertGreater(
            atlas._civic_bh(BuildingType.LARGE_POWER_PLANT, th=32),
            atlas._civic_bh(BuildingType.POWER_PLANT, th=32),
        )

    def test_building_asset_names_match_generated_pack(self) -> None:
        atlas = SpriteAtlas.__new__(SpriteAtlas)

        self.assertEqual(
            atlas._building_asset_name(ZoneType.RESIDENTIAL, stage=4, level=1, variant=2),
            "buildings/residential_4_2",
        )
        self.assertEqual(
            atlas._building_asset_name(ZoneType.COMMERCIAL, stage=3, level=2, variant=1),
            "buildings/commercial_tier2_3_1",
        )
        self.assertEqual(
            atlas._building_asset_name(ZoneType.INDUSTRIAL, stage=2, level=2, variant=0),
            "buildings/industrial_2_0",
        )

    def test_asset_store_rejects_absolute_and_parent_paths(self) -> None:
        store = ImageAssetStore("assets")

        # Parent traversal
        self.assertIsNone(store.path_for("../outside"))
        self.assertIsNone(store.path_for("sub/../../outside"))

        # Unix absolute path — on Windows, Path("/…").is_absolute() is False but .root is set
        self.assertIsNone(store.path_for("/etc/passwd"))

        # Windows absolute paths (forward-slash and backslash variants)
        self.assertIsNone(store.path_for("C:/outside"))
        self.assertIsNone(store.path_for("C:\\outside"))

        # Windows drive-relative root path — no drive letter but root is set
        self.assertIsNone(store.path_for("\\outside"))

        # Valid relative paths should still resolve correctly
        self.assertEqual(store.path_for("terrain/grass_0").as_posix(), "assets/terrain/grass_0.png")

    def test_asset_store_preserves_sprite_aspect_ratio_when_scaling(self) -> None:
        class FakeSurface:
            def __init__(self, size: tuple[int, int]) -> None:
                self._size = size

            def get_size(self) -> tuple[int, int]:
                return self._size

            def copy(self):
                return FakeSurface(self._size)

        scaled: list[tuple[int, int]] = []

        def fake_scale(_surface, size: tuple[int, int]):
            scaled.append(size)
            return FakeSurface(size)

        store = ImageAssetStore("assets")
        import citybuilder.asset_loader as asset_loader

        original_transform = getattr(asset_loader.pygame, "transform", None)
        asset_loader.pygame.transform = types.SimpleNamespace(scale=fake_scale)
        try:
            with patch.object(store, "_load_raw", return_value=FakeSurface((96, 128))):
                sprite = store.get("buildings/residential_4_0", 48)
        finally:
            if original_transform is None:
                delattr(asset_loader.pygame, "transform")
            else:
                asset_loader.pygame.transform = original_transform

        self.assertEqual(sprite.get_size(), (48, 64))
        self.assertEqual(scaled, [(48, 64)])


if __name__ == "__main__":
    unittest.main()
