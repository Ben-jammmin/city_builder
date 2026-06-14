from __future__ import annotations

import pygame

from .city_map import CityMap
from .models import (
    BUILDING_LABELS,
    MENU_ORDER,
    MENU_TOOLS,
    TOOL_HOTKEYS,
    TOOL_LABELS,
    BuildingType,
    Tool,
    ZoneType,
)
from .settings import COLORS, MAX_TAX_RATE, MIN_TAX_RATE, SIDEBAR_WIDTH, WINDOW_HEIGHT, WINDOW_WIDTH


class Sidebar:
    def __init__(self) -> None:
        self.rect = pygame.Rect(WINDOW_WIDTH - SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, WINDOW_HEIGHT)
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

    def set_screen_size(self, width: int, height: int) -> None:
        self.rect = pygame.Rect(width - SIDEBAR_WIDTH, 0, SIDEBAR_WIDTH, height)

    def draw(
        self,
        surface: pygame.Surface,
        stats,
        city_map: CityMap,
        active_tool: Tool,
        active_menu: str,
        fullscreen: bool,
        hover_tile,
    ) -> None:
        pygame.draw.rect(surface, COLORS["sidebar"], self.rect)
        self.menu_buttons.clear()
        self.tool_buttons.clear()

        x = self.rect.left + 16
        y = 16
        width = SIDEBAR_WIDTH - 32

        self._draw_text(surface, "City Builder", x, y, self.font_large)
        y += 34
        y = self._draw_city_stats(surface, stats, x, y)
        y = self._draw_menu_tabs(surface, x, y + 6, width, active_menu)
        y = self._draw_controls(surface, stats, x, y + 8, width, fullscreen)
        y = self._draw_demand_panel(surface, stats, x, y + 8, width)
        y = self._draw_system_panel(surface, stats, x, y + 8, width)
        y = self._draw_tool_buttons(surface, x, y + 8, width, active_tool, active_menu)
        y = self._draw_hover_panel(surface, city_map, hover_tile, x, y + 8, width)
        self._draw_messages(surface, stats, x, y + 8, width)

    def handle_click(self, pos: tuple[int, int]):
        if not self.rect.collidepoint(pos):
            return None
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

    def _draw_city_stats(self, surface: pygame.Surface, stats, x: int, y: int) -> int:
        self._draw_stat(surface, "Money", f"${stats.money:,}", x, y, positive=stats.money >= 0)
        y += 22
        self._draw_stat(surface, "Population", f"{stats.population:,}", x, y)
        y += 22
        self._draw_stat(surface, "Jobs", f"{stats.jobs:,}", x, y)
        y += 22
        self._draw_stat(surface, "Date", f"Y{stats.year} M{stats.month}", x, y)
        return y + 24

    def _draw_menu_tabs(self, surface: pygame.Surface, x: int, y: int, width: int, active_menu: str) -> int:
        button_w = (width - 8) // 3
        for index, menu_name in enumerate(MENU_ORDER):
            rect = pygame.Rect(x + index * (button_w + 4), y, button_w, 30)
            self.menu_buttons.append((rect, menu_name))
            self._button(surface, rect, menu_name, active=menu_name == active_menu)
        return y + 34

    def _draw_controls(self, surface: pygame.Surface, stats, x: int, y: int, width: int, fullscreen: bool) -> int:
        panel = self._panel(surface, x, y, width, 74)
        self._draw_text(surface, "Menu", panel.x + 10, panel.y + 8, self.font)

        self.tax_down_rect = pygame.Rect(panel.x + 10, panel.y + 34, 32, 28)
        tax_rect = pygame.Rect(panel.x + 46, panel.y + 34, 58, 28)
        self.tax_up_rect = pygame.Rect(panel.x + 108, panel.y + 34, 32, 28)
        self._button(surface, self.tax_down_rect, "-", disabled=stats.tax_rate <= MIN_TAX_RATE)
        self._button(surface, tax_rect, f"{stats.tax_rate}%")
        self._button(surface, self.tax_up_rect, "+", disabled=stats.tax_rate >= MAX_TAX_RATE)

        self.pause_rect = pygame.Rect(panel.x + 150, panel.y + 18, 60, 24)
        self.fullscreen_rect = pygame.Rect(panel.x + 150, panel.y + 44, 60, 24)
        self.save_rect = pygame.Rect(panel.x + 216, panel.y + 18, 58, 24)
        self.load_rect = pygame.Rect(panel.x + 216, panel.y + 44, 58, 24)
        self._button(surface, self.pause_rect, "Pause" if not stats.paused else "Run", active=stats.paused)
        self._button(surface, self.fullscreen_rect, "Window" if fullscreen else "Full")
        self._button(surface, self.save_rect, "Save")
        self._button(surface, self.load_rect, "Load")
        return panel.bottom

    def _draw_demand_panel(self, surface: pygame.Surface, stats, x: int, y: int, width: int) -> int:
        panel = self._panel(surface, x, y, width, 86)
        self._draw_text(surface, "Demand", panel.x + 10, panel.y + 8, self.font)
        self._bar(surface, "R", stats.demand_residential, COLORS["residential"], panel.x + 10, panel.y + 34, width - 20)
        self._bar(surface, "C", stats.demand_commercial, COLORS["commercial"], panel.x + 10, panel.y + 52, width - 20)
        self._bar(surface, "I", stats.demand_industrial, COLORS["industrial"], panel.x + 10, panel.y + 70, width - 20)
        return panel.bottom

    def _draw_system_panel(self, surface: pygame.Surface, stats, x: int, y: int, width: int) -> int:
        panel = self._panel(surface, x, y, width, 82)
        self._draw_text(surface, "Systems", panel.x + 10, panel.y + 8, self.font)
        self._draw_text(
            surface,
            f"Power {stats.power_usage}/{stats.power_capacity}",
            panel.x + 10,
            panel.y + 34,
            self.font_mono,
            self._capacity_color(stats.power_usage, stats.power_capacity),
        )
        self._draw_text(
            surface,
            f"Water {stats.water_usage}/{stats.water_capacity}",
            panel.x + 150,
            panel.y + 34,
            self.font_mono,
            self._capacity_color(stats.water_usage, stats.water_capacity),
        )
        self._bar(surface, "Svc", stats.service_score, COLORS["service"], panel.x + 10, panel.y + 58, width - 20)
        return panel.bottom

    def _draw_tool_buttons(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        width: int,
        active_tool: Tool,
        active_menu: str,
    ) -> int:
        tools = MENU_TOOLS[active_menu]
        rows = (len(tools) + 1) // 2
        panel = self._panel(surface, x, y, width, 36 + rows * 36)
        self._draw_text(surface, active_menu, panel.x + 10, panel.y + 8, self.font)
        button_w = (width - 28) // 2
        hotkeys_by_tool = {tool: key.upper() for key, tool in TOOL_HOTKEYS.items()}

        for index, tool in enumerate(tools):
            col = index % 2
            row = index // 2
            rect = pygame.Rect(panel.x + 10 + col * (button_w + 8), panel.y + 34 + row * 36, button_w, 30)
            self.tool_buttons.append((rect, tool))
            hotkey = hotkeys_by_tool.get(tool, "")
            label = f"{hotkey} {TOOL_LABELS[tool]}".strip()
            self._button(surface, rect, label, active=tool == active_tool, align_left=True)
        return panel.bottom

    def _draw_hover_panel(self, surface: pygame.Surface, city_map: CityMap, hover_tile, x: int, y: int, width: int) -> int:
        panel = self._panel(surface, x, y, width, 116)
        self._draw_text(surface, "Tile", panel.x + 10, panel.y + 8, self.font)
        if hover_tile is None:
            self._draw_text(surface, "Move over the map", panel.x + 10, panel.y + 38, self.font_small, COLORS["muted_text"])
            return panel.bottom

        tx, ty = hover_tile
        tile = city_map.get(tx, ty)
        self._draw_text(surface, f"{tx}, {ty}  {self._tile_kind(tile)}", panel.x + 10, panel.y + 34, self.font_small)
        self._draw_text(surface, f"Dev {tile.development:.0%}  Value {tile.land_value:.2f}", panel.x + 10, panel.y + 54, self.font_small)
        self._draw_text(surface, f"Residents {tile.residents}  Jobs {tile.jobs}", panel.x + 10, panel.y + 74, self.font_small)
        power = "Pwr" if tile.powered else "No Pwr"
        water = "Water" if tile.watered else "No Water"
        services = int(tile.police_coverage) + int(tile.fire_coverage) + int(tile.education_coverage)
        self._draw_text(surface, f"{power}  {water}  Services {services}/3", panel.x + 10, panel.y + 94, self.font_small)
        return panel.bottom

    def _draw_messages(self, surface: pygame.Surface, stats, x: int, y: int, width: int) -> None:
        remaining = max(70, self.rect.height - y - 12)
        panel = self._panel(surface, x, y, width, remaining)
        self._draw_text(surface, "Advisor", panel.x + 10, panel.y + 8, self.font)
        line_y = panel.y + 34
        for message in stats.messages[-3:]:
            self._draw_wrapped_text(surface, message, panel.x + 10, line_y, width - 20)
            line_y += 34

    def _tile_kind(self, tile) -> str:
        if tile.building != BuildingType.NONE:
            return BUILDING_LABELS[tile.building]
        if tile.has_road:
            return "Road"
        if tile.has_power_line:
            return "Power Line"
        if tile.has_water_pipe:
            return "Water Pipe"
        if tile.zone != ZoneType.EMPTY:
            return tile.zone.value.title()
        return "Empty"

    def _capacity_color(self, usage: int, capacity: int) -> tuple[int, int, int]:
        if capacity <= 0:
            return COLORS["money_bad"]
        if usage > capacity:
            return COLORS["money_bad"]
        return COLORS["money_good"]

    def _panel(self, surface: pygame.Surface, x: int, y: int, width: int, height: int) -> pygame.Rect:
        rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(surface, COLORS["sidebar_panel"], rect, border_radius=6)
        return rect

    def _bar(
        self,
        surface: pygame.Surface,
        label: str,
        value: int,
        color: tuple[int, int, int],
        x: int,
        y: int,
        width: int,
    ) -> None:
        label_surface = self.font_small.render(label, True, COLORS["text"])
        surface.blit(label_surface, (x, y - 2))
        bar_x = x + 38
        bar_w = width - 72
        bg = pygame.Rect(bar_x, y + 2, bar_w, 10)
        fill = pygame.Rect(bar_x, y + 2, int(bar_w * value / 100), 10)
        pygame.draw.rect(surface, (31, 36, 41), bg, border_radius=4)
        pygame.draw.rect(surface, color, fill, border_radius=4)
        value_surface = self.font_small.render(f"{value}%", True, COLORS["muted_text"])
        surface.blit(value_surface, (x + width - value_surface.get_width(), y - 2))

    def _draw_stat(self, surface: pygame.Surface, label: str, value: str, x: int, y: int, positive: bool | None = None) -> None:
        self._draw_text(surface, label, x, y, self.font_small, COLORS["muted_text"])
        color = COLORS["text"]
        if positive is True:
            color = COLORS["money_good"]
        elif positive is False:
            color = COLORS["money_bad"]
        text = self.font.render(value, True, color)
        surface.blit(text, (self.rect.right - 18 - text.get_width(), y - 3))

    def _button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        active: bool = False,
        disabled: bool = False,
        align_left: bool = False,
    ) -> None:
        color = COLORS["sidebar_panel_active"] if active else COLORS["sidebar_panel"]
        if disabled:
            color = (44, 48, 53)
        pygame.draw.rect(surface, color, rect, border_radius=5)
        pygame.draw.rect(surface, (78, 88, 96), rect, width=1, border_radius=5)
        text_color = COLORS["muted_text"] if disabled else COLORS["text"]
        text = self.font_small.render(label, True, text_color)
        if align_left:
            text_pos = (rect.x + 8, rect.centery - text.get_height() // 2)
        else:
            text_pos = (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2)
        surface.blit(text, text_pos)

    def _draw_text(
        self,
        surface: pygame.Surface,
        text: str,
        x: int,
        y: int,
        font: pygame.font.Font,
        color: tuple[int, int, int] | None = None,
    ) -> None:
        rendered = font.render(text, True, color or COLORS["text"])
        surface.blit(rendered, (x, y))

    def _draw_wrapped_text(self, surface: pygame.Surface, text: str, x: int, y: int, max_width: int) -> None:
        words = text.split()
        lines: list[str] = []
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if self.font_small.size(candidate)[0] <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        for offset, line_text in enumerate(lines[:2]):
            self._draw_text(surface, line_text, x, y + offset * 17, self.font_small, COLORS["muted_text"])
