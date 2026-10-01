"""Phase 4 tests: the frame compositor.

``Renderer`` puts three things on one 1280x800 surface -- the board, the HUD
panel and a popup -- so these tests check the layout, the layering order, and
the screen-to-board coordinate translation the later phases will click through.
"""

from __future__ import annotations

import unittest

import pygame

from monopoly.board import BOARD_PIXELS, Board, space_rect, token_positions
from monopoly.player import Player
from monopoly.property import build_properties
from monopoly.ui.renderer import BOARD_ORIGIN, HUD_RECT, Renderer
from monopoly.ui.theme import (
    BACKGROUND,
    PANEL,
    SCREEN_SIZE,
    TOKEN_RGB,
    clear_font_cache,
)


def rgb(surface: pygame.Surface, pos) -> tuple[int, int, int]:
    return tuple(surface.get_at(pos))[:3]


class Spy:
    """A stand-in for the Phase 6 HUD / a popup: it just records its turn."""

    def __init__(self, log: list, name: str, fill=None) -> None:
        self.log = log
        self.name = name
        self.fill = fill
        self.surfaces: list[pygame.Surface] = []

    def draw(self, surface: pygame.Surface) -> None:
        self.log.append(self.name)
        self.surfaces.append(surface)
        if self.fill is not None:
            surface.fill(self.fill)


class RendererTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        clear_font_cache()

    def setUp(self) -> None:
        self.screen = pygame.Surface(SCREEN_SIZE)
        self.board = Board()
        self.renderer = Renderer(self.screen, self.board)
        self.properties = build_properties()
        self.ada = Player("Ada", 1500, "red")


class TestLayout(RendererTestCase):
    def test_the_hud_panel_fills_the_space_beside_the_board(self) -> None:
        self.assertEqual(HUD_RECT.left, BOARD_PIXELS)
        self.assertEqual(HUD_RECT.right, SCREEN_SIZE[0])
        self.assertEqual(HUD_RECT.height, SCREEN_SIZE[1])
        self.assertEqual(HUD_RECT.width, 480)

    def test_a_renderer_builds_its_own_board_when_not_given_one(self) -> None:
        self.assertIsInstance(Renderer(self.screen).board, Board)

    def test_the_board_lands_at_the_top_left(self) -> None:
        self.renderer.draw([self.ada], self.properties)
        board = self.board.render([self.ada], self.properties)
        for point in ((4, 4), (BOARD_PIXELS - 5, BOARD_PIXELS - 5), (400, 400)):
            with self.subTest(point=point):
                self.assertEqual(rgb(self.screen, point), rgb(board, point))

    def test_tokens_show_through_onto_the_screen(self) -> None:
        self.ada.position = 24
        self.renderer.draw([self.ada], self.properties)
        x, y = token_positions(24, 1)[0]
        self.assertEqual(
            rgb(self.screen, (x + BOARD_ORIGIN[0], y + BOARD_ORIGIN[1])),
            TOKEN_RGB["red"],
        )


class TestPanels(RendererTestCase):
    def test_the_empty_panel_fills_the_hud_area(self) -> None:
        self.renderer.draw([self.ada], self.properties)
        self.assertEqual(rgb(self.screen, (HUD_RECT.left + 6, 300)), PANEL)

    def test_a_hud_is_handed_the_screen(self) -> None:
        log: list[str] = []
        hud = Spy(log, "hud")
        self.renderer.draw([self.ada], self.properties, hud=hud)
        self.assertEqual(log, ["hud"])
        self.assertIs(hud.surfaces[0], self.screen)

    def test_a_hud_replaces_the_empty_panel(self) -> None:
        hud = Spy([], "hud", fill=BACKGROUND)
        self.renderer.draw([self.ada], self.properties, hud=hud)
        self.assertNotEqual(rgb(self.screen, (HUD_RECT.left + 6, 300)), PANEL)

    def test_the_popup_is_drawn_last(self) -> None:
        log: list[str] = []
        hud, popup = Spy(log, "hud"), Spy(log, "popup")
        self.renderer.draw([self.ada], self.properties, hud=hud, popup=popup)
        self.assertEqual(log, ["hud", "popup"])

    def test_a_popup_covers_what_is_underneath(self) -> None:
        popup = Spy([], "popup", fill=(7, 7, 7))
        self.renderer.draw([self.ada], self.properties, popup=popup)
        self.assertEqual(rgb(self.screen, (400, 400)), (7, 7, 7))

    def test_drawing_an_empty_roster_is_fine(self) -> None:
        self.renderer.draw()
        self.assertEqual(rgb(self.screen, (HUD_RECT.left + 6, 300)), PANEL)

    def test_a_frame_redraws_from_scratch(self) -> None:
        """Yesterday's popup must not survive into today's frame."""
        self.renderer.draw([self.ada], self.properties, popup=Spy([], "p", fill=(7, 7, 7)))
        self.renderer.draw([self.ada], self.properties)
        self.assertNotEqual(rgb(self.screen, (400, 400)), (7, 7, 7))


class TestCoordinates(RendererTestCase):
    def test_a_point_on_the_board_translates(self) -> None:
        self.assertEqual(Renderer.board_point((10, 20)), (10, 20))

    def test_a_point_on_the_hud_is_not_on_the_board(self) -> None:
        self.assertIsNone(Renderer.board_point((HUD_RECT.left + 10, 400)))
        self.assertIsNone(Renderer.board_point((-1, 400)))

    def test_clicking_a_space_finds_it(self) -> None:
        for index in (0, 1, 11, 20, 24, 39):
            with self.subTest(index=index):
                centre = space_rect(index).center
                screen_point = (
                    centre[0] + BOARD_ORIGIN[0],
                    centre[1] + BOARD_ORIGIN[1],
                )
                self.assertEqual(self.renderer.space_at(screen_point), index)

    def test_clicking_the_middle_or_the_hud_finds_nothing(self) -> None:
        self.assertIsNone(self.renderer.space_at((400, 400)))
        self.assertIsNone(self.renderer.space_at((HUD_RECT.centerx, 400)))


if __name__ == "__main__":
    unittest.main()
