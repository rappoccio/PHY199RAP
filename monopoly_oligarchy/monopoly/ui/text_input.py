"""A single-line text field with a blinking caret.

Used by the Phase 3 setup screen for the name and starting-cash fields, and by
the later auction and trade screens for their cash inputs.
"""

from __future__ import annotations

import pygame

from monopoly.ui.theme import (
    BORDER,
    FIELD_BG,
    FIELD_BG_FOCUSED,
    FIELD_BORDER_FOCUSED,
    TEXT,
    TEXT_MUTED,
    get_font,
)

#: Milliseconds the caret spends visible, then hidden.
BLINK_MS = 500


class TextInput:
    """One editable line of text.

    Set ``digits_only`` for a numeric field: non-digit characters are simply
    not accepted, so a caller never has to strip them back out. Text longer
    than ``max_length`` is refused rather than truncated silently.
    """

    def __init__(
        self,
        rect: pygame.Rect | tuple[int, int, int, int],
        *,
        text: str = "",
        placeholder: str = "",
        max_length: int = 24,
        digits_only: bool = False,
        font_size: int = 20,
        focused: bool = False,
    ) -> None:
        self.rect = pygame.Rect(rect)
        self.placeholder = placeholder
        self.max_length = max_length
        self.digits_only = digits_only
        self.font_size = font_size
        self._text = ""
        self._caret = 0
        self._focused = focused
        self._blink_start = 0
        self._now = 0
        self.text = text

    # --- text ---------------------------------------------------------------
    @property
    def text(self) -> str:
        return self._text

    @text.setter
    def text(self, value: str) -> None:
        cleaned = "".join(c for c in value if self._accepts(c))[: self.max_length]
        self._text = cleaned
        self._caret = len(cleaned)
        self._restart_blink()

    @property
    def value(self) -> str:
        """The text with surrounding whitespace stripped."""
        return self._text.strip()

    def _accepts(self, char: str) -> bool:
        if len(char) != 1 or not char.isprintable():
            return False
        return char.isdigit() if self.digits_only else True

    # --- focus --------------------------------------------------------------
    @property
    def focused(self) -> bool:
        return self._focused

    @focused.setter
    def focused(self, value: bool) -> None:
        if value and not self._focused:
            self._restart_blink()
        self._focused = bool(value)

    def _restart_blink(self) -> None:
        self._blink_start = self._now

    @property
    def caret_visible(self) -> bool:
        if not self._focused:
            return False
        return ((self._now - self._blink_start) // BLINK_MS) % 2 == 0

    def update(self, now_ms: int) -> None:
        """Advance the caret blink clock (``pygame.time.get_ticks()``)."""
        self._now = now_ms

    # --- events -------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> bool:
        """Apply ``event``; return whether this field consumed it.

        A left click inside the field focuses it and a left click outside
        blurs it -- neither is reported as consumed, so a screen can let its
        buttons see the same click.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", None) == 1:
            self.focused = self.rect.collidepoint(event.pos)
            return False
        if not self._focused or event.type != pygame.KEYDOWN:
            return False

        key = event.key
        if key == pygame.K_BACKSPACE:
            if self._caret:
                self._text = self._text[: self._caret - 1] + self._text[self._caret :]
                self._caret -= 1
        elif key == pygame.K_DELETE:
            self._text = self._text[: self._caret] + self._text[self._caret + 1 :]
        elif key == pygame.K_LEFT:
            self._caret = max(0, self._caret - 1)
        elif key == pygame.K_RIGHT:
            self._caret = min(len(self._text), self._caret + 1)
        elif key == pygame.K_HOME:
            self._caret = 0
        elif key == pygame.K_END:
            self._caret = len(self._text)
        else:
            char = getattr(event, "unicode", "")
            if not self._accepts(char) or len(self._text) >= self.max_length:
                return False
            self._text = self._text[: self._caret] + char + self._text[self._caret :]
            self._caret += 1
        self._restart_blink()
        return True

    # --- drawing ------------------------------------------------------------
    def draw(self, surface: pygame.Surface) -> None:
        fill = FIELD_BG_FOCUSED if self._focused else FIELD_BG
        border = FIELD_BORDER_FOCUSED if self._focused else BORDER
        pygame.draw.rect(surface, fill, self.rect, border_radius=4)
        pygame.draw.rect(surface, border, self.rect, width=2, border_radius=4)

        font = get_font(self.font_size)
        shown, color = (self._text, TEXT) if self._text else (self.placeholder, TEXT_MUTED)
        text_x = self.rect.x + 8
        baseline_y = self.rect.centery
        if shown:
            rendered = font.render(shown, True, color)
            surface.blit(rendered, rendered.get_rect(midleft=(text_x, baseline_y)))

        if self.caret_visible:
            caret_x = text_x + font.size(self._text[: self._caret])[0]
            half = font.get_height() // 2
            pygame.draw.line(
                surface,
                TEXT,
                (caret_x, baseline_y - half),
                (caret_x, baseline_y + half),
                2,
            )
