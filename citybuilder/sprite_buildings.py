"""
sprite_buildings.py — Surface generators for zones, civic buildings, and roads.
"""
from __future__ import annotations

import math

import pygame

from .models import BuildingType, RecreationType, ZoneType
from .settings import COLORS
from .sprite_data import (
    _BLD_FRACS, _CIVIC_COLOR_KEY, _CIVIC_HEIGHT, _CIVIC_LABEL,
    _GRASS, _HIGHRISE_ROOF, _HIGHRISE_WALL, _HIGHRISE_WIN,
    _REC_BLD_FRACS, _REC_ROOF, _REC_WALL,
    _ZONE_ROOF, _ZONE_WALL, _ZONE_WIN,
    _diam_pts, _s,
)
from .sprite_details import (
    add_cinema_detail, add_civic_detail, add_com_detail, add_golf_detail,
    add_ind_detail, add_museum_detail, add_park_detail, add_playground_detail,
    add_pool_detail, add_res_detail, add_sports_field_detail,
    add_stadium_detail, add_zoo_detail,
)


# ---------------------------------------------------------------------------
# Height helpers
# ---------------------------------------------------------------------------

def bh_for_zone(
    zone: ZoneType,
    stage: int,
    level: int,
    th: int,
    recreation_type: RecreationType | None = None,
) -> int:
    """Building height in pixels for a zoned tile."""
    if zone == ZoneType.PARK and recreation_type is not None:
        fracs = _REC_BLD_FRACS.get(recreation_type, _BLD_FRACS[ZoneType.PARK])
    else:
        fracs = _BLD_FRACS.get(zone, [0, 0.8, 1.2, 1.8, 2.4])
    frac = fracs[min(stage, len(fracs) - 1)]
    mult = 2.5 if level >= 3 else (1.5 if level == 2 else 1.0)
    return max(4, int(th * frac * mult))


def bh_for_civic(building: BuildingType, th: int) -> int:
    """Building height in pixels for a civic building."""
    return max(8, int(th * _CIVIC_HEIGHT.get(building, 1.6)))


# ---------------------------------------------------------------------------
# Wall / story helpers (module-private)
# ---------------------------------------------------------------------------

def _left_windows(spr, tw, bh, hw, hh, ey, wc, n_cols, n_rows):
    if tw < 16 or bh < 8 or n_cols < 1 or n_rows < 1:
        return
    mg_u, mg_v = 0.14, 0.10
    cell_u = (1.0 - 2 * mg_u) / n_cols
    cell_v = (1.0 - 2 * mg_v) / n_rows
    wu      = cell_u * 0.62
    wv      = cell_v * 0.56
    frame_c = _s(wc, -60)

    def lpt(u, v):
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


def _right_windows(spr, tw, th, bh, hw, hh, ey, wc, n_cols, n_rows):
    if tw < 16 or bh < 8 or n_cols < 1 or n_rows < 1:
        return
    mg_u, mg_v = 0.14, 0.10
    cell_u = (1.0 - 2 * mg_u) / n_cols
    cell_v = (1.0 - 2 * mg_v) / n_rows
    wu      = cell_u * 0.62
    wv      = cell_v * 0.56
    frame_c = _s(wc, -60)

    def rpt(u, v):
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


def _story_lines(spr, tw, th, bh, hw, hh, ey, lc, n_floors):
    if tw < 18 or n_floors < 2 or bh < 10:
        return
    lw = max(1, tw // 32)
    for f in range(1, n_floors):
        v = f / n_floors
        y = int(v * bh)
        pygame.draw.line(spr, lc, (0,  hh + ey + y), (hw, th + ey + y), lw)
        pygame.draw.line(spr, lc, (hw, th + ey + y), (tw, hh + ey + y), lw)


# ---------------------------------------------------------------------------
# Highrise roof detail
# ---------------------------------------------------------------------------

def _add_highrise_roof_detail(
    spr: pygame.Surface,
    zone: ZoneType,
    tw: int, th: int, bh: int,
    hw: int, hh: int, ey: int,
    roof_c: tuple,
    variant: int,
) -> None:
    """Draws rooftop details on level-3 highrise buildings (antennas, helipad, tanks)."""
    if tw < 18:
        return
    roof_top = ey  # y-coord of the roof diamond north-vertex

    if zone == ZoneType.COMMERCIAL:
        # Antenna mast on commercial towers
        mast_h = max(4, bh // 6)
        mast_x = hw
        mast_y = roof_top
        lw = max(1, tw // 28)
        pygame.draw.line(spr, _s(roof_c, 40), (mast_x, mast_y), (mast_x, mast_y - mast_h), lw)
        # Crossbar
        cw = max(2, tw // 10)
        pygame.draw.line(spr, _s(roof_c, 30),
                         (mast_x - cw, mast_y - mast_h * 2 // 3),
                         (mast_x + cw, mast_y - mast_h * 2 // 3), lw)
        # Blinking light cap (static red dot)
        if tw >= 24:
            pygame.draw.circle(spr, (230, 60, 60), (mast_x, mast_y - mast_h), max(1, tw // 30))
        # Satellite dishes (variant-dependent)
        if variant % 2 == 0 and tw >= 24:
            dx, dy = hw - tw // 5, roof_top + hh // 3
            r = max(2, tw // 18)
            pygame.draw.ellipse(spr, _s(roof_c, 20), (dx - r, dy - r // 2, r * 2, r))
    else:
        # Residential highrise: rooftop water tank + railing
        if tw >= 22:
            tank_r = max(2, tw // 12)
            tx, ty = hw - tw // 6, roof_top + hh // 4
            # Tank body (barrel shape)
            pygame.draw.ellipse(spr, _s(roof_c, -10), (tx - tank_r, ty, tank_r * 2, max(2, tank_r)))
            pygame.draw.rect(spr, _s(roof_c, -20),
                             pygame.Rect(tx - tank_r, ty - tank_r, tank_r * 2, tank_r))
            pygame.draw.ellipse(spr, _s(roof_c, 10),
                                (tx - tank_r, ty - tank_r - 1, tank_r * 2, max(2, tank_r // 2)))
        # Thin railing around roof perimeter (simplified edge lines)
        lw = max(1, tw // 32)
        rc = _s(roof_c, -30)
        railing_pts = [(hw, ey - 2), (tw - 2, hh + ey), (hw, th + ey - 2), (2, hh + ey)]
        pygame.draw.polygon(spr, rc, railing_pts, lw)
        # Balcony bump on variant tiles
        if variant >= 2 and bh >= 20 and tw >= 22:
            by = hh + ey + bh // 4
            bw2 = max(2, tw // 10)
            bh2 = max(2, th // 5)
            pygame.draw.rect(spr, _s(roof_c, 15), (0 - bw2, by, bw2 * 2, bh2))


# ---------------------------------------------------------------------------
# Sprite generators
# ---------------------------------------------------------------------------

def make_zone_base_spr(
    zone: ZoneType,
    level: int,
    tw: int,
    th: int,
    recreation_type: RecreationType | None = None,
) -> pygame.Surface:
    """Semi-transparent lot indicator diamond for a zoned tile."""
    spr = pygame.Surface((tw, th), pygame.SRCALPHA)
    d   = _diam_pts(tw, th)
    hw, hh = tw // 2, th // 2
    grass     = _GRASS[0]
    color_key = (recreation_type.value
                 if (zone == ZoneType.PARK and recreation_type is not None)
                 else zone.value)
    zone_c = COLORS.get(color_key, (100, 100, 100))
    blend  = tuple(int(grass[i] * 0.5 + zone_c[i] * 0.5) for i in range(3))

    ALPHA = 85
    pygame.draw.polygon(spr, (*blend, ALPHA), d)
    pygame.draw.polygon(spr, (*_s(blend, 24), ALPHA),  [(hw, 0),  (0,  hh), (hw, hh)])
    pygame.draw.polygon(spr, (*_s(blend, -30), ALPHA), [(hw, th), (tw, hh), (hw, hh)])
    mid = _diam_pts(tw - max(2, tw // 10), th - max(1, th // 8), max(1, th // 16))
    pygame.draw.polygon(spr, (*blend, ALPHA), mid)

    bw = max(1, tw // 20)
    pygame.draw.polygon(spr, _s(zone_c, -20), d, bw)
    if level >= 2 and tw >= 16:
        inner = _diam_pts(tw - bw * 4, th - bw * 2, bw * 2)
        pygame.draw.polygon(spr, _s(zone_c, 10), inner, bw)
    if level >= 3 and tw >= 16:
        # Extra concentric ring to mark highrise lots.
        inner2 = _diam_pts(tw - bw * 8, th - bw * 4, bw * 4)
        pygame.draw.polygon(spr, _s(zone_c, 30), inner2, bw)
    if tw >= 22:
        dot_r = max(1, tw // 22)
        for px, py in ((hw * 3 // 2, hh // 2), (hw // 2, hh * 3 // 2)):
            pygame.draw.circle(spr, _s(zone_c, 20), (px, py), dot_r)
    return spr


def make_building_spr(
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
    """Isometric zone building surface for the given stage, level, and variant."""
    surf_h = th + bh + extra_h
    spr    = pygame.Surface((tw, surf_h), pygame.SRCALPHA)
    hw, hh = tw // 2, th // 2
    ey = extra_h

    is_highrise = level >= 3 and zone in (ZoneType.RESIDENTIAL, ZoneType.COMMERCIAL)

    if zone == ZoneType.PARK and recreation_type is not None:
        walls  = _REC_WALL.get(recreation_type, _ZONE_WALL[ZoneType.PARK])
        roof_c = _REC_ROOF.get(recreation_type, _ZONE_ROOF[ZoneType.PARK])
        win_c  = _ZONE_WIN[ZoneType.PARK]
    elif is_highrise:
        walls  = _HIGHRISE_WALL.get(zone, [(160, 172, 185)])
        roof_c = _HIGHRISE_ROOF.get(zone, (120, 130, 145))
        win_c  = _HIGHRISE_WIN.get(zone, (185, 210, 235))
    else:
        walls  = _ZONE_WALL.get(zone, [(150, 150, 150)])
        roof_c = _ZONE_ROOF.get(zone, (80, 80, 80))
        win_c  = _ZONE_WIN.get(zone, (200, 200, 180))
    base_w  = walls[variant % len(walls)]
    top_c   = _s(base_w,  40)
    left_c  = _s(base_w,   6) if not is_highrise else _s(base_w, 14)
    right_c = _s(base_w, -50) if not is_highrise else _s(base_w, -30)
    outline = _s(base_w, -85)
    story_c = _s(base_w, -38)

    roof  = [(hw, ey),      (tw, hh + ey), (hw, th + ey),      (0, hh + ey)]
    left  = [(0, hh + ey),  (hw, th + ey), (hw, th + bh + ey), (0, hh + bh + ey)]
    right = [(tw, hh + ey), (hw, th + ey), (hw, th + bh + ey), (tw, hh + bh + ey)]

    pygame.draw.polygon(spr, right_c, right)
    pygame.draw.polygon(spr, left_c,  left)
    pygame.draw.polygon(spr, top_c,   roof)

    if bh >= 10:
        gh = max(2, bh // 5)
        pygame.draw.polygon(spr, _s(left_c,   18),
                            [(0, hh+ey),      (hw, th+ey),      (hw, th+ey+gh),      (0, hh+ey+gh)])
        pygame.draw.polygon(spr, _s(left_c,  -18),
                            [(0, hh+bh+ey-gh), (hw, th+bh+ey-gh), (hw, th+bh+ey), (0, hh+bh+ey)])
        pygame.draw.polygon(spr, _s(right_c,  16),
                            [(tw, hh+ey),     (hw, th+ey),      (hw, th+ey+gh),      (tw, hh+ey+gh)])
        pygame.draw.polygon(spr, _s(right_c, -12),
                            [(tw, hh+bh+ey-gh), (hw, th+bh+ey-gh), (hw, th+bh+ey), (tw, hh+bh+ey)])

    n_floors = max(1, bh // max(1, th // 2))
    if is_highrise:
        # Curtain-wall treatment: dense horizontal glass bands across both faces.
        nc = max(2, min(8, tw // 10))
        nr = max(4, min(16, n_floors * 3))
        _left_windows(spr, tw, bh, hw, hh, ey, win_c, nc, nr)
        _right_windows(spr, tw, th, bh, hw, hh, ey, _s(win_c, -18), nc, nr)
        # Vertical steel frame lines on left face.
        if tw >= 16:
            fc = _s(base_w, -55)
            lw = max(1, tw // 36)
            for col in range(1, nc):
                t = col / nc
                fx = int(t * hw)
                fy_top  = hh + ey + int(t * hh)
                fy_bot  = hh + bh + ey + int(t * hh)
                pygame.draw.line(spr, fc, (fx, fy_top), (fx, fy_bot), lw)
                # Mirror on right face
                rfx = tw - fx
                pygame.draw.line(spr, fc, (rfx, fy_top), (rfx, fy_bot), lw)
        # Dense horizontal spandrel bands (structural bands between window rows).
        if bh >= 20:
            sc = _s(base_w, -42)
            band_h = max(1, bh // (nr * 2))
            for row in range(nr + 1):
                ry = hh + bh + ey - int(row / max(1, nr) * bh)
                lx0, lx1 = 0, hw
                rx0, rx1 = hw, tw
                pygame.draw.line(spr, sc, (lx0, ry + int(ry / tw * hh // 4)), (lx1, ry + hh // 8), band_h)
                pygame.draw.line(spr, _s(sc, 8), (rx0, ry + hh // 8), (rx1, ry + int(ry / tw * hh // 4)), band_h)
    elif zone == ZoneType.RESIDENTIAL:
        nc, nr = max(1, min(3, tw // 22)), max(1, min(4, n_floors))
        _left_windows(spr, tw, bh, hw, hh, ey, win_c, nc, nr)
        _right_windows(spr, tw, th, bh, hw, hh, ey, _s(win_c, -25), nc, nr)
    elif zone == ZoneType.COMMERCIAL:
        nc = max(1, min(5, tw // 16))
        nr = max(1, min(6, n_floors * 2))
        _left_windows(spr, tw, bh, hw, hh, ey, win_c, nc, nr)
        _right_windows(spr, tw, th, bh, hw, hh, ey, _s(win_c, -30), nc, nr)
    elif zone == ZoneType.INDUSTRIAL:
        nc = max(1, min(2, tw // 28))
        nr = max(1, min(3, n_floors))
        _left_windows(spr, tw, bh, hw, hh, ey, win_c, nc, nr)
        _right_windows(spr, tw, th, bh, hw, hh, ey, _s(win_c, -30), max(1, nc - 1), nr)

    if bh >= 18 and n_floors >= 2:
        _story_lines(spr, tw, th, bh, hw, hh, ey, story_c, min(n_floors, 5))

    pygame.draw.polygon(spr, outline, right, 1)
    pygame.draw.polygon(spr, outline, left,  1)
    pygame.draw.polygon(spr, outline, roof,  1)
    pygame.draw.line(spr, outline, (0,  hh + bh + ey), (hw, th + bh + ey), 1)
    pygame.draw.line(spr, outline, (tw, hh + bh + ey), (hw, th + bh + ey), 1)

    if is_highrise:
        _add_highrise_roof_detail(spr, zone, tw, th, bh, hw, hh, ey, roof_c, variant)
    elif zone == ZoneType.RESIDENTIAL:
        add_res_detail(spr, tw, th, bh, hw, hh, stage, variant, roof_c, ey)
    elif zone == ZoneType.COMMERCIAL:
        add_com_detail(spr, tw, th, bh, hw, hh, stage, variant, ey)
    elif zone == ZoneType.INDUSTRIAL:
        add_ind_detail(spr, tw, th, bh, hw, hh, stage, variant, ey)
    elif zone == ZoneType.PARK:
        rec = recreation_type or RecreationType.PARK
        _PARK_DETAIL = {
            RecreationType.PARK:         add_park_detail,
            RecreationType.PLAYGROUND:   add_playground_detail,
            RecreationType.SPORTS_FIELD: add_sports_field_detail,
            RecreationType.STADIUM:      add_stadium_detail,
            RecreationType.GOLF_COURSE:  add_golf_detail,
            RecreationType.POOL:         add_pool_detail,
            RecreationType.CINEMA:       add_cinema_detail,
            RecreationType.MUSEUM:       add_museum_detail,
            RecreationType.ZOO:          add_zoo_detail,
        }
        fn = _PARK_DETAIL.get(rec)
        if fn is not None:
            fn(spr, tw, th, bh, hw, hh, stage, ey)
    return spr


def make_civic_spr(
    building: BuildingType,
    tw: int,
    th: int,
    bh: int,
    extra_h: int,
    font,
) -> pygame.Surface:
    """Isometric civic building surface (power plant, hospital, etc.)."""
    surf_h = th + bh + extra_h
    spr    = pygame.Surface((tw, surf_h), pygame.SRCALPHA)
    hw, hh = tw // 2, th // 2
    ey = extra_h

    ck     = _CIVIC_COLOR_KEY.get(building, "building_dark")
    base_c = COLORS.get(ck, (80, 80, 80))
    top_c  = _s(base_c,  45)
    left_c = base_c
    right_c = _s(base_c, -55)
    outline = _s(base_c, -90)
    story_c = _s(base_c, -40)

    roof  = [(hw, ey),      (tw, hh + ey), (hw, th + ey),      (0, hh + ey)]
    left  = [(0, hh + ey),  (hw, th + ey), (hw, th + bh + ey), (0, hh + bh + ey)]
    right = [(tw, hh + ey), (hw, th + ey), (hw, th + bh + ey), (tw, hh + bh + ey)]

    pygame.draw.polygon(spr, right_c, right)
    pygame.draw.polygon(spr, left_c,  left)
    pygame.draw.polygon(spr, top_c,   roof)

    win_c = _s(base_c, 80)
    if tw >= 18 and bh >= 12:
        n_floors = max(1, bh // max(1, th // 2))
        nc = max(1, min(3, tw // 24))
        nr = max(1, min(4, n_floors))
        _left_windows(spr, tw, bh, hw, hh, ey, win_c, nc, nr)
        _right_windows(spr, tw, th, bh, hw, hh, ey, _s(win_c, -30), nc, nr)
        if n_floors >= 2:
            _story_lines(spr, tw, th, bh, hw, hh, ey, story_c, min(n_floors, 4))

    pygame.draw.polygon(spr, outline, right, 1)
    pygame.draw.polygon(spr, outline, left,  1)
    pygame.draw.polygon(spr, outline, roof,  1)
    pygame.draw.line(spr, outline, (0,  hh + bh + ey), (hw, th + bh + ey), 1)
    pygame.draw.line(spr, outline, (tw, hh + bh + ey), (hw, th + bh + ey), 1)

    add_civic_detail(spr, building, tw, th, bh, hw, hh, base_c, ey)

    if tw >= 24:
        label = _CIVIC_LABEL.get(building, "?")
        text  = font.render(label, True, (245, 245, 240))
        sx    = hw - text.get_width() // 2
        sy    = ey + max(2, bh // 4 - text.get_height() // 2)
        spr.blit(font.render(label, True, outline), (sx + 1, sy + 1))
        spr.blit(text, (sx, sy))
    return spr


def make_road_spr(tw: int, th: int, connections: dict[str, bool]) -> pygame.Surface:
    """Road tile surface with sidewalk outer ring and asphalt core."""
    spr    = pygame.Surface((tw, th), pygame.SRCALPHA)
    hw, hh = tw // 2, th // 2
    d      = _diam_pts(tw, th)

    sidewalk_c = (158, 155, 142)
    pygame.draw.polygon(spr, sidewalk_c, d)

    inset     = max(2, tw // 14)
    asphalt_c = (54, 58, 65)
    pygame.draw.polygon(spr, asphalt_c,
                        [(hw, inset), (tw - inset, hh), (hw, th - inset), (inset, hh)])

    if tw >= 14:
        center    = (hw, hh)
        edge_mids = {
            "north": (tw * 3 // 4, th // 4),
            "east":  (tw * 3 // 4, th * 3 // 4),
            "south": (tw // 4,     th * 3 // 4),
            "west":  (tw // 4,     th // 4),
        }
        arm    = max(2, tw // 10)
        arm_sw = max(2, arm + 2)

        for direction, ep in edge_mids.items():
            if not connections.get(direction, False):
                continue
            dx, dy = ep[0] - center[0], ep[1] - center[1]
            length = max(1.0, math.sqrt(dx * dx + dy * dy))
            nx = -dy / length
            ny =  dx / length

            pygame.draw.polygon(spr, sidewalk_c, [
                (int(center[0] + nx * arm_sw), int(center[1] + ny * arm_sw)),
                (int(ep[0]     + nx * arm_sw), int(ep[1]     + ny * arm_sw)),
                (int(ep[0]     - nx * arm_sw), int(ep[1]     - ny * arm_sw)),
                (int(center[0] - nx * arm_sw), int(center[1] - ny * arm_sw)),
            ])
            pygame.draw.polygon(spr, asphalt_c, [
                (int(center[0] + nx * arm), int(center[1] + ny * arm)),
                (int(ep[0]     + nx * arm), int(ep[1]     + ny * arm)),
                (int(ep[0]     - nx * arm), int(ep[1]     - ny * arm)),
                (int(center[0] - nx * arm), int(center[1] - ny * arm)),
            ])

        pygame.draw.circle(spr, asphalt_c, center, arm + 1)

        if tw >= 22:
            lane_c = (195, 180, 100)
            for direction, ep in edge_mids.items():
                if connections.get(direction, False):
                    mx = (center[0] * 2 + ep[0]) // 3
                    my = (center[1] * 2 + ep[1]) // 3
                    pygame.draw.circle(spr, lane_c, (mx, my), max(1, tw // 30))

    pygame.draw.polygon(spr, (132, 128, 116), d, max(1, tw // 38))
    return spr
