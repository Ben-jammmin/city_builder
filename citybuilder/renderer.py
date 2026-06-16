"""
renderer.py — Draws the city map onto the screen.

The renderer iterates over visible tiles and draws them in back-to-front order
(painter's algorithm) so buildings overlap correctly in the isometric view.

Painter's algorithm
-------------------
In isometric view, the tile at (x + y = smallest value) is furthest from the
viewer, so it must be drawn first.  We iterate diagonal bands of constant
(x + y), increasing, so each band naturally overlaps the previous one.

Drawing order per tile:
  1. Terrain (grass, water, forest, hill)
  2. Zone base (coloured lot indicator)
  3. Road  OR  civic building  OR  zone building
  4. Fire overlay (if burning)
  5. Status badges (no power, no water, high fire risk, high crime)

Special view modes (Power, Water, Fire, Police) skip step 3 and instead
draw tinted diamond overlays and the relevant infrastructure.
"""

from __future__ import annotations

import pygame

from .camera import Camera
from .city_map import CityMap
from .models import (
    POWER_SOURCE_BUILDINGS, TOOL_TO_BUILDING, TOOL_TO_RECREATION, TOOL_TO_ZONE,
    WATER_SOURCE_BUILDINGS,
    BuildingType, RecreationType, TerrainType, Tool, ViewMode, ZoneType,
)
from .pedestrian import PedestrianSystem
from .settings import COLORS, DAY_CYCLE_SECONDS, HIGH_RISK_THRESHOLD, TILE_SIZE
from .sprites import SpriteAtlas, tile_variant

# ── Minimap colour palette ─────────────────────────────────────────────────────
# Flat colours used for the small overview map in the top-right corner.
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

# Maps BuildingType to the colour key in COLORS (settings.py).
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

# Which building types are "main" for each special view mode (shown at full size).
VIEW_MAIN_BUILDINGS = {
    ViewMode.POWER:  POWER_SOURCE_BUILDINGS,
    ViewMode.WATER:  WATER_SOURCE_BUILDINGS,
    ViewMode.FIRE:   {BuildingType.FIRE},
    ViewMode.POLICE: {BuildingType.POLICE},
}

# Direction names in order — used when rotating the connection dict.
_CONN_DIRS = ["north", "east", "south", "west"]


class Renderer:
    """Handles all map drawing — terrain, buildings, roads, overlays, pedestrians."""

    def __init__(self) -> None:
        self.small_font = pygame.font.SysFont("Segoe UI", 13)
        self.sprites = SpriteAtlas(self.small_font)
        # Minimap: cached surface and update timer (rebuilt every ~2 seconds).
        self._mm_surf: pygame.Surface | None = None
        self._mm_last_update: int = -9999
        # Night overlay surface (reused to avoid allocating each frame).
        self._night_overlay: pygame.Surface | None = None
        self._night_overlay_size: tuple[int, int] = (0, 0)
        # Reusable transparent surface for drawing tile-shaped overlays.
        self._diam_overlay: pygame.Surface | None = None
        self._diam_overlay_size: tuple[int, int] = (0, 0)
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

        Painter's algorithm: iterates tiles in back-to-front order (increasing
        x + y in rotated space) so nearby tiles correctly overlap far ones.
        """
        pygame.draw.rect(surface, COLORS["background"], camera.viewport)

        # Clip drawing to the map viewport so nothing spills into the sidebar.
        old_clip = surface.get_clip()
        surface.set_clip(camera.viewport)

        # Tile dimensions in pixels at the current zoom level.
        tw = max(4, int(camera.tile_w * camera.zoom))
        th = max(2, int(camera.tile_h * camera.zoom))

        # Pre-compute the utility network for Power/Water view overlays.
        utility_network: set[tuple[int, int]] | None = None
        if view_mode == ViewMode.POWER:
            utility_network = self._connected_utility_network(city_map, POWER_SOURCE_BUILDINGS, "has_power_line")
        elif view_mode == ViewMode.WATER:
            utility_network = self._connected_utility_network(city_map, WATER_SOURCE_BUILDINGS, "has_water_pipe")

        # Ask the camera which tile range is currently visible, to skip off-screen tiles.
        start_x, start_y, end_x, end_y = camera.visible_tile_bounds(
            TILE_SIZE, city_map.width, city_map.height
        )

        rot = camera.rotation

        # Draw tiles in painter's back-to-front order for the current rotation.
        for x, y in self._iter_painter_order(start_x, start_y, end_x, end_y, rot):
            # Convert from rotated iteration coords to real map coords.
            mx, my = camera._unapply_rotation(x, y)
            if not city_map.in_bounds(mx, my):
                continue
            tile = city_map.get(mx, my)
            cx, cy = camera.world_to_screen(mx, my)
            self._draw_tile(surface, city_map, tile, mx, my, cx, cy, tw, th, view_mode, rot, utility_network)

        # Draw hover highlight on top of everything else.
        if hover_tile is not None and city_map.in_bounds(*hover_tile):
            hx, hy = hover_tile
            cx, cy = camera.world_to_screen(hx, hy)
            self._draw_hover(surface, city_map, active_tool, hover_tile, cx, cy, tw, th)

        # Pedestrians only show in normal view (not on top of overlay modes).
        if pedestrian_system is not None and view_mode == ViewMode.NORMAL:
            self._draw_pedestrians(surface, camera, pedestrian_system, tw, th)

        # Day/night cycle darkens the screen periodically (toggled by the player).
        if self.day_night_enabled:
            self._draw_day_night(surface, camera.viewport)

        # Minimap in the top-right corner of the viewport.
        self._draw_minimap(surface, city_map, camera)

        # Thin border around the map viewport area.
        pygame.draw.rect(surface, (20, 24, 28), camera.viewport, width=2)
        surface.set_clip(old_clip)

    # ── Day/night cycle ────────────────────────────────────────────────────────

    def _draw_day_night(self, surface: pygame.Surface, viewport: pygame.Rect) -> None:
        """
        Draws a semi-transparent colour wash to simulate time of day.

        t goes from 0.0 to 1.0 over one full DAY_CYCLE_SECONDS cycle.
        Phases:
          0.00-0.30  → full daylight (no overlay)
          0.30-0.45  → dusk (orange tint, growing alpha)
          0.45-0.75  → night (dark blue, full alpha)
          0.75-0.92  → dawn (dark blue fading out)
        """
        t = (pygame.time.get_ticks() / (DAY_CYCLE_SECONDS * 1000)) % 1.0
        if t < 0.30 or t >= 0.92:
            return  # full daylight — nothing to draw

        if t < 0.45:                   # dusk: 0.30 → 0.45
            p = (t - 0.30) / 0.15     # 0→1 progress through dusk
            col = (int(50 * p), int(20 * p), int(8 * p))
            alpha = int(90 * p)
        elif t < 0.75:                  # night: 0.45 → 0.75
            col = (8, 12, 55)
            alpha = 130
        else:                           # dawn: 0.75 → 0.92
            p = 1.0 - (t - 0.75) / 0.17   # 1→0 progress through dawn
            col = (int(8 * p), int(12 * p), int(55 * p))
            alpha = int(130 * p)

        sz = (viewport.width, viewport.height)
        # Reuse the overlay surface if its size hasn't changed.
        if self._night_overlay is None or self._night_overlay_size != sz:
            self._night_overlay = pygame.Surface(sz)
            self._night_overlay_size = sz
        self._night_overlay.fill(col)
        self._night_overlay.set_alpha(alpha)
        surface.blit(self._night_overlay, viewport.topleft)

    # ── Minimap ────────────────────────────────────────────────────────────────

    def _minimap_tile_color(self, tile) -> tuple:
        """Picks the flat minimap colour for a tile (fires and buildings take priority)."""
        if tile.on_fire:
            return _MINIMAP_COLOR["fire"]
        if tile.building != BuildingType.NONE:
            return _MINIMAP_COLOR["building"]
        if tile.has_road:
            return _MINIMAP_COLOR["road"]
        if tile.zone != ZoneType.EMPTY:
            return _MINIMAP_COLOR.get(tile.zone.value, _MINIMAP_COLOR["building"])
        return _MINIMAP_COLOR.get(tile.terrain.value, _MINIMAP_COLOR["grass"])

    def _draw_minimap(self, surface: pygame.Surface, city_map, camera) -> None:
        """
        Draws a small overview map in the top-right corner of the viewport.

        The map surface is re-rendered at most every 2 seconds for performance.
        A white polygon shows the area currently visible in the main camera.
        """
        mm_w = min(city_map.width, 128)
        mm_h = min(city_map.height, 96)
        vp = camera.viewport
        mm_x = vp.right - mm_w - 14
        mm_y = vp.top + 14

        now = pygame.time.get_ticks()
        # Rebuild the minimap pixel-by-pixel if it is stale or the wrong size.
        if self._mm_surf is None or self._mm_surf.get_size() != (mm_w, mm_h) or now - self._mm_last_update > 2000:
            self._mm_surf = pygame.Surface((mm_w, mm_h))
            scale_x = mm_w / city_map.width
            scale_y = mm_h / city_map.height
            for mx, my, tile in city_map.iter_tiles():
                px = int(mx * scale_x)
                py = int(my * scale_y)
                self._mm_surf.set_at((min(mm_w - 1, px), min(mm_h - 1, py)), self._minimap_tile_color(tile))
            self._mm_last_update = now

        # Dark background panel behind the minimap.
        pad = 4
        bg = pygame.Surface((mm_w + pad * 2, mm_h + pad * 2))
        bg.fill((8, 10, 14))
        bg.set_alpha(200)
        surface.blit(bg, (mm_x - pad, mm_y - pad))
        surface.blit(self._mm_surf, (mm_x, mm_y))

        self.minimap_rect = pygame.Rect(mm_x - pad, mm_y - pad, mm_w + pad * 2, mm_h + pad * 2)

        try:
            # Draw a white polygon showing the current camera viewport on the minimap.
            sx, sy, ex, ey = camera.visible_tile_bounds(TILE_SIZE, city_map.width, city_map.height)
            scale_x = mm_w / city_map.width
            scale_y = mm_h / city_map.height
            corners_rot = [(sx, sy), (ex, sy), (ex, ey), (sx, ey)]
            corners_mm = []
            for rx, ry in corners_rot:
                # Convert rotated tile coords back to map coords for correct minimap placement.
                mxc, myc = camera._unapply_rotation(rx, ry)
                mxc = max(0, min(city_map.width - 1, mxc))
                myc = max(0, min(city_map.height - 1, myc))
                corners_mm.append((mm_x + int(mxc * scale_x), mm_y + int(myc * scale_y)))
            if len(corners_mm) >= 3:
                pygame.draw.polygon(surface, (255, 255, 255), corners_mm, 1)
        except Exception:
            pass   # if bounds fail for any reason, skip the viewport indicator

        pygame.draw.rect(surface, (60, 80, 100), (mm_x - pad, mm_y - pad, mm_w + pad * 2, mm_h + pad * 2), 1)

    # ── Per-tile drawing ───────────────────────────────────────────────────────

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
        """Draws one tile: terrain first, then whatever infrastructure sits on top."""

        # Water tiles check their neighbours so shore edges can be drawn correctly.
        same_nbrs = None
        if tile.terrain == TerrainType.WATER:
            same_nbrs = self._same_terrain_neighbors(city_map, x, y, tile.terrain)
        self.sprites.draw_terrain(surface, cx, cy, tw, th, tile.terrain, x, y, same_nbrs)

        # Special view modes draw tinted overlays instead of the normal buildings.
        if view_mode != ViewMode.NORMAL:
            self._draw_view_overlay(surface, city_map, tile, x, y, cx, cy, tw, th, view_mode, rotation, utility_network)
            return

        # ── Normal view ──────────────────────────────────────────────────────
        if tile.has_road:
            # Roads connect visually to their neighbours — rotate the connection dict
            # to match the current camera orientation.
            conn = _rotate_connections(city_map.road_connections(x, y), rotation)
            self.sprites.draw_road(surface, cx, cy, tw, th, conn)
        elif tile.building != BuildingType.NONE:
            self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)
        elif tile.zone != ZoneType.EMPTY:
            rec_type = tile.recreation_type if tile.zone == ZoneType.PARK else None
            # Draw the coloured base lot.
            self.sprites.draw_zone_base(surface, cx, cy, tw, th, tile.zone, tile.zone_level, rec_type)
            if tile.development > 0.05:
                # Draw the building that has grown on this lot.
                self.sprites.draw_building(
                    surface, cx, cy, tw, th,
                    tile.zone, tile.development, tile.zone_level,
                    tile_variant(x, y), rotation, rec_type,
                )
            if tile.on_fire:
                self.sprites.draw_fire_overlay(surface, cx, cy, tw, th)
            else:
                # Show small warning icons for utility/risk problems.
                self._draw_zone_status_iso(surface, cx, cy, tw, th, tile)

        # Power lines and water pipes are invisible in normal view.
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
        Draws tile contents for a special view mode (power, water, fire, police).
        Each mode tints zone tiles green (OK) or red (problem) and shows relevant
        infrastructure that is normally hidden in the default view.
        """
        # Roads always show so the player can navigate in any view mode.
        if tile.has_road:
            conn = _rotate_connections(city_map.road_connections(x, y), rotation)
            self.sprites.draw_road(surface, cx, cy, tw, th, conn)

        if view_mode == ViewMode.TERRAIN:
            # Terrain view: tint zones but still show buildings.
            if tile.zone != ZoneType.EMPTY:
                zone_c = COLORS.get(tile.zone.value, (100, 100, 100))
                self._draw_diam_overlay(surface, cx, cy, tw, th, (*zone_c, 75))
            if tile.building != BuildingType.NONE:
                self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)

        elif view_mode == ViewMode.POWER:
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK):
                # Warm tint = powered; red tint = no power.
                c = (92, 82, 50, 138) if tile.powered else (120, 55, 55, 138)
                self._draw_diam_overlay(surface, cx, cy, tw, th, c)
                if not tile.powered:
                    self._draw_status_badge(surface, (cx, cy + th // 2), COLORS["power"], "power", tw)
            if tile.building in POWER_SOURCE_BUILDINGS:
                self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)
            elif tile.building != BuildingType.NONE:
                # Other buildings shown as small dots so the power network stays readable.
                self._draw_marker_dot(surface, cx, cy, tw, th, tile.building)
            if tile.has_power_line:
                conn = _rotate_connections(city_map.power_connections(x, y), rotation)
                connected = utility_network is not None and (x, y) in utility_network
                self._draw_power_line_iso(surface, cx, cy, tw, th, conn, connected)

        elif view_mode == ViewMode.WATER:
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK):
                # Blue tint = watered; red tint = no water.
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
                # Colour depends on fire risk level and whether fire station covers the tile.
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

    # ── Painter's algorithm tile iteration ────────────────────────────────────

    def _iter_painter_order(
        self,
        sx: int, sy: int,
        ex: int, ey: int,
        rotation: int,
    ):
        """
        Yields (x, y) tile indices in back-to-front draw order.

        In an isometric projection the screen Y of a tile is proportional to
        (rotated_x + rotated_y).  Tiles on the same diagonal have the same
        depth, so we iterate diagonals of constant (x + y) in increasing order.
        This works correctly for any camera rotation because tile coordinates
        are already in rotated space when this function is called.
        """
        for total in range(sx + sy, ex + ey - 1):
            x_lo = max(sx, total - (ey - 1))
            x_hi = min(ex - 1, total - sy)
            for x in range(x_lo, x_hi + 1):
                yield x, total - x

    # ── Drawing helpers ────────────────────────────────────────────────────────

    def _draw_diam_overlay(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        color: tuple,
    ) -> None:
        """Draws a translucent diamond-shaped overlay on a tile (used for view-mode tints)."""
        hw, hh = tw // 2, th // 2
        # Reuse the transparent surface if the tile size hasn't changed.
        if self._diam_overlay_size != (tw, th):
            self._diam_overlay = pygame.Surface((tw, th), pygame.SRCALPHA)
            self._diam_overlay_size = (tw, th)
        self._diam_overlay.fill((0, 0, 0, 0))   # clear to transparent
        pygame.draw.polygon(self._diam_overlay, color, [(hw, 0), (tw, hh), (hw, th), (0, hh)])
        surface.blit(self._diam_overlay, (cx - hw, cy))

    def _draw_marker_dot(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        building: BuildingType,
    ) -> None:
        """Draws a small coloured dot for a non-primary building in an overlay view."""
        if tw < 10:
            return
        ck    = BUILDING_COLOR_KEYS.get(building, "building_dark")
        color = COLORS.get(ck, (100, 100, 100))
        r      = max(4, tw // 8)
        center = (cx, cy + th // 2)
        # Dark outline then coloured fill.
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
        """Draws the diamond outline under the mouse cursor (white if valid, red if blocked)."""
        x, y   = hover_tile
        tile   = city_map.get(x, y)
        blocked = self._tool_blocked(tile, active_tool)
        color  = COLORS["hover_blocked"] if blocked else COLORS["hover_ok"]
        hw, hh = tw // 2, th // 2
        # Drop shadow slightly below and to the right.
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
        """Shows small warning badges on zoned tiles that have utility or risk problems."""
        if tw < 18 or tile.zone == ZoneType.PARK:
            return
        hh     = th // 2
        center = (cx, cy + hh)
        r      = max(4, tw // 8)
        # Four badge positions around the tile centre.
        if not tile.powered:
            self._draw_status_badge(surface, (center[0] - r, center[1] - r // 2),
                                    COLORS["power"], "power", tw)
        if not tile.watered:
            self._draw_status_badge(surface, (center[0] + r, center[1] - r // 2),
                                    COLORS["water"], "water", tw)
        if tile.fire_risk >= HIGH_RISK_THRESHOLD:
            self._draw_status_badge(surface, (center[0] - r, center[1] + r // 2),
                                    COLORS["fire"], "fire", tw)
        if tile.crime_risk >= HIGH_RISK_THRESHOLD:
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
        """Draws the power line pole and wires for a single tile."""
        hw, hh   = tw // 2, th // 2
        center   = (cx, cy + hh)
        pole_h   = max(3, th // 2)
        pole_top = (cx, cy + hh - pole_h)
        # Yellow when connected; red when disconnected from a power source.
        pole_c   = (230, 210, 80) if connected else (226, 96, 84)
        shadow_c = (74, 59, 42) if connected else (92, 45, 43)
        lw       = max(1, tw // 20)

        # Draw pole with drop shadow.
        pygame.draw.line(surface, shadow_c, (center[0] + 1, center[1] + 1), (pole_top[0] + 1, pole_top[1] + 1), lw + 1)
        pygame.draw.line(surface, pole_c, center, pole_top, lw)

        # Wire attachment points at the midpoint of each diamond edge.
        edge_mids = {
            "north": (cx + hw // 2, cy + hh // 2),
            "east":  (cx + hw // 2, cy + th - hh // 2),
            "south": (cx - hw // 2, cy + th - hh // 2),
            "west":  (cx - hw // 2, cy + hh // 2),
        }
        for direction, ep in edge_mids.items():
            if connections.get(direction, False):
                # Wire shadow then wire.
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
        """Draws the water pipe node and connecting segments for a single tile."""
        hw, hh  = tw // 2, th // 2
        center  = (cx, cy + hh)
        # Blue when connected; red when disconnected.
        pipe_c  = (80, 178, 230) if connected else (226, 96, 84)
        shadow_c = (35, 82, 108) if connected else (92, 45, 43)
        lw      = max(1, tw // 18)
        r       = max(2, tw // 14)

        # Central node circle.
        pygame.draw.circle(surface, shadow_c, (center[0] + 1, center[1] + 1), r + 1)
        pygame.draw.circle(surface, pipe_c, center, r)

        # Pipe segments running to the edge midpoints of adjacent connected tiles.
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
        """Returns an RGBA overlay colour for a fire or crime risk level."""
        if risk >= HIGH_RISK_THRESHOLD:
            return (142, 57, 53, 148)    # bright red = high risk
        if risk >= 40:
            return (142, 111, 58, 128)   # orange = moderate risk
        if covered:
            return (62, 105, 76, 110)    # muted green = covered and low risk
        return (83, 84, 72, 90)          # grey = uncovered but low risk

    def _tool_blocked(self, tile, active_tool: Tool) -> bool:
        """Returns True if the active tool cannot legally be placed on this tile."""
        if active_tool == Tool.BULLDOZE:
            # Bulldoze is only blocked on tiles that are already plain grass.
            return tile.is_empty and tile.terrain == TerrainType.GRASS
        if tile.terrain == TerrainType.WATER and active_tool not in (Tool.INSPECT, Tool.BULLDOZE):
            return True   # can't build on water (except to bulldoze it)
        if active_tool in (Tool.RESIDENTIAL, Tool.COMMERCIAL, Tool.INDUSTRIAL,
                           Tool.DENSE_RESIDENTIAL, Tool.DENSE_COMMERCIAL):
            zone, level = TOOL_TO_ZONE[active_tool]
            return (
                tile.terrain != TerrainType.GRASS
                or tile.has_road
                or tile.has_power_line
                or tile.has_water_pipe
                or tile.building != BuildingType.NONE
                or (tile.zone == zone and tile.zone_level == level)
            )
        if active_tool == Tool.PARK:
            return (
                tile.terrain != TerrainType.GRASS
                or tile.has_road
                or tile.has_power_line
                or tile.has_water_pipe
                or tile.building != BuildingType.NONE
                or (tile.zone == ZoneType.PARK and tile.recreation_type == RecreationType.PARK)
            )
        if active_tool in (Tool.PLAYGROUND, Tool.SPORTS_FIELD, Tool.STADIUM,
                           Tool.GOLF_COURSE, Tool.POOL, Tool.CINEMA, Tool.MUSEUM, Tool.ZOO):
            rec_type = TOOL_TO_RECREATION.get(active_tool)
            return (
                tile.terrain != TerrainType.GRASS
                or tile.has_road
                or tile.has_power_line
                or tile.has_water_pipe
                or tile.building != BuildingType.NONE
                or (tile.zone == ZoneType.PARK and tile.recreation_type == rec_type)
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
        """
        Flood-fill (BFS) from source buildings through connected lines.
        Used in Power/Water view to colour lines red when they're disconnected.
        """
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
        """Draws all walking pedestrians at their current world-space tile positions."""
        for ped in pedestrian_system.pedestrians:
            cx, cy  = camera.world_to_screen(ped.x, ped.y)
            # Place pedestrian at the vertical centre of the tile (the ground plane).
            cy_center = cy + th // 2
            # Derive a stable variant index from the pedestrian's position.
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
        """
        Draws a small circular icon badge on a tile to indicate a problem.

        kind selects the icon shape:
          "power"  → lightning bolt
          "water"  → water drop
          "fire"   → flame triangle
          "crime"  → square badge
        """
        radius     = max(4, tile_width // 8)
        icon_color = (24, 28, 31)
        # Dark shadow ring then coloured circle.
        pygame.draw.circle(surface, (20, 23, 26), center, radius + 1)
        pygame.draw.circle(surface, color, center, radius)
        if kind == "power":
            # Lightning bolt shape.
            pts = [
                (center[0] - radius // 3, center[1] - radius + 1),
                (center[0] + 1,           center[1] - 1),
                (center[0] - 1,           center[1] - 1),
                (center[0] + radius // 3, center[1] + radius - 1),
            ]
            pygame.draw.lines(surface, icon_color, False, pts, max(1, tile_width // 24))
        elif kind == "water":
            # Teardrop shape: small circle below a triangle.
            pygame.draw.circle(surface, icon_color,
                               (center[0], center[1] + 1), max(1, radius // 3))
            pygame.draw.polygon(surface, icon_color, [
                (center[0],           center[1] - radius + 2),
                (center[0] - radius // 3, center[1]),
                (center[0] + radius // 3, center[1]),
            ])
        elif kind == "fire":
            # Simple upward triangle.
            pygame.draw.polygon(surface, icon_color, [
                (center[0],               center[1] - radius + 2),
                (center[0] - radius // 2, center[1] + radius // 2),
                (center[0] + radius // 2, center[1] + radius // 2),
            ])
        elif kind == "crime":
            # Small rectangle badge (like a wanted notice).
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
        """
        Returns which of the four orthogonal neighbours share the same terrain type.
        Used by the water tile renderer to decide where to draw shore edges.
        """
        return {
            "north": city_map.in_bounds(x,     y - 1) and city_map.get(x,     y - 1).terrain == terrain,
            "east":  city_map.in_bounds(x + 1, y    ) and city_map.get(x + 1, y    ).terrain == terrain,
            "south": city_map.in_bounds(x,     y + 1) and city_map.get(x,     y + 1).terrain == terrain,
            "west":  city_map.in_bounds(x - 1, y    ) and city_map.get(x - 1, y    ).terrain == terrain,
        }


# ── Module-level helpers ───────────────────────────────────────────────────────

def _rotate_connections(connections: dict, rotation: int) -> dict:
    """
    Rotates a connections dict (north/east/south/west booleans) by `rotation`
    steps clockwise so road arms point in the correct visual direction on screen.

    Example: at rotation=1 the map is rotated 90° CW, so what was map-north
    now appears visually to the east.  The road arm for that direction should
    therefore be drawn pointing east.
    """
    if rotation == 0:
        return connections
    # Shift each direction index by `rotation` positions in the cyclic direction list.
    return {
        _CONN_DIRS[(i + rotation) % 4]: connections.get(_CONN_DIRS[i], False)
        for i in range(4)
    }
