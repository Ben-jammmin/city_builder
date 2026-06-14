from __future__ import annotations

import pygame

from .city_map import CityMap
from .models import Tool, ViewMode
from .settings import COLORS, SIDEBAR_WIDTH, WINDOW_HEIGHT, WINDOW_WIDTH
from .ui_panels import PANEL_GAP, SidebarPanelRenderer, fit_label

SCROLL_STEP = 38
SCROLLBAR_WIDTH = 4


class Sidebar:
    def __init__(self) -> None:
        self.rect = pygame.Rect(WINDOW_WIDTH - SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT)
        self.content_rect = pygame.Rect(self.rect.left, self.rect.top, self.rect.width, self.rect.height)
        self.content_height = 0
        self.scroll_offset = 0

        self.menu_buttons: list[tuple[pygame.Rect, str]] = []
        self.tool_buttons: list[tuple[pygame.Rect, Tool]] = []
        self.tax_down_rect = pygame.Rect(0, 0, 0, 0)
        self.tax_up_rect = pygame.Rect(0, 0, 0, 0)
        self.pause_rect = pygame.Rect(0, 0, 0, 0)
        self.fullscreen_rect = pygame.Rect(0, 0, 0, 0)
        self.save_rect = pygame.Rect(0, 0, 0, 0)
        self.load_rect = pygame.Rect(0, 0, 0, 0)

        self.font_large = pygame.font.SysFont("Segoe UI", 23, bold=True)
        self.font = pygame.font.SysFont("Segoe UI", 17)
        self.font_small = pygame.font.SysFont("Segoe UI", 14)
        self.font_mono = pygame.font.SysFont("Consolas", 15)
        self.panels = SidebarPanelRenderer(self)

    def set_screen_size(self, width: int, height: int) -> None:
        self.rect = pygame.Rect(width - SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, height)
        self._clamp_scroll()

    def contains(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)

    def handle_scroll(self, amount: int) -> bool:
        if self._max_scroll() <= 0:
            return True
        self.scroll_offset -= amount * SCROLL_STEP
        self._clamp_scroll()
        return True

    def draw(
        self,
        surface: pygame.Surface,
        stats,
        city_map: CityMap,
        active_tool: Tool,
        active_menu: str,
        view_mode: ViewMode,
        fullscreen: bool,
        hover_tile,
    ) -> None:
        pygame.draw.rect(surface, COLORS["sidebar"], self.rect)
        self.menu_buttons.clear()
        self.tool_buttons.clear()

        x = self.rect.left + 14
        y = 14
        width = SIDEBAR_WIDTH - 28

        header_bottom = self.panels.draw_header(surface, x, y, view_mode)
        self.content_rect = pygame.Rect(
            self.rect.left,
            header_bottom + PANEL_GAP,
            self.rect.width,
            max(0, self.rect.bottom - header_bottom - PANEL_GAP),
        )
        self._clamp_scroll()

        old_clip = surface.get_clip()
        surface.set_clip(self.content_rect)
        content_start = self.content_rect.top - self.scroll_offset
        content_bottom = self._draw_scrollable_content(
            surface,
            stats,
            city_map,
            active_tool,
            active_menu,
            fullscreen,
            hover_tile,
            x,
            content_start,
            width,
        )
        self.content_height = content_bottom - content_start
        self._clamp_scroll()
        surface.set_clip(old_clip)
        self._draw_scrollbar(surface)

    def handle_click(self, pos: tuple[int, int]):
        if not self.rect.collidepoint(pos):
            return None
        if not self.content_rect.collidepoint(pos):
            return ("sidebar", None)
        for rect, menu_name in self.menu_buttons:
            if rect.collidepoint(pos):
                return ("menu", menu_name)
        for rect, tool in self.tool_buttons:
            if rect.collidepoint(pos):
                return ("tool", tool)
        if self.tax_down_rect.collidepoint(pos):
            return ("tax", -1)
        if self.tax_up_rect.collidepoint(pos):
            return ("tax", 1)
        if self.pause_rect.collidepoint(pos):
            return ("pause", None)
        if self.fullscreen_rect.collidepoint(pos):
            return ("fullscreen", None)
        if self.save_rect.collidepoint(pos):
            return ("save", None)
        if self.load_rect.collidepoint(pos):
            return ("load", None)
        return ("sidebar", None)

    def _draw_scrollable_content(
        self,
        surface: pygame.Surface,
        stats,
        city_map: CityMap,
        active_tool: Tool,
        active_menu: str,
        fullscreen: bool,
        hover_tile,
        x: int,
        y: int,
        width: int,
    ) -> int:
        y = self.panels.draw_city_stats(surface, stats, x, y, width)
        y = self.panels.draw_menu_tabs(surface, x, y + PANEL_GAP, width, active_menu)
        y = self.panels.draw_controls(surface, stats, x, y + PANEL_GAP, width, fullscreen)
        y = self.panels.draw_demand_panel(surface, stats, x, y + PANEL_GAP, width)
        y = self.panels.draw_system_panel(surface, stats, x, y + PANEL_GAP, width)
        y = self.panels.draw_tool_buttons(surface, x, y + PANEL_GAP, width, active_tool, active_menu)
        y = self.panels.draw_hover_panel(surface, city_map, hover_tile, x, y + PANEL_GAP, width)
        return self.panels.draw_messages(surface, stats, x, y + PANEL_GAP, width)

    def _draw_scrollbar(self, surface: pygame.Surface) -> None:
        max_scroll = self._max_scroll()
        if max_scroll <= 0 or self.content_rect.height <= 0:
            return
        track = pygame.Rect(
            self.rect.right - SCROLLBAR_WIDTH - 4,
            self.content_rect.top + 4,
            SCROLLBAR_WIDTH,
            self.content_rect.height - 8,
        )
        thumb_h = max(24, int(track.height * self.content_rect.height / self.content_height))
        thumb_y = track.y + int((track.height - thumb_h) * (self.scroll_offset / max_scroll))
        thumb = pygame.Rect(track.x, thumb_y, track.width, thumb_h)
        pygame.draw.rect(surface, (54, 61, 68), track, border_radius=2)
        pygame.draw.rect(surface, COLORS["muted_text"], thumb, border_radius=2)

    def _max_scroll(self) -> int:
        return max(0, self.content_height - self.content_rect.height)

    def _clamp_scroll(self) -> None:
        self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))

    def _fit_label(self, label: str, font: pygame.font.Font, max_width: int) -> str:
        return fit_label(label, font, max_width)
