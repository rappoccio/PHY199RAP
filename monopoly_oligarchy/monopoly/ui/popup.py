"""Phase 7: the modal popup.

:class:`Popup` draws whatever :class:`monopoly.game.Prompt` the game is waiting
on -- "Buy Baltic Avenue for $60?", a drawn Chance card, Phase 8's three ways
out of Jail -- over a dimmed board, and turns a click on one of its buttons
back into that choice's key.

Like the HUD, it decides nothing: it is handed a prompt, it draws exactly that,
and :meth:`Popup.handle_event` reports the key so ``main`` can pass it to
:meth:`monopoly.game.Game.choose`. A popup with no prompt draws nothing and
swallows nothing.
"""

from __future__ import annotations

from typing import Callable, Optional

import pygame

from monopoly.game import BUY_KEY, OK_KEY, ROLL_KEY, Prompt
from monopoly.ui.button import Button
from monopoly.ui.theme import (
    BORDER,
    PANEL,
    TEXT,
    TEXT_MUTED,
    get_font,
    wrap_text,
)

#: The popup box, centred over the 800x800 board.
POPUP_SIZE = (520, 300)
POPUP_CENTER = (400, 380)

#: Margin inside the box.
PAD = 24

BUTTON_H = 48
BUTTON_GAP = 14

TITLE_SIZE = 26
BODY_SIZE = 18

#: How dark the rest of the screen goes behind the popup (0-255).
SCRIM_ALPHA = 150

#: The choice keys drawn as the filled, primary button.
PRIMARY_KEYS = frozenset({BUY_KEY, OK_KEY, ROLL_KEY})

#: Choices per row. Phase 8's jail prompt has three of them, and three across
#: a 520px box leaves no room for a label like "Roll for Doubles" -- so the
#: row wraps, and the odd one out spans the width on the bottom row.
MAX_PER_ROW = 2


class Popup:
    """A modal box: a title, a wrapped body and the choice buttons below it."""

    def __init__(
        self,
        rect: Optional[pygame.Rect | tuple[int, int, int, int]] = None,
        *,
        prompt: Optional[Prompt] = None,
        on_choice: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.rect = (
            pygame.Rect(rect)
            if rect is not None
            else pygame.Rect((0, 0), POPUP_SIZE)
        )
        if rect is None:
            self.rect.center = POPUP_CENTER
        self.on_choice = on_choice
        self._prompt: Optional[Prompt] = None
        self.buttons: list[Button] = []
        self.prompt = prompt

    # --- state --------------------------------------------------------------
    @property
    def prompt(self) -> Optional[Prompt]:
        return self._prompt

    @prompt.setter
    def prompt(self, value: Optional[Prompt]) -> None:
        """Show ``value`` (or nothing), rebuilding the button row to match."""
        self._prompt = value
        self.buttons = [] if value is None else self._build_buttons()

    @property
    def visible(self) -> bool:
        """Whether there is anything to draw."""
        return self._prompt is not None

    # --- layout -------------------------------------------------------------
    @property
    def choice_rows(self) -> tuple[tuple, ...]:
        """The open choices grouped into rows of at most :data:`MAX_PER_ROW`."""
        options = self._prompt.options if self._prompt is not None else ()
        return tuple(
            tuple(options[i : i + MAX_PER_ROW])
            for i in range(0, len(options), MAX_PER_ROW)
        )

    @property
    def buttons_rect(self) -> pygame.Rect:
        """The block along the bottom of the box that holds the choices.

        One row deep for the usual one- or two-choice prompt -- and for a
        popup showing nothing at all, so the empty box still lays out.
        """
        rows = max(1, len(self.choice_rows))
        height = rows * BUTTON_H + (rows - 1) * BUTTON_GAP
        return pygame.Rect(
            self.rect.left + PAD,
            self.rect.bottom - PAD - height,
            self.rect.width - 2 * PAD,
            height,
        )

    @property
    def title_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.rect.left + PAD, self.rect.top + PAD, self.rect.width - 2 * PAD, 32
        )

    @property
    def body_rect(self) -> pygame.Rect:
        """Everything between the title and the buttons."""
        top = self.title_rect.bottom + 12
        return pygame.Rect(
            self.rect.left + PAD,
            top,
            self.rect.width - 2 * PAD,
            self.buttons_rect.top - BUTTON_GAP - top,
        )

    def _build_buttons(self) -> list[Button]:
        """One button per choice: equal widths across each row, top to bottom.

        In prompt order, so :meth:`handle_event` can zip the two lists back
        together however the rows fell out.
        """
        block = self.buttons_rect
        buttons = []
        y = block.top
        for row in self.choice_rows:
            width = (block.width - BUTTON_GAP * (len(row) - 1)) // len(row)
            for i, option in enumerate(row):
                buttons.append(
                    Button(
                        (
                            block.left + i * (width + BUTTON_GAP),
                            y,
                            width,
                            BUTTON_H,
                        ),
                        option.label,
                        enabled=option.enabled,
                        primary=option.key in PRIMARY_KEYS,
                        font_size=20,
                        on_click=lambda key=option.key: self._fire(key),
                    )
                )
            y += BUTTON_H + BUTTON_GAP
        return buttons

    # --- events -------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """Dispatch one event; return the chosen key, if a choice was clicked.

        Returns ``None`` when nothing was chosen -- including for every event
        while no prompt is showing.
        """
        if self._prompt is None:
            return None
        for option, button in zip(self._prompt.options, self.buttons):
            if button.handle_event(event):
                return option.key
        return None

    def _fire(self, key: str) -> None:
        if self.on_choice is not None:
            self.on_choice(key)

    # --- drawing ------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        """Dim the screen and draw the box. A no-op with no prompt."""
        prompt = self._prompt
        if prompt is None:
            return
        self._draw_scrim(surface)
        pygame.draw.rect(surface, PANEL, self.rect, border_radius=10)
        pygame.draw.rect(surface, BORDER, self.rect, width=2, border_radius=10)

        title = get_font(TITLE_SIZE, bold=True).render(prompt.title, True, TEXT)
        surface.blit(title, (self.title_rect.left, self.title_rect.top))

        font = get_font(BODY_SIZE)
        y = self.body_rect.top
        for line in wrap_text(prompt.text, font, self.body_rect.width):
            if y + font.get_linesize() > self.body_rect.bottom:
                break
            surface.blit(font.render(line, True, TEXT_MUTED), (self.body_rect.left, y))
            y += font.get_linesize()

        for button in self.buttons:
            button.draw(surface)

    def _draw_scrim(self, surface: pygame.Surface) -> None:
        scrim = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        scrim.fill((0, 0, 0, SCRIM_ALPHA))
        surface.blit(scrim, (0, 0))
