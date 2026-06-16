"""
game_overlays.py — Full-screen overlay panels used by the Game class.

SaveOverlay  — dimmed slot-picker for save/load operations.
HelpOverlay  — keyboard-shortcut reference sheet toggled by F1.
"""
from __future__ import annotations

import pygame

from .save_load import list_saves
from .settings import NUM_SAVE_SLOTS


class SaveOverlay:
    """
    Full-screen dimmed panel for choosing a save or load slot.

    The overlay blocks all other input while visible. Clicking a slot number
    triggers a save or load; clicking Cancel or pressing Escape dismisses it.
    """

    def __init__(self) -> None:
        self.visible = False
        self.mode    = "save"   # "save" or "load"
        self._slot_rects: list[pygame.Rect] = []
        self._cancel_rect = pygame.Rect(0, 0, 0, 0)
        self._saves: list[dict | None] = [None] * NUM_SAVE_SLOTS
        self._font:    pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

    def open(self, mode: str) -> None:
        """Shows the overlay and refreshes slot metadata from disk."""
        self.visible = True
        self.mode    = mode
        self._saves  = list_saves()

    def close(self) -> None:
        """Hides the overlay without taking any action."""
        self.visible = False

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font    = pygame.font.SysFont("Segoe UI", 18, bold=True)
            self._font_sm = pygame.font.SysFont("Segoe UI", 15)

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        W, H = surface.get_size()

        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        surface.blit(dim, (0, 0))

        panel_w = min(520, W - 40)
        slot_h  = 54
        panel_h = 60 + NUM_SAVE_SLOTS * (slot_h + 8) + 52
        panel   = pygame.Rect(W // 2 - panel_w // 2, H // 2 - panel_h // 2, panel_w, panel_h)
        pygame.draw.rect(surface, (18, 24, 32), panel, border_radius=10)
        pygame.draw.rect(surface, (55, 90, 130), panel, width=2, border_radius=10)

        title = "Save Game — Choose a Slot" if self.mode == "save" else "Load Game — Choose a Slot"
        t = self._font.render(title, True, (235, 239, 242))
        surface.blit(t, (panel.centerx - t.get_width() // 2, panel.y + 16))

        mouse = pygame.mouse.get_pos()
        self._slot_rects = []
        for i, meta in enumerate(self._saves):
            slot_rect = pygame.Rect(panel.x + 18, panel.y + 52 + i * (slot_h + 8),
                                    panel_w - 36, slot_h)
            self._slot_rects.append(slot_rect)

            is_empty  = meta is None
            clickable = not is_empty or self.mode == "save"
            hovered   = clickable and slot_rect.collidepoint(mouse)

            if is_empty:
                bg        = (34, 46, 60) if hovered else (24, 34, 44)
                border    = (40, 58, 78)
                label_col = (90, 110, 130)
            else:
                bg        = (40, 56, 76) if hovered else (28, 38, 52)
                border    = (90, 130, 180) if hovered else (55, 82, 112)
                label_col = (130, 155, 180)

            pygame.draw.rect(surface, bg,     slot_rect, border_radius=6)
            pygame.draw.rect(surface, border, slot_rect, width=1, border_radius=6)

            sl = self._font_sm.render(f"Slot {i + 1}", True, label_col)
            surface.blit(sl, (slot_rect.x + 14, slot_rect.centery - sl.get_height() // 2))

            if is_empty:
                et = self._font_sm.render("— Empty —", True, (70, 88, 105))
                surface.blit(et, (slot_rect.x + 88, slot_rect.centery - et.get_height() // 2))
            else:
                pt = self._font_sm.render(
                    f"Pop {meta['population']:,}  ${meta['money']:,}", True, (220, 232, 240))
                surface.blit(pt, (slot_rect.x + 88, slot_rect.y + 10))
                dt = self._font_sm.render(
                    f"Year {meta['year']}  Month {meta['month']}  {meta['map_size']} map",
                    True, (140, 162, 182))
                surface.blit(dt, (slot_rect.x + 88, slot_rect.y + 30))

        cancel_w = 130
        self._cancel_rect = pygame.Rect(panel.centerx - cancel_w // 2,
                                        panel.bottom - 44, cancel_w, 30)
        c_hov = self._cancel_rect.collidepoint(mouse)
        pygame.draw.rect(surface,
                         (48, 60, 76) if c_hov else (36, 46, 58),
                         self._cancel_rect, border_radius=5)
        pygame.draw.rect(surface, (60, 76, 96), self._cancel_rect, width=1, border_radius=5)
        ct = self._font_sm.render("Cancel  [Esc]", True, (200, 212, 224))
        surface.blit(ct, (self._cancel_rect.centerx - ct.get_width() // 2,
                          self._cancel_rect.centery - ct.get_height() // 2))

    def handle_click(self, pos: tuple[int, int]) -> int | str | None:
        """Returns slot number (1-N), 'cancel', or None on a left-click."""
        if self._cancel_rect.collidepoint(pos):
            return "cancel"
        for i, rect in enumerate(self._slot_rects):
            if rect.collidepoint(pos):
                if self.mode == "load" and self._saves[i] is None:
                    return None
                return i + 1
        return None


class HelpOverlay:
    """
    Full-screen overlay showing keyboard shortcuts and gameplay tips.
    Triggered by F1; closed by F1 or Escape.
    """

    _SECTIONS = [
        ("Camera & Speed", [
            ("WASD / Arrows", "Pan the map"),
            ("Scroll wheel",  "Zoom in / out"),
            ("Middle drag",   "Pan the map"),
            ("Q / E",         "Rotate camera"),
            ("V",             "Cycle view mode (Power/Water/Fire/Police/Terrain/Traffic/Land Value/Pollution)"),
            ("[ / ]",         "Slower / faster simulation speed"),
            ("Space",         "Pause / resume"),
        ]),
        ("Building", [
            ("Left click",  "Place active tool"),
            ("Right click", "Bulldoze tile"),
            ("Drag",        "Paint multiple tiles"),
            ("Ctrl+Z",      "Undo last action"),
            ("1",  "Residential zone"),
            ("2",  "Commercial zone"),
            ("3",  "Industrial zone"),
            ("4",  "Road"),
            ("5",  "Power line"),
            ("6",  "Water pipe"),
            ("7",  "Power plant"),
            ("8",  "Water tower"),
            ("9",  "Bulldoze"),
        ]),
        ("Other", [
            ("F5",  "Save game"),
            ("F9",  "Load game"),
            ("F11", "Toggle fullscreen"),
            ("F1",  "This help screen"),
            ("Esc", "Close overlay / quit to menu"),
        ]),
    ]

    def __init__(self) -> None:
        self.visible   = False
        self._font:    pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

    def open(self) -> None:
        self.visible = True

    def close(self) -> None:
        self.visible = False

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font    = pygame.font.SysFont("Segoe UI", 17, bold=True)
            self._font_sm = pygame.font.SysFont("Segoe UI", 14)

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        W, H = surface.get_size()

        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        surface.blit(dim, (0, 0))

        panel_w = min(680, W - 40)
        panel_h = min(540, H - 40)
        panel   = pygame.Rect(W // 2 - panel_w // 2, H // 2 - panel_h // 2, panel_w, panel_h)
        pygame.draw.rect(surface, (18, 24, 32), panel, border_radius=10)
        pygame.draw.rect(surface, (55, 90, 130), panel, width=2, border_radius=10)

        title = self._font.render(
            "Help — Keyboard Shortcuts  [F1 or Esc to close]", True, (235, 239, 242))
        surface.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 14))

        col_w = (panel_w - 40) // 2
        cx    = [panel.x + 16, panel.x + 16 + col_w + 8]
        cy    = [panel.y + 50, panel.y + 50]

        for i, (heading, items) in enumerate(self._SECTIONS):
            col = 0 if i < 2 else 1
            x   = cx[col]
            y   = cy[col]

            hdr = self._font.render(heading, True, (140, 190, 240))
            surface.blit(hdr, (x, y))
            cy[col] += 22

            for key, desc in items:
                key_s  = self._font_sm.render(key,  True, (220, 232, 240))
                desc_s = self._font_sm.render(desc, True, (160, 175, 185))
                surface.blit(key_s,  (x,       cy[col]))
                surface.blit(desc_s, (x + 120, cy[col]))
                cy[col] += 18

            cy[col] += 8
