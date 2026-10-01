"""Phase 9: the build screen.

:class:`BuildScreen` draws a :class:`monopoly.building.BuildPlan` over a dimmed
board: one block per colour group the player holds whole, one row per lot, and
a ``-`` / ``+`` pair on each row. Below them sit the running total and the
Confirm / Cancel buttons.

Like the HUD and the popup **it decides nothing.** Every ``+`` click is a call
to :meth:`~monopoly.building.BuildPlan.add`, which refuses anything the even-
build rule, the bank's supply or the player's cash forbids; the screen only
asks :meth:`~monopoly.building.BuildPlan.can_add` which of its buttons to draw
live. :meth:`BuildScreen.handle_event` returns :data:`CONFIRM` or
:data:`CANCEL` when one of those two is pressed, and ``main`` turns that into
:meth:`monopoly.game.Game.close_build`.
"""

from __future__ import annotations

from typing import Callable, Optional

import pygame

from monopoly.building import BuildPlan, describe_plan
from monopoly.property import HOTEL_LEVEL
from monopoly.ui.button import Button
from monopoly.ui.hud import deed_label
from monopoly.ui.theme import (
    ACCENT,
    BORDER,
    DANGER,
    GROUP_COLORS,
    HOTEL_COLOR,
    HOUSE_COLOR,
    PANEL,
    PANEL_LIGHT,
    TEXT,
    TEXT_MUTED,
    ellipsize,
    get_font,
)

#: What :meth:`BuildScreen.handle_event` reports for the two closing buttons.
CONFIRM = "confirm"
CANCEL = "cancel"

#: The box, centred over the 800x800 board.
SCREEN_SIZE = (640, 700)
SCREEN_CENTER = (400, 400)

PAD = 22

TITLE_H = 30
SUPPLY_H = 22
GROUP_H = 22
ROW_H = 34
ROW_GAP = 4
GROUP_GAP = 10

FOOTER_H = 52
BUTTON_H = 44
BUTTON_W = 150
BUTTON_GAP = 14

#: The square +/- buttons at the right of a lot row.
STEP_W = 34

#: Columns inside a lot row, as offsets from its left edge: the name, then the
#: buildings. Fixed, so a long name is cut rather than drawn over its houses.
NAME_X = 10
NAME_W = 250
BUILDINGS_X = 272

#: Building markers drawn on a row.
ROW_HOUSE = 10
ROW_HOTEL = (22, 12)

#: How dark the board goes behind the screen (0-255).
SCRIM_ALPHA = 165

EMPTY_TEXT = "No complete, unmortgaged colour group to build on."


class BuildScreen:
    """A modal building panel: group blocks, +/- per lot, Confirm / Cancel."""

    def __init__(
        self,
        rect: Optional[pygame.Rect | tuple[int, int, int, int]] = None,
        *,
        plan: Optional[BuildPlan] = None,
        on_close: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.rect = (
            pygame.Rect(rect) if rect is not None else pygame.Rect((0, 0), SCREEN_SIZE)
        )
        if rect is None:
            self.rect.center = SCREEN_CENTER
        self.on_close = on_close
        self._plan: Optional[BuildPlan] = None
        self.rows: list[tuple[str, object]] = []
        self.scroll = 0
        self.add_buttons: dict[int, Button] = {}
        self.remove_buttons: dict[int, Button] = {}
        self.confirm = self._closing_button(CONFIRM, "Confirm", primary=True)
        self.cancel = self._closing_button(CANCEL, "Cancel")
        self.plan = plan

    # --- state --------------------------------------------------------------
    @property
    def plan(self) -> Optional[BuildPlan]:
        return self._plan

    @plan.setter
    def plan(self, value: Optional[BuildPlan]) -> None:
        """Show ``value`` (or nothing), rebuilding every row to match."""
        self._plan = value
        self.scroll = 0
        self.refresh()

    @property
    def visible(self) -> bool:
        return self._plan is not None

    def refresh(self) -> None:
        """Rebuild the rows and re-check which buttons are live.

        Called after every edit, because one click changes what the *other*
        lots may do: a house on the cheapest lot of a group unlocks its
        neighbours and may empty the bank for everybody.
        """
        plan = self._plan
        self.rows = [] if plan is None else _rows_for(plan)
        self.add_buttons = {}
        self.remove_buttons = {}
        if plan is None:
            self.confirm.enabled = False
            return
        self.scroll = max(0, min(self.scroll, self.max_scroll))
        for i in self.visible_rows:
            kind, item = self.rows[i]
            if kind != "lot":
                continue
            minus, plus = self.step_rects(i)
            self.remove_buttons[i] = Button(
                minus,
                "-",
                enabled=plan.can_remove(item),
                font_size=22,
                on_click=lambda deed=item: self._step(deed, False),
            )
            self.add_buttons[i] = Button(
                plus,
                "+",
                enabled=plan.can_add(item),
                font_size=22,
                on_click=lambda deed=item: self._step(deed, True),
            )
        self.confirm.enabled = plan.changed

    # --- layout -------------------------------------------------------------
    @property
    def title_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.rect.left + PAD, self.rect.top + PAD, self.rect.width - 2 * PAD, TITLE_H
        )

    @property
    def supply_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.rect.left + PAD, self.title_rect.bottom, self.rect.width - 2 * PAD,
            SUPPLY_H,
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
        """Everything between the supply line and the footer."""
        top = self.supply_rect.bottom + 8
        return pygame.Rect(
            self.rect.left + PAD,
            top,
            self.rect.width - 2 * PAD,
            self.footer_rect.top - 10 - top,
        )

    def row_height(self, row: int) -> int:
        """How tall entry ``row`` is: a group header is shorter than a lot."""
        return GROUP_H if self.rows[row][0] == "group" else ROW_H

    def _row_gap(self, row: int) -> int:
        return GROUP_GAP if self.rows[row][0] == "group" else ROW_GAP

    def row_rect(self, row: int) -> pygame.Rect:
        """The rectangle of the ``row``-th entry, group headers included.

        Measured from :attr:`scroll`, so a row above the window comes back
        with a negative top and simply falls outside :attr:`list_rect`.
        """
        y = self.list_rect.top
        step = 1 if row >= self.scroll else -1
        for i in range(self.scroll, row, step):
            j = i if step > 0 else i - 1
            y += step * (self.row_height(j) + self._row_gap(j))
        return pygame.Rect(
            self.list_rect.left, y, self.list_rect.width, self.row_height(row)
        )

    @property
    def visible_rows(self) -> list[int]:
        """Every entry index that fits the list window at the current scroll.

        Buttons are only built for these, so a row scrolled out of sight
        cannot be clicked by accident.
        """
        rows = []
        y = self.list_rect.top
        for row in range(self.scroll, len(self.rows)):
            height = self.row_height(row)
            if y + height > self.list_rect.bottom:
                break
            rows.append(row)
            y += height + self._row_gap(row)
        return rows

    @property
    def max_scroll(self) -> int:
        """The largest scroll offset that still fills the window."""
        remaining = self.list_rect.height
        for row in range(len(self.rows) - 1, -1, -1):
            remaining -= self.row_height(row)
            if remaining < 0:
                return row + 1
            remaining -= self._row_gap(row)
        return 0

    def scroll_by(self, rows: int) -> None:
        """Scroll the list, clamped to its ends, and rebuild the buttons."""
        scroll = max(0, min(self.max_scroll, self.scroll + rows))
        if scroll != self.scroll:
            self.scroll = scroll
            self.refresh()

    def step_rects(self, row: int) -> tuple[pygame.Rect, pygame.Rect]:
        """The ``-`` and ``+`` squares at the right of a lot row."""
        rect = self.row_rect(row)
        plus = pygame.Rect(rect.right - STEP_W, rect.top, STEP_W, rect.height)
        minus = pygame.Rect(plus.left - STEP_W - 6, rect.top, STEP_W, rect.height)
        return minus, plus

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

        A ``+`` or ``-`` click edits the draft in place and reports ``None``:
        the screen stays open until one of the two footer buttons is pressed.
        """
        if self._plan is None:
            return None
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_by(-getattr(event, "y", 0))
            return None
        for button in list(self.remove_buttons.values()) + list(
            self.add_buttons.values()
        ):
            if button.handle_event(event):
                return None
        if self.confirm.handle_event(event):
            return CONFIRM
        if self.cancel.handle_event(event):
            return CANCEL
        return None

    def _step(self, deed, add: bool) -> None:
        plan = self._plan
        if plan is None:
            return
        if add:
            plan.add(deed)
        else:
            plan.remove(deed)
        self.refresh()

    def _fire(self, key: str) -> None:
        if self.on_close is not None:
            self.on_close(key)

    # --- drawing ------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        """Dim the board and draw the panel. A no-op with no plan."""
        plan = self._plan
        if plan is None:
            return
        self._draw_scrim(surface)
        pygame.draw.rect(surface, PANEL, self.rect, border_radius=10)
        pygame.draw.rect(surface, BORDER, self.rect, width=2, border_radius=10)

        title = get_font(26, bold=True).render(
            f"Build -- {plan.player.name}", True, TEXT
        )
        surface.blit(title, (self.title_rect.left, self.title_rect.top))
        cash = get_font(20, bold=True).render(f"${plan.player.cash:,}", True, ACCENT)
        surface.blit(
            cash,
            cash.get_rect(
                midright=(self.title_rect.right, self.title_rect.centery)
            ),
        )

        supply = get_font(14).render(
            f"bank: {plan.houses} houses, {plan.hotels} hotels", True, TEXT_MUTED
        )
        surface.blit(supply, (self.supply_rect.left, self.supply_rect.top))

        if plan.is_empty:
            note = get_font(16).render(EMPTY_TEXT, True, TEXT_MUTED)
            surface.blit(note, (self.list_rect.left, self.list_rect.top + 6))
        else:
            self._draw_rows(surface, plan)
        self._draw_footer(surface, plan)

    def _draw_rows(self, surface: pygame.Surface, plan: BuildPlan) -> None:
        for i in self.visible_rows:
            kind, item = self.rows[i]
            rect = self.row_rect(i)
            if kind == "group":
                self._draw_group(surface, rect, item)
            else:
                self._draw_lot(surface, rect, plan, item)
                for buttons in (self.remove_buttons, self.add_buttons):
                    if i in buttons:
                        buttons[i].draw(surface)

    def _draw_group(
        self, surface: pygame.Surface, rect: pygame.Rect, group: str
    ) -> None:
        chip = pygame.Rect(rect.left, rect.top + 4, 16, rect.height - 8)
        pygame.draw.rect(surface, GROUP_COLORS[group], chip)
        label = group.replace("_", " ").upper()
        text = get_font(15, bold=True).render(label, True, TEXT_MUTED)
        surface.blit(text, text.get_rect(midleft=(chip.right + 10, rect.centery)))

    def _draw_lot(
        self, surface: pygame.Surface, rect: pygame.Rect, plan: BuildPlan, deed
    ) -> None:
        pygame.draw.rect(surface, PANEL_LIGHT, rect, border_radius=5)
        font = get_font(16)
        label = ellipsize(deed_label(deed), font, NAME_W)
        name = font.render(label, True, TEXT)
        surface.blit(name, name.get_rect(midleft=(rect.left + NAME_X, rect.centery)))

        cost = get_font(13).render(f"${deed.build_cost}", True, TEXT_MUTED)
        surface.blit(
            cost,
            cost.get_rect(midright=(rect.right - 2 * STEP_W - 16, rect.centery)),
        )
        self._draw_level(surface, rect, plan.level(deed))

    def _draw_level(
        self, surface: pygame.Surface, rect: pygame.Rect, level: int
    ) -> None:
        """The buildings the draft puts on this lot, left to right."""
        x = rect.left + BUILDINGS_X
        if level == HOTEL_LEVEL:
            hotel = pygame.Rect(x, 0, *ROW_HOTEL)
            hotel.centery = rect.centery
            pygame.draw.rect(surface, HOTEL_COLOR, hotel)
            return
        for _ in range(level):
            house = pygame.Rect(x, 0, ROW_HOUSE, ROW_HOUSE)
            house.centery = rect.centery
            pygame.draw.rect(surface, HOUSE_COLOR, house)
            x += ROW_HOUSE + 4

    def _draw_footer(self, surface: pygame.Surface, plan: BuildPlan) -> None:
        footer = self.footer_rect
        note = get_font(13).render(describe_plan(plan), True, TEXT_MUTED)
        surface.blit(note, (footer.left, footer.top))
        color = DANGER if plan.charge else (ACCENT if plan.refund else TEXT_MUTED)
        total = get_font(18, bold=True).render(_total_text(plan), True, color)
        surface.blit(total, (footer.left, footer.top + 22))
        self.cancel.draw(surface)
        self.confirm.draw(surface)

    def _draw_scrim(self, surface: pygame.Surface) -> None:
        scrim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        scrim.fill((0, 0, 0, SCRIM_ALPHA))
        surface.blit(scrim, (0, 0))


def _rows_for(plan: BuildPlan) -> list[tuple[str, object]]:
    """The screen's entries: a ``("group", key)`` then its ``("lot", deed)``s."""
    rows: list[tuple[str, object]] = []
    for group in plan.groups:
        rows.append(("group", group))
        rows.extend(("lot", lot) for lot in plan.lots[group])
    return rows


def _total_text(plan: BuildPlan) -> str:
    if plan.charge:
        return f"-${plan.charge:,}"
    if plan.refund:
        return f"+${plan.refund:,}"
    return "$0"
