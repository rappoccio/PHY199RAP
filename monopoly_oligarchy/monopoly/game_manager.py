"""Phase 3: the Game Manager setup screen.

The one rules change in this edition: before any board appears, a human
operator picks how many players there are and types each player's name and
**starting cash**. This module owns that screen end to end -- its layout, its
keyboard and mouse handling, its validation, and the :class:`~monopoly.player.Player`
objects it hands to the game loop.

The screen is a small state machine so that it can be driven either by a real
pygame event loop (:func:`run`) or, in tests, by synthesised events:

``Stage.COUNT`` -> ``Stage.DETAILS`` -> ``Stage.DONE``

Nothing here draws a board or touches game rules; :attr:`GameManager.players`
is the entire output.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Optional

import pygame

from monopoly.player import Player
from monopoly.ui.button import Button
from monopoly.ui.text_input import TextInput
from monopoly.ui.theme import (
    ACCENT,
    BACKGROUND,
    BORDER,
    DANGER,
    PANEL,
    SCREEN_SIZE,
    TEXT,
    TEXT_MUTED,
    TOKEN_COLORS,
    get_font,
)

MIN_PLAYERS = 2
MAX_PLAYERS = 6

#: What the cash field is pre-filled with -- the standard opening bank.
DEFAULT_CASH = 1500

#: Caps on what the operator may type. Names stay short enough for the HUD;
#: cash is capped at seven digits so the field cannot be filled forever.
MAX_NAME_LENGTH = 16
MAX_CASH_DIGITS = 7

TITLE = "MONOPOLY"
SUBTITLE = "Custom Stake Edition"


class Stage(Enum):
    """Which screen the setup flow is showing."""

    COUNT = auto()
    DETAILS = auto()
    DONE = auto()


class PlayerEntry:
    """One row of the details screen: a seat's name and starting cash."""

    def __init__(self, seat: int, name_rect, cash_rect, bot_rect) -> None:
        self.seat = seat
        self.token_color = TOKEN_COLORS[seat][0]
        self.token_rgb = TOKEN_COLORS[seat][1]
        self.is_bot: bool = False
        self.name_input = TextInput(
            name_rect,
            placeholder=f"Player {seat + 1}",
            max_length=MAX_NAME_LENGTH,
        )
        self.cash_input = TextInput(
            cash_rect,
            text=str(DEFAULT_CASH),
            placeholder="0",
            max_length=MAX_CASH_DIGITS,
            digits_only=True,
        )
        self.bot_button = Button(
            bot_rect,
            "Human",
            font_size=17,
            on_click=self._toggle_bot,
        )

    def _toggle_bot(self) -> None:
        self.is_bot = not self.is_bot
        self.bot_button.label = "Bot" if self.is_bot else "Human"
        self.bot_button.primary = self.is_bot

    @property
    def fields(self) -> tuple[TextInput, TextInput]:
        return (self.name_input, self.cash_input)

    @property
    def name(self) -> str:
        """The typed name, with surrounding whitespace trimmed."""
        return self.name_input.value

    @property
    def cash(self) -> Optional[int]:
        """The typed cash, or ``None`` when the field is not a valid amount."""
        text = self.cash_input.value
        if not text.isdigit():
            return None
        amount = int(text)
        return amount if amount > 0 else None

    @property
    def error(self) -> Optional[str]:
        """Why this row is not usable yet, or ``None`` when it is fine."""
        label = f"Player {self.seat + 1}"
        if not self.name:
            return f"{label}: name cannot be empty"
        if self.cash is None:
            return f"{label}: starting cash must be a positive whole number"
        return None

    def to_player(self) -> Player:
        if self.error is not None:  # pragma: no cover - guarded by is_valid
            raise ValueError(f"seat {self.seat} is not ready: {self.error}")
        return Player(
            name=self.name,
            cash=int(self.cash),
            token_color=self.token_color,
            is_bot=self.is_bot,
        )


class GameManager:
    """The setup screen: player count, then a name and stake per player."""

    #: Top of the roster panel, and how far the first row sits below it.
    PANEL_TOP = 190
    ROW_PITCH = 70
    ROW_INSET = 50

    def __init__(self, size: tuple[int, int] = SCREEN_SIZE) -> None:
        self.width, self.height = size
        self.stage = Stage.COUNT
        self.entries: list[PlayerEntry] = []
        self.players: list[Player] = []
        self.quit_requested = False
        self._now = 0
        self._build_count_buttons()
        self._build_detail_buttons()

    # --- layout -------------------------------------------------------------
    def _build_count_buttons(self) -> None:
        options = list(range(MIN_PLAYERS, MAX_PLAYERS + 1))
        button_w, button_h, gap = 90, 90, 24
        total = len(options) * button_w + (len(options) - 1) * gap
        x = (self.width - total) // 2
        y = self.height // 2 - button_h // 2
        self.count_buttons: list[Button] = []
        for count in options:
            button = Button(
                (x, y, button_w, button_h),
                str(count),
                font_size=34,
                on_click=lambda n=count: self.select_count(n),
            )
            self.count_buttons.append(button)
            x += button_w + gap

    def _row_rects(self, seat: int) -> tuple[pygame.Rect, pygame.Rect, pygame.Rect]:
        y = self.PANEL_TOP + self.ROW_INSET + seat * self.ROW_PITCH
        return (
            pygame.Rect(360, y, 240, 44),   # name  (shrunk from 340)
            pygame.Rect(618, y, 150, 44),   # cash  (moved left of toggle)
            pygame.Rect(782, y, 120, 44),   # bot toggle
        )

    def panel_rect(self, seats: Optional[int] = None) -> pygame.Rect:
        """The roster panel for ``seats`` rows (defaults to the current ones)."""
        rows = len(self.entries) if seats is None else seats
        height = rows * self.ROW_PITCH + self.ROW_INSET
        return pygame.Rect(280, self.PANEL_TOP, self.width - 560, height)

    @property
    def footer_top(self) -> int:
        """Where the error line, hint and buttons start.

        Anchored near the bottom of the screen, but pushed further down when a
        full six-seat panel would otherwise run into them.
        """
        return max(self.height - 130, self.panel_rect().bottom + 62)

    def _build_detail_buttons(self) -> None:
        y = self.footer_top
        self.back_button = Button(
            (self.width // 2 - 260, y, 200, 56),
            "Back",
            on_click=self.back,
        )
        self.start_button = Button(
            (self.width // 2 + 60, y, 200, 56),
            "Start Game",
            primary=True,
            on_click=self.start,
        )

    def _layout_detail_buttons(self) -> None:
        """Re-anchor Back/Start after the seat count (and panel height) changes."""
        y = self.footer_top
        self.back_button.rect.y = y
        self.start_button.rect.y = y

    # --- stage transitions --------------------------------------------------
    def select_count(self, count: int) -> None:
        """Move to the details screen with ``count`` seats."""
        if not MIN_PLAYERS <= count <= MAX_PLAYERS:
            raise ValueError(
                f"player count must be {MIN_PLAYERS}-{MAX_PLAYERS}, got {count}"
            )
        # Keep what the operator already typed when they come back and pick
        # the same (or a larger) number of players.
        while len(self.entries) > count:
            self.entries.pop()
        while len(self.entries) < count:
            seat = len(self.entries)
            self.entries.append(PlayerEntry(seat, *self._row_rects(seat)))
        self._layout_detail_buttons()
        self.stage = Stage.DETAILS
        self.focus(0)

    def back(self) -> None:
        """Return to the player-count screen."""
        self.stage = Stage.COUNT
        for field in self.fields:
            field.focused = False

    def start(self) -> bool:
        """Build the players and finish, if every row is valid."""
        if self.stage != Stage.DETAILS or not self.is_valid:
            return False
        self.players = [entry.to_player() for entry in self.entries]
        self.stage = Stage.DONE
        return True

    def reset(self) -> None:
        """Clear everything and return to the first screen (Play Again)."""
        self.stage = Stage.COUNT
        self.entries = []
        self.players = []
        self.quit_requested = False

    # --- fields and focus ---------------------------------------------------
    @property
    def fields(self) -> list[TextInput]:
        """Every text field on the details screen, in tab order."""
        return [field for entry in self.entries for field in entry.fields]

    @property
    def focused_index(self) -> Optional[int]:
        for i, field in enumerate(self.fields):
            if field.focused:
                return i
        return None

    def focus(self, index: int) -> None:
        """Give the keyboard to field ``index`` (wrapping at either end)."""
        fields = self.fields
        if not fields:
            return
        index %= len(fields)
        for i, field in enumerate(fields):
            field.focused = i == index

    def focus_next(self, step: int = 1) -> None:
        """Move the keyboard focus ``step`` fields along the tab order."""
        current = self.focused_index
        self.focus(0 if current is None else current + step)

    # --- validation ---------------------------------------------------------
    @property
    def validation_errors(self) -> list[str]:
        """One message per unusable row, in seat order."""
        return [entry.error for entry in self.entries if entry.error]

    @property
    def is_valid(self) -> bool:
        return bool(self.entries) and not self.validation_errors

    # --- events -------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> None:
        """Dispatch one pygame event to whichever screen is showing."""
        if event.type == pygame.QUIT:
            self.quit_requested = True
            return
        if self.stage == Stage.COUNT:
            self._handle_count_event(event)
        elif self.stage == Stage.DETAILS:
            self._handle_details_event(event)

    def _handle_count_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            digit = getattr(event, "unicode", "")
            if digit.isdigit() and MIN_PLAYERS <= int(digit) <= MAX_PLAYERS:
                self.select_count(int(digit))
            return
        for button in self.count_buttons:
            if button.handle_event(event):
                return

    def _handle_details_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                shift = bool(getattr(event, "mod", 0) & pygame.KMOD_SHIFT)
                self.focus_next(-1 if shift else 1)
                return
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._confirm_field()
                return
            if event.key == pygame.K_ESCAPE:
                self.back()
                return

        for field in self.fields:
            if field.handle_event(event):
                return
        for entry in self.entries:
            if entry.bot_button.handle_event(event):
                return
        # Start only accepts clicks once every row validates; typing in a field
        # can flip that between frames, so refresh it before dispatching.
        self.start_button.enabled = self.is_valid
        for button in (self.back_button, self.start_button):
            if button.handle_event(event):
                return

    def _confirm_field(self) -> None:
        """Enter: advance to the next field, or start once on the last one."""
        current = self.focused_index
        if current is not None and current < len(self.fields) - 1:
            self.focus(current + 1)
            return
        if not self.start():
            self.focus(0)

    # --- frame --------------------------------------------------------------
    def update(self, now_ms: int) -> None:
        """Advance widget animation clocks (just the caret blink, so far)."""
        self._now = now_ms
        for field in self.fields:
            field.update(now_ms)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BACKGROUND)
        self._draw_title(surface)
        if self.stage == Stage.COUNT:
            self._draw_count(surface)
        else:
            self._draw_details(surface)

    def _draw_title(self, surface: pygame.Surface) -> None:
        title = get_font(56, bold=True).render(TITLE, True, TEXT)
        surface.blit(title, title.get_rect(center=(self.width // 2, 90)))
        subtitle = get_font(24).render(SUBTITLE, True, ACCENT)
        surface.blit(subtitle, subtitle.get_rect(center=(self.width // 2, 140)))

    def _draw_count(self, surface: pygame.Surface) -> None:
        prompt = get_font(30).render(
            f"How many players? ({MIN_PLAYERS}-{MAX_PLAYERS})", True, TEXT
        )
        surface.blit(prompt, prompt.get_rect(center=(self.width // 2, 320)))
        for button in self.count_buttons:
            button.draw(surface)
        hint = get_font(18).render(
            "Click a number, or press a number key.", True, TEXT_MUTED
        )
        surface.blit(hint, hint.get_rect(center=(self.width // 2, self.height - 120)))

    def _draw_details(self, surface: pygame.Surface) -> None:
        panel = self.panel_rect()
        pygame.draw.rect(surface, PANEL, panel, border_radius=8)
        pygame.draw.rect(surface, BORDER, panel, width=2, border_radius=8)

        label_font = get_font(18, bold=True)
        header_y = panel.top + 15
        surface.blit(label_font.render("NAME", True, TEXT_MUTED), (360, header_y))
        surface.blit(label_font.render("STARTING CASH", True, TEXT_MUTED), (618, header_y))
        surface.blit(label_font.render("TYPE", True, TEXT_MUTED), (782, header_y))

        seat_font = get_font(20)
        for entry in self.entries:
            name_rect = entry.name_input.rect
            pygame.draw.circle(
                surface, entry.token_rgb, (325, name_rect.centery), 12
            )
            seat = seat_font.render(f"{entry.seat + 1}.", True, TEXT)
            surface.blit(seat, seat.get_rect(midright=(305, name_rect.centery)))
            entry.name_input.draw(surface)
            entry.cash_input.draw(surface)
            dollar = seat_font.render("$", True, TEXT_MUTED)
            surface.blit(
                dollar, dollar.get_rect(midright=(entry.cash_input.rect.x - 8,
                                                  entry.cash_input.rect.centery))
            )
            entry.bot_button.draw(surface)

        self.start_button.enabled = self.is_valid
        self.back_button.draw(surface)
        self.start_button.draw(surface)

        # Hint and error sit between the panel and the buttons, so a six-seat
        # roster pushes them down instead of printing over the bottom rows.
        footer = self.footer_top
        hint = get_font(18).render("Tab between fields, Enter to confirm.", True, TEXT_MUTED)
        surface.blit(hint, hint.get_rect(center=(self.width // 2, footer - 22)))
        # Show the first validation error (if any) just above the hint.
        errors = self.validation_errors
        if errors:
            err_surf = get_font(18).render(errors[0], True, DANGER)
            surface.blit(err_surf, err_surf.get_rect(center=(self.width // 2, footer - 46)))


def run(
    surface: Optional[pygame.Surface] = None,
    clock: Optional[pygame.time.Clock] = None,
    manager: Optional[GameManager] = None,
) -> Optional[list[Player]]:
    """Run the setup screen until it finishes or the window is closed.

    Returns the roster, or ``None`` if the operator quit.
    """
    manager = manager or GameManager()
    if surface is None:
        surface = pygame.display.set_mode(SCREEN_SIZE)
        pygame.display.set_caption(f"{TITLE} - {SUBTITLE}")
    clock = clock or pygame.time.Clock()

    while manager.stage != Stage.DONE and not manager.quit_requested:
        for event in pygame.event.get():
            manager.handle_event(event)
        manager.update(pygame.time.get_ticks())
        manager.draw(surface)
        pygame.display.flip()
        clock.tick(60)

    return None if manager.quit_requested else manager.players
