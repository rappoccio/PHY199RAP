"""Phase 4: the frame compositor.

One screen is 1280x800: the 800x800 board on the left and a 480x800 panel on
the right. :class:`Renderer` owns that split -- it blits the board surface,
lets the HUD draw itself into the panel, and puts any active popup on top.

The HUD (Phase 6's :class:`monopoly.ui.hud.Hud`) and any popup are injected:
anything with a ``draw(surface)`` method will do, which keeps this module free
of both. Without a HUD the panel is drawn empty, so the board can still be put
on screen on its own.
"""

from __future__ import annotations

from typing import Iterable, Optional, Protocol

import pygame

from monopoly.board import BOARD_PIXELS, Board
from monopoly.ui.theme import BACKGROUND, BORDER, PANEL, SCREEN_SIZE

#: Where the board surface lands on the screen.
BOARD_ORIGIN = (0, 0)

#: The panel to the right of the board (the Phase 6 HUD's home).
HUD_RECT = pygame.Rect(
    BOARD_PIXELS, 0, SCREEN_SIZE[0] - BOARD_PIXELS, SCREEN_SIZE[1]
)


class Drawable(Protocol):
    """Anything the renderer can hand the screen to."""

    def draw(self, surface: pygame.Surface) -> None: ...


class Renderer:
    """Draws one frame: board + HUD panel + popup."""

    def __init__(
        self, surface: pygame.Surface, board: Optional[Board] = None
    ) -> None:
        self.surface = surface
        self.board = board if board is not None else Board()

    # --- drawing ------------------------------------------------------------
    def draw(
        self,
        players: Iterable = (),
        properties: Iterable = (),
        hud: Optional[Drawable] = None,
        popup: Optional[Drawable] = None,
    ) -> None:
        """Compose a frame. Nothing is flipped here; the caller owns the loop."""
        players = list(players)
        self.surface.fill(BACKGROUND)
        self.surface.blit(self.board.render(players, properties), BOARD_ORIGIN)
        if hud is not None:
            hud.draw(self.surface)
        else:
            self.draw_empty_panel()
        if popup is not None:
            popup.draw(self.surface)

    def draw_empty_panel(self) -> None:
        """The panel chrome with nothing in it, for when no HUD is attached."""
        pygame.draw.rect(self.surface, PANEL, HUD_RECT)
        pygame.draw.rect(self.surface, BORDER, HUD_RECT, width=2)

    # --- coordinates --------------------------------------------------------
    @staticmethod
    def board_point(pos: tuple[int, int]) -> Optional[tuple[int, int]]:
        """Translate a screen point into board coordinates, or ``None``."""
        x = pos[0] - BOARD_ORIGIN[0]
        y = pos[1] - BOARD_ORIGIN[1]
        if 0 <= x < BOARD_PIXELS and 0 <= y < BOARD_PIXELS:
            return (x, y)
        return None

    def space_at(self, pos: tuple[int, int]) -> Optional[int]:
        """The board space under a screen point, or ``None``."""
        point = self.board_point(pos)
        return None if point is None else self.board.space_at_point(point)
