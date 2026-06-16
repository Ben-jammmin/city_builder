"""
city_map.py — The city grid.

CityMap holds the 2-D array of Tile objects and provides helpers for:
  - Querying neighbours (4-way and 8-way adjacency)
  - Placement validation (can the player put X here?)
  - Placement actions (actually modify the tile)
  - Aggregate counts used by the simulation (road count, maintenance costs, …)

All map coordinates are (x, y) where x goes left-right and y goes top-bottom.
"""
from __future__ import annotations

from collections.abc import Iterator

from .models import POWER_SOURCE_BUILDINGS, WATER_SOURCE_BUILDINGS, BuildingType, RecreationType, TerrainType, Tile, ZoneType
from .settings import RECREATION_MAINTENANCE, RECREATION_DEMAND_RES, RECREATION_DEMAND_COM


class CityMap:
    """A rectangular grid of Tile objects representing the whole city."""

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        # 2-D list: tiles[x][y]. Inner list is a column (varying y).
        self.tiles = [[Tile() for _ in range(height)] for _ in range(width)]

    # ── Basic accessors ────────────────────────────────────────────────────────

    def in_bounds(self, x: int, y: int) -> bool:
        """Returns True if (x, y) is a valid tile coordinate."""
        return 0 <= x < self.width and 0 <= y < self.height

    def get(self, x: int, y: int) -> Tile:
        """Returns the Tile at (x, y). Assumes coordinates are in bounds."""
        return self.tiles[x][y]

    def iter_tiles(self) -> Iterator[tuple[int, int, Tile]]:
        """Yields (x, y, tile) for every tile in the grid."""
        for x in range(self.width):
            for y in range(self.height):
                yield x, y, self.tiles[x][y]

    # ── Aggregate queries ──────────────────────────────────────────────────────

    def zoned_count(self) -> int:
        """Returns the total number of non-empty zoned tiles."""
        return sum(1 for _, _, tile in self.iter_tiles() if tile.zone != ZoneType.EMPTY)

    # ── Neighbour iterators ────────────────────────────────────────────────────

    def neighbors4(self, x: int, y: int) -> Iterator[tuple[int, int, Tile]]:
        """Yields the up-to-4 orthogonal (N/E/S/W) neighbours of (x, y)."""
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)):
            nx = x + dx
            ny = y + dy
            if self.in_bounds(nx, ny):
                yield nx, ny, self.get(nx, ny)

    def neighbors8(self, x: int, y: int) -> Iterator[tuple[int, int, Tile]]:
        """Yields the up-to-8 orthogonal and diagonal neighbours of (x, y)."""
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue   # skip the tile itself
                nx = x + dx
                ny = y + dy
                if self.in_bounds(nx, ny):
                    yield nx, ny, self.get(nx, ny)

    def has_adjacent_road(self, x: int, y: int) -> bool:
        """Returns True if at least one orthogonal neighbour has a road."""
        return any(tile.has_road for _, _, tile in self.neighbors4(x, y))

    # ── Terrain queries ────────────────────────────────────────────────────────

    def is_buildable_land(self, x: int, y: int) -> bool:
        """Returns True if the tile exists and is not water (roads can go on forests/hills)."""
        return self.in_bounds(x, y) and self.get(x, y).terrain != TerrainType.WATER

    def is_clear_land(self, x: int, y: int) -> bool:
        """Land is clear for zones/buildings only if it's grass terrain."""
        return self.in_bounds(x, y) and self.get(x, y).terrain == TerrainType.GRASS

    def is_water(self, x: int, y: int) -> bool:
        """Returns True if the tile is water terrain."""
        return self.in_bounds(x, y) and self.get(x, y).terrain == TerrainType.WATER

    # ── Placement validation ───────────────────────────────────────────────────

    def can_place_zone(self, x: int, y: int, zone: ZoneType, level: int = 1, recreation_type: RecreationType | None = None) -> bool:
        """Returns True if the player is allowed to zone this tile."""
        if not self.is_clear_land(x, y):
            return False
        tile = self.get(x, y)
        # Can't zone a tile that already has a road, power line, pipe, or building.
        if tile.has_road or tile.has_power_line or tile.has_water_pipe or tile.building != BuildingType.NONE:
            return False
        # Allow re-zoning to a different type, level, or recreation sub-type.
        if tile.zone != zone or tile.zone_level != level:
            return True
        # Same zone+level — allow if placing a different recreation type
        if zone == ZoneType.PARK and recreation_type is not None and tile.recreation_type != recreation_type:
            return True
        return False

    def can_place_road(self, x: int, y: int) -> bool:
        """Returns True when a road tile can be placed here."""
        if not self.is_buildable_land(x, y):
            return False
        tile = self.get(x, y)
        # Roads can only be placed on empty (unzoned, no buildings) tiles.
        if tile.zone != ZoneType.EMPTY or tile.building != BuildingType.NONE:
            return False
        return not tile.has_road

    def can_place_power_line(self, x: int, y: int) -> bool:
        """Returns True when a power line can be placed here."""
        if not self.is_buildable_land(x, y):
            return False
        tile = self.get(x, y)
        # Power lines share empty unzoned tiles only.
        return tile.zone == ZoneType.EMPTY and tile.building == BuildingType.NONE and not tile.has_power_line

    def can_place_water_pipe(self, x: int, y: int) -> bool:
        """Returns True when a water pipe can be placed here."""
        if not self.is_buildable_land(x, y):
            return False
        tile = self.get(x, y)
        return tile.zone == ZoneType.EMPTY and tile.building == BuildingType.NONE and not tile.has_water_pipe

    def can_place_building(self, x: int, y: int, building: BuildingType) -> bool:
        """Returns True when a civic building can be placed here."""
        if building == BuildingType.NONE or not self.is_clear_land(x, y):
            return False
        # Tile must be completely empty (no zone, road, pipes, or existing building).
        return self.get(x, y).is_empty

    # ── Connection queries ─────────────────────────────────────────────────────

    def road_connections(self, x: int, y: int) -> dict[str, bool]:
        """Returns which cardinal directions have a neighbouring road tile."""
        if not self.in_bounds(x, y) or not self.get(x, y).has_road:
            return {"north": False, "east": False, "south": False, "west": False}
        return {
            "north": self._has_road_at(x, y - 1),
            "east": self._has_road_at(x + 1, y),
            "south": self._has_road_at(x, y + 1),
            "west": self._has_road_at(x - 1, y),
        }

    def _has_road_at(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and self.get(x, y).has_road

    def power_connections(self, x: int, y: int) -> dict[str, bool]:
        """Returns which cardinal directions are connected by power infrastructure."""
        if not self._is_power_connector_at(x, y):
            return {"north": False, "east": False, "south": False, "west": False}
        return {
            "north": self._is_power_connector_at(x, y - 1),
            "east": self._is_power_connector_at(x + 1, y),
            "south": self._is_power_connector_at(x, y + 1),
            "west": self._is_power_connector_at(x - 1, y),
        }

    def _is_power_connector_at(self, x: int, y: int) -> bool:
        """Returns True if the tile has a power line or is a power-producing building."""
        if not self.in_bounds(x, y):
            return False
        tile = self.get(x, y)
        return tile.has_power_line or tile.building in POWER_SOURCE_BUILDINGS

    def water_connections(self, x: int, y: int) -> dict[str, bool]:
        """Returns which cardinal directions are connected by water infrastructure."""
        if not self._is_water_connector_at(x, y):
            return {"north": False, "east": False, "south": False, "west": False}
        return {
            "north": self._is_water_connector_at(x, y - 1),
            "east": self._is_water_connector_at(x + 1, y),
            "south": self._is_water_connector_at(x, y + 1),
            "west": self._is_water_connector_at(x - 1, y),
        }

    def _is_water_connector_at(self, x: int, y: int) -> bool:
        """Returns True if the tile has a water pipe or is a water-producing building."""
        if not self.in_bounds(x, y):
            return False
        tile = self.get(x, y)
        return tile.has_water_pipe or tile.building in WATER_SOURCE_BUILDINGS

    # ── Placement actions ──────────────────────────────────────────────────────

    def place_zone(self, x: int, y: int, zone: ZoneType, level: int = 1, recreation_type: RecreationType | None = None) -> bool:
        """Zones the tile if allowed. Returns True on success."""
        if not self.can_place_zone(x, y, zone, level, recreation_type):
            return False
        tile = self.get(x, y)
        # Bulldoze any trees/forest cover when building here.
        self._clear_natural_cover(tile)
        # Upgrading the density level of the same zone type keeps existing development
        # so the player's grown city isn't reset — only a full rezone starts fresh.
        upgrading_same_zone = (tile.zone == zone and level > tile.zone_level)
        tile.zone = zone
        tile.zone_level = level
        if zone == ZoneType.PARK and recreation_type is not None:
            tile.recreation_type = recreation_type
        if not upgrading_same_zone:
            tile.development = 0.0
            tile.residents = 0
            tile.jobs = 0
        return True

    def place_road(self, x: int, y: int) -> bool:
        """Places a road on the tile if allowed. Returns True on success."""
        if not self.can_place_road(x, y):
            return False
        tile = self.get(x, y)
        self._clear_natural_cover(tile)
        tile.has_road = True
        return True

    def place_power_line(self, x: int, y: int) -> bool:
        """Places a power line on the tile if allowed. Returns True on success."""
        if not self.can_place_power_line(x, y):
            return False
        tile = self.get(x, y)
        self._clear_natural_cover(tile)
        tile.has_power_line = True
        return True

    def place_water_pipe(self, x: int, y: int) -> bool:
        """Places a water pipe on the tile if allowed. Returns True on success."""
        if not self.can_place_water_pipe(x, y):
            return False
        tile = self.get(x, y)
        self._clear_natural_cover(tile)
        tile.has_water_pipe = True
        return True

    def place_building(self, x: int, y: int, building: BuildingType) -> bool:
        """Places a civic building on the tile if allowed. Returns True on success."""
        if not self.can_place_building(x, y, building):
            return False
        tile = self.get(x, y)
        self._clear_natural_cover(tile)
        tile.building = building
        return True

    def bulldoze(self, x: int, y: int) -> bool:
        """Clear man-made structures first; if already empty, clear non-grass terrain."""
        if not self.in_bounds(x, y):
            return False
        tile = self.get(x, y)
        if not tile.is_empty:
            # First pass: remove buildings, zones, roads, utilities.
            tile.clear()
            return True
        if tile.terrain != TerrainType.GRASS:
            # Second pass: clear remaining natural obstacles (water, forest, hill).
            tile.terrain = TerrainType.GRASS
            return True
        return False

    # ── Aggregate counts used by the simulation ────────────────────────────────

    def road_count(self) -> int:
        """Returns the total number of road tiles (used to calculate maintenance cost)."""
        return sum(1 for _, _, tile in self.iter_tiles() if tile.has_road)

    def zone_maintenance_units(self) -> int:
        """
        Returns the sum of zone levels across all non-empty, non-park zones.
        Dense zones (level 2) cost twice as much to maintain as standard zones.
        """
        return sum(
            tile.zone_level
            for _, _, tile in self.iter_tiles()
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK)
        )

    def power_line_count(self) -> int:
        return sum(1 for _, _, tile in self.iter_tiles() if tile.has_power_line)

    def water_pipe_count(self) -> int:
        return sum(1 for _, _, tile in self.iter_tiles() if tile.has_water_pipe)

    def park_count(self) -> int:
        return sum(1 for _, _, tile in self.iter_tiles() if tile.zone == ZoneType.PARK)

    def recreation_maintenance_cost(self) -> int:
        """Sums the monthly upkeep cost for every recreation tile on the map."""
        total = 0
        for _, _, tile in self.iter_tiles():
            if tile.zone == ZoneType.PARK:
                total += RECREATION_MAINTENANCE.get(tile.recreation_type.value, 3)
        return total

    def recreation_demand_bonus(self) -> tuple[float, float]:
        """Returns (residential_bonus, commercial_bonus) summed across all rec tiles."""
        res_bonus = 0.0
        com_bonus = 0.0
        for _, _, tile in self.iter_tiles():
            if tile.zone == ZoneType.PARK:
                res_bonus += RECREATION_DEMAND_RES.get(tile.recreation_type.value, 0.5)
                com_bonus += RECREATION_DEMAND_COM.get(tile.recreation_type.value, 0.0)
        return res_bonus, com_bonus

    def building_count(self, building: BuildingType | None = None) -> int:
        """Counts civic building tiles. Counts all non-NONE types if building is None."""
        if building is None:
            return sum(1 for _, _, tile in self.iter_tiles() if tile.building != BuildingType.NONE)
        return sum(1 for _, _, tile in self.iter_tiles() if tile.building == building)

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _clear_natural_cover(self, tile: Tile) -> None:
        """Converts forest to grass when the player builds on it (water stays water)."""
        if tile.terrain == TerrainType.FOREST:
            tile.terrain = TerrainType.GRASS
