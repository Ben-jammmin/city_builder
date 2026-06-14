from __future__ import annotations

from pathlib import Path

import pygame

from .camera import Camera
from .city_map import CityMap
from .models import (
    TOOL_HOTKEYS,
    TOOL_LABELS,
    TOOL_TO_BUILDING,
    CityStats,
    Tool,
    ZoneType,
    menu_for_tool,
)
from .renderer import Renderer
from .save_load import load_game, save_game
from .settings import (
    BUILDING_COST,
    BULLDOZE_COST,
    COLORS,
    FPS,
    MAP_HEIGHT,
    MAP_WIDTH,
    POWER_LINE_COST,
    ROAD_COST,
    SAVE_FILE,
    SIDEBAR_WIDTH,
    SIM_SECONDS_PER_MONTH,
    TILE_SIZE,
    WATER_PIPE_COST,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    ZONE_COST,
)
from .simulation import Simulation
from .ui import Sidebar


class Game:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Python City Builder Prototype")
        self.windowed_size = (WINDOW_WIDTH, WINDOW_HEIGHT)
        self.fullscreen = False
        self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.running = True

        self.map = CityMap(MAP_WIDTH, MAP_HEIGHT)
        self.stats = CityStats()
        self.simulation = Simulation(self.map, self.stats)
        viewport = pygame.Rect(0, 0, self.windowed_size[0] - SIDEBAR_WIDTH, self.windowed_size[1])
        self.camera = Camera(MAP_WIDTH * TILE_SIZE, MAP_HEIGHT * TILE_SIZE, viewport)
        self.renderer = Renderer()
        self.sidebar = Sidebar()
        self._resize_layout(*self.screen.get_size())

        self.active_tool = Tool.RESIDENTIAL
        self.active_menu = menu_for_tool(self.active_tool)
        self.save_path = Path(__file__).resolve().parent.parent / SAVE_FILE
        self.hover_tile: tuple[int, int] | None = None
        self.painting = False
        self.dragging_camera = False
        self.last_mouse_pos = (0, 0)
        self.painted_this_drag: set[tuple[int, int]] = set()

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000
            self._handle_events()
            self._handle_keyboard_camera(dt)
            self.simulation.update(dt, SIM_SECONDS_PER_MONTH)
            self._draw()
        pygame.quit()

    def _handle_events(self) -> None:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                self._handle_mouse_down(event)
            elif event.type == pygame.MOUSEBUTTONUP:
                self._handle_mouse_up(event)
            elif event.type == pygame.MOUSEMOTION:
                self._handle_mouse_motion(event)
            elif event.type == pygame.MOUSEWHEEL:
                self.camera.change_zoom(event.y * 0.08, pygame.mouse.get_pos())
            elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
                self._resize_window(event.w, event.h)

        self.hover_tile = self._mouse_tile(pygame.mouse.get_pos())

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        if event.key == pygame.K_ESCAPE:
            self.running = False
        elif event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT):
            self._toggle_fullscreen()
        elif event.key == pygame.K_SPACE:
            self.stats.paused = not self.stats.paused
        elif event.key in (pygame.K_EQUALS, pygame.K_PLUS):
            self.stats.change_tax_rate(1)
        elif event.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
            self.stats.change_tax_rate(-1)
        else:
            key_name = pygame.key.name(event.key)
            if key_name in TOOL_HOTKEYS:
                self.active_tool = TOOL_HOTKEYS[key_name]
                self.active_menu = menu_for_tool(self.active_tool)
        if event.key == pygame.K_F5:
            self._save_game()
        elif event.key == pygame.K_F9:
            self._load_game()

    def _toggle_fullscreen(self) -> None:
        if self.fullscreen:
            self._set_windowed()
        else:
            self._set_fullscreen()
        self._resize_layout(*self.screen.get_size())

    def _set_fullscreen(self) -> None:
        self.windowed_size = self.screen.get_size()
        try:
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN | pygame.SCALED)
        except pygame.error:
            self.screen = pygame.display.set_mode(self._desktop_size(), pygame.NOFRAME)
        self.fullscreen = True
        self.stats.add_message("Fullscreen enabled.")

    def _set_windowed(self) -> None:
        self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.fullscreen = False
        self.stats.add_message("Windowed mode enabled.")

    def _resize_window(self, width: int, height: int) -> None:
        self.windowed_size = (max(800, width), max(600, height))
        self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self._resize_layout(*self.screen.get_size())

    def _desktop_size(self) -> tuple[int, int]:
        try:
            return pygame.display.get_desktop_sizes()[0]
        except (AttributeError, IndexError):
            display_info = pygame.display.Info()
            return display_info.current_w, display_info.current_h

    def _resize_layout(self, width: int, height: int) -> None:
        map_width = max(240, width - SIDEBAR_WIDTH)
        self.camera.set_viewport(pygame.Rect(0, 0, map_width, height))
        self.sidebar.set_screen_size(width, height)

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
        self.last_mouse_pos = event.pos

        ui_action = self.sidebar.handle_click(event.pos)
        if ui_action:
            self._handle_ui_action(ui_action)
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
        if event.button in (1, 3):
            self.painting = False
            self.painted_this_drag.clear()
        elif event.button == 2:
            self.dragging_camera = False

    def _handle_mouse_motion(self, event: pygame.event.Event) -> None:
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
            self._save_game()
        elif kind == "load":
            self._load_game()

    def _handle_keyboard_camera(self, dt: float) -> None:
        keys = pygame.key.get_pressed()
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

    def _apply_tool_at_mouse(self, pos: tuple[int, int]) -> None:
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

        zone = {
            Tool.RESIDENTIAL: ZoneType.RESIDENTIAL,
            Tool.COMMERCIAL: ZoneType.COMMERCIAL,
            Tool.INDUSTRIAL: ZoneType.INDUSTRIAL,
        }[self.active_tool]
        self._place_zone(tile_pos, zone)

    def _bulldoze_at_mouse(self, pos: tuple[int, int]) -> None:
        tile_pos = self._mouse_tile(pos)
        if tile_pos is None or tile_pos in self.painted_this_drag:
            return
        self.painted_this_drag.add(tile_pos)
        self._bulldoze(tile_pos)

    def _place_zone(self, tile_pos: tuple[int, int], zone: ZoneType) -> None:
        cost = ZONE_COST[zone.value]
        if not self._can_afford(cost):
            return
        if self.map.place_zone(*tile_pos, zone):
            self.stats.money -= cost
            self.stats.add_message(f"Zoned {zone.value} for ${cost}.")

    def _place_road(self, tile_pos: tuple[int, int]) -> None:
        if not self._can_afford(ROAD_COST):
            return
        if self.map.place_road(*tile_pos):
            self.stats.money -= ROAD_COST
            self.stats.add_message(f"Built road for ${ROAD_COST}.")

    def _place_power_line(self, tile_pos: tuple[int, int]) -> None:
        if not self._can_afford(POWER_LINE_COST):
            return
        if self.map.place_power_line(*tile_pos):
            self.stats.money -= POWER_LINE_COST
            self.stats.add_message(f"Built power line for ${POWER_LINE_COST}.")

    def _place_water_pipe(self, tile_pos: tuple[int, int]) -> None:
        if not self._can_afford(WATER_PIPE_COST):
            return
        if self.map.place_water_pipe(*tile_pos):
            self.stats.money -= WATER_PIPE_COST
            self.stats.add_message(f"Built water pipe for ${WATER_PIPE_COST}.")

    def _place_building(self, tile_pos: tuple[int, int]) -> None:
        building = TOOL_TO_BUILDING[self.active_tool]
        cost = BUILDING_COST[building.value]
        if not self._can_afford(cost):
            return
        if self.map.place_building(*tile_pos, building):
            self.stats.money -= cost
            self.stats.add_message(f"Built {TOOL_LABELS[self.active_tool]} for ${cost}.")

    def _bulldoze(self, tile_pos: tuple[int, int]) -> None:
        if not self._can_afford(BULLDOZE_COST):
            return
        if self.map.bulldoze(*tile_pos):
            self.stats.money -= BULLDOZE_COST
            self.stats.add_message(f"Bulldozed tile for ${BULLDOZE_COST}.")

    def _save_game(self) -> None:
        save_game(self.map, self.stats, self.save_path)
        self.stats.add_message(f"Saved {self.save_path.name}.")

    def _load_game(self) -> None:
        if not self.save_path.exists():
            self.stats.add_message("No save file found yet.")
            return
        self.map, self.stats = load_game(self.save_path)
        self.simulation = Simulation(self.map, self.stats)
        self.stats.add_message(f"Loaded {self.save_path.name}.")

    def _can_afford(self, cost: int) -> bool:
        if self.stats.money < cost:
            self.stats.add_message(f"Not enough money for ${cost} action.")
            return False
        return True

    def _mouse_tile(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        tile_pos = self.camera.screen_to_tile(pos, TILE_SIZE)
        if tile_pos is None:
            return None
        if not self.map.in_bounds(*tile_pos):
            return None
        return tile_pos

    def _draw(self) -> None:
        self.screen.fill(COLORS["background"])
        self.renderer.draw_map(self.screen, self.map, self.camera, self.active_tool, self.hover_tile)
        self.sidebar.draw(
            self.screen,
            self.stats,
            self.map,
            self.active_tool,
            self.active_menu,
            self.fullscreen,
            self.hover_tile,
        )
        self._draw_top_hint()
        pygame.display.flip()

    def _draw_top_hint(self) -> None:
        font = pygame.font.SysFont("Segoe UI", 15)
        text = (
            f"{TOOL_LABELS[self.active_tool]} tool | WASD/Arrows pan | Wheel zoom | "
            "Left paint | Right bulldoze | F11/Alt+Enter fullscreen | F5 save | F9 load"
        )
        rendered = font.render(text, True, COLORS["text"])
        bg = pygame.Rect(12, 12, rendered.get_width() + 18, rendered.get_height() + 10)
        pygame.draw.rect(self.screen, (25, 30, 34), bg, border_radius=6)
        self.screen.blit(rendered, (bg.x + 9, bg.y + 5))
