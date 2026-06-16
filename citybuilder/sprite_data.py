"""
sprite_data.py — Colour palettes and shared drawing primitives for all sprite generators.
"""
from __future__ import annotations

import pygame

from .models import BuildingType, RecreationType, ZoneType


# ---------------------------------------------------------------------------
# Drawing primitives
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


def _draw_ground_shadow(surface: pygame.Surface, cx: int, cy: int, tw: int, th: int) -> None:
    """Draw a soft elliptical shadow on the ground plane under a building."""
    if tw < 14:
        return
    sw = max(8, tw * 5 // 8)
    sh = max(3, th // 3)
    ss = pygame.Surface((sw, sh), pygame.SRCALPHA)
    pygame.draw.ellipse(ss, (0, 0, 0, 60), ss.get_rect())
    surface.blit(ss, (cx - sw // 2, cy + th // 2 - sh // 2))


# ---------------------------------------------------------------------------
# Colour palettes
# ---------------------------------------------------------------------------

_GRASS = [
    (92, 136, 62),
    (80, 120, 52),
    (102, 148, 70),
    (74, 112, 50),
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

# Highrise (level-3) palettes — glass-tower aesthetic distinct from brick/concrete.
_HIGHRISE_WALL = {
    # Residential: light concrete + glass curtain — warm-grey with hints of blue
    ZoneType.RESIDENTIAL: [(188, 196, 210), (178, 186, 200), (196, 205, 218), (182, 190, 205)],
    # Commercial: deep tinted-glass tower — blue-grey steel frame
    ZoneType.COMMERCIAL:  [(72, 95, 128),   (62, 85, 118),   (82, 105, 138),  (68, 90, 122)],
}
_HIGHRISE_ROOF = {
    ZoneType.RESIDENTIAL: (145, 158, 172),   # flat concrete parapet
    ZoneType.COMMERCIAL:  (40, 58, 82),       # dark steel roof cap
}
_HIGHRISE_WIN = {
    ZoneType.RESIDENTIAL: (195, 215, 235),    # pale blue-white glass panes
    ZoneType.COMMERCIAL:  (140, 195, 240),    # bright reflective glass
}

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
