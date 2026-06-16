"""Main menu system — shown before and after the game."""
from __future__ import annotations

import random
import sys
from pathlib import Path

import pygame

from .menu_config import (
    DIFFICULTY_MONEY, MAP_SIZES, SIM_SPEED_SECONDS, TERRAIN_STYLES, GameConfig,
)
from .settings import SAVE_FILE, WINDOW_HEIGHT, WINDOW_WIDTH

# ── Colours (match game's dark sidebar palette) ───────────────────────────────
_BG      = (14, 18, 24)
_PANEL   = (24, 30, 38)
_TEXT    = (235, 239, 242)
_MUTED   = (140, 155, 165)
_ACCENT  = (75, 129, 207)
_BTN     = (35, 44, 56)
_BTN_HOV = (50, 65, 82)
_BTN_ACT = (55, 95, 155)
_DIVIDER = (38, 50, 64)
_TITLE   = (120, 185, 255)

# ── Font cache ────────────────────────────────────────────────────────────────
_font_cache: dict[tuple[int, bool], pygame.font.Font] = {}


def _font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    if key not in _font_cache:
        _font_cache[key] = pygame.font.SysFont("Segoe UI", size, bold=bold)
    return _font_cache[key]


# ── Drawing helpers ───────────────────────────────────────────────────────────
def _rrect(surf: pygame.Surface, color: tuple, rect: pygame.Rect, r: int = 6) -> None:
    pygame.draw.rect(surf, color, rect, border_radius=r)


def _rrect_border(surf: pygame.Surface, color: tuple, rect: pygame.Rect,
                  w: int = 2, r: int = 6) -> None:
    pygame.draw.rect(surf, color, rect, w, border_radius=r)


def _blit_text(surf: pygame.Surface, msg: str, font: pygame.font.Font,
               color: tuple, **anchor) -> None:
    rendered = font.render(str(msg), True, color)
    surf.blit(rendered, rendered.get_rect(**anchor))


# ── Background ────────────────────────────────────────────────────────────────
def _draw_bg(surface: pygame.Surface) -> None:
    """Solid fill with a faint isometric line grid for atmosphere."""
    surface.fill(_BG)
    w, h = surface.get_size()
    col = (20, 26, 34)
    step = 68  # spacing between parallel lines along y-axis

    # "/" diagonals (slope = +0.5)
    for b in range(-h, w // 2 + h + step, step):
        x1, y1 = 0, b
        x2, y2 = w, b + w // 2
        pygame.draw.line(surface, col, (x1, y1), (x2, y2), 1)

    # "\" diagonals (slope = -0.5)
    for b in range(-w // 2, h + w // 2 + step, step):
        x1, y1 = 0, b
        x2, y2 = w, b - w // 2
        pygame.draw.line(surface, col, (x1, y1), (x2, y2), 1)


# ── Button ────────────────────────────────────────────────────────────────────
class _Button:
    def __init__(self, rect: pygame.Rect, label: str) -> None:
        self.rect = pygame.Rect(rect)
        self.label = label
        self.hovered = False

    def draw(self, surf: pygame.Surface, active: bool = False,
             disabled: bool = False, fsize: int = 16) -> None:
        if disabled:
            bg, tc = _DIVIDER, _MUTED
        elif active:
            bg, tc = _BTN_ACT, (210, 232, 255)
        elif self.hovered:
            bg, tc = _BTN_HOV, _TEXT
        else:
            bg, tc = _BTN, _TEXT
        _rrect(surf, bg, self.rect)
        if active and not disabled:
            _rrect_border(surf, _ACCENT, self.rect)
        _blit_text(surf, self.label, _font(fsize), tc, center=self.rect.center)

    def hit(self, pos: tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)

    def update_hover(self, pos: tuple[int, int]) -> None:
        self.hovered = self.rect.collidepoint(pos)


# ── OptionRow ─────────────────────────────────────────────────────────────────
class _OptionRow:
    """A horizontal strip of mutually-exclusive option buttons."""

    def __init__(self, options: list[str], selected: int,
                 x: int, y: int, btn_w: int, btn_h: int, gap: int = 6) -> None:
        self.options = options
        self.selected = selected
        self.buttons = [
            _Button(pygame.Rect(x + i * (btn_w + gap), y, btn_w, btn_h), lbl)
            for i, lbl in enumerate(options)
        ]

    def draw(self, surf: pygame.Surface, fsize: int = 15) -> None:
        for i, btn in enumerate(self.buttons):
            btn.draw(surf, active=(i == self.selected), fsize=fsize)

    def handle_click(self, pos: tuple[int, int]) -> bool:
        for i, btn in enumerate(self.buttons):
            if btn.hit(pos):
                self.selected = i
                return True
        return False

    def update_hover(self, pos: tuple[int, int]) -> None:
        for btn in self.buttons:
            btn.update_hover(pos)

    @property
    def value(self) -> str:
        return self.options[self.selected]


# ── TextInput ─────────────────────────────────────────────────────────────────
class _TextInput:
    """Single-line digit input for the terrain seed."""

    def __init__(self, rect: pygame.Rect, placeholder: str = "Random",
                 max_chars: int = 9) -> None:
        self.rect = pygame.Rect(rect)
        self.placeholder = placeholder
        self.max_chars = max_chars
        self.text = ""
        self.focused = False
        self._blink = 0.0
        self._show_cursor = True

    def draw(self, surf: pygame.Surface, dt: float = 0) -> None:
        self._blink += dt
        if self._blink >= 0.5:
            self._blink = 0.0
            self._show_cursor = not self._show_cursor

        _rrect(surf, _BTN_HOV if self.focused else _BTN, self.rect)
        _rrect_border(surf, _ACCENT if self.focused else _DIVIDER, self.rect)

        display = self.text or self.placeholder
        color = _TEXT if self.text else _MUTED
        cursor = "|" if (self.focused and self._show_cursor) else ""
        inner = self.rect.inflate(-14, 0)
        _blit_text(surf, display + cursor, _font(15), color, midleft=inner.midleft)

    def handle_event(self, event: pygame.event.Event) -> None:
        if not self.focused or event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_BACKSPACE:
            self.text = self.text[:-1]
        elif event.unicode.isdigit() and len(self.text) < self.max_chars:
            self.text += event.unicode

    def handle_click(self, pos: tuple[int, int]) -> None:
        self.focused = self.rect.collidepoint(pos)

    @property
    def value(self) -> int | None:
        return int(self.text) if self.text else None


# ── Main Menu Screen ──────────────────────────────────────────────────────────
class _MainMenuScreen:
    def __init__(self, screen: pygame.Surface, save_exists: bool) -> None:
        self.screen = screen
        self.save_exists = save_exists
        self.clock = pygame.time.Clock()

    def run(self) -> str:
        """Returns 'new_game' | 'load' | 'settings' | 'quit'."""
        btn_labels = ["New Game", "Load Game", "Settings", "Quit"]
        btn_w, btn_h, v_gap = 260, 48, 10

        while True:
            dt = self.clock.tick(60) / 1000
            w, h = self.screen.get_size()
            cx = w // 2
            title_y = h // 3 - 10
            start_y = h // 2 - (len(btn_labels) * (btn_h + v_gap)) // 2

            buttons = [
                _Button(
                    pygame.Rect(cx - btn_w // 2, start_y + i * (btn_h + v_gap), btn_w, btn_h),
                    lbl,
                )
                for i, lbl in enumerate(btn_labels)
            ]

            pos = pygame.mouse.get_pos()
            for btn in buttons:
                btn.update_hover(pos)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return "quit"
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return "quit"
                if event.type == pygame.VIDEORESIZE:
                    self.screen = pygame.display.set_mode(
                        (max(800, event.w), max(600, event.h)), pygame.RESIZABLE
                    )
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if buttons[0].hit(pos):
                        return "new_game"
                    if buttons[1].hit(pos) and self.save_exists:
                        return "load"
                    if buttons[2].hit(pos):
                        return "settings"
                    if buttons[3].hit(pos):
                        return "quit"

            surf = self.screen
            _draw_bg(surf)

            # Drop shadow + title
            shadow = _font(54, bold=True).render("CITY BUILDER", True, (8, 16, 36))
            title  = _font(54, bold=True).render("CITY BUILDER", True, _TITLE)
            surf.blit(shadow, shadow.get_rect(center=(cx + 2, title_y + 2)))
            surf.blit(title,  title.get_rect(center=(cx, title_y)))

            sub = _font(14).render("An Isometric City Simulation", True, _MUTED)
            surf.blit(sub, sub.get_rect(center=(cx, title_y + 40)))
            pygame.draw.line(surf, _DIVIDER, (cx - 130, title_y + 56), (cx + 130, title_y + 56))

            for i, btn in enumerate(buttons):
                disabled = i == 1 and not self.save_exists
                btn.draw(surf, disabled=disabled, fsize=17)

            hint = _font(12).render("F11 · Alt+Enter — fullscreen", True, _MUTED)
            surf.blit(hint, (w - hint.get_width() - 12, h - hint.get_height() - 10))

            pygame.display.flip()

        return "quit"


# ── New Game Screen ───────────────────────────────────────────────────────────
class _NewGameScreen:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.clock = pygame.time.Clock()
        self._build(screen.get_size())

    def _build(self, size: tuple[int, int]) -> None:
        w, h = size
        cx = w // 2
        pW = min(740, w - 60)
        lx = cx - pW // 2
        bh, gap = 38, 6

        # Row y positions (where buttons sit)
        r0 = 158  # map size
        r1 = r0 + 74  # difficulty
        r2 = r1 + 74  # terrain style
        r3 = r2 + 74  # seed
        r4 = r3 + 68  # speed
        r5 = r4 + 70  # day/night cycle
        r6 = r5 + 58  # action buttons

        bw4 = (pW - 3 * gap) // 4
        bw3 = (pW - 2 * gap) // 3
        bw2 = (pW - gap) // 2

        self.map_size      = _OptionRow(list(MAP_SIZES.keys()),      1, lx, r0, bw4, bh, gap)
        self.difficulty    = _OptionRow(list(DIFFICULTY_MONEY.keys()),1, lx, r1, bw3, bh, gap)
        self.terrain_style = _OptionRow(TERRAIN_STYLES,              0, lx, r2, bw4, bh, gap)
        self.speed         = _OptionRow(list(SIM_SPEED_SECONDS.keys()),1, lx, r4, bw3, bh, gap)
        self.day_night     = _OptionRow(["Off", "On"],               0, lx, r5, bw2, bh, gap)

        rand_w = 116
        seed_w = pW - rand_w - gap
        self.seed_input = _TextInput(pygame.Rect(lx, r3, seed_w, bh))
        self.rand_btn   = _Button(pygame.Rect(lx + seed_w + gap, r3, rand_w, bh), "Randomize")

        self.back_btn  = _Button(pygame.Rect(lx, r6, 120, 44), "Back")
        self.start_btn = _Button(pygame.Rect(lx + pW - 160, r6, 160, 44), "Start Game")

        self._panel = pygame.Rect(lx - 20, 108, pW + 40, r6 + 44 + 22 - 108)
        self._lx = lx
        self._cx = cx
        self._rows = (r0, r1, r2, r3, r4, r5)

    def run(self) -> GameConfig | None:
        dt = 0.0
        while True:
            pos = pygame.mouse.get_pos()
            for widget in (self.map_size, self.difficulty, self.terrain_style, self.speed, self.day_night):
                widget.update_hover(pos)
            self.rand_btn.update_hover(pos)
            self.back_btn.update_hover(pos)
            self.start_btn.update_hover(pos)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return None
                    self.seed_input.handle_event(event)
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.seed_input.handle_click(pos)
                    self.map_size.handle_click(pos)
                    self.difficulty.handle_click(pos)
                    self.terrain_style.handle_click(pos)
                    self.speed.handle_click(pos)
                    self.day_night.handle_click(pos)
                    if self.rand_btn.hit(pos):
                        self.seed_input.text = str(random.randint(10000, 999999))
                    if self.back_btn.hit(pos):
                        return None
                    if self.start_btn.hit(pos):
                        return self._build_config()

            surf = self.screen
            cx = self._cx
            lx = self._lx
            r0, r1, r2, r3, r4, r5 = self._rows

            _draw_bg(surf)
            _rrect(surf, _PANEL, self._panel, 10)

            _blit_text(surf, "New Game", _font(30, bold=True), _TITLE, center=(cx, 72))
            pygame.draw.line(surf, _DIVIDER, (cx - 180, 96), (cx + 180, 96))

            # Section labels
            for ry, label in (
                (r0, "Map Size"),
                (r1, "Starting Funds"),
                (r2, "Terrain Style"),
                (r3, "Terrain Seed"),
                (r4, "Game Speed"),
                (r5, "Day/Night Cycle"),
            ):
                _blit_text(surf, label, _font(12, bold=True), _MUTED, topleft=(lx, ry - 18))

            # Per-selection hints
            mw, mh = MAP_SIZES[self.map_size.value]
            _blit_text(surf, f"{mw} × {mh} tiles", _font(12), _MUTED,
                       topleft=(lx, r0 + 42))

            money = DIFFICULTY_MONEY[self.difficulty.value]
            _blit_text(surf, f"${money:,} starting funds", _font(12), _MUTED,
                       topleft=(lx, r1 + 42))

            style_hints = {
                "Default": "Rivers, forests & hills",
                "Flat": "Open grassland — minimal water",
                "Hilly": "Rugged terrain with extra elevation",
                "Coastal": "Ocean along the southern edge",
            }
            _blit_text(surf, style_hints[self.terrain_style.value], _font(12), _MUTED,
                       topleft=(lx, r2 + 42))

            speed_hints = {
                "Slow":   "2.5 sec / month",
                "Normal": "1.25 sec / month",
                "Fast":   "0.4 sec / month",
            }
            _blit_text(surf, speed_hints[self.speed.value], _font(12), _MUTED,
                       topleft=(lx, r4 + 42))

            if self.day_night.value == "On":
                _blit_text(surf, "Dusk → night → dawn overlay (90 s cycle)", _font(12), _MUTED, topleft=(lx, r5 + 42))

            # Widgets
            self.map_size.draw(surf)
            self.difficulty.draw(surf)
            self.terrain_style.draw(surf)
            self.seed_input.draw(surf, dt)
            self.rand_btn.draw(surf)
            self.speed.draw(surf)
            self.day_night.draw(surf)

            self.back_btn.draw(surf)
            self.start_btn.draw(surf, active=True)

            pygame.display.flip()
            dt = self.clock.tick(60) / 1000

        return None

    def _build_config(self) -> GameConfig:
        return GameConfig(
            map_size_name=self.map_size.value,
            difficulty=self.difficulty.value,
            terrain_style=self.terrain_style.value,
            terrain_seed=self.seed_input.value,
            sim_speed=self.speed.value,
            day_night_cycle=self.day_night.value == "On",
        )


# ── Settings Screen ───────────────────────────────────────────────────────────
class _SettingsScreen:
    def __init__(self, screen: pygame.Surface) -> None:
        self.screen = screen
        self.clock = pygame.time.Clock()

    def run(self) -> None:
        while True:
            surf = self.screen
            w, h = surf.get_size()
            cx = w // 2

            back_btn = _Button(pygame.Rect(cx - 60, h // 2 + 90, 120, 44), "Back")
            pos = pygame.mouse.get_pos()
            back_btn.update_hover(pos)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    sys.exit()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if back_btn.hit(pos):
                        return

            _draw_bg(surf)
            panel = pygame.Rect(cx - 260, 100, 520, 300)
            _rrect(surf, _PANEL, panel, 10)

            _blit_text(surf, "Settings", _font(30, bold=True), _TITLE, center=(cx, 70))
            pygame.draw.line(surf, _DIVIDER, (cx - 140, 95), (cx + 140, 95))

            _blit_text(surf, "Display", _font(12, bold=True), _MUTED,
                       topleft=(panel.left + 24, 148))

            info_rect = pygame.Rect(panel.left + 24, 168, panel.width - 48, 40)
            _rrect(surf, _BTN, info_rect)
            _blit_text(surf, "Fullscreen: F11  or  Alt + Enter (during gameplay)",
                       _font(14), _MUTED, center=info_rect.center)

            _blit_text(surf, "Game Speed", _font(12, bold=True), _MUTED,
                       topleft=(panel.left + 24, 228))
            _blit_text(surf, "Game speed is chosen on the New Game screen.",
                       _font(13), _MUTED, topleft=(panel.left + 24, 248))

            _blit_text(surf, "Saves", _font(12, bold=True), _MUTED,
                       topleft=(panel.left + 24, 278))
            _blit_text(surf, "F5 = save   ·   F9 = load   ·   auto-saved on exit",
                       _font(13), _MUTED, topleft=(panel.left + 24, 298))

            back_btn.draw(surf)
            pygame.display.flip()
            self.clock.tick(60)


# ── Public entry point ────────────────────────────────────────────────────────
def run_main_menu() -> GameConfig | None:
    """Show the main menu loop. Returns a GameConfig to start a game, or None to quit."""
    if not pygame.get_init():
        pygame.init()

    screen = pygame.display.get_surface()
    if screen is None:
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
    pygame.display.set_caption("City Builder")

    save_path = Path(__file__).resolve().parent.parent / SAVE_FILE

    while True:
        result = _MainMenuScreen(screen, save_path.exists()).run()

        if result == "quit":
            return None

        if result == "settings":
            _SettingsScreen(screen).run()
            continue  # back to main menu

        if result == "new_game":
            config = _NewGameScreen(screen).run()
            if config is not None:
                return config
            continue  # user pressed Back → show main menu again

        if result == "load":
            return GameConfig(load_save=True)
