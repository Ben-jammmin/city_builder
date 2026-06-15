"""Loads and caches PNG sprite assets from the assets/ directory."""
from __future__ import annotations

from pathlib import Path

import pygame


class ImageAssetStore:
    """Loads optional PNG sprites and caches scaled copies."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else Path(__file__).resolve().parent.parent / "assets"
        self.raw_cache: dict[str, pygame.Surface | None] = {}
        self.scaled_cache: dict[tuple[str, int], pygame.Surface | None] = {}

    def get(self, name: str, size: int) -> pygame.Surface | None:
        if size <= 0:
            return None

        key = (name, size)
        if key in self.scaled_cache:
            return self.scaled_cache[key]

        raw = self._load_raw(name)
        if raw is None:
            self.scaled_cache[key] = None
            return None

        try:
            raw_width, raw_height = raw.get_size()
            target_height = max(1, round(raw_height * (size / raw_width)))
            if raw.get_size() == (size, target_height):
                sprite = raw.copy()
            else:
                sprite = pygame.transform.scale(raw, (size, target_height))
        except Exception:
            sprite = None

        self.scaled_cache[key] = sprite
        return sprite

    def path_for(self, name: str) -> Path | None:
        relative = Path(f"{name}.png")
        if relative.is_absolute() or ".." in relative.parts:
            return None
        return self.root / relative

    def _load_raw(self, name: str) -> pygame.Surface | None:
        if name in self.raw_cache:
            return self.raw_cache[name]

        path = self.path_for(name)
        if path is None or not path.is_file():
            self.raw_cache[name] = None
            return None

        try:
            image = pygame.image.load(str(path))
            try:
                image = image.convert_alpha()
            except Exception:
                pass
        except Exception:
            image = None

        self.raw_cache[name] = image
        return image
