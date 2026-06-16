from __future__ import annotations

import argparse
import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pygame

from citybuilder.game import Game
from citybuilder.models import (
    MENU_ORDER,
    TOOL_TO_BUILDING,
    TOOL_TO_ZONE,
    BuildingType,
    TerrainType,
    Tool,
    ViewMode,
    ZoneType,
    menu_for_tool,
)
from citybuilder.save_load import list_saves, load_game, slot_path


BUILD_TOOL_ORDER = [
    Tool.RESIDENTIAL,
    Tool.DENSE_RESIDENTIAL,
    Tool.COMMERCIAL,
    Tool.DENSE_COMMERCIAL,
    Tool.INDUSTRIAL,
    Tool.PARK,
    Tool.ROAD,
    Tool.POWER_LINE,
    Tool.WATER_PIPE,
    Tool.POWER_PLANT,
    Tool.LARGE_POWER_PLANT,
    Tool.WATER_TOWER,
    Tool.LARGE_WATER_TOWER,
    Tool.POLICE,
    Tool.FIRE,
    Tool.SCHOOL,
    Tool.TRAIN_STATION,
    Tool.AIRPORT,
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a headless Codex smoke test for the Pygame city builder.")
    parser.add_argument(
        "--screenshots",
        type=Path,
        default=None,
        help="Optional folder where rendered smoke-test screenshots should be saved.",
    )
    return parser.parse_args()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_surface_has_visual_content(surface: pygame.Surface, label: str) -> None:
    width, height = surface.get_size()
    step_x = max(1, width // 20)
    step_y = max(1, height // 14)
    colors: set[tuple[int, int, int]] = set()

    for x in range(0, width, step_x):
        for y in range(0, height, step_y):
            colors.add(surface.get_at((min(x, width - 1), min(y, height - 1)))[:3])

    require(len(colors) >= 8, f"{label} render looks blank or too flat ({len(colors)} sampled colors)")


def capture(game: Game, screenshot_dir: Path | None, name: str) -> None:
    game._draw()
    assert_surface_has_visual_content(game.screen, name)
    if screenshot_dir is not None:
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        pygame.image.save(game.screen, str(screenshot_dir / f"{name}.png"))


def prepare_tile(game: Game, tile_pos: tuple[int, int]) -> None:
    tile = game.map.get(*tile_pos)
    tile.clear()
    tile.terrain = TerrainType.GRASS


def pickable_screen_pos(game: Game, tile_pos: tuple[int, int]) -> tuple[int, int]:
    sx, sy = game.camera.world_to_screen(*tile_pos)
    max_dx = int(game.camera.tile_w * game.camera.zoom // 2)
    max_dy = int(game.camera.tile_h * game.camera.zoom)

    candidates: list[tuple[int, int]] = []
    for dy in range(1, max(2, max_dy)):
        candidates.append((sx, sy + dy))
    for dx in range(-max_dx, max_dx + 1, 4):
        for dy in range(1, max(2, max_dy), 3):
            candidates.append((sx + dx, sy + dy))

    for pos in candidates:
        if game._mouse_tile(pos) == tile_pos:
            return pos

    raise AssertionError(f"Could not find pickable screen position for tile {tile_pos}")


def click_tool(game: Game, tool: Tool, tile_pos: tuple[int, int]) -> None:
    select_tool_via_ui(game, tool)
    click_tile(game, tile_pos, button=1)


def click_screen(game: Game, pos: tuple[int, int], button: int = 1) -> None:
    down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": button, "pos": pos})
    up = pygame.event.Event(pygame.MOUSEBUTTONUP, {"button": button, "pos": pos})
    game._handle_mouse_down(down)
    game._handle_mouse_up(up)


def click_tile(game: Game, tile_pos: tuple[int, int], button: int = 1) -> None:
    game.painted_this_drag.clear()
    pos = pickable_screen_pos(game, tile_pos)
    click_screen(game, pos, button)


def click_sidebar_menu(game: Game, menu_name: str) -> None:
    game._draw()
    for rect, button_menu in game.sidebar.menu_buttons:
        if button_menu == menu_name:
            click_screen(game, rect.center)
            require(game.active_menu == menu_name, f"Menu click did not activate {menu_name}")
            return
    raise AssertionError(f"Could not find sidebar menu button {menu_name}")


def select_tool_via_ui(game: Game, tool: Tool) -> None:
    click_sidebar_menu(game, menu_for_tool(tool))
    game._draw()
    for rect, button_tool in game.sidebar.tool_buttons:
        if button_tool == tool:
            click_screen(game, rect.center)
            require(game.active_tool == tool, f"Tool click did not activate {tool.value}")
            return
    raise AssertionError(f"Could not find sidebar tool button {tool.value}")


def assert_tool_result(game: Game, tool: Tool, tile_pos: tuple[int, int]) -> None:
    tile = game.map.get(*tile_pos)
    if tool in TOOL_TO_ZONE:
        expected_zone, expected_level = TOOL_TO_ZONE[tool]
        require(tile.zone == expected_zone, f"{tool.value} did not place {expected_zone.value}")
        require(tile.zone_level == expected_level, f"{tool.value} placed wrong zone level")
    elif tool in TOOL_TO_BUILDING:
        expected_building = TOOL_TO_BUILDING[tool]
        require(tile.building == expected_building, f"{tool.value} did not place {expected_building.value}")
    elif tool == Tool.ROAD:
        require(tile.has_road, "Road placement failed")
    elif tool == Tool.POWER_LINE:
        require(tile.has_power_line, "Power line placement failed")
    elif tool == Tool.WATER_PIPE:
        require(tile.has_water_pipe, "Water pipe placement failed")
    else:
        raise AssertionError(f"No smoke assertion configured for {tool.value}")


def exercise_menu_tabs(game: Game) -> None:
    for menu_name in MENU_ORDER:
        click_sidebar_menu(game, menu_name)


def exercise_all_build_tools(game: Game, start: tuple[int, int]) -> dict[Tool, tuple[int, int]]:
    positions: dict[Tool, tuple[int, int]] = {}
    for index, tool in enumerate(BUILD_TOOL_ORDER):
        tile_pos = (start[0] + index % 6, start[1] + index // 6)
        positions[tool] = tile_pos
        prepare_tile(game, tile_pos)

    for tool, tile_pos in positions.items():
        click_tool(game, tool, tile_pos)
        assert_tool_result(game, tool, tile_pos)

    return positions


def exercise_bulldozing(game: Game, start: tuple[int, int]) -> None:
    road_tile = start
    zone_tile = (start[0] + 1, start[1])
    building_tile = (start[0] + 2, start[1])
    terrain_tile = (start[0] + 3, start[1])
    tool_tile = (start[0] + 4, start[1])

    for tile_pos in (road_tile, zone_tile, building_tile, terrain_tile, tool_tile):
        prepare_tile(game, tile_pos)

    game.map.place_road(*road_tile)
    game.map.place_zone(*zone_tile, ZoneType.RESIDENTIAL)
    game.map.place_building(*building_tile, BuildingType.SCHOOL)
    game.map.get(*terrain_tile).terrain = TerrainType.HILL
    game.map.place_water_pipe(*tool_tile)

    for tile_pos in (road_tile, zone_tile, building_tile, terrain_tile):
        click_tile(game, tile_pos, button=3)

    require(game.map.get(*road_tile).is_empty, "Right-click bulldoze did not clear road")
    require(game.map.get(*zone_tile).is_empty, "Right-click bulldoze did not clear zone")
    require(game.map.get(*building_tile).is_empty, "Right-click bulldoze did not clear building")
    require(game.map.get(*terrain_tile).terrain == TerrainType.GRASS, "Right-click bulldoze did not clear hill")

    click_tool(game, Tool.BULLDOZE, tool_tile)
    require(game.map.get(*tool_tile).is_empty, "Bulldoze tool did not clear utility")


def exercise_zoom_and_resize(game: Game, tile_pos: tuple[int, int]) -> None:
    prepare_tile(game, tile_pos)
    before_zoom = game.camera.zoom
    game.camera.change_zoom(0.45, pickable_screen_pos(game, tile_pos))
    click_tool(game, Tool.WATER_PIPE, tile_pos)
    require(game.map.get(*tile_pos).has_water_pipe, "Water pipe placement failed after zoom")
    game.camera.change_zoom(before_zoom - game.camera.zoom)

    game._resize_window(1024, 700)
    require(game.screen.get_size() == (1024, 700), "Window resize did not apply requested size")
    game._resize_window(1280, 800)
    require(game.screen.get_size() == (1280, 800), "Window resize did not restore default size")


def exercise_menu_minimize(game: Game, screenshot_dir: Path | None) -> None:
    game._draw()
    expanded_height = game.sidebar.current_height()
    expanded_viewport_height = game.camera.viewport.height
    click_screen(game, game.sidebar.minimize_rect.center)
    require(game.sidebar.minimized, "Command bar did not minimize")
    require(game.sidebar.current_height() < expanded_height, "Minimized command bar did not shrink")
    require(game.camera.viewport.height > expanded_viewport_height, "Map viewport did not expand after minimizing")
    capture(game, screenshot_dir, "menu_minimized")

    click_screen(game, game.sidebar.minimize_rect.center)
    require(not game.sidebar.minimized, "Command bar did not restore")
    require(game.camera.viewport.height == expanded_viewport_height, "Map viewport did not restore after expanding menu")
    capture(game, screenshot_dir, "menu_expanded")


def add_utility_debug_networks(game: Game, start: tuple[int, int]) -> None:
    power_source = start
    power_lines = [(start[0] + 1, start[1]), (start[0] + 2, start[1])]
    orphan_power = (start[0] + 4, start[1])
    water_source = (start[0], start[1] + 2)
    water_lines = [(start[0] + 1, start[1] + 2), (start[0] + 2, start[1] + 2)]
    orphan_water = (start[0] + 4, start[1] + 2)

    for tile_pos in [power_source, orphan_power, water_source, orphan_water, *power_lines, *water_lines]:
        prepare_tile(game, tile_pos)

    game.map.place_building(*power_source, BuildingType.POWER_PLANT)
    for tile_pos in power_lines:
        game.map.place_power_line(*tile_pos)
    game.map.place_power_line(*orphan_power)

    game.map.place_building(*water_source, BuildingType.WATER_TOWER)
    for tile_pos in water_lines:
        game.map.place_water_pipe(*tile_pos)
    game.map.place_water_pipe(*orphan_water)


def exercise_real_save_load() -> bool:
    saves = list_saves()
    filled = [(i + 1, s) for i, s in enumerate(saves) if s is not None]
    if not filled:
        return False
    slot, _ = filled[0]
    city_map, stats = load_game(slot_path(slot))
    require(city_map.width > 0 and city_map.height > 0, "Real save loaded with invalid map dimensions")
    require(stats.money is not None, "Real save loaded with invalid stats")
    return True


def main() -> None:
    args = parse_args()
    screenshot_dir = args.screenshots.resolve() if args.screenshots else None
    game: Game | None = None
    with tempfile.TemporaryDirectory() as _temp_dir:
        try:
            game = Game()
            game.stats.money = 100000

            center = (game.map.width // 2, game.map.height // 2)
            tool_start = (center[0] - 5, center[1] - 3)
            bulldoze_start = (center[0] - 5, center[1] + 2)
            zoom_tile = (center[0] + 4, center[1] + 2)

            exercise_menu_tabs(game)
            require(game._mouse_tile(pickable_screen_pos(game, center)) == center, "Camera picking failed")

            tool_positions = exercise_all_build_tools(game, tool_start)
            require(game.map.get(*tool_positions[Tool.WATER_PIPE]).has_water_pipe, "Water pipe tool was not covered")
            capture(game, screenshot_dir, "after_all_tools")
            exercise_menu_minimize(game, screenshot_dir)

            exercise_bulldozing(game, bulldoze_start)
            capture(game, screenshot_dir, "after_bulldoze")

            exercise_zoom_and_resize(game, zoom_tile)
            capture(game, screenshot_dir, "after_zoom_resize")

            add_utility_debug_networks(game, (center[0] + 7, center[1] - 4))
            real_save_checked = exercise_real_save_load()
            capture(game, screenshot_dir, "normal_after_build")
            for view_mode in ViewMode:
                game.view_mode = view_mode
                capture(game, screenshot_dir, f"view_{view_mode.value}")

            for rotation in range(1, 5):
                game.camera.rotate_cw()
                capture(game, screenshot_dir, f"rotation_{rotation % 4}")

            game.stats.paused = False
            for _ in range(3):
                game.simulation.simulate_month()
            capture(game, screenshot_dir, "after_three_months")

            game._do_save(1)
            require(slot_path(1).exists(), "Smoke save was not created")
            game._do_load(1)
            require(game.map.get(*tool_positions[Tool.WATER_PIPE]).has_water_pipe, "Water pipe did not survive save/load")
            capture(game, screenshot_dir, "after_save_load")

            game.view_mode = ViewMode.NORMAL
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_v, "mod": 0}))
            game._handle_events()
            require(game.view_mode != ViewMode.NORMAL, "Keyboard event handling did not cycle view")
            capture(game, screenshot_dir, "after_keyboard_view_cycle")

            print("Codex smoke test OK")
            print(f"money={game.stats.money} month={game.stats.month} messages={len(game.stats.messages)}")
            print(f"real_save_checked={real_save_checked}")
            if screenshot_dir is not None:
                print(f"screenshots={screenshot_dir}")
        finally:
            if game is not None:
                game.running = False
            pygame.quit()


if __name__ == "__main__":
    main()
