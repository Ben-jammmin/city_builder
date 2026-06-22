"""
game_overlays.py — Full-screen overlay panels used by the Game class.

SaveOverlay  — dimmed slot-picker for save/load operations.
HelpOverlay  — keyboard-shortcut reference sheet toggled by F1.
"""
from __future__ import annotations

import math
import pygame

from .save_load import list_saves, slot_metadata
from .settings import BOND_OPTIONS, NUM_SAVE_SLOTS, ORDINANCES


class SaveOverlay:
    """
    Full-screen dimmed panel for choosing a save or load slot.

    In load mode the autosave (slot 0) appears at the top as a special entry
    so players always have something to load even without a manual save.
    Slot numbers returned: 0 = autosave, 1-N = manual slots.
    """

    def __init__(self) -> None:
        self.visible  = False
        self.mode     = "save"      # "save" or "load"
        # _entries: list of (slot_number, meta_or_None, label, is_autosave)
        self._entries: list[tuple[int, dict | None, str, bool]] = []
        self._slot_rects:  list[pygame.Rect] = []
        self._cancel_rect  = pygame.Rect(0, 0, 0, 0)
        self._font:    pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

    def open(self, mode: str) -> None:
        self.visible = True
        self.mode    = mode
        self._refresh()

    def close(self) -> None:
        self.visible = False

    def _refresh(self) -> None:
        """Rebuilds the entry list from disk. In load mode, prepends the autosave."""
        manual = list_saves()                        # slots 1-N
        self._entries = []
        if self.mode == "load":
            auto_meta = slot_metadata(0)             # slot 0 = autosave
            if auto_meta is not None:
                self._entries.append((0, auto_meta, "Autosave", True))
        for i, meta in enumerate(manual):
            self._entries.append((i + 1, meta, f"Slot {i + 1}", False))

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font    = pygame.font.SysFont("Segoe UI", 18, bold=True)
            self._font_sm = pygame.font.SysFont("Segoe UI", 15)

    def draw(self, surface: pygame.Surface) -> None:
        self._ensure_fonts()
        W, H = surface.get_size()

        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 175))
        surface.blit(dim, (0, 0))

        slot_h  = 56
        n_slots = len(self._entries)
        panel_w = min(560, W - 40)
        panel_h = 58 + n_slots * (slot_h + 8) + 52
        panel   = pygame.Rect(W // 2 - panel_w // 2, H // 2 - panel_h // 2, panel_w, panel_h)
        pygame.draw.rect(surface, (14, 20, 30), panel, border_radius=12)
        pygame.draw.rect(surface, (55, 90, 130), panel, width=2, border_radius=12)

        title = "Save Game — Choose a Slot" if self.mode == "save" else "Load Game — Choose a Save"
        t = self._font.render(title, True, (235, 239, 242))
        surface.blit(t, (panel.centerx - t.get_width() // 2, panel.y + 16))

        mouse = pygame.mouse.get_pos()
        self._slot_rects = []

        for entry_i, (slot_num, meta, label, is_auto) in enumerate(self._entries):
            row_y     = panel.y + 52 + entry_i * (slot_h + 8)
            slot_rect = pygame.Rect(panel.x + 18, row_y, panel_w - 36, slot_h)
            self._slot_rects.append(slot_rect)

            is_empty  = meta is None
            clickable = (not is_empty) or self.mode == "save"
            hovered   = clickable and slot_rect.collidepoint(mouse)

            if is_auto:
                # Autosave row gets a distinct teal accent.
                bg        = (28, 52, 52) if hovered else (20, 38, 40)
                border    = (60, 160, 155) if hovered else (45, 110, 108)
                lbl_col   = (80, 210, 200)
            elif is_empty:
                bg        = (34, 46, 60) if hovered else (22, 32, 44)
                border    = (42, 60, 80)
                lbl_col   = (80, 100, 120)
            else:
                bg        = (38, 56, 80) if hovered else (26, 38, 54)
                border    = (90, 135, 185) if hovered else (52, 80, 115)
                lbl_col   = (130, 160, 195)

            pygame.draw.rect(surface, bg,     slot_rect, border_radius=7)
            pygame.draw.rect(surface, border, slot_rect, width=1, border_radius=7)

            # Slot label (left column).
            sl = self._font_sm.render(label, True, lbl_col)
            surface.blit(sl, (slot_rect.x + 14, slot_rect.centery - sl.get_height() // 2))

            # Save content (right area).
            content_x = slot_rect.x + 108
            if is_empty:
                et = self._font_sm.render("— Empty —", True, (55, 75, 95))
                surface.blit(et, (content_x, slot_rect.centery - et.get_height() // 2))
            else:
                city_title = "Outpost"
                # Infer milestone title from population if available.
                pop = meta.get("population", 0)
                for thresh, title_name in ((100, "Hamlet"), (500, "Village"), (2000, "Town"),
                                           (5000, "City"), (20000, "Large City"),
                                           (50000, "Metropolis"), (100000, "Megalopolis")):
                    if pop >= thresh:
                        city_title = title_name
                city_s = self._font.render(city_title, True, (210, 228, 245))
                surface.blit(city_s, (content_x, slot_rect.y + 8))

                detail = (f"Pop {meta['population']:,}   "
                          f"${meta['money']:,}   "
                          f"Y{meta['year']} M{meta['month']}   "
                          f"{meta['map_size']} map")
                dt = self._font_sm.render(detail, True, (130, 155, 180))
                surface.blit(dt, (content_x, slot_rect.y + 32))

            # "Click to load" hint on hover.
            if hovered and not is_empty:
                hint_s = self._font_sm.render(
                    "← Load" if self.mode == "load" else "← Overwrite",
                    True, (180, 210, 240))
                surface.blit(hint_s, (slot_rect.right - hint_s.get_width() - 12,
                                      slot_rect.centery - hint_s.get_height() // 2))

        # Cancel button.
        cw = 130
        self._cancel_rect = pygame.Rect(panel.centerx - cw // 2, panel.bottom - 44, cw, 30)
        c_hov = self._cancel_rect.collidepoint(mouse)
        pygame.draw.rect(surface, (48, 60, 78) if c_hov else (34, 44, 58), self._cancel_rect, border_radius=6)
        pygame.draw.rect(surface, (60, 78, 100), self._cancel_rect, width=1, border_radius=6)
        ct = self._font_sm.render("Cancel  [Esc]", True, (195, 210, 226))
        surface.blit(ct, (self._cancel_rect.centerx - ct.get_width() // 2,
                          self._cancel_rect.centery - ct.get_height() // 2))

    def handle_click(self, pos: tuple[int, int]) -> int | str | None:
        """Returns slot number (0=autosave, 1-N=manual), 'cancel', or None."""
        if self._cancel_rect.collidepoint(pos):
            return "cancel"
        for i, rect in enumerate(self._slot_rects):
            if rect.collidepoint(pos):
                slot_num, meta, _, _ = self._entries[i]
                if self.mode == "load" and meta is None:
                    return None        # empty slot in load mode — ignore
                return slot_num
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
            ("Home",          "Re-center camera on map"),
            ("V",             "Cycle view mode (Power/Water/Fire/Police/Terrain/Traffic/Land Value/Pollution)"),
            ("N",             "Toggle day/night cycle"),
            ("Tab",           "Cycle to next menu tab"),
            ("[ / ]",         "Slower / faster simulation speed"),
            ("Space",         "Pause / resume"),
        ]),
        ("Building", [
            ("Left click",       "Place active tool"),
            ("Shift + drag",     "Fill rectangle with active tool"),
            ("Right click/drag", "Bulldoze tiles"),
            ("Ctrl+Z",           "Undo last action"),
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
            ("F5",      "Save game (manual)"),
            ("F9",      "Load game"),
            ("Auto",    "Game autosaves every 2 in-game years to slot 0"),
            ("A",       "City Analytics — graphs for population, budget, demand"),
            ("B",       "Open bond / loan menu (finance city expansion)"),
            ("O",       "City Ordinances — enact or repeal policies"),
            ("F11",     "Toggle fullscreen"),
            ("F1",      "This help screen"),
            ("Esc",     "Close overlay / quit to menu"),
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


class BondOverlay:
    """
    Full-screen dimmed overlay for issuing municipal bonds.

    Shows the three preset bond options plus a summary of any currently
    active bonds.  Opened with the B key; closed with B, Escape, or Cancel.
    """

    def __init__(self) -> None:
        self.visible = False
        self._option_rects: list[pygame.Rect] = []
        self._cancel_rect = pygame.Rect(0, 0, 0, 0)
        self._font:    pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

    def open(self) -> None:
        self.visible = True

    def close(self) -> None:
        self.visible = False

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font    = pygame.font.SysFont("Segoe UI", 18, bold=True)
            self._font_sm = pygame.font.SysFont("Segoe UI", 15)

    def draw(self, surface: pygame.Surface, stats) -> None:
        self._ensure_fonts()
        W, H = surface.get_size()

        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        surface.blit(dim, (0, 0))

        panel_w = min(540, W - 40)
        opt_h   = 58
        active_section_h = 0
        bonds = getattr(stats, "bonds", [])
        if bonds:
            active_section_h = 14 + len(bonds) * 18 + 8

        panel_h = 56 + active_section_h + len(BOND_OPTIONS) * (opt_h + 8) + 52
        panel   = pygame.Rect(W // 2 - panel_w // 2, H // 2 - panel_h // 2, panel_w, panel_h)
        pygame.draw.rect(surface, (18, 24, 32), panel, border_radius=10)
        pygame.draw.rect(surface, (55, 90, 130), panel, width=2, border_radius=10)

        title = self._font.render("Municipal Bonds  [B or Esc to close]", True, (235, 239, 242))
        surface.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 14))

        row_y = panel.y + 44
        mouse = pygame.mouse.get_pos()

        # ── Active bonds summary ───────────────────────────────────────────────
        if bonds:
            total_debt  = sum(b["monthly_payment"] * b["months_left"] for b in bonds)
            monthly_pay = sum(b["monthly_payment"] for b in bonds)
            hdr = self._font_sm.render(
                f"Active bonds — ${monthly_pay:,}/mo  ·  ${total_debt:,} remaining total",
                True, (220, 165, 55))
            surface.blit(hdr, (panel.x + 18, row_y))
            row_y += 18
            for b in bonds:
                remaining_cost = b["monthly_payment"] * b["months_left"]
                ln = self._font_sm.render(
                    f"  ${b['amount']:,} bond  ·  {b['months_left']} months left  ·  ${remaining_cost:,} remaining",
                    True, (160, 175, 185))
                surface.blit(ln, (panel.x + 18, row_y))
                row_y += 18
            row_y += 8

        # ── Bond options ───────────────────────────────────────────────────────
        self._option_rects = []
        for opt in BOND_OPTIONS:
            total_cost  = opt["monthly_payment"] * opt["months"]
            interest    = total_cost - opt["amount"]
            opt_rect    = pygame.Rect(panel.x + 18, row_y, panel_w - 36, opt_h)
            self._option_rects.append(opt_rect)

            hovered = opt_rect.collidepoint(mouse)
            bg      = (38, 54, 72) if hovered else (28, 38, 52)
            border  = (90, 135, 190) if hovered else (55, 82, 112)
            pygame.draw.rect(surface, bg,     opt_rect, border_radius=6)
            pygame.draw.rect(surface, border, opt_rect, width=1, border_radius=6)

            name_s = self._font.render(opt["name"], True, (220, 235, 245))
            surface.blit(name_s, (opt_rect.x + 14, opt_rect.y + 8))

            cash_s = self._font_sm.render(f"+${opt['amount']:,} now", True, (118, 213, 140))
            surface.blit(cash_s, (opt_rect.x + 14, opt_rect.y + 32))

            pay_s = self._font_sm.render(
                f"${opt['monthly_payment']:,}/mo  ×  {opt['months']} months  =  ${total_cost:,} total  (+${interest:,} interest)",
                True, (160, 175, 185))
            surface.blit(pay_s, (opt_rect.x + 130, opt_rect.y + 32))

            row_y += opt_h + 8

        # ── Cancel button ──────────────────────────────────────────────────────
        cancel_w = 130
        self._cancel_rect = pygame.Rect(panel.centerx - cancel_w // 2, panel.bottom - 44, cancel_w, 30)
        c_hov = self._cancel_rect.collidepoint(mouse)
        pygame.draw.rect(surface, (48, 60, 76) if c_hov else (36, 46, 58),
                         self._cancel_rect, border_radius=5)
        pygame.draw.rect(surface, (60, 76, 96), self._cancel_rect, width=1, border_radius=5)
        ct = self._font_sm.render("Cancel  [Esc / B]", True, (200, 212, 224))
        surface.blit(ct, (self._cancel_rect.centerx - ct.get_width() // 2,
                          self._cancel_rect.centery - ct.get_height() // 2))

    def handle_click(self, pos: tuple[int, int]) -> int | str | None:
        """Returns a bond option index (0-N), 'cancel', or None on no match."""
        if self._cancel_rect.collidepoint(pos):
            return "cancel"
        for i, rect in enumerate(self._option_rects):
            if rect.collidepoint(pos):
                return i
        return None


class OrdinanceOverlay:
    """
    Full-screen dimmed overlay for toggling city ordinances.

    Shows all 5 policy rows with their monthly cost, effects, and an
    Active/Enable toggle button.  Opened with the O key.
    """

    def __init__(self) -> None:
        self.visible = False
        self._toggle_rects: list[tuple[pygame.Rect, str]] = []
        self._close_rect = pygame.Rect(0, 0, 0, 0)
        self._font:    pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None

    def open(self) -> None:
        self.visible = True

    def close(self) -> None:
        self.visible = False

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font    = pygame.font.SysFont("Segoe UI", 18, bold=True)
            self._font_sm = pygame.font.SysFont("Segoe UI", 15)

    def draw(self, surface: pygame.Surface, stats) -> None:
        self._ensure_fonts()
        W, H = surface.get_size()

        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 170))
        surface.blit(dim, (0, 0))

        panel_w = min(600, W - 40)
        row_h   = 62
        panel_h = 58 + len(ORDINANCES) * (row_h + 8) + 52
        panel   = pygame.Rect(W // 2 - panel_w // 2, H // 2 - panel_h // 2, panel_w, panel_h)
        pygame.draw.rect(surface, (18, 24, 32), panel, border_radius=10)
        pygame.draw.rect(surface, (75, 132, 208), panel, width=2, border_radius=10)

        active_ords = getattr(stats, "active_ordinances", [])
        active_cost = sum(o["monthly_cost"] for o in ORDINANCES if o["id"] in active_ords)

        if active_cost > 0:
            title_str = f"City Ordinances  —  Active policies: ${active_cost:,}/mo  [O / Esc]"
        else:
            title_str = "City Ordinances  [O or Esc to close]"
        title = self._font.render(title_str, True, (235, 239, 242))
        surface.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 14))

        mouse  = pygame.mouse.get_pos()
        self._toggle_rects = []
        row_y  = panel.y + 46

        for ord_def in ORDINANCES:
            is_active = ord_def["id"] in active_ords
            row_rect  = pygame.Rect(panel.x + 18, row_y, panel_w - 36, row_h)

            bg     = (30, 50, 34) if is_active else (28, 38, 52)
            border = (80, 190, 100) if is_active else (55, 82, 112)
            pygame.draw.rect(surface, bg,     row_rect, border_radius=6)
            pygame.draw.rect(surface, border, row_rect, width=1, border_radius=6)

            name_color = (118, 230, 140) if is_active else (220, 235, 245)
            name_s = self._font.render(ord_def["name"], True, name_color)
            surface.blit(name_s, (row_rect.x + 14, row_rect.y + 8))

            cost_s = self._font_sm.render(f"${ord_def['monthly_cost']:,}/mo", True, (200, 165, 60))
            surface.blit(cost_s, (row_rect.x + 14, row_rect.y + 38))

            # Build effects summary string.
            fx     = ord_def.get("effects", {})
            parts  = []
            if "res_demand" in fx:
                parts.append(f"Res {'+' if fx['res_demand'] > 0 else ''}{fx['res_demand']}")
            if "com_demand" in fx:
                parts.append(f"Com {'+' if fx['com_demand'] > 0 else ''}{fx['com_demand']}")
            if "ind_demand" in fx:
                parts.append(f"Ind {'+' if fx['ind_demand'] > 0 else ''}{fx['ind_demand']}")
            if "crime_reduction" in fx:
                parts.append(f"Crime -{fx['crime_reduction']}")
            if "congestion_reduction" in fx:
                parts.append(f"Traffic -{int(fx['congestion_reduction'] * 100)}%")
            if "park_absorption_bonus" in fx:
                parts.append("Park absorb +50%")
            appr = ord_def.get("approval_bonus", 0)
            if appr:
                parts.append(f"Appr +{appr}%")

            eff_s = self._font_sm.render("  ·  ".join(parts), True, (160, 185, 210))
            surface.blit(eff_s, (row_rect.x + 140, row_rect.y + 38))

            # Toggle button (right-aligned in row).
            btn_w    = 64
            btn_rect = pygame.Rect(row_rect.right - btn_w - 10,
                                   row_rect.centery - 14, btn_w, 28)
            self._toggle_rects.append((btn_rect, ord_def["id"]))
            btn_hov  = btn_rect.collidepoint(mouse)
            if is_active:
                btn_bg     = (55, 105, 65) if btn_hov else (40, 80, 50)
                btn_border = (100, 200, 120)
                btn_label  = "Active"
                btn_color  = (130, 240, 160)
            else:
                btn_bg     = (50, 62, 80) if btn_hov else (36, 46, 60)
                btn_border = (60, 80, 105)
                btn_label  = "Enable"
                btn_color  = (185, 200, 220)
            pygame.draw.rect(surface, btn_bg,     btn_rect, border_radius=5)
            pygame.draw.rect(surface, btn_border, btn_rect, width=1, border_radius=5)
            bl = self._font_sm.render(btn_label, True, btn_color)
            surface.blit(bl, (btn_rect.centerx - bl.get_width() // 2,
                               btn_rect.centery - bl.get_height() // 2))

            row_y += row_h + 8

        # Close button.
        close_w = 140
        self._close_rect = pygame.Rect(panel.centerx - close_w // 2,
                                       panel.bottom - 44, close_w, 30)
        c_hov = self._close_rect.collidepoint(mouse)
        pygame.draw.rect(surface,
                         (48, 60, 76) if c_hov else (36, 46, 58),
                         self._close_rect, border_radius=5)
        pygame.draw.rect(surface, (60, 76, 96), self._close_rect, width=1, border_radius=5)
        ct = self._font_sm.render("Close  [O / Esc]", True, (200, 212, 224))
        surface.blit(ct, (self._close_rect.centerx - ct.get_width() // 2,
                          self._close_rect.centery - ct.get_height() // 2))

    def handle_click(self, pos: tuple[int, int]) -> str | None:
        """Returns ordinance id to toggle, 'close', or None on no match."""
        if self._close_rect.collidepoint(pos):
            return "close"
        for btn_rect, ord_id in self._toggle_rects:
            if btn_rect.collidepoint(pos):
                return ord_id
        return None


class AnalyticsOverlay:
    """
    Full-screen analytics dashboard showing historical charts and city metrics.

    Four panels:
      - Population trend (24-month line chart)
      - Budget (12-month revenue vs expenses grouped bars)
      - Demand trends (12-month R/C/I lines)
      - City snapshot (all key metrics as labelled bars)

    Opened with the A key; closed with A or Escape.
    """

    _RES_COL = (118, 213, 140)
    _COM_COL = (255, 198, 80)
    _IND_COL = (220, 100, 80)
    _REV_COL = (80, 190, 105)
    _EXP_COL = (200, 85, 65)
    _POP_COL = (100, 175, 255)

    def __init__(self) -> None:
        self.visible = False
        self._close_rect = pygame.Rect(0, 0, 0, 0)
        self._font:    pygame.font.Font | None = None
        self._font_sm: pygame.font.Font | None = None
        self._font_xs: pygame.font.Font | None = None

    def open(self) -> None:
        self.visible = True

    def close(self) -> None:
        self.visible = False

    def _ensure_fonts(self) -> None:
        if self._font is None:
            self._font    = pygame.font.SysFont("Segoe UI", 18, bold=True)
            self._font_sm = pygame.font.SysFont("Segoe UI", 14, bold=True)
            self._font_xs = pygame.font.SysFont("Segoe UI", 12)

    # ── Top-level draw ─────────────────────────────────────────────────────────

    def draw(self, surface: pygame.Surface, stats) -> None:
        self._ensure_fonts()
        W, H = surface.get_size()

        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 185))
        surface.blit(dim, (0, 0))

        panel_w = min(940, W - 32)
        panel_h = min(610, H - 32)
        panel   = pygame.Rect(W // 2 - panel_w // 2, H // 2 - panel_h // 2, panel_w, panel_h)
        pygame.draw.rect(surface, (12, 18, 26), panel, border_radius=12)
        pygame.draw.rect(surface, (50, 85, 125), panel, width=2, border_radius=12)

        title = self._font.render("City Analytics  [A or Esc to close]", True, (235, 239, 242))
        surface.blit(title, (panel.centerx - title.get_width() // 2, panel.y + 12))

        pad     = 12
        inner_y = panel.y + 42
        half_w  = (panel_w - pad * 3) // 2
        ch      = (panel_h - 42 - pad * 3 - 42) // 2   # height of each chart cell

        # Top-left: population
        self._draw_line_chart(
            surface,
            pygame.Rect(panel.x + pad, inner_y, half_w, ch),
            "Population  (24 months)",
            [stats.population_history[-24:]],
            [self._POP_COL],
            ["Pop"],
            fmt=lambda v: f"{int(v):,}",
        )

        # Top-right: budget
        self._draw_budget_chart(
            surface,
            pygame.Rect(panel.x + pad * 2 + half_w, inner_y, half_w, ch),
            stats.budget_history[-12:],
        )

        inner_y += ch + pad

        # Bottom-left: demand trends
        demand = list(stats.demand_history[-12:])
        self._draw_line_chart(
            surface,
            pygame.Rect(panel.x + pad, inner_y, half_w, ch),
            "Demand Trends  (12 months)",
            [
                [d[0] for d in demand],
                [d[1] for d in demand],
                [d[2] for d in demand],
            ],
            [self._RES_COL, self._COM_COL, self._IND_COL],
            ["Res", "Com", "Ind"],
            y_range=(0, 100),
        )

        # Bottom-right: city snapshot
        self._draw_snapshot(
            surface,
            pygame.Rect(panel.x + pad * 2 + half_w, inner_y, half_w, ch),
            stats,
        )

        # Close button
        cw = 140
        self._close_rect = pygame.Rect(panel.centerx - cw // 2, panel.bottom - 36, cw, 28)
        mouse = pygame.mouse.get_pos()
        hov   = self._close_rect.collidepoint(mouse)
        pygame.draw.rect(surface, (50, 62, 80) if hov else (36, 46, 58), self._close_rect, border_radius=5)
        pygame.draw.rect(surface, (62, 80, 102), self._close_rect, width=1, border_radius=5)
        ct = self._font_xs.render("Close  [A / Esc]", True, (200, 215, 228))
        surface.blit(ct, (self._close_rect.centerx - ct.get_width() // 2,
                          self._close_rect.centery - ct.get_height() // 2))

    # ── Chart helpers ──────────────────────────────────────────────────────────

    def _chart_bg(self, surface: pygame.Surface, rect: pygame.Rect, title: str) -> tuple:
        """Draws chart background, title, and grid lines. Returns (gx, gy, gw, gh) inner plot area."""
        pygame.draw.rect(surface, (18, 26, 36), rect, border_radius=8)
        pygame.draw.rect(surface, (38, 56, 78), rect, width=1, border_radius=8)
        t = self._font_sm.render(title, True, (130, 170, 210))
        surface.blit(t, (rect.x + 8, rect.y + 6))
        gx = rect.x + 8
        gy = rect.y + 26
        gw = rect.width - 16
        gh = rect.height - 42
        # horizontal grid lines
        for i in range(4):
            ly = gy + int(gh * i / 3)
            pygame.draw.line(surface, (28, 40, 54), (gx, ly), (gx + gw, ly))
        return gx, gy, gw, gh

    def _draw_line_chart(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        title: str,
        series: list,          # list of lists, one per data line
        colors: list,
        labels: list,
        fmt=None,
        y_range: tuple | None = None,
    ) -> None:
        gx, gy, gw, gh = self._chart_bg(surface, rect, title)
        all_pts = [v for s in series for v in s if s]
        if not all_pts:
            nd = self._font_xs.render("No data yet — play a few months", True, (60, 80, 100))
            surface.blit(nd, (rect.centerx - nd.get_width() // 2, rect.centery - 6))
            return

        vmin = y_range[0] if y_range else min(all_pts)
        vmax = y_range[1] if y_range else max(all_pts)
        vrange = max(1, vmax - vmin)

        def sx(i, n): return gx + int(i / max(1, n - 1) * gw)
        def sy(v):    return gy + gh - 4 - int((v - vmin) / vrange * (gh - 8))

        for s_data, col in zip(series, colors):
            if not s_data:
                continue
            n = len(s_data)
            pts = [(sx(i, n), sy(v)) for i, v in enumerate(s_data)]
            if len(pts) >= 2:
                pygame.draw.lines(surface, col, False, pts, 2)
            if pts:
                pygame.draw.circle(surface, col, pts[-1], 3)
                # Label the last value
                lbl = (fmt(s_data[-1]) if fmt else f"{int(s_data[-1])}")
                ls = self._font_xs.render(lbl, True, col)
                lx = min(pts[-1][0] + 4, rect.right - ls.get_width() - 4)
                surface.blit(ls, (lx, pts[-1][1] - ls.get_height() // 2))

        # Y-axis min/max labels
        for v, anchor_y in ((vmin, gy + gh - 4), (vmax, gy + 2)):
            lbl = (fmt(v) if fmt else f"{int(v)}")
            ls = self._font_xs.render(lbl, True, (55, 75, 95))
            surface.blit(ls, (gx, anchor_y - ls.get_height()))

        # Legend
        for i, (label, col) in enumerate(zip(labels, colors)):
            lx = gx + i * 52
            ly = gy + gh + 6
            pygame.draw.line(surface, col, (lx, ly + 6), (lx + 14, ly + 6), 2)
            ls = self._font_xs.render(label, True, col)
            surface.blit(ls, (lx + 17, ly))

    def _draw_budget_chart(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        history: list,
    ) -> None:
        gx, gy, gw, gh = self._chart_bg(surface, rect, "Budget  (12 months)  — Rev vs Exp")
        if not history:
            nd = self._font_xs.render("No data yet — play a few months", True, (60, 80, 100))
            surface.blit(nd, (rect.centerx - nd.get_width() // 2, rect.centery - 6))
            return

        n    = len(history)
        vmax = max(max(r, e) for r, e in history) or 1
        sw   = gw // n
        bw   = max(2, sw // 2 - 1)

        for i, (rev, exp) in enumerate(history):
            bx  = gx + i * sw
            rh  = max(2, int(rev / vmax * (gh - 4)))
            eh  = max(2, int(exp / vmax * (gh - 4)))
            pygame.draw.rect(surface, self._REV_COL,
                             (bx + 1, gy + gh - rh - 2, bw, rh), border_radius=2)
            pygame.draw.rect(surface, self._EXP_COL,
                             (bx + bw + 2, gy + gh - eh - 2, bw, eh), border_radius=2)

        # Net profit line overlay
        net_vals = [r - e for r, e in history]
        abs_max  = max(abs(v) for v in net_vals) or 1
        mid_y    = gy + gh // 2
        line_pts = []
        for i, net in enumerate(net_vals):
            px = gx + i * sw + sw // 2
            py = mid_y - int(net / abs_max * (gh // 2 - 4))
            line_pts.append((px, py))
        if len(line_pts) >= 2:
            pygame.draw.lines(surface, (220, 215, 80), False, line_pts, 1)

        # Legend
        pygame.draw.rect(surface, self._REV_COL, (gx, gy + gh + 6, 10, 8), border_radius=1)
        r_lbl = self._font_xs.render("Revenue", True, self._REV_COL)
        surface.blit(r_lbl, (gx + 13, gy + gh + 4))
        pygame.draw.rect(surface, self._EXP_COL, (gx + 76, gy + gh + 6, 10, 8), border_radius=1)
        e_lbl = self._font_xs.render("Expenses", True, self._EXP_COL)
        surface.blit(e_lbl, (gx + 89, gy + gh + 4))
        pygame.draw.line(surface, (220, 215, 80), (gx + 158, gy + gh + 10), (gx + 172, gy + gh + 10), 1)
        n_lbl = self._font_xs.render("Net", True, (220, 215, 80))
        surface.blit(n_lbl, (gx + 175, gy + gh + 4))

    def _draw_snapshot(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        stats,
    ) -> None:
        pygame.draw.rect(surface, (18, 26, 36), rect, border_radius=8)
        pygame.draw.rect(surface, (38, 56, 78), rect, width=1, border_radius=8)
        t = self._font_sm.render("City Snapshot", True, (130, 170, 210))
        surface.blit(t, (rect.x + 8, rect.y + 6))

        grade_col = ((80, 200, 110) if stats.city_score >= 70
                     else ((230, 155, 50) if stats.city_score >= 50 else (210, 70, 70)))
        gs = self._font.render(f"{stats.city_grade}  ({stats.city_score}/100)", True, grade_col)
        surface.blit(gs, (rect.right - gs.get_width() - 10, rect.y + 5))

        rows = [
            ("Approval",   stats.approval_rating,              100, True),
            ("Power",      stats.power_satisfaction,           100, True),
            ("Water",      stats.water_satisfaction,           100, True),
            ("Fire Cover", stats.fire_coverage_percent,        100, True),
            ("Police",     stats.police_coverage_percent,      100, True),
            ("Education",  stats.education_coverage_percent,   100, True),
            ("Health",     stats.health_coverage_percent,      100, True),
            ("Crime Risk", stats.average_crime_risk,           100, False),
            ("Fire Risk",  stats.average_fire_risk,            100, False),
        ]

        row_h  = (rect.height - 30) / len(rows)
        bar_x  = rect.x + 90
        bar_w  = rect.width - 100
        bar_h  = 8

        for i, (label, val, vmax, high_good) in enumerate(rows):
            ry = rect.y + 26 + int(i * row_h)
            ls = self._font_xs.render(label, True, (145, 168, 195))
            surface.blit(ls, (rect.x + 8, ry + 1))
            frac = min(1.0, max(0.0, val / vmax))
            if high_good:
                col = (80, 190, 105) if frac >= 0.6 else ((230, 150, 50) if frac >= 0.35 else (210, 70, 70))
            else:
                col = (210, 70, 70) if frac >= 0.6 else ((230, 150, 50) if frac >= 0.35 else (80, 190, 105))
            pygame.draw.rect(surface, (26, 38, 50), (bar_x, ry + 2, bar_w, bar_h), border_radius=3)
            if frac > 0:
                pygame.draw.rect(surface, col, (bar_x, ry + 2, int(bar_w * frac), bar_h), border_radius=3)
            vs = self._font_xs.render(f"{val}%", True, col)
            surface.blit(vs, (bar_x + bar_w + 4, ry))

    def handle_click(self, pos: tuple[int, int]) -> str | None:
        if self._close_rect.collidepoint(pos):
            return "close"
        return None
