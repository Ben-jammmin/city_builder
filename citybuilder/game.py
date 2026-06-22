"""
game.py — Main game loop, input handling, and top-level game logic.

Game.__init__  sets up pygame, creates the map, camera, renderer, sidebar, and
simulation, then loads or generates the city.

Game.run() is the main loop:
  1. tick the clock and collect dt (delta-time in seconds since last frame)
  2. _handle_events() — processes the pygame event queue
  3. _handle_keyboard_camera() — smooth WASD/arrow key scrolling
  4. simulation.update(dt) — monthly simulation tick when enough time has passed
  5. pedestrian_system.update() — move walking pedestrians
  6. _check_message_sounds() — play sound effects for new advisor messages
  7. _draw() — render map + sidebar + HUD then flip the display

SaveOverlay is a separate full-screen dimmed panel for picking save/load slots.
It has its own draw() and handle_click() so Game.run() can delegate to it.

Key design decisions
--------------------
- painting flag: held mouse button drags the active tool across multiple tiles,
  but painted_this_drag tracks which tiles were hit to avoid double-spending.
- dragging_camera: middle mouse button pans the camera smoothly.
- _refresh_city_status() calls simulation.refresh_systems() after every build
  action so the power/water/coverage stats are always up to date.
- Save slots are stored in saves/slot_N.json, N=1..5 (see save_load.py).
"""
from __future__ import annotations

import copy
import math
import pygame

from .camera import Camera
from .city_map import CityMap
from .models import (
    MENU_ORDER,
    RECREATION_LABELS,
    TOOL_HOTKEYS,
    TOOL_LABELS,
    TOOL_TO_BUILDING,
    TOOL_TO_RECREATION,
    TOOL_TO_ZONE,
    VIEW_LABELS,
    VIEW_ORDER,
    BuildingType,
    CityStats,
    RecreationType,
    TerrainType,
    Tool,
    ViewMode,
    ZoneType,
    menu_for_tool,
)
from .renderer import Renderer
from .save_load import load_game, most_recent_slot, save_game, slot_path
from .game_overlays import AnalyticsOverlay, BondOverlay, HelpOverlay, OrdinanceOverlay, SaveOverlay
from .menu_config import GameConfig
from .settings import (
    BOND_OPTIONS,
    ORDINANCES,
    BUILDING_COST,
    BULLDOZE_COST,
    COLORS,
    COMMAND_BAR_HEIGHT,
    FPS,
    POWER_LINE_COST,
    RECREATION_COST,
    ROAD_COST,
    SIM_SPEED_PRESETS,
    TERRAIN_CLEAR_COSTS,
    TILE_SIZE,
    WATER_PIPE_COST,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    HIGHRISE_MIN_DEVELOPMENT,
    HIGHRISE_MIN_LAND_VALUE,
    AUTOSAVE_INTERVAL_YEARS,
    LOW_MONEY_THRESHOLD,
    ONBOARDING_TIPS,
    ZONE_COST,
    ZONE_LEVEL_COST_MULTIPLIERS,
    ZONE_LEVEL_LABELS,
)
from .pedestrian import PedestrianSystem
from .simulation import Simulation
from .sounds import SoundManager
from .terrain import generate_terrain
from .ui import Sidebar


class Game:
    """Top-level game object — owns the map, camera, renderer, sidebar, and simulation."""

    def __init__(self, config: GameConfig | None = None) -> None:
        cfg = config if config is not None else GameConfig()

        pygame.init()
        pygame.display.set_caption("City Builder")
        self.windowed_size = (WINDOW_WIDTH, WINDOW_HEIGHT)
        self.fullscreen = False
        self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.quit_to_desktop = False   # True = close the app; False = back to menu

        self.save_overlay      = SaveOverlay()
        self.help_overlay      = HelpOverlay()
        self.bond_overlay      = BondOverlay()
        self.ordinance_overlay = OrdinanceOverlay()
        self.analytics_overlay = AnalyticsOverlay()
        # Undo stack: each entry is (money_before_drag, [(x, y, tile_snapshot), ...]).
        # Capped at 20 entries so memory stays bounded.
        self._undo_stack: list[tuple[int, list[tuple[int, int, object]]]] = []
        self._current_undo_group: list[tuple[int, int, object]] = []
        self._undo_money_before: int = 0
        # Find the speed preset closest to the one chosen in GameConfig.
        self._speed_index = min(
            range(len(SIM_SPEED_PRESETS)),
            key=lambda i: abs(SIM_SPEED_PRESETS[i][1] - cfg.sim_seconds_per_month),
        )
        self._sim_speed = SIM_SPEED_PRESETS[self._speed_index][1]

        # Load an existing save file or generate a fresh city.
        recent = most_recent_slot() if cfg.load_save else None
        if recent is not None:
            self.map, self.stats = load_game(slot_path(recent))
        else:
            self.map = CityMap(cfg.map_width, cfg.map_height)
            generate_terrain(self.map, seed=cfg.terrain_seed, style=cfg.terrain_style_key)
            self.stats = CityStats(money=cfg.starting_money)

        self.simulation = Simulation(self.map, self.stats)
        self.pedestrian_system = PedestrianSystem(max_count=50)
        # Viewport covers the full window except for the bottom command bar.
        viewport = pygame.Rect(0, 0, self.windowed_size[0], self.windowed_size[1] - COMMAND_BAR_HEIGHT)
        self.camera = Camera(self.map.width * TILE_SIZE, self.map.height * TILE_SIZE, viewport)
        self.renderer = Renderer()
        self.renderer.day_night_enabled = cfg.day_night_cycle
        self.sidebar = Sidebar()
        self._resize_layout(*self.screen.get_size())

        self.active_tool = Tool.RESIDENTIAL
        self.active_menu = menu_for_tool(self.active_tool)
        self.view_mode = ViewMode.NORMAL
        self.hover_tile: tuple[int, int] | None = None
        self.painting = False          # True while a mouse button is held over the map
        self.dragging_camera = False   # True while middle mouse button is held
        self.last_mouse_pos = (0, 0)
        # Track which tiles were already painted this drag to avoid double cost.
        self.painted_this_drag: set[tuple[int, int]] = set()
        self.sounds = SoundManager()
        self._last_sound_msg: str = self.stats.messages[-1] if self.stats.messages else ""
        self._hint_font = pygame.font.SysFont("Segoe UI", 15)
        self._alert_font = pygame.font.SysFont("Segoe UI", 28, bold=True)
        self._autosave_last_year: int = self.stats.year
        self._fill_start: tuple[int, int] | None = None   # tile where Shift+drag started
        self._fire_flash_until: int = 0   # pygame.time.get_ticks() deadline for fire flash
        self._toasts: list[dict] = []   # brief on-map notification bubbles

    def run(self) -> bool:
        """Run the game loop. Returns True if player quit to desktop, False to return to menu."""
        while self.running:
            dt = self.clock.tick(FPS) / 1000
            self._handle_events()
            self._handle_keyboard_camera(dt)
            self.simulation.update(dt, self._sim_speed)
            self._check_autosave()
            self.pedestrian_system.update(dt, self.map.width, self.map.height, self.stats.population, 0.002)
            self._check_message_sounds()
            self._draw()
        return self.quit_to_desktop

    # ── Event handling ─────────────────────────────────────────────────────────

    def _handle_events(self) -> None:
        """Drains the pygame event queue and dispatches each event to the appropriate handler."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                self.quit_to_desktop = True
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse_down(event)
            elif event.type == pygame.MOUSEBUTTONUP:
                self._handle_mouse_up(event)
            elif event.type == pygame.MOUSEMOTION:
                self._handle_mouse_motion(event)
            elif event.type == pygame.MOUSEWHEEL:
                mouse_pos = pygame.mouse.get_pos()
                if self.sidebar.contains(mouse_pos):
                    self.sidebar.handle_scroll(event.y)
                else:
                    self.camera.change_zoom(event.y * 0.08, mouse_pos)
            elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                self._resize_window(event.w, event.h)

        self.hover_tile = self._mouse_tile(pygame.mouse.get_pos())

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        """Handles keyboard shortcuts: Escape, F1/F5/F9, F11, Ctrl+Z, Space, Q/E, V, +/-, WASD, hotkeys."""
        if event.key == pygame.K_ESCAPE:
            if self._fill_start is not None:
                self._fill_start = None
            elif self.save_overlay.visible:
                self.save_overlay.close()
            elif self.help_overlay.visible:
                self.help_overlay.close()
            elif self.bond_overlay.visible:
                self.bond_overlay.close()
            elif self.ordinance_overlay.visible:
                self.ordinance_overlay.close()
            elif self.analytics_overlay.visible:
                self.analytics_overlay.close()
            else:
                self.running = False
        elif event.key == pygame.K_F1:
            if self.help_overlay.visible:
                self.help_overlay.close()
            else:
                self.help_overlay.open()
        elif event.key == pygame.K_z and (event.mod & pygame.KMOD_CTRL):
            self._undo()
        elif event.key == pygame.K_F5:
            self._open_save_overlay()
        elif event.key == pygame.K_F9:
            self._open_load_overlay()
        elif event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT):
            self._toggle_fullscreen()
        elif event.key == pygame.K_SPACE:
            self.stats.paused = not self.stats.paused
        elif event.key == pygame.K_LEFTBRACKET:
            self._cycle_speed(-1)
        elif event.key == pygame.K_RIGHTBRACKET:
            self._cycle_speed(1)
        elif event.key == pygame.K_v:
            direction = -1 if event.mod & pygame.KMOD_SHIFT else 1
            self._cycle_view_mode(direction)
        elif event.key in (pygame.K_EQUALS, pygame.K_PLUS):
            self.stats.change_tax_rate(1)
        elif event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
            self.stats.change_tax_rate(-1)
        elif event.key == pygame.K_q:
            self.camera.rotate_ccw()
        elif event.key == pygame.K_e:
            self.camera.rotate_cw()
        elif event.key == pygame.K_b:
            if self.bond_overlay.visible:
                self.bond_overlay.close()
            else:
                self.bond_overlay.open()
        elif event.key == pygame.K_o:
            if self.ordinance_overlay.visible:
                self.ordinance_overlay.close()
            else:
                self.ordinance_overlay.open()
        elif event.key == pygame.K_a and not (event.mod & pygame.KMOD_CTRL):
            if self.analytics_overlay.visible:
                self.analytics_overlay.close()
            else:
                self.analytics_overlay.open()
        elif event.key == pygame.K_HOME:
            self.camera._recenter()
        elif event.key == pygame.K_n:
            self.renderer.day_night_enabled = not self.renderer.day_night_enabled
            self.stats.add_message(
                "Night cycle on." if self.renderer.day_night_enabled else "Night cycle off."
            )
        elif event.key == pygame.K_TAB:
            idx = MENU_ORDER.index(self.active_menu) if self.active_menu in MENU_ORDER else 0
            self.active_menu = MENU_ORDER[(idx + 1) % len(MENU_ORDER)]
        else:
            key_name = pygame.key.name(event.key)
            if key_name in TOOL_HOTKEYS:
                self.active_tool = TOOL_HOTKEYS[key_name]
                self.active_menu = menu_for_tool(self.active_tool)

    # ── Speed and view-mode cycling ────────────────────────────────────────────

    def _cycle_speed(self, delta: int) -> None:
        """Moves the speed preset index by delta steps (wraps at the ends)."""
        self._set_speed_index(self._speed_index + delta)

    def _set_speed_index(self, idx: int) -> None:
        """Clamps idx to a valid preset and applies the new simulation speed."""
        self._speed_index = max(0, min(len(SIM_SPEED_PRESETS) - 1, idx))
        self._sim_speed = SIM_SPEED_PRESETS[self._speed_index][1]
        label = SIM_SPEED_PRESETS[self._speed_index][0]
        self.stats.add_message(f"Speed set to {label}.")

    def _cycle_view_mode(self, direction: int = 1) -> None:
        """Cycles through Normal/Power/Water/Fire/Police/Terrain views (press V)."""
        current_index = VIEW_ORDER.index(self.view_mode)
        self.view_mode = VIEW_ORDER[(current_index + direction) % len(VIEW_ORDER)]
        self.stats.add_message(f"{VIEW_LABELS[self.view_mode]} view.")

    # ── Fullscreen and window resize ───────────────────────────────────────────

    def _toggle_fullscreen(self) -> None:
        """Switches between fullscreen and windowed mode (F11 or Alt+Enter)."""
        if self.fullscreen:
            self._set_windowed()
        else:
            self._set_fullscreen()
        self._resize_layout(*self.screen.get_size())

    def _set_fullscreen(self) -> None:
        """Saves current window size then switches to fullscreen or borderless."""
        self.windowed_size = self.screen.get_size()
        try:
            # SCALED lets pygame upscale if the desktop resolution differs.
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.SCALED)
        except pygame.error:
            # Fallback: borderless window at desktop size.
            self.screen = pygame.display.set_mode(self._desktop_size(), pygame.NOFRAME)
        self.fullscreen = True
        self.stats.add_message("Fullscreen enabled.")

    def _set_windowed(self) -> None:
        """Restores the previously saved windowed size."""
        self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.fullscreen = False
        self.stats.add_message("Windowed mode enabled.")

    def _resize_window(self, width: int, height: int) -> None:
        """Handles VIDEORESIZE events; enforces a minimum 800×600 window."""
        self.windowed_size = (max(800, width), max(600, height))
        self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self._resize_layout(*self.screen.get_size())

    def _desktop_size(self) -> tuple[int, int]:
        """Returns the primary monitor's resolution for the fullscreen fallback."""
        try:
            return pygame.display.get_desktop_sizes()[0]
        except (AttributeError, IndexError):
            display_info = pygame.display.Info()
            return display_info.current_w, display_info.current_h

    def _resize_layout(self, width: int, height: int) -> None:
        """Updates sidebar and camera viewport whenever the window size changes."""
        self.sidebar.set_screen_size(width, height)
        # Map viewport takes all vertical space above the sidebar.
        map_height = max(240, height - self.sidebar.current_height())
        self.camera.set_viewport(pygame.Rect(0, 0, width, map_height))

    # ── Mouse input ────────────────────────────────────────────────────────────

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        """Handles MOUSEBUTTONDOWN: save overlay, help overlay, minimap click, sidebar, or map painting."""
        if self.help_overlay.visible:
            return
        if self.analytics_overlay.visible:
            if event.button == 1:
                result = self.analytics_overlay.handle_click(event.pos)
                if result == "close":
                    self.analytics_overlay.close()
            return
        if self.ordinance_overlay.visible:
            if event.button == 1:
                result = self.ordinance_overlay.handle_click(event.pos)
                if result == "close":
                    self.ordinance_overlay.close()
                elif isinstance(result, str):
                    self._toggle_ordinance(result)
            return
        if self.bond_overlay.visible:
            if event.button == 1:
                result = self.bond_overlay.handle_click(event.pos)
                if result == "cancel":
                    self.bond_overlay.close()
                elif isinstance(result, int):
                    self._issue_bond(result)
            return
        if self.save_overlay.visible:
            if event.button == 1:
                result = self.save_overlay.handle_click(event.pos)
                if result == "cancel":
                    self.save_overlay.close()
                elif isinstance(result, int):
                    if self.save_overlay.mode == "save":
                        self._do_save(result)
                    else:
                        self._do_load(result)
                    self.save_overlay.close()
            return

        self.last_mouse_pos = event.pos

        # Minimap click-to-jump
        if event.button == 1 and self.renderer.minimap_rect and self.renderer.minimap_rect.collidepoint(event.pos):
            self._jump_camera_minimap(event.pos)
            return

        ui_action = self.sidebar.handle_click(event.pos)
        if ui_action:
            self._handle_ui_action(ui_action)
            self.sounds.play("click")
            return

        if event.button == 1:
            if pygame.key.get_mods() & pygame.KMOD_SHIFT and self.active_tool not in (Tool.INSPECT, Tool.BULLDOZE):
                self._fill_start = self._mouse_tile(event.pos)
            else:
                self.painting = True
                self.painted_this_drag.clear()
                self._undo_money_before = self.stats.money
                self._current_undo_group = []
                self._apply_tool_at_mouse(event.pos)
        elif event.button == 2:
            self.dragging_camera = True
        elif event.button == 3:
            self.painting = True
            self.painted_this_drag.clear()
            self._undo_money_before = self.stats.money
            self._current_undo_group = []
            self._bulldoze_at_mouse(event.pos)

    def _handle_mouse_up(self, event: pygame.event.Event) -> None:
        """Ends the current painting or camera-drag drag when the mouse button is released."""
        if event.button == 1 and self._fill_start is not None:
            end_tile = self.hover_tile or self._fill_start
            self._apply_rectangle_fill(self._fill_start, end_tile)
            self._fill_start = None
            return
        if event.button in (1, 3):
            self.painting = False
            # Commit the undo group collected during this drag.
            if self._current_undo_group:
                self._undo_stack.append((self._undo_money_before, self._current_undo_group))
                self._current_undo_group = []
                # Cap stack to 20 entries so memory stays bounded.
                if len(self._undo_stack) > 20:
                    self._undo_stack.pop(0)
            self.painted_this_drag.clear()
        elif event.button == 2:
            self.dragging_camera = False

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        """Continues camera drag or paints more tiles while the mouse is held down."""
        if self.save_overlay.visible or self.help_overlay.visible:
            return
        if self.dragging_camera:
            dx = (self.last_mouse_pos[0] - event.pos[0]) / self.camera.zoom
            dy = (self.last_mouse_pos[1] - event.pos[1]) / self.camera.zoom
            self.camera.move(dx, dy)
        elif self.painting:
            if pygame.mouse.get_pressed(num_buttons=3)[0]:
                self._apply_tool_at_mouse(event.pos)
            elif pygame.mouse.get_pressed(num_buttons=3)[2]:
                self._bulldoze_at_mouse(event.pos)
        self.last_mouse_pos = event.pos

    def _handle_ui_action(self, action) -> None:
        """Dispatches a (kind, value) tuple returned by sidebar.handle_click()."""
        kind, value = action
        if kind == "tool":
            self.active_tool = value
            self.active_menu = menu_for_tool(value)
        elif kind == "menu":
            self.active_menu = value
        elif kind == "tax":
            self.stats.change_tax_rate(value)
        elif kind == "pause":
            self.stats.paused = not self.stats.paused
        elif kind == "fullscreen":
            self._toggle_fullscreen()
        elif kind == "save":
            self._open_save_overlay()
        elif kind == "load":
            self._open_load_overlay()
        elif kind == "speed":
            self._set_speed_index(value)
        elif kind == "toggle_menu":
            self.sidebar.minimized = not self.sidebar.minimized
            self._resize_layout(*self.screen.get_size())

    def _handle_keyboard_camera(self, dt: float) -> None:
        """Pans the camera smoothly with WASD / arrow keys. Speed scales with dt and zoom."""
        if self.save_overlay.visible or self.help_overlay.visible:
            return
        keys = pygame.key.get_pressed()
        # Divide by zoom so panning feels consistent regardless of zoom level.
        speed = 520 * dt / self.camera.zoom
        dx = 0.0
        dy = 0.0
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            dx -= speed
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            dx += speed
        if keys[pygame.K_w] or keys[pygame.K_UP]:
            dy -= speed
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            dy += speed
        if dx or dy:
            self.camera.move(dx, dy)

    # ── Tool placement ─────────────────────────────────────────────────────────

    def _apply_tool_at_mouse(self, pos: tuple[int, int]) -> None:
        """Applies the active tool to the tile under the mouse (skips already-painted tiles)."""
        tile_pos = self._mouse_tile(pos)
        if tile_pos is None or tile_pos in self.painted_this_drag:
            return
        self.painted_this_drag.add(tile_pos)
        self._apply_tool_at_tile(tile_pos)

    def _apply_tool_at_tile(self, tile_pos: tuple[int, int]) -> None:
        """Applies the active tool to the given tile position."""
        if self.active_tool == Tool.INSPECT:
            return
        if self.active_tool == Tool.BULLDOZE:
            self._bulldoze(tile_pos)
            return
        if self.active_tool == Tool.ROAD:
            self._place_road(tile_pos)
            return
        if self.active_tool == Tool.POWER_LINE:
            self._place_power_line(tile_pos)
            return
        if self.active_tool == Tool.WATER_PIPE:
            self._place_water_pipe(tile_pos)
            return
        if self.active_tool in TOOL_TO_BUILDING:
            self._place_building(tile_pos)
            return
        if self.active_tool in TOOL_TO_ZONE:
            zone, level = TOOL_TO_ZONE[self.active_tool]
            rec_type = TOOL_TO_RECREATION.get(self.active_tool)
            self._place_zone(tile_pos, zone, level, rec_type)

    def _bulldoze_at_mouse(self, pos: tuple[int, int]) -> None:
        tile_pos = self._mouse_tile(pos)
        if tile_pos is None or tile_pos in self.painted_this_drag:
            return
        self.painted_this_drag.add(tile_pos)
        self._bulldoze(tile_pos)

    def _place_zone(self, tile_pos: tuple[int, int], zone: ZoneType, level: int = 1, recreation_type: RecreationType | None = None) -> None:
        cost = self._zone_cost(zone, level, recreation_type)
        if not self._can_afford(cost):
            return
        x, y = tile_pos
        old_tile = copy.copy(self.map.get(x, y))
        if self.map.place_zone(*tile_pos, zone, level, recreation_type):
            self._current_undo_group.append((x, y, old_tile))
            self.stats.money -= cost
            self.sounds.play("build")
            upgrading = (old_tile.zone == zone and level > old_tile.zone_level)
            label = "Upgraded to dense " + self._zone_label(zone, 1, recreation_type) if upgrading else self._zone_label(zone, level, recreation_type)
            self.stats.add_message(f"Zoned {label} for ${cost}.")
            self._refresh_city_status()
        else:
            self._add_zone_blocked_message(tile_pos, zone, level, recreation_type)

    def _add_zone_blocked_message(self, tile_pos: tuple[int, int], zone: ZoneType, level: int = 1, recreation_type: RecreationType | None = None) -> None:
        x, y = tile_pos
        tile = self.map.get(x, y)
        if self.map.is_water(x, y):
            self.stats.add_message("Cannot build on water.")
        elif tile.terrain != TerrainType.GRASS:
            self.stats.add_message("Terrain not clear - bulldoze first.")
        elif tile.zone == zone and tile.zone_level == level and (
            zone != ZoneType.PARK or tile.recreation_type == recreation_type
        ):
            self.stats.add_message("Zone already exists here.")
        elif tile.building != BuildingType.NONE or tile.has_road or tile.has_power_line or tile.has_water_pipe:
            self.stats.add_message("Tile already occupied.")
        elif level >= 3:
            if tile.zone != zone or tile.zone_level < 2:
                self.stats.add_message("Highrise requires an existing dense zone here.")
            elif tile.development < HIGHRISE_MIN_DEVELOPMENT:
                need_pct = int(HIGHRISE_MIN_DEVELOPMENT * 100)
                cur_pct  = int(tile.development * 100)
                self.stats.add_message(f"Highrise needs {need_pct}% development (currently {cur_pct}%).")
            elif tile.land_value < HIGHRISE_MIN_LAND_VALUE:
                self.stats.add_message(f"Highrise needs land value ≥ {HIGHRISE_MIN_LAND_VALUE:.2f} (currently {tile.land_value:.2f}).")
            else:
                self.stats.add_message("Cannot place highrise here.")
        else:
            self.stats.add_message("Cannot place zone.")

    def _zone_cost(self, zone: ZoneType, level: int, recreation_type: RecreationType | None = None) -> int:
        """Returns the cost to place this zone type. Dense zones use a cost multiplier."""
        if zone == ZoneType.PARK and recreation_type is not None:
            return RECREATION_COST.get(recreation_type.value, 150)
        multiplier = ZONE_LEVEL_COST_MULTIPLIERS.get(level, 1.0)
        return int(ZONE_COST[zone.value] * multiplier)

    def _zone_label(self, zone: ZoneType, level: int, recreation_type: RecreationType | None = None) -> str:
        if zone == ZoneType.PARK and recreation_type is not None:
            return RECREATION_LABELS.get(recreation_type, recreation_type.value.replace("_", " "))
        label = zone.value.replace("_", " ")
        if level <= 1:
            return label
        return f"{ZONE_LEVEL_LABELS.get(level, f'Level {level}')} {label}".lower()

    def _place_road(self, tile_pos: tuple[int, int]) -> None:
        if not self._can_afford(ROAD_COST):
            return
        x, y = tile_pos
        old_tile = copy.copy(self.map.get(x, y))
        if self.map.place_road(*tile_pos):
            self._current_undo_group.append((x, y, old_tile))
            self.stats.money -= ROAD_COST
            self.sounds.play("build")
            self.stats.add_message(f"Built road for ${ROAD_COST}.")
            self._refresh_city_status()
        else:
            x, y = tile_pos
            if self.map.is_water(x, y):
                self.stats.add_message("Cannot build road on water.")
            elif self.map.get(x, y).has_road:
                self.stats.add_message("Road already exists.")
            elif self.map.get(x, y).zone != ZoneType.EMPTY or self.map.get(x, y).building != BuildingType.NONE:
                self.stats.add_message("Tile occupied by zone/building.")
            else:
                self.stats.add_message("Cannot place road.")

    def _place_power_line(self, tile_pos: tuple[int, int]) -> None:
        if not self._can_afford(POWER_LINE_COST):
            return
        x, y = tile_pos
        old_tile = copy.copy(self.map.get(x, y))
        if self.map.place_power_line(*tile_pos):
            self._current_undo_group.append((x, y, old_tile))
            self.stats.money -= POWER_LINE_COST
            self.stats.add_message(f"Built power line for ${POWER_LINE_COST}.")
            self._refresh_city_status()
        else:
            x, y = tile_pos
            if self.map.is_water(x, y):
                self.stats.add_message("Cannot build on water.")
            elif self.map.get(x, y).has_power_line:
                self.stats.add_message("Power line already exists.")
            elif self.map.get(x, y).zone != ZoneType.EMPTY or self.map.get(x, y).building != BuildingType.NONE:
                self.stats.add_message("Tile occupied by zone/building.")
            else:
                self.stats.add_message("Cannot place power line.")

    def _place_water_pipe(self, tile_pos: tuple[int, int]) -> None:
        if not self._can_afford(WATER_PIPE_COST):
            return
        x, y = tile_pos
        old_tile = copy.copy(self.map.get(x, y))
        if self.map.place_water_pipe(*tile_pos):
            self._current_undo_group.append((x, y, old_tile))
            self.stats.money -= WATER_PIPE_COST
            self.stats.add_message(f"Built water pipe for ${WATER_PIPE_COST}.")
            self._refresh_city_status()
        else:
            x, y = tile_pos
            if self.map.is_water(x, y):
                self.stats.add_message("Cannot build on water.")
            elif self.map.get(x, y).has_water_pipe:
                self.stats.add_message("Water pipe already exists.")
            elif self.map.get(x, y).zone != ZoneType.EMPTY or self.map.get(x, y).building != BuildingType.NONE:
                self.stats.add_message("Tile occupied by zone/building.")
            else:
                self.stats.add_message("Cannot place water pipe.")

    def _place_building(self, tile_pos: tuple[int, int]) -> None:
        building = TOOL_TO_BUILDING[self.active_tool]
        cost = BUILDING_COST[building.value]
        if not self._can_afford(cost):
            return
        x, y = tile_pos
        old_tile = copy.copy(self.map.get(x, y))
        if self.map.place_building(*tile_pos, building):
            self._current_undo_group.append((x, y, old_tile))
            self.stats.money -= cost
            self.sounds.play("build")
            self.stats.add_message(f"Built {TOOL_LABELS[self.active_tool]} for ${cost}.")
            self._refresh_city_status()
        else:
            x, y = tile_pos
            tile = self.map.get(x, y)
            if self.map.is_water(x, y):
                self.stats.add_message("Cannot build on water.")
            elif tile.terrain != TerrainType.GRASS:
                self.stats.add_message("Terrain not clear - bulldoze first.")
            elif not tile.is_empty:
                self.stats.add_message("Tile already occupied.")
            else:
                self.stats.add_message("Cannot place building.")

    def _bulldoze(self, tile_pos: tuple[int, int]) -> None:
        """
        Clears the tile at tile_pos, deducting the appropriate cost.

        First pass removes man-made structures (zone, road, utilities, building).
        Second pass (if the tile was already empty) clears natural terrain obstacles
        (water, forest, hill) which cost more to remove than built structures.
        """
        x, y = tile_pos
        tile = self.map.get(x, y)
        cost = BULLDOZE_COST
        item_name = "tile"
        # Natural terrain costs more to clear than a simple built structure.
        if tile.is_empty and tile.terrain != TerrainType.GRASS:
            if tile.terrain == TerrainType.WATER:
                cost = TERRAIN_CLEAR_COSTS["water"]
                item_name = "water"
            elif tile.terrain == TerrainType.FOREST:
                cost = TERRAIN_CLEAR_COSTS["forest"]
                item_name = "forest"
            elif tile.terrain == TerrainType.HILL:
                cost = TERRAIN_CLEAR_COSTS["hill"]
                item_name = "hill"
        
        if not self._can_afford(cost):
            return
        old_tile = copy.copy(tile)
        if self.map.bulldoze(*tile_pos):
            self._current_undo_group.append((x, y, old_tile))
            self.stats.money -= cost
            self.sounds.play("bulldoze")
            self.stats.add_message(f"Cleared {item_name} for ${cost}.")
            self._refresh_city_status()

    # ── Save / load ────────────────────────────────────────────────────────────

    def _open_save_overlay(self) -> None:
        """Opens the slot selection overlay in save mode."""
        self.save_overlay.open("save")

    def _open_load_overlay(self) -> None:
        """Opens the slot selection overlay in load mode."""
        self.save_overlay.open("load")

    def _do_save(self, slot: int) -> None:
        """Copies active fire timers back onto tiles, then serialises the game to disk."""
        for (fx, fy), burn_time in self.simulation._fires.items():
            self.map.get(fx, fy).fire_burn_time = burn_time
        save_game(self.map, self.stats, slot_path(slot))
        self.stats.add_message(f"Saved to slot {slot}.")

    def _do_load(self, slot: int) -> None:
        """Loads a save file from disk and hot-swaps the running game state."""
        p = slot_path(slot)
        if not p.exists():
            self.stats.add_message(f"Slot {slot} is empty.")
            return
        try:
            city_map, stats = load_game(p)
        except Exception:
            self.stats.add_message(f"Slot {slot} save data is corrupt and could not be loaded.")
            return
        self.map, self.stats = city_map, stats
        self.simulation = Simulation(self.map, self.stats)
        # Re-register any tiles that were on fire when the game was saved.
        for x, y, tile in self.map.iter_tiles():
            if tile.on_fire:
                self.simulation._fires[(x, y)] = tile.fire_burn_time
        self.pedestrian_system.clear()
        self._undo_stack.clear()
        self._current_undo_group = []
        # Recalculate camera pixel extents for the newly loaded map size.
        hw = self.camera.tile_w // 2
        self.camera.map_width  = self.map.width
        self.camera.map_height = self.map.height
        self.camera.map_pixel_width  = (self.map.width + self.map.height) * hw + self.camera.tile_w
        self.camera.map_pixel_height = (self.map.width + self.map.height) * (self.camera.tile_h // 2) + self.camera.tile_h * 4
        self.camera._recenter()
        self._refresh_city_status()
        self.stats.add_message(f"Loaded slot {slot}.")

    # ── Utility helpers ────────────────────────────────────────────────────────

    def _issue_bond(self, option_index: int) -> None:
        """Issues a municipal bond by index from BOND_OPTIONS and closes the overlay."""
        opt = BOND_OPTIONS[option_index]
        self.stats.issue_bond(option_index)
        self.stats.add_city_message(
            f"Issued ${opt['amount']:,} bond. "
            f"${opt['monthly_payment']:,}/mo for {opt['months']} months "
            f"(+${opt['monthly_payment'] * opt['months'] - opt['amount']:,} interest)."
        )
        self.bond_overlay.close()
        self._add_toast(
            f"Bond issued: +${opt['amount']:,} cash",
            color=(220, 190, 60),
            duration_ms=4000,
        )

    def _toggle_ordinance(self, ord_id: str) -> None:
        """Enacts or repeals a city ordinance by id."""
        ord_def = next((o for o in ORDINANCES if o["id"] == ord_id), None)
        if ord_def is None:
            return
        if ord_id in self.stats.active_ordinances:
            self.stats.active_ordinances.remove(ord_id)
            self.stats.add_city_message(f"Policy repealed: {ord_def['name']}.")
            self._add_toast(f"Repealed: {ord_def['name']}", color=(200, 110, 60), duration_ms=3500)
        else:
            self.stats.active_ordinances.append(ord_id)
            self.stats.add_city_message(
                f"Policy enacted: {ord_def['name']} costs ${ord_def['monthly_cost']:,}/mo."
            )
            self._add_toast(f"Enacted: {ord_def['name']}", color=(80, 210, 120), duration_ms=3500)

    def _can_afford(self, cost: int) -> bool:
        """Returns True if the player has enough money; shows a message and returns False if not."""
        if self.stats.money < cost:
            self.stats.add_message(f"Not enough money for ${cost} action.")
            return False
        return True

    def _refresh_city_status(self) -> None:
        """Re-runs the BFS utility/coverage sweep so stats are immediately up to date."""
        self.simulation.refresh_systems()
        self.pedestrian_system.update_road_tiles(self.map)

    def _undo(self) -> None:
        """Restores the last painting drag — tiles and money are rolled back."""
        if not self._undo_stack:
            self.stats.add_message("Nothing to undo.")
            return
        money_before, snapshots = self._undo_stack.pop()
        self.stats.money = money_before
        for x, y, old_tile in snapshots:
            self.map.tiles[x][y] = old_tile
        self._refresh_city_status()
        self.stats.add_message("Action undone.")

    def _preview_cost(self) -> int:
        """Returns the cost of placing the active tool on one tile (0 for inspect/bulldoze)."""
        if self.active_tool == Tool.ROAD:
            return ROAD_COST
        if self.active_tool == Tool.POWER_LINE:
            return POWER_LINE_COST
        if self.active_tool == Tool.WATER_PIPE:
            return WATER_PIPE_COST
        if self.active_tool in TOOL_TO_BUILDING:
            return BUILDING_COST[TOOL_TO_BUILDING[self.active_tool].value]
        if self.active_tool in TOOL_TO_ZONE:
            zone, level = TOOL_TO_ZONE[self.active_tool]
            rec = TOOL_TO_RECREATION.get(self.active_tool)
            return self._zone_cost(zone, level, rec)
        return 0

    def _check_message_sounds(self) -> None:
        """Plays a sound effect when the latest advisor message matches a known keyword."""
        if not self.stats.messages:
            return
        latest = self.stats.messages[-1]
        if latest == self._last_sound_msg:
            return   # same message as before — don't replay the sound
        self._last_sound_msg = latest
        ml = latest.lower()
        if "fire outbreak" in ml:
            self.sounds.play("fire")
            self.stats.paused = True
            self._fire_flash_until = pygame.time.get_ticks() + 3500
        elif "milestone" in ml:
            self.sounds.play("milestone")
            self._add_toast(latest, color=(225, 205, 70), duration_ms=6000)
        elif "crime incident" in ml:
            self.sounds.play("crime")
        elif "★" in latest:
            color = COLORS["money_bad"] if any(w in ml for w in ("recession","drought","fine","scandal","wave","closure")) else COLORS["money_good"]
            self._add_toast(latest[:72], color=color, duration_ms=5000)
        elif "autosaved" in ml:
            self._add_toast(latest, color=(115, 140, 165), duration_ms=2000)

    def _add_toast(self, text: str, color: tuple = (235, 239, 242), duration_ms: int = 3500) -> None:
        """Queues a brief notification bubble on the map area."""
        self._toasts.append({"text": text, "color": color, "expire": pygame.time.get_ticks() + duration_ms})
        if len(self._toasts) > 4:
            self._toasts = self._toasts[-4:]

    def _draw_toasts(self) -> None:
        """Draws fading notification bubbles near the top-right of the map viewport."""
        now = pygame.time.get_ticks()
        self._toasts = [t for t in self._toasts if t["expire"] > now]
        vp = self.camera.viewport
        ty = vp.y + 52   # below the minimap area
        font = self._hint_font
        for toast in self._toasts:
            remaining = toast["expire"] - now
            alpha = min(255, int(255 * remaining / 600)) if remaining < 600 else 255
            color = toast["color"]
            rendered = font.render(toast["text"], True, color)
            bw = min(rendered.get_width() + 24, vp.width - 20)
            bx = vp.right - bw - 10
            bh = rendered.get_height() + 12
            bg = pygame.Surface((bw, bh), pygame.SRCALPHA)
            bg.fill((14, 18, 24, min(210, alpha)))
            pygame.draw.rect(bg, (*color, min(160, alpha)), bg.get_rect(), 1, border_radius=6)
            self.screen.blit(bg, (bx, ty))
            # Clip the text to the bubble width.
            text_surf = pygame.Surface((bw - 24, rendered.get_height()), pygame.SRCALPHA)
            text_surf.blit(rendered, (0, 0))
            text_surf.set_alpha(alpha)
            self.screen.blit(text_surf, (bx + 12, ty + 6))
            ty += bh + 6

    def _draw_pause_indicator(self) -> None:
        """Shows a subtle 'PAUSED' watermark in the top-left of the map viewport when paused."""
        if not self.stats.paused:
            return
        vp = self.camera.viewport
        t = pygame.time.get_ticks()
        alpha = int(140 + 70 * abs(math.sin(t / 800.0)))
        rendered = self._hint_font.render("⏸  PAUSED  —  Press Space to resume", True, (200, 210, 230))
        sw = self.screen.get_width()
        rx = (sw - rendered.get_width()) // 2
        ry = vp.bottom - 44
        bg = pygame.Surface((rendered.get_width() + 22, rendered.get_height() + 10), pygame.SRCALPHA)
        bg.fill((12, 16, 22, min(200, alpha)))
        pygame.draw.rect(bg, (80, 95, 120, min(160, alpha)), bg.get_rect(), 1, border_radius=6)
        self.screen.blit(bg, (rx - 11, ry - 5))
        rendered.set_alpha(alpha)
        self.screen.blit(rendered, (rx, ry))

    def _draw_fill_preview(self) -> None:
        """Draws a green diamond highlight over every tile in the Shift+drag rectangle."""
        if self._fill_start is None or self.hover_tile is None:
            return
        x0, y0 = self._fill_start
        x1, y1 = self.hover_tile
        min_x, max_x = min(x0, x1), max(x0, x1)
        min_y, max_y = min(y0, y1), max(y0, y1)
        tw = max(4, int(self.camera.tile_w * self.camera.zoom))
        th = max(2, int(self.camera.tile_h * self.camera.zoom))
        hw, hh = tw // 2, th // 2
        old_clip = self.screen.get_clip()
        self.screen.set_clip(self.camera.viewport)
        fill_surf = pygame.Surface((tw, th + 1), pygame.SRCALPHA)
        pygame.draw.polygon(fill_surf, (90, 220, 130, 70), [(hw, 0), (tw, hh), (hw, th), (0, hh)])
        for rx in range(min_x, max_x + 1):
            for ry in range(min_y, max_y + 1):
                if self.map.in_bounds(rx, ry):
                    cx, cy = self.camera.world_to_screen(rx, ry)
                    self.screen.blit(fill_surf, (cx - hw, cy))
                    diam = [(cx, cy), (cx + hw, cy + hh), (cx, cy + th), (cx - hw, cy + hh)]
                    pygame.draw.polygon(self.screen, (110, 240, 150), diam, 2)
        self.screen.set_clip(old_clip)

    def _draw_onboarding_tip(self) -> None:
        """Shows a contextual tip bubble during the first in-game year."""
        tip = next(
            (msg for yr, mo, msg in ONBOARDING_TIPS if yr == self.stats.year and mo == self.stats.month),
            None,
        )
        if tip is None:
            return
        rendered = self._hint_font.render(tip, True, (230, 210, 110))
        sw = self.screen.get_width()
        bar_h = self.sidebar.current_height()
        tip_y = self.screen.get_height() - bar_h - 46
        bg = pygame.Rect(
            sw // 2 - rendered.get_width() // 2 - 14, tip_y - 6,
            rendered.get_width() + 28, 32,
        )
        pygame.draw.rect(self.screen, (28, 34, 38), bg, border_radius=8)
        pygame.draw.rect(self.screen, (180, 155, 45), bg, 1, border_radius=8)
        self.screen.blit(rendered, (bg.x + 14, bg.y + 8))

    def _draw_fire_flash(self) -> None:
        """Draws a red alert overlay for 3.5 seconds after a fire outbreak."""
        remaining = self._fire_flash_until - pygame.time.get_ticks()
        if remaining <= 0:
            return
        frac = min(1.0, remaining / 3500.0)
        alpha = int(50 * frac)
        w, h = self.screen.get_size()
        flash_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        flash_surf.fill((220, 60, 20, alpha))
        self.screen.blit(flash_surf, (0, 0))
        rendered = self._alert_font.render("FIRE OUTBREAK — Simulation Paused", True, (255, 120, 40))
        rx = (w - rendered.get_width()) // 2
        ry = max(60, self.camera.viewport.height // 2 - 30)
        bg = pygame.Rect(rx - 18, ry - 12, rendered.get_width() + 36, rendered.get_height() + 24)
        pygame.draw.rect(self.screen, (40, 18, 10), bg, border_radius=10)
        pygame.draw.rect(self.screen, (220, 80, 30), bg, 2, border_radius=10)
        self.screen.blit(rendered, (rx, ry))

    def _draw_low_money_warning(self) -> None:
        """Draws a pulsing red border around the screen when the city is in debt."""
        if self.stats.money >= 0:
            return
        t = pygame.time.get_ticks()
        alpha = int(55 + 45 * abs(math.sin(t / 500.0)))
        w, h = self.screen.get_size()
        border_surf = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(border_surf, (220, 40, 40, alpha), border_surf.get_rect(), 16)
        self.screen.blit(border_surf, (0, 0))

    def _jump_camera_minimap(self, pos: tuple[int, int]) -> None:
        """
        Pans the camera so the tile clicked on the minimap appears in the
        centre of the main viewport.

        Converts the click's pixel fraction across the minimap to a tile
        coordinate, then applies the isometric projection to get the world-pixel
        position and sets the camera scroll accordingly.
        """
        mr = self.renderer.minimap_rect
        if mr is None:
            return
        mm_w = min(self.map.width, 128)
        mm_h = min(self.map.height, 96)
        mm_x = mr.x + 4   # inner area starts 4 px inside the minimap panel border
        mm_y = mr.y + 4
        # frac_x / frac_y = click position as a 0-1 fraction across the minimap.
        frac_x = max(0.0, min(1.0, (pos[0] - mm_x) / mm_w))
        frac_y = max(0.0, min(1.0, (pos[1] - mm_y) / mm_h))
        tx = int(frac_x * self.map.width)
        ty = int(frac_y * self.map.height)
        tx = max(0, min(self.map.width - 1, tx))
        ty = max(0, min(self.map.height - 1, ty))
        # Convert the target tile to an isometric world-pixel position and
        # scroll so that position lands at the centre of the viewport.
        rtx, rty = self.camera._apply_rotation(tx, ty)
        hw = self.camera.tile_w // 2
        hh = self.camera.tile_h // 2
        wx = (rtx - rty) * hw + self.camera._origin_x()
        wy = (rtx + rty) * hh
        vp = self.camera.viewport
        self.camera.x = wx - vp.width / (2 * self.camera.zoom)
        self.camera.y = wy - vp.height / (2 * self.camera.zoom)
        self.camera.clamp()

    def _mouse_tile(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        """Converts a screen pixel to a map tile, or returns None if out of bounds."""
        tile_pos = self.camera.screen_to_tile(pos)
        if tile_pos is None:
            return None
        if not self.map.in_bounds(*tile_pos):
            return None
        return tile_pos

    def _check_autosave(self) -> None:
        """Saves to slot 0 (autosave) every AUTOSAVE_INTERVAL_YEARS in-game years."""
        if self.stats.year - self._autosave_last_year >= AUTOSAVE_INTERVAL_YEARS:
            self._autosave_last_year = self.stats.year
            try:
                save_game(self.map, self.stats, slot_path(0))
                self.stats.add_message(f"Autosaved (Year {self.stats.year}).")
            except Exception:
                pass

    def _apply_rectangle_fill(self, start: tuple[int, int], end: tuple[int, int]) -> None:
        """Applies the active tool to every tile in the bounding box from start to end."""
        x0, y0 = start
        x1, y1 = end
        min_x, max_x = min(x0, x1), max(x0, x1)
        min_y, max_y = min(y0, y1), max(y0, y1)
        self._undo_money_before = self.stats.money
        self._current_undo_group = []
        self.painted_this_drag.clear()
        for rx in range(min_x, max_x + 1):
            for ry in range(min_y, max_y + 1):
                if self.map.in_bounds(rx, ry) and (rx, ry) not in self.painted_this_drag:
                    self.painted_this_drag.add((rx, ry))
                    self._apply_tool_at_tile((rx, ry))
        if self._current_undo_group:
            self._undo_stack.append((self._undo_money_before, self._current_undo_group))
            self._current_undo_group = []
            if len(self._undo_stack) > 20:
                self._undo_stack.pop(0)
        self.painted_this_drag.clear()

    # ── Drawing ────────────────────────────────────────────────────────────────

    def _draw(self) -> None:
        """Renders one complete frame: map, sidebar, HUD hint bar, save overlay."""
        self.sidebar.speed_index = self._speed_index
        self.screen.fill(COLORS["background"])
        self.renderer.draw_map(
            self.screen,
            self.map,
            self.camera,
            self.active_tool,
            self.view_mode,
            self.hover_tile,
            self.pedestrian_system,
        )
        self._draw_fill_preview()
        self._draw_toasts()
        self._draw_pause_indicator()
        self.sidebar.draw(
            self.screen,
            self.stats,
            self.map,
            self.active_tool,
            self.active_menu,
            self.view_mode,
            self.fullscreen,
            self.hover_tile,
        )
        self._draw_top_hint()
        self._draw_onboarding_tip()
        self._draw_fire_flash()
        if self.analytics_overlay.visible:
            self.analytics_overlay.draw(self.screen, self.stats)
        if self.ordinance_overlay.visible:
            self.ordinance_overlay.draw(self.screen, self.stats)
        if self.bond_overlay.visible:
            self.bond_overlay.draw(self.screen, self.stats)
        if self.save_overlay.visible:
            self.save_overlay.draw(self.screen)
        if self.help_overlay.visible:
            self.help_overlay.draw(self.screen)
        self._draw_low_money_warning()
        pygame.display.flip()

    def _draw_top_hint(self) -> None:
        """Draws a compact HUD bar at the top: active tool, cost, view, speed, date."""
        font = self._hint_font
        speed_label = SIM_SPEED_PRESETS[self._speed_index][0]
        paused_str = "⏸ PAUSED" if self.stats.paused else speed_label

        # Active tool + cost (only when hovering over the map).
        tool_str = TOOL_LABELS[self.active_tool]
        cost_str = ""
        if self.active_tool not in (Tool.INSPECT, Tool.BULLDOZE):
            cost = self._preview_cost()
            if cost > 0:
                can_afford = self.stats.money >= cost
                cost_str = f"  ${cost:,}/tile" + (" ✗" if not can_afford else "")

        fill_str = "  [Shift+drag — filling rect]" if self._fill_start is not None else ""

        tile_str = ""
        if self.hover_tile is not None:
            hx, hy = self.hover_tile
            tile_str = f"({hx},{hy})"

        parts = [
            tool_str + cost_str + fill_str,
            f"{VIEW_LABELS[self.view_mode]} view",
            f"Y{self.stats.year} M{self.stats.month}",
            paused_str,
        ]
        if tile_str:
            parts.append(tile_str)
        parts.append("F1 help")
        text = "  ·  ".join(parts)

        if self.stats.money < 0:
            text_color = COLORS["money_bad"]
        elif cost_str.endswith("✗"):
            text_color = (230, 130, 50)
        elif self.stats.money < LOW_MONEY_THRESHOLD:
            text_color = (230, 190, 70)
        else:
            text_color = COLORS["text"]

        rendered = font.render(text, True, text_color)
        bg = pygame.Rect(12, 12, rendered.get_width() + 18, rendered.get_height() + 10)
        pygame.draw.rect(self.screen, (20, 25, 30), bg, border_radius=6)
        pygame.draw.rect(self.screen, (45, 55, 70), bg, 1, border_radius=6)
        self.screen.blit(rendered, (bg.x + 9, bg.y + 5))
