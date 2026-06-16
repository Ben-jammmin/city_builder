"""
sprite_details.py — Per-zone and per-civic-building detail painters.

Each function receives a Surface and paints zone-specific visual elements
(roof shapes, equipment, field markings, etc.) on top of the base geometry
produced by make_building_spr / make_civic_spr in sprite_buildings.py.
"""
from __future__ import annotations

import math

import pygame

from .models import BuildingType
from .sprite_data import _s


def add_res_detail(spr, tw, th, bh, hw, hh, stage, variant, roof_c, ey):
    """Peaked roof, chimney, and doorway on a residential building."""
    if tw >= 16:
        peak    = min(ey, max(4, bh // 4))
        pk_top  = (hw, ey - peak)
        roof_pts = [pk_top, (0, hh + ey), (hw, th + ey), (tw, hh + ey)]
        pygame.draw.polygon(spr, roof_c, roof_pts)
        pygame.draw.polygon(spr, _s(roof_c, -28), [pk_top, (hw, th + ey), (tw, hh + ey)])
        pygame.draw.polygon(spr, _s(roof_c, -50), roof_pts, 1)
        pygame.draw.line(spr, _s(roof_c, -38), pk_top, (hw, th + ey), max(1, tw // 30))

    if tw >= 22 and stage >= 2:
        ch_w   = max(2, tw // 16)
        ch_x   = hw + tw // 6
        ch_top = max(0, ey - max(3, bh // 8))
        ch_bot = ey + max(1, th // 8)
        pygame.draw.rect(spr, _s(roof_c, -20),
                         pygame.Rect(ch_x, ch_top, ch_w, ch_bot - ch_top))
        pygame.draw.line(spr, _s(roof_c, 15),
                         (ch_x, ch_top), (ch_x + ch_w, ch_top), max(1, tw // 30))

    if tw >= 26 and stage >= 2:
        dw = max(2, tw // 14)
        dh = max(3, bh // 6)
        dx = max(1, tw // 10)
        dy = th + bh + ey - dh
        pygame.draw.rect(spr, (60, 50, 40), pygame.Rect(dx, dy, dw, dh), border_radius=1)


def add_com_detail(spr, tw, th, bh, hw, hh, stage, variant, ey):
    """Flat parapet roof, antenna spire, and rooftop AC unit on a commercial building."""
    if tw >= 16:
        rd = (52, 68, 88)
        pygame.draw.polygon(spr, rd, [(hw, ey), (tw, hh + ey), (hw, th + ey), (0, hh + ey)])
        par_h   = max(2, bh // 10)
        ppl = [(0, hh + ey), (hw, th + ey), (hw, th + ey - par_h), (0, hh + ey - par_h)]
        ppr = [(tw, hh + ey), (hw, th + ey), (hw, th + ey - par_h), (tw, hh + ey - par_h)]
        pygame.draw.polygon(spr, _s(rd, 25), ppl)
        pygame.draw.polygon(spr, _s(rd,  8), ppr)
        pygame.draw.polygon(spr, _s(rd, -20), ppl, 1)
        pygame.draw.polygon(spr, _s(rd, -20), ppr, 1)

    if tw >= 22 and stage >= 3:
        sh = min(ey, max(4, tw // 9))
        pygame.draw.line(spr, (72, 80, 92), (hw, ey), (hw, ey - sh), max(1, tw // 26))
        pygame.draw.circle(spr, (88, 100, 112), (hw, ey - sh), max(1, tw // 28))

    if tw >= 20 and stage >= 2:
        aw = max(3, tw // 12)
        ax = hw - aw // 2
        ay = th + ey - aw - max(1, bh // 10)
        pygame.draw.rect(spr, (78, 90, 104), pygame.Rect(ax, ay, aw, aw), border_radius=1)


def add_ind_detail(spr, tw, th, bh, hw, hh, stage, variant, ey):
    """Corrugated roof ridges, smokestacks, and hazard stripes on an industrial building."""
    if tw < 12:
        return

    if tw >= 18:
        rc      = _s((82, 78, 65), -15)
        n_ridges = max(1, tw // 14)
        for i in range(n_ridges):
            u  = (i + 0.5) / n_ridges
            p1 = (int(u * hw),        int(hh + ey + u * hh))
            p2 = (int(hw + u * hw),   int(th + ey - u * hh))
            pygame.draw.line(spr, rc, p1, p2, 1)

    sc      = (72, 68, 58)
    sh      = max(4, bh // 3)
    sw      = max(2, tw // 14)
    offsets = [hw + hw // 3, hw - hw // 5] if stage >= 3 else [hw + hw // 3]
    for i, ox in enumerate(offsets[:min(len(offsets), stage)]):
        top = max(0, ey - sh + i * 2)
        bot = ey + max(2, th // 6)
        pygame.draw.rect(spr, sc, pygame.Rect(ox, top, sw, bot - top))
        pygame.draw.ellipse(spr, _s(sc, 25),
                            pygame.Rect(ox - sw // 2, top - sw // 2, sw * 2, sw))
        pygame.draw.line(spr, (102, 98, 88), (ox, top), (ox + sw, top), max(1, tw // 30))

    if tw >= 20 and stage >= 2:
        stripe_h = max(2, bh // 8)
        n_stripes = max(2, tw // 16)
        for i in range(n_stripes):
            u  = i / n_stripes
            x1 = int(u * hw)
            x2 = int((u + 1.0 / n_stripes) * hw)
            y1 = int(hh + ey + u * hh + (1.0 - stripe_h / bh) * bh)
            y2 = int(hh + ey + (u + 1.0 / n_stripes) * hh + (1.0 - stripe_h / bh) * bh)
            c  = (220, 180, 40) if i % 2 == 0 else (40, 40, 40)
            pygame.draw.polygon(spr, c,
                                [(x1, y1), (x2, y2), (x2, y2 + stripe_h), (x1, y1 + stripe_h)])


def add_park_detail(spr, tw, th, bh, hw, hh, stage, ey):
    """Park trees with slender pillars suggesting an open pavilion."""
    if tw < 12:
        return
    if tw >= 16:
        pillar_c = (148, 138, 115)
        pw       = max(1, tw // 20)
        for px, py in [(tw // 8, hh + ey), (tw * 7 // 8, hh + ey), (hw, th + ey)]:
            pygame.draw.rect(spr, pillar_c, pygame.Rect(px - pw // 2, py, pw, bh))

    tc    = (38, 90, 50)
    hi    = (60, 126, 74)
    shad  = (28, 66, 36)
    trunk = (72, 62, 42)
    r     = max(4, tw // 7)
    positions = [
        (hw,           ey + bh // 4),
        (hw - tw // 5, ey + bh * 3 // 5),
        (hw + tw // 5, ey + bh * 3 // 5),
    ]
    for i, (px, py) in enumerate(positions[:min(len(positions), stage + 1)]):
        ri = max(3, r - i)
        pygame.draw.ellipse(spr, shad,
                            pygame.Rect(px - ri, py + ri // 3, ri * 2, max(2, ri // 2)))
        pygame.draw.rect(spr, trunk,
                         pygame.Rect(px - 1, py + ri // 2, max(2, tw // 26), max(3, th // 5)))
        pygame.draw.circle(spr, tc, (px, py), ri)
        pygame.draw.circle(spr, hi, (px - ri // 3, py - ri // 3), max(1, ri // 3))


def add_playground_detail(spr, tw, th, bh, hw, hh, stage, ey):
    """Slide, A-frame swing set, chain seat, and sandbox."""
    if tw < 10:
        return
    lw = max(2, tw // 14)
    pygame.draw.line(spr, (220, 70, 50),
                     (hw + hw // 3, ey + hh // 2),
                     (hw - hw // 4, th + ey - th // 4), lw)
    if tw >= 14:
        fc  = (55, 130, 220)
        ph  = max(4, hh + bh // 3)
        px1 = hw - tw // 5
        px2 = hw + tw // 5
        by  = ey - ph
        pygame.draw.line(spr, fc, (px1, ey), (px1, by), max(1, tw // 20))
        pygame.draw.line(spr, fc, (px2, ey), (px2, by), max(1, tw // 20))
        pygame.draw.line(spr, fc, (px1, by), (px2, by), max(1, tw // 20))
        if stage >= 2 and tw >= 20:
            sy = by + ph // 3
            pygame.draw.line(spr, (195, 178, 132), (hw, by), (hw, sy), 1)
            sw = max(2, tw // 8)
            pygame.draw.rect(spr, (100, 65, 28),
                             pygame.Rect(hw - sw // 2, sy, sw, max(1, tw // 22)))
    if tw >= 18 and stage >= 2:
        pygame.draw.ellipse(spr, (215, 195, 120),
                            pygame.Rect(hw // 2, th + ey - th // 3, hw, max(2, th // 4)))


def add_sports_field_detail(spr, tw, th, bh, hw, hh, stage, ey):
    """Centre line, circle, goal boxes, and corner flags on a sports field."""
    if tw < 10:
        return
    lc = (240, 240, 240)
    lw = max(1, tw // 24)
    pygame.draw.line(spr, lc, (0, hh + ey), (tw, hh + ey), lw)
    pygame.draw.circle(spr, lc, (hw, hh + ey), max(2, tw // 8), lw)
    if tw >= 18:
        gw   = max(2, tw // 5)
        gh   = max(1, th // 5)
        pygame.draw.polygon(spr, lc,
                            [(hw - gw // 2, ey + gh), (hw + gw // 2, ey + gh),
                             (hw + gw // 2, ey),      (hw - gw // 2, ey)], lw)
        pygame.draw.polygon(spr, lc,
                            [(hw - gw // 2, th + ey - gh), (hw + gw // 2, th + ey - gh),
                             (hw + gw // 2, th + ey),      (hw - gw // 2, th + ey)], lw)
    if tw >= 22 and stage >= 2:
        fc = (230, 60, 60)
        for fx, fy in ((0, hh + ey), (tw, hh + ey)):
            ph = max(3, bh + hh)
            pygame.draw.line(spr, (200, 195, 175), (fx, fy), (fx, fy - ph), max(1, tw // 22))
            pygame.draw.polygon(spr, fc,
                                [(fx, fy - ph),
                                 (fx + tw // 7, fy - ph + hh // 2),
                                 (fx, fy - ph + hh)])


def add_stadium_detail(spr, tw, th, bh, hw, hh, stage, ey):
    """Tiered seating lines, oval field on roof, and scoreboard."""
    if tw < 10:
        return
    tc      = _s((110, 95, 135), 30)
    n_tiers = max(2, min(5, bh // max(1, th // 3)))
    lw      = max(1, tw // 28)
    for i in range(1, n_tiers):
        v    = i / n_tiers
        y    = int(v * bh)
        pygame.draw.line(spr, tc, (0,  hh + ey + y), (hw, th + ey + y), lw)
        pygame.draw.line(spr, tc, (hw, th + ey + y), (tw, hh + ey + y), lw)
    if tw >= 14:
        fw = max(4, tw * 2 // 5)
        fh = max(2, th * 2 // 5)
        pygame.draw.ellipse(spr, (38, 148, 58),
                            pygame.Rect(hw - fw // 2, hh + ey - fh // 2, fw, fh))
        if tw >= 22:
            pygame.draw.ellipse(spr, (240, 240, 240),
                                pygame.Rect(hw - fw // 2, hh + ey - fh // 2, fw, fh), 1)
    if tw >= 22 and stage >= 2:
        sw, sh = max(4, tw // 5), max(3, hh)
        sx, sy = hw + hw // 3 - sw // 2, ey - sh - 1
        pygame.draw.rect(spr, (30, 28, 36), pygame.Rect(sx, sy, sw, sh))
        pygame.draw.rect(spr, (245, 220, 50),
                         pygame.Rect(sx + 1, sy + 1, sw - 2, max(1, sh - 2)), 1)


def add_golf_detail(spr, tw, th, bh, hw, hh, stage, ey):
    """Fairway, sand trap, and flag pin for a golf course."""
    if tw < 10:
        return
    pygame.draw.polygon(spr, (46, 132, 52),
                        [(hw, ey), (tw, hh + ey), (hw, th + ey), (0, hh + ey)])
    fw = max(4, tw // 3)
    pygame.draw.ellipse(spr, (72, 165, 78),
                        pygame.Rect(hw - fw // 2, ey + th // 4, fw, th // 2))
    if tw >= 14:
        pygame.draw.ellipse(spr, (210, 190, 110),
                            pygame.Rect(hw - tw // 5, th + ey - th // 3, tw // 3, th // 4))
    ph    = max(4, bh + hh)
    pin_x = hw + hw // 4
    pin_y = ey + th // 4
    pygame.draw.line(spr, (195, 185, 165), (pin_x, pin_y), (pin_x, pin_y - ph), max(1, tw // 24))
    fh = max(2, ph // 3)
    pygame.draw.polygon(spr, (220, 55, 55),
                        [(pin_x, pin_y - ph),
                         (pin_x + max(3, tw // 7), pin_y - ph + fh // 2),
                         (pin_x, pin_y - ph + fh)])
    pygame.draw.circle(spr, (24, 22, 28), (pin_x, pin_y), max(1, tw // 14))


def add_pool_detail(spr, tw, th, bh, hw, hh, stage, ey):
    """Swimming pool with lane dividers and a diving board."""
    if tw < 10:
        return
    pw = max(4, tw * 3 // 5)
    ph = max(2, th * 2 // 5)
    px = hw - pw // 2
    py = hh + ey - ph // 2
    pygame.draw.rect(spr, (195, 188, 172), pygame.Rect(px - 1, py - 1, pw + 2, ph + 2))
    pygame.draw.rect(spr, (58, 158, 218),  pygame.Rect(px, py, pw, ph))
    n_lanes = max(2, min(5, pw // max(1, tw // 8)))
    lw      = max(1, tw // 32)
    for i in range(1, n_lanes):
        lx = px + pw * i // n_lanes
        pygame.draw.line(spr, (240, 240, 240), (lx, py), (lx, py + ph), lw)
    if tw >= 18 and stage >= 2:
        bl = max(3, tw // 6)
        bx = hw - hw // 2
        pygame.draw.rect(spr, (188, 172, 130),
                         pygame.Rect(bx - bl, ey - max(2, tw // 18), bl, max(2, tw // 18)))


def add_cinema_detail(spr, tw, th, bh, hw, hh, stage, ey):
    """Lit marquee canopy, neon sign, and film reel for a cinema."""
    if tw < 10:
        return
    mh = max(2, bh // 4)
    marquee_pts = [(0, hh + ey), (hw, th + ey), (hw, th + ey + mh), (0, hh + ey + mh)]
    pygame.draw.polygon(spr, (235, 215, 55), marquee_pts)
    if tw >= 16:
        n_bulbs = max(2, min(8, tw // 10))
        for i in range(n_bulbs):
            t  = (i + 0.5) / n_bulbs
            bx = int(t * hw)
            by = int(hh + ey + t * hh) + mh // 2
            pygame.draw.circle(spr, (255, 245, 180), (bx, by), max(1, tw // 24))
    if tw >= 18:
        nh = max(2, bh // 5)
        pygame.draw.polygon(spr, (205, 55, 90),
                            [(tw, hh + ey), (hw, th + ey), (hw, th + ey + nh), (tw, hh + ey + nh)])
    if tw >= 22 and stage >= 2:
        rr = max(3, tw // 10)
        rx = hw - hw // 3
        ry = ey + hh // 2
        pygame.draw.circle(spr, (28, 25, 35), (rx, ry), rr)
        pygame.draw.circle(spr, (60, 55, 70), (rx, ry), max(1, rr // 2))
        for deg in (0, 60, 120):
            a  = math.radians(deg)
            sx = rx + int(rr * math.cos(a) * 0.7)
            sy = ry + int(rr * math.sin(a) * 0.7)
            pygame.draw.circle(spr, (28, 25, 35), (sx, sy), max(1, rr // 4))


def add_museum_detail(spr, tw, th, bh, hw, hh, stage, ey):
    """Classical columns and triangular pediment for a museum."""
    if tw < 10:
        return
    col_c  = _s((188, 172, 138),  25)
    base_c = _s((188, 172, 138), -20)
    n_cols = max(2, min(5, tw // 14))
    col_w  = max(1, tw // (n_cols * 5))
    for i in range(n_cols):
        t      = (i + 0.5) / n_cols
        cx_top = int(t * hw)
        cy_top = int(hh + ey + t * hh)
        pygame.draw.rect(spr, col_c,
                         pygame.Rect(cx_top - col_w, cy_top, col_w * 2, bh))
        pygame.draw.rect(spr, base_c,
                         pygame.Rect(cx_top - col_w - 1, cy_top,
                                     col_w * 2 + 2, max(1, tw // 22)))
        pygame.draw.rect(spr, base_c,
                         pygame.Rect(cx_top - col_w - 1, cy_top + bh - max(1, tw // 22),
                                     col_w * 2 + 2, max(1, tw // 22)))
    if tw >= 18:
        ped_h   = max(3, hh)
        ped_pts = [(0, hh + ey), (hw, hh + ey - ped_h), (tw, hh + ey)]
        pygame.draw.polygon(spr, _s((188, 172, 138), 15), ped_pts)
        pygame.draw.polygon(spr, base_c, ped_pts, max(1, tw // 28))


def add_zoo_detail(spr, tw, th, bh, hw, hh, stage, ey):
    """Fence enclosures, elephant silhouette, and trees for a zoo."""
    if tw < 10:
        return
    post_c  = (158, 132, 82)
    rail_c  = (182, 158, 108)
    n_posts = max(2, min(6, tw // 12))
    lw      = max(1, tw // 24)
    pygame.draw.line(spr, rail_c, (0, hh + ey), (hw, ey), lw)
    pygame.draw.line(spr, rail_c, (hw, ey), (tw, hh + ey), lw)
    for i in range(n_posts + 1):
        t  = i / n_posts
        px = int(t * hw)
        py = int(hh + ey - t * hh)
        ph = max(3, bh // 2 + hh // 2)
        pygame.draw.line(spr, post_c, (px, py), (px, py - ph), max(1, tw // 22))
    if tw >= 18:
        bc  = (88, 72, 52)
        bw2 = max(3, tw // 6)
        bh2 = max(2, th // 5)
        bx  = hw - bw2 // 2
        by  = hh + ey - bh2 // 2
        pygame.draw.ellipse(spr, bc, pygame.Rect(bx, by, bw2, bh2))
        hr = max(2, bw2 // 3)
        pygame.draw.circle(spr, bc, (bx + bw2 + hr // 2, by + bh2 // 3), hr)
        pygame.draw.line(spr, bc,
                         (bx + bw2 + hr, by + bh2 // 3 + hr // 2),
                         (bx + bw2 + hr + max(2, tw // 10), by + bh2),
                         max(1, tw // 20))
    if stage >= 2 and tw >= 20:
        r = max(2, tw // 9)
        for tx2, ty2 in ((tw * 3 // 4, ey + th // 4), (tw // 5, th * 2 // 3 + ey)):
            pygame.draw.circle(spr, (38, 100, 48), (tx2, ty2), r)
            pygame.draw.circle(spr, (58, 132, 68), (tx2 - r // 3, ty2 - r // 3), max(1, r // 3))


def add_civic_detail(spr, building, tw, th, bh, hw, hh, color, ey):
    """Building-type-specific details for civic buildings."""
    if building in (BuildingType.POWER_PLANT, BuildingType.LARGE_POWER_PLANT):
        stripe_c  = [(210, 60, 50), (240, 240, 240)]
        sh        = min(ey, max(6, bh // 3))
        sw        = max(3, tw // 11)
        sx        = hw + hw // 3
        top       = max(0, ey - sh)
        bot       = ey + max(2, th // 6)
        n_stripes = max(2, sh // 6)
        for i in range(n_stripes):
            seg_top = top + i * (bot - top) // n_stripes
            seg_bot = top + (i + 1) * (bot - top) // n_stripes
            pygame.draw.rect(spr, stripe_c[i % 2],
                             pygame.Rect(sx, seg_top, sw, seg_bot - seg_top))
        pygame.draw.ellipse(spr, (110, 108, 98),
                            pygame.Rect(sx - sw // 2, top - sw // 3, sw * 2, sw * 2 // 3))
        if building == BuildingType.LARGE_POWER_PLANT and tw >= 22:
            pygame.draw.circle(spr, (255, 230, 80),
                               (sx + sw // 2, top - 1), max(2, tw // 20))

    elif building in (BuildingType.WATER_TOWER, BuildingType.LARGE_WATER_TOWER):
        tank_r  = max(5, tw // 6) if building == BuildingType.LARGE_WATER_TOWER else max(4, tw // 8)
        tank_cy = max(tank_r + 1, ey - tank_r // 2)
        leg_c   = _s(color, -25)
        for lx in (hw - tank_r // 2, hw + tank_r // 2):
            leg_top = min(tank_cy, ey - 2)
            leg_bot = ey + hh
            if leg_bot > leg_top:
                pygame.draw.line(spr, leg_c, (lx, leg_top), (lx, leg_bot), max(1, tw // 24))
        tank_c = _s(color, 35)
        pygame.draw.circle(spr, _s(color, -10), (hw, tank_cy + tank_r // 4), tank_r)
        pygame.draw.ellipse(spr, tank_c,
                            pygame.Rect(hw - tank_r, tank_cy - tank_r // 2, tank_r * 2, tank_r))
        pygame.draw.circle(spr, _s(color, 65),
                           (hw - tank_r // 3, tank_cy - tank_r // 3), max(2, tank_r // 3))

    elif building == BuildingType.HOSPITAL:
        cross_c = (230, 50, 60)
        lw      = max(2, tw // 12)
        pygame.draw.line(spr, cross_c, (hw - hw // 3, hh + ey), (hw + hw // 3, hh + ey), lw)
        pygame.draw.line(spr, cross_c, (hw, hh + ey - hh // 2), (hw, hh + ey + hh // 2), lw)
        if tw >= 18:
            w = (245, 245, 245)
            pygame.draw.line(spr, w, (hw - hw // 3, hh + ey), (hw + hw // 3, hh + ey), max(1, lw - 1))
            pygame.draw.line(spr, w, (hw, hh + ey - hh // 2), (hw, hh + ey + hh // 2), max(1, lw - 1))
            pygame.draw.line(spr, cross_c, (hw - hw // 4, hh + ey), (hw + hw // 4, hh + ey), lw)
            pygame.draw.line(spr, cross_c, (hw, hh + ey - hh // 3), (hw, hh + ey + hh // 3), lw)
        if tw >= 20 and bh >= 10:
            hx = hw // 2
            hy = int(hh + ey + hh * 0.5 + bh * 0.4)
            hr = max(3, tw // 9)
            pygame.draw.circle(spr, (210, 210, 200), (hx, hy), hr, max(1, tw // 26))
            pygame.draw.line(spr, (210, 210, 200),
                             (hx - hr + 2, hy), (hx + hr - 2, hy), max(1, tw // 30))

    elif building == BuildingType.AIRPORT:
        rwy_c = _s(color, -15)
        lw    = max(3, tw // 14)
        pygame.draw.line(spr, rwy_c, (tw // 8, ey + bh // 2), (tw * 7 // 8, ey + bh // 2), lw)
        pygame.draw.line(spr, rwy_c, (hw, ey + bh // 8), (hw, ey + bh * 7 // 8), max(2, lw // 2))
        if tw >= 26:
            mk_c = _s(color, 35)
            for i in range(3):
                mx = tw // 8 + i * tw // 4
                pygame.draw.line(spr, mk_c,
                                 (mx, ey + bh // 2 - 1),
                                 (mx + tw // 12, ey + bh // 2 - 1), max(1, tw // 28))
