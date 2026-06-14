from __future__ import annotations

import pygame


class Camera:
    def __init__(self, map_pixel_width: int, map_pixel_height: int, viewport: pygame.Rect) -> None:
        self.x = 0.0
        self.y = 0.0
        self.zoom = 1.0
        self.map_pixel_width = map_pixel_width
        self.map_pixel_height = map_pixel_height
        self.viewport = viewport

    def set_viewport(self, viewport: pygame.Rect) -> None:
        self.viewport = viewport
        self.clamp()

    def move(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy
        self.clamp()

    def change_zoom(self, amount: float, mouse_pos: tuple[int, int] | None = None) -> None:
        before_x, before_y = (0.0, 0.0)
        if mouse_pos is not None:
            before_x, before_y = self.screen_to_world_pixels(mouse_pos)
        self.zoom = max(0.55, min(1.8, self.zoom + amount))
        if mouse_pos is not None:
            after_x, after_y = self.screen_to_world_pixels(mouse_pos)
            self.x += before_x - after_x
            self.y += before_y - after_y
        self.clamp()

    def world_to_screen(self, tile_x: int, tile_y: int, tile_size: int) -> tuple[int, int]:
        screen_x = self.viewport.left + int((tile_x * tile_size - self.x) * self.zoom)
        screen_y = self.viewport.top + int((tile_y * tile_size - self.y) * self.zoom)
        return screen_x, screen_y

    def screen_to_tile(self, pos: tuple[int, int], tile_size: int) -> tuple[int, int] | None:
        if not self.viewport.collidepoint(pos):
            return None
        world_x, world_y = self.screen_to_world_pixels(pos)
        return int(world_x // tile_size), int(world_y // tile_size)

    def screen_to_world_pixels(self, pos: tuple[int, int]) -> tuple[float, float]:
        screen_x = pos[0] - self.viewport.left
        screen_y = pos[1] - self.viewport.top
        return self.x + screen_x / self.zoom, self.y + screen_y / self.zoom

    def visible_tile_bounds(self, tile_size: int, map_width: int, map_height: int) -> tuple[int, int, int, int]:
        start_x = max(0, int(self.x // tile_size) - 1)
        start_y = max(0, int(self.y // tile_size) - 1)
        end_x = min(map_width, int((self.x + self.viewport.width / self.zoom) // tile_size) + 2)
        end_y = min(map_height, int((self.y + self.viewport.height / self.zoom) // tile_size) + 2)
        return start_x, start_y, end_x, end_y

    def clamp(self) -> None:
        view_width = self.viewport.width / self.zoom
        view_height = self.viewport.height / self.zoom
        max_x = max(0, self.map_pixel_width - view_width)
        max_y = max(0, self.map_pixel_height - view_height)
        self.x = max(0, min(self.x, max_x))
        self.y = max(0, min(self.y, max_y))
