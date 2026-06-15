"""Main game loop — handles input, runs the simulation, and draws every frame."""
from __future__ import annotations

from pathlib import Path

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
from .pedestrian import PedestrianSystem
from .renderer import Renderer
from .save_load import load_game, save_game
from .menu_config import GameConfig
from .settings import (
    BUILDING_COST,
    BULLDOZE_COST,
    COLORS,
    COMMAND_BAR_HEIGHT,
    FPS,
    PEDESTRIAN_MAX_COUNT,
    PEDESTRIAN_SPAWN_RATE,
    POWER_LINE_COST,
    RECREATION_COST,
    ROAD_COST,
    SAVE_FILE,
    TERRAIN_CLEAR_COSTS,
    TILE_SIZE,
    WATER_PIPE_COST,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
    ZONE_COST,
    ZONE_LEVEL_COST_MULTIPLIERS,
    ZONE_LEVEL_LABELS,
)
from .simulation import Simulation
from .sounds import SoundManager
from .terrain import generate_terrain
from .ui import Sidebar


class Game:
    def __init__(self, config: GameConfig | None = None) -> None:
        cfg = config if config is not None else GameConfig()

        pygame.init()
        pygame.display.set_caption("City Builder")
        self.windowed_size = (WINDOW_WIDTH, WINDOW_HEIGHT)
        self.fullscreen = False
        self.screen = pygame.display.set_mode(self.windowed_size, pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.quit_to_desktop = False

        self.save_path = Path(__file__).resolve().parent.parent / SAVE_FILE
        self._sim_speed = cfg.sim_seconds_per_month

        if cfg.load_save and self.save_path.exists():
            self.map, self.stats = load_game(self.save_path)
        else:
            self.map = CityMap(cfg.map_width, cfg.map_height)
            generate_terrain(self.map, seed=cfg.terrain_seed, style=cfg.terrain_style_key)
            self.stats = CityStats(money=cfg.starting_money)

        self.simulation = Simulation(self.map, self.stats)
        self.pedestrian_system = PedestrianSystem(max_count=PEDESTRIAN_MAX_COUNT)
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
        self.painting = False
        self.dragging_camera = False
        self.last_mouse_pos = (0, 0)
        self.painted_this_drag: set[tuple[int, int]] = set()
        self.sounds = SoundManager()
        self._prev_msg_count = len(self.stats.messages)
        self._hint_font = pygame.font.SysFont("Segoe UI", 15)

    def run(self) -> bool:
        """Run the game loop. Returns True if player quit to desktop, False to return to menu."""
        while self.running:
            dt = self.clock.tick(FPS) / 1000
            self._handle_events()
            self._handle_keyboard_camera(dt)
            self.simulation.update(dt, self._sim_speed)
            self.pedestrian_system.update(
                dt, self.map.width, self.map.height,
                self.stats.population, PEDESTRIAN_SPAWN_RATE,
            )
            self._check_message_sounds()
            self._draw()
        return self.quit_to_desktop

    def _handle_events(self) -> None:
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
        if event.key == pygame.K_ESCAPE:
            self.running = False
        elif event.key == pygame.K_F5:
            self._save_game()
        elif event.key == pygame.K_F9:
            self._load_game()
        elif event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT):
            self._toggle_fullscreen()
        elif event.key == pygame.K_SPACE:
            self.stats.paused = not self.stats.paused
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

    def _cycle_view_mode(self, direction: int = 1) -> None:
        current_index = VIEW_ORDER.index(self.view_mode)
        self.view_mode = VIEW_ORDER[(current_index + direction) % len(VIEW_ORDER)]
        self.stats.add_message(f"{VIEW_LABELS[self.view_mode]} view.")

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
        self.sidebar.set_screen_size(width, height)
        map_height = max(240, height - self.sidebar.current_height())
        self.camera.set_viewport(pygame.Rect(0, 0, width, map_height))

    def _handle_mouse_down(self, event: pygame.event.Event) -> None:
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
        elif kind == "toggle_menu":
            self.sidebar.minimized = not self.sidebar.minimized
            self._resize_layout(*self.screen.get_size())

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
        elif not self.map.has_adjacent_road(x, y):
            self.stats.add_message("Zone needs adjacent road.")
        else:
            self.stats.add_message("Cannot place zone.")

    def _zone_cost(self, zone: ZoneType, level: int, recreation_type: RecreationType | None = None) -> int:
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
        x, y = tile_pos
        tile = self.map.get(x, y)
        cost = BULLDOZE_COST
        item_name = "tile"
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

    def _save_game(self) -> None:
        save_game(self.map, self.stats, self.save_path)
        self.stats.add_message(f"Saved {self.save_path.name}.")

    def _load_game(self) -> None:
        if not self.save_path.exists():
            self.stats.add_message("No save file found yet.")
            return
        self.map, self.stats = load_game(self.save_path)
        self.simulation = Simulation(self.map, self.stats)
        self._refresh_city_status()
        self.stats.add_message(f"Loaded {self.save_path.name}.")

    def _can_afford(self, cost: int) -> bool:
        if self.stats.money < cost:
            self.stats.add_message(f"Not enough money for ${cost} action.")
            return False
        return True

    def _refresh_city_status(self) -> None:
        simulation = getattr(self, "simulation", None)
        if simulation is not None:
            simulation.refresh_systems()

    def _check_message_sounds(self) -> None:
        current = len(self.stats.messages)
        if current > self._prev_msg_count:
            for msg in self.stats.messages[self._prev_msg_count:]:
                ml = msg.lower()
                if "fire outbreak" in ml:
                    self.sounds.play("fire")
                elif "milestone" in ml:
                    self.sounds.play("milestone")
                elif "crime incident" in ml:
                    self.sounds.play("crime")
        self._prev_msg_count = current

    def _jump_camera_minimap(self, pos: tuple[int, int]) -> None:
        mr = self.renderer.minimap_rect
        if mr is None:
            return
        mm_w = min(self.map.width, 128)
        mm_h = min(self.map.height, 96)
        mm_x = mr.x + 4
        mm_y = mr.y + 4
        frac_x = max(0.0, min(1.0, (pos[0] - mm_x) / mm_w))
        frac_y = max(0.0, min(1.0, (pos[1] - mm_y) / mm_h))
        tx = int(frac_x * self.map.width)
        ty = int(frac_y * self.map.height)
        tx = max(0, min(self.map.width - 1, tx))
        ty = max(0, min(self.map.height - 1, ty))
        vp = self.camera.viewport
        cur = self.camera.screen_to_tile((vp.centerx, vp.centery), TILE_SIZE)
        if cur:
            dx = (tx - cur[0]) * TILE_SIZE
            dy = (ty - cur[1]) * TILE_SIZE
            self.camera.move(dx, dy)

    def _mouse_tile(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        tile_pos = self.camera.screen_to_tile(pos, TILE_SIZE)
        if tile_pos is None:
            return None
        if not self.map.in_bounds(*tile_pos):
            return None
        return tile_pos

    def _draw(self) -> None:
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
        pygame.display.flip()

    def _draw_top_hint(self) -> None:
        font = self._hint_font
        text = (
            f"{TOOL_LABELS[self.active_tool]} tool | {VIEW_LABELS[self.view_mode]} view | "
            "V view | Q/E rotate | WASD pan | Scroll zoom | F5 save | F9 load | Esc menu"
        )
        rendered = font.render(text, True, COLORS["text"])
        bg = pygame.Rect(12, 12, rendered.get_width() + 18, rendered.get_height() + 10)
        pygame.draw.rect(self.screen, (25, 30, 34), bg, border_radius=6)
        self.screen.blit(rendered, (bg.x + 9, bg.y + 5))
