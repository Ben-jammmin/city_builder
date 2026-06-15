"""
camera.py — Isometric camera system

The camera converts map tile coordinates (tx, ty) into screen pixel positions
using an isometric projection. The map looks like a diamond grid viewed from
the top-left. You can scroll, zoom, and rotate the view.

Isometric math quick reference:
  - tile (tx, ty) draws with its top (north) vertex at screen position (sx, sy)
  - diamond width  = ISO_W pixels (e.g. 64)
  - diamond height = ISO_H pixels (e.g. 32, always half the width)
  - wx = (tx - ty) * half_width  + origin_offset  (left/right position)
  - wy = (tx + ty) * half_height                  (up/down position)
"""

from __future__ import annotations

import math

import pygame

# The size of one tile at 100% zoom.
# ISO_H is always half of ISO_W to keep the classic 2:1 isometric ratio.
ISO_W = 64
ISO_H = 32


class Camera:
    """
    Tracks where the player is looking on the map.

    Key concepts:
      - self.x / self.y  : world-pixel scroll position (what part of the map is visible)
      - self.zoom        : zoom multiplier (0.3 = very zoomed out, 2.8 = very zoomed in)
      - self.rotation    : 0/1/2/3 (0=NW view, 1=NE, 2=SE, 3=SW). Press Q/E to rotate.
      - self.viewport    : the pygame.Rect area on screen where the map is drawn
    """

    def __init__(self, map_pixel_width: int, map_pixel_height: int, viewport: pygame.Rect) -> None:
        # Accept either (map_width, map_height) tile counts or old (pixels) style
        if map_pixel_width > 512:
            map_width  = map_pixel_width  // 32
            map_height = map_pixel_height // 32
        else:
            map_width  = map_pixel_width
            map_height = map_pixel_height

        self.map_width  = map_width
        self.map_height = map_height
        self.viewport   = viewport
        self.zoom       = 1.0
        self.rotation   = 0        # 0=NW viewer, 1=NE, 2=SE, 3=SW
        self.tile_w     = ISO_W
        self.tile_h     = ISO_H

        hw = ISO_W // 2

        # Total world pixel extents — same for all rotations because (W+H) is constant.
        self.map_pixel_width  = (map_width + map_height) * hw + ISO_W
        self.map_pixel_height = (map_width + map_height) * (ISO_H // 2) + ISO_H * 4

        # Start the camera centered on the map (rotation 0)
        self.x = 0.0
        self.y = 0.0
        self._recenter()

    # ------------------------------------------------------------------ #
    # Simple camera controls                                               #
    # ------------------------------------------------------------------ #

    def set_viewport(self, viewport: pygame.Rect) -> None:
        """Update the screen area the map is drawn into (called on window resize)."""
        self.viewport = viewport
        self.clamp()

    def move(self, dx: float, dy: float) -> None:
        """Scroll the camera by (dx, dy) world pixels."""
        self.x += dx
        self.y += dy
        self.clamp()

    def change_zoom(self, amount: float, mouse_pos: tuple[int, int] | None = None) -> None:
        """Zoom in/out. If mouse_pos is given, zoom toward that point on screen."""
        before_x, before_y = (0.0, 0.0)
        if mouse_pos is not None:
            before_x, before_y = self.screen_to_world_pixels(mouse_pos)

        self.zoom = max(0.3, min(2.8, self.zoom + amount))

        if mouse_pos is not None:
            # Shift scroll so the tile under the cursor stays under the cursor
            after_x, after_y = self.screen_to_world_pixels(mouse_pos)
            self.x += before_x - after_x
            self.y += before_y - after_y

        self.clamp()

    def rotate_cw(self) -> None:
        """Rotate the view 90 degrees clockwise (press E)."""
        self.rotation = (self.rotation + 1) % 4
        self._recenter()

    def rotate_ccw(self) -> None:
        """Rotate the view 90 degrees counter-clockwise (press Q)."""
        self.rotation = (self.rotation - 1) % 4
        self._recenter()

    # ------------------------------------------------------------------ #
    # Coordinate conversion                                                #
    # ------------------------------------------------------------------ #

    def world_to_screen(self, tx: float, ty: float, tile_size: int = 0) -> tuple[int, int]:
        """
        Convert map tile (tx, ty) to the screen pixel of the tile's TOP (north) vertex.

        The returned point is the very top of the diamond shape — you'd then
        draw the diamond extending down from there.
        """
        # First rotate the tile coords so the view direction is applied
        rtx, rty = self._apply_rotation(tx, ty)

        hw = self.tile_w // 2
        hh = self.tile_h // 2

        # Isometric projection: convert rotated tile grid to world pixels.
        # The origin shifts so the leftmost tile always appears near the left edge.
        wx = (rtx - rty) * hw + self._origin_x()
        wy = (rtx + rty) * hh

        # Apply scroll (self.x/y) and zoom, then offset to the viewport corner
        sx = self.viewport.left + int((wx - self.x) * self.zoom)
        sy = self.viewport.top  + int((wy - self.y) * self.zoom)
        return sx, sy

    def screen_to_tile(self, pos: tuple[int, int], tile_size: int = 0) -> tuple[int, int] | None:
        """
        Convert a screen pixel position (from mouse) back to a map tile (tx, ty).
        Returns None if the position is outside the viewport or map bounds.
        """
        if not self.viewport.collidepoint(pos):
            return None

        wx, wy = self.screen_to_world_pixels(pos)

        hw = self.tile_w // 2
        hh = self.tile_h // 2
        rx = wx - self._origin_x()

        # Inverse of the isometric projection formula
        rtx = math.floor((rx / hw + wy / hh) / 2)
        rty = math.floor((wy / hh - rx / hw) / 2)

        # Un-rotate to get back to real map coordinates
        tx, ty = self._unapply_rotation(rtx, rty)

        if 0 <= tx < self.map_width and 0 <= ty < self.map_height:
            return tx, ty
        return None

    def screen_to_world_pixels(self, pos: tuple[int, int]) -> tuple[float, float]:
        """Convert a screen pixel to a world (pre-zoom) pixel position."""
        sx = pos[0] - self.viewport.left
        sy = pos[1] - self.viewport.top
        return self.x + sx / self.zoom, self.y + sy / self.zoom

    def visible_tile_bounds(self, tile_size: int, map_width: int, map_height: int) -> tuple[int, int, int, int]:
        """
        Return (start_x, start_y, end_x, end_y) — the range of tiles visible
        on screen right now. The renderer only draws tiles inside this box.

        We add a margin of a few tiles to avoid pop-in at the edges.
        """
        margin = 5
        hw = self.tile_w // 2
        hh = self.tile_h // 2
        origin = self._origin_x()

        # Sample the four corners of the viewport to find the tile range
        rtxs: list[float] = []
        rtys: list[float] = []
        for sx, sy in [
            (self.viewport.left,  self.viewport.top),
            (self.viewport.right, self.viewport.top),
            (self.viewport.left,  self.viewport.bottom),
            (self.viewport.right, self.viewport.bottom),
        ]:
            wx, wy = self.screen_to_world_pixels((sx, sy))
            rx = wx - origin
            rtxs.append((rx / hw + wy / hh) / 2)
            rtys.append((wy / hh - rx / hw) / 2)

        # The rotated map has swapped dimensions for 90° and 270° rotations
        if self.rotation in (1, 3):
            rot_w, rot_h = map_height, map_width
        else:
            rot_w, rot_h = map_width, map_height

        return (
            max(0,     math.floor(min(rtxs)) - margin),
            max(0,     math.floor(min(rtys)) - margin),
            min(rot_w, math.ceil(max(rtxs))  + margin),
            min(rot_h, math.ceil(max(rtys))  + margin),
        )

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def clamp(self) -> None:
        """Keep the scroll position inside the map boundaries."""
        vw = self.viewport.width  / self.zoom
        vh = self.viewport.height / self.zoom
        self.x = max(0.0, min(self.x, max(0.0, self.map_pixel_width  - vw)))
        self.y = max(0.0, min(self.y, max(0.0, self.map_pixel_height - vh)))

    def _origin_x(self) -> int:
        """
        The horizontal world-pixel offset that places the leftmost map tile
        at world_x = 0.  This changes with rotation because which corner
        ends up at the far left of the diamond depends on the view angle.
        """
        hw = self.tile_w // 2
        # For rotations 0 & 2 the far-left corner is at map tile (0, H-1).
        # For rotations 1 & 3 it is at map tile (0, W-1) in rotated space.
        if self.rotation in (0, 2):
            return (self.map_height - 1) * hw
        else:
            return (self.map_width - 1) * hw

    def _recenter(self) -> None:
        """Move the scroll position so the centre of the map is on screen after a rotation."""
        hw = self.tile_w // 2
        hh = self.tile_h // 2
        origin = self._origin_x()

        # Size of the map in the current rotated orientation
        if self.rotation in (1, 3):
            rot_w, rot_h = self.map_height, self.map_width
        else:
            rot_w, rot_h = self.map_width, self.map_height

        # World position of the centre tile (in rotated space)
        cx, cy = rot_w / 2.0, rot_h / 2.0
        center_wx = (cx - cy) * hw + origin
        center_wy = (cx + cy) * hh

        # Position the camera so the centre tile is roughly centred on screen
        self.x = max(0.0, center_wx - self.viewport.width  / (2.0 * self.zoom))
        self.y = max(0.0, center_wy - self.viewport.height / (2.8 * self.zoom))
        self.clamp()

    def _apply_rotation(self, tx: float, ty: float) -> tuple[float, float]:
        """
        Transform map tile (tx, ty) for the current camera rotation.

        Rotation 0 = viewer from NW (default)  -> tiles unchanged
        Rotation 1 = viewer from NE (90 deg CW) -> map rotated 90 deg CW
        Rotation 2 = viewer from SE (180 deg)   -> map rotated 180 deg
        Rotation 3 = viewer from SW (270 deg CW)-> map rotated 270 deg CW
        """
        W, H = self.map_width, self.map_height
        if self.rotation == 0:
            return tx, ty
        elif self.rotation == 1:
            return H - 1 - ty, tx
        elif self.rotation == 2:
            return W - 1 - tx, H - 1 - ty
        else:  # rotation == 3
            return ty, W - 1 - tx

    def _unapply_rotation(self, rtx: float, rty: float) -> tuple[int, int]:
        """Inverse of _apply_rotation: convert rotated coords back to map coords."""
        W, H = self.map_width, self.map_height
        if self.rotation == 0:
            return int(rtx), int(rty)
        elif self.rotation == 1:
            return int(rty), int(H - 1 - rtx)
        elif self.rotation == 2:
            return int(W - 1 - rtx), int(H - 1 - rty)
        else:  # rotation == 3
            return int(W - 1 - rty), int(rtx)
