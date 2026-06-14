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

    def collidepoint(self, pos: tuple[int, int]) -> bool:
        x, y = pos
        return self.left <= x < self.left + self.width and self.top <= y < self.top + self.height


sys.modules["pygame"] = types.SimpleNamespace(Rect=FakeRect)
camera_module = importlib.import_module("citybuilder.camera")
Camera = camera_module.Camera


class CameraTests(unittest.TestCase):
    def test_move_clamps_to_map_edges(self) -> None:
        camera = Camera(320, 320, FakeRect(0, 0, 100, 100))

        camera.move(999, 999)
        self.assertEqual(camera.x, 220)
        self.assertEqual(camera.y, 220)

        camera.move(-999, -999)
        self.assertEqual(camera.x, 0)
        self.assertEqual(camera.y, 0)

    def test_world_and_screen_tile_coordinates_match(self) -> None:
        camera = Camera(640, 640, FakeRect(10, 20, 200, 160))
        camera.x = 64
        camera.y = 32

        screen_pos = camera.world_to_screen(3, 2, tile_size=32)

        self.assertEqual(screen_pos, (42, 52))
        self.assertEqual(camera.screen_to_tile(screen_pos, tile_size=32), (3, 2))

    def test_screen_to_tile_ignores_positions_outside_viewport(self) -> None:
        camera = Camera(320, 320, FakeRect(10, 20, 100, 100))

        self.assertIsNone(camera.screen_to_tile((9, 50), tile_size=32))
        self.assertIsNone(camera.screen_to_tile((50, 19), tile_size=32))
        self.assertEqual(camera.screen_to_tile((10, 20), tile_size=32), (0, 0))

    def test_zoom_clamps_between_minimum_and_maximum(self) -> None:
        camera = Camera(2000, 2000, FakeRect(0, 0, 300, 200))

        camera.change_zoom(99)
        self.assertEqual(camera.zoom, 1.8)

        camera.change_zoom(-99)
        self.assertEqual(camera.zoom, 0.55)

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
        camera = Camera(640, 640, FakeRect(0, 0, 96, 96))
        camera.x = 64
        camera.y = 64

        bounds = camera.visible_tile_bounds(tile_size=32, map_width=20, map_height=20)

        self.assertEqual(bounds, (1, 1, 7, 7))


if __name__ == "__main__":
    unittest.main()
