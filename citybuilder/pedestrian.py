"""
pedestrian.py — Cosmetic walking pedestrians.

Pedestrians have no effect on the simulation; they exist purely to make the
city feel alive. Each one picks a random tile nearby, walks toward it, then
picks another target when it arrives.

Spawning: PedestrianSystem accumulates "spawn credits" proportional to the
city population.  When the credit total reaches 1, a new pedestrian is spawned
at a random position, up to max_count.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

from .settings import PEDESTRIAN_SPEED


@dataclass
class Pedestrian:
    """A single walking person, positioned in tile-space (float coordinates)."""

    x: float
    y: float
    vx: float = 0.0
    vy: float = 0.0
    target_x: int | None = None
    target_y: int | None = None

    def update(self, dt: float, map_width: int, map_height: int) -> None:
        """Move toward the current target; pick a new one when it is reached."""
        if self.target_x is None or self.target_y is None:
            self._choose_target(map_width, map_height)

        if self.target_x is not None and self.target_y is not None:
            dx = self.target_x - self.x
            dy = self.target_y - self.y
            distance = (dx ** 2 + dy ** 2) ** 0.5

            if distance < 0.2:
                # Close enough — pick the next destination.
                self._choose_target(map_width, map_height)
            else:
                # Normalise direction then scale by speed.
                speed = PEDESTRIAN_SPEED * dt
                self.vx = (dx / distance) * speed
                self.vy = (dy / distance) * speed
                self.x += self.vx
                self.y += self.vy
                # Clamp to stay inside the map.
                self.x = max(0, min(map_width - 0.2, self.x))
                self.y = max(0, min(map_height - 0.2, self.y))

    def _choose_target(self, map_width: int, map_height: int) -> None:
        """Picks a random tile within 3 tiles of the current position as the next goal."""
        current_tx = int(self.x)
        current_ty = int(self.y)
        radius = 3
        target_tx = random.randint(max(0, current_tx - radius), min(map_width - 1, current_tx + radius))
        target_ty = random.randint(max(0, current_ty - radius), min(map_height - 1, current_ty + radius))
        # Add a sub-tile offset so pedestrians don't always snap to exact tile centres.
        self.target_x = target_tx + random.random()
        self.target_y = target_ty + random.random()

    def get_tile_position(self) -> tuple[int, int]:
        """Returns the integer tile (x, y) where this pedestrian currently stands."""
        return int(self.x), int(self.y)


class PedestrianSystem:
    """Manages the full list of active pedestrians and their spawning logic."""

    def __init__(self, max_count: int = 50) -> None:
        self.pedestrians: list[Pedestrian] = []
        self.max_count = max_count
        # Fractional spawn credit accumulates each frame and converts to real
        # pedestrians once it reaches 1.0.
        self.spawn_accumulator = 0.0

    def update(self, dt: float, map_width: int, map_height: int, population: int, spawn_rate: float) -> None:
        """Ticks all pedestrians and spawns new ones proportional to population size."""
        for ped in self.pedestrians:
            ped.update(dt, map_width, map_height)

        if population > 0 and len(self.pedestrians) < self.max_count:
            # Accumulate credit; cap so we don't burst-spawn after a pause.
            self.spawn_accumulator = min(self.spawn_accumulator + population * spawn_rate * dt,
                                         float(self.max_count))
            while self.spawn_accumulator >= 1.0 and len(self.pedestrians) < self.max_count:
                self.spawn_accumulator -= 1.0
                self._spawn_pedestrian(map_width, map_height)

    def _spawn_pedestrian(self, map_width: int, map_height: int) -> None:
        """Creates a new Pedestrian at a random position anywhere on the map."""
        x = random.random() * map_width
        y = random.random() * map_height
        self.pedestrians.append(Pedestrian(x=x, y=y))

    def clear(self) -> None:
        """Removes all pedestrians (called when loading a save file)."""
        self.pedestrians.clear()
