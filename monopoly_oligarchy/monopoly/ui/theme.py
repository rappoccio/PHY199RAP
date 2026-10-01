"""Shared colours and fonts for every pygame surface the game draws.

Phase 3 only needs the setup screen's chrome, but the palette lives here --
rather than in :mod:`monopoly.ui.renderer` as the plan sketched it -- so that
the widgets in this package can be used before the board exists.
"""

from __future__ import annotations

import pygame

#: Target window size (board 800x800 on the left, HUD 480x800 on the right).
SCREEN_SIZE = (1280, 800)

# --- UI chrome -------------------------------------------------------------
BACKGROUND = (28, 32, 38)
PANEL = (44, 50, 58)
PANEL_LIGHT = (62, 70, 80)
BORDER = (96, 106, 118)
ACCENT = (68, 150, 96)
ACCENT_DARK = (46, 106, 68)
DANGER = (188, 78, 72)

TEXT = (238, 240, 243)
TEXT_MUTED = (150, 158, 168)
TEXT_DARK = (24, 26, 30)

FIELD_BG = (18, 21, 25)
FIELD_BG_FOCUSED = (24, 30, 36)
FIELD_BORDER_FOCUSED = ACCENT

#: Token colours, one per seat, in the order they are handed out.
TOKEN_COLORS: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("red", (204, 62, 62)),
    ("blue", (58, 112, 200)),
    ("green", (72, 160, 88)),
    ("yellow", (218, 186, 60)),
    ("purple", (150, 92, 190)),
    ("orange", (222, 130, 52)),
)

TOKEN_RGB = dict(TOKEN_COLORS)

_FONT_CACHE: dict[tuple[int, bool], pygame.font.Font] = {}


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    """A cached monospace font, initialising ``pygame.font`` on first use."""
    if not pygame.font.get_init():
        # Anything cached before the module was shut down is now dangling.
        _FONT_CACHE.clear()
        pygame.font.init()
    key = (size, bold)
    font = _FONT_CACHE.get(key)
    if font is None:
        font = pygame.font.SysFont("monospace", size, bold=bold)
        _FONT_CACHE[key] = font
    return font


def clear_font_cache() -> None:
    """Drop every cached font.

    ``pygame.font.quit()`` frees the underlying SDL_ttf fonts, so a cached
    :class:`pygame.font.Font` created before that call renders into freed
    memory -- a hard crash rather than an exception. Anything that shuts the
    font module down must clear the cache too.
    """
    _FONT_CACHE.clear()


# --- board -----------------------------------------------------------------
#: The board's own chrome: a pale green field with cream spaces, drawn dark.
BOARD_BG = (196, 223, 200)
BOARD_LINE = (24, 26, 30)
BOARD_TEXT = (24, 26, 30)
BOARD_TEXT_MUTED = (92, 98, 104)
SPACE_BG = (241, 240, 230)

#: Buildings and the mortgage overlay.
HOUSE_COLOR = (34, 139, 58)
HOTEL_COLOR = (186, 44, 44)
BUILDING_EDGE = (18, 40, 24)
MORTGAGE_TINT = (128, 134, 142)

#: Deed strip colours. The eight standard groups plus the two flat groups the
#: railroads and utilities share (``Property.group`` uses the same keys).
GROUP_COLORS: dict[str, tuple[int, int, int]] = {
    "brown": (124, 74, 46),
    "light_blue": (170, 224, 248),
    "pink": (214, 60, 143),
    "orange": (244, 148, 42),
    "red": (222, 48, 48),
    "yellow": (248, 226, 66),
    "green": (32, 150, 72),
    "dark_blue": (32, 86, 190),
    "railroad": (58, 62, 70),
    "utility": (168, 176, 186),
}

#: Font sizes :func:`fit_text` tries, largest first.
LABEL_SIZES = (14, 13, 12, 11, 10, 9, 8, 7, 6)


def _split_word(word: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Break a single word that cannot fit on one line into chunks that can."""
    if max_width <= 0 or font.size(word)[0] <= max_width:
        return [word]
    chunks: list[str] = []
    chunk = ""
    for char in word:
        if chunk and font.size(chunk + char)[0] > max_width:
            chunks.append(chunk)
            chunk = char
        else:
            chunk += char
    if chunk:
        chunks.append(chunk)
    return chunks


def wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Wrap ``text`` to ``max_width`` pixels, hard-splitting over-long words.

    Board spaces are 64px wide, so a name like "Mediterranean" has to be able
    to break mid-word rather than overflow its space.
    """
    lines: list[str] = []
    current = ""
    for word in text.split():
        for piece in _split_word(word, font, max_width):
            candidate = f"{current} {piece}" if current else piece
            if not current or font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = piece
    if current:
        lines.append(current)
    return lines


def ellipsize(text: str, font: pygame.font.Font, max_width: int) -> str:
    """``text`` shortened with a trailing ellipsis until it fits ``max_width``.

    Unlike :func:`wrap_text` this never adds a line: a panel row is one line
    tall, so a name that does not fit is cut rather than spilled.
    """
    if max_width <= 0:
        return ""
    if font.size(text)[0] <= max_width:
        return text
    trimmed = text
    while trimmed and font.size(trimmed + "...")[0] > max_width:
        trimmed = trimmed[:-1]
    return trimmed + "..." if trimmed else ""


def fit_text(
    text: str,
    max_width: int,
    max_height: int,
    *,
    sizes: tuple[int, ...] = LABEL_SIZES,
    bold: bool = False,
) -> tuple[pygame.font.Font, list[str]]:
    """The largest font in ``sizes`` whose wrapped ``text`` fits the given box.

    A size only counts as fitting when every whole word fits the width -- a
    board space would rather print "Connecticut" small than "Connectic/ut"
    large. ``sizes`` is tried largest first; when nothing fits, the smallest
    size is returned anyway so a caller always has something to draw.
    """
    words = text.split()
    font = get_font(sizes[-1], bold)
    lines = wrap_text(text, font, max_width)
    for size in sizes:
        font = get_font(size, bold)
        lines = wrap_text(text, font, max_width)
        fits_height = len(lines) * font.get_linesize() <= max_height
        fits_width = all(font.size(word)[0] <= max_width for word in words)
        if fits_height and fits_width:
            break
    return font, lines
