"""Phase 4: the board, drawn procedurally onto a pygame surface.

The board is a 800x800 square with the 40 spaces around its edge: four corner
squares of :data:`CORNER_SIZE` and, between them, nine side spaces of
:data:`SPACE_WIDTH` per edge (the plan says "10 per side" -- that would make 44
spaces; 4 + 4*9 = 40 is what the real board has).

    (0,0) +-------------------------+
          | 20 | 21 ... 29 |    30  |      20 Free Parking, 30 Go To Jail
          | 19 |                    | 31
          | .. |        centre      | ..
          | 11 |                    | 39
          | 10 |  9  ...  1 |     0 |      10 Jail, 0 Go
          +-------------------------+ (800,800)

Everything about *where* a space is lives in the module-level geometry
functions, which are pure and need no display; :class:`Board` layers the
drawing on top and caches it.

Two surfaces are kept:

* the **base** surface -- space outlines, colour strips, names, prices -- which
  depends only on ``spaces.json`` and so is drawn exactly once;
* the **composite** -- base plus ownership pips, mortgage tints, houses/hotels
  and player tokens -- which is rebuilt only when that state actually changes.
"""

from __future__ import annotations

from typing import Iterable, Optional, Sequence

import pygame

from monopoly.data_loader import BOARD_SIZE, load_spaces
from monopoly.ui.theme import (
    BOARD_BG,
    BOARD_LINE,
    BOARD_TEXT,
    BOARD_TEXT_MUTED,
    BUILDING_EDGE,
    GROUP_COLORS,
    HOTEL_COLOR,
    HOUSE_COLOR,
    MORTGAGE_TINT,
    SPACE_BG,
    TOKEN_RGB,
    fit_text,
    get_font,
)

#: The board is square; this is its side in pixels (the plan's ~800x800).
BOARD_PIXELS = 800

#: Corner squares, and the side spaces between them: 2*112 + 9*64 == 800.
CORNER_SIZE = 112
SPACE_WIDTH = 64

#: Depth of the coloured deed strip along a space's inner edge.
STRIP_DEPTH = 26

#: Depth of the owner pip along a space's *outer* edge.
OWNER_PIP_DEPTH = 7

#: Player tokens: radius, and the pitch of the stacking grid.
TOKEN_RADIUS = 9
TOKEN_GAP = 2
TOKEN_COLUMNS = 3

#: House / hotel markers drawn on the deed strip.
HOUSE_SIZE = 12
HOUSE_GAP = 3
HOTEL_LENGTH = 26
HOTEL_DEPTH = 14

BOTTOM = "bottom"
LEFT = "left"
TOP = "top"
RIGHT = "right"

#: How far a side's labels are rotated so their "up" points at the board centre
#: (pygame rotates counter-clockwise, so the left column takes a negative turn).
ROTATION = {BOTTOM: 0, LEFT: -90, TOP: 180, RIGHT: 90}

#: Corner indices, anticlockwise from Go.
CORNERS = (0, 10, 20, 30)


def _check_index(index: int) -> None:
    if not 0 <= index < BOARD_SIZE:
        raise ValueError(f"board index must be 0-{BOARD_SIZE - 1}, got {index}")


def is_corner(index: int) -> bool:
    """Whether ``index`` is one of Go, Jail, Free Parking or Go To Jail."""
    _check_index(index)
    return index % 10 == 0


def side_of(index: int) -> str:
    """Which edge of the board ``index`` sits on.

    Corners belong to the edge they start: Go and Jail are on the bottom,
    Free Parking and Go To Jail on the top.
    """
    _check_index(index)
    if index <= 10:
        return BOTTOM
    if index < 20:
        return LEFT
    if index <= 30:
        return TOP
    return RIGHT


def rotation_of(index: int) -> int:
    """Degrees a space's label is rotated (counter-clockwise)."""
    return ROTATION[side_of(index)]


def space_rect(index: int) -> pygame.Rect:
    """The rectangle space ``index`` occupies, in board-surface coordinates."""
    _check_index(index)
    size, corner, width = BOARD_PIXELS, CORNER_SIZE, SPACE_WIDTH
    if index == 0:
        return pygame.Rect(size - corner, size - corner, corner, corner)
    if index == 10:
        return pygame.Rect(0, size - corner, corner, corner)
    if index == 20:
        return pygame.Rect(0, 0, corner, corner)
    if index == 30:
        return pygame.Rect(size - corner, 0, corner, corner)

    side = side_of(index)
    if side == BOTTOM:  # 1-9, running right to left
        return pygame.Rect(size - corner - index * width, size - corner, width, corner)
    if side == LEFT:  # 11-19, running bottom to top
        return pygame.Rect(0, size - corner - (index - 10) * width, corner, width)
    if side == TOP:  # 21-29, running left to right
        return pygame.Rect(corner + (index - 21) * width, 0, width, corner)
    return pygame.Rect(size - corner, corner + (index - 31) * width, corner, width)


def strip_rect(index: int) -> pygame.Rect:
    """The coloured band along a space's inner edge (the one facing centre)."""
    rect = space_rect(index)
    side = side_of(index)
    if side == BOTTOM:
        return pygame.Rect(rect.left, rect.top, rect.width, STRIP_DEPTH)
    if side == TOP:
        return pygame.Rect(
            rect.left, rect.bottom - STRIP_DEPTH, rect.width, STRIP_DEPTH
        )
    if side == LEFT:
        return pygame.Rect(rect.right - STRIP_DEPTH, rect.top, STRIP_DEPTH, rect.height)
    return pygame.Rect(rect.left, rect.top, STRIP_DEPTH, rect.height)


def owner_pip_rect(index: int) -> pygame.Rect:
    """The thin bar along a space's outer edge showing who owns the deed."""
    rect = space_rect(index)
    side = side_of(index)
    if side == BOTTOM:
        return pygame.Rect(
            rect.left, rect.bottom - OWNER_PIP_DEPTH, rect.width, OWNER_PIP_DEPTH
        )
    if side == TOP:
        return pygame.Rect(rect.left, rect.top, rect.width, OWNER_PIP_DEPTH)
    if side == LEFT:
        return pygame.Rect(rect.left, rect.top, OWNER_PIP_DEPTH, rect.height)
    return pygame.Rect(
        rect.right - OWNER_PIP_DEPTH, rect.top, OWNER_PIP_DEPTH, rect.height
    )


def body_rect(index: int, *, strip: bool = True) -> pygame.Rect:
    """The part of a space left for its name and price.

    ``strip=False`` (a space with no deed, so no colour band) gives the whole
    space back.
    """
    rect = space_rect(index)
    if not strip:
        return rect
    side = side_of(index)
    if side == BOTTOM:
        return pygame.Rect(
            rect.left, rect.top + STRIP_DEPTH, rect.width, rect.height - STRIP_DEPTH
        )
    if side == TOP:
        return pygame.Rect(rect.left, rect.top, rect.width, rect.height - STRIP_DEPTH)
    if side == LEFT:
        return pygame.Rect(rect.left, rect.top, rect.width - STRIP_DEPTH, rect.height)
    return pygame.Rect(
        rect.left + STRIP_DEPTH, rect.top, rect.width - STRIP_DEPTH, rect.height
    )


def space_at_point(pos: tuple[int, int]) -> Optional[int]:
    """The space under a board-surface point, or ``None`` for the centre."""
    for index in range(BOARD_SIZE):
        if space_rect(index).collidepoint(pos):
            return index
    return None


def token_positions(index: int, count: int) -> list[tuple[int, int]]:
    """Centres for ``count`` tokens sharing space ``index``.

    Tokens fill a grid of at most :data:`TOKEN_COLUMNS` per row, centred on the
    space's body so they never sit on the colour strip. The last row is centred
    on its own width, so three players on a space read as a neat row of three
    and four as three-over-one.
    """
    if count <= 0:
        return []
    body = body_rect(index)
    step = 2 * TOKEN_RADIUS + TOKEN_GAP
    rows = -(-count // TOKEN_COLUMNS)
    centre_x, centre_y = body.center
    positions: list[tuple[int, int]] = []
    for seat in range(count):
        row, column = divmod(seat, TOKEN_COLUMNS)
        in_row = min(TOKEN_COLUMNS, count - row * TOKEN_COLUMNS)
        x = centre_x + (column - (in_row - 1) / 2) * step
        y = centre_y + (row - (rows - 1) / 2) * step
        positions.append((round(x), round(y)))
    return positions


def building_rects(index: int, houses: int, has_hotel: bool) -> list[pygame.Rect]:
    """Marker rectangles for the buildings standing on space ``index``.

    A hotel is one wide rectangle; houses are up to four small squares spread
    along the colour strip. Both are returned in board-surface coordinates.
    """
    strip = strip_rect(index)
    horizontal = side_of(index) in (BOTTOM, TOP)
    if has_hotel:
        length, depth = HOTEL_LENGTH, HOTEL_DEPTH
        width, height = (length, depth) if horizontal else (depth, length)
        rect = pygame.Rect(0, 0, width, height)
        rect.center = strip.center
        return [rect]
    if houses <= 0:
        return []

    pitch = HOUSE_SIZE + HOUSE_GAP
    span = houses * HOUSE_SIZE + (houses - 1) * HOUSE_GAP
    rects = []
    for i in range(houses):
        offset = i * pitch - span / 2 + HOUSE_SIZE / 2
        rect = pygame.Rect(0, 0, HOUSE_SIZE, HOUSE_SIZE)
        if horizontal:
            rect.center = (round(strip.centerx + offset), strip.centery)
        else:
            rect.center = (strip.centerx, round(strip.centery + offset))
        rects.append(rect)
    return rects


#: Names shortened for the board only -- the deeds keep their full names.
DISPLAY_NAMES = {
    "Reading Railroad": "Reading RR",
    "Pennsylvania Railroad": "Penn. RR",
    "B. & O. Railroad": "B&O RR",
    "Short Line Railroad": "Short Line RR",
    "Electric Company": "Electric Co.",
}

#: Font sizes the labels may use. Side spaces keep to a narrow range so that
#: neighbouring names do not end up wildly different sizes.
SIDE_LABEL_SIZES = (11, 10, 9, 8, 7, 6)
CORNER_LABEL_SIZES = (17, 16, 15, 14, 13, 12, 11, 10)


def display_name(space: dict) -> str:
    """The name as the board prints it (railroads and utilities abbreviate)."""
    return DISPLAY_NAMES.get(space["name"], space["name"])


def space_label(space: dict) -> tuple[str, str]:
    """The (title, subtitle) drawn on a space, from its ``spaces.json`` entry."""
    kind = space["type"]
    if kind in ("property", "railroad", "utility"):
        return display_name(space), f"${space['price']}"
    if kind == "tax":
        return space["name"], f"PAY ${space['amount']}"
    if kind == "chance":
        return "CHANCE", "?"
    if kind == "community_chest":
        return "COMMUNITY CHEST", ""
    if kind == "go":
        return "GO", "COLLECT $200"
    if kind == "jail":
        return "JAIL", "Just Visiting"
    if kind == "go_to_jail":
        return "GO TO JAIL", ""
    if kind == "free_parking":
        return "FREE PARKING", ""
    return space["name"], ""  # pragma: no cover - every type is covered above


def group_color(space: dict) -> Optional[tuple[int, int, int]]:
    """The strip colour for a deed space, or ``None`` where there is no deed."""
    kind = space["type"]
    if kind == "property":
        return GROUP_COLORS[space["color"]]
    if kind in ("railroad", "utility"):
        return GROUP_COLORS[kind]
    return None


def _render_label(
    size: tuple[int, int],
    title: str,
    subtitle: str,
    *,
    bold: bool,
    sizes: tuple[int, ...] = SIDE_LABEL_SIZES,
) -> pygame.Surface:
    """Draw a space's title and subtitle onto an upright transparent surface.

    The label is drawn the right way up and rotated into place by the caller,
    so its bottom edge is always the space's *outer* edge -- which is also
    where the owner pip goes, hence the extra bottom margin.
    """
    width, height = size
    surface = pygame.Surface(size, pygame.SRCALPHA)
    pad = 3
    bottom_pad = pad + OWNER_PIP_DEPTH
    sub_font = get_font(9)
    sub_height = sub_font.get_linesize() if subtitle else 0

    box_height = height - pad - bottom_pad - sub_height
    font, lines = fit_text(
        title, width - 2 * pad, box_height, sizes=sizes, bold=bold
    )
    line_height = font.get_linesize()
    block = len(lines) * line_height
    y = pad + max(0, (box_height - block) // 2)
    for line in lines:
        text = font.render(line, True, BOARD_TEXT)
        surface.blit(text, text.get_rect(centerx=width // 2, top=y))
        y += line_height
    if subtitle:
        text = sub_font.render(subtitle, True, BOARD_TEXT_MUTED)
        surface.blit(
            text, text.get_rect(centerx=width // 2, bottom=height - bottom_pad)
        )
    return surface


class Board:
    """The board's pixels: built from ``spaces.json``, cached between frames."""

    def __init__(self, spaces: Optional[Sequence[dict]] = None) -> None:
        self.spaces = list(spaces) if spaces is not None else load_spaces()
        if len(self.spaces) != BOARD_SIZE:
            raise ValueError(
                f"a board needs {BOARD_SIZE} spaces, got {len(self.spaces)}"
            )
        self._base: Optional[pygame.Surface] = None
        self._composite: Optional[pygame.Surface] = None
        self._signature: Optional[tuple] = None
        #: How many times each surface has actually been drawn (the caching
        #: contract is part of the public behaviour, so the tests can see it).
        self.base_builds = 0
        self.composite_builds = 0

    @property
    def size(self) -> tuple[int, int]:
        return (BOARD_PIXELS, BOARD_PIXELS)

    # --- caching ------------------------------------------------------------
    def mark_dirty(self) -> None:
        """Force the next :meth:`render` to redraw the dynamic layer."""
        self._signature = None
        self._composite = None

    @property
    def base_surface(self) -> pygame.Surface:
        """The static board art, drawn once and kept."""
        if self._base is None:
            self._base = self._draw_base()
            self.base_builds += 1
        return self._base

    def render(
        self,
        players: Iterable = (),
        properties: Iterable = (),
    ) -> pygame.Surface:
        """The board with tokens, buildings and ownership drawn on.

        The returned surface is cached: calling this every frame costs nothing
        until a token moves or a building, mortgage or deed changes hands.
        """
        players = [p for p in players if not getattr(p, "is_bankrupt", False)]
        properties = list(properties)
        signature = self._state_signature(players, properties)
        if self._composite is None or signature != self._signature:
            self._composite = self._draw_composite(players, properties)
            self._signature = signature
            self.composite_builds += 1
        return self._composite

    @staticmethod
    def _state_signature(players: Sequence, properties: Sequence) -> tuple:
        return (
            tuple((p.position, p.token_color) for p in players),
            tuple(
                (
                    d.index,
                    None if d.owner is None else d.owner.token_color,
                    d.houses,
                    d.has_hotel,
                    d.mortgaged,
                )
                for d in properties
            ),
        )

    # --- static layer -------------------------------------------------------
    def _draw_base(self) -> pygame.Surface:
        surface = pygame.Surface(self.size)
        surface.fill(BOARD_BG)
        for space in self.spaces:
            self._draw_space(surface, space)
        self._draw_centre(surface)
        pygame.draw.rect(surface, BOARD_LINE, pygame.Rect((0, 0), self.size), width=3)
        return surface

    def _draw_space(self, surface: pygame.Surface, space: dict) -> None:
        index = space["index"]
        rect = space_rect(index)
        pygame.draw.rect(surface, SPACE_BG, rect)

        color = group_color(space)
        if color is not None:
            strip = strip_rect(index)
            pygame.draw.rect(surface, color, strip)
            pygame.draw.rect(surface, BOARD_LINE, strip, width=1)

        body = body_rect(index, strip=color is not None)
        upright = (
            (body.width, body.height)
            if side_of(index) in (BOTTOM, TOP)
            else (body.height, body.width)
        )
        title, subtitle = space_label(space)
        corner = is_corner(index)
        label = _render_label(
            upright,
            title,
            subtitle,
            bold=corner,
            sizes=CORNER_LABEL_SIZES if corner else SIDE_LABEL_SIZES,
        )
        surface.blit(pygame.transform.rotate(label, rotation_of(index)), body.topleft)

        pygame.draw.rect(surface, BOARD_LINE, rect, width=2)

    def _draw_centre(self, surface: pygame.Surface) -> None:
        centre = pygame.Rect(
            CORNER_SIZE,
            CORNER_SIZE,
            BOARD_PIXELS - 2 * CORNER_SIZE,
            BOARD_PIXELS - 2 * CORNER_SIZE,
        )
        pygame.draw.rect(surface, BOARD_BG, centre)
        title = get_font(52, bold=True).render("MONOPOLY", True, BOARD_LINE)
        subtitle = get_font(20).render("Custom Stake Edition", True, BOARD_TEXT_MUTED)
        block = pygame.Surface(
            (
                max(title.get_width(), subtitle.get_width()),
                title.get_height() + subtitle.get_height() + 8,
            ),
            pygame.SRCALPHA,
        )
        block.blit(title, title.get_rect(centerx=block.get_width() // 2, top=0))
        block.blit(
            subtitle,
            subtitle.get_rect(centerx=block.get_width() // 2, bottom=block.get_height()),
        )
        turned = pygame.transform.rotate(block, 45)
        surface.blit(turned, turned.get_rect(center=centre.center))

    # --- dynamic layer ------------------------------------------------------
    def _draw_composite(
        self, players: Sequence, properties: Sequence
    ) -> pygame.Surface:
        surface = self.base_surface.copy()
        for deed in properties:
            self._draw_deed_state(surface, deed)
        for index, occupants in self.occupants(players).items():
            for (x, y), player in zip(token_positions(index, len(occupants)), occupants):
                self._draw_token(surface, (x, y), player.token_color)
        return surface

    def _draw_deed_state(self, surface: pygame.Surface, deed) -> None:
        if deed.owner is not None:
            pip = owner_pip_rect(deed.index)
            pygame.draw.rect(
                surface, TOKEN_RGB.get(deed.owner.token_color, BOARD_LINE), pip
            )
            pygame.draw.rect(surface, BOARD_LINE, pip, width=1)
        if deed.mortgaged:
            strip = strip_rect(deed.index)
            pygame.draw.rect(surface, MORTGAGE_TINT, strip)
            pygame.draw.rect(surface, BOARD_LINE, strip, width=1)
            pygame.draw.line(surface, BOARD_LINE, strip.topleft, strip.bottomright, 2)
            return
        color = HOTEL_COLOR if deed.has_hotel else HOUSE_COLOR
        for rect in building_rects(deed.index, deed.houses, deed.has_hotel):
            pygame.draw.rect(surface, color, rect)
            pygame.draw.rect(surface, BUILDING_EDGE, rect, width=1)

    @staticmethod
    def _draw_token(
        surface: pygame.Surface, centre: tuple[int, int], token_color: str
    ) -> None:
        rgb = TOKEN_RGB.get(token_color, BOARD_LINE)
        pygame.draw.circle(surface, rgb, centre, TOKEN_RADIUS)
        pygame.draw.circle(surface, BOARD_LINE, centre, TOKEN_RADIUS, width=2)

    # --- queries ------------------------------------------------------------
    @staticmethod
    def occupants(players: Iterable) -> dict[int, list]:
        """Players grouped by the space they stand on, skipping the bankrupt."""
        by_space: dict[int, list] = {}
        for player in players:
            if getattr(player, "is_bankrupt", False):
                continue
            by_space.setdefault(player.position, []).append(player)
        return by_space

    def space(self, index: int) -> dict:
        """The ``spaces.json`` entry at ``index``."""
        _check_index(index)
        return self.spaces[index]

    @staticmethod
    def space_at_point(pos: tuple[int, int]) -> Optional[int]:
        """The space under a board-surface point, or ``None``."""
        return space_at_point(pos)
