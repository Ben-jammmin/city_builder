from __future__ import annotations

import pygame

from .camera import Camera
from .city_map import CityMap
from .models import POWER_SOURCE_BUILDINGS, TOOL_TO_BUILDING, WATER_SOURCE_BUILDINGS, BuildingType, TerrainType, Tool, ViewMode, ZoneType
from .pedestrian import PedestrianSystem
from .settings import COLORS, TILE_SIZE
from .sprites import SpriteAtlas, tile_variant


TERRAIN_COLOR_KEYS = {
    TerrainType.WATER: "terrain_water",
    TerrainType.FOREST: "terrain_forest",
    TerrainType.HILL: "terrain_hill",
}

BUILDING_COLOR_KEYS = {
    BuildingType.POWER_PLANT: "power",
    BuildingType.LARGE_POWER_PLANT: "power",
    BuildingType.WATER_TOWER: "water",
    BuildingType.LARGE_WATER_TOWER: "water",
    BuildingType.POLICE: "police",
    BuildingType.FIRE: "fire",
    BuildingType.SCHOOL: "school",
    BuildingType.TRAIN_STATION: "train_station",
    BuildingType.AIRPORT: "airport",
}

BUILDING_MARKER_LABELS = {
    BuildingType.POWER_PLANT: "P",
    BuildingType.LARGE_POWER_PLANT: "P+",
    BuildingType.WATER_TOWER: "W",
    BuildingType.LARGE_WATER_TOWER: "W+",
    BuildingType.POLICE: "Po",
    BuildingType.FIRE: "F",
    BuildingType.SCHOOL: "S",
    BuildingType.TRAIN_STATION: "T",
    BuildingType.AIRPORT: "A",
}

VIEW_MAIN_BUILDINGS = {
    ViewMode.POWER: POWER_SOURCE_BUILDINGS,
    ViewMode.WATER: WATER_SOURCE_BUILDINGS,
    ViewMode.FIRE: {BuildingType.FIRE},
    ViewMode.POLICE: {BuildingType.POLICE},
}


class Renderer:
    def __init__(self) -> None:
        self.small_font = pygame.font.SysFont("Segoe UI", 13)
        self.sprites = SpriteAtlas(self.small_font)

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
        self._draw_terrain_base(surface, rect, city_map, tile, x, y)

        if view_mode != ViewMode.NORMAL:
            self._draw_view_tile(surface, rect, city_map, tile, x, y, view_mode)
            self._draw_grid(surface, rect, zoom, system_view=True)
            return

        if tile.has_road:
            self._draw_road(surface, rect, city_map.road_connections(x, y))
        elif tile.building != BuildingType.NONE:
            self._draw_service_building(surface, rect, tile)
        elif tile.zone != ZoneType.EMPTY:
            self.sprites.draw_zone(surface, rect, tile.zone, tile.development, tile.zone_level, tile_variant(x, y))
            self._draw_zone_status(surface, rect, tile)

        self._draw_utilities(surface, rect, city_map, tile, x, y)
        self._draw_grid(surface, rect, zoom, system_view=False)

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
            self._draw_terrain_base(surface, rect, city_map, tile, x, y)
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

    def _draw_terrain_base(self, surface: pygame.Surface, rect: pygame.Rect, city_map: CityMap, tile, x: int, y: int) -> None:
        same_neighbors = None
        if tile.terrain == TerrainType.WATER:
            same_neighbors = self._same_terrain_neighbors(city_map, x, y, tile.terrain)
        self.sprites.draw_terrain(surface, rect, tile.terrain, x, y, same_neighbors)

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
        if tile.building in POWER_SOURCE_BUILDINGS:
            self._draw_service_building(surface, rect, tile)
        if tile.has_power_line:
            self._draw_power_line(surface, rect, city_map.power_connections(x, y))

    def _draw_water_view(self, surface: pygame.Surface, rect: pygame.Rect, city_map: CityMap, tile, x: int, y: int) -> None:
        if tile.zone != ZoneType.EMPTY:
            color = (45, 78, 94) if tile.watered else (94, 58, 58)
            pygame.draw.rect(surface, color, rect)
        if tile.building in WATER_SOURCE_BUILDINGS:
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
        self.sprites.draw_road(surface, rect, connections)

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
        self.sprites.draw_zone_building(surface, rect, tile.zone, tile.development, tile.zone_level)

    def _draw_service_building(self, surface: pygame.Surface, rect: pygame.Rect, tile) -> None:
        self.sprites.draw_civic_building(surface, rect, tile.building)

    def _draw_context_building_marker(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        tile,
        view_mode: ViewMode,
    ) -> None:
        if tile.building == BuildingType.NONE:
            return
        if tile.building in VIEW_MAIN_BUILDINGS.get(view_mode, set()):
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
        self.sprites.draw_power_line(surface, rect, connections)

    def _draw_water_pipe(self, surface: pygame.Surface, rect: pygame.Rect, connections: dict[str, bool]) -> None:
        self.sprites.draw_water_pipe(surface, rect, connections)

    def _draw_zone_status(self, surface: pygame.Surface, rect: pygame.Rect, tile) -> None:
        if rect.width < 18:
            return
        if not tile.powered:
            self._draw_status_badge(surface, (rect.left + 8, rect.top + 8), COLORS["power"], "power", rect.width)
        if not tile.watered:
            self._draw_status_badge(surface, (rect.right - 8, rect.top + 8), COLORS["water"], "water", rect.width)
        if tile.fire_risk >= 70:
            self._draw_status_badge(surface, (rect.left + 8, rect.bottom - 8), COLORS["fire"], "fire", rect.width)
        if tile.crime_risk >= 70:
            self._draw_status_badge(surface, (rect.right - 8, rect.bottom - 8), COLORS["police"], "crime", rect.width)

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
        pygame.draw.rect(surface, (18, 22, 24), rect.inflate(2, 2), width=2)
        pygame.draw.rect(surface, color, rect, width=3)

    def _tool_blocked(self, tile, active_tool: Tool) -> bool:
        if active_tool == Tool.BULLDOZE:
            return tile.is_empty and tile.terrain == TerrainType.GRASS
        if tile.terrain == TerrainType.WATER and active_tool not in (Tool.INSPECT, Tool.BULLDOZE):
            return True
        if active_tool in (Tool.RESIDENTIAL, Tool.COMMERCIAL, Tool.INDUSTRIAL):
            return (
                tile.terrain != TerrainType.GRASS
                or tile.has_road
                or tile.has_power_line
                or tile.has_water_pipe
                or tile.building != BuildingType.NONE
            )
        if active_tool == Tool.ROAD:
            return tile.has_road
        if active_tool == Tool.POWER_LINE:
            return tile.has_power_line or tile.zone != ZoneType.EMPTY or tile.building != BuildingType.NONE
        if active_tool == Tool.WATER_PIPE:
            return tile.has_water_pipe or tile.zone != ZoneType.EMPTY or tile.building != BuildingType.NONE
        if active_tool in TOOL_TO_BUILDING:
            return tile.terrain != TerrainType.GRASS or not tile.is_empty
        return False

    def _draw_pedestrians(self, surface: pygame.Surface, camera: Camera, pedestrian_system: PedestrianSystem) -> None:
        for ped in pedestrian_system.pedestrians:
            screen_x, screen_y = camera.world_to_screen(ped.x, ped.y, TILE_SIZE)
            ped_size = max(3, int(TILE_SIZE * camera.zoom * 0.22))
            variant = abs(int(ped.x * 11 + ped.y * 7))
            self.sprites.draw_pedestrian(surface, (screen_x, screen_y), ped_size, variant)

    def _draw_grid(self, surface: pygame.Surface, rect: pygame.Rect, zoom: float, system_view: bool) -> None:
        if zoom < 0.75 and not system_view:
            return
        if system_view:
            color = COLORS["grid_light"] if zoom >= 1.15 else COLORS["grid"]
        else:
            color = (47, 58, 51) if zoom >= 1.15 else (42, 51, 46)
        pygame.draw.rect(surface, color, rect, width=1)

    def _draw_status_badge(
        self,
        surface: pygame.Surface,
        center: tuple[int, int],
        color: tuple[int, int, int],
        kind: str,
        tile_width: int,
    ) -> None:
        radius = max(4, tile_width // 8)
        pygame.draw.circle(surface, (20, 23, 26), center, radius + 1)
        pygame.draw.circle(surface, color, center, radius)
        icon_color = (24, 28, 31)
        if kind == "power":
            points = [
                (center[0] - radius // 3, center[1] - radius + 1),
                (center[0] + 1, center[1] - 1),
                (center[0] - 1, center[1] - 1),
                (center[0] + radius // 3, center[1] + radius - 1),
            ]
            pygame.draw.lines(surface, icon_color, False, points, max(1, tile_width // 24))
        elif kind == "water":
            pygame.draw.circle(surface, icon_color, (center[0], center[1] + 1), max(1, radius // 3))
            pygame.draw.polygon(surface, icon_color, [(center[0], center[1] - radius + 2), (center[0] - radius // 3, center[1]), (center[0] + radius // 3, center[1])])
        elif kind == "fire":
            pygame.draw.polygon(surface, icon_color, [(center[0], center[1] - radius + 2), (center[0] - radius // 2, center[1] + radius // 2), (center[0] + radius // 2, center[1] + radius // 2)])
        elif kind == "crime":
            pygame.draw.rect(surface, icon_color, pygame.Rect(center[0] - radius // 2, center[1] - radius // 3, radius, radius), border_radius=1)

    def _same_terrain_neighbors(
        self,
        city_map: CityMap,
        x: int,
        y: int,
        terrain: TerrainType,
    ) -> dict[str, bool]:
        return {
            "north": city_map.in_bounds(x, y - 1) and city_map.get(x, y - 1).terrain == terrain,
            "east": city_map.in_bounds(x + 1, y) and city_map.get(x + 1, y).terrain == terrain,
            "south": city_map.in_bounds(x, y + 1) and city_map.get(x, y + 1).terrain == terrain,
            "west": city_map.in_bounds(x - 1, y) and city_map.get(x - 1, y).terrain == terrain,
        }
