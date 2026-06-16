"""
asset_loader.py — Optional PNG sprite loader with a two-tier cache.

The game draws all sprites procedurally (in sprites.py), but if PNG files are
placed in the assets/ directory they are used instead.  This module handles
finding, loading, and scaling those images.

Cache tiers
-----------
  raw_cache   : {name: Surface}  — full-size image loaded from disk once
  scaled_cache: {(name, size): Surface}  — image scaled to a requested width

Scaling is proportional: the height adjusts automatically so sprites don't
get squashed or stretched.
"""
from __future__ import annotations

from pathlib import Path

import pygame


class ImageAssetStore:
    """Loads optional PNG sprites and caches scaled copies."""

    def __init__(self, root: str | Path | None = None) -> None:
        # Default asset directory is <project_root>/assets/.
        self.root = Path(root) if root is not None else Path(__file__).resolve().parent.parent / "assets"
        # Two separate caches: raw (original size) and scaled (requested size).
        self.raw_cache: dict[str, pygame.Surface | None] = {}
        self.scaled_cache: dict[tuple[str, int], pygame.Surface | None] = {}

    def get(self, name: str, size: int) -> pygame.Surface | None:
        """
        Returns the named sprite scaled to `size` pixels wide, or None if not found.

        Results are cached so each (name, size) pair is scaled only once.
        """
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
            # Compute proportional height so the sprite keeps its aspect ratio.
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
        """
        Returns the absolute Path to assets/<name>.png, or None if the path
        is unsafe (absolute paths or directory traversal are rejected).
        """
        relative = Path(f"{name}.png")
        if relative.is_absolute() or relative.drive or relative.root or ".." in relative.parts:
            return None
        return self.root / relative

    def _load_raw(self, name: str) -> pygame.Surface | None:
        """
        Loads a PNG from disk into the raw cache (first access only).
        Returns None silently if the file doesn't exist or can't be decoded.
        """
        if name in self.raw_cache:
            return self.raw_cache[name]

        path = self.path_for(name)
        if path is None or not path.is_file():
            self.raw_cache[name] = None
            return None

        try:
            image = pygame.image.load(str(path))
            try:
                # convert_alpha() pre-multiplies alpha for faster blitting.
                image = image.convert_alpha()
            except Exception:
                pass   # convert_alpha() needs a display surface; skip if not ready
        except Exception:
            image = None

        self.raw_cache[name] = image
        return image
