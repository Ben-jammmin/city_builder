"""
camera.py — Isometric camera system.

The camera converts map tile coordinates (tx, ty) into screen pixel positions
using an isometric projection. The map looks like a diamond grid viewed from
the top-left. You can scroll, zoom, and rotate the view.

Isometric math quick reference
-------------------------------
  Tiles are drawn at a 2:1 diagonal (2 pixels wide, 1 pixel tall).
  Given a tile at (tx, ty), its top vertex appears on screen at:

      screen_x = (tile_x - tile_y) * half_tile_width  + origin_offset
      screen_y = (tile_x + tile_y) * half_tile_height

  The origin_offset shifts the whole map so its leftmost tile stays near
  the left edge of the viewport regardless of map size or rotation.

Camera rotation
---------------
  The map can be viewed from four cardinal directions:
    rotation 0 = viewer from NW (default, tile (0,0) in top-left)
    rotation 1 = viewer from NE  (90 degrees clockwise)
    rotation 2 = viewer from SE  (180 degrees)
    rotation 3 = viewer from SW  (270 degrees clockwise)
  Press Q/E in-game to rotate counter-clockwise/clockwise.
  _apply_rotation() transforms tile coords into the rotated display space.
"""

from __future__ import annotations

import math

import pygame

# ── Base tile size (at 100% zoom) ─────────────────────────────────────────────
# ISO_H is always half of ISO_W to maintain the classic 2:1 isometric ratio.
ISO_W = 64   # tile diamond pixel width
ISO_H = 32   # tile diamond pixel height (= ISO_W // 2)


class Camera:
    """
    Tracks where the player is looking on the map.

    Key attributes
    ---------------
    self.x / self.y   : world-pixel scroll position (top-left of visible area)
    self.zoom         : zoom multiplier (0.3 = very zoomed out, 2.8 = very zoomed in)
    self.rotation     : 0/1/2/3 — which corner of the map faces the viewer
    self.viewport     : pygame.Rect area on screen reserved for the map
    """

    def __init__(self, map_pixel_width: int, map_pixel_height: int, viewport: pygame.Rect) -> None:
        # Accept either (map_width, map_height) tile counts or old-style pixel dimensions.
        if map_pixel_width > 512:
            # Legacy call with pixel dimensions — convert back to tile counts.
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

        # Total world-pixel extents of the full isometric map.
        # Width: the longest diagonal row has (W + H) tiles, each ISO_W//2 pixels wide.
        self.map_pixel_width  = (map_width + map_height) * hw + ISO_W
        self.map_pixel_height = (map_width + map_height) * (ISO_H // 2) + ISO_H * 4

        # Start scrolled to the map centre.
        self.x = 0.0
        self.y = 0.0
        self._recenter()

    # ── Simple camera controls ─────────────────────────────────────────────────

    def set_viewport(self, viewport: pygame.Rect) -> None:
        """Updates the screen area the map is drawn into (called on window resize)."""
        self.viewport = viewport
        self.clamp()

    def move(self, dx: float, dy: float) -> None:
        """Scrolls the camera by (dx, dy) world pixels."""
        self.x += dx
        self.y += dy
        self.clamp()

    def change_zoom(self, amount: float, mouse_pos: tuple[int, int] | None = None) -> None:
        """
        Zooms in/out by amount. If mouse_pos is given, zooms toward that
        screen point so the tile under the cursor stays under the cursor.
        """
        before_x, before_y = (0.0, 0.0)
        if mouse_pos is not None:
            # Record which world pixel is under the cursor before the zoom.
            before_x, before_y = self.screen_to_world_pixels(mouse_pos)

        # Clamp zoom between 0.3× (overview) and 2.8× (close-up).
        self.zoom = max(0.3, min(2.8, self.zoom + amount))

        if mouse_pos is not None:
            # After the zoom the same screen position maps to a different world pixel.
            # Shift the scroll so the world pixel is back under the cursor.
            after_x, after_y = self.screen_to_world_pixels(mouse_pos)
            self.x += before_x - after_x
            self.y += before_y - after_y

        self.clamp()

    def rotate_cw(self) -> None:
        """Rotates the view 90 degrees clockwise (press E)."""
        self.rotation = (self.rotation + 1) % 4
        self._recenter()

    def rotate_ccw(self) -> None:
        """Rotates the view 90 degrees counter-clockwise (press Q)."""
        self.rotation = (self.rotation - 1) % 4
        self._recenter()

    # ── Coordinate conversion ──────────────────────────────────────────────────

    def world_to_screen(self, tx: float, ty: float, tile_size: int = 0) -> tuple[int, int]:
        """
        Converts map tile (tx, ty) to the screen pixel of the tile's TOP (north) vertex.

        Isometric projection (for the current rotation):
          wx = (rtx - rty) * half_width  + origin_offset
          wy = (rtx + rty) * half_height
        where rtx, rty are the tile coords in rotated space.

        The returned point is the very top of the diamond shape; the diamond
        then extends half_height down from there on each side.
        """
        # Apply camera rotation so we draw in the correct orientation.
        rtx, rty = self._apply_rotation(tx, ty)

        hw = self.tile_w // 2
        hh = self.tile_h // 2

        # Isometric projection: horizontal position depends on (x - y), vertical on (x + y).
        wx = (rtx - rty) * hw + self._origin_x()
        wy = (rtx + rty) * hh

        # Translate from world pixels to screen pixels using scroll and zoom.
        sx = self.viewport.left + int((wx - self.x) * self.zoom)
        sy = self.viewport.top  + int((wy - self.y) * self.zoom)
        return sx, sy

    def screen_to_tile(self, pos: tuple[int, int], tile_size: int = 0) -> tuple[int, int] | None:
        """
        Converts a screen pixel position (from the mouse) back to a map tile (tx, ty).
        Returns None if the position is outside the viewport or map bounds.
        """
        if not self.viewport.collidepoint(pos):
            return None

        wx, wy = self.screen_to_world_pixels(pos)

        hw = self.tile_w // 2
        hh = self.tile_h // 2
        rx = wx - self._origin_x()

        # Inverse of the isometric formula: solve for (rtx, rty).
        rtx = math.floor((rx / hw + wy / hh) / 2)
        rty = math.floor((wy / hh - rx / hw) / 2)

        # Convert rotated coords back to real map coordinates.
        tx, ty = self._unapply_rotation(rtx, rty)

        if 0 <= tx < self.map_width and 0 <= ty < self.map_height:
            return tx, ty
        return None

    def screen_to_world_pixels(self, pos: tuple[int, int]) -> tuple[float, float]:
        """Converts a screen pixel to a world (pre-zoom, pre-scroll) pixel position."""
        sx = pos[0] - self.viewport.left
        sy = pos[1] - self.viewport.top
        # Divide by zoom to undo the zoom scaling, then add the scroll offset.
        return self.x + sx / self.zoom, self.y + sy / self.zoom

    def visible_tile_bounds(self, tile_size: int, map_width: int, map_height: int) -> tuple[int, int, int, int]:
        """
        Returns (start_x, start_y, end_x, end_y) in rotated tile space — the
        range of tiles that are currently visible on screen.

        The renderer uses this to skip tiles that are off-screen entirely.
        A margin of a few extra tiles prevents pop-in at the screen edges.
        """
        margin = 5
        hw = self.tile_w // 2
        hh = self.tile_h // 2
        origin = self._origin_x()

        # Sample all four viewport corners to find the tile range.
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
            # Apply inverse isometric formula for each corner.
            rtxs.append((rx / hw + wy / hh) / 2)
            rtys.append((wy / hh - rx / hw) / 2)

        # For 90° and 270° rotations, the map's width and height are swapped
        # in rotated tile space because the map is transposed.
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

    # ── Internal helpers ───────────────────────────────────────────────────────

    def clamp(self) -> None:
        """Prevents scrolling outside the map area."""
        vw = self.viewport.width  / self.zoom
        vh = self.viewport.height / self.zoom
        self.x = max(0.0, min(self.x, max(0.0, self.map_pixel_width  - vw)))
        self.y = max(0.0, min(self.y, max(0.0, self.map_pixel_height - vh)))

    def _origin_x(self) -> int:
        """
        Returns the horizontal world-pixel offset so the leftmost diamond
        tip of the map lands at world x = 0.

        In an isometric view the leftmost corner changes with rotation:
          - rotations 0 and 2: the far-left corner is at tile (0, H-1)
          - rotations 1 and 3: the far-left corner is at tile (0, W-1) in rotated space
        """
        hw = self.tile_w // 2
        if self.rotation in (0, 2):
            return (self.map_height - 1) * hw
        else:
            return (self.map_width - 1) * hw

    def _recenter(self) -> None:
        """Scrolls to the centre of the map after a rotation or initialisation."""
        hw = self.tile_w // 2
        hh = self.tile_h // 2
        origin = self._origin_x()

        # The rotated map has swapped dimensions for 90° and 270° rotations.
        if self.rotation in (1, 3):
            rot_w, rot_h = self.map_height, self.map_width
        else:
            rot_w, rot_h = self.map_width, self.map_height

        # World-pixel position of the centre tile in rotated space.
        cx, cy = rot_w / 2.0, rot_h / 2.0
        center_wx = (cx - cy) * hw + origin
        center_wy = (cx + cy) * hh

        # Set scroll so the centre tile appears near the middle of the viewport.
        self.x = max(0.0, center_wx - self.viewport.width  / (2.0 * self.zoom))
        self.y = max(0.0, center_wy - self.viewport.height / (2.8 * self.zoom))
        self.clamp()

    def _apply_rotation(self, tx: float, ty: float) -> tuple[float, float]:
        """
        Transforms map tile (tx, ty) into rotated display coordinates.

        Camera rotation remaps which map corner faces the viewer:
          rotation 0 → tile (0,0)   faces NW (top-left)  — no change
          rotation 1 → tile (W-1,0) faces NW             — map rotated 90° CW
          rotation 2 → tile (W-1,H-1) faces NW           — map rotated 180°
          rotation 3 → tile (0,H-1) faces NW             — map rotated 270° CW

        Each case is a coordinate flip/swap derived from the 2-D rotation matrix
        applied to tile indices.
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
        """Inverse of _apply_rotation: converts rotated display coords back to map tile coords."""
        W, H = self.map_width, self.map_height
        if self.rotation == 0:
            return int(rtx), int(rty)
        elif self.rotation == 1:
            return int(rty), int(H - 1 - rtx)
        elif self.rotation == 2:
            return int(W - 1 - rtx), int(H - 1 - rty)
        else:  # rotation == 3
            return int(W - 1 - rty), int(rtx)
