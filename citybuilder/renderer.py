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
from .settings import COLORS, DAY_CYCLE_SECONDS, TILE_SIZE
from .sprites import SpriteAtlas, tile_variant

_MINIMAP_COLOR = {
    "water":       (40,  80, 130),
    "forest":      (30,  70,  40),
    "hill":        (90,  90,  75),
    "grass":       (50, 100,  50),
    "road":        (60,  65,  70),
    "residential": (60, 140,  70),
    "commercial":  (50, 100, 170),
    "industrial":  (170, 140, 60),
    "park":        (40, 160,  80),
    "fire":        (220,  60,  20),
    "building":    (140, 120, 100),
}


# Maps BuildingType to the color key in COLORS (settings.py)
BUILDING_COLOR_KEYS = {
    BuildingType.POWER_PLANT:       "power",
    BuildingType.LARGE_POWER_PLANT: "power",
    BuildingType.WATER_TOWER:       "water",
    BuildingType.LARGE_WATER_TOWER: "water",
    BuildingType.POLICE:            "police",
    BuildingType.FIRE:              "fire",
    BuildingType.SCHOOL:            "school",
    BuildingType.HOSPITAL:          "hospital",
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
        self._mm_surf: pygame.Surface | None = None
        self._mm_last_update: int = -9999
        self._night_overlay: pygame.Surface | None = None
        self._night_overlay_size: tuple[int, int] = (0, 0)
        self.minimap_rect: pygame.Rect | None = None
        self.day_night_enabled: bool = False

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

        utility_network: set[tuple[int, int]] | None = None
        if view_mode == ViewMode.POWER:
            utility_network = self._connected_utility_network(city_map, POWER_SOURCE_BUILDINGS, "has_power_line")
        elif view_mode == ViewMode.WATER:
            utility_network = self._connected_utility_network(city_map, WATER_SOURCE_BUILDINGS, "has_water_pipe")

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
            self._draw_tile(surface, city_map, tile, mx, my, cx, cy, tw, th, view_mode, rot, utility_network)

        # Draw hover highlight over the tile under the mouse cursor
        if hover_tile and city_map.in_bounds(*hover_tile):
            hx, hy = hover_tile
            cx, cy = camera.world_to_screen(hx, hy)
            self._draw_hover(surface, city_map, active_tool, hover_tile, cx, cy, tw, th)

        # Draw walking pedestrians (only in normal view)
        if pedestrian_system is not None and view_mode == ViewMode.NORMAL:
            self._draw_pedestrians(surface, camera, pedestrian_system, tw, th)

        # Day/night cycle overlay (only when enabled in settings)
        if self.day_night_enabled:
            self._draw_day_night(surface, camera.viewport)

        # Minimap in top-right corner
        self._draw_minimap(surface, city_map, camera)

        # Thin border around the map area
        pygame.draw.rect(surface, (20, 24, 28), camera.viewport, width=2)
        surface.set_clip(old_clip)

    # ------------------------------------------------------------------ #
    # Day/night cycle                                                      #
    # ------------------------------------------------------------------ #

    def _draw_day_night(self, surface: pygame.Surface, viewport: pygame.Rect) -> None:
        t = (pygame.time.get_ticks() / (DAY_CYCLE_SECONDS * 1000)) % 1.0
        if t < 0.30 or t >= 0.92:
            return  # full daylight

        if t < 0.45:                   # dusk: 0.30 → 0.45
            p = (t - 0.30) / 0.15
            col = (int(50 * p), int(20 * p), int(8 * p))
            alpha = int(90 * p)
        elif t < 0.75:                  # night: 0.45 → 0.75
            col = (8, 12, 55)
            alpha = 130
        else:                           # dawn: 0.75 → 0.92
            p = 1.0 - (t - 0.75) / 0.17
            col = (int(8 * p), int(12 * p), int(55 * p))
            alpha = int(130 * p)

        sz = (viewport.width, viewport.height)
        if self._night_overlay is None or self._night_overlay_size != sz:
            self._night_overlay = pygame.Surface(sz)
            self._night_overlay_size = sz
        self._night_overlay.fill(col)
        self._night_overlay.set_alpha(alpha)
        surface.blit(self._night_overlay, viewport.topleft)

    # ------------------------------------------------------------------ #
    # Minimap                                                              #
    # ------------------------------------------------------------------ #

    def _minimap_tile_color(self, tile) -> tuple:
        if tile.on_fire:
            return _MINIMAP_COLOR["fire"]
        if tile.building.value != "none":
            return _MINIMAP_COLOR["building"]
        if tile.has_road:
            return _MINIMAP_COLOR["road"]
        if tile.zone.value != "empty":
            return _MINIMAP_COLOR.get(tile.zone.value, _MINIMAP_COLOR["building"])
        return _MINIMAP_COLOR.get(tile.terrain.value, _MINIMAP_COLOR["grass"])

    def _draw_minimap(self, surface: pygame.Surface, city_map, camera) -> None:
        mm_w = min(city_map.width, 128)
        mm_h = min(city_map.height, 96)
        vp = camera.viewport
        mm_x = vp.right - mm_w - 14
        mm_y = vp.top + 14

        now = pygame.time.get_ticks()
        if self._mm_surf is None or self._mm_surf.get_size() != (mm_w, mm_h) or now - self._mm_last_update > 2000:
            self._mm_surf = pygame.Surface((mm_w, mm_h))
            scale_x = mm_w / city_map.width
            scale_y = mm_h / city_map.height
            for mx, my, tile in city_map.iter_tiles():
                px = int(mx * scale_x)
                py = int(my * scale_y)
                self._mm_surf.set_at((min(mm_w - 1, px), min(mm_h - 1, py)), self._minimap_tile_color(tile))
            self._mm_last_update = now

        pad = 4
        bg = pygame.Surface((mm_w + pad * 2, mm_h + pad * 2))
        bg.fill((8, 10, 14))
        bg.set_alpha(200)
        surface.blit(bg, (mm_x - pad, mm_y - pad))
        surface.blit(self._mm_surf, (mm_x, mm_y))

        self.minimap_rect = pygame.Rect(mm_x - pad, mm_y - pad, mm_w + pad * 2, mm_h + pad * 2)

        try:
            sx, sy, ex, ey = camera.visible_tile_bounds(TILE_SIZE, city_map.width, city_map.height)
            scale_x = mm_w / city_map.width
            scale_y = mm_h / city_map.height
            corners_rot = [(sx, sy), (ex, sy), (ex, ey), (sx, ey)]
            corners_mm = []
            for rx, ry in corners_rot:
                mxc, myc = camera._unapply_rotation(rx, ry)
                mxc = max(0, min(city_map.width - 1, mxc))
                myc = max(0, min(city_map.height - 1, myc))
                corners_mm.append((mm_x + int(mxc * scale_x), mm_y + int(myc * scale_y)))
            if len(corners_mm) >= 3:
                pygame.draw.polygon(surface, (255, 255, 255), corners_mm, 1)
        except Exception:
            pass

        pygame.draw.rect(surface, (60, 80, 100), (mm_x - pad, mm_y - pad, mm_w + pad * 2, mm_h + pad * 2), 1)

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
        utility_network: set[tuple[int, int]] | None = None,
    ) -> None:
        """Draw one tile: terrain first, then whatever sits on top of it."""

        # Water tiles need to know their neighbors to draw shore edges correctly
        same_nbrs = None
        if tile.terrain == TerrainType.WATER:
            same_nbrs = self._same_terrain_neighbors(city_map, x, y, tile.terrain)
        self.sprites.draw_terrain(surface, cx, cy, tw, th, tile.terrain, x, y, same_nbrs)

        # Special view modes (power, water, fire, police) get their own overlay
        if view_mode != ViewMode.NORMAL:
            self._draw_view_overlay(surface, city_map, tile, x, y, cx, cy, tw, th, view_mode, rotation, utility_network)
            return

        # --- Normal view ---
        if tile.has_road:
            conn = _rotate_connections(city_map.road_connections(x, y), rotation)
            self.sprites.draw_road(surface, cx, cy, tw, th, conn)
        elif tile.building != BuildingType.NONE:
            self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)
        elif tile.zone != ZoneType.EMPTY:
            rec_type = tile.recreation_type if tile.zone == ZoneType.PARK else None
            self.sprites.draw_zone_base(surface, cx, cy, tw, th, tile.zone, tile.zone_level, rec_type)
            if tile.development > 0.05:
                self.sprites.draw_building(
                    surface, cx, cy, tw, th,
                    tile.zone, tile.development, tile.zone_level,
                    tile_variant(x, y), rotation, rec_type,
                )
            if tile.on_fire:
                self.sprites.draw_fire_overlay(surface, cx, cy, tw, th)
            else:
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
        utility_network: set[tuple[int, int]] | None = None,
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
                if not tile.powered:
                    self._draw_status_badge(surface, (cx, cy + th // 2), COLORS["power"], "power", tw)
            if tile.building in POWER_SOURCE_BUILDINGS:
                self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)
            elif tile.building != BuildingType.NONE:
                self._draw_marker_dot(surface, cx, cy, tw, th, tile.building)
            if tile.has_power_line:
                conn = _rotate_connections(city_map.power_connections(x, y), rotation)
                connected = utility_network is not None and (x, y) in utility_network
                self._draw_power_line_iso(surface, cx, cy, tw, th, conn, connected)

        elif view_mode == ViewMode.WATER:
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK):
                c = (45, 80, 100, 138) if tile.watered else (110, 58, 58, 138)
                self._draw_diam_overlay(surface, cx, cy, tw, th, c)
                if not tile.watered:
                    self._draw_status_badge(surface, (cx, cy + th // 2), COLORS["water"], "water", tw)
            if tile.building in WATER_SOURCE_BUILDINGS:
                self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)
            elif tile.building != BuildingType.NONE:
                self._draw_marker_dot(surface, cx, cy, tw, th, tile.building)
            if tile.has_water_pipe:
                conn = _rotate_connections(city_map.water_connections(x, y), rotation)
                connected = utility_network is not None and (x, y) in utility_network
                self._draw_water_pipe_iso(surface, cx, cy, tw, th, conn, connected)

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
        connected: bool = True,
    ) -> None:
        """Draw the power line pole and wires for a single tile."""
        hw, hh   = tw // 2, th // 2
        center   = (cx, cy + hh)
        pole_h   = max(3, th // 2)
        pole_top = (cx, cy + hh - pole_h)
        pole_c   = (230, 210, 80) if connected else (226, 96, 84)
        shadow_c = (74, 59, 42) if connected else (92, 45, 43)
        lw       = max(1, tw // 20)

        pygame.draw.line(surface, shadow_c, (center[0] + 1, center[1] + 1), (pole_top[0] + 1, pole_top[1] + 1), lw + 1)
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
                pygame.draw.line(surface, shadow_c, (pole_top[0] + 1, pole_top[1] + 1), (ep[0] + 1, ep[1] + 1), max(1, tw // 28) + 1)
                pygame.draw.line(surface, pole_c, pole_top, ep, max(1, tw // 28))
        if not connected and tw >= 18:
            self._draw_status_badge(surface, (cx, cy + hh), (226, 96, 84), "power", tw)

    def _draw_water_pipe_iso(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        connections: dict,
        connected: bool = True,
    ) -> None:
        """Draw the water pipe node and segments for a single tile."""
        hw, hh  = tw // 2, th // 2
        center  = (cx, cy + hh)
        pipe_c  = (80, 178, 230) if connected else (226, 96, 84)
        shadow_c = (35, 82, 108) if connected else (92, 45, 43)
        lw      = max(1, tw // 18)
        r       = max(2, tw // 14)

        pygame.draw.circle(surface, shadow_c, (center[0] + 1, center[1] + 1), r + 1)
        pygame.draw.circle(surface, pipe_c, center, r)

        edge_mids = {
            "north": (cx + hw // 2, cy + hh // 2),
            "east":  (cx + hw // 2, cy + th - hh // 2),
            "south": (cx - hw // 2, cy + th - hh // 2),
            "west":  (cx - hw // 2, cy + hh // 2),
        }
        for direction, ep in edge_mids.items():
            if connections.get(direction, False):
                pygame.draw.line(surface, shadow_c, (center[0] + 1, center[1] + 1), (ep[0] + 1, ep[1] + 1), lw + 1)
                pygame.draw.line(surface, pipe_c, center, ep, lw)
        if not connected and tw >= 18:
            self._draw_status_badge(surface, (cx, cy + hh), (226, 96, 84), "water", tw)

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
        if active_tool in (Tool.PLAYGROUND, Tool.SPORTS_FIELD, Tool.STADIUM,
                           Tool.GOLF_COURSE, Tool.POOL, Tool.CINEMA, Tool.MUSEUM, Tool.ZOO):
            return (
                tile.terrain != TerrainType.GRASS
                or tile.has_road
                or tile.has_power_line
                or tile.has_water_pipe
                or tile.building != BuildingType.NONE
            )
        if active_tool == Tool.ROAD:
            return tile.has_road or tile.zone != ZoneType.EMPTY or tile.building != BuildingType.NONE
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

    def _connected_utility_network(
        self,
        city_map: CityMap,
        source_buildings: set[BuildingType],
        line_attr: str,
    ) -> set[tuple[int, int]]:
        starts = [
            (x, y)
            for x, y, tile in city_map.iter_tiles()
            if tile.building in source_buildings
        ]
        network = set(starts)
        frontier = list(starts)

        while frontier:
            x, y = frontier.pop()
            for nx, ny, neighbor in city_map.neighbors4(x, y):
                if (nx, ny) in network:
                    continue
                if getattr(neighbor, line_attr) or neighbor.building in source_buildings:
                    network.add((nx, ny))
                    frontier.append((nx, ny))

        return network

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
