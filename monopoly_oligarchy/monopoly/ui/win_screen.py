"""Phase 14: the win screen.

:class:`WinScreen` is the full-screen overlay the game ends on: the winner's
name in their token colour, the cash and net worth they finished with, every
deed they held at the end, and the two buttons that decide what happens next
-- ``Play Again``, which sends ``main`` back to the Game Manager, and ``Quit``,
which closes the window.

Like every other surface in this package **it decides nothing.** It is handed a
:class:`WinState` -- built by :func:`monopoly.main.win_state` from
:attr:`monopoly.game.Game.winner`, the same one-way join the HUD uses -- and it
draws exactly that. :meth:`WinScreen.handle_event` reports :data:`PLAY_AGAIN`
or :data:`QUIT` and remembers it in :attr:`WinScreen.choice`, which is how
``main`` learns whether to start a new game after the loop drops out.

A ``WinState`` with no winner is a real state, not an absent one: a one-handed
game whose only player goes bankrupt to the bank leaves nobody standing, and
the screen says so. ``result = None`` is what means "the game is not over".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

import pygame

from monopoly.player import Player
from monopoly.property import Property
from monopoly.ui.button import Button
from monopoly.ui.hud import deed_label, token_rgb
from monopoly.ui.theme import (
    BORDER,
    DANGER,
    GROUP_COLORS,
    HOTEL_COLOR,
    HOUSE_COLOR,
    PANEL,
    PANEL_LIGHT,
    SCREEN_SIZE,
    TEXT,
    TEXT_MUTED,
    ellipsize,
    get_font,
)

#: What :meth:`WinScreen.handle_event` reports for the two buttons.
PLAY_AGAIN = "play_again"
QUIT = "quit"

#: The overlay fills the window; the card is inset inside it.
INSET = 40
PAD = 36

#: How dark the board goes behind the overlay (0-255). Nearly opaque: the game
#: is over, so there is nothing left to read underneath.
SCRIM_ALPHA = 225

HEADING_H = 26
BANNER_H = 64
STATS_H = 28

#: The token swatch beside the winner's name.
TOKEN_RADIUS = 18

#: One deed per row, in columns filled top to bottom, left to right.
COLUMNS = 3
COLUMN_GAP = 28
ROW_H = 30
ROW_GAP = 4
CHIP_W = 8
NAME_X = 16
STATUS_GAP = 10

#: Building marks at the right of a deed row, as the HUD draws them.
ROW_HOUSE = 9
ROW_HOTEL = (16, 11)

FOOTER_H = 56
BUTTON_H = 52
BUTTON_W = 200
BUTTON_GAP = 20

HEADING_TEXT = "GAME OVER"
NO_WINNER_TEXT = "Nobody wins"
NO_WINNER_NOTE = "Everybody went bankrupt; the bank takes the board."
EMPTY_TEXT = "No properties held at the end."
MORTGAGED_STATUS = "mortgaged"
HOTEL_STATUS = "hotel"


@dataclass(frozen=True)
class WinState:
    """The finished game, as the overlay sees it.

    ``winner`` is ``None`` for a table that went bankrupt to the last player;
    ``players`` is the whole roster in seat order, for the count in the
    heading. Both are read-only here -- the screen never touches a player.
    """

    winner: Optional[Player] = None
    players: Sequence[Player] = ()


class WinScreen:
    """A full-screen overlay: the winner, their final stats, two buttons."""

    def __init__(
        self,
        rect: Optional[pygame.Rect | tuple[int, int, int, int]] = None,
        *,
        result: Optional[WinState] = None,
        on_close: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.rect = (
            pygame.Rect(rect) if rect is not None else pygame.Rect((0, 0), SCREEN_SIZE)
        )
        self.on_close = on_close
        #: The last button pressed, or ``None`` while the screen is unanswered.
        self.choice: Optional[str] = None
        self._result: Optional[WinState] = None
        self.deeds: list[Property] = []
        self.play_again = self._button(PLAY_AGAIN, "Play Again", primary=True)
        self.quit = self._button(QUIT, "Quit")
        self.result = result

    # --- state --------------------------------------------------------------
    @property
    def result(self) -> Optional[WinState]:
        return self._result

    @result.setter
    def result(self, value: Optional[WinState]) -> None:
        """Show ``value`` (or nothing), collecting the winner's deeds."""
        self._result = value
        winner = None if value is None else value.winner
        self.deeds = (
            [] if winner is None else sorted(winner.properties, key=lambda p: p.index)
        )

    @property
    def visible(self) -> bool:
        """Whether there is anything to draw. ``False`` until the game ends."""
        return self._result is not None

    @property
    def winner(self) -> Optional[Player]:
        return None if self._result is None else self._result.winner

    # --- layout -------------------------------------------------------------
    @property
    def card_rect(self) -> pygame.Rect:
        """The panel inside the overlay."""
        return self.rect.inflate(-2 * INSET, -2 * INSET)

    @property
    def heading_rect(self) -> pygame.Rect:
        card = self.card_rect
        return pygame.Rect(
            card.left + PAD, card.top + PAD, card.width - 2 * PAD, HEADING_H
        )

    @property
    def banner_rect(self) -> pygame.Rect:
        """The winner's token and name."""
        return pygame.Rect(
            self.heading_rect.left,
            self.heading_rect.bottom + 8,
            self.heading_rect.width,
            BANNER_H,
        )

    @property
    def stats_rect(self) -> pygame.Rect:
        """The two money lines under the banner."""
        return pygame.Rect(
            self.banner_rect.left,
            self.banner_rect.bottom + 6,
            self.banner_rect.width,
            2 * STATS_H,
        )

    @property
    def footer_rect(self) -> pygame.Rect:
        """The strip along the bottom holding the two buttons."""
        card = self.card_rect
        return pygame.Rect(
            card.left + PAD,
            card.bottom - PAD - FOOTER_H,
            card.width - 2 * PAD,
            FOOTER_H,
        )

    @property
    def list_rect(self) -> pygame.Rect:
        """Everything between the stats and the footer: the deed columns.

        The gap above it is the deed list's own heading, which is drawn just
        outside the rectangle rather than inside it -- so a row never has to
        share its space with a label.
        """
        top = self.stats_rect.bottom + 30
        return pygame.Rect(
            self.stats_rect.left,
            top,
            self.stats_rect.width,
            self.footer_rect.top - 16 - top,
        )

    @property
    def rows_per_column(self) -> int:
        """How many whole deed rows one column holds."""
        return max(1, (self.list_rect.height + ROW_GAP) // (ROW_H + ROW_GAP))

    @property
    def capacity(self) -> int:
        """How many deeds the columns can show before overflowing."""
        return self.rows_per_column * COLUMNS

    @property
    def shown_deeds(self) -> list[Property]:
        """The deeds that fit. The board holds 28, the columns hold more."""
        return self.deeds[: self.capacity]

    @property
    def overflow(self) -> int:
        """How many deeds did not fit (``0`` on the real board)."""
        return max(0, len(self.deeds) - self.capacity)

    @property
    def column_width(self) -> int:
        return (self.list_rect.width - COLUMN_GAP * (COLUMNS - 1)) // COLUMNS

    def row_rect(self, row: int) -> pygame.Rect:
        """The rectangle of the ``row``-th shown deed.

        Columns fill top to bottom, then left to right, so a short list stays
        in one column rather than spreading itself thin across two.
        """
        column, offset = divmod(row, self.rows_per_column)
        width = self.column_width
        return pygame.Rect(
            self.list_rect.left + column * (width + COLUMN_GAP),
            self.list_rect.top + offset * (ROW_H + ROW_GAP),
            width,
            ROW_H,
        )

    def _button(self, key: str, label: str, *, primary: bool = False) -> Button:
        """One of the two footer buttons, side by side and centred."""
        footer = self.footer_rect
        span = 2 * BUTTON_W + BUTTON_GAP
        left = footer.centerx - span // 2
        x = left if primary else left + BUTTON_W + BUTTON_GAP
        return Button(
            (x, footer.bottom - BUTTON_H, BUTTON_W, BUTTON_H),
            label,
            primary=primary,
            font_size=22,
            on_click=lambda k=key: self._fire(k),
        )

    # --- events -------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Dispatch one event; return :data:`PLAY_AGAIN` / :data:`QUIT`.

        ``None`` for anything else -- including every event while the screen
        is holding nothing, so a live game is never answered by accident.
        """
        if self._result is None:
            return None
        if self.play_again.handle_event(event):
            return PLAY_AGAIN
        if self.quit.handle_event(event):
            return QUIT
        return None

    def _fire(self, key: str) -> None:
        self.choice = key
        if self.on_close is not None:
            self.on_close(key)

    # --- drawing ------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        """Cover the screen and draw the card. A no-op with no result."""
        result = self._result
        if result is None:
            return
        self._draw_scrim(surface)
        card = self.card_rect
        pygame.draw.rect(surface, PANEL, card, border_radius=12)
        pygame.draw.rect(surface, BORDER, card, width=2, border_radius=12)

        self._draw_heading(surface, result)
        self._draw_banner(surface, result)
        if result.winner is None:
            note = get_font(18).render(NO_WINNER_NOTE, True, TEXT_MUTED)
            surface.blit(
                note,
                note.get_rect(
                    midleft=(self.stats_rect.left, self.stats_rect.centery)
                ),
            )
        else:
            self._draw_stats(surface, result.winner)
            self._draw_deeds(surface)
        self.play_again.draw(surface)
        self.quit.draw(surface)

    def _draw_heading(self, surface: pygame.Surface, result: WinState) -> None:
        rect = self.heading_rect
        heading = get_font(20, bold=True).render(HEADING_TEXT, True, TEXT_MUTED)
        surface.blit(heading, heading.get_rect(midleft=(rect.left, rect.centery)))
        if result.players:
            tally = get_font(16).render(_tally(result.players), True, TEXT_MUTED)
            surface.blit(tally, tally.get_rect(midright=(rect.right, rect.centery)))

    def _draw_banner(self, surface: pygame.Surface, result: WinState) -> None:
        rect = self.banner_rect
        winner = result.winner
        if winner is None:
            text = get_font(44, bold=True).render(NO_WINNER_TEXT, True, TEXT_MUTED)
            surface.blit(text, text.get_rect(midleft=(rect.left, rect.centery)))
            return
        color = token_rgb(winner)
        center = (rect.left + TOKEN_RADIUS, rect.centery)
        pygame.draw.circle(surface, color, center, TOKEN_RADIUS)
        pygame.draw.circle(surface, TEXT, center, TOKEN_RADIUS, width=2)
        font = get_font(44, bold=True)
        label = ellipsize(
            f"{winner.name} wins!", font, rect.width - 2 * TOKEN_RADIUS - 24
        )
        text = font.render(label, True, color)
        surface.blit(
            text, text.get_rect(midleft=(rect.left + 2 * TOKEN_RADIUS + 20, rect.centery))
        )

    def _draw_stats(self, surface: pygame.Surface, winner: Player) -> None:
        rect = self.stats_rect
        lines = (
            ("Final cash", f"${winner.cash:,}"),
            ("Net worth", f"${winner.net_worth():,}"),
        )
        label_font = get_font(16)
        value_font = get_font(20, bold=True)
        for i, (label, value) in enumerate(lines):
            y = rect.top + i * STATS_H
            surface.blit(label_font.render(label, True, TEXT_MUTED), (rect.left, y + 4))
            surface.blit(value_font.render(value, True, TEXT), (rect.left + 150, y))

    def _draw_deeds(self, surface: pygame.Surface) -> None:
        rect = self.list_rect
        header = get_font(15, bold=True).render(
            f"PROPERTIES OWNED ({len(self.deeds)})", True, TEXT_MUTED
        )
        surface.blit(header, (rect.left, rect.top - 20))
        if not self.deeds:
            empty = get_font(16).render(EMPTY_TEXT, True, TEXT_MUTED)
            surface.blit(empty, (rect.left, rect.top + 4))
            return
        for i, deed in enumerate(self.shown_deeds):
            self._draw_deed_row(surface, self.row_rect(i), deed)
        if self.overflow:
            more = get_font(14).render(f"+{self.overflow} more", True, TEXT_MUTED)
            surface.blit(more, more.get_rect(bottomright=(rect.right, rect.bottom)))

    def _draw_deed_row(
        self, surface: pygame.Surface, rect: pygame.Rect, deed: Property
    ) -> None:
        pygame.draw.rect(surface, PANEL_LIGHT, rect, border_radius=5)
        chip = pygame.Rect(rect.left, rect.top + 4, CHIP_W, rect.height - 8)
        pygame.draw.rect(surface, GROUP_COLORS[deed.group], chip)

        right = rect.right - 8
        if deed.mortgaged:
            badge = get_font(13, bold=True).render(MORTGAGED_STATUS, True, DANGER)
            surface.blit(badge, badge.get_rect(midright=(right, rect.centery)))
            right = badge.get_rect(midright=(right, rect.centery)).left - STATUS_GAP
        else:
            right = self._draw_buildings(surface, rect, deed, right)

        font = get_font(16)
        color = TEXT_MUTED if deed.mortgaged else TEXT
        name = ellipsize(deed_label(deed), font, right - rect.left - NAME_X - 4)
        text = font.render(name, True, color)
        surface.blit(text, text.get_rect(midleft=(rect.left + NAME_X, rect.centery)))

    def _draw_buildings(
        self, surface: pygame.Surface, rect: pygame.Rect, deed: Property, right: int
    ) -> int:
        """A hotel, or one square per house, right to left; the new edge."""
        if deed.has_hotel:
            hotel = pygame.Rect(0, 0, *ROW_HOTEL)
            hotel.midright = (right, rect.centery)
            pygame.draw.rect(surface, HOTEL_COLOR, hotel)
            return hotel.left - STATUS_GAP
        for _ in range(deed.houses):
            house = pygame.Rect(0, 0, ROW_HOUSE, ROW_HOUSE)
            house.midright = (right, rect.centery)
            pygame.draw.rect(surface, HOUSE_COLOR, house)
            right = house.left - 3
        return right - STATUS_GAP if deed.houses else right

    def _draw_scrim(self, surface: pygame.Surface) -> None:
        scrim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        scrim.fill((0, 0, 0, SCRIM_ALPHA))
        surface.blit(scrim, (0, 0))


def _tally(players: Sequence[Player]) -> str:
    """The count in the corner of the heading: how many played, how many out."""
    count = len(players)
    out = sum(1 for player in players if player.is_bankrupt)
    return f"{count} player{'' if count == 1 else 's'} -- {out} bankrupt"


def describe_result(result: WinState) -> str:
    """A one-line summary of a finished game, for the console.

    Named apart from ``main.describe`` (which summarises the *roster*) so the
    two can live side by side in that module.
    """
    winner = result.winner
    if winner is None:
        return NO_WINNER_NOTE
    return (
        f"{winner.name} wins with ${winner.net_worth():,} "
        f"(${winner.cash:,} cash, {len(winner.properties)} deeds)"
    )
