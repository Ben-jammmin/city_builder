"""
renderer.py — Draws the city map onto the screen

The renderer iterates over visible tiles and draws them in back-to-front order
(painter's algorithm) so buildings overlap correctly in the isometric view.

Drawing order per tile:
  1. Terrain (grass, water, forest, hill)
  2. Zone base (empty lot indicator)
  3. Road or civic building or zone building
  4. Status badges (no power, no water, fire risk, crime)
"""

from __future__ import annotations

import pygame

from .camera import Camera
from .city_map import CityMap
from .models import (
    POWER_SOURCE_BUILDINGS, TOOL_TO_BUILDING, WATER_SOURCE_BUILDINGS,
    BuildingType, TerrainType, Tool, ViewMode, ZoneType,
)
from .pedestrian import PedestrianSystem
from .settings import COLORS, TILE_SIZE
from .sprites import SpriteAtlas, tile_variant


# Maps BuildingType to the color key in COLORS (settings.py)
BUILDING_COLOR_KEYS = {
    BuildingType.POWER_PLANT:       "power",
    BuildingType.LARGE_POWER_PLANT: "power",
    BuildingType.WATER_TOWER:       "water",
    BuildingType.LARGE_WATER_TOWER: "water",
    BuildingType.POLICE:            "police",
    BuildingType.FIRE:              "fire",
    BuildingType.SCHOOL:            "school",
    BuildingType.TRAIN_STATION:     "train_station",
    BuildingType.AIRPORT:           "airport",
}

# Which building types are "main" for each special view mode
VIEW_MAIN_BUILDINGS = {
    ViewMode.POWER:  POWER_SOURCE_BUILDINGS,
    ViewMode.WATER:  WATER_SOURCE_BUILDINGS,
    ViewMode.FIRE:   {BuildingType.FIRE},
    ViewMode.POLICE: {BuildingType.POLICE},
}

# Order to cycle through connection directions when rotating connections dict
_CONN_DIRS = ["north", "east", "south", "west"]


class Renderer:
    """Handles all map drawing — terrain, buildings, roads, overlays, pedestrians."""

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
        """
        Main entry point — clears the viewport and draws every visible tile.

        Uses the painter's algorithm: tiles furthest from the viewer are drawn
        first so that nearby buildings correctly overlap distant ones.
        """
        pygame.draw.rect(surface, COLORS["background"], camera.viewport)

        # Clip drawing to the map viewport (keeps the sidebar clean)
        old_clip = surface.get_clip()
        surface.set_clip(camera.viewport)

        # Tile dimensions in pixels at the current zoom level
        tw = max(4, int(camera.tile_w * camera.zoom))
        th = max(2, int(camera.tile_h * camera.zoom))

        # Only draw tiles that are actually visible on screen
        start_x, start_y, end_x, end_y = camera.visible_tile_bounds(
            TILE_SIZE, city_map.width, city_map.height
        )

        rot = camera.rotation

        # Iterate tiles in painter's back-to-front order for this rotation
        for x, y in self._iter_painter_order(start_x, start_y, end_x, end_y, rot):
            # Convert rotated iteration coords back to real map coords
            mx, my = camera._unapply_rotation(x, y)
            if not city_map.in_bounds(mx, my):
                continue
            tile = city_map.get(mx, my)
            cx, cy = camera.world_to_screen(mx, my)
            self._draw_tile(surface, city_map, tile, mx, my, cx, cy, tw, th, view_mode, rot)

        # Draw hover highlight over the tile under the mouse cursor
        if hover_tile and city_map.in_bounds(*hover_tile):
            hx, hy = hover_tile
            cx, cy = camera.world_to_screen(hx, hy)
            self._draw_hover(surface, city_map, active_tool, hover_tile, cx, cy, tw, th)

        # Draw walking pedestrians (only in normal view)
        if pedestrian_system is not None and view_mode == ViewMode.NORMAL:
            self._draw_pedestrians(surface, camera, pedestrian_system, tw, th)

        # Thin border around the map area
        pygame.draw.rect(surface, (20, 24, 28), camera.viewport, width=2)
        surface.set_clip(old_clip)

    # ------------------------------------------------------------------ #
    # Per-tile drawing                                                     #
    # ------------------------------------------------------------------ #

    def _draw_tile(
        self,
        surface: pygame.Surface,
        city_map: CityMap,
        tile,
        x: int,
        y: int,
        cx: int,
        cy: int,
        tw: int,
        th: int,
        view_mode: ViewMode,
        rotation: int = 0,
    ) -> None:
        """Draw one tile: terrain first, then whatever sits on top of it."""

        # Water tiles need to know their neighbors to draw shore edges correctly
        same_nbrs = None
        if tile.terrain == TerrainType.WATER:
            same_nbrs = self._same_terrain_neighbors(city_map, x, y, tile.terrain)
        self.sprites.draw_terrain(surface, cx, cy, tw, th, tile.terrain, x, y, same_nbrs)

        # Special view modes (power, water, fire, police) get their own overlay
        if view_mode != ViewMode.NORMAL:
            self._draw_view_overlay(surface, city_map, tile, x, y, cx, cy, tw, th, view_mode, rotation)
            return

        # --- Normal view ---
        if tile.has_road:
            conn = _rotate_connections(city_map.road_connections(x, y), rotation)
            self.sprites.draw_road(surface, cx, cy, tw, th, conn)
        elif tile.building != BuildingType.NONE:
            self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)
        elif tile.zone != ZoneType.EMPTY:
            self.sprites.draw_zone_base(surface, cx, cy, tw, th, tile.zone, tile.zone_level)
            if tile.development > 0.05:
                self.sprites.draw_building(
                    surface, cx, cy, tw, th,
                    tile.zone, tile.development, tile.zone_level,
                    tile_variant(x, y), rotation,
                )
            self._draw_zone_status_iso(surface, cx, cy, tw, th, tile)

        # Power lines and water pipes are NOT shown in normal view.
        # Switch to Power or Water view (press V) to see the networks.

    def _draw_view_overlay(
        self,
        surface: pygame.Surface,
        city_map: CityMap,
        tile,
        x: int,
        y: int,
        cx: int,
        cy: int,
        tw: int,
        th: int,
        view_mode: ViewMode,
        rotation: int = 0,
    ) -> None:
        """
        Draw tile contents for a special view mode (power, water, fire, police).
        Each mode tints zones red/green and shows the relevant infrastructure.
        """
        # Roads always show so you can navigate in any view mode
        if tile.has_road:
            conn = _rotate_connections(city_map.road_connections(x, y), rotation)
            self.sprites.draw_road(surface, cx, cy, tw, th, conn)

        if view_mode == ViewMode.TERRAIN:
            if tile.zone != ZoneType.EMPTY:
                zone_c = COLORS.get(tile.zone.value, (100, 100, 100))
                self._draw_diam_overlay(surface, cx, cy, tw, th, (*zone_c, 75))
            if tile.building != BuildingType.NONE:
                self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)

        elif view_mode == ViewMode.POWER:
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK):
                c = (92, 82, 50, 138) if tile.powered else (120, 55, 55, 138)
                self._draw_diam_overlay(surface, cx, cy, tw, th, c)
            if tile.building in POWER_SOURCE_BUILDINGS:
                self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)
            elif tile.building != BuildingType.NONE:
                self._draw_marker_dot(surface, cx, cy, tw, th, tile.building)
            if tile.has_power_line:
                conn = _rotate_connections(city_map.power_connections(x, y), rotation)
                self._draw_power_line_iso(surface, cx, cy, tw, th, conn)

        elif view_mode == ViewMode.WATER:
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK):
                c = (45, 80, 100, 138) if tile.watered else (110, 58, 58, 138)
                self._draw_diam_overlay(surface, cx, cy, tw, th, c)
            if tile.building in WATER_SOURCE_BUILDINGS:
                self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)
            elif tile.building != BuildingType.NONE:
                self._draw_marker_dot(surface, cx, cy, tw, th, tile.building)
            if tile.has_water_pipe:
                conn = _rotate_connections(city_map.water_connections(x, y), rotation)
                self._draw_water_pipe_iso(surface, cx, cy, tw, th, conn)

        elif view_mode == ViewMode.FIRE:
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK):
                self._draw_diam_overlay(surface, cx, cy, tw, th,
                                        self._risk_color_iso(tile.fire_risk, tile.fire_coverage))
            if tile.building == BuildingType.FIRE:
                self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)
            elif tile.building != BuildingType.NONE:
                self._draw_marker_dot(surface, cx, cy, tw, th, tile.building)

        elif view_mode == ViewMode.POLICE:
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK):
                self._draw_diam_overlay(surface, cx, cy, tw, th,
                                        self._risk_color_iso(tile.crime_risk, tile.police_coverage))
            if tile.building == BuildingType.POLICE:
                self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)
            elif tile.building != BuildingType.NONE:
                self._draw_marker_dot(surface, cx, cy, tw, th, tile.building)

    # ------------------------------------------------------------------ #
    # Painter's algorithm tile iteration                                   #
    # ------------------------------------------------------------------ #

    def _iter_painter_order(
        self,
        sx: int, sy: int,
        ex: int, ey: int,
        rotation: int,
    ):
        """
        Yield (x, y) tile indices in back-to-front draw order for the given rotation.

        In isometric view, tiles closer to the viewer must be drawn LAST so they
        appear in front of distant tiles. The "depth" of a tile depends on the
        camera angle (rotation), so we iterate diagonals in a different direction
        for each rotation.

        Diagonals at rotation r:
          r=0 (NW view): depth = x+y → draw increasing x+y
          r=1 (NE view): depth = x-y → draw increasing x-y
          r=2 (SE view): depth = -(x+y) → draw decreasing x+y
          r=3 (SW view): depth = y-x → draw increasing y-x
        """
        if rotation == 0:
            # Standard: draw diagonal bands of (x+y=constant) from back to front
            for total in range(sx + sy, ex + ey - 1):
                x_lo = max(sx, total - (ey - 1))
                x_hi = min(ex - 1, total - sy)
                for x in range(x_lo, x_hi + 1):
                    yield x, total - x

        elif rotation == 1:
            # Diagonal bands of (x-y=constant) from smallest to largest
            for total in range(sx - (ey - 1), ex - sy):
                x_lo = max(sx, total + sy)
                x_hi = min(ex - 1, total + ey - 1)
                for x in range(x_lo, x_hi + 1):
                    yield x, x - total

        elif rotation == 2:
            # Same bands as rotation=0 but drawn in reverse order
            for total in range(ex + ey - 2, sx + sy - 1, -1):
                x_lo = max(sx, total - (ey - 1))
                x_hi = min(ex - 1, total - sy)
                for x in range(x_lo, x_hi + 1):
                    yield x, total - x

        else:  # rotation == 3
            # Diagonal bands of (y-x=constant) from smallest to largest
            for total in range(sy - (ex - 1), ey - sx):
                y_lo = max(sy, total + sx)
                y_hi = min(ey - 1, total + ex - 1)
                for y in range(y_lo, y_hi + 1):
                    yield y - total, y

    # ------------------------------------------------------------------ #
    # Drawing helpers                                                      #
    # ------------------------------------------------------------------ #

    def _draw_diam_overlay(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        color: tuple,
    ) -> None:
        """Draw a translucent diamond overlay on a tile (used for view mode tints)."""
        hw, hh = tw // 2, th // 2
        ov = pygame.Surface((tw, th), pygame.SRCALPHA)
        pygame.draw.polygon(ov, color, [(hw, 0), (tw, hh), (hw, th), (0, hh)])
        surface.blit(ov, (cx - hw, cy))

    def _draw_marker_dot(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        building: BuildingType,
    ) -> None:
        """Draw a small colored dot for a building in a view-mode overlay."""
        if tw < 10:
            return
        ck    = BUILDING_COLOR_KEYS.get(building, "building_dark")
        color = COLORS.get(ck, (100, 100, 100))
        r      = max(4, tw // 8)
        center = (cx, cy + th // 2)
        pygame.draw.circle(surface, COLORS["building_dark"], center, r + 1)
        pygame.draw.circle(surface, color, center, r)

    def _draw_hover(
        self,
        surface: pygame.Surface,
        city_map: CityMap,
        active_tool: Tool,
        hover_tile: tuple[int, int],
        cx: int, cy: int,
        tw: int, th: int,
    ) -> None:
        """Draw the diamond outline under the mouse cursor."""
        x, y   = hover_tile
        tile   = city_map.get(x, y)
        blocked = self._tool_blocked(tile, active_tool)
        color  = COLORS["hover_blocked"] if blocked else COLORS["hover_ok"]
        hw, hh = tw // 2, th // 2
        # Slightly larger shadow behind the hover border
        shadow = [(cx, cy - 1), (cx + hw + 1, cy + hh), (cx, cy + th + 1), (cx - hw - 1, cy + hh)]
        pygame.draw.polygon(surface, (18, 22, 24), shadow, 2)
        diam = [(cx, cy), (cx + hw, cy + hh), (cx, cy + th), (cx - hw, cy + hh)]
        pygame.draw.polygon(surface, color, diam, 3)

    def _draw_zone_status_iso(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        tile,
    ) -> None:
        """Show small warning badges on zoned tiles that have problems."""
        if tw < 18 or tile.zone == ZoneType.PARK:
            return
        hh     = th // 2
        center = (cx, cy + hh)
        r      = max(4, tw // 8)
        if not tile.powered:
            self._draw_status_badge(surface, (center[0] - r, center[1] - r // 2),
                                    COLORS["power"], "power", tw)
        if not tile.watered:
            self._draw_status_badge(surface, (center[0] + r, center[1] - r // 2),
                                    COLORS["water"], "water", tw)
        if tile.fire_risk >= 70:
            self._draw_status_badge(surface, (center[0] - r, center[1] + r // 2),
                                    COLORS["fire"], "fire", tw)
        if tile.crime_risk >= 70:
            self._draw_status_badge(surface, (center[0] + r, center[1] + r // 2),
                                    COLORS["police"], "crime", tw)

    def _draw_power_line_iso(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        connections: dict,
    ) -> None:
        """Draw the power line pole and wires for a single tile."""
        hw, hh   = tw // 2, th // 2
        center   = (cx, cy + hh)
        pole_h   = max(3, th // 2)
        pole_top = (cx, cy + hh - pole_h)
        pole_c   = (220, 200, 90)
        lw       = max(1, tw // 20)

        pygame.draw.line(surface, pole_c, center, pole_top, lw)

        # Wire attachment points at the midpoint of each diamond edge
        edge_mids = {
            "north": (cx + hw // 2, cy + hh // 2),
            "east":  (cx + hw // 2, cy + th - hh // 2),
            "south": (cx - hw // 2, cy + th - hh // 2),
            "west":  (cx - hw // 2, cy + hh // 2),
        }
        for direction, ep in edge_mids.items():
            if connections.get(direction, False):
                pygame.draw.line(surface, pole_c, pole_top, ep, max(1, tw // 28))

    def _draw_water_pipe_iso(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        connections: dict,
    ) -> None:
        """Draw the water pipe node and segments for a single tile."""
        hw, hh  = tw // 2, th // 2
        center  = (cx, cy + hh)
        pipe_c  = (65, 155, 205)
        lw      = max(1, tw // 18)
        r       = max(2, tw // 14)

        pygame.draw.circle(surface, pipe_c, center, r)

        edge_mids = {
            "north": (cx + hw // 2, cy + hh // 2),
            "east":  (cx + hw // 2, cy + th - hh // 2),
            "south": (cx - hw // 2, cy + th - hh // 2),
            "west":  (cx - hw // 2, cy + hh // 2),
        }
        for direction, ep in edge_mids.items():
            if connections.get(direction, False):
                pygame.draw.line(surface, pipe_c, center, ep, lw)

    def _risk_color_iso(self, risk: int, covered: bool) -> tuple:
        """Return an RGBA overlay color for a fire/crime risk level."""
        if risk >= 70:
            return (142, 57, 53, 148)
        if risk >= 40:
            return (142, 111, 58, 128)
        if covered:
            return (62, 105, 76, 110)
        return (83, 84, 72, 90)

    def _tool_blocked(self, tile, active_tool: Tool) -> bool:
        """Return True if the active tool cannot be placed on this tile."""
        if active_tool == Tool.BULLDOZE:
            return tile.is_empty and tile.terrain == TerrainType.GRASS
        if tile.terrain == TerrainType.WATER and active_tool not in (Tool.INSPECT, Tool.BULLDOZE):
            return True
        if active_tool in (Tool.RESIDENTIAL, Tool.COMMERCIAL, Tool.INDUSTRIAL,
                           Tool.DENSE_RESIDENTIAL, Tool.DENSE_COMMERCIAL):
            return (
                tile.terrain != TerrainType.GRASS
                or tile.has_road
                or tile.has_power_line
                or tile.has_water_pipe
                or tile.building != BuildingType.NONE
            )
        if active_tool == Tool.PARK:
            return (
                tile.terrain != TerrainType.GRASS
                or tile.has_road
                or tile.has_power_line
                or tile.has_water_pipe
                or tile.building != BuildingType.NONE
                or tile.zone == ZoneType.PARK
            )
        if active_tool == Tool.ROAD:
            return tile.has_road
        if active_tool == Tool.POWER_LINE:
            return (tile.has_power_line
                    or tile.zone != ZoneType.EMPTY
                    or tile.building != BuildingType.NONE)
        if active_tool == Tool.WATER_PIPE:
            return (tile.has_water_pipe
                    or tile.zone != ZoneType.EMPTY
                    or tile.building != BuildingType.NONE)
        if active_tool in TOOL_TO_BUILDING:
            return tile.terrain != TerrainType.GRASS or not tile.is_empty
        return False

    def _draw_pedestrians(
        self,
        surface: pygame.Surface,
        camera: Camera,
        pedestrian_system: PedestrianSystem,
        tw: int,
        th: int,
    ) -> None:
        """Draw all walking pedestrians at their current world positions."""
        for ped in pedestrian_system.pedestrians:
            cx, cy  = camera.world_to_screen(ped.x, ped.y)
            cy_center = cy + th // 2
            variant   = abs(int(ped.x * 11 + ped.y * 7))
            self.sprites.draw_pedestrian(surface, cx, cy_center, tw, th, variant)

    def _draw_status_badge(
        self,
        surface: pygame.Surface,
        center: tuple[int, int],
        color: tuple,
        kind: str,
        tile_width: int,
    ) -> None:
        """Draw a small icon badge (power bolt, water drop, flame, badge) on a tile."""
        radius     = max(4, tile_width // 8)
        icon_color = (24, 28, 31)
        pygame.draw.circle(surface, (20, 23, 26), center, radius + 1)
        pygame.draw.circle(surface, color, center, radius)
        if kind == "power":
            pts = [
                (center[0] - radius // 3, center[1] - radius + 1),
                (center[0] + 1,           center[1] - 1),
                (center[0] - 1,           center[1] - 1),
                (center[0] + radius // 3, center[1] + radius - 1),
            ]
            pygame.draw.lines(surface, icon_color, False, pts, max(1, tile_width // 24))
        elif kind == "water":
            pygame.draw.circle(surface, icon_color,
                               (center[0], center[1] + 1), max(1, radius // 3))
            pygame.draw.polygon(surface, icon_color, [
                (center[0],           center[1] - radius + 2),
                (center[0] - radius // 3, center[1]),
                (center[0] + radius // 3, center[1]),
            ])
        elif kind == "fire":
            pygame.draw.polygon(surface, icon_color, [
                (center[0],               center[1] - radius + 2),
                (center[0] - radius // 2, center[1] + radius // 2),
                (center[0] + radius // 2, center[1] + radius // 2),
            ])
        elif kind == "crime":
            pygame.draw.rect(surface, icon_color,
                             pygame.Rect(center[0] - radius // 2, center[1] - radius // 3,
                                         radius, radius),
                             border_radius=1)

    def _same_terrain_neighbors(
        self,
        city_map: CityMap,
        x: int, y: int,
        terrain: TerrainType,
    ) -> dict[str, bool]:
        """Return which of the four neighbors share the same terrain type."""
        return {
            "north": city_map.in_bounds(x,     y - 1) and city_map.get(x,     y - 1).terrain == terrain,
            "east":  city_map.in_bounds(x + 1, y    ) and city_map.get(x + 1, y    ).terrain == terrain,
            "south": city_map.in_bounds(x,     y + 1) and city_map.get(x,     y + 1).terrain == terrain,
            "west":  city_map.in_bounds(x - 1, y    ) and city_map.get(x - 1, y    ).terrain == terrain,
        }


# ------------------------------------------------------------------ #
# Module-level helpers                                                #
# ------------------------------------------------------------------ #

def _rotate_connections(connections: dict, rotation: int) -> dict:
    """
    Rotate a connections dict (north/east/south/west booleans) by `rotation` steps
    clockwise to match the visual direction on screen after a camera rotation.

    Example: at rotation=1, map-north appears visually to the east, so the
    road arm for map-north should be drawn pointing east.
    """
    if rotation == 0:
        return connections
    return {
        _CONN_DIRS[(i + rotation) % 4]: connections.get(_CONN_DIRS[i], False)
        for i in range(4)
    }
