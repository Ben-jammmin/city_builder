"""
menu_config.py — Shared constants and the GameConfig dataclass.

This module defines all the options the player can choose on the New Game
screen and packages them into a GameConfig that is passed to Game.__init__.

Lookup tables
-------------
  MAP_SIZES        — display name  → (width, height) in tiles
  DIFFICULTY_MONEY — display name  → starting money amount
  TERRAIN_STYLES   — ordered list of terrain style names
  SIM_SPEED_SECONDS — display name → seconds of real time per simulated month

GameConfig
----------
  A simple dataclass whose properties derive the raw values needed by the game
  (map_width, starting_money, etc.) from the human-readable setting names.
  When load_save=True the game loads the most recent save file instead of
  generating a fresh map.
"""
from __future__ import annotations

from dataclasses import dataclass

# ── Option tables ──────────────────────────────────────────────────────────────

# Map size presets: each entry is (tile_columns, tile_rows).
MAP_SIZES: dict[str, tuple[int, int]] = {
    "Small":  (32, 24),
    "Medium": (64, 48),
    "Large":  (96, 72),
    "Huge":  (128, 96),
}

# Starting money for each difficulty level.
DIFFICULTY_MONEY: dict[str, int] = {
    "Easy":   75_000,
    "Normal": 50_000,
    "Hard":   25_000,
}

# Terrain generation styles shown in the New Game screen.
TERRAIN_STYLES: list[str] = ["Default", "Flat", "Hilly", "Coastal"]

# How many real-world seconds pass per simulated month at each speed.
SIM_SPEED_SECONDS: dict[str, float] = {
    "Slow":   2.5,
    "Normal": 1.25,
    "Fast":   0.4,
}

# ── GameConfig ─────────────────────────────────────────────────────────────────

@dataclass
class GameConfig:
    """
    All settings chosen on the New Game / Load Game screens, bundled for Game.

    The named string fields map to the lookup tables above; use the properties
    to get the actual numeric values the game needs.
    """
    map_size_name: str = "Medium"
    difficulty: str = "Normal"
    terrain_style: str = "Default"
    terrain_seed: int | None = None   # None = random seed each time
    sim_speed: str = "Normal"
    day_night_cycle: bool = False
    load_save: bool = False           # True = skip new-map generation, load latest save

    @property
    def map_width(self) -> int:
        """Tile columns for the chosen map size."""
        return MAP_SIZES[self.map_size_name][0]

    @property
    def map_height(self) -> int:
        """Tile rows for the chosen map size."""
        return MAP_SIZES[self.map_size_name][1]

    @property
    def starting_money(self) -> int:
        """Starting cash for the chosen difficulty level."""
        return DIFFICULTY_MONEY[self.difficulty]

    @property
    def sim_seconds_per_month(self) -> float:
        """Real-world seconds between simulation ticks (lower = faster game clock)."""
        return SIM_SPEED_SECONDS[self.sim_speed]

    @property
    def terrain_style_key(self) -> str:
        """Lowercase terrain style name passed to generate_terrain()."""
        return self.terrain_style.lower()
