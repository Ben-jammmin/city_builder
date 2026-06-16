"""
sprite_terrain.py — Surface generators for isometric terrain tiles.
"""
from __future__ import annotations

import pygame

from .models import TerrainType
from .sprite_data import _GRASS, _diam_pts, _s


def make_terrain_spr(
    terrain: TerrainType,
    tw: int,
    th: int,
    variant: int,
    same_neighbors: dict | None,
) -> pygame.Surface:
    """Creates and returns a terrain tile Surface (tw × th, SRCALPHA)."""
    spr = pygame.Surface((tw, th), pygame.SRCALPHA)
    hw, hh = tw // 2, th // 2
    d = _diam_pts(tw, th)
    if terrain == TerrainType.GRASS:
        _draw_grass(spr, tw, th, hw, hh, d, variant)
    elif terrain == TerrainType.WATER:
        _draw_water(spr, tw, th, hw, hh, d, same_neighbors)
    elif terrain == TerrainType.FOREST:
        _draw_forest(spr, tw, th, hw, hh, d, variant)
    elif terrain == TerrainType.HILL:
        _draw_hill(spr, tw, th, hw, hh, d, variant)
    return spr


def _draw_grass(spr, tw, th, hw, hh, d, variant):
    base   = _GRASS[variant]
    light  = _s(base,  30)
    shadow = _s(base, -40)

    pygame.draw.polygon(spr, base, d)
    pygame.draw.polygon(spr, light,  [(hw, 0), (0, hh), (hw, hh), (hw, 0)])
    pygame.draw.polygon(spr, shadow, [(hw, th), (tw, hh), (hw, hh), (hw, th)])
    mid_shrink = max(1, tw // 12)
    mid_d = _diam_pts(tw - mid_shrink * 4, th - mid_shrink * 2, mid_shrink)
    pygame.draw.polygon(spr, base, mid_d)

    if tw >= 16:
        detail_cols = [
            (_s(base, 22), _s(base, -12)),
            (_s(base, 18), _s(base, -10)),
            (_s(base, 28), _s(base, -14)),
            (_s(base, 20), _s(base,  -8)),
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

    pygame.draw.polygon(spr, _s(base, -45), d, 1)


def _draw_water(spr, tw, th, hw, hh, d, sn):
    base    = (44, 104, 148)
    deep    = (34,  88, 130)
    shimmer = (92, 158, 195)
    foam    = (148, 196, 222)

    pygame.draw.polygon(spr, deep, d)
    pygame.draw.polygon(spr, base, [(hw, 0), (0, hh), (hw, hh)])

    if tw >= 12:
        lw = max(1, tw // 22)
        for i, frac in enumerate((0.28, 0.62)):
            wy  = int(th * frac)
            xl  = max(tw // 5, int(hw * (1 - (1 - frac) * 0.8)))
            xr  = min(tw * 4 // 5, int(hw * (1 + (1 - frac) * 0.8)))
            xm  = (xl + xr) // 2
            col = shimmer if i == 0 else foam
            pygame.draw.line(spr, col, (xl, wy), (xm - 2, wy + 1), lw)
            pygame.draw.line(spr, col, (xm + 2, wy + 1), (xr, wy), lw)

    if tw >= 22:
        for px, py in ((hw - tw // 6, hh // 2), (hw + tw // 8, hh // 3)):
            pygame.draw.circle(spr, foam, (px, py), max(1, tw // 28))

    if sn and tw >= 12:
        shore = (148, 148, 108)
        lw    = max(2, tw // 14)
        edges = {
            "north": ((hw, 0),  (tw, hh)),
            "east":  ((tw, hh), (hw, th)),
            "south": ((hw, th), (0,  hh)),
            "west":  ((0,  hh), (hw,  0)),
        }
        for direction, (p1, p2) in edges.items():
            if not sn.get(direction, True):
                pygame.draw.line(spr, shore, p1, p2, lw)

    pygame.draw.polygon(spr, (22, 55, 88), d, 1)


def _draw_forest(spr, tw, th, hw, hh, d, variant):
    floor_c = (48, 86, 50)
    floor_s = (32, 60, 34)
    pygame.draw.polygon(spr, floor_s, d)
    pygame.draw.polygon(spr, floor_c,           [(hw, 0), (0,  hh), (hw, hh)])
    pygame.draw.polygon(spr, _s(floor_c, 10),   [(hw, 0), (tw, hh), (hw, hh)])
    pygame.draw.polygon(spr, (22, 45, 24), d, 1)

    if tw < 12:
        return

    tc     = [(36, 96, 48), (44, 110, 56), (30, 84, 42)]
    hi     = [(62, 140, 74), (70, 152, 84), (54, 126, 66)]
    shad   = (20, 52, 26)
    trunk  = (72, 60, 36)
    r_base = max(4, tw // 8)

    positions = [
        (hw,           hh - th // 5),
        (hw - tw // 5, hh + th // 10),
        (hw + tw // 5, hh + th // 10),
        (hw,           hh + th // 4),
    ]
    count = 2 + (variant % 2)
    for i, (px, py) in enumerate(positions[:count]):
        r = max(3, r_base - i * max(0, tw // 28))
        pygame.draw.ellipse(spr, shad,
                            pygame.Rect(px - r, py + r // 3, r * 2, max(2, r // 2)))
        pygame.draw.rect(spr, trunk,
                         pygame.Rect(px - 1, py + r // 2, max(2, tw // 28), max(3, th // 6)))
        pygame.draw.circle(spr, tc[i % 3], (px, py), r)
        pygame.draw.circle(spr, hi[i % 3], (px - r // 3, py - r // 3), max(1, r // 3))


def _draw_hill(spr, tw, th, hw, hh, d, variant):
    base = (110, 110, 95)
    lit  = (138, 138, 120)
    dark = (70,  70,  60)
    rock = (150, 146, 128)

    pygame.draw.polygon(spr, base, d)
    pygame.draw.polygon(spr, lit,  [(hw, 0),  (0,  hh), (hw, hh)])
    pygame.draw.polygon(spr, dark, [(hw, th), (tw, hh), (hw, hh)])
    pygame.draw.polygon(spr, (52, 52, 44), d, 1)

    if tw < 14:
        return

    lw = max(1, tw // 26)
    for i, frac in enumerate((0.28, 0.54, 0.78)):
        y  = int(th * frac)
        xm = int(hw * (1 - abs(frac - 0.5) * 0.6))
        col = _s(lit, -i * 8) if frac < 0.5 else _s(dark, i * 6)
        pygame.draw.line(spr, col, (hw - xm, y), (hw + xm, y), lw)

    if tw >= 20:
        for rx, ry in ((hw - tw // 6, hh // 2), (hw + tw // 8, th // 3)):
            pygame.draw.circle(spr, rock, (rx, ry), max(2, tw // 18))
            pygame.draw.circle(spr, lit,  (rx - 1, ry - 1), max(1, tw // 26))
