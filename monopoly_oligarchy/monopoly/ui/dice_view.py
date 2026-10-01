"""Phase 5: drawing a pair of dice.

:mod:`monopoly.dice` knows the numbers and the clock; this module knows the
pips. It is kept separate so the rules can be unit-tested without pygame's
drawing, and so the Phase 6 HUD can drop the dice anywhere in its panel by
handing :func:`draw_dice` a corner.
"""

from __future__ import annotations

from typing import Optional

import pygame

from monopoly.dice import Dice
from monopoly.ui.theme import (
    ACCENT,
    BOARD_LINE,
    BORDER,
    SPACE_BG,
    TEXT_MUTED,
    get_font,
)

#: Edge length of one die, and the gap between the two.
DIE_SIZE = 56
DIE_GAP = 14

#: Pip radius as a fraction of the die's edge.
PIP_RATIO = 0.11

#: Pip positions per face, as columns/rows of a 3x3 grid (0 = near edge,
#: 1 = centre, 2 = far edge).
PIP_LAYOUT: dict[int, tuple[tuple[int, int], ...]] = {
    1: ((1, 1),),
    2: ((0, 0), (2, 2)),
    3: ((0, 0), (1, 1), (2, 2)),
    4: ((0, 0), (2, 0), (0, 2), (2, 2)),
    5: ((0, 0), (2, 0), (1, 1), (0, 2), (2, 2)),
    6: ((0, 0), (2, 0), (0, 1), (2, 1), (0, 2), (2, 2)),
}

#: Label shown under the dice while the animation runs.
ROLLING_TEXT = "ROLLING..."
DOUBLES_TEXT = "DOUBLES!"


def dice_size(size: int = DIE_SIZE, gap: int = DIE_GAP) -> tuple[int, int]:
    """The width and height two dice occupy side by side."""
    return (size * 2 + gap, size)


def die_rects(
    topleft: tuple[int, int], size: int = DIE_SIZE, gap: int = DIE_GAP
) -> tuple[pygame.Rect, pygame.Rect]:
    """The rectangles of the left and right die, laid out from ``topleft``."""
    x, y = topleft
    return (
        pygame.Rect(x, y, size, size),
        pygame.Rect(x + size + gap, y, size, size),
    )


def pip_centers(rect: pygame.Rect, face: int) -> list[tuple[int, int]]:
    """Pixel centres of every pip on ``face`` within ``rect``.

    Raises :class:`ValueError` for a face outside 1--6, which means a caller
    handed us something that is not a die roll.
    """
    if face not in PIP_LAYOUT:
        raise ValueError(f"not a die face: {face!r}")
    columns = (rect.x + rect.width // 4, rect.centerx, rect.right - rect.width // 4)
    rows = (rect.y + rect.height // 4, rect.centery, rect.bottom - rect.height // 4)
    return [(columns[col], rows[row]) for col, row in PIP_LAYOUT[face]]


def draw_die(surface: pygame.Surface, rect: pygame.Rect, face: int) -> None:
    """Draw one die: a rounded pale square with ``face`` pips."""
    pygame.draw.rect(surface, SPACE_BG, rect, border_radius=8)
    pygame.draw.rect(surface, BORDER, rect, width=2, border_radius=8)
    radius = max(2, round(rect.width * PIP_RATIO))
    for center in pip_centers(rect, face):
        pygame.draw.circle(surface, BOARD_LINE, center, radius)


def draw_dice(
    surface: pygame.Surface,
    dice: Dice,
    topleft: tuple[int, int],
    *,
    size: int = DIE_SIZE,
    gap: int = DIE_GAP,
    label: bool = True,
) -> pygame.Rect:
    """Draw ``dice`` at ``topleft`` and return the area covered.

    Reads :attr:`Dice.faces`, never :attr:`Dice.result`, so it is safe to call
    on every frame of the animation. With ``label`` set, "ROLLING..." shows
    while the roll is in the air and "DOUBLES!" once a doubles roll settles;
    the returned rectangle covers the label too.
    """
    left, right = die_rects(topleft, size, gap)
    faces = dice.faces
    draw_die(surface, left, faces[0])
    draw_die(surface, right, faces[1])
    area = left.union(right)

    if label:
        caption = _caption(dice)
        if caption:
            color = TEXT_MUTED if dice.rolling else ACCENT
            text = get_font(16, bold=not dice.rolling).render(caption, True, color)
            rect = text.get_rect(midtop=(area.centerx, area.bottom + 8))
            surface.blit(text, rect)
            area = area.union(rect)
    return area


def _caption(dice: Dice) -> Optional[str]:
    if dice.rolling:
        return ROLLING_TEXT
    if dice.settled and dice.doubles:
        return DOUBLES_TEXT
    return None
