"""The sidebar — the bottom bar with city stats, controls, menus, and tool buttons."""
from __future__ import annotations

import pygame

from .city_map import CityMap
from .models import TOOL_LABELS, Tool, ViewMode
from .settings import (
    COLORS,
    COMMAND_BAR_HEIGHT,
    MINIMIZED_COMMAND_BAR_HEIGHT,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from .settings import SIM_SPEED_PRESETS
from .ui_panels import PANEL_GAP, SidebarPanelRenderer, fit_label

SCROLL_STEP = 38
SCROLLBAR_WIDTH = 4
BAR_PAD = 12
BAR_GAP = 8


class Sidebar:
    def __init__(self) -> None:
        self.minimized = False
        self.rect = pygame.Rect(0, WINDOW_HEIGHT - COMMAND_BAR_HEIGHT, WINDOW_WIDTH, COMMAND_BAR_HEIGHT)
        self.content_rect = pygame.Rect(self.rect.left, self.rect.top, self.rect.width, self.rect.height)
        self.content_height = 0
        self.scroll_offset = 0

        self.menu_buttons: list[tuple[pygame.Rect, str]] = []
        self.tool_buttons: list[tuple[pygame.Rect, Tool]] = []
        self.speed_rects: list[tuple[pygame.Rect, int]] = []
        self.speed_index: int = 1
        self.minimize_rect = pygame.Rect(0, 0, 0, 0)
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

    def current_height(self) -> int:
        return MINIMIZED_COMMAND_BAR_HEIGHT if self.minimized else COMMAND_BAR_HEIGHT

    def set_screen_size(self, width: int, height: int) -> None:
        bar_h = self.current_height()
        self.rect = pygame.Rect(0, height - bar_h, width, bar_h)
        self.content_rect = self.rect.copy()
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
        self._reset_click_targets()
        pygame.draw.rect(surface, COLORS["sidebar"], self.rect)
        pygame.draw.line(surface, (55, 80, 110), (0, self.rect.y), (self.rect.right, self.rect.y), 2)
        self.content_rect = self.rect.copy()

        if self.minimized:
            self._draw_minimized(surface, stats, active_tool, view_mode)
            return

        old_clip = surface.get_clip()
        surface.set_clip(self.rect)
        self._draw_expanded(
            surface,
            stats,
            city_map,
            active_tool,
            active_menu,
            view_mode,
            fullscreen,
            hover_tile,
        )
        surface.set_clip(old_clip)

    def handle_click(self, pos: tuple[int, int]):
        if not self.rect.collidepoint(pos):
            return None
        if self.minimize_rect.collidepoint(pos):
            return ("toggle_menu", None)
        if self.minimized:
            return ("sidebar", None)
        for rect, menu_name in self.menu_buttons:
            if rect.collidepoint(pos):
                return ("menu", menu_name)
        for rect, tool in self.tool_buttons:
            if rect.collidepoint(pos):
                return ("tool", tool)
        for rect, idx in self.speed_rects:
            if rect.collidepoint(pos):
                return ("speed", idx)
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

    def _draw_expanded(
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
        header_y = self.rect.y + 8
        self.panels._draw_text(surface, "City Builder", BAR_PAD, header_y, self.font_large)
        view_text = self.font_small.render(f"{view_mode.value.title()} view", True, COLORS["muted_text"])
        surface.blit(view_text, (BAR_PAD + 142, header_y + 6))
        self.minimize_rect = pygame.Rect(self.rect.right - 72, header_y, 58, 24)
        self.panels._button(surface, self.minimize_rect, "Hide")

        content_x = self.rect.x + BAR_PAD
        content_y = self.rect.y + 42
        content_w = self.rect.width - BAR_PAD * 2
        left_w = 300
        status_w = 268 if content_w >= 1060 else max(170, min(238, content_w // 4))
        info_w = 250 if content_w >= 1180 else 0
        center_w = content_w - left_w - status_w - info_w - BAR_GAP * (2 + int(info_w > 0))
        if center_w < 280:
            info_w = 0
            status_w = max(160, min(220, content_w // 4))
            center_w = max(260, content_w - left_w - status_w - BAR_GAP * 2)

        left_x = content_x
        center_x = left_x + left_w + BAR_GAP
        status_x = center_x + center_w + BAR_GAP
        info_x = status_x + status_w + BAR_GAP

        speed_labels = [label for label, _ in SIM_SPEED_PRESETS]
        city_bottom = self.panels.draw_city_stats(surface, stats, left_x, content_y, left_w)
        self.panels.draw_controls(surface, stats, left_x, city_bottom + PANEL_GAP, left_w, fullscreen, self.speed_index, speed_labels)

        tab_bottom = self.panels.draw_menu_tabs(surface, center_x, content_y, center_w, active_menu)
        self.panels.draw_tool_buttons(surface, center_x, tab_bottom + 2, center_w, active_tool, active_menu)

        demand_bottom = self.panels.draw_demand_panel(surface, stats, status_x, content_y, status_w)
        self.panels.draw_system_panel(surface, stats, status_x, demand_bottom + PANEL_GAP, status_w)

        if info_w >= 210:
            hover_bottom = self._draw_tile_compact(surface, city_map, hover_tile, info_x, content_y, info_w)
            self._draw_advisor_compact(surface, stats, info_x, hover_bottom + PANEL_GAP, info_w, self.rect.bottom - hover_bottom - PANEL_GAP - BAR_PAD)

    def _draw_minimized(self, surface: pygame.Surface, stats, active_tool: Tool, view_mode: ViewMode) -> None:
        y = self.rect.y + 9
        self.panels._draw_text(surface, "City Builder", BAR_PAD, y - 1, self.font)
        summary = (
            f"${stats.money:,}  Pop {stats.population:,}  Jobs {stats.jobs:,}  "
            f"{TOOL_LABELS[active_tool]}  {view_mode.value.title()} view"
        )
        fitted = fit_label(summary, self.font_small, max(80, self.rect.width - 220))
        self.panels._draw_text(surface, fitted, BAR_PAD + 112, y + 2, self.font_small, COLORS["muted_text"])
        self.minimize_rect = pygame.Rect(self.rect.right - 72, self.rect.y + 10, 58, 24)
        self.panels._button(surface, self.minimize_rect, "Show")

    def _draw_tile_compact(self, surface: pygame.Surface, city_map: CityMap, hover_tile, x: int, y: int, width: int) -> int:
        panel_h = 116
        panel = self.panels._panel(surface, x, y, width, panel_h)
        self.panels._draw_text(surface, "Tile", panel.x + 10, panel.y + 8, self.font)
        if hover_tile is None:
            self.panels._draw_text(surface, "Move over the map", panel.x + 10, panel.y + 34, self.font_small, COLORS["muted_text"])
            return panel.bottom

        tx, ty = hover_tile
        tile = city_map.get(tx, ty)
        kind = self._tile_kind(tile)
        self.panels._draw_text(surface, fit_label(f"{tx},{ty} {kind}", self.font_small, width - 20), panel.x + 10, panel.y + 32, self.font_small)
        self.panels._draw_text(
            surface,
            fit_label(f"Dev {tile.development:.0%}  Val {tile.land_value:.2f}", self.font_small, width - 20),
            panel.x + 10,
            panel.y + 50,
            self.font_small,
            COLORS["muted_text"],
        )
        self.panels._draw_text(
            surface,
            fit_label(f"R {tile.residents}  J {tile.jobs}  Fire {tile.fire_risk}%  Crime {tile.crime_risk}%", self.font_small, width - 20),
            panel.x + 10,
            panel.y + 68,
            self.font_small,
            COLORS["muted_text"],
        )
        status, status_color = self.panels._tile_status(tile, city_map, tx, ty)
        self.panels._draw_text(surface, fit_label(status, self.font_small, width - 20), panel.x + 10, panel.y + 88, self.font_small, status_color)
        return panel.bottom

    def _draw_advisor_compact(self, surface: pygame.Surface, stats, x: int, y: int, width: int, height: int) -> int:
        if height < 70:
            return y
        panel = self.panels._panel(surface, x, y, width, height)
        self.panels._draw_text(surface, "Advisor", panel.x + 10, panel.y + 8, self.font)
        line_y = panel.y + 34
        for message in stats.messages[-2:]:
            self.panels._draw_wrapped_text(surface, message, panel.x + 10, line_y, width - 20)
            line_y += 34
            if line_y > panel.bottom - 18:
                break
        return panel.bottom

    def _tile_kind(self, tile) -> str:
        return self.panels._tile_kind(tile)

    def _reset_click_targets(self) -> None:
        self.menu_buttons.clear()
        self.tool_buttons.clear()
        self.speed_rects.clear()
        self.minimize_rect = pygame.Rect(0, 0, 0, 0)
        self.tax_down_rect = pygame.Rect(0, 0, 0, 0)
        self.tax_up_rect = pygame.Rect(0, 0, 0, 0)
        self.pause_rect = pygame.Rect(0, 0, 0, 0)
        self.fullscreen_rect = pygame.Rect(0, 0, 0, 0)
        self.save_rect = pygame.Rect(0, 0, 0, 0)
        self.load_rect = pygame.Rect(0, 0, 0, 0)

    def _max_scroll(self) -> int:
        return max(0, self.content_height - self.content_rect.height)

    def _clamp_scroll(self) -> None:
        self.scroll_offset = max(0, min(self.scroll_offset, self._max_scroll()))

