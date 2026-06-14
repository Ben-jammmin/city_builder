from __future__ import annotations

import pygame

from .camera import Camera
from .city_map import CityMap
from .models import TOOL_TO_BUILDING, BuildingType, Tool, ZoneType
from .settings import COLORS, TILE_SIZE


class Renderer:
    def __init__(self) -> None:
        self.small_font = pygame.font.SysFont("Segoe UI", 13)

    def draw_map(
        self,
        surface: pygame.Surface,
        city_map: CityMap,
        camera: Camera,
        active_tool: Tool,
        hover_tile: tuple[int, int] | None,
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
                self._draw_tile(surface, rect, tile, x, y, camera.zoom)

        if hover_tile and city_map.in_bounds(*hover_tile):
            self._draw_hover(surface, city_map, camera, active_tool, hover_tile, tile_px)

        pygame.draw.rect(surface, (20, 24, 28), camera.viewport, width=2)
        surface.set_clip(old_clip)

    def _draw_tile(self, surface: pygame.Surface, rect: pygame.Rect, tile, x: int, y: int, zoom: float) -> None:
        base_color = COLORS["empty"] if (x + y) % 2 == 0 else COLORS["empty_alt"]
        pygame.draw.rect(surface, base_color, rect)

        if tile.has_road:
            self._draw_road(surface, rect)
        elif tile.building != BuildingType.NONE:
            self._draw_service_building(surface, rect, tile)
        elif tile.zone != ZoneType.EMPTY:
            pygame.draw.rect(surface, COLORS[tile.zone.value], rect)
            pygame.draw.rect(surface, COLORS["zone_border"], rect, width=1)
            if tile.development > 0.08:
                self._draw_building(surface, rect, tile)
            self._draw_zone_status(surface, rect, tile)

        self._draw_utilities(surface, rect, tile)

        grid_color = COLORS["grid_light"] if zoom >= 1.15 else COLORS["grid"]
        pygame.draw.rect(surface, grid_color, rect, width=1)

    def _draw_road(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        pygame.draw.rect(surface, COLORS["road"], rect)
        if rect.width >= 14 and rect.height >= 14:
            pygame.draw.line(
                surface,
                COLORS["road_line"],
                (rect.left + 4, rect.centery),
                (rect.right - 4, rect.centery),
                width=2,
            )
            pygame.draw.line(
                surface,
                COLORS["road_line"],
                (rect.centerx, rect.top + 4),
                (rect.centerx, rect.bottom - 4),
                width=2,
            )

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
        color_key = {
            BuildingType.POWER_PLANT: "power",
            BuildingType.WATER_TOWER: "water",
            BuildingType.POLICE: "police",
            BuildingType.FIRE: "fire",
            BuildingType.SCHOOL: "school",
        }[tile.building]
        pygame.draw.rect(surface, COLORS[color_key], rect)
        inner = rect.inflate(-max(4, rect.width // 5), -max(4, rect.height // 5))
        pygame.draw.rect(surface, COLORS["building_light"], inner, border_radius=2)
        label = {
            BuildingType.POWER_PLANT: "P",
            BuildingType.WATER_TOWER: "W",
            BuildingType.POLICE: "Po",
            BuildingType.FIRE: "F",
            BuildingType.SCHOOL: "S",
        }[tile.building]
        if rect.width >= 22:
            text = self.small_font.render(label, True, COLORS["building_dark"])
            surface.blit(text, (rect.centerx - text.get_width() // 2, rect.centery - text.get_height() // 2))

    def _draw_utilities(self, surface: pygame.Surface, rect: pygame.Rect, tile) -> None:
        if tile.has_power_line and rect.width >= 8:
            pygame.draw.line(
                surface,
                COLORS["power"],
                (rect.left + 3, rect.top + 5),
                (rect.right - 3, rect.bottom - 5),
                width=2,
            )
        if tile.has_water_pipe and rect.width >= 8:
            pygame.draw.line(
                surface,
                COLORS["water"],
                (rect.left + 3, rect.bottom - 5),
                (rect.right - 3, rect.top + 5),
                width=2,
            )

    def _draw_zone_status(self, surface: pygame.Surface, rect: pygame.Rect, tile) -> None:
        if rect.width < 16:
            return
        if not tile.powered:
            pygame.draw.circle(surface, COLORS["power"], (rect.left + 7, rect.top + 7), 3)
        if not tile.watered:
            pygame.draw.circle(surface, COLORS["water"], (rect.right - 7, rect.top + 7), 3)

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
