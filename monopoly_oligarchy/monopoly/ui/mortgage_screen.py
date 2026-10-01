"""Phase 12: the mortgage screen.

:class:`MortgageScreen` draws a :class:`monopoly.mortgage.MortgageLedger` over
a dimmed board: one row per deed the player owns, in board order, each with its
group chip, its status and one button -- ``Mortgage`` on a free lot, ``Lift`` on
a mortgaged one. Below them sit the running total and the Confirm / Cancel
buttons.

Like the build screen **it decides nothing.** Every click is a call to
:meth:`~monopoly.mortgage.MortgageLedger.toggle`, which refuses anything the
bare-group rule or the player's cash forbids; the screen only asks
:meth:`~monopoly.mortgage.MortgageLedger.can_toggle` which of its buttons to
draw live and :meth:`~monopoly.mortgage.MortgageLedger.blocker` what to print
beside a dark one. :meth:`MortgageScreen.handle_event` returns :data:`CONFIRM`
or :data:`CANCEL` when one of those two is pressed, and ``main`` turns that
into :meth:`monopoly.game.Game.close_mortgage`.
"""

from __future__ import annotations

from typing import Callable, Optional

import pygame

from monopoly.mortgage import MortgageLedger, describe
from monopoly.property import Property
from monopoly.ui.button import Button
from monopoly.ui.hud import deed_label
from monopoly.ui.theme import (
    ACCENT,
    BORDER,
    DANGER,
    GROUP_COLORS,
    PANEL,
    PANEL_LIGHT,
    TEXT,
    TEXT_MUTED,
    ellipsize,
    get_font,
)

#: What :meth:`MortgageScreen.handle_event` reports for the two closing buttons.
CONFIRM = "confirm"
CANCEL = "cancel"

#: The box, centred over the 800x800 board.
SCREEN_SIZE = (640, 700)
SCREEN_CENTER = (400, 400)

PAD = 22

TITLE_H = 30
SUBTITLE_H = 22
ROW_H = 34
ROW_GAP = 4

FOOTER_H = 52
BUTTON_H = 44
BUTTON_W = 150
BUTTON_GAP = 14

#: The toggle button at the right of a deed row.
TOGGLE_W = 96

#: Columns inside a row, as offsets from its left edge. Fixed, so a long name
#: is cut rather than drawn over its status.
CHIP_W = 8
NAME_X = 16
NAME_W = 210
STATUS_X = 238

#: What a row's toggle button says, and what its status column prints.
MORTGAGE_LABEL = "Mortgage"
LIFT_LABEL = "Lift"
MORTGAGED_STATUS = "mortgaged"
FREE_STATUS = "free"

#: How dark the board goes behind the screen (0-255).
SCRIM_ALPHA = 165

EMPTY_TEXT = "No deeds to mortgage."


class MortgageScreen:
    """A modal mortgage panel: one row per deed, a total, Confirm / Cancel."""

    def __init__(
        self,
        rect: Optional[pygame.Rect | tuple[int, int, int, int]] = None,
        *,
        ledger: Optional[MortgageLedger] = None,
        on_close: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.rect = (
            pygame.Rect(rect) if rect is not None else pygame.Rect((0, 0), SCREEN_SIZE)
        )
        if rect is None:
            self.rect.center = SCREEN_CENTER
        self.on_close = on_close
        self._ledger: Optional[MortgageLedger] = None
        self.deeds: list[Property] = []
        self.scroll = 0
        self.toggles: dict[int, Button] = {}
        self.confirm = self._closing_button(CONFIRM, "Confirm", primary=True)
        self.cancel = self._closing_button(CANCEL, "Cancel")
        self.ledger = ledger

    # --- state --------------------------------------------------------------
    @property
    def ledger(self) -> Optional[MortgageLedger]:
        return self._ledger

    @ledger.setter
    def ledger(self, value: Optional[MortgageLedger]) -> None:
        """Show ``value`` (or nothing), rebuilding every row to match."""
        self._ledger = value
        self.scroll = 0
        self.refresh()

    @property
    def visible(self) -> bool:
        return self._ledger is not None

    def refresh(self) -> None:
        """Rebuild the rows and re-check which buttons are live.

        Called after every click, because one of them changes what the *other*
        rows may do: mortgaging a lot is what pays for lifting the next one.
        """
        ledger = self._ledger
        self.deeds = [] if ledger is None else list(ledger.deeds)
        self.toggles = {}
        if ledger is None:
            self.confirm.enabled = False
            return
        self.scroll = max(0, min(self.scroll, self.max_scroll))
        for i in self.visible_rows:
            deed = self.deeds[i]
            self.toggles[i] = Button(
                self.toggle_rect(i),
                LIFT_LABEL if ledger.state(deed) else MORTGAGE_LABEL,
                enabled=ledger.can_toggle(deed),
                font_size=15,
                on_click=lambda d=deed: self._toggle(d),
            )
        self.confirm.enabled = ledger.changed

    # --- layout -------------------------------------------------------------
    @property
    def title_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.rect.left + PAD, self.rect.top + PAD, self.rect.width - 2 * PAD, TITLE_H
        )

    @property
    def subtitle_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.rect.left + PAD,
            self.title_rect.bottom,
            self.rect.width - 2 * PAD,
            SUBTITLE_H,
        )

    @property
    def footer_rect(self) -> pygame.Rect:
        """The strip along the bottom: the total and the two buttons."""
        return pygame.Rect(
            self.rect.left + PAD,
            self.rect.bottom - PAD - FOOTER_H,
            self.rect.width - 2 * PAD,
            FOOTER_H,
        )

    @property
    def list_rect(self) -> pygame.Rect:
        """Everything between the subtitle and the footer."""
        top = self.subtitle_rect.bottom + 8
        return pygame.Rect(
            self.rect.left + PAD,
            top,
            self.rect.width - 2 * PAD,
            self.footer_rect.top - 10 - top,
        )

    def row_rect(self, row: int) -> pygame.Rect:
        """The rectangle of the ``row``-th deed, measured from :attr:`scroll`.

        A row above the window comes back with a negative top and simply falls
        outside :attr:`list_rect`.
        """
        y = self.list_rect.top + (row - self.scroll) * (ROW_H + ROW_GAP)
        return pygame.Rect(self.list_rect.left, y, self.list_rect.width, ROW_H)

    @property
    def rows_per_page(self) -> int:
        """How many whole rows the list window holds."""
        return max(1, (self.list_rect.height + ROW_GAP) // (ROW_H + ROW_GAP))

    @property
    def visible_rows(self) -> list[int]:
        """Every deed index that fits the window at the current scroll.

        Buttons are only built for these, so a row scrolled out of sight
        cannot be clicked by accident.
        """
        last = min(len(self.deeds), self.scroll + self.rows_per_page)
        return list(range(self.scroll, last))

    @property
    def max_scroll(self) -> int:
        """The largest scroll offset that still fills the window."""
        return max(0, len(self.deeds) - self.rows_per_page)

    def scroll_by(self, rows: int) -> None:
        """Scroll the list, clamped to its ends, and rebuild the buttons."""
        scroll = max(0, min(self.max_scroll, self.scroll + rows))
        if scroll != self.scroll:
            self.scroll = scroll
            self.refresh()

    def toggle_rect(self, row: int) -> pygame.Rect:
        """The Mortgage / Lift button at the right of a deed row."""
        rect = self.row_rect(row)
        return pygame.Rect(
            rect.right - TOGGLE_W, rect.top + 3, TOGGLE_W, rect.height - 6
        )

    def _closing_button(self, key: str, label: str, *, primary: bool = False) -> Button:
        footer = self.footer_rect
        right = footer.right if primary else footer.right - BUTTON_W - BUTTON_GAP
        x = right - BUTTON_W
        return Button(
            (x, footer.bottom - BUTTON_H, BUTTON_W, BUTTON_H),
            label,
            primary=primary,
            font_size=20,
            on_click=lambda k=key: self._fire(k),
        )

    # --- events -------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Dispatch one event; return :data:`CONFIRM` / :data:`CANCEL` or ``None``.

        A row click edits the draft in place and reports ``None``: the screen
        stays open until one of the two footer buttons is pressed.
        """
        if self._ledger is None:
            return None
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_by(-getattr(event, "y", 0))
            return None
        for button in list(self.toggles.values()):
            if button.handle_event(event):
                return None
        if self.confirm.handle_event(event):
            return CONFIRM
        if self.cancel.handle_event(event):
            return CANCEL
        return None

    def _toggle(self, deed: Property) -> None:
        ledger = self._ledger
        if ledger is None:
            return
        ledger.toggle(deed)
        self.refresh()

    def _fire(self, key: str) -> None:
        if self.on_close is not None:
            self.on_close(key)

    # --- drawing ------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        """Dim the board and draw the panel. A no-op with no ledger."""
        ledger = self._ledger
        if ledger is None:
            return
        self._draw_scrim(surface)
        pygame.draw.rect(surface, PANEL, self.rect, border_radius=10)
        pygame.draw.rect(surface, BORDER, self.rect, width=2, border_radius=10)

        title = get_font(26, bold=True).render(
            f"Mortgage -- {ledger.player.name}", True, TEXT
        )
        surface.blit(title, (self.title_rect.left, self.title_rect.top))
        cash = get_font(20, bold=True).render(f"${ledger.player.cash:,}", True, ACCENT)
        surface.blit(
            cash,
            cash.get_rect(midright=(self.title_rect.right, self.title_rect.centery)),
        )

        note = get_font(14).render(_subtitle(ledger), True, TEXT_MUTED)
        surface.blit(note, (self.subtitle_rect.left, self.subtitle_rect.top))

        if ledger.is_empty:
            empty = get_font(16).render(EMPTY_TEXT, True, TEXT_MUTED)
            surface.blit(empty, (self.list_rect.left, self.list_rect.top + 6))
        else:
            self._draw_rows(surface, ledger)
        self._draw_footer(surface, ledger)

    def _draw_rows(self, surface: pygame.Surface, ledger: MortgageLedger) -> None:
        for i in self.visible_rows:
            self._draw_row(surface, self.row_rect(i), ledger, self.deeds[i])
            if i in self.toggles:
                self.toggles[i].draw(surface)

    def _draw_row(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        ledger: MortgageLedger,
        deed: Property,
    ) -> None:
        pygame.draw.rect(surface, PANEL_LIGHT, rect, border_radius=5)
        chip = pygame.Rect(rect.left, rect.top + 4, CHIP_W, rect.height - 8)
        pygame.draw.rect(surface, GROUP_COLORS[deed.group], chip)

        mortgaged = ledger.state(deed)
        font = get_font(16)
        label = ellipsize(deed_label(deed), font, NAME_W)
        name = font.render(label, True, TEXT_MUTED if mortgaged else TEXT)
        surface.blit(name, name.get_rect(midleft=(rect.left + NAME_X, rect.centery)))

        text, color = _status(ledger, deed)
        status = get_font(13).render(text, True, color)
        surface.blit(
            status, status.get_rect(midleft=(rect.left + STATUS_X, rect.centery))
        )

    def _draw_footer(self, surface: pygame.Surface, ledger: MortgageLedger) -> None:
        footer = self.footer_rect
        font = get_font(13)
        summary = ellipsize(describe(ledger), font, footer.width - 2 * BUTTON_W - 40)
        surface.blit(font.render(summary, True, TEXT_MUTED), (footer.left, footer.top))
        color = DANGER if ledger.charge else (ACCENT if ledger.refund else TEXT_MUTED)
        total = get_font(18, bold=True).render(_total_text(ledger), True, color)
        surface.blit(total, (footer.left, footer.top + 22))
        self.cancel.draw(surface)
        self.confirm.draw(surface)

    def _draw_scrim(self, surface: pygame.Surface) -> None:
        scrim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        scrim.fill((0, 0, 0, SCRIM_ALPHA))
        surface.blit(scrim, (0, 0))


def _status(
    ledger: MortgageLedger, deed: Property
) -> tuple[str, tuple[int, int, int]]:
    """The middle column of a row: the price, or why the row is dark."""
    blocker = ledger.blocker(deed)
    if blocker is not None:
        return blocker, TEXT_MUTED
    if ledger.state(deed):
        return f"{MORTGAGED_STATUS} -- lift for ${deed.unmortgage_cost:,}", DANGER
    return f"{FREE_STATUS} -- raises ${deed.mortgage_value:,}", TEXT_MUTED


def _subtitle(ledger: MortgageLedger) -> str:
    """The line under the heading: what the draft has done so far."""
    if not ledger.changed:
        return "Mortgage a deed to raise cash, or pay 110% to lift one."
    return f"raising ${ledger.proceeds:,}, owing ${ledger.interest:,}"


def _total_text(ledger: MortgageLedger) -> str:
    if ledger.charge:
        return f"-${ledger.charge:,}"
    if ledger.refund:
        return f"+${ledger.refund:,}"
    return "$0"
