from __future__ import annotations

import pygame

from .camera import Camera
from .city_map import CityMap
from .models import TOOL_TO_BUILDING, BuildingType, TerrainType, Tool, ViewMode, ZoneType
from .pedestrian import PedestrianSystem
from .settings import COLORS, TILE_SIZE


TERRAIN_COLOR_KEYS = {
    TerrainType.WATER: "terrain_water",
    TerrainType.FOREST: "terrain_forest",
    TerrainType.HILL: "terrain_hill",
}

BUILDING_COLOR_KEYS = {
    BuildingType.POWER_PLANT: "power",
    BuildingType.WATER_TOWER: "water",
    BuildingType.POLICE: "police",
    BuildingType.FIRE: "fire",
    BuildingType.SCHOOL: "school",
    BuildingType.TRAIN_STATION: "train_station",
    BuildingType.AIRPORT: "airport",
}

BUILDING_MARKER_LABELS = {
    BuildingType.POWER_PLANT: "P",
    BuildingType.WATER_TOWER: "W",
    BuildingType.POLICE: "Po",
    BuildingType.FIRE: "F",
    BuildingType.SCHOOL: "S",
    BuildingType.TRAIN_STATION: "T",
    BuildingType.AIRPORT: "A",
}

VIEW_MAIN_BUILDINGS = {
    ViewMode.POWER: BuildingType.POWER_PLANT,
    ViewMode.WATER: BuildingType.WATER_TOWER,
    ViewMode.FIRE: BuildingType.FIRE,
    ViewMode.POLICE: BuildingType.POLICE,
}


class Renderer:
    def __init__(self) -> None:
        self.small_font = pygame.font.SysFont("Segoe UI", 13)

    def draw_map(
        self,
        surface: pygame.Surface,
        city_map: CityMap,
        camera: Camera,
        active_tool: Tool,
        view_mode: ViewMode,
        hover_tile: tuple[int, int] | None,
        pedestrian_system: PedestrianSystem | None = None,
    ) -> None:
        pygame.draw.rect(surface, COLORS["background"], camera.viewport)
        old_clip = surface.get_clip()
        surface.set_clip(camera.viewport)

        start_x, start_y, end_x, end_y = camera.visible_tile_bounds(TILE_SIZE, city_map.width, city_map.height)
        tile_px = max(2, int(TILE_SIZE * camera.zoom))

        for x in range(start_x, end_x):
            for y in range(start_y, end_y):
                tile = city_map.get(x, y)
                screen_x, screen_y = camera.world_to_screen(x, y, TILE_SIZE)
                rect = pygame.Rect(screen_x, screen_y, tile_px + 1, tile_px + 1)
                self._draw_tile(surface, rect, city_map, tile, x, y, camera.zoom, view_mode)

        if hover_tile and city_map.in_bounds(*hover_tile):
            self._draw_hover(surface, city_map, camera, active_tool, hover_tile, tile_px)

        # Draw pedestrians if provided
        if pedestrian_system is not None and view_mode == ViewMode.NORMAL:
            self._draw_pedestrians(surface, camera, pedestrian_system)

        pygame.draw.rect(surface, (20, 24, 28), camera.viewport, width=2)
        surface.set_clip(old_clip)

    def _draw_tile(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        city_map: CityMap,
        tile,
        x: int,
        y: int,
        zoom: float,
        view_mode: ViewMode,
    ) -> None:
        self._draw_terrain_base(surface, rect, tile, x, y)

        if view_mode != ViewMode.NORMAL:
            self._draw_view_tile(surface, rect, city_map, tile, x, y, view_mode)
            grid_color = COLORS["grid_light"] if zoom >= 1.15 else COLORS["grid"]
            pygame.draw.rect(surface, grid_color, rect, width=1)
            return

        if tile.has_road:
            self._draw_road(surface, rect, city_map.road_connections(x, y))
        elif tile.building != BuildingType.NONE:
            self._draw_service_building(surface, rect, tile)
        elif tile.zone != ZoneType.EMPTY:
            pygame.draw.rect(surface, COLORS[tile.zone.value], rect)
            pygame.draw.rect(surface, COLORS["zone_border"], rect, width=1)
            if tile.development > 0.08:
                self._draw_building(surface, rect, tile)
            self._draw_zone_status(surface, rect, tile)

        self._draw_utilities(surface, rect, city_map, tile, x, y)

        grid_color = COLORS["grid_light"] if zoom >= 1.15 else COLORS["grid"]
        pygame.draw.rect(surface, grid_color, rect, width=1)

    def _draw_view_tile(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        city_map: CityMap,
        tile,
        x: int,
        y: int,
        view_mode: ViewMode,
    ) -> None:
        if view_mode == ViewMode.TERRAIN:
            self._draw_terrain_base(surface, rect, tile, x, y)
            if tile.zone != ZoneType.EMPTY:
                self._draw_context_zone(surface, rect, tile)
        else:
            self._draw_system_view_base(surface, rect, tile)

        if tile.has_road:
            self._draw_context_road(surface, rect, city_map.road_connections(x, y))

        if view_mode == ViewMode.POWER:
            self._draw_power_view(surface, rect, city_map, tile, x, y)
        elif view_mode == ViewMode.WATER:
            self._draw_water_view(surface, rect, city_map, tile, x, y)
        elif view_mode == ViewMode.FIRE:
            self._draw_fire_view(surface, rect, tile)
        elif view_mode == ViewMode.POLICE:
            self._draw_police_view(surface, rect, tile)

        self._draw_context_building_marker(surface, rect, tile, view_mode)

    def _draw_terrain_base(self, surface: pygame.Surface, rect: pygame.Rect, tile, x: int, y: int) -> None:
        if tile.terrain == TerrainType.GRASS:
            color = COLORS["empty"] if (x + y) % 2 == 0 else COLORS["empty_alt"]
        else:
            color = COLORS[TERRAIN_COLOR_KEYS[tile.terrain]]
        pygame.draw.rect(surface, color, rect)

        if rect.width < 18:
            return
        if tile.terrain == TerrainType.WATER:
            self._draw_water_detail(surface, rect)
        elif tile.terrain == TerrainType.FOREST:
            self._draw_forest_detail(surface, rect)
        elif tile.terrain == TerrainType.HILL:
            self._draw_hill_detail(surface, rect)

    def _draw_system_view_base(self, surface: pygame.Surface, rect: pygame.Rect, tile) -> None:
        color = (54, 62, 66)
        if tile.terrain == TerrainType.WATER:
            color = (41, 70, 84)
        elif tile.terrain == TerrainType.FOREST:
            color = (45, 61, 50)
        elif tile.terrain == TerrainType.HILL:
            color = (66, 66, 61)
        pygame.draw.rect(surface, color, rect)

    def _draw_water_detail(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        line_width = max(1, rect.width // 18)
        outline_width = max(1, rect.width // 20)
        pygame.draw.rect(surface, (36, 87, 119), rect, width=outline_width)
        for index, offset in enumerate((-rect.height // 7, rect.height // 8)):
            y = rect.centery + offset
            start_x = rect.left + 5 + index * 3
            middle_x = rect.centerx
            end_x = rect.right - 5
            pygame.draw.line(surface, (102, 169, 198), (start_x, y), (middle_x - 2, y + 1), line_width)
            pygame.draw.line(surface, (102, 169, 198), (middle_x + 2, y + 1), (end_x, y), line_width)

    def _draw_forest_detail(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        radius = max(2, rect.width // 8)
        pygame.draw.circle(surface, (34, 77, 46), (rect.centerx, rect.centery - radius), radius)
        pygame.draw.rect(
            surface,
            (76, 69, 47),
            pygame.Rect(rect.centerx - 1, rect.centery, 3, max(4, rect.height // 5)),
        )

    def _draw_hill_detail(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        line_width = max(1, rect.width // 16)
        points = [
            (rect.left + rect.width // 5, rect.bottom - rect.height // 3),
            (rect.centerx, rect.top + rect.height // 4),
            (rect.right - rect.width // 5, rect.bottom - rect.height // 3),
        ]
        pygame.draw.lines(surface, (152, 153, 132), False, points, line_width)

    def _draw_power_view(self, surface: pygame.Surface, rect: pygame.Rect, city_map: CityMap, tile, x: int, y: int) -> None:
        if tile.zone != ZoneType.EMPTY:
            color = (92, 82, 50) if tile.powered else (100, 55, 55)
            pygame.draw.rect(surface, color, rect)
        if tile.building == BuildingType.POWER_PLANT:
            self._draw_service_building(surface, rect, tile)
        if tile.has_power_line:
            self._draw_power_line(surface, rect, city_map.power_connections(x, y))

    def _draw_water_view(self, surface: pygame.Surface, rect: pygame.Rect, city_map: CityMap, tile, x: int, y: int) -> None:
        if tile.zone != ZoneType.EMPTY:
            color = (45, 78, 94) if tile.watered else (94, 58, 58)
            pygame.draw.rect(surface, color, rect)
        if tile.building == BuildingType.WATER_TOWER:
            self._draw_service_building(surface, rect, tile)
        if tile.has_water_pipe:
            self._draw_water_pipe(surface, rect, city_map.water_connections(x, y))

    def _draw_fire_view(self, surface: pygame.Surface, rect: pygame.Rect, tile) -> None:
        if tile.zone != ZoneType.EMPTY:
            color = self._risk_color(tile.fire_risk, covered=tile.fire_coverage)
            pygame.draw.rect(surface, color, rect)
        if tile.building == BuildingType.FIRE:
            self._draw_service_building(surface, rect, tile)

    def _draw_police_view(self, surface: pygame.Surface, rect: pygame.Rect, tile) -> None:
        if tile.zone != ZoneType.EMPTY:
            color = self._risk_color(tile.crime_risk, covered=tile.police_coverage)
            pygame.draw.rect(surface, color, rect)
        if tile.building == BuildingType.POLICE:
            self._draw_service_building(surface, rect, tile)

    def _risk_color(self, risk: int, covered: bool) -> tuple[int, int, int]:
        if risk >= 70:
            return (142, 57, 53)
        if risk >= 40:
            return (142, 111, 58)
        if covered:
            return (62, 105, 76)
        return (83, 84, 72)

    def _draw_road(self, surface: pygame.Surface, rect: pygame.Rect, connections: dict[str, bool]) -> None:
        road_width = max(6, int(rect.width * 0.48))
        half_width = road_width // 2
        center_x = rect.centerx
        center_y = rect.centery

        center_rect = pygame.Rect(center_x - half_width, center_y - half_width, road_width, road_width)
        pygame.draw.rect(surface, COLORS["road"], center_rect)

        arms = {
            "north": pygame.Rect(center_x - half_width, rect.top, road_width, center_y - rect.top),
            "east": pygame.Rect(center_x, center_y - half_width, rect.right - center_x, road_width),
            "south": pygame.Rect(center_x - half_width, center_y, road_width, rect.bottom - center_y),
            "west": pygame.Rect(rect.left, center_y - half_width, center_x - rect.left, road_width),
        }
        for direction, connected in connections.items():
            if connected:
                pygame.draw.rect(surface, COLORS["road"], arms[direction])

        self._draw_road_markings(surface, rect, connections)

    def _draw_road_markings(self, surface: pygame.Surface, rect: pygame.Rect, connections: dict[str, bool]) -> None:
        if rect.width < 18 or rect.height < 18:
            return
        line_width = max(1, rect.width // 18)
        center = (rect.centerx, rect.centery)
        margin = max(4, rect.width // 7)
        if connections["north"]:
            pygame.draw.line(surface, COLORS["road_line"], center, (rect.centerx, rect.top + margin), line_width)
        if connections["east"]:
            pygame.draw.line(surface, COLORS["road_line"], center, (rect.right - margin, rect.centery), line_width)
        if connections["south"]:
            pygame.draw.line(surface, COLORS["road_line"], center, (rect.centerx, rect.bottom - margin), line_width)
        if connections["west"]:
            pygame.draw.line(surface, COLORS["road_line"], center, (rect.left + margin, rect.centery), line_width)

    def _draw_context_road(self, surface: pygame.Surface, rect: pygame.Rect, connections: dict[str, bool]) -> None:
        road_width = max(3, int(rect.width * 0.22))
        half_width = road_width // 2
        color = (38, 43, 47)
        center_x = rect.centerx
        center_y = rect.centery

        center_rect = pygame.Rect(center_x - half_width, center_y - half_width, road_width, road_width)
        pygame.draw.rect(surface, color, center_rect)

        arms = {
            "north": pygame.Rect(center_x - half_width, rect.top, road_width, center_y - rect.top),
            "east": pygame.Rect(center_x, center_y - half_width, rect.right - center_x, road_width),
            "south": pygame.Rect(center_x - half_width, center_y, road_width, rect.bottom - center_y),
            "west": pygame.Rect(rect.left, center_y - half_width, center_x - rect.left, road_width),
        }
        for direction, connected in connections.items():
            if connected:
                pygame.draw.rect(surface, color, arms[direction])

    def _draw_context_zone(self, surface: pygame.Surface, rect: pygame.Rect, tile) -> None:
        if rect.width < 12:
            return
        zone_rect = rect.inflate(-max(4, rect.width // 5), -max(4, rect.height // 5))
        border_width = max(1, rect.width // 13)
        pygame.draw.rect(surface, COLORS[tile.zone.value], zone_rect, width=border_width, border_radius=2)

    def _draw_building(self, surface: pygame.Surface, rect: pygame.Rect, tile) -> None:
        pad = max(3, rect.width // 6)
        height_scale = max(0.25, tile.development)
        building_rect = rect.inflate(-pad * 2, -pad * 2)
        building_rect.height = max(4, int(building_rect.height * height_scale))
        building_rect.bottom = rect.bottom - pad
        pygame.draw.rect(surface, COLORS["shadow"], building_rect.move(2, 2))
        pygame.draw.rect(surface, COLORS["building_light"], building_rect)
        pygame.draw.rect(surface, COLORS["building_dark"], building_rect, width=1)

    def _draw_service_building(self, surface: pygame.Surface, rect: pygame.Rect, tile) -> None:
        color_key = BUILDING_COLOR_KEYS[tile.building]
        pygame.draw.rect(surface, COLORS[color_key], rect)
        inner = rect.inflate(-max(4, rect.width // 5), -max(4, rect.height // 5))
        pygame.draw.rect(surface, COLORS["building_light"], inner, border_radius=2)
        label = BUILDING_MARKER_LABELS[tile.building]
        if rect.width >= 22:
            text = self.small_font.render(label, True, COLORS["building_dark"])
            surface.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def _draw_context_building_marker(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        tile,
        view_mode: ViewMode,
    ) -> None:
        if tile.building == BuildingType.NONE:
            return
        if tile.building == VIEW_MAIN_BUILDINGS.get(view_mode):
            return

        marker_size = max(10, int(rect.width * 0.56))
        marker = pygame.Rect(0, 0, marker_size, marker_size)
        marker.center = rect.center
        border_width = max(1, rect.width // 12)
        color = COLORS[BUILDING_COLOR_KEYS[tile.building]]

        pygame.draw.rect(surface, COLORS["building_dark"], marker, border_radius=2)
        pygame.draw.rect(surface, color, marker, width=border_width, border_radius=2)

        if rect.width >= 22:
            label = BUILDING_MARKER_LABELS[tile.building]
            text = self.small_font.render(label, True, COLORS["text"])
            surface.blit(text, (marker.centerx - text.get_width() // 2, marker.centery - text.get_height() // 2))

    def _draw_utilities(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        city_map: CityMap,
        tile,
        x: int,
        y: int,
    ) -> None:
        if tile.has_power_line and rect.width >= 8:
            self._draw_power_line(surface, rect, city_map.power_connections(x, y))
        if tile.has_water_pipe and rect.width >= 8:
            self._draw_water_pipe(surface, rect, city_map.water_connections(x, y))

    def _draw_power_line(self, surface: pygame.Surface, rect: pygame.Rect, connections: dict[str, bool]) -> None:
        line_width = max(2, rect.width // 10)
        node_radius = max(3, rect.width // 8)
        center = (rect.centerx, rect.centery)
        endpoints = {
            "north": (rect.centerx, rect.top + 2),
            "east": (rect.right - 2, rect.centery),
            "south": (rect.centerx, rect.bottom - 2),
            "west": (rect.left + 2, rect.centery),
        }

        if not any(connections.values()):
            pygame.draw.circle(surface, COLORS["power"], center, node_radius)
            return

        for direction, connected in connections.items():
            if connected:
                pygame.draw.line(surface, COLORS["power"], center, endpoints[direction], line_width)
        pygame.draw.circle(surface, COLORS["power"], center, node_radius)

    def _draw_water_pipe(self, surface: pygame.Surface, rect: pygame.Rect, connections: dict[str, bool]) -> None:
        line_width = max(3, rect.width // 8)
        node_radius = max(3, rect.width // 10)
        center = (rect.centerx, rect.centery)
        endpoints = {
            "north": (rect.centerx, rect.top + 2),
            "east": (rect.right - 2, rect.centery),
            "south": (rect.centerx, rect.bottom - 2),
            "west": (rect.left + 2, rect.centery),
        }

        if not any(connections.values()):
            pygame.draw.circle(surface, COLORS["water"], center, node_radius)
            return

        for direction, connected in connections.items():
            if connected:
                pygame.draw.line(surface, COLORS["water"], center, endpoints[direction], line_width)
        pygame.draw.circle(surface, COLORS["water"], center, node_radius)

    def _draw_zone_status(self, surface: pygame.Surface, rect: pygame.Rect, tile) -> None:
        if rect.width < 16:
            return
        if not tile.powered:
            pygame.draw.circle(surface, COLORS["power"], (rect.left + 7, rect.top + 7), 3)
        if not tile.watered:
            pygame.draw.circle(surface, COLORS["water"], (rect.right - 7, rect.top + 7), 3)
        if tile.fire_risk >= 70:
            pygame.draw.circle(surface, COLORS["fire"], (rect.centerx, rect.bottom - 7), 3)
        if tile.crime_risk >= 70:
            pygame.draw.circle(surface, COLORS["police"], (rect.right - 7, rect.bottom - 7), 3)

    def _draw_hover(
        self,
        surface: pygame.Surface,
        city_map: CityMap,
        camera: Camera,
        active_tool: Tool,
        hover_tile: tuple[int, int],
        tile_px: int,
    ) -> None:
        x, y = hover_tile
        screen_x, screen_y = camera.world_to_screen(x, y, TILE_SIZE)
        rect = pygame.Rect(screen_x, screen_y, tile_px + 1, tile_px + 1)
        blocked = self._tool_blocked(city_map.get(x, y), active_tool)
        color = COLORS["hover_blocked"] if blocked else COLORS["hover_ok"]
        pygame.draw.rect(surface, color, rect, width=3)

    def _tool_blocked(self, tile, active_tool: Tool) -> bool:
        if tile.terrain == TerrainType.WATER and active_tool not in (Tool.INSPECT, Tool.BULLDOZE):
            return True
        if active_tool in (Tool.RESIDENTIAL, Tool.COMMERCIAL, Tool.INDUSTRIAL):
            return tile.has_road or tile.has_power_line or tile.has_water_pipe or tile.building != BuildingType.NONE
        if active_tool == Tool.ROAD:
            return tile.has_road
        if active_tool == Tool.POWER_LINE:
            return tile.has_power_line or tile.zone != ZoneType.EMPTY or tile.building != BuildingType.NONE
        if active_tool == Tool.WATER_PIPE:
            return tile.has_water_pipe or tile.zone != ZoneType.EMPTY or tile.building != BuildingType.NONE
        if active_tool in TOOL_TO_BUILDING:
            return not tile.is_empty
        return False

    def _draw_pedestrians(self, surface: pygame.Surface, camera: Camera, pedestrian_system: PedestrianSystem) -> None:
        """Draw pedestrians on the map."""
        for ped in pedestrian_system.pedestrians:
            screen_x, screen_y = camera.world_to_screen(ped.x, ped.y, TILE_SIZE)
            ped_size = max(2, int(TILE_SIZE * camera.zoom * 0.3))
            pygame.draw.circle(surface, COLORS["pedestrian"], (screen_x, screen_y), ped_size)
