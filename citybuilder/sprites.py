from __future__ import annotations

import pygame

from .asset_loader import ImageAssetStore
from .models import BuildingType, TerrainType, ZoneType
from .settings import COLORS


TERRAIN_VARIANTS = 4
CONNECTION_ORDER = ("north", "east", "south", "west")

ZONE_COLORS = {
    ZoneType.RESIDENTIAL: "residential",
    ZoneType.COMMERCIAL: "commercial",
    ZoneType.INDUSTRIAL: "industrial",
}

BUILDING_COLORS = {
    BuildingType.POWER_PLANT: "power",
    BuildingType.LARGE_POWER_PLANT: "power",
    BuildingType.WATER_TOWER: "water",
    BuildingType.LARGE_WATER_TOWER: "water",
    BuildingType.POLICE: "police",
    BuildingType.FIRE: "fire",
    BuildingType.SCHOOL: "school",
    BuildingType.TRAIN_STATION: "train_station",
    BuildingType.AIRPORT: "airport",
}

BUILDING_LABELS = {
    BuildingType.POWER_PLANT: "P",
    BuildingType.LARGE_POWER_PLANT: "P+",
    BuildingType.WATER_TOWER: "W",
    BuildingType.LARGE_WATER_TOWER: "W+",
    BuildingType.POLICE: "Po",
    BuildingType.FIRE: "F",
    BuildingType.SCHOOL: "S",
    BuildingType.TRAIN_STATION: "T",
    BuildingType.AIRPORT: "A",
}


def tile_variant(x: int, y: int) -> int:
    return abs(x * 37 + y * 17) % TERRAIN_VARIANTS


def connection_mask(connections: dict[str, bool]) -> str:
    return "".join("1" if connections.get(direction, False) else "0" for direction in CONNECTION_ORDER)


def terrain_asset_names(terrain: TerrainType, variant: int) -> tuple[str, ...]:
    if terrain == TerrainType.GRASS:
        return (f"terrain/grass_{variant % TERRAIN_VARIANTS}", "terrain/grass")
    if terrain == TerrainType.FOREST:
        return (f"terrain/forest_{variant % 2}", "terrain/forest")
    if terrain == TerrainType.WATER:
        return ("terrain/water",)
    if terrain == TerrainType.HILL:
        return ("terrain/hill",)
    return ()


def zone_asset_name(zone: ZoneType, level: int = 1) -> str:
    if level > 1:
        return f"zones/{zone.value}_tier{level}"
    return f"zones/{zone.value}"


def zone_asset_names(zone: ZoneType, level: int = 1) -> tuple[str, ...]:
    if level > 1:
        return (zone_asset_name(zone, level), zone_asset_name(zone, 1))
    return (zone_asset_name(zone, 1),)


def zone_building_asset_name(zone: ZoneType, stage: int, variant: int, level: int = 1) -> str:
    if level > 1:
        return f"buildings/{zone.value}_tier{level}_{stage}_{variant % TERRAIN_VARIANTS}"
    return f"buildings/{zone.value}_{stage}_{variant % TERRAIN_VARIANTS}"


def zone_building_asset_names(zone: ZoneType, stage: int, variant: int, level: int = 1) -> tuple[str, ...]:
    if level > 1:
        return (
            zone_building_asset_name(zone, stage, variant, level),
            zone_building_asset_name(zone, stage, variant, 1),
        )
    return (zone_building_asset_name(zone, stage, variant, 1),)


def civic_asset_name(building: BuildingType) -> str:
    return f"civic/{building.value}"


def road_asset_name(connections: dict[str, bool]) -> str:
    return f"roads/road_{connection_mask(connections)}"


def utility_asset_name(utility: str, connections: dict[str, bool]) -> str:
    return f"utilities/{utility}_{connection_mask(connections)}"


def pedestrian_asset_name(variant: int) -> str:
    return f"pedestrians/pedestrian_{variant % 3}"


def _shift(color: tuple[int, int, int], amount: int) -> tuple[int, int, int]:
    return tuple(max(0, min(255, channel + amount)) for channel in color)


class SpriteAtlas:
    def __init__(self, font: pygame.font.Font, assets: ImageAssetStore | None = None) -> None:
        self.font = font
        self.assets = assets if assets is not None else ImageAssetStore()
        self.cache: dict[tuple, pygame.Surface] = {}

    def draw_terrain(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        terrain: TerrainType,
        x: int,
        y: int,
        same_neighbors: dict[str, bool] | None = None,
    ) -> None:
        variant = tile_variant(x, y)
        sprite = self._asset_from_names(terrain_asset_names(terrain, variant), rect.width)
        if sprite is None:
            sprite = self._terrain_sprite(terrain, rect.width, variant, same_neighbors)
        surface.blit(sprite, rect.topleft)

    def draw_zone(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        zone: ZoneType,
        development: float,
        level: int = 1,
        variant: int = 0,
    ) -> None:
        sprite = self._asset_from_names(zone_asset_names(zone, level), rect.width)
        if sprite is None:
            sprite = self._zone_sprite(zone, rect.width)
        surface.blit(sprite, rect.topleft)
        if development > 0.08:
            self.draw_zone_building(surface, rect, zone, development, level, variant)

    def draw_zone_building(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        zone: ZoneType,
        development: float,
        level: int = 1,
        variant: int = 0,
    ) -> None:
        stage = max(1, min(4, int(development * 4) + 1))
        sprite = self._asset_from_names(zone_building_asset_names(zone, stage, variant, level), rect.width)
        if sprite is None:
            sprite = self._zone_building_sprite(zone, rect.width, stage, variant)
        surface.blit(sprite, rect.topleft)

    def draw_civic_building(self, surface: pygame.Surface, rect: pygame.Rect, building: BuildingType) -> None:
        sprite = self._asset(civic_asset_name(building), rect.width)
        if sprite is None:
            sprite = self._civic_sprite(building, rect.width)
        surface.blit(sprite, rect.topleft)

    def draw_road(self, surface: pygame.Surface, rect: pygame.Rect, connections: dict[str, bool]) -> None:
        sprite = self._asset(road_asset_name(connections), rect.width)
        if sprite is None:
            sprite = self._road_sprite(rect.width, connections)
        surface.blit(sprite, rect.topleft)

    def draw_power_line(self, surface: pygame.Surface, rect: pygame.Rect, connections: dict[str, bool]) -> None:
        sprite = self._asset(utility_asset_name("power", connections), rect.width)
        if sprite is None:
            sprite = self._utility_sprite("power", rect.width, connections)
        surface.blit(sprite, rect.topleft)

    def draw_water_pipe(self, surface: pygame.Surface, rect: pygame.Rect, connections: dict[str, bool]) -> None:
        sprite = self._asset(utility_asset_name("water", connections), rect.width)
        if sprite is None:
            sprite = self._utility_sprite("water", rect.width, connections)
        surface.blit(sprite, rect.topleft)

    def draw_pedestrian(self, surface: pygame.Surface, center: tuple[int, int], size: int, variant: int) -> None:
        if size < 2:
            return
        sprite_size = max(4, size * 2)
        sprite = self._asset(pedestrian_asset_name(variant), sprite_size)
        if sprite is not None:
            surface.blit(sprite, (center[0] - sprite_size // 2, center[1] - sprite_size // 2))
            return
        shadow_rect = pygame.Rect(0, 0, size * 2, max(2, size // 2))
        shadow_rect.center = (center[0], center[1] + size // 2)
        pygame.draw.ellipse(surface, (24, 26, 24), shadow_rect)
        palette = (
            ((244, 190, 111), (61, 93, 150)),
            ((238, 134, 112), (80, 130, 95)),
            ((219, 198, 145), (145, 86, 128)),
        )
        shirt, pants = palette[variant % len(palette)]
        pygame.draw.circle(surface, shirt, (center[0], center[1] - size // 2), max(2, size // 2))
        pygame.draw.rect(surface, pants, pygame.Rect(center[0] - size // 3, center[1], max(2, size * 2 // 3), size), border_radius=1)
        pygame.draw.circle(surface, (248, 205, 163), (center[0], center[1] - size), max(2, size // 3))

    def _asset(self, name: str, size: int) -> pygame.Surface | None:
        return self.assets.get(name, size)

    def _asset_from_names(self, names: tuple[str, ...], size: int) -> pygame.Surface | None:
        for name in names:
            sprite = self._asset(name, size)
            if sprite is not None:
                return sprite
        return None

    def _terrain_sprite(
        self,
        terrain: TerrainType,
        size: int,
        variant: int,
        same_neighbors: dict[str, bool] | None,
    ) -> pygame.Surface:
        edge_key = self._edge_key(same_neighbors) if terrain == TerrainType.WATER else None
        key = ("terrain", terrain, size, variant, edge_key)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        sprite = pygame.Surface((size, size))
        if terrain == TerrainType.GRASS:
            base = COLORS["empty"] if variant % 2 == 0 else COLORS["empty_alt"]
            sprite.fill(base)
            self._grass_detail(sprite, size, variant, base)
        elif terrain == TerrainType.WATER:
            sprite.fill(COLORS["terrain_water"])
            self._water_detail(sprite, size)
            self._shore_detail(sprite, size, same_neighbors)
        elif terrain == TerrainType.FOREST:
            sprite.fill(COLORS["terrain_forest"])
            self._forest_detail(sprite, size, variant)
        elif terrain == TerrainType.HILL:
            sprite.fill(COLORS["terrain_hill"])
            self._hill_detail(sprite, size)
        self.cache[key] = sprite
        return sprite

    def _zone_sprite(self, zone: ZoneType, size: int) -> pygame.Surface:
        key = ("zone", zone, size)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        sprite = pygame.Surface((size, size))
        base = COLORS[ZONE_COLORS[zone]]
        sprite.fill(_shift(base, -18))
        plot = pygame.Rect(max(1, size // 10), max(1, size // 10), size - max(2, size // 5), size - max(2, size // 5))
        pygame.draw.rect(sprite, base, plot, border_radius=max(1, size // 14))
        pygame.draw.rect(sprite, COLORS["zone_border"], plot, width=max(1, size // 18), border_radius=max(1, size // 14))
        if size >= 18:
            line_color = _shift(base, 28)
            pygame.draw.line(sprite, line_color, (plot.left + 2, plot.centery), (plot.right - 2, plot.centery), 1)
            pygame.draw.line(sprite, line_color, (plot.centerx, plot.top + 2), (plot.centerx, plot.bottom - 2), 1)
            curb = _shift(base, -35)
            pygame.draw.rect(sprite, curb, pygame.Rect(plot.left, plot.bottom - max(2, size // 12), plot.width, max(2, size // 12)))
            if zone == ZoneType.RESIDENTIAL:
                pygame.draw.circle(sprite, (54, 116, 66), (plot.right - size // 6, plot.top + size // 5), max(2, size // 15))
            elif zone == ZoneType.COMMERCIAL:
                awning_h = max(2, size // 10)
                pygame.draw.rect(sprite, (230, 226, 178), pygame.Rect(plot.left + 3, plot.top + 3, plot.width - 6, awning_h))
            elif zone == ZoneType.INDUSTRIAL:
                stripe_y = plot.top + 4
                for stripe_x in range(plot.left + 3, plot.right - 3, max(4, size // 7)):
                    pygame.draw.line(sprite, (119, 99, 59), (stripe_x, stripe_y), (stripe_x + size // 10, stripe_y + size // 10), 1)
        self.cache[key] = sprite
        return sprite

    def _zone_building_sprite(self, zone: ZoneType, size: int, stage: int, variant: int) -> pygame.Surface:
        key = ("zone_building", zone, size, stage, variant % TERRAIN_VARIANTS)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        sprite = pygame.Surface((size, size), pygame.SRCALPHA)
        if zone == ZoneType.RESIDENTIAL:
            self._draw_house(sprite, size, stage, variant)
        elif zone == ZoneType.COMMERCIAL:
            self._draw_commercial(sprite, size, stage, variant)
        elif zone == ZoneType.INDUSTRIAL:
            self._draw_industrial(sprite, size, stage, variant)
        self.cache[key] = sprite
        return sprite

    def _civic_sprite(self, building: BuildingType, size: int) -> pygame.Surface:
        key = ("civic", building, size)
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        sprite = pygame.Surface((size, size), pygame.SRCALPHA)
        color = COLORS[BUILDING_COLORS[building]]
        sprite.fill(color)
        shadow = pygame.Rect(size // 5 + 2, size // 4 + 2, size * 3 // 5, size // 2)
        body = pygame.Rect(size // 5, size // 4, size * 3 // 5, size // 2)
        pygame.draw.rect(sprite, COLORS["shadow"], shadow, border_radius=max(1, size // 12))
        pygame.draw.rect(sprite, COLORS["building_light"], body, border_radius=max(1, size // 12))
        pygame.draw.rect(sprite, COLORS["building_dark"], body, width=max(1, size // 20), border_radius=max(1, size // 12))
        self._draw_civic_roof(sprite, building, body, color, size)
        if size >= 22:
            label = BUILDING_LABELS[building]
            text = self.font.render(label, True, COLORS["building_dark"])
            sprite.blit(text, (size // 2 - text.get_width() // 2, size // 2 - text.get_height() // 2))
        self.cache[key] = sprite
        return sprite

    def _road_sprite(self, size: int, connections: dict[str, bool]) -> pygame.Surface:
        key = (
            "road",
            size,
            connections["north"],
            connections["east"],
            connections["south"],
            connections["west"],
        )
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        sprite = pygame.Surface((size, size), pygame.SRCALPHA)
        road_width = max(6, int(size * 0.48))
        curb_width = road_width + max(2, size // 10)
        half_road = road_width // 2
        half_curb = curb_width // 2
        center = size // 2
        curb = _shift(COLORS["road"], 28)

        self._draw_road_parts(sprite, size, center, half_curb, curb, connections)
        self._draw_road_parts(sprite, size, center, half_road, COLORS["road"], connections)
        if size >= 18:
            self._draw_crosswalks(sprite, size, center, half_road, connections)
            self._draw_lane_markings(sprite, size, center, connections)
        self.cache[key] = sprite
        return sprite

    def _utility_sprite(self, utility: str, size: int, connections: dict[str, bool]) -> pygame.Surface:
        key = (
            "utility",
            utility,
            size,
            connections["north"],
            connections["east"],
            connections["south"],
            connections["west"],
        )
        cached = self.cache.get(key)
        if cached is not None:
            return cached

        sprite = pygame.Surface((size, size), pygame.SRCALPHA)
        if utility == "power":
            color = COLORS["power"]
            shadow = (95, 78, 32)
            line_width = max(2, size // 12)
            node_radius = max(3, size // 9)
        else:
            color = COLORS["water"]
            shadow = (31, 76, 98)
            line_width = max(3, size // 9)
            node_radius = max(3, size // 11)

        self._draw_utility_parts(sprite, size, connections, shadow, line_width + 2, node_radius + 1)
        self._draw_utility_parts(sprite, size, connections, color, line_width, node_radius)
        if utility == "power" and size >= 20:
            center = size // 2
            pole_w = max(2, size // 12)
            pygame.draw.rect(sprite, (96, 79, 48), pygame.Rect(center - pole_w // 2, center - size // 5, pole_w, size * 2 // 5))
            pygame.draw.line(sprite, color, (center - size // 6, center - size // 7), (center + size // 6, center - size // 7), max(1, size // 24))
        elif utility == "water" and size >= 20:
            center = size // 2
            pygame.draw.circle(sprite, (150, 213, 233), (center - size // 8, center - size // 10), max(1, size // 18))
        self.cache[key] = sprite
        return sprite

    def _edge_key(self, same_neighbors: dict[str, bool] | None) -> tuple[bool, bool, bool, bool] | None:
        if same_neighbors is None:
            return None
        return (
            same_neighbors["north"],
            same_neighbors["east"],
            same_neighbors["south"],
            same_neighbors["west"],
        )

    def _grass_detail(self, sprite: pygame.Surface, size: int, variant: int, base: tuple[int, int, int]) -> None:
        if size < 12:
            return
        blade_color = _shift(base, 18)
        dark_blade = _shift(base, -13)
        points = (
            (size // 5, size // 4),
            (size * 3 // 5, size // 5),
            (size // 3, size * 2 // 3),
            (size * 4 // 5, size * 3 // 4),
        )
        for index, (px, py) in enumerate(points):
            color = blade_color if (index + variant) % 2 == 0 else dark_blade
            pygame.draw.line(sprite, color, (px, py + 2), (px + max(1, size // 14), py), max(1, size // 28))
        if size >= 24 and variant in (1, 3):
            flower_color = (220, 209, 130) if variant == 1 else (196, 151, 202)
            pygame.draw.circle(sprite, flower_color, (size * 3 // 4, size // 3), max(1, size // 24))
            pygame.draw.circle(sprite, flower_color, (size // 4, size * 3 // 4), max(1, size // 26))

    def _water_detail(self, sprite: pygame.Surface, size: int) -> None:
        if size < 12:
            return
        outline_width = max(1, size // 22)
        wave_width = max(1, size // 18)
        pygame.draw.rect(sprite, (36, 87, 119), sprite.get_rect(), width=outline_width)
        for index, offset in enumerate((-size // 6, size // 8)):
            y = size // 2 + offset
            start_x = 5 + index * 3
            pygame.draw.line(sprite, (102, 169, 198), (start_x, y), (size // 2 - 2, y + 1), wave_width)
            pygame.draw.line(sprite, (102, 169, 198), (size // 2 + 2, y + 1), (size - 5, y), wave_width)
        pygame.draw.line(sprite, (67, 135, 170), (size // 5, size - size // 5), (size * 4 // 5, size - size // 4), max(1, size // 26))

    def _shore_detail(self, sprite: pygame.Surface, size: int, same_neighbors: dict[str, bool] | None) -> None:
        if same_neighbors is None or size < 10:
            return
        shore = (144, 145, 102)
        foam = (138, 197, 215)
        width = max(2, size // 12)
        thin = max(1, size // 24)
        if not same_neighbors["north"]:
            pygame.draw.rect(sprite, shore, pygame.Rect(0, 0, size, width))
            pygame.draw.line(sprite, foam, (2, width + 1), (size - 2, width + 1), thin)
        if not same_neighbors["east"]:
            pygame.draw.rect(sprite, shore, pygame.Rect(size - width, 0, width, size))
            pygame.draw.line(sprite, foam, (size - width - 1, 2), (size - width - 1, size - 2), thin)
        if not same_neighbors["south"]:
            pygame.draw.rect(sprite, shore, pygame.Rect(0, size - width, size, width))
            pygame.draw.line(sprite, foam, (2, size - width - 1), (size - 2, size - width - 1), thin)
        if not same_neighbors["west"]:
            pygame.draw.rect(sprite, shore, pygame.Rect(0, 0, width, size))
            pygame.draw.line(sprite, foam, (width + 1, 2), (width + 1, size - 2), thin)

    def _forest_detail(self, sprite: pygame.Surface, size: int, variant: int) -> None:
        if size < 12:
            return
        tree_color = (34, 77, 46)
        highlight = (56, 122, 70)
        trunk = (76, 69, 47)
        centers = (
            (size // 2, size // 3),
            (size // 3, size * 3 // 5),
            (size * 2 // 3, size * 3 // 5),
        )
        radius = max(3, size // 8)
        for index, center in enumerate(centers[: 2 + variant % 2]):
            pygame.draw.rect(sprite, trunk, pygame.Rect(center[0] - 1, center[1], max(2, size // 12), size // 5))
            pygame.draw.circle(sprite, tree_color, center, radius)
            pygame.draw.circle(sprite, highlight, (center[0] - radius // 3, center[1] - radius // 3), max(1, radius // 3))
        if size >= 24:
            pygame.draw.circle(sprite, (25, 58, 36), (size // 5, size // 5), max(2, size // 12))

    def _hill_detail(self, sprite: pygame.Surface, size: int) -> None:
        if size < 12:
            return
        line_width = max(1, size // 18)
        light = (152, 153, 132)
        dark = (89, 91, 80)
        points = [
            (size // 5, size * 2 // 3),
            (size // 2, size // 4),
            (size * 4 // 5, size * 2 // 3),
        ]
        pygame.draw.lines(sprite, dark, False, [(x, y + 2) for x, y in points], line_width)
        pygame.draw.lines(sprite, light, False, points, line_width)
        pygame.draw.arc(sprite, light, pygame.Rect(size // 4, size // 2, size // 2, size // 4), 3.2, 6.2, line_width)
        if size >= 24:
            pygame.draw.line(sprite, dark, (size // 2, size // 4 + 2), (size * 3 // 5, size // 2), max(1, size // 24))

    def _draw_house(self, sprite: pygame.Surface, size: int, stage: int, variant: int) -> None:
        width = size // 3 + stage * size // 18
        height = size // 4 + stage * size // 20
        x_shift = ((variant % 3) - 1) * max(1, size // 24)
        body = pygame.Rect(size // 2 - width // 2 + x_shift, size - height - size // 6, width, height)
        wall_palette = ((219, 226, 205), (226, 213, 190), (203, 221, 221), (224, 205, 203))
        roof_palette = ((129, 72, 58), (111, 82, 68), (92, 85, 96), (145, 88, 58))
        if stage >= 3 and size >= 24:
            garage = pygame.Rect(body.right - size // 8, body.bottom - size // 5, size // 5, size // 6)
            pygame.draw.rect(sprite, COLORS["shadow"], garage.move(1, 1))
            pygame.draw.rect(sprite, (196, 201, 186), garage)
        roof = [
            (body.left - size // 12, body.top),
            (body.centerx, body.top - size // 5),
            (body.right + size // 12, body.top),
        ]
        pygame.draw.rect(sprite, COLORS["shadow"], body.move(2, 2), border_radius=1)
        pygame.draw.rect(sprite, wall_palette[variant % len(wall_palette)], body, border_radius=1)
        pygame.draw.polygon(sprite, roof_palette[variant % len(roof_palette)], roof)
        if size >= 24:
            pygame.draw.rect(sprite, (72, 114, 143), pygame.Rect(body.left + width // 5, body.top + height // 3, 3, 3))
            pygame.draw.rect(sprite, (72, 114, 143), pygame.Rect(body.right - width // 4, body.top + height // 3, 3, 3))
            pygame.draw.rect(sprite, (92, 69, 49), pygame.Rect(body.centerx - 1, body.bottom - height // 4, 3, height // 4))
        if stage >= 4 and size >= 26:
            porch = pygame.Rect(body.left - size // 8, body.bottom - size // 6, body.width + size // 4, max(2, size // 10))
            pygame.draw.rect(sprite, (186, 168, 121), porch)

    def _draw_commercial(self, sprite: pygame.Surface, size: int, stage: int, variant: int) -> None:
        width = size // 3 + stage * size // 12
        height = size // 4 + stage * size // 10
        body = pygame.Rect(size // 2 - width // 2, size - height - size // 7, width, height)
        glass_palette = ((83, 137, 178), (86, 151, 157), (111, 129, 180), (75, 122, 164))
        facade_palette = ((202, 216, 222), (217, 213, 194), (204, 212, 226), (198, 219, 211))
        pygame.draw.rect(sprite, COLORS["shadow"], body.move(2, 2))
        pygame.draw.rect(sprite, facade_palette[variant % len(facade_palette)], body)
        roof = pygame.Rect(body.left, body.top, body.width, max(3, size // 8))
        pygame.draw.rect(sprite, (68, 89, 102), roof)
        pygame.draw.rect(sprite, COLORS["building_dark"], body, width=max(1, size // 24))
        if size >= 22:
            window = max(2, size // 12)
            for wx in range(body.left + 4, body.right - window, window + 3):
                for wy in range(body.top + 4, body.bottom - window, window + 3):
                    pygame.draw.rect(sprite, glass_palette[variant % len(glass_palette)], pygame.Rect(wx, wy, window, window))
            sign = pygame.Rect(body.left + 3, body.bottom - max(5, size // 5), body.width - 6, max(3, size // 9))
            sign_palette = ((233, 199, 92), (218, 126, 101), (126, 184, 143), (180, 149, 214))
            pygame.draw.rect(sprite, sign_palette[variant % len(sign_palette)], sign, border_radius=1)
            if stage >= 3:
                antenna_x = body.centerx
                pygame.draw.line(sprite, (50, 58, 64), (antenna_x, body.top), (antenna_x, body.top - size // 6), max(1, size // 26))

    def _draw_industrial(self, sprite: pygame.Surface, size: int, stage: int, variant: int) -> None:
        width = size // 2 + stage * size // 16
        height = size // 4 + stage * size // 18
        body = pygame.Rect(size // 2 - width // 2, size - height - size // 7, width, height)
        stack_left = body.right - size // 5 if variant % 2 == 0 else body.left + size // 10
        stack = pygame.Rect(stack_left, body.top - size // 5, max(3, size // 9), size // 4)
        pygame.draw.rect(sprite, COLORS["shadow"], body.move(2, 2))
        pygame.draw.rect(sprite, (159, 149, 123), body)
        pygame.draw.rect(sprite, (102, 99, 88), stack)
        roof_points = [
            (body.left, body.top),
            (body.left + width // 4, body.top - size // 7),
            (body.left + width // 2, body.top),
            (body.left + width * 3 // 4, body.top - size // 7),
            (body.right, body.top),
        ]
        pygame.draw.lines(sprite, COLORS["building_dark"], False, roof_points, max(1, size // 22))
        if size >= 22:
            pygame.draw.circle(sprite, (125, 128, 119), (stack.centerx, max(2, stack.top - size // 8)), max(2, size // 13))
            door = pygame.Rect(body.left + size // 8, body.bottom - size // 5, size // 5, size // 5)
            pygame.draw.rect(sprite, (88, 82, 72), door)
            for stripe in range(door.left, door.right, max(3, size // 12)):
                pygame.draw.line(sprite, (211, 174, 77), (stripe, door.top), (stripe + size // 12, door.bottom), 1)
            if stage >= 3:
                pygame.draw.circle(sprite, (151, 154, 141), (stack.centerx + size // 8, max(2, stack.top - size // 5)), max(2, size // 14))

    def _draw_civic_roof(
        self,
        sprite: pygame.Surface,
        building: BuildingType,
        body: pygame.Rect,
        color: tuple[int, int, int],
        size: int,
    ) -> None:
        accent = _shift(color, -22)
        if building in (BuildingType.WATER_TOWER, BuildingType.LARGE_WATER_TOWER):
            tank = pygame.Rect(body.centerx - size // 5, body.top - size // 7, size * 2 // 5, size // 4)
            if building == BuildingType.LARGE_WATER_TOWER:
                tank = tank.inflate(size // 7, size // 12)
            pygame.draw.ellipse(sprite, accent, tank)
            pygame.draw.ellipse(sprite, _shift(accent, 28), tank.inflate(-max(2, size // 10), -max(2, size // 12)))
            pygame.draw.line(sprite, COLORS["building_dark"], (tank.left + 2, tank.bottom), (body.left + 3, body.bottom), max(1, size // 22))
            pygame.draw.line(sprite, COLORS["building_dark"], (tank.right - 2, tank.bottom), (body.right - 3, body.bottom), max(1, size // 22))
        elif building in (BuildingType.POWER_PLANT, BuildingType.LARGE_POWER_PLANT):
            stack = pygame.Rect(body.right - size // 5, body.top - size // 5, max(3, size // 9), size // 4)
            pygame.draw.rect(sprite, accent, stack)
            pygame.draw.circle(sprite, (126, 130, 121), (stack.centerx + size // 8, max(2, stack.top - size // 8)), max(2, size // 13))
            if building == BuildingType.LARGE_POWER_PLANT:
                stack_two = stack.move(-size // 4, size // 12)
                pygame.draw.rect(sprite, _shift(accent, -12), stack_two)
                pygame.draw.circle(sprite, (126, 130, 121), (stack_two.centerx + size // 8, max(2, stack_two.top - size // 8)), max(2, size // 13))
        elif building == BuildingType.AIRPORT:
            wing_y = body.centery
            pygame.draw.line(sprite, accent, (body.left + 3, wing_y), (body.right - 3, wing_y), max(2, size // 9))
            pygame.draw.line(sprite, accent, (body.centerx, body.top), (body.centerx, body.bottom), max(1, size // 12))
            pygame.draw.polygon(
                sprite,
                _shift(accent, 32),
                [(body.centerx, body.top - size // 7), (body.centerx - size // 9, body.top + size // 12), (body.centerx + size // 9, body.top + size // 12)],
            )
        elif building == BuildingType.TRAIN_STATION:
            rail_y = body.bottom - size // 8
            pygame.draw.line(sprite, accent, (body.left + 2, rail_y), (body.right - 2, rail_y), max(1, size // 18))
            pygame.draw.line(sprite, accent, (body.left + 2, rail_y + 3), (body.right - 2, rail_y + 3), max(1, size // 18))
            for tie_x in range(body.left + 3, body.right - 2, max(4, size // 7)):
                pygame.draw.line(sprite, COLORS["building_dark"], (tie_x, rail_y - 2), (tie_x + 2, rail_y + 5), 1)
        elif building == BuildingType.POLICE:
            badge = pygame.Rect(body.centerx - size // 9, body.top + size // 8, size // 5, size // 5)
            pygame.draw.rect(sprite, accent, badge, border_radius=1)
        elif building == BuildingType.FIRE:
            door = pygame.Rect(body.centerx - size // 8, body.bottom - size // 4, size // 4, size // 4)
            pygame.draw.rect(sprite, accent, door)
            pygame.draw.line(sprite, COLORS["building_light"], (door.centerx, door.top), (door.centerx, door.bottom), 1)
        elif building == BuildingType.SCHOOL:
            pygame.draw.polygon(
                sprite,
                accent,
                [(body.left, body.top), (body.centerx, body.top - size // 7), (body.right, body.top)],
            )
        else:
            pygame.draw.rect(sprite, accent, pygame.Rect(body.left, body.top, body.width, max(3, size // 8)))

    def _draw_road_parts(
        self,
        sprite: pygame.Surface,
        size: int,
        center: int,
        half_width: int,
        color: tuple[int, int, int],
        connections: dict[str, bool],
    ) -> None:
        center_rect = pygame.Rect(center - half_width, center - half_width, half_width * 2, half_width * 2)
        pygame.draw.rect(sprite, color, center_rect)
        arms = {
            "north": pygame.Rect(center - half_width, 0, half_width * 2, center),
            "east": pygame.Rect(center, center - half_width, size - center, half_width * 2),
            "south": pygame.Rect(center - half_width, center, half_width * 2, size - center),
            "west": pygame.Rect(0, center - half_width, center, half_width * 2),
        }
        for direction, connected in connections.items():
            if connected:
                pygame.draw.rect(sprite, color, arms[direction])

    def _draw_utility_parts(
        self,
        sprite: pygame.Surface,
        size: int,
        connections: dict[str, bool],
        color: tuple[int, int, int],
        line_width: int,
        node_radius: int,
    ) -> None:
        center = (size // 2, size // 2)
        endpoints = {
            "north": (size // 2, 2),
            "east": (size - 2, size // 2),
            "south": (size // 2, size - 2),
            "west": (2, size // 2),
        }
        if not any(connections.values()):
            pygame.draw.circle(sprite, color, center, node_radius)
            return
        for direction, connected in connections.items():
            if connected:
                pygame.draw.line(sprite, color, center, endpoints[direction], line_width)
        pygame.draw.circle(sprite, color, center, node_radius)

    def _draw_crosswalks(
        self,
        sprite: pygame.Surface,
        size: int,
        center: int,
        half_road: int,
        connections: dict[str, bool],
    ) -> None:
        if sum(connections.values()) < 3 or size < 24:
            return
        stripe_color = (214, 214, 188)
        stripe_w = max(1, size // 24)
        stripe_len = max(5, size // 5)
        gap = max(3, size // 10)
        for offset in (-gap, 0, gap):
            if connections["north"]:
                pygame.draw.line(sprite, stripe_color, (center - stripe_len // 2, center - half_road + offset // 4), (center + stripe_len // 2, center - half_road + offset // 4), stripe_w)
            if connections["south"]:
                pygame.draw.line(sprite, stripe_color, (center - stripe_len // 2, center + half_road + offset // 4), (center + stripe_len // 2, center + half_road + offset // 4), stripe_w)
            if connections["east"]:
                pygame.draw.line(sprite, stripe_color, (center + half_road + offset // 4, center - stripe_len // 2), (center + half_road + offset // 4, center + stripe_len // 2), stripe_w)
            if connections["west"]:
                pygame.draw.line(sprite, stripe_color, (center - half_road + offset // 4, center - stripe_len // 2), (center - half_road + offset // 4, center + stripe_len // 2), stripe_w)

    def _draw_lane_markings(
        self,
        sprite: pygame.Surface,
        size: int,
        center: int,
        connections: dict[str, bool],
    ) -> None:
        line_width = max(1, size // 20)
        margin = max(4, size // 7)
        if connections["north"]:
            pygame.draw.line(sprite, COLORS["road_line"], (center, center), (center, margin), line_width)
        if connections["east"]:
            pygame.draw.line(sprite, COLORS["road_line"], (center, center), (size - margin, center), line_width)
        if connections["south"]:
            pygame.draw.line(sprite, COLORS["road_line"], (center, center), (center, size - margin), line_width)
        if connections["west"]:
            pygame.draw.line(sprite, COLORS["road_line"], (center, center), (margin, center), line_width)
