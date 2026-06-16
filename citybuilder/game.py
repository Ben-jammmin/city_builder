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

import pygame

from .camera import Camera
from .city_map import CityMap
from .models import (
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
from .save_load import list_saves, load_game, most_recent_slot, save_game, slot_path
from .menu_config import GameConfig
from .settings import (
    BUILDING_COST,
    BULLDOZE_COST,
    COLORS,
    COMMAND_BAR_HEIGHT,
    FPS,
    NUM_SAVE_SLOTS,
    POWER_LINE_COST,
    RECREATION_COST,
    ROAD_COST,
    SIM_SPEED_PRESETS,
    TERRAIN_CLEAR_COSTS,
    TILE_SIZE,
    WATER_PIPE_COST,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    ZONE_COST,
    ZONE_LEVEL_COST_MULTIPLIERS,
    ZONE_LEVEL_LABELS,
)
from .pedestrian import PedestrianSystem
from .simulation import Simulation
from .sounds import SoundManager
from .terrain import generate_terrain
from .ui import Sidebar


class SaveOverlay:
    """
    Full-screen dimmed panel for choosing a save or load slot.

    The overlay blocks all other input while visible. Clicking a slot number
    triggers a save or load; clicking Cancel or pressing Escape dismisses it.
    """

    def __init__(self) -> None:
        self.visible = False
        self.mode = "save"   # "save" or "load"
        self._slot_rects: list[pygame.Rect] = []
        self._cancel_rect = pygame.Rect(0, 0, 0, 0)
        # _saves holds slot metadata dicts (or None for empty slots) read from disk.
        self._saves: list[dict | None] = [None] * NUM_SAVE_SLOTS
        self._font: pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

    def open(self, mode: str) -> None:
        """Shows the overlay and refreshes the slot metadata from disk."""
        self.visible = True
        self.mode = mode
        self._saves = list_saves()

    def close(self) -> None:
        """Hides the overlay without taking any action."""
        self.visible = False

    def _ensure_fonts(self) -> None:
        """Initialises fonts lazily (pygame display must be up before SysFont works)."""
        if self._font is None:
            self._font = pygame.font.SysFont("Segoe UI", 18, bold=True)
            self._font_sm = pygame.font.SysFont("Segoe UI", 15)

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        W, H = surface.get_size()

        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        surface.blit(dim, (0, 0))

        panel_w = min(520, W - 40)
        slot_h = 54
        panel_h = 60 + NUM_SAVE_SLOTS * (slot_h + 8) + 52
        panel = pygame.Rect(W // 2 - panel_w // 2, H // 2 - panel_h // 2, panel_w, panel_h)
        pygame.draw.rect(surface, (18, 24, 32), panel, border_radius=10)
        pygame.draw.rect(surface, (55, 90, 130), panel, width=2, border_radius=10)

        title = "Save Game — Choose a Slot" if self.mode == "save" else "Load Game — Choose a Slot"
        t = self._font.render(title, True, (235, 239, 242))
        surface.blit(t, (panel.centerx - t.get_width() // 2, panel.y + 16))

        mouse = pygame.mouse.get_pos()
        self._slot_rects = []
        for i, meta in enumerate(self._saves):
            slot_rect = pygame.Rect(panel.x + 18, panel.y + 52 + i * (slot_h + 8), panel_w - 36, slot_h)
            self._slot_rects.append(slot_rect)

            is_empty = meta is None
            clickable = not is_empty or self.mode == "save"
            hovered = clickable and slot_rect.collidepoint(mouse)

            if is_empty:
                bg = (34, 46, 60) if hovered else (24, 34, 44)
                border = (40, 58, 78)
                label_col = (90, 110, 130)
            else:
                bg = (40, 56, 76) if hovered else (28, 38, 52)
                border = (90, 130, 180) if hovered else (55, 82, 112)
                label_col = (130, 155, 180)

            pygame.draw.rect(surface, bg, slot_rect, border_radius=6)
            pygame.draw.rect(surface, border, slot_rect, width=1, border_radius=6)

            sl = self._font_sm.render(f"Slot {i + 1}", True, label_col)
            surface.blit(sl, (slot_rect.x + 14, slot_rect.centery - sl.get_height() // 2))

            if is_empty:
                et = self._font_sm.render("— Empty —", True, (70, 88, 105))
                surface.blit(et, (slot_rect.x + 88, slot_rect.centery - et.get_height() // 2))
            else:
                pt = self._font_sm.render(
                    f"Pop {meta['population']:,}  ${meta['money']:,}", True, (220, 232, 240))
                surface.blit(pt, (slot_rect.x + 88, slot_rect.y + 10))
                dt = self._font_sm.render(
                    f"Year {meta['year']}  Month {meta['month']}  {meta['map_size']} map",
                    True, (140, 162, 182))
                surface.blit(dt, (slot_rect.x + 88, slot_rect.y + 30))

        cancel_w = 130
        self._cancel_rect = pygame.Rect(panel.centerx - cancel_w // 2, panel.bottom - 44, cancel_w, 30)
        c_hov = self._cancel_rect.collidepoint(mouse)
        pygame.draw.rect(surface, (48, 60, 76) if c_hov else (36, 46, 58), self._cancel_rect, border_radius=5)
        pygame.draw.rect(surface, (60, 76, 96), self._cancel_rect, width=1, border_radius=5)
        ct = self._font_sm.render("Cancel  [Esc]", True, (200, 212, 224))
        surface.blit(ct, (self._cancel_rect.centerx - ct.get_width() // 2,
                          self._cancel_rect.centery - ct.get_height() // 2))

    def handle_click(self, pos: tuple[int, int]) -> int | str | None:
        """Processes a left-click on the overlay. Returns slot number (1-5), 'cancel', or None."""
        if self._cancel_rect.collidepoint(pos):
            return "cancel"
        for i, rect in enumerate(self._slot_rects):
            if rect.collidepoint(pos):
                if self.mode == "load" and self._saves[i] is None:
                    return None
                return i + 1
        return None


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

        self.save_overlay = SaveOverlay()
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

    def run(self) -> bool:
        """Run the game loop. Returns True if player quit to desktop, False to return to menu."""
        while self.running:
            dt = self.clock.tick(FPS) / 1000
            self._handle_events()
            self._handle_keyboard_camera(dt)
            self.simulation.update(dt, self._sim_speed)
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
        """Handles keyboard shortcuts: Escape, F5/F9, F11, Space, Q/E, V, +/-, WASD, hotkeys."""
        if event.key == pygame.K_ESCAPE:
            if self.save_overlay.visible:
                self.save_overlay.close()
            else:
                self.running = False
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
        """Handles MOUSEBUTTONDOWN: save overlay, minimap click, sidebar, or map painting."""
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
            self.painting = True
            self.painted_this_drag.clear()
            self._apply_tool_at_mouse(event.pos)
        elif event.button == 2:
            self.dragging_camera = True
        elif event.button == 3:
            self.painting = True
            self.painted_this_drag.clear()
            self._bulldoze_at_mouse(event.pos)

    def _handle_mouse_up(self, event: pygame.event.Event) -> None:
        """Ends the current painting or camera-drag drag when the mouse button is released."""
        if event.button in (1, 3):
            self.painting = False
            self.painted_this_drag.clear()
        elif event.button == 2:
            self.dragging_camera = False

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
        """Continues camera drag or paints more tiles while the mouse is held down."""
        if self.save_overlay.visible:
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
        if self.save_overlay.visible:
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
        if self.map.place_zone(*tile_pos, zone, level, recreation_type):
            self.stats.money -= cost
            self.sounds.play("build")
            self.stats.add_message(f"Zoned {self._zone_label(zone, level, recreation_type)} for ${cost}.")
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
        if self.map.place_road(*tile_pos):
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
        if self.map.place_power_line(*tile_pos):
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
        if self.map.place_water_pipe(*tile_pos):
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
        if self.map.place_building(*tile_pos, building):
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
        if self.map.bulldoze(*tile_pos):
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

    def _can_afford(self, cost: int) -> bool:
        """Returns True if the player has enough money; shows a message and returns False if not."""
        if self.stats.money < cost:
            self.stats.add_message(f"Not enough money for ${cost} action.")
            return False
        return True

    def _refresh_city_status(self) -> None:
        """Re-runs the BFS utility/coverage sweep so stats are immediately up to date."""
        self.simulation.refresh_systems()

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
        elif "milestone" in ml:
            self.sounds.play("milestone")
        elif "crime incident" in ml:
            self.sounds.play("crime")

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
        if self.save_overlay.visible:
            self.save_overlay.draw(self.screen)
        pygame.display.flip()

    def _draw_top_hint(self) -> None:
        """Draws the thin toolbar at the top of the screen showing active tool, view, and hotkeys."""
        font = self._hint_font
        speed_label = SIM_SPEED_PRESETS[self._speed_index][0]
        text = (
            f"{TOOL_LABELS[self.active_tool]} tool | {VIEW_LABELS[self.view_mode]} view | "
            f"Speed: {speed_label} [ / ] | V view | Q/E rotate | WASD pan | Scroll zoom | F5 save | F9 load | Esc"
        )
        rendered = font.render(text, True, COLORS["text"])
        bg = pygame.Rect(12, 12, rendered.get_width() + 18, rendered.get_height() + 10)
        pygame.draw.rect(self.screen, (25, 30, 34), bg, border_radius=6)
        self.screen.blit(rendered, (bg.x + 9, bg.y + 5))
