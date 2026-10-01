"""Phase 6: the right-hand HUD panel.

The panel is 480x800 and sits beside the board. It shows, top to bottom:

* the current player -- token, name, cash and net worth,
* the dice (:mod:`monopoly.ui.dice_view` draws them here rather than in
  ``main``),
* a one-line message from the game ("Ada pays $50 rent"),
* the current player's deeds, with building and mortgage status,
* the action buttons, and
* every other player's cash summary.

**The HUD knows no rules.** It is handed a :class:`HudState` -- the roster, the
deeds, the dice and the set of actions that are legal right now -- and draws
exactly that. Deciding *which* actions are available is Phase 7's job, so the
turn loop can change without this module changing with it. Clicks come back
out as an :class:`Action`, both as :meth:`Hud.handle_event`'s return value and
through the optional ``on_action`` callback.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

import pygame

from monopoly.board import DISPLAY_NAMES
from monopoly.dice import Dice
from monopoly.game import Action
from monopoly.player import Player
from monopoly.property import Property
from monopoly.ui.button import Button
from monopoly.ui.dice_view import DIE_SIZE, dice_size, draw_dice
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
    TOKEN_RGB,
    ellipsize,
    get_font,
)


# ``Action`` is imported above rather than defined here: the enum moved to
# :mod:`monopoly.game` in Phase 7, because *which* actions exist is a rules
# question. It is re-exported so ``from monopoly.ui.hud import Action`` still
# works, and each member's value is still its button label.

#: The order the buttons are laid out in: one wide row, then two pairs.
ACTION_ROWS: tuple[tuple[Action, ...], ...] = (
    (Action.ROLL,),
    (Action.BUILD, Action.MORTGAGE),
    (Action.TRADE, Action.END_TURN),
)

#: Buttons drawn filled in the accent colour when they are enabled -- the one
#: obvious next step at either end of a turn.
PRIMARY_ACTIONS = frozenset({Action.ROLL, Action.END_TURN})

# --- layout ----------------------------------------------------------------
#: Margin between the panel edge and its content.
PAD = 20

#: Heights of the fixed blocks, top to bottom.
HEADER_H = 78
DICE_BLOCK_H = DIE_SIZE + 28
MESSAGE_H = 24
TITLE_H = 20

#: One deed in the property list, and one player in the roster.
ROW_H = 27
ROSTER_ROW_H = 28

#: Space reserved for the roster: a title plus every seat but the current one.
MAX_OTHER_PLAYERS = 5

BUTTON_H = 48
BUTTON_GAP = 12
BLOCK_GAP = 16

#: Chip drawn at the left of a deed row, in its group colour.
CHIP_W = 14
CHIP_H = 18

#: Building markers in a deed row.
ROW_HOUSE = 8
ROW_HOTEL = (18, 10)

MORTGAGE_BADGE = "MTG"
EMPTY_LIST_TEXT = "(no deeds yet)"


@dataclass
class HudState:
    """Everything the panel draws, as the game sees it this frame.

    ``available`` is the set of actions whose buttons are enabled; anything
    left out is drawn greyed and never reports a click.
    """

    players: Sequence[Player] = ()
    current: Optional[Player] = None
    properties: Sequence[Property] = ()
    dice: Optional[Dice] = None
    message: str = ""
    available: frozenset[Action] = field(default_factory=frozenset)

    def is_available(self, action: Action) -> bool:
        return action in self.available


class Hud:
    """The panel: layout, the action buttons, and a scrolling deed list."""

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        *,
        state: Optional[HudState] = None,
        on_action: Optional[Callable[[Action], None]] = None,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.on_action = on_action
        self.scroll = 0
        self._layout()
        self._state = HudState()
        self.state = state if state is not None else HudState()

    # --- layout -------------------------------------------------------------
    def _layout(self) -> None:
        """Carve the panel into blocks. Pure geometry -- no display needed."""
        x = self.rect.left + PAD
        width = self.rect.width - 2 * PAD

        self.header_rect = pygame.Rect(x, self.rect.top + PAD, width, HEADER_H)
        self.dice_rect = pygame.Rect(
            x, self.header_rect.bottom + 10, width, DICE_BLOCK_H
        )
        self.message_rect = pygame.Rect(
            x, self.dice_rect.bottom, width, MESSAGE_H
        )
        self.list_title_rect = pygame.Rect(
            x, self.message_rect.bottom + 12, width, TITLE_H
        )

        roster_h = TITLE_H + 4 + MAX_OTHER_PLAYERS * ROSTER_ROW_H
        self.roster_rect = pygame.Rect(
            x, self.rect.bottom - PAD - roster_h, width, roster_h
        )

        buttons_h = len(ACTION_ROWS) * BUTTON_H + (len(ACTION_ROWS) - 1) * BUTTON_GAP
        self.buttons_rect = pygame.Rect(
            x, self.roster_rect.top - BLOCK_GAP - buttons_h, width, buttons_h
        )

        top = self.list_title_rect.bottom + 6
        self.property_list_rect = pygame.Rect(
            x, top, width, self.buttons_rect.top - BLOCK_GAP - top
        )

        self.buttons = self._build_buttons()

    def _build_buttons(self) -> dict[Action, Button]:
        buttons: dict[Action, Button] = {}
        half = (self.buttons_rect.width - BUTTON_GAP) // 2
        y = self.buttons_rect.top
        for row in ACTION_ROWS:
            x = self.buttons_rect.left
            width = self.buttons_rect.width if len(row) == 1 else half
            for action in row:
                buttons[action] = Button(
                    (x, y, width, BUTTON_H),
                    action.value,
                    enabled=False,
                    primary=action in PRIMARY_ACTIONS,
                    font_size=20,
                    on_click=lambda a=action: self._fire(a),
                )
                x += width + BUTTON_GAP
            y += BUTTON_H + BUTTON_GAP
        return buttons

    @property
    def visible_rows(self) -> int:
        """How many deeds the property list can show at once."""
        return max(1, self.property_list_rect.height // ROW_H)

    def row_rect(self, row: int) -> pygame.Rect:
        """The rectangle of the ``row``-th *visible* deed row."""
        return pygame.Rect(
            self.property_list_rect.left,
            self.property_list_rect.top + row * ROW_H,
            self.property_list_rect.width,
            ROW_H,
        )

    def chip_rect(self, row: int) -> pygame.Rect:
        """The group-colour chip at the left of a visible deed row."""
        return _chip_in(self.row_rect(row))

    # --- state --------------------------------------------------------------
    @property
    def state(self) -> HudState:
        return self._state

    @state.setter
    def state(self, value: HudState) -> None:
        self._state = value
        for action, button in self.buttons.items():
            button.enabled = value.is_available(action)
        self.scroll = min(self.scroll, self.max_scroll)

    @property
    def deeds(self) -> list[Property]:
        """The current player's deeds, in board order."""
        current = self._state.current
        if current is None:
            return []
        return sorted(current.properties, key=lambda p: p.index)

    @property
    def others(self) -> list[Player]:
        """Every player but the current one, in seat order."""
        current = self._state.current
        return [p for p in self._state.players if p is not current]

    @property
    def max_scroll(self) -> int:
        """The largest scroll offset that still shows a full list."""
        return max(0, len(self.deeds) - self.visible_rows)

    def scroll_by(self, rows: int) -> None:
        """Scroll the deed list, clamped to its ends."""
        self.scroll = max(0, min(self.max_scroll, self.scroll + rows))

    # --- events -------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> Optional[Action]:
        """Dispatch one event; return the action clicked, if any.

        A mouse-wheel event scrolls the deed list. pygame puts no position on
        wheel events, so a caller that wants the wheel to mean something else
        elsewhere on screen simply does not pass that event on.
        """
        if event.type == pygame.MOUSEWHEEL:
            self.scroll_by(-getattr(event, "y", 0))
            return None
        for action, button in self.buttons.items():
            if button.handle_event(event):
                return action
        return None

    def _fire(self, action: Action) -> None:
        if self.on_action is not None:
            self.on_action(action)

    # --- drawing ------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.rect(surface, PANEL, self.rect)
        pygame.draw.rect(surface, BORDER, self.rect, width=2)
        self._draw_header(surface)
        self._draw_dice(surface)
        self._draw_message(surface)
        self._draw_properties(surface)
        for button in self.buttons.values():
            button.draw(surface)
        self._draw_roster(surface)

    def _draw_header(self, surface: pygame.Surface) -> None:
        rect = self.header_rect
        current = self._state.current
        if current is None:
            text = get_font(22, bold=True).render("NO PLAYER", True, TEXT_MUTED)
            surface.blit(text, (rect.left, rect.top))
            return

        radius = 11
        pygame.draw.circle(
            surface,
            token_rgb(current),
            (rect.left + radius, rect.top + radius + 2),
            radius,
        )
        font = get_font(24, bold=True)
        name = ellipsize(current.name, font, rect.width - 2 * radius - 12)
        surface.blit(
            font.render(name, True, TEXT), (rect.left + 2 * radius + 12, rect.top)
        )

        cash = get_font(30, bold=True).render(f"${current.cash:,}", True, ACCENT)
        surface.blit(cash, (rect.left, rect.top + 28))

        worth = get_font(14).render(
            f"net worth ${current.net_worth():,}", True, TEXT_MUTED
        )
        surface.blit(worth, worth.get_rect(bottomright=(rect.right, rect.bottom)))

    def _draw_dice(self, surface: pygame.Surface) -> None:
        dice = self._state.dice
        if dice is None:
            return
        width = dice_size()[0]
        draw_dice(
            surface,
            dice,
            (self.dice_rect.centerx - width // 2, self.dice_rect.top),
        )

    def _draw_message(self, surface: pygame.Surface) -> None:
        if not self._state.message:
            return
        font = get_font(16)
        text = ellipsize(self._state.message, font, self.message_rect.width)
        rendered = font.render(text, True, TEXT)
        surface.blit(rendered, rendered.get_rect(center=self.message_rect.center))

    def _draw_properties(self, surface: pygame.Surface) -> None:
        title = get_font(15, bold=True).render("DEEDS", True, TEXT_MUTED)
        surface.blit(title, (self.list_title_rect.left, self.list_title_rect.top))

        deeds = self.deeds
        if not deeds:
            note = get_font(16).render(EMPTY_LIST_TEXT, True, TEXT_MUTED)
            surface.blit(note, (self.property_list_rect.left, self.row_rect(0).top + 4))
            return

        self._draw_scroll_hint(surface, title.get_height())
        monopolies = set(
            self._state.current.monopolies(self._state.properties)
            if self._state.current is not None and self._state.properties
            else ()
        )
        window = deeds[self.scroll : self.scroll + self.visible_rows]
        for row, deed in enumerate(window):
            self._draw_deed_row(surface, self.row_rect(row), deed, monopolies)

    def _draw_scroll_hint(self, surface: pygame.Surface, height: int) -> None:
        """"3 of 9" beside the list title once the deeds outgrow the panel."""
        if not self.max_scroll:
            return
        shown = min(len(self.deeds), self.scroll + self.visible_rows)
        text = get_font(13).render(
            f"{self.scroll + 1}-{shown} of {len(self.deeds)}", True, TEXT_MUTED
        )
        surface.blit(text, text.get_rect(topright=self.list_title_rect.topright))

    def _draw_deed_row(
        self,
        surface: pygame.Surface,
        rect: pygame.Rect,
        deed: Property,
        monopolies: set,
    ) -> None:
        chip = _chip_in(rect)
        pygame.draw.rect(surface, GROUP_COLORS[deed.group], chip)
        if deed.group in monopolies:
            pygame.draw.rect(surface, TEXT, chip, width=2)

        right = rect.right
        if deed.mortgaged:
            badge = get_font(12, bold=True).render(MORTGAGE_BADGE, True, DANGER)
            surface.blit(badge, badge.get_rect(midright=(right, rect.centery)))
            right -= badge.get_width() + 8
        else:
            right = self._draw_row_buildings(surface, rect, deed, right)

        font = get_font(16)
        color = TEXT_MUTED if deed.mortgaged else TEXT
        name = ellipsize(deed_label(deed), font, right - chip.right - 16)
        text = font.render(name, True, color)
        surface.blit(text, text.get_rect(midleft=(chip.right + 8, rect.centery)))

    def _draw_row_buildings(
        self, surface: pygame.Surface, rect: pygame.Rect, deed: Property, right: int
    ) -> int:
        """Draw this row's houses or hotel, right to left; return the new edge."""
        if deed.has_hotel:
            hotel = pygame.Rect(0, 0, *ROW_HOTEL)
            hotel.midright = (right, rect.centery)
            pygame.draw.rect(surface, HOTEL_COLOR, hotel)
            return hotel.left - 8
        for _ in range(deed.houses):
            house = pygame.Rect(0, 0, ROW_HOUSE, ROW_HOUSE)
            house.midright = (right, rect.centery)
            pygame.draw.rect(surface, HOUSE_COLOR, house)
            right = house.left - 3
        return right - 5 if deed.houses else right

    def _draw_roster(self, surface: pygame.Surface) -> None:
        rect = self.roster_rect
        title = get_font(15, bold=True).render("OTHER PLAYERS", True, TEXT_MUTED)
        surface.blit(title, (rect.left, rect.top))

        y = rect.top + TITLE_H + 4
        font = get_font(16)
        for player in self.others[:MAX_OTHER_PLAYERS]:
            row = pygame.Rect(rect.left, y, rect.width, ROSTER_ROW_H)
            pygame.draw.rect(surface, PANEL_LIGHT, row, border_radius=4)
            muted = player.is_bankrupt
            pygame.draw.circle(
                surface,
                TEXT_MUTED if muted else token_rgb(player),
                (row.left + 14, row.centery),
                7,
            )
            cash_text = "BANKRUPT" if muted else f"${player.cash:,}"
            cash = font.render(cash_text, True, TEXT_MUTED if muted else ACCENT)
            cash_rect = cash.get_rect(midright=(row.right - 8, row.centery))
            surface.blit(cash, cash_rect)

            deeds = font.render(f"{len(player.properties)}d", True, TEXT_MUTED)
            deeds_rect = deeds.get_rect(midright=(cash_rect.left - 10, row.centery))
            surface.blit(deeds, deeds_rect)

            name = ellipsize(player.name, font, deeds_rect.left - row.left - 36)
            text = font.render(name, True, TEXT_MUTED if muted else TEXT)
            surface.blit(text, text.get_rect(midleft=(row.left + 26, row.centery)))
            y += ROSTER_ROW_H


def _chip_in(rect: pygame.Rect) -> pygame.Rect:
    """The group-colour chip inside a deed row's rectangle."""
    return pygame.Rect(rect.left, rect.centery - CHIP_H // 2, CHIP_W, CHIP_H)


def deed_label(deed: Property) -> str:
    """A deed's name as the panel prints it (long names abbreviate)."""
    return DISPLAY_NAMES.get(deed.name, deed.name)


def token_rgb(player: Player) -> tuple[int, int, int]:
    """A player's token colour, falling back to the panel border colour."""
    return TOKEN_RGB.get(player.token_color, BORDER)


