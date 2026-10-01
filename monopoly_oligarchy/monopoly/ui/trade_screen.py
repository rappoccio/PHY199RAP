"""Phase 11: the trade screen.

:class:`TradeScreen` draws the :class:`monopoly.trade.Trade` the game is
holding over a dimmed board. It shows whichever of the deal's three live
phases is current:

* **Choose a partner** -- one button per player still at the table. Skipped
  when there is only one of them, because :class:`~monopoly.trade.Trade` has
  already picked.
* **Draft** -- two columns, "You Offer" and "They Offer". Each has a cash
  field, a jail-card counter and a row per deed its owner holds, with a
  checkbox. Propose and Cancel sit below.
* **Review** -- the same two columns, now read-only, with Accept and Reject.

Like the HUD, the popup, the build screen and the auction screen **it decides
nothing.** Every checkbox click is a call to
:meth:`~monopoly.trade.Trade.toggle`, which refuses anything the rules forbid;
the screen only asks :meth:`~monopoly.trade.Trade.can_offer` which rows may be
clicked, :func:`row_flags` how each one should read, and
:meth:`~monopoly.trade.Trade.is_valid` whether Propose and Accept should be
live. :meth:`TradeScreen.handle_event` reports :data:`PROPOSE`,
:data:`ACCEPT`, :data:`REJECT` or :data:`CANCEL`, and ``main`` turns that into
the matching :class:`monopoly.game.Game` call.

The one place the screen shapes what is typed rather than reporting it is the
cash field: an amount beyond the player's cash is **clamped**, so what is on
screen is always exactly what is on the table.
"""

from __future__ import annotations

from typing import Callable, Optional

import pygame

from monopoly.player import Player
from monopoly.property import Property
from monopoly.trade import (
    DRAFT,
    PARTNER,
    REVIEW,
    Offer,
    Trade,
    describe,
    group_is_bare,
)
from monopoly.ui.button import Button
from monopoly.ui.hud import deed_label, token_rgb
from monopoly.ui.text_input import TextInput
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

#: What :meth:`TradeScreen.handle_event` reports for the four closing moves.
PROPOSE = "propose"
ACCEPT = "accept"
REJECT = "reject"
CANCEL = "cancel"

#: The box, centred over the 800x800 board.
SCREEN_SIZE = (740, 700)
SCREEN_CENTER = (400, 400)

PAD = 20

TITLE_H = 30
STATUS_H = 22

FOOTER_H = 52
BUTTON_H = 44
BUTTON_W = 150
BUTTON_GAP = 14

#: The two columns and the gutter between them.
COLUMN_GAP = 16
COLUMN_HEAD_H = 24

#: The cash field and the jail-card counter above each deed list.
FIELD_W = 150
FIELD_H = 32
GOOJF_H = 26
GOOJF_STEP_W = 26
BLOCK_GAP = 6

#: One deed row, and the checkbox at its left.
ROW_H = 26
ROW_GAP = 3
BOX_SIZE = 14
BOX_X = 6
CHIP_W = 8
NAME_X = 40

#: One partner button in the opening phase.
PARTNER_H = 44
PARTNER_GAP = 8

#: Badges drawn at the right of a deed row.
MORTGAGE_BADGE = "MTG"
BUILT_BADGE = "BUILT"

#: How dark the board goes behind the screen (0-255).
SCRIM_ALPHA = 165

EMPTY_TEXT = "(no deeds)"


class TradeScreen:
    """A modal trade panel: a partner list, then two columns and two buttons."""

    def __init__(
        self,
        rect: Optional[pygame.Rect | tuple[int, int, int, int]] = None,
        *,
        trade: Optional[Trade] = None,
        on_close: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.rect = (
            pygame.Rect(rect) if rect is not None else pygame.Rect((0, 0), SCREEN_SIZE)
        )
        if rect is None:
            self.rect.center = SCREEN_CENTER
        self.on_close = on_close
        self._trade: Optional[Trade] = None
        self._shown: Optional[tuple[int, str]] = None
        self._pointer: Optional[tuple[int, int]] = None

        #: Per column (0 = the proposer, 1 = the partner).
        self.scroll = [0, 0]
        self.fields: list[TextInput] = [
            TextInput(
                self.cash_rect(i), placeholder="0", digits_only=True, max_length=7
            )
            for i in range(2)
        ]
        self.goojf_buttons: dict[tuple[int, bool], Button] = {}
        self.rows: list[tuple[int, Property, pygame.Rect]] = []
        self.partner_buttons: list[Button] = []
        self.primary = self._closing_button(PROPOSE, "Propose", primary=True)
        self.secondary = self._closing_button(CANCEL, "Cancel")
        self.trade = trade

    # --- state --------------------------------------------------------------
    @property
    def trade(self) -> Optional[Trade]:
        return self._trade

    @trade.setter
    def trade(self, value: Optional[Trade]) -> None:
        """Show ``value`` (or nothing), rebuilding every widget to match."""
        self._trade = value
        self._shown = None
        self.scroll = [0, 0]
        self.sync()

    @property
    def visible(self) -> bool:
        return self._trade is not None

    @property
    def phase(self) -> Optional[str]:
        return self._trade.phase if self._trade is not None else None

    def sync(self) -> None:
        """Follow the deal, rebuilding whenever it moves to another phase.

        Called every frame: Propose is what carries the same trade from its
        draft to the partner's review, and the whole footer changes with it.
        """
        trade = self._trade
        mark = (id(trade), trade.phase) if trade is not None else None
        if mark != self._shown:
            self._shown = mark
            self.scroll = [0, 0]
            self._refill_fields()
        self.refresh()

    def _refill_fields(self) -> None:
        """Put each side's offered cash back into its field."""
        for i, field in enumerate(self.fields):
            side = self.side(i)
            field.text = str(side.cash) if side is not None and side.cash else ""
            field.focused = False

    def side(self, column: int) -> Optional[Offer]:
        """The :class:`~monopoly.trade.Offer` shown in ``column``, if any."""
        trade = self._trade
        if trade is None:
            return None
        sides = trade.sides
        return sides[column] if column < len(sides) else None

    def player(self, column: int) -> Optional[Player]:
        side = self.side(column)
        return side.player if side is not None else None

    def refresh(self) -> None:
        """Rebuild the rows and re-check which widgets are live.

        Called after every edit, because one click changes what the rest of
        the panel may do: a deed on the table can make an empty offer a legal
        one, and Propose lights up with it.
        """
        trade = self._trade
        self.rows = []
        self.goojf_buttons = {}
        self.partner_buttons = []
        if trade is None:
            self.primary.enabled = False
            return

        if trade.phase == PARTNER:
            self._build_partner_buttons(trade)
        else:
            self._build_columns(trade)
        self._build_footer(trade)

    def _build_partner_buttons(self, trade: Trade) -> None:
        for i, player in enumerate(trade.candidates):
            self.partner_buttons.append(
                Button(
                    self.partner_rect(i),
                    f"{player.name}   ${player.cash:,}   "
                    f"{len(trade.holdings(player))} deeds",
                    font_size=18,
                    on_click=lambda p=player: self._choose(p),
                )
            )

    def _build_columns(self, trade: Trade) -> None:
        editable = trade.editable
        for column in range(2):
            player = self.player(column)
            if player is None:
                continue
            field = self.fields[column]
            field.rect = self.cash_rect(column)
            for plus in (False, True):
                legal = self._goojf_step(trade, player, plus) is not None
                self.goojf_buttons[(column, plus)] = Button(
                    self.goojf_step_rect(column, plus),
                    "+" if plus else "-",
                    enabled=editable and legal,
                    font_size=18,
                    on_click=lambda c=column, p=plus: self._step_goojf(c, p),
                )
            self._build_rows(trade, column, player)

    def _build_rows(self, trade: Trade, column: int, player: Player) -> None:
        deeds = trade.holdings(player)
        self.scroll[column] = max(0, min(self.scroll[column], self.max_scroll(column)))
        start = self.scroll[column]
        for i, deed in enumerate(deeds[start : start + self.visible_rows]):
            self.rows.append((column, deed, self.row_rect(column, i)))

    def _build_footer(self, trade: Trade) -> None:
        if trade.phase == REVIEW:
            self.primary.label, self.secondary.label = "Accept", "Reject"
            self.primary.enabled = trade.is_valid
        else:
            self.primary.label, self.secondary.label = "Propose", "Cancel"
            self.primary.enabled = trade.phase == DRAFT and trade.is_valid
        self.secondary.enabled = True

    @staticmethod
    def _goojf_step(trade: Trade, player: Player, plus: bool) -> Optional[int]:
        """The count a ``+``/``-`` click would set, or ``None`` if it cannot."""
        side = trade.offer(player)
        count = side.goojf + (1 if plus else -1)
        if count < 0 or count > player.goojf_cards:
            return None
        return count

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
            self.title_rect.bottom,
            self.rect.width - 2 * PAD,
            STATUS_H,
        )

    @property
    def footer_rect(self) -> pygame.Rect:
        """The strip along the bottom: a note and the two buttons."""
        return pygame.Rect(
            self.rect.left + PAD,
            self.rect.bottom - PAD - FOOTER_H,
            self.rect.width - 2 * PAD,
            FOOTER_H,
        )

    @property
    def body_rect(self) -> pygame.Rect:
        """Everything between the status line and the footer."""
        top = self.status_rect.bottom + 8
        return pygame.Rect(
            self.rect.left + PAD,
            top,
            self.rect.width - 2 * PAD,
            self.footer_rect.top - 10 - top,
        )

    @property
    def column_width(self) -> int:
        return (self.body_rect.width - COLUMN_GAP) // 2

    def column_rect(self, column: int) -> pygame.Rect:
        """One whole column of the two-column view."""
        body = self.body_rect
        width = self.column_width
        return pygame.Rect(
            body.left + column * (width + COLUMN_GAP), body.top, width, body.height
        )

    def cash_rect(self, column: int) -> pygame.Rect:
        col = self.column_rect(column)
        return pygame.Rect(
            col.left, col.top + COLUMN_HEAD_H + BLOCK_GAP, FIELD_W, FIELD_H
        )

    def goojf_rect(self, column: int) -> pygame.Rect:
        cash = self.cash_rect(column)
        col = self.column_rect(column)
        return pygame.Rect(col.left, cash.bottom + BLOCK_GAP, col.width, GOOJF_H)

    def goojf_step_rect(self, column: int, plus: bool) -> pygame.Rect:
        """The ``-`` / ``+`` squares of a column's jail-card counter."""
        row = self.goojf_rect(column)
        x = row.right - GOOJF_STEP_W if plus else row.right - 2 * GOOJF_STEP_W - 4
        return pygame.Rect(x, row.top, GOOJF_STEP_W, row.height)

    def list_rect(self, column: int) -> pygame.Rect:
        """The deed rows of one column, below its cash and card lines."""
        col = self.column_rect(column)
        top = self.goojf_rect(column).bottom + BLOCK_GAP
        return pygame.Rect(col.left, top, col.width, col.bottom - top)

    def row_rect(self, column: int, row: int) -> pygame.Rect:
        """The ``row``-th *visible* deed row of ``column``."""
        window = self.list_rect(column)
        return pygame.Rect(
            window.left, window.top + row * (ROW_H + ROW_GAP), window.width, ROW_H
        )

    @property
    def visible_rows(self) -> int:
        """How many deed rows fit one column's list window."""
        return max(0, (self.list_rect(0).height + ROW_GAP) // (ROW_H + ROW_GAP))

    def max_scroll(self, column: int) -> int:
        """The largest scroll offset for ``column`` that still fills its window."""
        trade = self._trade
        player = self.player(column)
        if trade is None or player is None:
            return 0
        return max(0, len(trade.holdings(player)) - self.visible_rows)

    def scroll_by(self, column: int, rows: int) -> None:
        """Scroll one column's deed list, clamped to its ends."""
        scroll = max(0, min(self.max_scroll(column), self.scroll[column] + rows))
        if scroll != self.scroll[column]:
            self.scroll[column] = scroll
            self.refresh()

    def partner_rect(self, i: int) -> pygame.Rect:
        """The ``i``-th candidate's button in the opening phase."""
        body = self.body_rect
        return pygame.Rect(
            body.left, body.top + i * (PARTNER_H + PARTNER_GAP), body.width, PARTNER_H
        )

    def box_rect(self, rect: pygame.Rect) -> pygame.Rect:
        """The checkbox inside a deed row's rectangle."""
        return pygame.Rect(
            rect.left + BOX_X, rect.centery - BOX_SIZE // 2, BOX_SIZE, BOX_SIZE
        )

    def chip_rect(self, rect: pygame.Rect) -> pygame.Rect:
        """The group-colour chip between a row's checkbox and its name."""
        box = self.box_rect(rect)
        return pygame.Rect(box.right + 6, rect.top + 4, CHIP_W, rect.height - 8)

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
        """Advance the cash fields' caret blink."""
        for field in self.fields:
            field.update(now_ms)

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Dispatch one event; return a closing key or ``None``.

        Picking a partner, typing cash, nudging the jail-card counter and
        ticking a deed all report ``None``: the screen stays open until one of
        the two footer buttons is pressed.
        """
        trade = self._trade
        if trade is None:
            return None
        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
            self._pointer = event.pos
        if event.type == pygame.MOUSEWHEEL:
            self._wheel(getattr(event, "y", 0))
            return None
        if trade.phase == PARTNER:
            for button in self.partner_buttons:
                if button.handle_event(event):
                    return None
            return self._footer_event(event)
        if trade.editable:
            if self._cash_event(event):
                return None
            for button in self.goojf_buttons.values():
                if button.handle_event(event):
                    return None
            if self._row_event(event):
                return None
        return self._footer_event(event)

    def _footer_event(self, event: pygame.event.Event) -> Optional[str]:
        trade = self._trade
        assert trade is not None
        if self.primary.handle_event(event):
            return ACCEPT if trade.phase == REVIEW else PROPOSE
        if self.secondary.handle_event(event):
            return REJECT if trade.phase == REVIEW else CANCEL
        return None

    def _cash_event(self, event: pygame.event.Event) -> bool:
        """Let the two cash fields see ``event``, then put what they hold up."""
        consumed = False
        for column, field in enumerate(self.fields):
            if self.player(column) is None:
                continue
            if field.handle_event(event):
                self._apply_cash(column)
                consumed = True
        return consumed

    def _apply_cash(self, column: int) -> None:
        """Offer whatever is typed, clamping it to the cash actually in hand."""
        trade = self._trade
        player = self.player(column)
        if trade is None or player is None:
            return
        field = self.fields[column]
        typed = int(field.value) if field.value.isdigit() else 0
        amount = min(typed, player.cash)
        trade.set_cash(player, amount)
        if amount != typed:
            field.text = str(amount)
        self.refresh()

    def _step_goojf(self, column: int, plus: bool) -> None:
        trade = self._trade
        player = self.player(column)
        if trade is None or player is None:
            return
        count = self._goojf_step(trade, player, plus)
        if count is not None:
            trade.set_goojf(player, count)
        self.refresh()

    def _row_event(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.MOUSEBUTTONDOWN or getattr(event, "button", 0) != 1:
            return False
        trade = self._trade
        assert trade is not None
        for _column, deed, rect in self.rows:
            if rect.collidepoint(event.pos):
                if not trade.can_offer(deed):
                    return True  # a dead row still swallows its own click
                trade.toggle(deed)
                self.refresh()
                return True
        return False

    def _wheel(self, y: int) -> None:
        """Scroll the column under the pointer, or both when it is elsewhere."""
        if self._trade is None or self._trade.phase == PARTNER:
            return
        under = [
            column
            for column in range(2)
            if self._pointer is not None
            and self.list_rect(column).collidepoint(self._pointer)
        ]
        for column in under or [0, 1]:
            self.scroll_by(column, -y)

    def _choose(self, player: Player) -> None:
        trade = self._trade
        if trade is not None and trade.choose_partner(player):
            self.sync()

    def _fire(self, key: str) -> None:
        if self.on_close is not None:
            self.on_close(key)

    # --- drawing ------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        """Dim the board and draw the panel. A no-op with no trade."""
        trade = self._trade
        if trade is None:
            return
        self._draw_scrim(surface)
        pygame.draw.rect(surface, PANEL, self.rect, border_radius=10)
        pygame.draw.rect(surface, BORDER, self.rect, width=2, border_radius=10)

        title = get_font(26, bold=True).render(_title(trade), True, TEXT)
        surface.blit(title, (self.title_rect.left, self.title_rect.top))

        note, color = _status(trade)
        status = get_font(15).render(
            ellipsize(note, get_font(15), self.status_rect.width), True, color
        )
        surface.blit(status, (self.status_rect.left, self.status_rect.top))

        if trade.phase == PARTNER:
            for button in self.partner_buttons:
                button.draw(surface)
        else:
            for column in range(2):
                if self.player(column) is not None:
                    self._draw_column(surface, trade, column)
        self._draw_footer(surface, trade)

    def _draw_column(
        self, surface: pygame.Surface, trade: Trade, column: int
    ) -> None:
        col = self.column_rect(column)
        pygame.draw.rect(surface, PANEL_LIGHT, col, border_radius=8)
        side = self.side(column)
        assert side is not None
        player = side.player

        head = pygame.Rect(col.left, col.top, col.width, COLUMN_HEAD_H)
        token = pygame.Rect(head.left + 8, head.centery - 6, 12, 12)
        pygame.draw.rect(surface, token_rgb(player), token)
        font = get_font(16, bold=True)
        label = f"{'You' if column == 0 else 'They'} Offer -- {player.name}"
        text = font.render(ellipsize(label, font, col.width - 40), True, TEXT)
        surface.blit(text, text.get_rect(midleft=(token.right + 8, head.centery)))

        self.fields[column].draw(surface)
        field = self.cash_rect(column)
        cash = get_font(13).render(f"of ${player.cash:,}", True, TEXT_MUTED)
        surface.blit(
            cash, cash.get_rect(midleft=(field.right + 8, field.centery))
        )
        self._draw_goojf(surface, column, side, player)
        self._draw_rows(surface, trade, column, player)

    def _draw_goojf(
        self, surface: pygame.Surface, column: int, side: Offer, player: Player
    ) -> None:
        row = self.goojf_rect(column)
        color = TEXT if player.goojf_cards else TEXT_MUTED
        label = get_font(14).render(
            f"Jail cards: {side.goojf} of {player.goojf_cards}", True, color
        )
        surface.blit(label, label.get_rect(midleft=(row.left + 4, row.centery)))
        for plus in (False, True):
            button = self.goojf_buttons.get((column, plus))
            if button is not None:
                button.draw(surface)

    def _draw_rows(
        self, surface: pygame.Surface, trade: Trade, column: int, player: Player
    ) -> None:
        rows = [r for r in self.rows if r[0] == column]
        if not rows:
            note = get_font(14).render(EMPTY_TEXT, True, TEXT_MUTED)
            window = self.list_rect(column)
            surface.blit(note, (window.left + 6, window.top + 4))
            return
        for _column, deed, rect in rows:
            self._draw_row(surface, trade, rect, deed)

    def _draw_row(
        self,
        surface: pygame.Surface,
        trade: Trade,
        rect: pygame.Rect,
        deed: Property,
    ) -> None:
        live, ticked = row_flags(trade, deed)
        pygame.draw.rect(surface, PANEL, rect, border_radius=4)

        box = self.box_rect(rect)
        pygame.draw.rect(surface, ACCENT if ticked else BORDER, box, border_radius=3)
        if ticked:
            pygame.draw.rect(surface, PANEL, box.inflate(-6, -6), border_radius=2)

        chip = self.chip_rect(rect)
        pygame.draw.rect(surface, GROUP_COLORS.get(deed.group, BORDER), chip)

        badge, badge_color = _badge(deed, live)
        font = get_font(14)
        width = rect.width - NAME_X - (font.size(badge)[0] + 12 if badge else 8)
        name = font.render(
            ellipsize(deed_label(deed), font, width),
            True,
            TEXT if live else TEXT_MUTED,
        )
        surface.blit(name, name.get_rect(midleft=(rect.left + NAME_X, rect.centery)))
        if badge:
            text = get_font(12, bold=True).render(badge, True, badge_color)
            surface.blit(
                text, text.get_rect(midright=(rect.right - 6, rect.centery))
            )

    def _draw_footer(self, surface: pygame.Surface, trade: Trade) -> None:
        footer = self.footer_rect
        font = get_font(13)
        note = ellipsize(describe(trade), font, footer.width - 2 * BUTTON_W - 40)
        surface.blit(font.render(note, True, TEXT_MUTED), (footer.left, footer.top))
        self.secondary.draw(surface)
        self.primary.draw(surface)

    def _draw_scrim(self, surface: pygame.Surface) -> None:
        scrim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        scrim.fill((0, 0, 0, SCRIM_ALPHA))
        surface.blit(scrim, (0, 0))


def row_flags(trade: Trade, deed: Property) -> tuple[bool, bool]:
    """``(tradable, on the table)`` for one deed row.

    Deliberately *not* :meth:`~monopoly.trade.Trade.can_offer`: that also goes
    false the moment the offer is out, and a read-only review should still
    show which lots are mortgaged and which are stuck behind houses rather
    than flag every one of them as built on.
    """
    return group_is_bare(deed, trade.properties), trade.is_offered(deed)


def _title(trade: Trade) -> str:
    """The panel's heading for whichever phase the deal is in."""
    if trade.phase == PARTNER:
        return f"Trade -- who with, {trade.proposer.name}?"
    if trade.phase == REVIEW:
        return f"Offer to {trade.partner.name}"
    return f"Trade -- {trade.proposer.name}"


def _status(trade: Trade) -> tuple[str, tuple[int, int, int]]:
    """The line under the heading: what is wrong, or what happens next."""
    if trade.phase == PARTNER:
        return "Choose somebody to trade with.", TEXT_MUTED
    problems = trade.problems()
    if problems:
        return problems[0], DANGER
    if trade.phase == REVIEW:
        return f"{trade.partner.name}: accept or reject the offer.", ACCENT
    return "Ready to propose.", ACCENT


def _badge(deed: Property, live: bool) -> tuple[str, tuple[int, int, int]]:
    """The tag at the right of a deed row: mortgaged, or built on and stuck."""
    if not live:
        return BUILT_BADGE, TEXT_MUTED
    if deed.mortgaged:
        return MORTGAGE_BADGE, DANGER
    return "", TEXT_MUTED
