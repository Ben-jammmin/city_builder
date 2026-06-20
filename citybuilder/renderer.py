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

import math
import pygame

from .camera import Camera
from .city_map import CityMap
from .models import (
    POWER_SOURCE_BUILDINGS, TOOL_TO_BUILDING, TOOL_TO_RECREATION, TOOL_TO_ZONE,
    WATER_SOURCE_BUILDINGS,
    BuildingType, RecreationType, TerrainType, Tool, ViewMode, ZoneType,
)
from .pedestrian import PedestrianSystem
from .settings import (
    COLORS, DAY_CYCLE_SECONDS, HIGH_RISK_THRESHOLD,
    LAND_VALUE_MIN, LAND_VALUE_MAX,
    ROAD_TRAFFIC_CAPACITY, TILE_SIZE,
)
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
        # Vignette overlay surface (rebuilt on viewport size change).
        self._vignette_surf: pygame.Surface | None = None
        self._vignette_size: tuple[int, int] = (0, 0)

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

        # Vignette frames the map area with a subtle dark gradient at the edges.
        self._draw_vignette(surface, camera.viewport)

        # Minimap in the top-right corner of the viewport.
        self._draw_minimap(surface, city_map, camera, hover_tile)

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

    # ── Water animation ────────────────────────────────────────────────────────

    def _draw_water_anim(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        tile_x: int, tile_y: int,
    ) -> None:
        """Draws animated shimmer lines on water tiles, oscillating with time."""
        if tw < 12:
            return
        hw, hh = tw // 2, th // 2
        tick = pygame.time.get_ticks()
        # Each tile gets a unique phase offset so ripples don't move in sync.
        offset_ms = (tile_x * 37 + tile_y * 17) * 400

        if self._diam_overlay_size != (tw, th):
            self._diam_overlay = pygame.Surface((tw, th), pygame.SRCALPHA)
            self._diam_overlay_size = (tw, th)
        self._diam_overlay.fill((0, 0, 0, 0))

        lw = max(1, tw // 22)
        shimmer = (148, 208, 240)

        for frac, extra_ms in ((0.28, 0), (0.62, 1100)):
            phase = ((tick + offset_ms + extra_ms) % 2400) / 2400.0
            anim_off = int(math.sin(phase * math.pi * 2) * (th * 0.07))
            wy = int(th * frac) + anim_off
            if wy <= 0 or wy >= th - 1:
                continue
            # Clip x range to inside the diamond at this y scanline.
            if wy <= hh:
                xl = int(hw * wy / max(1, hh))
                xr = tw - xl
            else:
                xl = int(hw * (th - wy) / max(1, hh))
                xr = tw - xl
            if xl >= xr - 1:
                continue
            alpha = int(50 + 40 * abs(math.sin(phase * math.pi * 2)))
            pygame.draw.line(
                self._diam_overlay, (*shimmer, alpha),
                (xl + 1, wy), (xr - 1, wy), lw,
            )

        surface.blit(self._diam_overlay, (cx - hw, cy))

    # ── Vignette ───────────────────────────────────────────────────────────────

    def _draw_vignette(self, surface: pygame.Surface, viewport: pygame.Rect) -> None:
        """Dark gradient vignette around the map viewport edges for visual depth."""
        size = (viewport.width, viewport.height)
        if self._vignette_surf is None or self._vignette_size != size:
            self._vignette_surf = pygame.Surface(size, pygame.SRCALPHA)
            self._vignette_surf.fill((0, 0, 0, 0))
            edge = min(80, size[0] // 7, size[1] // 7)
            for i in range(edge):
                a = int(72 * ((edge - i) / edge) ** 2)
                if a < 1:
                    continue
                c = (0, 0, 0, a)
                w, h = size
                pygame.draw.line(self._vignette_surf, c, (0, i), (w, i))
                pygame.draw.line(self._vignette_surf, c, (0, h - 1 - i), (w, h - 1 - i))
                pygame.draw.line(self._vignette_surf, c, (i, 0), (i, h))
                pygame.draw.line(self._vignette_surf, c, (w - 1 - i, 0), (w - 1 - i, h))
            self._vignette_size = size
        surface.blit(self._vignette_surf, viewport.topleft)

    # ── Zone stakes ────────────────────────────────────────────────────────────

    def _draw_zone_stakes(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        zone: ZoneType,
    ) -> None:
        """Shows tiny surveyor-stake dots at the four diamond corners of an undeveloped lot."""
        hw, hh = tw // 2, th // 2
        zone_c = COLORS.get(zone.value, (100, 100, 100))
        stake_c = (
            min(255, zone_c[0] + 60),
            min(255, zone_c[1] + 60),
            min(255, zone_c[2] + 60),
        )
        r = max(1, tw // 18)
        for sx, sy in ((cx, cy), (cx + hw, cy + hh), (cx, cy + th), (cx - hw, cy + hh)):
            pygame.draw.circle(surface, (16, 18, 20), (sx, sy), r + 1)
            pygame.draw.circle(surface, stake_c, (sx, sy), r)

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

    def _draw_minimap(self, surface: pygame.Surface, city_map, camera, hover_tile=None) -> None:
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
        pad = 5
        label_h = 14
        bg = pygame.Surface((mm_w + pad * 2, mm_h + pad * 2 + label_h))
        bg.fill((10, 13, 18))
        bg.set_alpha(215)
        surface.blit(bg, (mm_x - pad, mm_y - pad - label_h))
        # "MAP" label above the minimap
        if self.small_font:
            lbl = self.small_font.render("MAP", True, (90, 110, 135))
            surface.blit(lbl, (mm_x, mm_y - pad - label_h + 1))
        surface.blit(self._mm_surf, (mm_x, mm_y))

        self.minimap_rect = pygame.Rect(mm_x - pad, mm_y - pad - label_h, mm_w + pad * 2, mm_h + pad * 2 + label_h)

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

        # Highlight the hovered tile on the minimap as a bright crosshair dot.
        if hover_tile is not None:
            hx, hy = hover_tile
            hdx = mm_x + int(hx * mm_w / max(1, city_map.width))
            hdy = mm_y + int(hy * mm_h / max(1, city_map.height))
            hdx = max(mm_x, min(mm_x + mm_w - 1, hdx))
            hdy = max(mm_y, min(mm_y + mm_h - 1, hdy))
            pygame.draw.circle(surface, (255, 255, 100), (hdx, hdy), 2)
            pygame.draw.circle(surface, (40, 40, 20), (hdx, hdy), 2, 1)

        # Outer border.
        pygame.draw.rect(surface, (55, 80, 110), (mm_x - pad, mm_y - pad - label_h, mm_w + pad * 2, mm_h + pad * 2 + label_h), 1, border_radius=3)
        # Inner border just around the map image.
        pygame.draw.rect(surface, (40, 58, 78), (mm_x - 1, mm_y - 1, mm_w + 2, mm_h + 2), 1)

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

        # Animated shimmer on water tiles (drawn above the static sprite).
        if tile.terrain == TerrainType.WATER:
            self._draw_water_anim(surface, cx, cy, tw, th, x, y)

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
            # Tint congested roads: yellow at moderate load, red when heavily congested.
            if tile.traffic_load > ROAD_TRAFFIC_CAPACITY // 2:
                frac = min(1.0, tile.traffic_load / (ROAD_TRAFFIC_CAPACITY * 2.0))
                r = min(255, int(200 + 55 * frac))
                g = int(200 * (1.0 - frac))
                alpha = int(55 + 80 * frac)
                self._draw_diam_overlay(surface, cx, cy, tw, th, (r, g, 0, alpha))
        elif tile.building != BuildingType.NONE:
            self.sprites.draw_civic_building(surface, cx, cy, tw, th, tile.building, rotation)
        elif tile.zone != ZoneType.EMPTY:
            rec_type = tile.recreation_type if tile.zone == ZoneType.PARK else None
            # Draw the coloured base lot.
            self.sprites.draw_zone_base(surface, cx, cy, tw, th, tile.zone, tile.zone_level, rec_type)
            if tile.development <= 0.05 and tw >= 14:
                # Undeveloped lot: show small surveyor stakes at diamond corners.
                self._draw_zone_stakes(surface, cx, cy, tw, th, tile.zone)
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
            # Industrial smoke rises above developed factories.
            if tile.zone == ZoneType.INDUSTRIAL and tile.development > 0.35:
                self._draw_smoke(surface, cx, cy, tw, th, tile.development)

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

        elif view_mode == ViewMode.TRAFFIC:
            if tile.has_road:
                # Road tiles: green → yellow → red as load rises.
                load = tile.traffic_load
                frac = min(1.0, load / max(1, ROAD_TRAFFIC_CAPACITY * 2))
                r = min(255, int(80 + 175 * frac))
                g = min(255, int(220 * (1.0 - frac * 0.8)))
                self._draw_diam_overlay(surface, cx, cy, tw, th, (r, g, 20, 200))
            elif tile.zone not in (ZoneType.EMPTY, ZoneType.PARK):
                # Dim non-road tiles so roads stand out.
                self._draw_diam_overlay(surface, cx, cy, tw, th, (30, 30, 30, 100))
            if tile.building != BuildingType.NONE:
                self._draw_marker_dot(surface, cx, cy, tw, th, tile.building)

        elif view_mode == ViewMode.LAND_VALUE:
            if tile.zone not in (ZoneType.EMPTY, ZoneType.PARK) or tile.building != BuildingType.NONE:
                # Map land_value (LAND_VALUE_MIN..LAND_VALUE_MAX) to a cool-warm gradient.
                lv = tile.land_value
                lv_min, lv_max = LAND_VALUE_MIN, LAND_VALUE_MAX
                frac = max(0.0, min(1.0, (lv - lv_min) / max(0.01, lv_max - lv_min)))
                # Blue (low) → green (mid) → amber (high)
                if frac < 0.5:
                    t = frac * 2
                    r, g, b = int(30 * t), int(100 + 120 * t), int(180 - 180 * t)
                else:
                    t = (frac - 0.5) * 2
                    r, g, b = int(30 + 200 * t), int(220 - 80 * t), 0
                self._draw_diam_overlay(surface, cx, cy, tw, th, (r, g, b, 180))
            if tile.building != BuildingType.NONE:
                self._draw_marker_dot(surface, cx, cy, tw, th, tile.building)

        elif view_mode == ViewMode.POLLUTION:
            if tile.pollution > 0.02:
                # Grey-brown tint; opacity scales with pollution level.
                frac = min(1.0, tile.pollution)
                r = int(90 + 80 * frac)
                g = int(70 - 20 * frac)
                b = int(20)
                alpha = int(40 + 200 * frac)
                self._draw_diam_overlay(surface, cx, cy, tw, th, (r, g, b, alpha))
            if tile.building == BuildingType.NONE and tile.zone == ZoneType.INDUSTRIAL:
                # Show industrial source tiles clearly.
                conn = _rotate_connections(city_map.road_connections(x, y), rotation) if tile.has_road else {}
                if tile.has_road:
                    self.sprites.draw_road(surface, cx, cy, tw, th, conn)
            if tile.building != BuildingType.NONE:
                self._draw_marker_dot(surface, cx, cy, tw, th, tile.building)
            if tile.zone == ZoneType.INDUSTRIAL and tile.development > 0.35:
                self._draw_smoke(surface, cx, cy, tw, th, tile.development)

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

    def _draw_smoke(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        development: float,
    ) -> None:
        """Draws animated smoke puffs rising above industrial buildings."""
        if tw < 10:
            return
        tick   = pygame.time.get_ticks()
        n_puffs = 1 + int(development * 2)  # 1-3 puffs depending on development
        for i in range(n_puffs):
            phase  = (tick // 600 + i * 200) % 1000
            rise   = phase / 1000.0          # 0→1 as puff rises
            alpha  = int(120 * (1.0 - rise) * min(1.0, development))
            if alpha < 8:
                continue
            r      = max(2, int(tw / 6 * (0.5 + rise * 0.8)))
            offset_x = (i - n_puffs // 2) * max(2, tw // 8)
            px     = cx + offset_x
            py     = cy - int(rise * th * 1.8) - th // 4
            grey   = int(140 + 60 * rise)
            smoke  = pygame.Surface((r * 2 + 2, r * 2 + 2), pygame.SRCALPHA)
            pygame.draw.circle(smoke, (grey, grey, grey, alpha), (r + 1, r + 1), r)
            surface.blit(smoke, (px - r - 1, py - r - 1))

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

    # Maps each tool to the colour used for the hover diamond when placement is valid.
    _TOOL_HOVER_COLORS: dict[str, tuple[int, int, int]] = {
        "inspect":            (200, 210, 230),
        "residential":        (85,  200,  95),
        "dense_residential":  (110, 225, 120),
        "highrise_residential":(140, 245, 150),
        "commercial":         (85,  148, 245),
        "dense_commercial":   (105, 175, 255),
        "highrise_commercial":(135, 200, 255),
        "industrial":         (230, 180,  55),
        "road":               (185, 180, 160),
        "power_line":         (245, 220,  75),
        "water_pipe":         (85,  195, 240),
        "power_plant":        (245, 220,  75),
        "large_power_plant":  (245, 220,  75),
        "water_tower":        (85,  195, 240),
        "large_water_tower":  (85,  195, 240),
        "police":             (90,  120, 220),
        "fire":               (225,  90,  75),
        "school":             (160, 120, 220),
        "hospital":           (225,  90, 105),
        "train_station":      (215, 160, 100),
        "airport":            (110, 168, 225),
        "park":               (65,  210, 110),
        "playground":         (240, 135,  55),
        "sports_field":       (50,  205,  80),
        "stadium":            (145, 110, 195),
        "golf_course":        (110, 225, 120),
        "pool":               (80,  175, 245),
        "cinema":             (210,  65, 100),
        "museum":             (215, 200, 155),
        "zoo":                (180, 135,  70),
        "bulldoze":           (220,  75,  65),
    }

    def _tool_hover_color(self, active_tool: Tool) -> tuple[int, int, int]:
        return self._TOOL_HOVER_COLORS.get(active_tool.value, COLORS["hover_ok"])

    def _draw_hover(
        self,
        surface: pygame.Surface,
        city_map: CityMap,
        active_tool: Tool,
        hover_tile: tuple[int, int],
        cx: int, cy: int,
        tw: int, th: int,
    ) -> None:
        """Draws a colored diamond highlight under the cursor (tool color if valid, red if blocked)."""
        x, y   = hover_tile
        tile   = city_map.get(x, y)
        blocked = self._tool_blocked(tile, active_tool)
        color  = COLORS["hover_blocked"] if blocked else self._tool_hover_color(active_tool)
        hw, hh = tw // 2, th // 2
        diam_pts = [(cx, cy), (cx + hw, cy + hh), (cx, cy + th), (cx - hw, cy + hh)]
        # Translucent fill so the tool color reads on all terrain.
        if tw >= 8:
            fill_alpha = 45 if not blocked else 55
            fill_surf = pygame.Surface((tw, th + 1), pygame.SRCALPHA)
            pygame.draw.polygon(fill_surf, (*color, fill_alpha), [(hw, 0), (tw, hh), (hw, th), (0, hh)])
            surface.blit(fill_surf, (cx - hw, cy))
        # Drop shadow (offset 1 px).
        shadow = [(cx, cy + 1), (cx + hw + 1, cy + hh + 1), (cx, cy + th + 1), (cx - hw - 1, cy + hh + 1)]
        pygame.draw.polygon(surface, (12, 16, 20), shadow, 2)
        # Colored outline (3px).
        pygame.draw.polygon(surface, color, diam_pts, 3)

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
