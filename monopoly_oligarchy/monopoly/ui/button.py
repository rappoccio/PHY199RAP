"""A clickable rectangle with a label.

The plan lists ``button.py`` under Phase 6, but the setup screen needs the same
widget first, so it lands here and the HUD reuses it later.
"""

from __future__ import annotations

from typing import Callable, Optional

import pygame

from monopoly.ui.theme import (
    ACCENT,
    ACCENT_DARK,
    BORDER,
    PANEL,
    PANEL_LIGHT,
    TEXT,
    TEXT_DARK,
    TEXT_MUTED,
    get_font,
)


class Button:
    """A labelled button that reports its own clicks.

    ``primary`` buttons are drawn filled in the accent colour (the one obvious
    next step on a screen); the rest are drawn as panel-coloured chrome. A
    disabled button renders greyed out and never reports a click.
    """

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        label: str,
        *,
        enabled: bool = True,
        primary: bool = False,
        font_size: int = 20,
        on_click: Optional[Callable[[], None]] = None,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.label = label
        self.enabled = enabled
        self.primary = primary
        self.font_size = font_size
        self.on_click = on_click
        self.hovered = False

    # --- events -------------------------------------------------------------
    def is_clicked(self, event: pygame.event.Event) -> bool:
        """Whether ``event`` is a left press on this button while enabled."""
        return (
            self.enabled
            and event.type == pygame.MOUSEBUTTONDOWN
            and getattr(event, "button", None) == 1
            and self.rect.collidepoint(event.pos)
        )

    def handle_event(self, event: pygame.event.Event) -> bool:
        """Track hover, fire :attr:`on_click`, and report whether we consumed.

        Hover tracking never consumes the event; a click on an enabled button
        does, so a caller can stop dispatching it to widgets underneath.
        """
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.enabled and self.rect.collidepoint(event.pos)
            return False
        if self.is_clicked(event):
            if self.on_click is not None:
                self.on_click()
            return True
        return False

    # --- drawing ------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        if not self.enabled:
            fill, border, text_color = PANEL, BORDER, TEXT_MUTED
        elif self.primary:
            fill = ACCENT if not self.hovered else ACCENT_DARK
            border, text_color = ACCENT_DARK, TEXT_DARK
        else:
            fill = PANEL_LIGHT if self.hovered else PANEL
            border, text_color = BORDER, TEXT

        pygame.draw.rect(surface, fill, self.rect, border_radius=6)
        pygame.draw.rect(surface, border, self.rect, width=2, border_radius=6)

        font = get_font(self.font_size, bold=self.primary)
        text = font.render(self.label, True, text_color)
        surface.blit(text, text.get_rect(center=self.rect.center))
