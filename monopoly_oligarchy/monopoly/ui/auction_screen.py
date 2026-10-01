"""Phase 10: the auction screen.

:class:`AuctionScreen` draws the :class:`monopoly.auction.Auction` the game is
running over a dimmed board: the deed under the hammer, where the bidding
stands, one row per bidder, and -- for whoever the round is waiting on -- a
cash field with three quick-raise buttons, **Bid** and **Pass**.

Like the HUD, the popup and the build screen **it decides nothing.** The field
is only a number; :meth:`AuctionScreen.handle_event` reports :data:`BID` or
:data:`PASS` and ``main`` turns that into :meth:`monopoly.game.Game.bid` /
:meth:`monopoly.game.Game.pass_bid`, which are free to refuse it. The screen
asks :meth:`~monopoly.auction.Auction.can_bid` which buttons to draw live, and
:meth:`sync` re-reads the sale every frame so the field refills with the new
asking price as the turn goes round.
"""

from __future__ import annotations

from typing import Callable, Optional

import pygame

from monopoly.auction import Auction, summarise
from monopoly.player import Player
from monopoly.ui.button import Button
from monopoly.ui.hud import deed_label, token_rgb
from monopoly.ui.text_input import TextInput
from monopoly.ui.theme import (
    ACCENT,
    BORDER,
    GROUP_COLORS,
    PANEL,
    PANEL_LIGHT,
    TEXT,
    TEXT_MUTED,
    ellipsize,
    get_font,
)

#: What :meth:`AuctionScreen.handle_event` reports for the two closing moves.
BID = "bid"
PASS = "pass"

#: The box, centred over the 800x800 board.
SCREEN_SIZE = (620, 560)
SCREEN_CENTER = (400, 400)

PAD = 22

TITLE_H = 32
STATUS_H = 24
ROW_H = 30
ROW_GAP = 4

FOOTER_H = 112
BUTTON_H = 42
BUTTON_W = 130
BUTTON_GAP = 12

#: The bid field, and the quick raises that add to whatever is in it.
FIELD_W = 150
FIELD_H = 38
RAISE_W = 62
RAISE_GAP = 8
RAISES = (1, 10, 50)

#: Columns inside a bidder row: the name, then the cash, then the standing.
NAME_X = 34
NAME_W = 210
CASH_X = 260
STATUS_X = 400

#: How dark the board goes behind the screen (0-255).
SCRIM_ALPHA = 165

#: The marker drawn beside whoever the round is waiting on.
TURN_MARK = ">"


class AuctionScreen:
    """A modal sale panel: the deed, the bidders, a bid field and two buttons."""

    def __init__(
        self,
        rect: Optional[pygame.Rect | tuple[int, int, int, int]] = None,
        *,
        auction: Optional[Auction] = None,
        on_close: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.rect = (
            pygame.Rect(rect) if rect is not None else pygame.Rect((0, 0), SCREEN_SIZE)
        )
        if rect is None:
            self.rect.center = SCREEN_CENTER
        self.on_close = on_close
        self._auction: Optional[Auction] = None
        self._shown: Optional[tuple[int, int]] = None
        self.field = TextInput(
            self.field_rect,
            placeholder="0",
            digits_only=True,
            max_length=7,
            focused=True,
        )
        self.raises = [
            Button(
                self.raise_rect(i),
                f"+{step}",
                font_size=16,
                on_click=lambda amount=step: self.raise_by(amount),
            )
            for i, step in enumerate(RAISES)
        ]
        self.bid = self._closing_button(BID, "Bid", primary=True)
        self.pass_button = self._closing_button(PASS, "Pass")
        self.auction = auction

    # --- state --------------------------------------------------------------
    @property
    def auction(self) -> Optional[Auction]:
        return self._auction

    @auction.setter
    def auction(self, value: Optional[Auction]) -> None:
        """Show ``value`` (or nothing), refilling the field from scratch."""
        self._auction = value
        self._shown = None
        self.sync()

    @property
    def visible(self) -> bool:
        return self._auction is not None

    @property
    def amount(self) -> int:
        """Whatever number is in the field right now (``0`` when it is empty)."""
        text = self.field.value
        return int(text) if text.isdigit() else 0

    @amount.setter
    def amount(self, value: int) -> None:
        self.field.text = str(max(0, value))

    def sync(self) -> None:
        """Follow the sale: refill the field whenever the asking price moves.

        Called every frame, because the round moves on under the screen --
        one click hands the turn to the next bidder, and that bidder should
        find the new minimum already typed in for them.
        """
        auction = self._auction
        if auction is None:
            self._shown = None
            self.refresh()
            return
        bidder = auction.bidder
        mark = (id(bidder) if bidder is not None else 0, auction.min_bid)
        if mark != self._shown:
            self._shown = mark
            self.amount = auction.min_bid
        self.refresh()

    def refresh(self) -> None:
        """Re-check which buttons are live for the number in the field."""
        auction = self._auction
        running = auction is not None and not auction.finished
        self.bid.enabled = running and auction.can_bid(self.amount)
        self.pass_button.enabled = running
        for button in self.raises:
            button.enabled = running

    def raise_by(self, step: int) -> None:
        """Add ``step`` to the field, never dropping below the asking price."""
        auction = self._auction
        floor = auction.min_bid if auction is not None else 0
        self.amount = max(floor, self.amount + step)
        self.refresh()

    # --- layout -------------------------------------------------------------
    @property
    def title_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.rect.left + PAD, self.rect.top + PAD, self.rect.width - 2 * PAD, TITLE_H
        )

    @property
    def status_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.rect.left + PAD,
            self.title_rect.bottom + 2,
            self.rect.width - 2 * PAD,
            STATUS_H,
        )

    @property
    def footer_rect(self) -> pygame.Rect:
        """The strip along the bottom: the bid field and the two buttons."""
        return pygame.Rect(
            self.rect.left + PAD,
            self.rect.bottom - PAD - FOOTER_H,
            self.rect.width - 2 * PAD,
            FOOTER_H,
        )

    @property
    def list_rect(self) -> pygame.Rect:
        """The bidder rows, between the status line and the footer."""
        top = self.status_rect.bottom + 8
        return pygame.Rect(
            self.rect.left + PAD,
            top,
            self.rect.width - 2 * PAD,
            self.footer_rect.top - 10 - top,
        )

    def row_rect(self, row: int) -> pygame.Rect:
        """The ``row``-th bidder's row."""
        return pygame.Rect(
            self.list_rect.left,
            self.list_rect.top + row * (ROW_H + ROW_GAP),
            self.list_rect.width,
            ROW_H,
        )

    @property
    def visible_rows(self) -> int:
        """How many bidder rows fit the list window."""
        return max(0, (self.list_rect.height + ROW_GAP) // (ROW_H + ROW_GAP))

    @property
    def field_rect(self) -> pygame.Rect:
        footer = self.footer_rect
        return pygame.Rect(footer.left, footer.top + 20, FIELD_W, FIELD_H)

    def raise_rect(self, i: int) -> pygame.Rect:
        field = self.field_rect
        return pygame.Rect(
            field.right + RAISE_GAP + i * (RAISE_W + RAISE_GAP),
            field.top,
            RAISE_W,
            FIELD_H,
        )

    def _closing_button(self, key: str, label: str, *, primary: bool = False) -> Button:
        footer = self.footer_rect
        right = footer.right if primary else footer.right - BUTTON_W - BUTTON_GAP
        return Button(
            (right - BUTTON_W, footer.bottom - BUTTON_H, BUTTON_W, BUTTON_H),
            label,
            primary=primary,
            font_size=20,
            on_click=lambda k=key: self._fire(k),
        )

    # --- events -------------------------------------------------------------
    def update(self, now_ms: int) -> None:
        """Advance the field's caret blink."""
        self.field.update(now_ms)

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Dispatch one event; return :data:`BID` / :data:`PASS` or ``None``.

        Typing in the field, or nudging it with a quick raise, reports
        ``None``: the sale only moves when Bid or Pass is pressed. Enter is
        the Bid button's shortcut, and is ignored while the bid would be
        refused.
        """
        if self._auction is None:
            return None
        if self.field.handle_event(event):
            self.refresh()
            return None
        if event.type == pygame.KEYDOWN and event.key in (
            pygame.K_RETURN,
            pygame.K_KP_ENTER,
        ):
            return BID if self.bid.enabled else None
        for button in self.raises:
            if button.handle_event(event):
                return None
        if self.bid.handle_event(event):
            return BID
        if self.pass_button.handle_event(event):
            return PASS
        return None

    def _fire(self, key: str) -> None:
        if self.on_close is not None:
            self.on_close(key)

    # --- drawing ------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        """Dim the board and draw the panel. A no-op with no auction."""
        auction = self._auction
        if auction is None:
            return
        self._draw_scrim(surface)
        pygame.draw.rect(surface, PANEL, self.rect, border_radius=10)
        pygame.draw.rect(surface, BORDER, self.rect, width=2, border_radius=10)

        deed = auction.deed
        chip = pygame.Rect(self.title_rect.left, self.title_rect.top + 4, 14, 24)
        pygame.draw.rect(surface, GROUP_COLORS.get(deed.group, BORDER), chip)
        font = get_font(24, bold=True)
        name = ellipsize(
            f"Auction -- {deed_label(deed)}", font, self.title_rect.width - 130
        )
        surface.blit(
            font.render(name, True, TEXT),
            (chip.right + 10, self.title_rect.top),
        )
        price = get_font(16).render(f"list ${deed.price}", True, TEXT_MUTED)
        surface.blit(
            price,
            price.get_rect(midright=(self.title_rect.right, self.title_rect.centery)),
        )

        status = get_font(16).render(summarise(auction), True, ACCENT)
        surface.blit(status, (self.status_rect.left, self.status_rect.top))

        self._draw_rows(surface, auction)
        self._draw_footer(surface, auction)

    def _draw_rows(self, surface: pygame.Surface, auction: Auction) -> None:
        for row, player in enumerate(auction.bidders[: self.visible_rows]):
            self._draw_row(surface, self.row_rect(row), auction, player)

    def _draw_row(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        auction: Auction,
        player: Player,
    ) -> None:
        out = auction.has_passed(player)
        pygame.draw.rect(
            surface, PANEL if out else PANEL_LIGHT, rect, border_radius=5
        )
        token = pygame.Rect(rect.left + 10, 0, 12, 12)
        token.centery = rect.centery
        pygame.draw.rect(surface, token_rgb(player), token)

        font = get_font(16)
        color = TEXT_MUTED if out else TEXT
        name = font.render(ellipsize(player.name, font, NAME_W), True, color)
        surface.blit(name, name.get_rect(midleft=(rect.left + NAME_X, rect.centery)))
        cash = get_font(15).render(f"${player.cash:,}", True, color)
        surface.blit(cash, cash.get_rect(midleft=(rect.left + CASH_X, rect.centery)))

        standing, standing_color = _standing(auction, player)
        if standing:
            text = get_font(15, bold=player is auction.high_bidder).render(
                standing, True, standing_color
            )
            surface.blit(
                text, text.get_rect(midleft=(rect.left + STATUS_X, rect.centery))
            )
        if player is auction.bidder:
            mark = get_font(18, bold=True).render(TURN_MARK, True, ACCENT)
            surface.blit(mark, mark.get_rect(midright=(rect.left + 8, rect.centery)))

    def _draw_footer(self, surface: pygame.Surface, auction: Auction) -> None:
        footer = self.footer_rect
        bidder = auction.bidder
        prompt = (
            f"{bidder.name} to bid -- at least ${auction.min_bid:,}"
            if bidder is not None
            else "The sale is over."
        )
        surface.blit(
            get_font(15).render(prompt, True, TEXT_MUTED), (footer.left, footer.top)
        )
        self.field.draw(surface)
        for button in self.raises:
            button.draw(surface)
        self.pass_button.draw(surface)
        self.bid.draw(surface)

    def _draw_scrim(self, surface: pygame.Surface) -> None:
        scrim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        scrim.fill((0, 0, 0, SCRIM_ALPHA))
        surface.blit(scrim, (0, 0))


def _standing(auction: Auction, player: Player) -> tuple[str, tuple[int, int, int]]:
    """The right-hand column for one bidder: their bid, or that they are out."""
    if auction.has_passed(player):
        return "passed", TEXT_MUTED
    if player is auction.high_bidder:
        return f"high ${auction.high_bid:,}", ACCENT
    return "in", TEXT_MUTED
