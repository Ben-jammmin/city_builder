"""
sprites.py — SpriteAtlas: cached procedural sprites for the isometric city view.

Sprite generation is delegated to focused submodules:
  sprite_data.py      — colour palettes and shared drawing primitives
  sprite_terrain.py   — terrain tile generators
  sprite_buildings.py — zone / civic / road sprite generators
  sprite_details.py   — per-type building detail painters

SpriteAtlas owns the shared Surface cache and the public draw_* interface
consumed by renderer.py.  The primitives _diam_pts and tile_variant are
re-exported here because renderer.py and tests import them from this module.
"""
from __future__ import annotations

import pygame

from .asset_loader import ImageAssetStore
from .models import BuildingType, RecreationType, TerrainType, ZoneType
from .settings import USE_IMAGE_SPRITES
from .sprite_data import (   # re-exported — renderer.py and tests import from here
    _BLD_FRACS, _diam_pts, _draw_ground_shadow, tile_variant,
)
from .sprite_terrain import make_terrain_spr
from .sprite_buildings import (
    bh_for_civic, bh_for_zone,
    make_building_spr, make_civic_spr, make_road_spr, make_zone_base_spr,
)


class SpriteAtlas:
    """Generates and caches all procedural isometric sprites."""

    def __init__(self, font: pygame.font.Font) -> None:
        self.font   = font
        self.assets = ImageAssetStore() if USE_IMAGE_SPRITES else None
        self.cache: dict = {}

    # ── Public draw interface ──────────────────────────────────────────────────

    def draw_terrain(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        terrain: TerrainType,
        x: int, y: int,
        same_neighbors: dict | None = None,
    ) -> None:
        """Draws the terrain diamond for one tile (grass, water, forest, or hill)."""
        v = tile_variant(x, y)
        if self.assets is not None and terrain in (TerrainType.GRASS, TerrainType.WATER):
            asset = self._asset(f"terrain/{terrain.value}", tw)
            if asset is not None:
                surface.blit(asset, (cx - tw // 2, cy))
                return
        ek  = self._edge_key(same_neighbors) if terrain == TerrainType.WATER else None
        key = ("T", terrain, tw, v, ek)
        spr = self._get(key, lambda: make_terrain_spr(terrain, tw, th, v, same_neighbors))
        surface.blit(spr, (cx - tw // 2, cy))

    def draw_zone_base(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        zone: ZoneType,
        level: int,
        recreation_type: RecreationType | None = None,
    ) -> None:
        """Draws the semi-transparent tinted diamond indicating a lot's zone type."""
        key = ("ZB", zone, level, tw, recreation_type)
        spr = self._get(key, lambda: make_zone_base_spr(zone, level, tw, th, recreation_type))
        surface.blit(spr, (cx - tw // 2, cy))

    def draw_building(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        zone: ZoneType,
        development: float,
        level: int = 1,
        variant: int = 0,
        rotation: int = 0,
        recreation_type: RecreationType | None = None,
    ) -> None:
        """Draws the building that has grown on a zoned lot."""
        if development < 0.06 or (zone not in _BLD_FRACS and zone != ZoneType.PARK):
            return
        _draw_ground_shadow(surface, cx, cy, tw, th)
        stage = max(1, min(4, int(development * 4) + 1))
        v     = variant & 3
        if zone != ZoneType.PARK or recreation_type is None or recreation_type == RecreationType.PARK:
            asset = self._asset(self._building_asset_name(zone, stage, level, v), tw)
            if asset is not None:
                if rotation in (1, 3):
                    flip_key = ("BAF", zone, stage, level, tw, v)
                    _a = asset
                    asset = self._get(flip_key, lambda: pygame.transform.flip(_a, True, False))
                self._blit_grounded(surface, asset, cx, cy, th)
                return
        bh      = bh_for_zone(zone, stage, level, th, recreation_type)
        extra_h = th // 2
        key     = ("B", zone, stage, level, tw, th, v, recreation_type)
        spr     = self._get(key, lambda: make_building_spr(zone, tw, th, bh, stage, level, v, extra_h, recreation_type))
        if rotation in (1, 3):
            flip_key = ("BF", zone, stage, level, tw, th, v, recreation_type)
            _s = spr
            spr = self._get(flip_key, lambda: pygame.transform.flip(_s, True, False))
        surface.blit(spr, (cx - tw // 2, cy - bh - extra_h))

    def draw_civic_building(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        building: BuildingType,
        rotation: int = 0,
    ) -> None:
        """Draws a fixed civic building (power plant, hospital, etc.) at this tile."""
        _draw_ground_shadow(surface, cx, cy, tw, th)
        asset = self._asset(f"civic/{building.value}", tw)
        if asset is not None:
            if rotation in (1, 3):
                flip_key = ("CAF", building, tw)
                _a = asset
                asset = self._get(flip_key, lambda: pygame.transform.flip(_a, True, False))
            self._blit_grounded(surface, asset, cx, cy, th)
            return
        bh      = bh_for_civic(building, th)
        extra_h = th // 2
        key     = ("C", building, tw, th)
        _f      = self.font
        spr     = self._get(key, lambda: make_civic_spr(building, tw, th, bh, extra_h, _f))
        if rotation in (1, 3):
            flip_key = ("CF", building, tw, th)
            _s = spr
            spr = self._get(flip_key, lambda: pygame.transform.flip(_s, True, False))
        surface.blit(spr, (cx - tw // 2, cy - bh - extra_h))

    def draw_road(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        connections: dict[str, bool],
    ) -> None:
        """Draws a road tile with arms extending toward connected neighbours."""
        if self.assets is not None:
            road_name = self._road_asset_name(connections)
            if road_name:
                asset = self._asset(road_name, tw)
                if asset is not None:
                    surface.blit(asset, (cx - tw // 2, cy))
                    return
        key = ("R", tw, connections["north"], connections["east"],
               connections["south"], connections["west"])
        spr = self._get(key, lambda: make_road_spr(tw, th, connections))
        surface.blit(spr, (cx - tw // 2, cy))

    def draw_pedestrian(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
        variant: int,
    ) -> None:
        """Draws a small pedestrian figure at the given screen position."""
        asset_size = max(8, tw // 3)
        asset = self._asset(f"pedestrians/pedestrian_{variant % 3}", asset_size)
        if asset is not None:
            surface.blit(asset, (cx - asset.get_width() // 2, cy - asset.get_height()))
            return
        size = max(3, tw // 6)
        palette = (
            ((244, 190, 111), (61,  93, 150)),
            ((238, 134, 112), (80, 130,  95)),
            ((219, 198, 145), (145, 86, 128)),
        )
        shirt, pants = palette[variant % 3]
        pygame.draw.ellipse(surface, (16, 18, 16),
                            pygame.Rect(cx - size, cy + size // 4, size * 2, max(2, size // 2)))
        pygame.draw.circle(surface, shirt,  (cx, cy - size // 2), max(2, size // 2))
        pygame.draw.rect(surface, pants,
                         pygame.Rect(cx - size // 3, cy, max(2, size * 2 // 3), size),
                         border_radius=1)
        pygame.draw.circle(surface, (248, 205, 163), (cx, cy - size), max(1, size // 3))

    def draw_fire_overlay(
        self,
        surface: pygame.Surface,
        cx: int, cy: int,
        tw: int, th: int,
    ) -> None:
        """Animated fire overlay drawn directly (not cached) over a burning tile."""
        hw, hh = tw // 2, th // 2
        phase  = (pygame.time.get_ticks() // 220) % 2

        base_col     = (210, 55, 10) if phase == 0 else (230, 90, 18)
        pts_diamond  = [(cx, cy), (cx + hw, cy + hh), (cx, cy + th), (cx - hw, cy + hh)]
        pygame.draw.polygon(surface, base_col,    pts_diamond)
        pygame.draw.polygon(surface, (255, 200, 40), pts_diamond, max(1, tw // 18))

        flame_h = max(3, int(th * (1.1 if phase == 0 else 0.8)))
        tip_col = (255, 230, 60) if phase == 0 else (255, 150, 20)
        fw      = max(2, tw // 6)
        for ox in (-hw // 3, 0, hw // 3):
            bx = cx + ox
            by = cy + hh // 3
            fh = flame_h + (tw // 6 if ox == 0 else 0)
            pygame.draw.polygon(surface, tip_col,
                                [(bx - fw, by), (bx, by - fh), (bx + fw, by)])

    # ── Road asset name helper ─────────────────────────────────────────────────

    def _road_asset_name(self, connections: dict[str, bool]) -> str | None:
        n = connections.get("north", False)
        e = connections.get("east",  False)
        s = connections.get("south", False)
        w = connections.get("west",  False)
        count = sum([n, e, s, w])
        if count == 4:                       return "roads/xing"
        if count == 2:
            if n and s:                      return "roads/straight_SW"
            if e and w:                      return "roads/straight_SE"
            if n and e:                      return "roads/corner_W"
            if e and s:                      return "roads/corner_N"
            if s and w:                      return "roads/corner_E"
            if n and w:                      return "roads/corner_S"
        if count == 3:
            if not n:                        return "roads/intersect_NE"
            if not w:                        return "roads/intersect_NW"
            if not e:                        return "roads/intersect_SE"
            if not s:                        return "roads/intersect_SW"
        if count == 1:
            if n:                            return "roads/deadend_SW"
            if e:                            return "roads/deadend_NW"
            if s:                            return "roads/deadend_NE"
            if w:                            return "roads/deadend_SE"
        return None

    # ── Utility helpers ────────────────────────────────────────────────────────

    def _edge_key(self, sn: dict | None) -> tuple | None:
        if sn is None:
            return None
        return (sn.get("north", False), sn.get("east",  False),
                sn.get("south", False), sn.get("west",  False))

    def _asset(self, name: str, size: int) -> pygame.Surface | None:
        if self.assets is None:
            return None
        return self.assets.get(name, size)

    def _building_asset_name(self, zone: ZoneType, stage: int, level: int, variant: int) -> str:
        if level > 1 and zone in (ZoneType.RESIDENTIAL, ZoneType.COMMERCIAL):
            return f"buildings/{zone.value}_tier2_{stage}_{variant}"
        return f"buildings/{zone.value}_{stage}_{variant}"

    def _blit_grounded(
        self,
        surface: pygame.Surface,
        sprite: pygame.Surface,
        cx: int, cy: int, th: int,
    ) -> None:
        surface.blit(sprite, (cx - sprite.get_width() // 2, cy + th - sprite.get_height()))

    def _bh(self, zone: ZoneType, stage: int, level: int, th: int, recreation_type: RecreationType | None = None) -> int:
        return bh_for_zone(zone, stage, level, th, recreation_type)

    def _civic_bh(self, building: BuildingType, th: int) -> int:
        return bh_for_civic(building, th)

    def _get(self, key: tuple, maker) -> pygame.Surface:
        if key not in self.cache:
            self.cache[key] = maker()
        return self.cache[key]
