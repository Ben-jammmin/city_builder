"""Walking pedestrians — purely visual eye-candy, no effect on the simulation."""
from __future__ import annotations

import random
from dataclasses import dataclass

from .settings import PEDESTRIAN_SPEED


@dataclass
class Pedestrian:
    """Represents a walking pedestrian on the map."""

    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    target_x: int | None = None
    target_y: int | None = None

    def update(self, dt: float, map_width: int, map_height: int) -> None:
        """Advance position one frame, picking a new target when the current one is reached."""
        if self.target_x is None or self.target_y is None:
            self._choose_target(map_width, map_height)

        if self.target_x is not None and self.target_y is not None:
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            distance = (dx ** 2 + dy ** 2) ** 0.5

            if distance < 0.2:
                self._choose_target(map_width, map_height)
            else:
                speed = PEDESTRIAN_SPEED * dt
                self.vx = (dx / distance) * speed
                self.vy = (dy / distance) * speed
                self.x += self.vx
                self.y += self.vy
                self.x = max(0, min(map_width - 0.2, self.x))
                self.y = max(0, min(map_height - 0.2, self.y))

    def _choose_target(self, map_width: int, map_height: int) -> None:
        """Pick a random tile within 3 steps of the current position."""
        current_tx = int(self.x)
        current_ty = int(self.y)
        radius = 3
        target_tx = random.randint(max(0, current_tx - radius), min(map_width - 1, current_tx + radius))
        target_ty = random.randint(max(0, current_ty - radius), min(map_height - 1, current_ty + radius))
        self.target_x = target_tx + random.random()
        self.target_y = target_ty + random.random()

    def get_tile_position(self) -> tuple[int, int]:
        """Get the current tile coordinates."""
        return int(self.x), int(self.y)


class PedestrianSystem:
    """Manages all pedestrians on the map."""

    def __init__(self, max_count: int = 50) -> None:
        self.pedestrians: list[Pedestrian] = []
        self.max_count = max_count
        self.spawn_accumulator = 0.0

    def update(self, dt: float, map_width: int, map_height: int, population: int, spawn_rate: float) -> None:
        """Tick every pedestrian and spawn new ones based on current population."""
        for ped in self.pedestrians:
            ped.update(dt, map_width, map_height)

        if population > 0 and len(self.pedestrians) < self.max_count:
            self.spawn_accumulator += population * spawn_rate * dt
            while self.spawn_accumulator >= 1.0 and len(self.pedestrians) < self.max_count:
                self.spawn_accumulator -= 1.0
                self._spawn_pedestrian(map_width, map_height)

    def _spawn_pedestrian(self, map_width: int, map_height: int) -> None:
        x = random.random() * map_width
        y = random.random() * map_height
        self.pedestrians.append(Pedestrian(x=x, y=y))

    def clear(self) -> None:
        """Remove all pedestrians."""
        self.pedestrians.clear()
