from __future__ import annotations

from collections.abc import Iterator

from .models import BuildingType, Tile, ZoneType


class CityMap:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.tiles = [[Tile() for _ in range(height)] for _ in range(width)]

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def get(self, x: int, y: int) -> Tile:
        return self.tiles[x][y]

    def iter_tiles(self) -> Iterator[tuple[int, int, Tile]]:
        for x in range(self.width):
            for y in range(self.height):
                yield x, y, self.tiles[x][y]

    def neighbors4(self, x: int, y: int) -> Iterator[tuple[int, int, Tile]]:
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx = x + dx
            ny = y + dy
            if self.in_bounds(nx, ny):
                yield nx, ny, self.get(nx, ny)

    def neighbors8(self, x: int, y: int) -> Iterator[tuple[int, int, Tile]]:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nx = x + dx
                ny = y + dy
                if self.in_bounds(nx, ny):
                    yield nx, ny, self.get(nx, ny)

    def has_adjacent_road(self, x: int, y: int) -> bool:
        return any(tile.has_road for _, _, tile in self.neighbors4(x, y))

    def place_zone(self, x: int, y: int, zone: ZoneType) -> bool:
        if not self.in_bounds(x, y):
            return False
        tile = self.get(x, y)
        if tile.has_road or tile.has_power_line or tile.has_water_pipe or tile.building != BuildingType.NONE:
            return False
        if tile.zone == zone:
            return False
        tile.zone = zone
        tile.development = 0.0
        tile.residents = 0
        tile.jobs = 0
        return True

    def place_road(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return False
        tile = self.get(x, y)
        if tile.has_road:
            return False
        tile.zone = ZoneType.EMPTY
        tile.building = BuildingType.NONE
        tile.development = 0.0
        tile.residents = 0
        tile.jobs = 0
        tile.land_value = 1.0
        tile.has_road = True
        return True

    def place_power_line(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return False
        tile = self.get(x, y)
        if tile.has_power_line or tile.zone != ZoneType.EMPTY or tile.building != BuildingType.NONE:
            return False
        tile.has_power_line = True
        return True

    def place_water_pipe(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return False
        tile = self.get(x, y)
        if tile.has_water_pipe or tile.zone != ZoneType.EMPTY or tile.building != BuildingType.NONE:
            return False
        tile.has_water_pipe = True
        return True

    def place_building(self, x: int, y: int, building: BuildingType) -> bool:
        if not self.in_bounds(x, y) or building == BuildingType.NONE:
            return False
        tile = self.get(x, y)
        if not tile.is_empty:
            return False
        tile.building = building
        return True

    def bulldoze(self, x: int, y: int) -> bool:
        if not self.in_bounds(x, y):
            return False
        tile = self.get(x, y)
        if tile.is_empty:
            return False
        tile.clear()
        return True

    def road_count(self) -> int:
        return sum(1 for _, _, tile in self.iter_tiles() if tile.has_road)

    def zoned_count(self) -> int:
        return sum(1 for _, _, tile in self.iter_tiles() if tile.zone != ZoneType.EMPTY)

    def power_line_count(self) -> int:
        return sum(1 for _, _, tile in self.iter_tiles() if tile.has_power_line)

    def water_pipe_count(self) -> int:
        return sum(1 for _, _, tile in self.iter_tiles() if tile.has_water_pipe)

    def building_count(self, building: BuildingType | None = None) -> int:
        if building is None:
            return sum(1 for _, _, tile in self.iter_tiles() if tile.building != BuildingType.NONE)
        return sum(1 for _, _, tile in self.iter_tiles() if tile.building == building)
