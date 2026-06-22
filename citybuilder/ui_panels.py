"""
ui_panels.py — Low-level panel and widget renderers for the sidebar.

SidebarPanelRenderer draws each individual section of the bottom command bar:
  - City stats panel     (money, population, jobs, date, revenue)
  - Controls panel       (tax +/-, pause, speed, save, load buttons)
  - Demand panel         (R/C/I horizontal progress bars)
  - System panel         (power, water, fire, police, education coverage)
  - Menu tab row         (Zones / Recreation / Utilities / Services / Transit)
  - Tool button grid     (active tools for the selected menu tab)

Drawing helpers at the bottom (_panel, _button, _bar, _draw_text) are shared
primitives used by every panel above.

fit_label(label, font, max_width) truncates a string with "..." so it always
fits within the given pixel width — used wherever space is tight.
"""
from __future__ import annotations

import pygame

from .city_map import CityMap
from .models import (
    BUILDING_LABELS,
    MENU_ORDER,
    MENU_TOOLS,
    RECREATION_LABELS,
    TOOL_HOTKEYS,
    TOOL_LABELS,
    TOOL_TO_BUILDING,
    TOOL_TO_RECREATION,
    TOOL_TO_ZONE,
    BuildingType,
    Tool,
    ZoneType,
)
from .settings import (
    BOND_OPTIONS, BUILDING_COST, COLORS, HIGH_RISK_THRESHOLD, HIGHRISE_MIN_LAND_VALUE,
    MAX_TAX_RATE, MIN_TAX_RATE, POPULATION_MILESTONES, RECREATION_COST,
    ROAD_COST, POWER_LINE_COST, WATER_PIPE_COST,
    ROAD_TRAFFIC_CAPACITY, ZONE_COST, ZONE_LEVEL_COST_MULTIPLIERS,
)

# ── Layout constants ───────────────────────────────────────────────────────────
PANEL_GAP = 6    # vertical gap between stacked panels
PANEL_PAD = 10   # inner horizontal padding inside a panel
BUTTON_GAP = 6   # gap between adjacent buttons in the same row

_MONTH_NAMES = ("Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec")

# Panel header accent colours (left-edge stripe).
_ACCENT_CITY     = (175, 148,  48)
_ACCENT_CONTROLS = ( 75, 132, 208)
_ACCENT_DEMAND   = ( 80, 185,  92)
_ACCENT_SYSTEMS  = ( 72, 178, 215)
_ACCENT_TOOLS    = (105, 120, 140)
_ACCENT_ADVISOR  = (140, 105, 188)

# Short display names for the menu tabs across the top of the tool area.
MENU_TAB_LABELS = {
    "Zones": "Zones",
    "Recreation": "Rec",
    "Utilities": "Utility",
    "Services": "Services",
    "Transport": "Transit",
}

TOOL_SHORT_LABELS = {
    Tool.INSPECT: "Inspect",
    Tool.RESIDENTIAL: "Residential",
    Tool.DENSE_RESIDENTIAL: "Dense Res",
    Tool.HIGHRISE_RESIDENTIAL: "Highrise Res",
    Tool.COMMERCIAL: "Commercial",
    Tool.DENSE_COMMERCIAL: "Dense Com",
    Tool.HIGHRISE_COMMERCIAL: "Highrise Com",
    Tool.INDUSTRIAL: "Industrial",
    Tool.PARK: "Park",
    Tool.PLAYGROUND: "Playground",
    Tool.SPORTS_FIELD: "Sports Fld",
    Tool.STADIUM: "Stadium",
    Tool.GOLF_COURSE: "Golf Course",
    Tool.POOL: "Pool",
    Tool.CINEMA: "Cinema",
    Tool.MUSEUM: "Museum",
    Tool.ZOO: "Zoo",
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
    Tool.HOSPITAL: "Hospital",
    Tool.TRAIN_STATION: "Train",
    Tool.AIRPORT: "Airport",
}

def _build_swatch_map() -> dict:
    """Returns a dict mapping each Tool to its colour swatch shown on the tool button."""
    return {
        Tool.RESIDENTIAL:          COLORS["residential"],
        Tool.DENSE_RESIDENTIAL:    COLORS["residential"],
        Tool.HIGHRISE_RESIDENTIAL: COLORS["residential"],
        Tool.COMMERCIAL:           COLORS["commercial"],
        Tool.DENSE_COMMERCIAL:     COLORS["commercial"],
        Tool.HIGHRISE_COMMERCIAL:  COLORS["commercial"],
        Tool.INDUSTRIAL:        COLORS["industrial"],
        Tool.PARK:              COLORS["park"],
        Tool.PLAYGROUND:        COLORS["playground"],
        Tool.SPORTS_FIELD:      COLORS["sports_field"],
        Tool.STADIUM:           COLORS["stadium"],
        Tool.GOLF_COURSE:       COLORS["golf_course"],
        Tool.POOL:              COLORS["pool"],
        Tool.CINEMA:            COLORS["cinema"],
        Tool.MUSEUM:            COLORS["museum"],
        Tool.ZOO:               COLORS["zoo"],
        Tool.ROAD:              COLORS["road"],
        Tool.POWER_LINE:        COLORS["power"],
        Tool.WATER_PIPE:        COLORS["water"],
        Tool.POLICE:            COLORS["police"],
        Tool.FIRE:              COLORS["fire"],
        Tool.SCHOOL:            COLORS["school"],
        Tool.HOSPITAL:          COLORS["hospital"],
        Tool.POWER_PLANT:       COLORS["power"],
        Tool.LARGE_POWER_PLANT: COLORS["power"],
        Tool.WATER_TOWER:       COLORS["water"],
        Tool.LARGE_WATER_TOWER: COLORS["water"],
        Tool.TRAIN_STATION:     COLORS["train_station"],
        Tool.AIRPORT:           COLORS["airport"],
    }


def fit_label(label: str, font: pygame.font.Font, max_width: int) -> str:
    """
    Truncates label to fit within max_width pixels, appending "..." when cut.
    Returns an empty string if even "..." won't fit.
    """
    if max_width <= 0:
        return ""
    if font.size(label)[0] <= max_width:
        return label
    suffix = "..."
    if font.size(suffix)[0] > max_width:
        return ""
    trimmed = label.rstrip()
    # Strip one character at a time from the right until it fits.
    while trimmed and font.size(trimmed + suffix)[0] > max_width:
        trimmed = trimmed[:-1].rstrip()
    return f"{trimmed}{suffix}" if trimmed else suffix


class SidebarPanelRenderer:
    """Draws every individual panel section inside the sidebar."""

    def __init__(self, sidebar) -> None:
        # Keep a reference to the parent Sidebar for fonts and click-target lists.
        self.sidebar = sidebar
        self._swatch_map = _build_swatch_map()

    # ── Panel draw methods ─────────────────────────────────────────────────────

    def draw_city_stats(self, surface: pygame.Surface, stats, x: int, y: int, width: int) -> int:
        """Draws the city overview panel (money, pop, jobs, date, revenue, net, goal, sparkline). Returns bottom y."""
        panel = self._panel(surface, x, y, width, 134, accent_color=_ACCENT_CITY)

        # Title row: milestone name (left) + grade + appr% (right).
        city_title = "Outpost"
        for pop_thresh, title, _ in POPULATION_MILESTONES:
            if stats.population >= pop_thresh:
                city_title = title
        self._draw_text(surface, city_title, panel.x + PANEL_PAD, panel.y + 6, self.sidebar.font)

        appr       = getattr(stats, "approval_rating", 75)
        appr_color = (COLORS["money_good"] if appr >= 70 else ((230, 140, 60) if appr >= 40 else COLORS["money_bad"]))
        grade      = getattr(stats, "city_grade", "")
        score      = getattr(stats, "city_score", 0)
        grade_col  = (COLORS["money_good"] if score >= 70 else ((230, 140, 60) if score >= 50 else COLORS["money_bad"]))
        appr_surf  = self.sidebar.font_small.render(f"Appr {appr}%", True, appr_color)
        grade_surf = self.sidebar.font_small.render(grade, True, grade_col)
        surface.blit(appr_surf,  (panel.right - PANEL_PAD - appr_surf.get_width(), panel.y + 8))
        surface.blit(grade_surf, (panel.right - PANEL_PAD - appr_surf.get_width() - grade_surf.get_width() - 8, panel.y + 8))

        col_w  = (width - PANEL_PAD * 2) // 2
        left_x = panel.x + PANEL_PAD
        right_x = left_x + col_w
        r1 = panel.y + 26
        r2 = panel.y + 43
        r3 = panel.y + 60

        # Row 1: money (large) + population with delta.
        money_color = COLORS["money_good"] if stats.money >= 0 else COLORS["money_bad"]
        self._draw_text(surface, "$", left_x, r1 + 1, self.sidebar.font_small, COLORS["muted_text"])
        self._draw_text(surface, f"{stats.money:,}", left_x + 12, r1 - 1, self.sidebar.font, money_color)
        pop_delta     = stats.last_population_delta
        pop_sign      = "+" if pop_delta > 0 else ""
        pop_delta_str = f"({pop_sign}{pop_delta})" if pop_delta != 0 else ""
        pop_color     = COLORS["money_good"] if pop_delta >= 0 else COLORS["money_bad"]
        self._draw_text(surface, "Pop", right_x, r1, self.sidebar.font_small, COLORS["muted_text"])
        self._draw_text(surface, fit_label(f"{stats.population:,} {pop_delta_str}", self.sidebar.font_small, col_w - 32),
                        right_x + 32, r1, self.sidebar.font_small, pop_color)

        # Row 2: jobs + date.
        month_name = _MONTH_NAMES[(stats.month - 1) % 12]
        self._draw_stat_pair(surface, "Jobs", f"{stats.jobs:,}", left_x, r2, col_w)
        self._draw_stat_pair(surface, "Date", f"Y{stats.year} {month_name}", right_x, r2, col_w)

        # Row 3: revenue + net income.
        net     = stats.last_revenue - stats.last_expenses
        net_str = f"+${net:,}" if net >= 0 else f"-${-net:,}"
        self._draw_stat_pair(surface, "Rev", f"${stats.last_revenue:,}", left_x, r3, col_w, True)
        self._draw_stat_pair(surface, "Net", net_str, right_x, r3, col_w, net >= 0)

        # Row 4: milestone goal bar + budget sparkline side by side.
        bar_y   = panel.y + 78
        bar_w   = width - PANEL_PAD * 2
        next_ms = next((ms for ms in POPULATION_MILESTONES if stats.population < ms[0]), None)
        if next_ms:
            goal_pop, goal_title, _ = next_ms
            frac = min(1.0, stats.population / goal_pop) if goal_pop > 0 else 1.0
            self._draw_text(surface, f"→ {goal_title}  {stats.population:,}/{goal_pop:,}",
                            left_x, bar_y, self.sidebar.font_small, COLORS["muted_text"])
            pygame.draw.rect(surface, (35, 45, 55), pygame.Rect(left_x, bar_y + 14, bar_w, 6), border_radius=3)
            if frac > 0:
                fill_c = COLORS["money_good"] if frac >= 0.8 else COLORS["commercial"]
                pygame.draw.rect(surface, fill_c, pygame.Rect(left_x, bar_y + 14, int(bar_w * frac), 6), border_radius=3)
        else:
            self._draw_text(surface, "All milestones reached!", left_x, bar_y, self.sidebar.font_small, COLORS["money_good"])

        # Budget sparkline (right-aligned on the same row as the annual forecast).
        spark_y   = bar_y + 24
        history   = stats.budget_history[-6:] if stats.budget_history else []
        net_cur   = stats.last_revenue - stats.last_expenses
        annual    = net_cur * 12
        if annual != 0:
            ann_str   = f"~+${annual:,}/yr" if annual >= 0 else f"~-${-annual:,}/yr"
            ann_color = COLORS["money_good"] if annual >= 0 else COLORS["money_bad"]
            ann_surf  = self.sidebar.font_small.render(ann_str, True, ann_color)
            surface.blit(ann_surf, (panel.right - PANEL_PAD - ann_surf.get_width(), spark_y))
        if history:
            spark_x    = left_x
            spark_avail = bar_w - (ann_surf.get_width() + 6 if annual != 0 else 0)
            slot_w     = max(4, spark_avail // len(history))
            max_net    = max(abs(r - e) for r, e in history) or 1
            bar_h      = 12
            for i, (rev, exp) in enumerate(history):
                net_i    = rev - exp
                bh       = max(2, int(abs(net_i) / max_net * bar_h))
                bx       = spark_x + i * slot_w
                bar_col  = COLORS["money_good"] if net_i >= 0 else COLORS["money_bad"]
                by       = spark_y + bar_h - bh if net_i >= 0 else spark_y + bar_h
                pygame.draw.rect(surface, bar_col, (bx, by, slot_w - 1, bh), border_radius=1)
            pygame.draw.line(surface, (50, 62, 76),
                             (spark_x, spark_y + bar_h), (spark_x + len(history) * slot_w, spark_y + bar_h))

        return panel.bottom

    def draw_menu_tabs(self, surface: pygame.Surface, x: int, y: int, width: int, active_menu: str) -> int:
        """Draws the row of menu category tabs and registers them as click targets. Returns the bottom y."""
        gap = 4
        menu_count = max(1, len(MENU_ORDER))
        button_w = (width - gap * (menu_count - 1)) // menu_count
        for index, menu_name in enumerate(MENU_ORDER):
            rect = pygame.Rect(x + index * (button_w + gap), y, button_w, 28)
            self.sidebar.menu_buttons.append((rect, menu_name))
            label = MENU_TAB_LABELS.get(menu_name, menu_name)
            self._button(surface, rect, label, active=menu_name == active_menu)
        return y + 32

    def draw_controls(self, surface: pygame.Surface, stats, x: int, y: int, width: int, fullscreen: bool, speed_index: int, speed_labels: list) -> int:
        """Draws the controls panel (tax, pause, speed, save/load). Returns the bottom y."""
        panel = self._panel(surface, x, y, width, 80, accent_color=_ACCENT_CONTROLS)

        # Row 1: Tax label + −/rate/+ buttons, then Pause / Full / Save / Load all in one line.
        r1 = panel.y + 10
        self._draw_text(surface, "Tax", panel.x + PANEL_PAD, r1 + 3, self.sidebar.font_small, COLORS["muted_text"])
        self.sidebar.tax_down_rect = pygame.Rect(panel.x + PANEL_PAD + 26, r1, 22, 22)
        tax_rect                   = pygame.Rect(panel.x + PANEL_PAD + 52, r1, 40, 22)
        self.sidebar.tax_up_rect   = pygame.Rect(panel.x + PANEL_PAD + 96, r1, 22, 22)
        self._button(surface, self.sidebar.tax_down_rect, "-", disabled=stats.tax_rate <= MIN_TAX_RATE)
        self._button(surface, tax_rect, f"{stats.tax_rate}%")
        self._button(surface, self.sidebar.tax_up_rect,   "+", disabled=stats.tax_rate >= MAX_TAX_RATE)

        btn_x = panel.x + PANEL_PAD + 124
        btn_w = (width - PANEL_PAD * 2 - 124 - BUTTON_GAP * 3) // 4
        self.sidebar.pause_rect      = pygame.Rect(btn_x,                           r1, btn_w, 22)
        self.sidebar.fullscreen_rect = pygame.Rect(btn_x + (btn_w + BUTTON_GAP),   r1, btn_w, 22)
        self.sidebar.save_rect       = pygame.Rect(btn_x + (btn_w + BUTTON_GAP)*2, r1, btn_w, 22)
        self.sidebar.load_rect       = pygame.Rect(btn_x + (btn_w + BUTTON_GAP)*3, r1, btn_w, 22)
        self._button(surface, self.sidebar.pause_rect,      "Pause" if not stats.paused else "Run", active=stats.paused)
        self._button(surface, self.sidebar.fullscreen_rect, "Win" if fullscreen else "Full")
        self._button(surface, self.sidebar.save_rect,       "Save")
        self._button(surface, self.sidebar.load_rect,       "Load")

        # Row 2: Speed label + preset buttons.
        r2 = panel.y + 40
        self._draw_text(surface, "Speed", panel.x + PANEL_PAD, r2 + 3, self.sidebar.font_small, COLORS["muted_text"])
        n          = len(speed_labels)
        spd_area_x = panel.x + PANEL_PAD + 46
        spd_area_w = width - PANEL_PAD * 2 - 46
        spd_btn_w  = (spd_area_w - BUTTON_GAP * (n - 1)) // n
        for i, label in enumerate(speed_labels):
            rect = pygame.Rect(spd_area_x + i * (spd_btn_w + BUTTON_GAP), r2, spd_btn_w, 22)
            self.sidebar.speed_rects.append((rect, i))
            self._button(surface, rect, label, active=(i == speed_index))

        # Bond debt indicator (right-aligned in row 2 area if no space conflict).
        bonds = getattr(stats, "bonds", [])
        if bonds:
            monthly   = sum(b["monthly_payment"] for b in bonds)
            bond_str  = f"Debt ${monthly:,}/mo"
            bond_surf = self.sidebar.font_small.render(bond_str, True, (220, 165, 55))
            surface.blit(bond_surf, (panel.right - PANEL_PAD - bond_surf.get_width(), panel.y + 62))

        return panel.bottom

    def _demand_arrow(self, current: int, prev: int) -> str:
        """Returns a Unicode arrow prefix showing demand trend (▲/▼/empty)."""
        diff = current - prev
        if diff >= 4:
            return "▲"   # ▲
        if diff <= -4:
            return "▼"   # ▼
        return ""

    def draw_demand_panel(self, surface: pygame.Surface, stats, x: int, y: int, width: int) -> int:
        """Draws three horizontal demand bars for Residential, Commercial, and Industrial zones. Returns the bottom y."""
        demand_history = getattr(stats, "demand_history", [])
        spark_w = 36 if demand_history else 0
        panel = self._panel(surface, x, y, width, 82, accent_color=_ACCENT_DEMAND)
        self._draw_text(surface, "Demand", panel.x + PANEL_PAD, panel.y + 8, self.sidebar.font)
        prev_res = getattr(stats, "prev_demand_residential", stats.demand_residential)
        prev_com = getattr(stats, "prev_demand_commercial", stats.demand_commercial)
        prev_ind = getattr(stats, "prev_demand_industrial", stats.demand_industrial)
        res_lbl = self._demand_arrow(stats.demand_residential, prev_res) + "Res"
        com_lbl = self._demand_arrow(stats.demand_commercial, prev_com) + "Com"
        ind_lbl = self._demand_arrow(stats.demand_industrial, prev_ind) + "Ind"
        bar_w = width - PANEL_PAD * 2 - spark_w - (4 if spark_w else 0)
        self._bar(surface, res_lbl, stats.demand_residential, COLORS["residential"], panel.x + PANEL_PAD, panel.y + 32, bar_w)
        self._bar(surface, com_lbl, stats.demand_commercial, COLORS["commercial"], panel.x + PANEL_PAD, panel.y + 52, bar_w)
        self._bar(surface, ind_lbl, stats.demand_industrial, COLORS["industrial"], panel.x + PANEL_PAD, panel.y + 72, bar_w)
        # Mini sparklines (last 6 months per zone type) — drawn to the right of bars.
        if demand_history:
            hist6 = demand_history[-6:]
            spark_x = panel.x + PANEL_PAD + bar_w + 4
            for si, (col, di) in enumerate(((COLORS["residential"], 0), (COLORS["commercial"], 1), (COLORS["industrial"], 2))):
                vals = [h[di] for h in hist6]
                sy0 = panel.y + 30 + si * 20
                self._mini_sparkline(surface, spark_x, sy0, spark_w, 14, vals, col)
        return panel.bottom

    def _mini_sparkline(self, surface, sx, sy, w, h, vals, col) -> None:
        """Draws a tiny 1px-stroke line chart for a list of values."""
        if len(vals) < 2:
            return
        vmin, vmax = min(vals), max(vals)
        vrange = max(1, vmax - vmin)
        pts = [
            (sx + int(i / (len(vals) - 1) * w),
             sy + h - 1 - int((v - vmin) / vrange * (h - 2)))
            for i, v in enumerate(vals)
        ]
        pygame.draw.lines(surface, col, False, pts, 1)

    def draw_system_panel(self, surface: pygame.Surface, stats, x: int, y: int, width: int) -> int:
        """Draws the systems panel as a compact 2-column metric grid. Returns the bottom y."""
        panel = self._panel(surface, x, y, width, 108, accent_color=_ACCENT_SYSTEMS)
        self._draw_text(surface, "Systems", panel.x + PANEL_PAD, panel.y + 6, self.sidebar.font)

        # 2-column layout: left metrics / right metrics
        col_w  = (width - PANEL_PAD * 2 - 8) // 2
        left_x = panel.x + PANEL_PAD
        right_x = left_x + col_w + 8
        row_h  = 17

        power_col  = self._utility_color(stats.power_capacity, stats.power_usage, stats.unpowered_zones)
        water_col  = self._utility_color(stats.water_capacity, stats.water_usage, stats.unwatered_zones)
        fire_col   = COLORS["money_good"] if stats.fire_uncovered_zones == 0 and stats.average_fire_risk < HIGH_RISK_THRESHOLD else COLORS["money_bad"]
        police_col = COLORS["money_good"] if stats.police_uncovered_zones == 0 and stats.average_crime_risk < HIGH_RISK_THRESHOLD else COLORS["money_bad"]
        edu_col    = COLORS["money_good"] if stats.education_coverage_percent >= 70 else COLORS["muted_text"]
        health_col = COLORS["money_good"] if stats.health_coverage_percent >= 70 else COLORS["muted_text"]

        metrics_left = [
            (f"Power  {stats.power_satisfaction}%",  power_col),
            (f"Water  {stats.water_satisfaction}%",  water_col),
            (f"School {stats.education_coverage_percent}%", edu_col),
        ]
        metrics_right = [
            (f"Fire cov  {stats.fire_coverage_percent}%", fire_col),
            (f"Crime     {stats.average_crime_risk}%",    police_col),
            (f"Health    {stats.health_coverage_percent}%", health_col),
        ]

        dot_ox = 5   # dot x offset from column start
        txt_ox = 14  # text x offset from column start
        base_y = panel.y + 26
        for i, (label, col) in enumerate(metrics_left):
            ry = base_y + i * row_h
            self._draw_status_dot(surface, left_x + dot_ox, ry + 6, col)
            self._draw_text(surface, label, left_x + txt_ox, ry, self.sidebar.font_small, col)
        for i, (label, col) in enumerate(metrics_right):
            ry = base_y + i * row_h
            self._draw_status_dot(surface, right_x + dot_ox, ry + 6, col)
            self._draw_text(surface, label, right_x + txt_ox, ry, self.sidebar.font_small, col)

        # Service score bar at the bottom of the panel.
        self._bar(surface, "Svc", stats.service_score, COLORS["service"],
                  panel.x + PANEL_PAD, panel.y + 88, width - PANEL_PAD * 2)
        return panel.bottom

    def _draw_status_dot(self, surface: pygame.Surface, x: int, y: int, color: tuple) -> None:
        """Draws a small filled circle (status indicator) at the given centre position."""
        pygame.draw.circle(surface, color, (x, y), 4)
        pygame.draw.circle(surface, (max(0, color[0] - 40), max(0, color[1] - 40), max(0, color[2] - 40)), (x, y), 4, 1)

    def _tool_cost(self, tool: Tool) -> int:
        """Returns the per-tile placement cost for any tool (0 for inspect/bulldoze)."""
        if tool == Tool.ROAD:
            return ROAD_COST
        if tool == Tool.POWER_LINE:
            return POWER_LINE_COST
        if tool == Tool.WATER_PIPE:
            return WATER_PIPE_COST
        if tool in TOOL_TO_BUILDING:
            return BUILDING_COST.get(TOOL_TO_BUILDING[tool].value, 0)
        if tool in TOOL_TO_ZONE:
            zone, level = TOOL_TO_ZONE[tool]
            rec = TOOL_TO_RECREATION.get(tool)
            if zone.value == "park" and rec:
                return RECREATION_COST.get(rec.value, 150)
            return int(ZONE_COST.get(zone.value, 0) * ZONE_LEVEL_COST_MULTIPLIERS.get(level, 1.0))
        return 0

    def draw_tool_buttons(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        width: int,
        active_tool: Tool,
        active_menu: str,
        money: int = 999_999,
    ) -> int:
        """
        Draws a 2-column grid of tool buttons for the active menu tab.

        Tools are laid out two per row. Each button shows a colour swatch
        (matching the zone or infrastructure colour) and a hotkey prefix.
        Returns the bottom y of the panel.
        """
        tools = MENU_TOOLS[active_menu]
        rows = (len(tools) + 1) // 2
        row_h = 30
        panel = self._panel(surface, x, y, width, 32 + rows * row_h, accent_color=_ACCENT_TOOLS)
        self._draw_text(surface, active_menu, panel.x + PANEL_PAD, panel.y + 8, self.sidebar.font)
        if active_tool in tools:
            cost = self._tool_cost(active_tool)
            cost_str = f"${cost:,}/tile" if cost > 0 else ""
            active_label = fit_label(
                TOOL_SHORT_LABELS.get(active_tool, TOOL_LABELS[active_tool]),
                self.sidebar.font_small, width // 2 - (self.sidebar.font_small.size(cost_str)[0] + 8 if cost_str else 0)
            )
            active_text = self.sidebar.font_small.render(active_label, True, COLORS["muted_text"])
            surface.blit(active_text, (panel.right - PANEL_PAD - active_text.get_width() - (self.sidebar.font_small.size(cost_str)[0] + 6 if cost_str else 0), panel.y + 10))
            if cost_str:
                cost_surf = self.sidebar.font_small.render(cost_str, True, (170, 160, 110))
                surface.blit(cost_surf, (panel.right - PANEL_PAD - cost_surf.get_width(), panel.y + 10))
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
            # Red border on tools the player can't currently afford.
            cost = self._tool_cost(tool)
            if cost > 0 and money < cost and tool != active_tool:
                pygame.draw.rect(surface, (140, 52, 52), rect, width=1, border_radius=5)
        return panel.bottom

    # ── Tile inspection helpers ────────────────────────────────────────────────

    def _tile_status(self, tile, city_map: CityMap, x: int, y: int) -> tuple[str, tuple]:
        """Returns a (status_text, color) pair describing what is stopping or enabling growth."""
        if tile.has_road:
            load = tile.traffic_load
            if load > ROAD_TRAFFIC_CAPACITY:
                return f"Traffic: {load} (congested)", COLORS["money_bad"]
            elif load > 0:
                return f"Traffic: {load}", COLORS["muted_text"]
            return "Road — no traffic", COLORS["muted_text"]
        if tile.zone in (ZoneType.EMPTY, ZoneType.PARK):
            return "", COLORS["muted_text"]
        if tile.on_fire:
            return "On fire!", COLORS["money_bad"]
        if not city_map.has_adjacent_road(x, y):
            return "Needs road to grow", COLORS["money_bad"]
        if not tile.powered:
            return "Needs power to grow", COLORS["money_bad"]
        if not tile.watered:
            return "Needs water to grow", COLORS["money_bad"]
        if tile.zone_level >= 3 and tile.land_value < HIGHRISE_MIN_LAND_VALUE:
            return f"Highrise stalled (need val {HIGHRISE_MIN_LAND_VALUE:.2f})", COLORS["money_bad"]
        if tile.development >= 0.95:
            return "Fully developed", COLORS["money_good"]
        return "Growing...", COLORS["money_good"]

    def _tile_kind(self, tile) -> str:
        """Returns a human-readable label for the primary content of a tile."""
        if tile.building != BuildingType.NONE:
            return BUILDING_LABELS[tile.building]
        if tile.has_road:
            return "Road"
        if tile.has_power_line:
            return "Power Line"
        if tile.has_water_pipe:
            return "Water Pipe"
        if tile.zone == ZoneType.PARK:
            return RECREATION_LABELS.get(tile.recreation_type, "Park")
        if tile.zone != ZoneType.EMPTY:
            if tile.zone_level >= 3:
                prefix = "Highrise "
            elif tile.zone_level == 2:
                prefix = "Dense "
            else:
                prefix = ""
            return f"{prefix}{tile.zone.value.title()}"
        return "Empty"

    def _tool_button_label(self, tool: Tool, hotkey: str) -> str:
        """Builds the text shown on a tool button, e.g. 'R Road' or 'W Power Line'."""
        label = TOOL_SHORT_LABELS.get(tool, TOOL_LABELS[tool])
        return f"{hotkey} {label}".strip()

    # ── Low-level drawing primitives ───────────────────────────────────────────

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
        """Draws a muted label and a coloured value side by side (green=good, red=bad)."""
        self._draw_text(surface, label, x, y, self.sidebar.font_small, COLORS["muted_text"])
        color = COLORS["text"]
        if positive is True:
            color = COLORS["money_good"]
        elif positive is False:
            color = COLORS["money_bad"]
        value_x = x + 46
        fitted = fit_label(value, self.sidebar.font_small, max(16, width - 52))
        self._draw_text(surface, fitted, value_x, y, self.sidebar.font_small, color)

    def _utility_color(self, capacity: int, usage: int, uncovered_zones: int) -> tuple[int, int, int]:
        """Returns green if the utility has spare capacity and zero uncovered zones; red otherwise."""
        if capacity <= 0 or uncovered_zones > 0 or usage > capacity:
            return COLORS["money_bad"]
        return COLORS["money_good"]

    def _panel(self, surface: pygame.Surface, x: int, y: int, width: int, height: int,
               accent_color: tuple | None = None) -> pygame.Rect:
        """
        Draws a rounded dark rectangle with a subtle top highlight, a thin outer
        border, a separator groove below the title row, and an optional colored
        left-edge accent stripe. Returns the Rect.
        """
        rect = pygame.Rect(x, y, width, height)
        pygame.draw.rect(surface, COLORS["sidebar_panel"], rect, border_radius=6)
        # Outer border.
        pygame.draw.rect(surface, (36, 46, 58), rect, width=1, border_radius=6)
        # Top highlight.
        pygame.draw.line(surface, (42, 54, 68), (rect.x + 7, rect.y + 1), (rect.right - 7, rect.y + 1))
        # Separator groove under the title row.
        sep_y = rect.y + 24
        pygame.draw.line(surface, (18, 24, 32), (rect.x + 6, sep_y), (rect.right - 6, sep_y))
        pygame.draw.line(surface, (38, 48, 62), (rect.x + 6, sep_y + 1), (rect.right - 6, sep_y + 1))
        # Colored left-edge accent stripe.
        if accent_color:
            accent_rect = pygame.Rect(rect.x + 2, rect.y + 4, 3, rect.height - 8)
            pygame.draw.rect(surface, accent_color, accent_rect, border_radius=2)
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
        """
        Draws a labelled horizontal progress bar.

        value is 0-100 — the bar fills proportionally from left to right.
        The percentage is also printed on the right end of the bar.
        """
        label_surface = self.sidebar.font_small.render(label, True, COLORS["text"])
        surface.blit(label_surface, (x, y - 2))
        bar_x = x + 44
        bar_w = width - 78
        bg = pygame.Rect(bar_x, y + 2, bar_w, 11)
        fill_w = int(bar_w * max(0, min(100, value)) / 100)
        pygame.draw.rect(surface, (31, 36, 41), bg, border_radius=4)
        if fill_w > 0:
            pygame.draw.rect(surface, color, pygame.Rect(bar_x, y + 2, fill_w, 11), border_radius=4)
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
        """
        Draws a rounded button with optional active/disabled/swatch states.

        active=True  → highlighted background + blue left-edge accent bar
        disabled=True → greyed out, text dimmed
        swatch_color  → small colour diamond shown left of the label (tool buttons)
        align_left    → label is left-aligned (tool buttons); default is centred
        """
        color = COLORS["sidebar_panel_active"] if active else COLORS["sidebar_panel"]
        if disabled:
            color = (36, 40, 46)
        pygame.draw.rect(surface, color, rect, border_radius=5)
        # Bevel highlight (top/left lighter, bottom/right darker — inverted when pressed)
        if not disabled:
            hi = (min(255, color[0] + 18), min(255, color[1] + 18), min(255, color[2] + 22))
            sh = (max(0, color[0] - 14), max(0, color[1] - 14), max(0, color[2] - 14))
            if active:
                hi, sh = sh, hi
            pygame.draw.line(surface, hi, (rect.x + 5, rect.y + 1), (rect.right - 6, rect.y + 1))
            pygame.draw.line(surface, hi, (rect.x + 1, rect.y + 5), (rect.x + 1, rect.bottom - 6))
            pygame.draw.line(surface, sh, (rect.x + 5, rect.bottom - 1), (rect.right - 6, rect.bottom - 1))
            pygame.draw.line(surface, sh, (rect.right - 1, rect.y + 5), (rect.right - 1, rect.bottom - 6))
        border_color = (80, 100, 120) if active else (55, 66, 78)
        pygame.draw.rect(surface, border_color, rect, width=1, border_radius=5)
        # Blue accent bar on the left edge of the active button
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
        """Renders text at (x, y) using the given font and optional colour."""
        rendered = font.render(text, True, color or COLORS["text"])
        surface.blit(rendered, (x, y))

    def _draw_wrapped_text(self, surface: pygame.Surface, text: str, x: int, y: int, max_width: int,
                           color: tuple | None = None) -> None:
        """Word-wraps text into up to 2 lines, each spaced 17 px apart."""
        col = color if color is not None else COLORS["muted_text"]
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
            self._draw_text(surface, line_text, x, y + offset * 17, self.sidebar.font_small, col)
