"""Sprite drawing routines — procedurally generates all tile, building, and road graphics.
All sprites are cached in SpriteAtlas so each unique combination is only drawn once."""
from __future__ import annotations

import math

import pygame

from .asset_loader import ImageAssetStore
from .models import BuildingType, RecreationType, TerrainType, ZoneType
from .settings import COLORS, USE_IMAGE_SPRITES


# ---------------------------------------------------------------------------
# Small drawing helpers
# ---------------------------------------------------------------------------

def _s(color: tuple, amt: int) -> tuple:
    """Shift a colour brighter (positive) or darker (negative), clamped to 0-255."""
    return tuple(max(0, min(255, c + amt)) for c in color)


def _lerp(a: int, b: int, t: float) -> int:
    """Linear interpolation between two integers."""
    return int(a + (b - a) * t)


def _diam_pts(tw: int, th: int, oy: int = 0) -> list[tuple[int, int]]:
    """Four corners of an isometric diamond (north, east, south, west)."""
    hw, hh = tw // 2, th // 2
    return [(hw, oy), (tw, oy + hh), (hw, oy + th), (0, oy + hh)]


def tile_variant(x: int, y: int) -> int:
    """Deterministic 0-3 index so the same tile coordinate always gets the same look."""
    return (x * 37 + y * 17) & 3


# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------

_GRASS = [
    (82, 115, 60),
    (74, 105, 54),
    (90, 124, 66),
    (70, 100, 52),
]

_ZONE_WALL = {
    ZoneType.RESIDENTIAL: [(196, 176, 145), (188, 166, 134), (205, 184, 154), (190, 172, 140)],
    ZoneType.COMMERCIAL:  [(118, 148, 182), (108, 138, 172), (128, 156, 190), (112, 142, 178)],
    ZoneType.INDUSTRIAL:  [(148, 138, 115), (138, 128, 106), (156, 145, 122), (142, 132, 110)],
    ZoneType.PARK:        [(62, 138, 76),   (54, 126, 68),   (70, 148, 84),   (58, 132, 72)],
}

_ZONE_ROOF = {
    ZoneType.RESIDENTIAL: (152, 75, 58),
    ZoneType.COMMERCIAL:  (58, 78, 100),
    ZoneType.INDUSTRIAL:  (82, 78, 65),
    ZoneType.PARK:        (42, 105, 58),
}

_ZONE_WIN = {
    ZoneType.RESIDENTIAL: (222, 195, 138),
    ZoneType.COMMERCIAL:  (165, 215, 245),
    ZoneType.INDUSTRIAL:  (188, 172, 132),
    ZoneType.PARK:        (168, 218, 148),
}

_BLD_FRACS = {
    ZoneType.RESIDENTIAL: [0, 0.70, 1.10, 1.60, 2.10],
    ZoneType.COMMERCIAL:  [0, 0.80, 1.30, 2.00, 2.80],
    ZoneType.INDUSTRIAL:  [0, 0.70, 1.00, 1.40, 1.80],
    ZoneType.PARK:        [0, 0.50, 0.70, 0.90, 1.10],
}

# Per-recreation-type wall colours (4 variants), roof colours, accent colours
_REC_WALL = {
    RecreationType.PARK:         [(62, 138, 76),   (54, 126, 68),   (70, 148, 84),   (58, 132, 72)],
    RecreationType.PLAYGROUND:   [(210, 105, 50),  (200, 95, 44),   (220, 115, 58),  (205, 100, 48)],
    RecreationType.SPORTS_FIELD: [(46, 168, 72),   (38, 155, 62),   (54, 178, 80),   (42, 160, 68)],
    RecreationType.STADIUM:      [(110, 95, 135),  (100, 85, 125),  (120, 105, 145), (105, 90, 130)],
    RecreationType.GOLF_COURSE:  [(90, 185, 95),   (80, 172, 85),   (100, 196, 105), (85, 178, 90)],
    RecreationType.POOL:         [(65, 155, 215),  (55, 140, 200),  (75, 168, 228),  (60, 148, 208)],
    RecreationType.CINEMA:       [(175, 50, 80),   (160, 42, 72),   (188, 58, 88),   (168, 46, 76)],
    RecreationType.MUSEUM:       [(188, 172, 138), (178, 162, 128), (198, 182, 148), (182, 166, 132)],
    RecreationType.ZOO:          [(148, 108, 60),  (138, 98, 52),   (158, 118, 68),  (142, 102, 56)],
}

_REC_ROOF = {
    RecreationType.PARK:         (42, 105, 58),
    RecreationType.PLAYGROUND:   (235, 185, 30),
    RecreationType.SPORTS_FIELD: (30, 140, 55),
    RecreationType.STADIUM:      (90, 70, 120),
    RecreationType.GOLF_COURSE:  (68, 158, 72),
    RecreationType.POOL:         (40, 130, 195),
    RecreationType.CINEMA:       (140, 30, 60),
    RecreationType.MUSEUM:       (145, 132, 108),
    RecreationType.ZOO:          (110, 78, 40),
}

_REC_BLD_FRACS = {
    RecreationType.PARK:         [0, 0.50, 0.70, 0.90, 1.10],
    RecreationType.PLAYGROUND:   [0, 0.55, 0.75, 0.95, 1.15],
    RecreationType.SPORTS_FIELD: [0, 0.20, 0.28, 0.36, 0.44],
    RecreationType.STADIUM:      [0, 0.90, 1.30, 1.70, 2.10],
    RecreationType.GOLF_COURSE:  [0, 0.28, 0.38, 0.48, 0.58],
    RecreationType.POOL:         [0, 0.28, 0.38, 0.48, 0.58],
    RecreationType.CINEMA:       [0, 1.00, 1.40, 1.80, 2.20],
    RecreationType.MUSEUM:       [0, 0.90, 1.25, 1.60, 1.95],
    RecreationType.ZOO:          [0, 0.45, 0.60, 0.75, 0.90],
}

_CIVIC_COLOR_KEY = {
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

_CIVIC_HEIGHT = {
    BuildingType.POLICE:            1.40,
    BuildingType.FIRE:              1.40,
    BuildingType.SCHOOL:            1.50,
    BuildingType.HOSPITAL:          1.55,
    BuildingType.POWER_PLANT:       2.00,
    BuildingType.WATER_TOWER:       2.20,
    BuildingType.LARGE_POWER_PLANT: 2.80,
    BuildingType.LARGE_WATER_TOWER: 2.60,
    BuildingType.TRAIN_STATION:     2.00,
    BuildingType.AIRPORT:           1.80,
}

_CIVIC_LABEL = {
    BuildingType.POWER_PLANT:       "P",
    BuildingType.LARGE_POWER_PLANT: "P+",
    BuildingType.WATER_TOWER:       "W",
    BuildingType.LARGE_WATER_TOWER: "W+",
    BuildingType.POLICE:            "Po",
    BuildingType.FIRE:              "Fi",
    BuildingType.SCHOOL:            "Sc",
    BuildingType.HOSPITAL:          "H+",
    BuildingType.TRAIN_STATION:     "Tr",
    BuildingType.AIRPORT:           "Ap",
}


# ---------------------------------------------------------------------------
# Sprite atlas
# ---------------------------------------------------------------------------

class SpriteAtlas:
    def __init__(self, font: pygame.font.Font) -> None:
        self.font = font
        self.assets = ImageAssetStore() if USE_IMAGE_SPRITES else None
        self.cache: dict = {}

    # ------------------------------------------------------------------ #
    # Public draw interface                                                #
    # ------------------------------------------------------------------ #

    def draw_terrain(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        tw: int,
        th: int,
        terrain: TerrainType,
        x: int,
        y: int,
        same_neighbors: dict | None = None,
    ) -> None:
        v = tile_variant(x, y)
        ek = self._edge_key(same_neighbors) if terrain == TerrainType.WATER else None
        key = ("T", terrain, tw, v, ek)
        spr = self._get(key, lambda: self._terrain_spr(terrain, tw, th, v, same_neighbors))
        surface.blit(spr, (cx - tw // 2, cy))

    def draw_zone_base(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        tw: int,
        th: int,
        zone: ZoneType,
        level: int,
        recreation_type: RecreationType | None = None,
    ) -> None:
        key = ("ZB", zone, level, tw, recreation_type)
        spr = self._get(key, lambda: self._zone_base_spr(zone, level, tw, th, recreation_type))
        surface.blit(spr, (cx - tw // 2, cy))

    def draw_building(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        tw: int,
        th: int,
        zone: ZoneType,
        development: float,
        level: int = 1,
        variant: int = 0,
        rotation: int = 0,
        recreation_type: RecreationType | None = None,
    ) -> None:
        if development < 0.06 or (zone not in _BLD_FRACS and zone != ZoneType.PARK):
            return
        stage   = max(1, min(4, int(development * 4) + 1))
        v       = variant & 3
        # Image assets only apply to standard zones, not recreation subtypes
        if zone != ZoneType.PARK or recreation_type is None or recreation_type == RecreationType.PARK:
            asset = self._asset(self._building_asset_name(zone, stage, level, v), tw)
            if asset is not None:
                if rotation in (1, 3):
                    flip_key = ("BAF", zone, stage, level, tw, v)
                    asset = self._get(flip_key, lambda: pygame.transform.flip(asset, True, False))
                self._blit_grounded(surface, asset, cx, cy, th)
                return
        bh      = self._bh(zone, stage, level, th, recreation_type)
        extra_h = th // 2
        key     = ("B", zone, stage, level, tw, th, v, recreation_type)
        spr     = self._get(key, lambda: self._building_spr(zone, tw, th, bh, stage, level, v, extra_h, recreation_type))
        if rotation in (1, 3):
            flip_key = ("BF", zone, stage, level, tw, th, v, recreation_type)
            spr = self._get(flip_key, lambda: pygame.transform.flip(spr, True, False))
        surface.blit(spr, (cx - tw // 2, cy - bh - extra_h))

    def draw_civic_building(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        tw: int,
        th: int,
        building: BuildingType,
        rotation: int = 0,
    ) -> None:
        asset = self._asset(f"civic/{building.value}", tw)
        if asset is not None:
            if rotation in (1, 3):
                flip_key = ("CAF", building, tw)
                asset = self._get(flip_key, lambda: pygame.transform.flip(asset, True, False))
            self._blit_grounded(surface, asset, cx, cy, th)
            return
        bh      = self._civic_bh(building, th)
        extra_h = th // 2
        key     = ("C", building, tw, th)
        spr     = self._get(key, lambda: self._civic_spr(building, tw, th, bh, extra_h))
        if rotation in (1, 3):
            flip_key = ("CF", building, tw, th)
            spr = self._get(flip_key, lambda: pygame.transform.flip(spr, True, False))
        surface.blit(spr, (cx - tw // 2, cy - bh - extra_h))

    def draw_road(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        tw: int,
        th: int,
        connections: dict[str, bool],
    ) -> None:
        key = ("R", tw, connections["north"], connections["east"],
               connections["south"], connections["west"])
        spr = self._get(key, lambda: self._road_spr(tw, th, connections))
        surface.blit(spr, (cx - tw // 2, cy))

    def draw_pedestrian(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        tw: int,
        th: int,
        variant: int,
    ) -> None:
        asset_size = max(8, tw // 3)
        asset = self._asset(f"pedestrians/pedestrian_{variant % 3}", asset_size)
        if asset is not None:
            surface.blit(asset, (cx - asset.get_width() // 2, cy - asset.get_height()))
            return
        size = max(3, tw // 6)
        palette = (
            ((244, 190, 111), (61, 93, 150)),
            ((238, 134, 112), (80, 130, 95)),
            ((219, 198, 145), (145, 86, 128)),
        )
        shirt, pants = palette[variant % 3]
        shadow = pygame.Rect(cx - size, cy + size // 4, size * 2, max(2, size // 2))
        pygame.draw.ellipse(surface, (16, 18, 16), shadow)
        pygame.draw.circle(surface, shirt, (cx, cy - size // 2), max(2, size // 2))
        pygame.draw.rect(surface, pants,
                         pygame.Rect(cx - size // 3, cy, max(2, size * 2 // 3), size),
                         border_radius=1)
        pygame.draw.circle(surface, (248, 205, 163), (cx, cy - size), max(1, size // 3))

    # ------------------------------------------------------------------ #
    # Window / story helpers                                               #
    # ------------------------------------------------------------------ #

    def _left_windows(
        self,
        spr: pygame.Surface,
        tw: int,
        bh: int,
        hw: int,
        hh: int,
        ey: int,
        wc: tuple,
        n_cols: int,
        n_rows: int,
    ) -> None:
        """Draw parallelogram windows on the SW (left) face."""
        if tw < 16 or bh < 8 or n_cols < 1 or n_rows < 1:
            return
        mg_u, mg_v = 0.14, 0.10
        cell_u = (1.0 - 2 * mg_u) / n_cols
        cell_v = (1.0 - 2 * mg_v) / n_rows
        wu = cell_u * 0.62
        wv = cell_v * 0.56

        frame_c = _s(wc, -60)

        def lpt(u: float, v: float) -> tuple[int, int]:
            return (int(u * hw), int(hh + ey + u * hh + v * bh))

        for r in range(n_rows):
            for c in range(n_cols):
                uc = mg_u + (c + 0.5) * cell_u
                vc = mg_v + (r + 0.5) * cell_v
                u1, u2 = uc - wu / 2, uc + wu / 2
                v1, v2 = vc - wv / 2, vc + wv / 2
                pts = [lpt(u1, v1), lpt(u2, v1), lpt(u2, v2), lpt(u1, v2)]
                if abs(pts[0][0] - pts[1][0]) > 0 or abs(pts[0][1] - pts[2][1]) > 1:
                    pygame.draw.polygon(spr, wc, pts)
                    pygame.draw.polygon(spr, frame_c, pts, 1)

    def _right_windows(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        ey: int,
        wc: tuple,
        n_cols: int,
        n_rows: int,
    ) -> None:
        """Draw parallelogram windows on the SE (right) face."""
        if tw < 16 or bh < 8 or n_cols < 1 or n_rows < 1:
            return
        mg_u, mg_v = 0.14, 0.10
        cell_u = (1.0 - 2 * mg_u) / n_cols
        cell_v = (1.0 - 2 * mg_v) / n_rows
        wu = cell_u * 0.62
        wv = cell_v * 0.56

        frame_c = _s(wc, -60)

        def rpt(u: float, v: float) -> tuple[int, int]:
            return (int(hw + u * hw), int(th + ey - u * hh + v * bh))

        for r in range(n_rows):
            for c in range(n_cols):
                uc = mg_u + (c + 0.5) * cell_u
                vc = mg_v + (r + 0.5) * cell_v
                u1, u2 = uc - wu / 2, uc + wu / 2
                v1, v2 = vc - wv / 2, vc + wv / 2
                pts = [rpt(u1, v1), rpt(u2, v1), rpt(u2, v2), rpt(u1, v2)]
                if abs(pts[0][0] - pts[1][0]) > 0 or abs(pts[0][1] - pts[2][1]) > 1:
                    pygame.draw.polygon(spr, wc, pts)
                    pygame.draw.polygon(spr, frame_c, pts, 1)

    def _story_lines(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        ey: int,
        lc: tuple,
        n_floors: int,
    ) -> None:
        """Draw horizontal story-divider lines across both visible faces."""
        if tw < 18 or n_floors < 2 or bh < 10:
            return
        lw = max(1, tw // 32)
        for f in range(1, n_floors):
            v = f / n_floors
            y_at_v = int(v * bh)
            # Left face: from (0, hh+ey+y) to (hw, th+ey+y)
            pygame.draw.line(spr, lc,
                             (0,  hh + ey + y_at_v),
                             (hw, th + ey + y_at_v), lw)
            # Right face: from (hw, th+ey+y) to (tw, hh+ey+y)
            pygame.draw.line(spr, lc,
                             (hw, th + ey + y_at_v),
                             (tw, hh + ey + y_at_v), lw)

    # ------------------------------------------------------------------ #
    # Sprite makers                                                        #
    # ------------------------------------------------------------------ #

    def _terrain_spr(
        self,
        terrain: TerrainType,
        tw: int,
        th: int,
        variant: int,
        same_neighbors: dict | None,
    ) -> pygame.Surface:
        spr = pygame.Surface((tw, th), pygame.SRCALPHA)
        hw, hh = tw // 2, th // 2
        d = _diam_pts(tw, th)

        if terrain == TerrainType.GRASS:
            self._draw_grass(spr, tw, th, hw, hh, d, variant)
        elif terrain == TerrainType.WATER:
            self._draw_water(spr, tw, th, hw, hh, d, same_neighbors)
        elif terrain == TerrainType.FOREST:
            self._draw_forest(spr, tw, th, hw, hh, d, variant)
        elif terrain == TerrainType.HILL:
            self._draw_hill(spr, tw, th, hw, hh, d, variant)
        return spr

    def _draw_grass(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        hw: int,
        hh: int,
        d: list,
        variant: int,
    ) -> None:
        base = _GRASS[variant]
        light = _s(base, 14)
        shadow = _s(base, -20)

        # Fill full diamond
        pygame.draw.polygon(spr, base, d)

        # Light NE half (north vertex → east vertex)
        ne_face = [(hw, 0), (tw, hh), (hw, hh), (hw, 0)]
        pygame.draw.polygon(spr, light, ne_face)

        # Shadow SW half (south vertex → west vertex)
        sw_face = [(hw, th), (0, hh), (hw, hh), (hw, th)]
        pygame.draw.polygon(spr, shadow, sw_face)

        # Blend back to base at center with small mid-diamond
        mid_shrink = max(1, tw // 12)
        mid_d = _diam_pts(tw - mid_shrink * 4, th - mid_shrink * 2, mid_shrink)
        pygame.draw.polygon(spr, base, mid_d)

        # Grass detail marks
        if tw >= 16:
            detail_cols = [
                (_s(base, 20), _s(base, -10)),
                (_s(base, 15), _s(base, -8)),
                (_s(base, 25), _s(base, -12)),
                (_s(base, 18), _s(base, -6)),
            ][variant]
            positions = [
                (tw * 2 // 7, th * 3 // 8),
                (tw * 5 // 7, th * 2 // 7),
                (tw * 3 // 7, th * 5 // 7),
                (tw * 6 // 7, th * 6 // 8),
            ]
            lw = max(1, tw // 36)
            for i, (px, py) in enumerate(positions):
                c = detail_cols[0] if i % 2 == 0 else detail_cols[1]
                pygame.draw.line(spr, c, (px, py + 2), (px + lw, py), lw)

    def _draw_water(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        hw: int,
        hh: int,
        d: list,
        sn: dict | None,
    ) -> None:
        base = (44, 104, 148)
        deep = (34, 88, 130)
        shimmer = (92, 158, 195)
        foam = (148, 196, 222)

        # Fill with deep water base
        pygame.draw.polygon(spr, deep, d)

        # Lighter NW half
        nw_face = [(hw, 0), (0, hh), (hw, hh)]
        pygame.draw.polygon(spr, base, nw_face)

        # Wave lines — slightly angled to follow diamond
        if tw >= 12:
            lw = max(1, tw // 22)
            for i, frac in enumerate((0.28, 0.62)):
                wy = int(th * frac)
                xl = max(tw // 5, int(hw * (1 - (1 - frac) * 0.8)))
                xr = min(tw * 4 // 5, int(hw * (1 + (1 - frac) * 0.8)))
                xm = (xl + xr) // 2
                col = shimmer if i == 0 else foam
                pygame.draw.line(spr, col, (xl, wy), (xm - 2, wy + 1), lw)
                pygame.draw.line(spr, col, (xm + 2, wy + 1), (xr, wy), lw)

        # Sparkle dots
        if tw >= 22:
            for px, py in ((hw - tw // 6, hh // 2), (hw + tw // 8, hh // 3)):
                pygame.draw.circle(spr, foam, (px, py), max(1, tw // 28))

        # Shore edges where NOT adjacent to water
        if sn and tw >= 12:
            shore = (148, 148, 108)
            lw = max(2, tw // 14)
            edges = {
                "north": ((hw, 0),  (tw, hh)),
                "east":  ((tw, hh), (hw, th)),
                "south": ((hw, th), (0,  hh)),
                "west":  ((0,  hh), (hw, 0)),
            }
            for direction, (p1, p2) in edges.items():
                if not sn.get(direction, True):
                    pygame.draw.line(spr, shore, p1, p2, lw)

    def _draw_forest(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        hw: int,
        hh: int,
        d: list,
        variant: int,
    ) -> None:
        floor_c = (44, 80, 46)
        floor_s = (36, 64, 38)
        pygame.draw.polygon(spr, floor_s, d)
        # Lighter NW floor
        pygame.draw.polygon(spr, floor_c, [(hw, 0), (0, hh), (hw, hh)])
        pygame.draw.polygon(spr, floor_c, [(hw, 0), (tw, hh), (hw, hh)])

        if tw < 12:
            return

        tc = [(32, 88, 44), (38, 100, 50), (28, 78, 40)]
        hi = [(56, 128, 68), (62, 138, 76), (50, 118, 62)]
        shadow_c = (24, 60, 30)
        trunk = (68, 58, 38)
        r_base = max(4, tw // 8)

        tree_positions = [
            (hw, hh - th // 5),
            (hw - tw // 5, hh + th // 10),
            (hw + tw // 5, hh + th // 10),
            (hw, hh + th // 4),
        ]
        count = 2 + (variant % 2)
        for i, (px, py) in enumerate(tree_positions[:count]):
            r = r_base - i * max(0, tw // 28)
            r = max(3, r)
            # Shadow below canopy
            pygame.draw.ellipse(spr, shadow_c,
                                pygame.Rect(px - r, py + r // 3, r * 2, max(2, r // 2)))
            # Trunk
            pygame.draw.rect(spr, trunk,
                             pygame.Rect(px - 1, py + r // 2, max(2, tw // 28), max(3, th // 6)))
            # Main canopy
            pygame.draw.circle(spr, tc[i % 3], (px, py), r)
            # Highlight
            pygame.draw.circle(spr, hi[i % 3], (px - r // 3, py - r // 3), max(1, r // 3))

    def _draw_hill(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        hw: int,
        hh: int,
        d: list,
        variant: int,
    ) -> None:
        base = (104, 104, 90)
        lit  = (124, 124, 108)
        dark = (80, 80, 70)
        rock = (140, 136, 120)

        pygame.draw.polygon(spr, base, d)

        # NW face lighter
        pygame.draw.polygon(spr, lit, [(hw, 0), (0, hh), (hw, hh)])
        # SE face darker
        pygame.draw.polygon(spr, dark, [(hw, th), (tw, hh), (hw, hh)])

        if tw < 14:
            return

        # Contour ridgelines
        lw = max(1, tw // 26)
        for i, frac in enumerate((0.28, 0.54, 0.78)):
            y = int(th * frac)
            xm = int(hw * (1 - abs(frac - 0.5) * 0.6))
            col = _s(lit, -i * 8) if frac < 0.5 else _s(dark, i * 6)
            pygame.draw.line(spr, col, (hw - xm, y), (hw + xm, y), lw)

        # Rock highlights
        if tw >= 20:
            for rx, ry in ((hw - tw // 6, hh // 2), (hw + tw // 8, th // 3)):
                pygame.draw.circle(spr, rock, (rx, ry), max(2, tw // 18))
                pygame.draw.circle(spr, lit, (rx - 1, ry - 1), max(1, tw // 26))

    def _zone_base_spr(self, zone: ZoneType, level: int, tw: int, th: int, recreation_type: RecreationType | None = None) -> pygame.Surface:
        spr = pygame.Surface((tw, th), pygame.SRCALPHA)
        d = _diam_pts(tw, th)
        hw, hh = tw // 2, th // 2
        grass = _GRASS[0]
        color_key = recreation_type.value if (zone == ZoneType.PARK and recreation_type is not None) else zone.value
        zone_c = COLORS.get(color_key, (100, 100, 100))
        blend = tuple(int(grass[i] * 0.5 + zone_c[i] * 0.5) for i in range(3))

        # Directional shading like grass tile
        pygame.draw.polygon(spr, blend, d)
        light = _s(blend, 12)
        shadow = _s(blend, -18)
        pygame.draw.polygon(spr, light, [(hw, 0), (tw, hh), (hw, hh)])
        pygame.draw.polygon(spr, shadow, [(hw, th), (0, hh), (hw, hh)])
        mid = _diam_pts(tw - max(2, tw // 10), th - max(1, th // 8), max(1, th // 16))
        pygame.draw.polygon(spr, blend, mid)

        # Zone indicator border
        bw = max(1, tw // 24)
        pygame.draw.polygon(spr, _s(zone_c, -30), d, bw)

        # Dense: extra inner ring
        if level > 1 and tw >= 16:
            inner = _diam_pts(tw - bw * 4, th - bw * 2, bw * 2)
            pygame.draw.polygon(spr, _s(zone_c, 10), inner, bw)

        # Corner dots marking zone type
        if tw >= 22:
            dot_r = max(1, tw // 22)
            for px, py in ((hw * 3 // 2, hh // 2), (hw // 2, hh * 3 // 2)):
                pygame.draw.circle(spr, _s(zone_c, 20), (px, py), dot_r)

        return spr

    def _building_spr(
        self,
        zone: ZoneType,
        tw: int,
        th: int,
        bh: int,
        stage: int,
        level: int,
        variant: int,
        extra_h: int,
        recreation_type: RecreationType | None = None,
    ) -> pygame.Surface:
        surf_h = th + bh + extra_h
        spr = pygame.Surface((tw, surf_h), pygame.SRCALPHA)
        hw, hh = tw // 2, th // 2
        ey = extra_h

        if zone == ZoneType.PARK and recreation_type is not None:
            walls  = _REC_WALL.get(recreation_type, _ZONE_WALL[ZoneType.PARK])
            roof_c = _REC_ROOF.get(recreation_type, _ZONE_ROOF[ZoneType.PARK])
            win_c  = _ZONE_WIN[ZoneType.PARK]
        else:
            walls  = _ZONE_WALL.get(zone, [(150, 150, 150)])
            roof_c = _ZONE_ROOF.get(zone, (80, 80, 80))
            win_c  = _ZONE_WIN.get(zone, (200, 200, 180))
        base_w = walls[variant % len(walls)]
        win_dark = _s(win_c, -55)

        # Face colours: top brighter, left mid, right dark
        top_c   = _s(base_w,  40)
        left_c  = _s(base_w,   6)
        right_c = _s(base_w, -50)
        outline = _s(base_w, -85)
        story_c = _s(base_w, -38)

        roof  = [(hw, ey),      (tw, hh + ey), (hw, th + ey),      (0, hh + ey)]
        left  = [(0, hh + ey),  (hw, th + ey), (hw, th + bh + ey), (0, hh + bh + ey)]
        right = [(tw, hh + ey), (hw, th + ey), (hw, th + bh + ey), (tw, hh + bh + ey)]

        pygame.draw.polygon(spr, right_c, right)
        pygame.draw.polygon(spr, left_c,  left)
        pygame.draw.polygon(spr, top_c,   roof)

        # Subtle top-lighting gradient: lighter strip at top of each wall face,
        # darker strip at the bottom (simulates light coming from above).
        if bh >= 10:
            grad_h = max(2, bh // 5)
            # Left face: top strip lighter, bottom strip darker
            left_top = [(0, hh+ey), (hw, th+ey), (hw, th+ey+grad_h), (0, hh+ey+grad_h)]
            left_bot = [(0, hh+bh+ey-grad_h), (hw, th+bh+ey-grad_h), (hw, th+bh+ey), (0, hh+bh+ey)]
            pygame.draw.polygon(spr, _s(left_c,  18), left_top)
            pygame.draw.polygon(spr, _s(left_c, -18), left_bot)
            # Right face: same idea
            right_top = [(tw, hh+ey), (hw, th+ey), (hw, th+ey+grad_h), (tw, hh+ey+grad_h)]
            right_bot = [(tw, hh+bh+ey-grad_h), (hw, th+bh+ey-grad_h), (hw, th+bh+ey), (tw, hh+bh+ey)]
            pygame.draw.polygon(spr, _s(right_c,  16), right_top)
            pygame.draw.polygon(spr, _s(right_c, -12), right_bot)

        # Windows on wall faces
        n_floors = max(1, bh // max(1, th // 2))
        if zone == ZoneType.RESIDENTIAL:
            nc, nr = max(1, min(3, tw // 22)), max(1, min(4, n_floors))
            self._left_windows(spr, tw, bh, hw, hh, ey, win_c, nc, nr)
            self._right_windows(spr, tw, th, bh, hw, hh, ey, _s(win_c, -25), nc, nr)
        elif zone == ZoneType.COMMERCIAL:
            nc = max(1, min(5, tw // 16))
            nr = max(1, min(6, n_floors * 2))
            self._left_windows(spr, tw, bh, hw, hh, ey, win_c, nc, nr)
            self._right_windows(spr, tw, th, bh, hw, hh, ey, _s(win_c, -30), nc, nr)
        elif zone == ZoneType.INDUSTRIAL:
            nc = max(1, min(2, tw // 28))
            nr = max(1, min(3, n_floors))
            self._left_windows(spr, tw, bh, hw, hh, ey, win_c, nc, nr)
            self._right_windows(spr, tw, th, bh, hw, hh, ey, _s(win_c, -30), max(1, nc - 1), nr)

        # Story divider lines
        if bh >= 18 and n_floors >= 2:
            self._story_lines(spr, tw, th, bh, hw, hh, ey, story_c, min(n_floors, 5))

        # Face outlines
        pygame.draw.polygon(spr, outline, right, 1)
        pygame.draw.polygon(spr, outline, left,  1)
        pygame.draw.polygon(spr, outline, roof,  1)
        # Bottom edge
        pygame.draw.line(spr, outline, (0, hh + bh + ey), (hw, th + bh + ey), 1)
        pygame.draw.line(spr, outline, (tw, hh + bh + ey), (hw, th + bh + ey), 1)

        # Zone-specific details
        if zone == ZoneType.RESIDENTIAL:
            self._res_det(spr, tw, th, bh, hw, hh, stage, variant, roof_c, ey)
        elif zone == ZoneType.COMMERCIAL:
            self._com_det(spr, tw, th, bh, hw, hh, stage, variant, ey)
        elif zone == ZoneType.INDUSTRIAL:
            self._ind_det(spr, tw, th, bh, hw, hh, stage, variant, ey)
        elif zone == ZoneType.PARK:
            rec = recreation_type or RecreationType.PARK
            if rec == RecreationType.PARK:
                self._park_det(spr, tw, th, bh, hw, hh, stage, ey)
            elif rec == RecreationType.PLAYGROUND:
                self._playground_det(spr, tw, th, bh, hw, hh, stage, ey)
            elif rec == RecreationType.SPORTS_FIELD:
                self._sports_field_det(spr, tw, th, bh, hw, hh, stage, ey)
            elif rec == RecreationType.STADIUM:
                self._stadium_det(spr, tw, th, bh, hw, hh, stage, ey)
            elif rec == RecreationType.GOLF_COURSE:
                self._golf_det(spr, tw, th, bh, hw, hh, stage, ey)
            elif rec == RecreationType.POOL:
                self._pool_det(spr, tw, th, bh, hw, hh, stage, ey)
            elif rec == RecreationType.CINEMA:
                self._cinema_det(spr, tw, th, bh, hw, hh, stage, ey)
            elif rec == RecreationType.MUSEUM:
                self._museum_det(spr, tw, th, bh, hw, hh, stage, ey)
            elif rec == RecreationType.ZOO:
                self._zoo_det(spr, tw, th, bh, hw, hh, stage, ey)
        return spr

    def _civic_spr(
        self,
        building: BuildingType,
        tw: int,
        th: int,
        bh: int,
        extra_h: int,
    ) -> pygame.Surface:
        surf_h = th + bh + extra_h
        spr = pygame.Surface((tw, surf_h), pygame.SRCALPHA)
        hw, hh = tw // 2, th // 2
        ey = extra_h

        ck = _CIVIC_COLOR_KEY.get(building, "building_dark")
        base_c = COLORS.get(ck, (80, 80, 80))

        top_c   = _s(base_c,  45)
        left_c  = base_c
        right_c = _s(base_c, -55)
        outline = _s(base_c, -90)
        story_c = _s(base_c, -40)

        roof  = [(hw, ey),      (tw, hh + ey), (hw, th + ey),      (0, hh + ey)]
        left  = [(0, hh + ey),  (hw, th + ey), (hw, th + bh + ey), (0, hh + bh + ey)]
        right = [(tw, hh + ey), (hw, th + ey), (hw, th + bh + ey), (tw, hh + bh + ey)]

        pygame.draw.polygon(spr, right_c, right)
        pygame.draw.polygon(spr, left_c,  left)
        pygame.draw.polygon(spr, top_c,   roof)

        # Civic windows (sparse)
        win_c = _s(base_c, 80)
        if tw >= 18 and bh >= 12:
            n_floors = max(1, bh // max(1, th // 2))
            nc = max(1, min(3, tw // 24))
            nr = max(1, min(4, n_floors))
            self._left_windows(spr, tw, bh, hw, hh, ey, win_c, nc, nr)
            self._right_windows(spr, tw, th, bh, hw, hh, ey, _s(win_c, -30), nc, nr)
            if n_floors >= 2:
                self._story_lines(spr, tw, th, bh, hw, hh, ey, story_c, min(n_floors, 4))

        pygame.draw.polygon(spr, outline, right, 1)
        pygame.draw.polygon(spr, outline, left,  1)
        pygame.draw.polygon(spr, outline, roof,  1)
        pygame.draw.line(spr, outline, (0, hh + bh + ey), (hw, th + bh + ey), 1)
        pygame.draw.line(spr, outline, (tw, hh + bh + ey), (hw, th + bh + ey), 1)

        self._civic_det(spr, building, tw, th, bh, hw, hh, base_c, ey)

        if tw >= 24:
            label = _CIVIC_LABEL.get(building, "?")
            text = self.font.render(label, True, (245, 245, 240))
            sx = hw - text.get_width() // 2
            sy = ey + max(2, bh // 4 - text.get_height() // 2)
            # Drop shadow
            spr.blit(self.font.render(label, True, outline), (sx + 1, sy + 1))
            spr.blit(text, (sx, sy))
        return spr

    def _road_spr(self, tw: int, th: int, connections: dict[str, bool]) -> pygame.Surface:
        spr = pygame.Surface((tw, th), pygame.SRCALPHA)
        hw, hh = tw // 2, th // 2
        d = _diam_pts(tw, th)

        # Sidewalk (outer ring)
        sidewalk_c = (158, 155, 142)
        pygame.draw.polygon(spr, sidewalk_c, d)

        # Asphalt core (slightly inset diamond)
        inset = max(2, tw // 14)
        asphalt_c = (54, 58, 65)
        asphalt_d = [(hw, inset), (tw - inset, hh), (hw, th - inset), (inset, hh)]
        pygame.draw.polygon(spr, asphalt_c, asphalt_d)

        if tw >= 14:
            center = (hw, hh)
            edge_mids = {
                "north": (tw * 3 // 4, th // 4),
                "east":  (tw * 3 // 4, th * 3 // 4),
                "south": (tw // 4,     th * 3 // 4),
                "west":  (tw // 4,     th // 4),
            }
            arm = max(2, tw // 10)
            arm_sw = max(2, arm + 2)  # sidewalk arm slightly wider

            for direction, ep in edge_mids.items():
                if not connections.get(direction, False):
                    continue
                dx, dy = ep[0] - center[0], ep[1] - center[1]
                length = max(1.0, math.sqrt(dx * dx + dy * dy))
                nx = -dy / length
                ny =  dx / length

                # Sidewalk strip
                sw_pts = [
                    (int(center[0] + nx * arm_sw), int(center[1] + ny * arm_sw)),
                    (int(ep[0]     + nx * arm_sw), int(ep[1]     + ny * arm_sw)),
                    (int(ep[0]     - nx * arm_sw), int(ep[1]     - ny * arm_sw)),
                    (int(center[0] - nx * arm_sw), int(center[1] - ny * arm_sw)),
                ]
                pygame.draw.polygon(spr, sidewalk_c, sw_pts)

                # Asphalt strip
                asp_pts = [
                    (int(center[0] + nx * arm), int(center[1] + ny * arm)),
                    (int(ep[0]     + nx * arm), int(ep[1]     + ny * arm)),
                    (int(ep[0]     - nx * arm), int(ep[1]     - ny * arm)),
                    (int(center[0] - nx * arm), int(center[1] - ny * arm)),
                ]
                pygame.draw.polygon(spr, asphalt_c, asp_pts)

            # Intersection node
            pygame.draw.circle(spr, asphalt_c, center, arm + 1)

            # Centre lane markings
            if tw >= 22:
                lane_c = (195, 180, 100)
                for direction, ep in edge_mids.items():
                    if connections.get(direction, False):
                        mx = (center[0] * 2 + ep[0]) // 3
                        my = (center[1] * 2 + ep[1]) // 3
                        lw = max(1, tw // 30)
                        pygame.draw.circle(spr, lane_c, (mx, my), lw)

        # Sidewalk outline along diamond edge
        pygame.draw.polygon(spr, (132, 128, 116), d, max(1, tw // 38))
        return spr

    # ------------------------------------------------------------------ #
    # Building details                                                     #
    # ------------------------------------------------------------------ #

    def _res_det(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        stage: int,
        variant: int,
        roof_c: tuple,
        ey: int,
    ) -> None:
        if tw >= 16:
            # Peaked roof over the top diamond face
            peak = min(ey, max(4, bh // 4))
            pk_top = (hw, ey - peak)
            roof_pts = [pk_top, (0, hh + ey), (hw, th + ey), (tw, hh + ey)]
            pygame.draw.polygon(spr, roof_c, roof_pts)
            # Ridge shadow side (right half)
            ridge_r = [pk_top, (hw, th + ey), (tw, hh + ey)]
            pygame.draw.polygon(spr, _s(roof_c, -28), ridge_r)
            pygame.draw.polygon(spr, _s(roof_c, -50), roof_pts, 1)
            # Ridge line
            pygame.draw.line(spr, _s(roof_c, -38), pk_top, (hw, th + ey), max(1, tw // 30))

        # Chimney
        if tw >= 22 and stage >= 2:
            ch_w = max(2, tw // 16)
            ch_x = hw + tw // 6
            ch_top = max(0, ey - max(3, bh // 8))
            ch_bot = ey + max(1, th // 8)
            pygame.draw.rect(spr, _s(roof_c, -20), pygame.Rect(ch_x, ch_top, ch_w, ch_bot - ch_top))
            pygame.draw.line(spr, _s(roof_c, 15), (ch_x, ch_top), (ch_x + ch_w, ch_top), max(1, tw // 30))

        # Doorway hint at bottom of left face
        if tw >= 26 and stage >= 2:
            door_c = (60, 50, 40)
            dw = max(2, tw // 14)
            dh = max(3, bh // 6)
            dx = max(1, tw // 10)
            dy = th + bh + ey - dh
            pygame.draw.rect(spr, door_c, pygame.Rect(dx, dy, dw, dh), border_radius=1)

    def _com_det(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        stage: int,
        variant: int,
        ey: int,
    ) -> None:
        # Flat roof with parapet
        if tw >= 16:
            roof_dark = (52, 68, 88)
            # Roof surface fill (slightly darker than top face)
            pygame.draw.polygon(spr, roof_dark,
                                [(hw, ey), (tw, hh + ey), (hw, th + ey), (0, hh + ey)])
            # Parapet (raised border)
            par_h = max(2, bh // 10)
            par_pts_l = [(0, hh + ey), (hw, th + ey), (hw, th + ey - par_h), (0, hh + ey - par_h)]
            par_pts_r = [(tw, hh + ey), (hw, th + ey), (hw, th + ey - par_h), (tw, hh + ey - par_h)]
            pygame.draw.polygon(spr, _s(roof_dark, 25), par_pts_l)
            pygame.draw.polygon(spr, _s(roof_dark, 8), par_pts_r)
            pygame.draw.polygon(spr, _s(roof_dark, -20), par_pts_l, 1)
            pygame.draw.polygon(spr, _s(roof_dark, -20), par_pts_r, 1)

        # Rooftop HVAC / antenna
        if tw >= 22 and stage >= 3:
            spire_h = min(ey, max(4, tw // 9))
            pygame.draw.line(spr, (72, 80, 92), (hw, ey), (hw, ey - spire_h), max(1, tw // 26))
            pygame.draw.circle(spr, (88, 100, 112), (hw, ey - spire_h), max(1, tw // 28))

        if tw >= 20 and stage >= 2:
            # Rooftop AC unit
            ac_c = (78, 90, 104)
            aw = max(3, tw // 12)
            ax = hw - aw // 2
            ay = th + ey - aw - max(1, bh // 10)
            pygame.draw.rect(spr, ac_c, pygame.Rect(ax, ay, aw, aw), border_radius=1)

    def _ind_det(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        stage: int,
        variant: int,
        ey: int,
    ) -> None:
        if tw < 12:
            return

        # Corrugated roof lines on top face
        if tw >= 18:
            ridge_c = _s((82, 78, 65), -15)
            n_ridges = max(1, tw // 14)
            for i in range(n_ridges):
                u = (i + 0.5) / n_ridges
                p1 = (int(u * hw), int(hh + ey + u * hh))
                p2 = (int(hw + u * hw), int(th + ey - u * hh))
                pygame.draw.line(spr, ridge_c, p1, p2, 1)

        # Smokestacks
        sc = (72, 68, 58)
        sh = max(4, bh // 3)
        sw = max(2, tw // 14)
        offsets = [hw + hw // 3, hw - hw // 5] if stage >= 3 else [hw + hw // 3]
        for i, ox in enumerate(offsets[:min(len(offsets), stage)]):
            top = max(0, ey - sh + i * 2)
            bot = ey + max(2, th // 6)
            pygame.draw.rect(spr, sc, pygame.Rect(ox, top, sw, bot - top))
            # Smoke cap
            pygame.draw.ellipse(spr, _s(sc, 25), pygame.Rect(ox - sw // 2, top - sw // 2, sw * 2, sw))
            pygame.draw.line(spr, (102, 98, 88), (ox, top), (ox + sw, top), max(1, tw // 30))

        # Warning stripe on bottom of left wall
        if tw >= 20 and stage >= 2:
            stripe_h = max(2, bh // 8)
            stripe_y = th + bh + ey - stripe_h
            n_stripes = max(2, tw // 16)
            for i in range(n_stripes):
                u = i / n_stripes
                x1 = int(u * hw)
                x2 = int((u + 1.0 / n_stripes) * hw)
                y1 = int(hh + ey + u * hh + (1.0 - stripe_h / bh) * bh)
                y2 = int(hh + ey + (u + 1.0 / n_stripes) * hh + (1.0 - stripe_h / bh) * bh)
                c = (220, 180, 40) if i % 2 == 0 else (40, 40, 40)
                pygame.draw.polygon(spr, c, [(x1, y1), (x2, y2), (x2, y2 + stripe_h), (x1, y1 + stripe_h)])

    def _park_det(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        stage: int,
        ey: int,
    ) -> None:
        if tw < 12:
            return
        # Park pavilion - no solid walls, just a canopy structure
        # Draw canopy roof in green (already has the top face)
        # Draw slender pillars on each corner
        if tw >= 16:
            pillar_c = (148, 138, 115)
            pw = max(1, tw // 20)
            pillar_positions = [(tw // 8, hh + ey), (tw * 7 // 8, hh + ey),
                                (hw, th + ey)]
            for px, py in pillar_positions:
                pygame.draw.rect(spr, pillar_c, pygame.Rect(px - pw // 2, py, pw, bh))

        tc = (38, 90, 50)
        hi = (60, 126, 74)
        shadow_c = (28, 66, 36)
        trunk = (72, 62, 42)
        r = max(4, tw // 7)

        positions = [
            (hw,           ey + bh // 4),
            (hw - tw // 5, ey + bh * 3 // 5),
            (hw + tw // 5, ey + bh * 3 // 5),
        ]
        for i, (px, py) in enumerate(positions[:min(len(positions), stage + 1)]):
            r_i = max(3, r - i)
            pygame.draw.ellipse(spr, shadow_c,
                                pygame.Rect(px - r_i, py + r_i // 3, r_i * 2, max(2, r_i // 2)))
            pygame.draw.rect(spr, trunk,
                             pygame.Rect(px - 1, py + r_i // 2, max(2, tw // 26), max(3, th // 5)))
            pygame.draw.circle(spr, tc, (px, py), r_i)
            pygame.draw.circle(spr, hi, (px - r_i // 3, py - r_i // 3), max(1, r_i // 3))

    def _playground_det(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        stage: int,
        ey: int,
    ) -> None:
        if tw < 10:
            return
        # Slide ramp across top face (NE to SW)
        slide_c = (220, 70, 50)
        lw = max(2, tw // 14)
        pygame.draw.line(spr, slide_c,
                         (hw + hw // 3, ey + hh // 2),
                         (hw - hw // 4, th + ey - th // 4), lw)
        # A-frame swing set sticking above roof
        if tw >= 14:
            frame_c = (55, 130, 220)
            ph = max(4, hh + bh // 3)
            px1, px2 = hw - tw // 5, hw + tw // 5
            bar_y = ey - ph
            pygame.draw.line(spr, frame_c, (px1, ey), (px1, bar_y), max(1, tw // 20))
            pygame.draw.line(spr, frame_c, (px2, ey), (px2, bar_y), max(1, tw // 20))
            pygame.draw.line(spr, frame_c, (px1, bar_y), (px2, bar_y), max(1, tw // 20))
            # Hanging chain + seat
            if stage >= 2 and tw >= 20:
                chain_c = (195, 178, 132)
                seat_y = bar_y + ph // 3
                pygame.draw.line(spr, chain_c, (hw, bar_y), (hw, seat_y), 1)
                sw = max(2, tw // 8)
                pygame.draw.rect(spr, (100, 65, 28),
                                 pygame.Rect(hw - sw // 2, seat_y, sw, max(1, tw // 22)))
        # Sandbox patch near base
        if tw >= 18 and stage >= 2:
            sand_c = (215, 195, 120)
            pygame.draw.ellipse(spr, sand_c,
                                pygame.Rect(hw // 2, th + ey - th // 3, hw, max(2, th // 4)))

    def _sports_field_det(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        stage: int,
        ey: int,
    ) -> None:
        if tw < 10:
            return
        # White pitch markings on top face
        line_c = (240, 240, 240)
        lw = max(1, tw // 24)
        # Centre line (west → east across diamond)
        pygame.draw.line(spr, line_c, (0, hh + ey), (tw, hh + ey), lw)
        # Centre circle
        r = max(2, tw // 8)
        pygame.draw.circle(spr, line_c, (hw, hh + ey), r, lw)
        # Goal boxes near north and south vertices
        if tw >= 18:
            gw = max(2, tw // 5)
            gh = max(1, th // 5)
            # North goal
            ng_pts = [(hw - gw // 2, ey + gh), (hw + gw // 2, ey + gh),
                      (hw + gw // 2, ey), (hw - gw // 2, ey)]
            pygame.draw.polygon(spr, line_c, ng_pts, lw)
            # South goal
            sg_pts = [(hw - gw // 2, th + ey - gh), (hw + gw // 2, th + ey - gh),
                      (hw + gw // 2, th + ey), (hw - gw // 2, th + ey)]
            pygame.draw.polygon(spr, line_c, sg_pts, lw)
        # Corner flags
        if tw >= 22 and stage >= 2:
            flag_c = (230, 60, 60)
            for fx, fy in ((0, hh + ey), (tw, hh + ey)):
                ph = max(3, bh + hh)
                pygame.draw.line(spr, (200, 195, 175), (fx, fy), (fx, fy - ph), max(1, tw // 22))
                pygame.draw.polygon(spr, flag_c,
                                    [(fx, fy - ph), (fx + tw // 7, fy - ph + hh // 2), (fx, fy - ph + hh)])

    def _stadium_det(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        stage: int,
        ey: int,
    ) -> None:
        if tw < 10:
            return
        # Tiered seating lines on both wall faces
        tier_c = _s((110, 95, 135), 30)
        n_tiers = max(2, min(5, bh // max(1, th // 3)))
        lw = max(1, tw // 28)
        for i in range(1, n_tiers):
            v = i / n_tiers
            y_off = int(v * bh)
            pygame.draw.line(spr, tier_c,
                             (0,  hh + ey + y_off),
                             (hw, th + ey + y_off), lw)
            pygame.draw.line(spr, tier_c,
                             (hw, th + ey + y_off),
                             (tw, hh + ey + y_off), lw)
        # Field on top face (green oval)
        if tw >= 14:
            field_c = (38, 148, 58)
            fw = max(4, tw * 2 // 5)
            fh = max(2, th * 2 // 5)
            pygame.draw.ellipse(spr, field_c,
                                pygame.Rect(hw - fw // 2, hh + ey - fh // 2, fw, fh))
            if tw >= 22:
                pygame.draw.ellipse(spr, (240, 240, 240),
                                    pygame.Rect(hw - fw // 2, hh + ey - fh // 2, fw, fh), 1)
        # Scoreboard sticking above roof
        if tw >= 22 and stage >= 2:
            sb_c = (30, 28, 36)
            sw, sh = max(4, tw // 5), max(3, hh)
            sx, sy = hw + hw // 3 - sw // 2, ey - sh - 1
            pygame.draw.rect(spr, sb_c, pygame.Rect(sx, sy, sw, sh))
            pygame.draw.rect(spr, (245, 220, 50), pygame.Rect(sx + 1, sy + 1, sw - 2, max(1, sh - 2)), 1)

    def _golf_det(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        stage: int,
        ey: int,
    ) -> None:
        if tw < 10:
            return
        # Undulating fairway shading on top face
        fairway_c = (72, 165, 78)
        rough_c   = (46, 132, 52)
        pygame.draw.polygon(spr, rough_c,
                            [(hw, ey), (tw, hh + ey), (hw, th + ey), (0, hh + ey)])
        # Fairway strip
        fw = max(4, tw // 3)
        pygame.draw.ellipse(spr, fairway_c,
                            pygame.Rect(hw - fw // 2, ey + th // 4, fw, th // 2))
        # Sand trap (yellow oval near south)
        if tw >= 14:
            sand_c = (210, 190, 110)
            pygame.draw.ellipse(spr, sand_c,
                                pygame.Rect(hw - tw // 5, th + ey - th // 3, tw // 3, th // 4))
        # Flag pin
        ph = max(4, bh + hh)
        pin_x = hw + hw // 4
        pin_y = ey + th // 4
        pygame.draw.line(spr, (195, 185, 165), (pin_x, pin_y), (pin_x, pin_y - ph), max(1, tw // 24))
        flag_c = (220, 55, 55)
        fh = max(2, ph // 3)
        pygame.draw.polygon(spr, flag_c,
                            [(pin_x, pin_y - ph),
                             (pin_x + max(3, tw // 7), pin_y - ph + fh // 2),
                             (pin_x, pin_y - ph + fh)])
        # Cup
        pygame.draw.circle(spr, (24, 22, 28), (pin_x, pin_y), max(1, tw // 14))

    def _pool_det(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        stage: int,
        ey: int,
    ) -> None:
        if tw < 10:
            return
        # Pool water on top face
        water_c  = (58, 158, 218)
        lane_c   = (240, 240, 240)
        edge_c   = (195, 188, 172)
        # Pool surround
        pw = max(4, tw * 3 // 5)
        ph = max(2, th * 2 // 5)
        px, py = hw - pw // 2, hh + ey - ph // 2
        pygame.draw.rect(spr, edge_c, pygame.Rect(px - 1, py - 1, pw + 2, ph + 2))
        pygame.draw.rect(spr, water_c, pygame.Rect(px, py, pw, ph))
        # Lane dividers
        n_lanes = max(2, min(5, pw // max(1, tw // 8)))
        lw = max(1, tw // 32)
        for i in range(1, n_lanes):
            lx = px + pw * i // n_lanes
            pygame.draw.line(spr, lane_c, (lx, py), (lx, py + ph), lw)
        # Diving board sticking off roof edge
        if tw >= 18 and stage >= 2:
            board_c = (188, 172, 130)
            bx = hw - hw // 2
            by = ey
            bl = max(3, tw // 6)
            pygame.draw.rect(spr, board_c,
                             pygame.Rect(bx - bl, by - max(2, tw // 18), bl, max(2, tw // 18)))

    def _cinema_det(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        stage: int,
        ey: int,
    ) -> None:
        if tw < 10:
            return
        # Marquee canopy on left (SW) face, upper portion
        marquee_c = (235, 215, 55)
        mh = max(2, bh // 4)
        marquee_pts = [
            (0,  hh + ey),
            (hw, th + ey),
            (hw, th + ey + mh),
            (0,  hh + ey + mh),
        ]
        pygame.draw.polygon(spr, marquee_c, marquee_pts)
        # Light bulbs along marquee edge
        if tw >= 16:
            bulb_c = (255, 245, 180)
            n_bulbs = max(2, min(8, tw // 10))
            for i in range(n_bulbs):
                t = (i + 0.5) / n_bulbs
                bx = int(t * hw)
                by = int(hh + ey + t * hh) + mh // 2
                pygame.draw.circle(spr, bulb_c, (bx, by), max(1, tw // 24))
        # Neon sign band on right (SE) face
        if tw >= 18:
            neon_c = (205, 55, 90)
            nh = max(2, bh // 5)
            neon_pts = [
                (tw, hh + ey),
                (hw, th + ey),
                (hw, th + ey + nh),
                (tw, hh + ey + nh),
            ]
            pygame.draw.polygon(spr, neon_c, neon_pts)
        # Film reel on roof
        if tw >= 22 and stage >= 2:
            reel_c = (28, 25, 35)
            rr = max(3, tw // 10)
            rx, ry = hw - hw // 3, ey + hh // 2
            pygame.draw.circle(spr, reel_c, (rx, ry), rr)
            pygame.draw.circle(spr, (60, 55, 70), (rx, ry), max(1, rr // 2))
            for angle_deg in (0, 60, 120):
                a = math.radians(angle_deg)
                sx = rx + int(rr * math.cos(a) * 0.7)
                sy = ry + int(rr * math.sin(a) * 0.7)
                pygame.draw.circle(spr, reel_c, (sx, sy), max(1, rr // 4))

    def _museum_det(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        stage: int,
        ey: int,
    ) -> None:
        if tw < 10:
            return
        # Classical columns on left (SW) face
        col_c   = _s((188, 172, 138), 25)
        base_c  = _s((188, 172, 138), -20)
        n_cols  = max(2, min(5, tw // 14))
        col_w   = max(1, tw // (n_cols * 5))
        for i in range(n_cols):
            t = (i + 0.5) / n_cols
            # Column top on left face at u=t
            cx_top = int(t * hw)
            cy_top = int(hh + ey + t * hh)
            pygame.draw.rect(spr, col_c,
                             pygame.Rect(cx_top - col_w, cy_top, col_w * 2, bh))
            # Column base cap
            pygame.draw.rect(spr, base_c,
                             pygame.Rect(cx_top - col_w - 1, cy_top, col_w * 2 + 2, max(1, tw // 22)))
            # Column top cap
            pygame.draw.rect(spr, base_c,
                             pygame.Rect(cx_top - col_w - 1, cy_top + bh - max(1, tw // 22),
                                         col_w * 2 + 2, max(1, tw // 22)))
        # Triangular pediment above roof (gable end)
        if tw >= 18:
            ped_c   = _s((188, 172, 138), 15)
            ped_h   = max(3, hh)
            ped_pts = [(0, hh + ey), (hw, hh + ey - ped_h), (tw, hh + ey)]
            pygame.draw.polygon(spr, ped_c, ped_pts)
            pygame.draw.polygon(spr, base_c, ped_pts, max(1, tw // 28))

    def _zoo_det(
        self,
        spr: pygame.Surface,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        stage: int,
        ey: int,
    ) -> None:
        if tw < 10:
            return
        # Enclosure fence posts on top face edges
        post_c = (158, 132, 82)
        rail_c = (182, 158, 108)
        n_posts = max(2, min(6, tw // 12))
        lw = max(1, tw // 24)
        # Rail lines along top face edges
        pygame.draw.line(spr, rail_c, (0, hh + ey), (hw, ey), lw)
        pygame.draw.line(spr, rail_c, (hw, ey), (tw, hh + ey), lw)
        for i in range(n_posts + 1):
            t = i / n_posts
            # Left edge posts: from West(0, hh+ey) to North(hw, ey)
            px = int(t * hw)
            py = int(hh + ey - t * hh)
            ph = max(3, bh // 2 + hh // 2)
            pygame.draw.line(spr, post_c, (px, py), (px, py - ph), max(1, tw // 22))
        # Animal silhouettes (elephant shape) near centre
        if tw >= 18:
            body_c = (88, 72, 52)
            # Body oval
            bw2 = max(3, tw // 6)
            bh2 = max(2, th // 5)
            bx, by = hw - bw2 // 2, hh + ey - bh2 // 2
            pygame.draw.ellipse(spr, body_c, pygame.Rect(bx, by, bw2, bh2))
            # Head
            hr = max(2, bw2 // 3)
            pygame.draw.circle(spr, body_c, (bx + bw2 + hr // 2, by + bh2 // 3), hr)
            # Trunk
            trunk_c = body_c
            pygame.draw.line(spr, trunk_c,
                             (bx + bw2 + hr, by + bh2 // 3 + hr // 2),
                             (bx + bw2 + hr + max(2, tw // 10), by + bh2),
                             max(1, tw // 20))
        # Trees at stage 2+
        if stage >= 2 and tw >= 20:
            tc = (38, 100, 48)
            hi = (58, 132, 68)
            r = max(2, tw // 9)
            for tx2, ty2 in ((tw * 3 // 4, ey + th // 4), (tw // 5, th * 2 // 3 + ey)):
                pygame.draw.circle(spr, tc, (tx2, ty2), r)
                pygame.draw.circle(spr, hi, (tx2 - r // 3, ty2 - r // 3), max(1, r // 3))

    def _civic_det(
        self,
        spr: pygame.Surface,
        building: BuildingType,
        tw: int,
        th: int,
        bh: int,
        hw: int,
        hh: int,
        color: tuple,
        ey: int,
    ) -> None:
        if building in (BuildingType.POWER_PLANT, BuildingType.LARGE_POWER_PLANT):
            # Red & white striped chimney
            stripe_c = [(210, 60, 50), (240, 240, 240)]
            sh = min(ey, max(6, bh // 3))
            sw = max(3, tw // 11)
            sx = hw + hw // 3
            top = max(0, ey - sh)
            bot = ey + max(2, th // 6)
            n_stripes = max(2, sh // 6)
            for i in range(n_stripes):
                seg_top = top + i * (bot - top) // n_stripes
                seg_bot = top + (i + 1) * (bot - top) // n_stripes
                pygame.draw.rect(spr, stripe_c[i % 2],
                                 pygame.Rect(sx, seg_top, sw, seg_bot - seg_top))
            # Top ring
            pygame.draw.ellipse(spr, (110, 108, 98),
                                pygame.Rect(sx - sw // 2, top - sw // 3, sw * 2, sw * 2 // 3))

            # Glow dots at top if large
            if building == BuildingType.LARGE_POWER_PLANT and tw >= 22:
                pygame.draw.circle(spr, (255, 230, 80), (sx + sw // 2, top - 1), max(2, tw // 20))

        elif building in (BuildingType.WATER_TOWER, BuildingType.LARGE_WATER_TOWER):
            # Cylindrical tank with legs
            tank_r = max(5, tw // 6) if building == BuildingType.LARGE_WATER_TOWER else max(4, tw // 8)
            tank_cy = max(tank_r + 1, ey - tank_r // 2)

            # Legs
            leg_c = _s(color, -25)
            for lx in (hw - tank_r // 2, hw + tank_r // 2):
                leg_top = min(tank_cy, ey - 2)
                leg_bot = ey + hh
                if leg_bot > leg_top:
                    pygame.draw.line(spr, leg_c, (lx, leg_top), (lx, leg_bot), max(1, tw // 24))

            # Tank body
            tank_c = _s(color, 35)
            pygame.draw.circle(spr, _s(color, -10), (hw, tank_cy + tank_r // 4), tank_r)
            pygame.draw.ellipse(spr, tank_c,
                                pygame.Rect(hw - tank_r, tank_cy - tank_r // 2, tank_r * 2, tank_r))
            # Highlight
            pygame.draw.circle(spr, _s(color, 65),
                               (hw - tank_r // 3, tank_cy - tank_r // 3), max(2, tank_r // 3))

        elif building == BuildingType.HOSPITAL:
            # Red cross on roof face
            cross_c = (230, 50, 60)
            lw = max(2, tw // 12)
            # Horizontal bar of cross across the diamond top
            pygame.draw.line(spr, cross_c,
                             (hw - hw // 3, hh + ey),
                             (hw + hw // 3, hh + ey), lw)
            # Vertical bar of cross
            pygame.draw.line(spr, cross_c,
                             (hw, hh + ey - hh // 2),
                             (hw, hh + ey + hh // 2), lw)
            # White accent outline around cross
            if tw >= 18:
                pygame.draw.line(spr, (245, 245, 245),
                                 (hw - hw // 3, hh + ey),
                                 (hw + hw // 3, hh + ey), max(1, lw - 1))
                pygame.draw.line(spr, (245, 245, 245),
                                 (hw, hh + ey - hh // 2),
                                 (hw, hh + ey + hh // 2), max(1, lw - 1))
                pygame.draw.line(spr, cross_c,
                                 (hw - hw // 4, hh + ey),
                                 (hw + hw // 4, hh + ey), lw)
                pygame.draw.line(spr, cross_c,
                                 (hw, hh + ey - hh // 3),
                                 (hw, hh + ey + hh // 3), lw)
            # Helipad circle on left face
            if tw >= 20 and bh >= 10:
                hpad_c = (210, 210, 200)
                hx = hw // 2
                hy = int(hh + ey + hh * 0.5 + bh * 0.4)
                hr = max(3, tw // 9)
                pygame.draw.circle(spr, hpad_c, (hx, hy), hr, max(1, tw // 26))
                pygame.draw.line(spr, hpad_c, (hx - hr + 2, hy), (hx + hr - 2, hy), max(1, tw // 30))

        elif building == BuildingType.AIRPORT:
            # Runway cross
            rwy_c = _s(color, -15)
            lw = max(3, tw // 14)
            pygame.draw.line(spr, rwy_c,
                             (tw // 8, ey + bh // 2),
                             (tw * 7 // 8, ey + bh // 2), lw)
            pygame.draw.line(spr, rwy_c,
                             (hw, ey + bh // 8),
                             (hw, ey + bh * 7 // 8), max(2, lw // 2))
            # Runway markings
            if tw >= 26:
                mk_c = _s(color, 35)
                for i in range(3):
                    mx = tw // 8 + i * tw // 4
                    pygame.draw.line(spr, mk_c,
                                     (mx, ey + bh // 2 - 1),
                                     (mx + tw // 12, ey + bh // 2 - 1), max(1, tw // 28))

    # ------------------------------------------------------------------ #
    # Utility helpers                                                      #
    # ------------------------------------------------------------------ #

    def _bh(self, zone: ZoneType, stage: int, level: int, th: int, recreation_type: RecreationType | None = None) -> int:
        if zone == ZoneType.PARK and recreation_type is not None:
            fracs = _REC_BLD_FRACS.get(recreation_type, _BLD_FRACS[ZoneType.PARK])
        else:
            fracs = _BLD_FRACS.get(zone, [0, 0.8, 1.2, 1.8, 2.4])
        frac = fracs[min(stage, len(fracs) - 1)]
        mult = 1.5 if level > 1 else 1.0
        return max(4, int(th * frac * mult))

    def _civic_bh(self, building: BuildingType, th: int) -> int:
        frac = _CIVIC_HEIGHT.get(building, 1.6)
        return max(8, int(th * frac))

    def _edge_key(self, sn: dict | None) -> tuple | None:
        if sn is None:
            return None
        return (sn.get("north", False), sn.get("east", False),
                sn.get("south", False), sn.get("west", False))

    def _asset(self, name: str, size: int) -> pygame.Surface | None:
        if self.assets is None:
            return None
        return self.assets.get(name, size)

    def _building_asset_name(self, zone: ZoneType, stage: int, level: int, variant: int) -> str:
        if level > 1 and zone in (ZoneType.RESIDENTIAL, ZoneType.COMMERCIAL):
            return f"buildings/{zone.value}_tier2_{stage}_{variant}"
        return f"buildings/{zone.value}_{stage}_{variant}"

    def _blit_grounded(self, surface: pygame.Surface, sprite: pygame.Surface, cx: int, cy: int, th: int) -> None:
        surface.blit(sprite, (cx - sprite.get_width() // 2, cy + th - sprite.get_height()))

    def draw_fire_overlay(
        self, surface: pygame.Surface, cx: int, cy: int, tw: int, th: int
    ) -> None:
        """Draw an animated fire over a burning tile (drawn directly, not cached)."""
        hw, hh = tw // 2, th // 2
        t = pygame.time.get_ticks()
        phase = (t // 220) % 2

        # Base: orange-red diamond covering the tile
        base_col = (210, 55, 10) if phase == 0 else (230, 90, 18)
        pts_diamond = [
            (cx,      cy),
            (cx + hw, cy + hh),
            (cx,      cy + th),
            (cx - hw, cy + hh),
        ]
        pygame.draw.polygon(surface, base_col, pts_diamond)

        # Bright outline
        pygame.draw.polygon(surface, (255, 200, 40), pts_diamond, max(1, tw // 18))

        # Flame tongues rising above the tile centre
        flame_h = max(3, int(th * (1.1 if phase == 0 else 0.8)))
        tip_col  = (255, 230, 60) if phase == 0 else (255, 150, 20)
        fw       = max(2, tw // 6)

        for ox in (-hw // 3, 0, hw // 3):
            bx = cx + ox
            by = cy + hh // 3
            fh = flame_h + (tw // 6 if ox == 0 else 0)
            pygame.draw.polygon(surface, tip_col, [
                (bx - fw, by),
                (bx,      by - fh),
                (bx + fw, by),
            ])

    def _get(self, key: tuple, maker) -> pygame.Surface:
        if key not in self.cache:
            self.cache[key] = maker()
        return self.cache[key]
