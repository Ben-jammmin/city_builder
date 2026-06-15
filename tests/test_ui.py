import sys
import types
import unittest

sys.modules.setdefault("pygame", types.SimpleNamespace())

from citybuilder.ui import Sidebar
from citybuilder.settings import COMMAND_BAR_HEIGHT, MINIMIZED_COMMAND_BAR_HEIGHT


class FakeFont:
    def size(self, text: str) -> tuple[int, int]:
        return len(text) * 6, 12


class SidebarLabelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.sidebar = Sidebar.__new__(Sidebar)
        self.font = FakeFont()
        self.sidebar.scroll_offset = 0
        self.sidebar.content_height = 500
        self.sidebar.content_rect = types.SimpleNamespace(height=300)

    def test_fit_label_keeps_text_that_fits(self) -> None:
        self.assertEqual(self.sidebar._fit_label("Save", self.font, 24), "Save")

    def test_fit_label_truncates_long_text(self) -> None:
        self.assertEqual(self.sidebar._fit_label("Transport", self.font, 36), "Tra...")

    def test_fit_label_returns_empty_when_suffix_cannot_fit(self) -> None:
        self.assertEqual(self.sidebar._fit_label("Transport", self.font, 8), "")

    def test_handle_scroll_moves_down_for_negative_wheel_amount(self) -> None:
        handled = self.sidebar.handle_scroll(-1)

        self.assertTrue(handled)
        self.assertEqual(self.sidebar.scroll_offset, 38)

    def test_handle_scroll_clamps_to_content_range(self) -> None:
        self.sidebar.handle_scroll(-99)

        self.assertEqual(self.sidebar.scroll_offset, 200)

        self.sidebar.handle_scroll(99)

        self.assertEqual(self.sidebar.scroll_offset, 0)

    def test_current_height_tracks_minimized_state(self) -> None:
        self.sidebar.minimized = False
        self.assertEqual(self.sidebar.current_height(), COMMAND_BAR_HEIGHT)

        self.sidebar.minimized = True
        self.assertEqual(self.sidebar.current_height(), MINIMIZED_COMMAND_BAR_HEIGHT)


if __name__ == "__main__":
    unittest.main()
