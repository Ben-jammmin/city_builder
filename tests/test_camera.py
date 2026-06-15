import importlib
import sys
import types
import unittest


class FakeRect:
    def __init__(self, left: int, top: int, width: int, height: int) -> None:
        self.left = left
        self.top = top
        self.width = width
        self.height = height

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    def collidepoint(self, pos: tuple[int, int]) -> bool:
        x, y = pos
        return self.left <= x < self.right and self.top <= y < self.bottom


sys.modules["pygame"] = types.SimpleNamespace(Rect=FakeRect)
camera_module = importlib.import_module("citybuilder.camera")
Camera = camera_module.Camera


class CameraTests(unittest.TestCase):
    def test_move_clamps_to_map_edges(self) -> None:
        camera = Camera(10, 10, FakeRect(0, 0, 100, 100))

        camera.move(999, 999)
        self.assertEqual(camera.x, 604)
        self.assertEqual(camera.y, 348)

        camera.move(-999, -999)
        self.assertEqual(camera.x, 0)
        self.assertEqual(camera.y, 0)

    def test_world_and_screen_tile_coordinates_round_trip_at_tile_center(self) -> None:
        camera = Camera(20, 20, FakeRect(10, 20, 300, 200))

        screen_pos = camera.world_to_screen(10, 10, tile_size=32)
        tile_center = (screen_pos[0], screen_pos[1] + camera.tile_h // 2)

        self.assertEqual(screen_pos, (160, 91))
        self.assertEqual(camera.screen_to_tile(tile_center, tile_size=32), (10, 10))

    def test_screen_to_tile_ignores_positions_outside_viewport(self) -> None:
        camera = Camera(10, 10, FakeRect(10, 20, 100, 100))

        self.assertIsNone(camera.screen_to_tile((9, 50), tile_size=32))
        self.assertIsNone(camera.screen_to_tile((50, 19), tile_size=32))

    def test_zoom_clamps_between_minimum_and_maximum(self) -> None:
        camera = Camera(2000, 2000, FakeRect(0, 0, 300, 200))

        camera.change_zoom(99)
        self.assertEqual(camera.zoom, 2.8)

        camera.change_zoom(-99)
        self.assertEqual(camera.zoom, 0.3)

    def test_zoom_keeps_mouse_world_position_anchored(self) -> None:
        camera = Camera(2000, 2000, FakeRect(0, 0, 300, 200))
        camera.x = 100
        camera.y = 50
        mouse_pos = (100, 50)
        before = camera.screen_to_world_pixels(mouse_pos)

        camera.change_zoom(0.5, mouse_pos)

        after = camera.screen_to_world_pixels(mouse_pos)
        self.assertAlmostEqual(before[0], after[0])
        self.assertAlmostEqual(before[1], after[1])

    def test_visible_tile_bounds_include_only_needed_area(self) -> None:
        camera = Camera(20, 20, FakeRect(0, 0, 96, 96))
        camera.x = 64
        camera.y = 64

        bounds = camera.visible_tile_bounds(tile_size=32, map_width=20, map_height=20)

        self.assertEqual(bounds, (0, 4, 3, 19))

    def test_rotation_round_trips_visible_tiles(self) -> None:
        for rotation in range(4):
            with self.subTest(rotation=rotation):
                camera = Camera(10, 6, FakeRect(0, 0, 300, 200))
                for _ in range(rotation):
                    camera.rotate_cw()

                screen_pos = camera.world_to_screen(4, 2)
                tile_center = (screen_pos[0], screen_pos[1] + camera.tile_h // 2)

                self.assertEqual(camera.rotation, rotation)
                self.assertEqual(camera.screen_to_tile(tile_center), (4, 2))


if __name__ == "__main__":
    unittest.main()
