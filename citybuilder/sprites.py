from __future__ import annotations

import math

import pygame

from .asset_loader import ImageAssetStore
from .models import BuildingType, TerrainType, ZoneType
from .settings import COLORS, USE_IMAGE_SPRITES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _s(color: tuple, amt: int) -> tuple:
    return tuple(max(0, min(255, c + amt)) for c in color)


def _lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def _diam_pts(tw: int, th: int, oy: int = 0) -> list[tuple[int, int]]:
    hw, hh = tw // 2, th // 2
    return [(hw, oy), (tw, oy + hh), (hw, oy + th), (0, oy + hh)]


def tile_variant(x: int, y: int) -> int:
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

_CIVIC_COLOR_KEY = {
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

_CIVIC_HEIGHT = {
    BuildingType.POLICE:            1.40,
    BuildingType.FIRE:              1.40,
    BuildingType.SCHOOL:            1.50,
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
    ) -> None:
        key = ("ZB", zone, level, tw)
        spr = self._get(key, lambda: self._zone_base_spr(zone, level, tw, th))
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
    ) -> None:
        if development < 0.06 or zone not in _BLD_FRACS:
            return
        stage   = max(1, min(4, int(development * 4) + 1))
        v       = variant & 3
        asset = self._asset(self._building_asset_name(zone, stage, level, v), tw)
        if asset is not None:
            if rotation in (1, 3):
                flip_key = ("BAF", zone, stage, level, tw, v)
                asset = self._get(flip_key, lambda: pygame.transform.flip(asset, True, False))
            self._blit_grounded(surface, asset, cx, cy, th)
            return
        bh      = self._bh(zone, stage, level, th)
        extra_h = th // 2
        key     = ("B", zone, stage, level, tw, th, v)
        spr     = self._get(key, lambda: self._building_spr(zone, tw, th, bh, stage, level, v, extra_h))
        # For odd rotations (1 & 3) mirror the building so the visible face
        # roughly corresponds to what you'd see from that viewing angle.
        if rotation in (1, 3):
            flip_key = ("BF", zone, stage, level, tw, th, v)
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

    def _zone_base_spr(self, zone: ZoneType, level: int, tw: int, th: int) -> pygame.Surface:
        spr = pygame.Surface((tw, th), pygame.SRCALPHA)
        d = _diam_pts(tw, th)
        hw, hh = tw // 2, th // 2
        grass = _GRASS[0]
        zone_c = COLORS.get(zone.value, (100, 100, 100))
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
    ) -> pygame.Surface:
        surf_h = th + bh + extra_h
        spr = pygame.Surface((tw, surf_h), pygame.SRCALPHA)
        hw, hh = tw // 2, th // 2
        ey = extra_h

        walls = _ZONE_WALL.get(zone, [(150, 150, 150)])
        base_w = walls[variant % len(walls)]
        roof_c = _ZONE_ROOF.get(zone, (80, 80, 80))
        win_c  = _ZONE_WIN.get(zone, (200, 200, 180))
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
            self._park_det(spr, tw, th, bh, hw, hh, stage, ey)
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

    def _bh(self, zone: ZoneType, stage: int, level: int, th: int) -> int:
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

    def _get(self, key: tuple, maker) -> pygame.Surface:
        if key not in self.cache:
            self.cache[key] = maker()
        return self.cache[key]
