from __future__ import annotations

import pygame

from .city_map import CityMap
from .models import (
    BUILDING_LABELS,
    MENU_ORDER,
    MENU_TOOLS,
    TERRAIN_LABELS,
    TOOL_HOTKEYS,
    TOOL_LABELS,
    VIEW_LABELS,
    BuildingType,
    Tool,
    ViewMode,
    ZoneType,
)
from .settings import COLORS, MAX_TAX_RATE, MIN_TAX_RATE

PANEL_GAP = 6
PANEL_PAD = 10
BUTTON_GAP = 6

MENU_TAB_LABELS = {
    "Zones": "Zones",
    "Utilities": "Utility",
    "Services": "Services",
    "Transport": "Transit",
}

TOOL_SHORT_LABELS = {
    Tool.INSPECT: "Inspect",
    Tool.RESIDENTIAL: "Residential",
    Tool.DENSE_RESIDENTIAL: "Dense Res",
    Tool.COMMERCIAL: "Commercial",
    Tool.DENSE_COMMERCIAL: "Dense Com",
    Tool.INDUSTRIAL: "Industrial",
    Tool.PARK: "Park",
    Tool.BULLDOZE: "Bulldoze",
    Tool.ROAD: "Road",
    Tool.POWER_LINE: "Power Line",
    Tool.WATER_PIPE: "Water Pipe",
    Tool.POWER_PLANT: "Plant",
    Tool.LARGE_POWER_PLANT: "Big Plant",
    Tool.WATER_TOWER: "Tower",
    Tool.LARGE_WATER_TOWER: "Large Tower",
    Tool.POLICE: "Police",
    Tool.FIRE: "Fire",
    Tool.SCHOOL: "School",
    Tool.TRAIN_STATION: "Train",
    Tool.AIRPORT: "Airport",
}

def _build_swatch_map() -> dict:
    return {
        Tool.RESIDENTIAL:       COLORS["residential"],
        Tool.DENSE_RESIDENTIAL: COLORS["residential"],
        Tool.COMMERCIAL:        COLORS["commercial"],
        Tool.DENSE_COMMERCIAL:  COLORS["commercial"],
        Tool.INDUSTRIAL:        COLORS["industrial"],
        Tool.PARK:              COLORS["park"],
        Tool.ROAD:              COLORS["road"],
        Tool.POWER_LINE:        COLORS["power"],
        Tool.WATER_PIPE:        COLORS["water"],
        Tool.POLICE:            COLORS["police"],
        Tool.FIRE:              COLORS["fire"],
        Tool.SCHOOL:            COLORS["school"],
        Tool.POWER_PLANT:       COLORS["power"],
        Tool.LARGE_POWER_PLANT: COLORS["power"],
        Tool.WATER_TOWER:       COLORS["water"],
        Tool.LARGE_WATER_TOWER: COLORS["water"],
        Tool.TRAIN_STATION:     COLORS["train_station"],
        Tool.AIRPORT:           COLORS["airport"],
    }


def fit_label(label: str, font: pygame.font.Font, max_width: int) -> str:
    if max_width <= 0:
        return ""
    if font.size(label)[0] <= max_width:
        return label
    suffix = "..."
    if font.size(suffix)[0] > max_width:
        return ""
    trimmed = label.rstrip()
    while trimmed and font.size(trimmed + suffix)[0] > max_width:
        trimmed = trimmed[:-1].rstrip()
    return f"{trimmed}{suffix}" if trimmed else suffix


class SidebarPanelRenderer:
    def __init__(self, sidebar) -> None:
        self.sidebar = sidebar
        self._swatch_map = _build_swatch_map()

    def draw_header(self, surface: pygame.Surface, x: int, y: int, view_mode: ViewMode) -> int:
        # Accent line across the top
        bar_rect = pygame.Rect(x, y, self.sidebar.rect.width - 28, 2)
        pygame.draw.rect(surface, (55, 80, 110), bar_rect)
        self._draw_text(surface, "City Builder", x, y + 6, self.sidebar.font_large)
        view_text = self.sidebar.font_small.render(f"{VIEW_LABELS[view_mode]} view", True, COLORS["muted_text"])
        surface.blit(view_text, (self.sidebar.rect.right - 14 - view_text.get_width(), y + 10))
        return y + 34

    def draw_city_stats(self, surface: pygame.Surface, stats, x: int, y: int, width: int) -> int:
        panel = self._panel(surface, x, y, width, 76)
        self._draw_text(surface, "City", panel.x + PANEL_PAD, panel.y + 8, self.sidebar.font)
        col_w = (width - PANEL_PAD * 2) // 2
        left_x = panel.x + PANEL_PAD
        right_x = left_x + col_w
        row_one = panel.y + 32
        row_two = panel.y + 54

        self._draw_stat_pair(surface, "Money", f"${stats.money:,}", left_x, row_one, col_w, stats.money >= 0)
        self._draw_stat_pair(surface, "Pop", f"{stats.population:,}", right_x, row_one, col_w)
        self._draw_stat_pair(surface, "Jobs", f"{stats.jobs:,}", left_x, row_two, col_w)
        self._draw_stat_pair(surface, "Date", f"Y{stats.year} M{stats.month}", right_x, row_two, col_w)
        return panel.bottom

    def draw_menu_tabs(self, surface: pygame.Surface, x: int, y: int, width: int, active_menu: str) -> int:
        gap = 4
        menu_count = max(1, len(MENU_ORDER))
        button_w = (width - gap * (menu_count - 1)) // menu_count
        for index, menu_name in enumerate(MENU_ORDER):
            rect = pygame.Rect(x + index * (button_w + gap), y, button_w, 28)
            self.sidebar.menu_buttons.append((rect, menu_name))
            label = MENU_TAB_LABELS.get(menu_name, menu_name)
            self._button(surface, rect, label, active=menu_name == active_menu)
        return y + 32

    def draw_controls(self, surface: pygame.Surface, stats, x: int, y: int, width: int, fullscreen: bool) -> int:
        panel = self._panel(surface, x, y, width, 68)
        self._draw_text(surface, "Controls", panel.x + PANEL_PAD, panel.y + 8, self.sidebar.font)

        self._draw_text(surface, "Tax", panel.x + PANEL_PAD, panel.y + 39, self.sidebar.font_small, COLORS["muted_text"])
        self.sidebar.tax_down_rect = pygame.Rect(panel.x + 42, panel.y + 34, 28, 24)
        tax_rect = pygame.Rect(panel.x + 74, panel.y + 34, 50, 24)
        self.sidebar.tax_up_rect = pygame.Rect(panel.x + 128, panel.y + 34, 28, 24)
        self._button(surface, self.sidebar.tax_down_rect, "-", disabled=stats.tax_rate <= MIN_TAX_RATE)
        self._button(surface, tax_rect, f"{stats.tax_rate}%")
        self._button(surface, self.sidebar.tax_up_rect, "+", disabled=stats.tax_rate >= MAX_TAX_RATE)

        self.sidebar.pause_rect = pygame.Rect(panel.x + 166, panel.y + 10, 54, 23)
        self.sidebar.fullscreen_rect = pygame.Rect(panel.x + 226, panel.y + 10, 56, 23)
        self.sidebar.save_rect = pygame.Rect(panel.x + 166, panel.y + 38, 54, 23)
        self.sidebar.load_rect = pygame.Rect(panel.x + 226, panel.y + 38, 56, 23)
        self._button(surface, self.sidebar.pause_rect, "Pause" if not stats.paused else "Run", active=stats.paused)
        self._button(surface, self.sidebar.fullscreen_rect, "Window" if fullscreen else "Full")
        self._button(surface, self.sidebar.save_rect, "Save")
        self._button(surface, self.sidebar.load_rect, "Load")
        return panel.bottom

    def draw_demand_panel(self, surface: pygame.Surface, stats, x: int, y: int, width: int) -> int:
        panel = self._panel(surface, x, y, width, 78)
        self._draw_text(surface, "Demand", panel.x + PANEL_PAD, panel.y + 8, self.sidebar.font)
        self._bar(surface, "R", stats.demand_residential, COLORS["residential"], panel.x + PANEL_PAD, panel.y + 32, width - PANEL_PAD * 2)
        self._bar(surface, "C", stats.demand_commercial, COLORS["commercial"], panel.x + PANEL_PAD, panel.y + 50, width - PANEL_PAD * 2)
        self._bar(surface, "I", stats.demand_industrial, COLORS["industrial"], panel.x + PANEL_PAD, panel.y + 68, width - PANEL_PAD * 2)
        return panel.bottom

    def draw_system_panel(self, surface: pygame.Surface, stats, x: int, y: int, width: int) -> int:
        panel = self._panel(surface, x, y, width, 136)
        self._draw_text(surface, "Systems", panel.x + PANEL_PAD, panel.y + 8, self.sidebar.font)
        self._draw_text(
            surface,
            f"Power {stats.power_usage}/{stats.power_capacity}  {stats.power_satisfaction}%",
            panel.x + PANEL_PAD,
            panel.y + 30,
            self.sidebar.font_mono,
            self._power_color(stats),
        )
        self._draw_text(
            surface,
            f"Water {stats.water_usage}/{stats.water_capacity}  {stats.water_satisfaction}%",
            panel.x + PANEL_PAD,
            panel.y + 48,
            self.sidebar.font_mono,
            self._water_color(stats),
        )
        fire_color = COLORS["money_good"] if stats.fire_uncovered_zones == 0 and stats.average_fire_risk < 70 else COLORS["money_bad"]
        self._draw_text(
            surface,
            f"Fire {stats.fire_coverage_percent}%  Risk {stats.average_fire_risk}%",
            panel.x + PANEL_PAD,
            panel.y + 66,
            self.sidebar.font_mono,
            fire_color,
        )
        police_color = COLORS["money_good"] if stats.police_uncovered_zones == 0 and stats.average_crime_risk < 70 else COLORS["money_bad"]
        self._draw_text(
            surface,
            f"Police {stats.police_coverage_percent}%  Crime {stats.average_crime_risk}%",
            panel.x + PANEL_PAD,
            panel.y + 84,
            self.sidebar.font_mono,
            police_color,
        )
        issue_text = "All zoned tiles connected"
        issue_color = COLORS["muted_text"]
        if stats.unpowered_zones or stats.unwatered_zones or stats.fire_uncovered_zones or stats.police_uncovered_zones:
            issue_text = (
                f"No P:{stats.unpowered_zones}  "
                f"No W:{stats.unwatered_zones}  "
                f"No F:{stats.fire_uncovered_zones}  "
                f"No Po:{stats.police_uncovered_zones}"
            )
            issue_color = COLORS["money_bad"]
        self._draw_text(surface, issue_text, panel.x + PANEL_PAD, panel.y + 104, self.sidebar.font_small, issue_color)
        self._bar(surface, "Svc", stats.service_score, COLORS["service"], panel.x + PANEL_PAD, panel.y + 120, width - PANEL_PAD * 2)
        return panel.bottom

    def draw_tool_buttons(
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
        row_h = 30
        panel = self._panel(surface, x, y, width, 32 + rows * row_h)
        self._draw_text(surface, active_menu, panel.x + PANEL_PAD, panel.y + 8, self.sidebar.font)
        if active_tool in tools:
            active_label = fit_label(TOOL_SHORT_LABELS.get(active_tool, TOOL_LABELS[active_tool]), self.sidebar.font_small, width // 2)
            active_text = self.sidebar.font_small.render(active_label, True, COLORS["muted_text"])
            surface.blit(active_text, (panel.right - PANEL_PAD - active_text.get_width(), panel.y + 10))
        button_w = (width - PANEL_PAD * 2 - BUTTON_GAP) // 2
        hotkeys_by_tool = {tool: key.upper() for key, tool in TOOL_HOTKEYS.items()}

        for index, tool in enumerate(tools):
            col = index % 2
            row = index // 2
            rect = pygame.Rect(panel.x + PANEL_PAD + col * (button_w + BUTTON_GAP), panel.y + 30 + row * row_h, button_w, 25)
            self.sidebar.tool_buttons.append((rect, tool))
            hotkey = hotkeys_by_tool.get(tool, "")
            label = self._tool_button_label(tool, hotkey)
            swatch = self._swatch_map.get(tool)
            self._button(surface, rect, label, active=tool == active_tool, align_left=True, swatch_color=swatch)
        return panel.bottom

    def draw_hover_panel(self, surface: pygame.Surface, city_map: CityMap, hover_tile, x: int, y: int, width: int) -> int:
        panel = self._panel(surface, x, y, width, 118)
        self._draw_text(surface, "Tile", panel.x + PANEL_PAD, panel.y + 8, self.sidebar.font)
        if hover_tile is None:
            self._draw_text(surface, "Move over the map", panel.x + PANEL_PAD, panel.y + 34, self.sidebar.font_small, COLORS["muted_text"])
            return panel.bottom

        tx, ty = hover_tile
        tile = city_map.get(tx, ty)
        self._draw_text(surface, f"{tx}, {ty}  {self._tile_kind(tile)}", panel.x + PANEL_PAD, panel.y + 30, self.sidebar.font_small)
        self._draw_text(surface, f"{TERRAIN_LABELS[tile.terrain]}  Dev {tile.development:.0%}  Value {tile.land_value:.2f}", panel.x + PANEL_PAD, panel.y + 48, self.sidebar.font_small)
        self._draw_text(surface, f"Residents {tile.residents}  Jobs {tile.jobs}", panel.x + PANEL_PAD, panel.y + 66, self.sidebar.font_small)
        power = "Pwr" if tile.powered else "No Pwr"
        water = "Water" if tile.watered else "No Water"
        services = int(tile.police_coverage) + int(tile.fire_coverage) + int(tile.education_coverage)
        self._draw_text(surface, f"{power}  {water}  Svc {services}/3", panel.x + PANEL_PAD, panel.y + 84, self.sidebar.font_small)
        self._draw_text(
            surface,
            f"Fire {tile.fire_risk}%  Crime {tile.crime_risk}%",
            panel.x + PANEL_PAD,
            panel.y + 100,
            self.sidebar.font_small,
        )
        return panel.bottom

    def draw_messages(self, surface: pygame.Surface, stats, x: int, y: int, width: int) -> int:
        panel = self._panel(surface, x, y, width, 148)
        self._draw_text(surface, "Advisor", panel.x + PANEL_PAD, panel.y + 8, self.sidebar.font)
        line_y = panel.y + 34
        for message in stats.messages[-3:]:
            self._draw_wrapped_text(surface, message, panel.x + PANEL_PAD, line_y, width - PANEL_PAD * 2)
            line_y += 34
        return panel.bottom

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
            prefix = "Dense " if tile.zone_level > 1 else ""
            return f"{prefix}{tile.zone.value.title()}"
        return "Empty"

    def _tool_button_label(self, tool: Tool, hotkey: str) -> str:
        label = TOOL_SHORT_LABELS.get(tool, TOOL_LABELS[tool])
        return f"{hotkey} {label}".strip()

    def _draw_stat_pair(
        self,
        surface: pygame.Surface,
        label: str,
        value: str,
        x: int,
        y: int,
        width: int,
        positive: bool | None = None,
    ) -> None:
        self._draw_text(surface, label, x, y, self.sidebar.font_small, COLORS["muted_text"])
        color = COLORS["text"]
        if positive is True:
            color = COLORS["money_good"]
        elif positive is False:
            color = COLORS["money_bad"]
        value_x = x + 46
        fitted = fit_label(value, self.sidebar.font_small, max(16, width - 52))
        self._draw_text(surface, fitted, value_x, y, self.sidebar.font_small, color)

    def _power_color(self, stats) -> tuple[int, int, int]:
        if stats.power_capacity <= 0 or stats.unpowered_zones > 0:
            return COLORS["money_bad"]
        if stats.power_usage > stats.power_capacity:
            return COLORS["money_bad"]
        return COLORS["money_good"]

    def _water_color(self, stats) -> tuple[int, int, int]:
        if stats.water_capacity <= 0 or stats.unwatered_zones > 0:
            return COLORS["money_bad"]
        if stats.water_usage > stats.water_capacity:
            return COLORS["money_bad"]
        return COLORS["money_good"]

    def _panel(self, surface: pygame.Surface, x: int, y: int, width: int, height: int) -> pygame.Rect:
        rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(surface, COLORS["sidebar_panel"], rect, border_radius=6)
        # Subtle top-edge highlight
        pygame.draw.line(surface, (38, 48, 60), (rect.x + 6, rect.y + 1), (rect.right - 6, rect.y + 1))
        # Inner panel separator under the title area
        sep_y = rect.y + 24
        pygame.draw.line(surface, (20, 26, 34), (rect.x + 6, sep_y), (rect.right - 6, sep_y))
        pygame.draw.line(surface, (36, 44, 56), (rect.x + 6, sep_y + 1), (rect.right - 6, sep_y + 1))
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
        label_surface = self.sidebar.font_small.render(label, True, COLORS["text"])
        surface.blit(label_surface, (x, y - 2))
        bar_x = x + 38
        bar_w = width - 72
        bg = pygame.Rect(bar_x, y + 2, bar_w, 10)
        fill = pygame.Rect(bar_x, y + 2, int(bar_w * value / 100), 10)
        pygame.draw.rect(surface, (31, 36, 41), bg, border_radius=4)
        pygame.draw.rect(surface, color, fill, border_radius=4)
        value_surface = self.sidebar.font_small.render(f"{value}%", True, COLORS["muted_text"])
        surface.blit(value_surface, (x + width - value_surface.get_width(), y - 2))

    def _button(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        active: bool = False,
        disabled: bool = False,
        align_left: bool = False,
        swatch_color: tuple | None = None,
    ) -> None:
        color = COLORS["sidebar_panel_active"] if active else COLORS["sidebar_panel"]
        if disabled:
            color = (36, 40, 46)
        pygame.draw.rect(surface, color, rect, border_radius=5)
        # Bevel highlight (top/left edge lighter, bottom/right darker)
        if not disabled:
            hi = (min(255, color[0] + 18), min(255, color[1] + 18), min(255, color[2] + 22))
            sh = (max(0, color[0] - 14), max(0, color[1] - 14), max(0, color[2] - 14))
            if active:
                hi, sh = sh, hi  # pressed: invert bevel
            pygame.draw.line(surface, hi, (rect.x + 5, rect.y + 1), (rect.right - 6, rect.y + 1))
            pygame.draw.line(surface, hi, (rect.x + 1, rect.y + 5), (rect.x + 1, rect.bottom - 6))
            pygame.draw.line(surface, sh, (rect.x + 5, rect.bottom - 1), (rect.right - 6, rect.bottom - 1))
            pygame.draw.line(surface, sh, (rect.right - 1, rect.y + 5), (rect.right - 1, rect.bottom - 6))
        # Border
        border_color = (80, 100, 120) if active else (55, 66, 78)
        pygame.draw.rect(surface, border_color, rect, width=1, border_radius=5)
        # Active left accent bar
        if active:
            bar = pygame.Rect(rect.x + 2, rect.y + 4, 3, rect.height - 8)
            pygame.draw.rect(surface, (95, 155, 220), bar, border_radius=2)
        text_color = COLORS["muted_text"] if disabled else COLORS["text"]
        swatch_w = 0
        if swatch_color and align_left and not disabled and rect.width >= 38:
            swatch_w = 7
            sx = rect.x + (13 if active else 10)
            sy = rect.centery - 4
            sc = swatch_color
            diam = [(sx + 4, sy), (sx + swatch_w, sy + 4), (sx + 4, sy + 8), (sx, sy + 4)]
            pygame.draw.polygon(surface, sc, diam)
            pygame.draw.polygon(surface, (max(0, sc[0] - 40), max(0, sc[1] - 40), max(0, sc[2] - 40)), diam, 1)
        text_budget = rect.width - 12 if swatch_w == 0 else rect.width - 12 - swatch_w - 8
        fitted_label = fit_label(label, self.sidebar.font_small, max(0, text_budget))
        text = self.sidebar.font_small.render(fitted_label, True, text_color)
        if align_left:
            text_x = rect.x + 10 + (swatch_w + 8 if swatch_w > 0 else 0)
            if active:
                text_x += 3
            text_pos = (text_x, rect.centery - text.get_height() // 2)
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
            if self.sidebar.font_small.size(candidate)[0] <= max_width:
                line = candidate
            else:
                if line:
                    lines.append(line)
                line = word
        if line:
            lines.append(line)
        for offset, line_text in enumerate(lines[:2]):
            self._draw_text(surface, line_text, x, y + offset * 17, self.sidebar.font_small, COLORS["muted_text"])
