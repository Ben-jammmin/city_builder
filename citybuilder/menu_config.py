"""Configuration passed from the main menu to the Game."""
from __future__ import annotations

from dataclasses import dataclass, field

MAP_SIZES: dict[str, tuple[int, int]] = {
    "Small":  (32, 24),
    "Medium": (64, 48),
    "Large":  (96, 72),
    "Huge":  (128, 96),
}

DIFFICULTY_MONEY: dict[str, int] = {
    "Easy":   75_000,
    "Normal": 50_000,
    "Hard":   25_000,
}

TERRAIN_STYLES: list[str] = ["Default", "Flat", "Hilly", "Coastal"]

SIM_SPEED_SECONDS: dict[str, float] = {
    "Slow":   2.5,
    "Normal": 1.25,
    "Fast":   0.4,
}


@dataclass
class GameConfig:
    map_size_name: str = "Medium"
    difficulty: str = "Normal"
    terrain_style: str = "Default"
    terrain_seed: int | None = None
    sim_speed: str = "Normal"
    day_night_cycle: bool = False
    load_save: bool = False

    @property
    def map_width(self) -> int:
        return MAP_SIZES[self.map_size_name][0]

    @property
    def map_height(self) -> int:
        return MAP_SIZES[self.map_size_name][1]

    @property
    def starting_money(self) -> int:
        return DIFFICULTY_MONEY[self.difficulty]

    @property
    def sim_seconds_per_month(self) -> float:
        return SIM_SPEED_SECONDS[self.sim_speed]

    @property
    def terrain_style_key(self) -> str:
        return self.terrain_style.lower()
