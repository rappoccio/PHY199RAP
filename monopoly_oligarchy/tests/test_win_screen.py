"""Phase 14 tests: the win screen.

The overlay is the last thing the game draws, so what matters is that it shows
the *finished* game truthfully and that its two buttons report themselves:
the winner's name in their token colour, the cash and net worth they ended on,
every deed they still held (in board order, mortgages and buildings marked),
and ``Play Again`` / ``Quit`` coming back out of :meth:`WinScreen.handle_event`
and sticking in :attr:`WinScreen.choice`.

The other half is that it stays out of the way until the game is over:
``result = None`` draws nothing and swallows nothing, so a live game can never
be answered by a stray click on a button that is not there.

Everything runs on a plain ``Surface``; no window is opened.
"""

from __future__ import annotations

import unittest

import pygame

from monopoly.player import Player
from monopoly.property import build_properties
from monopoly.ui.theme import (
    DANGER,
    GROUP_COLORS,
    HOTEL_COLOR,
    HOUSE_COLOR,
    PANEL,
    PANEL_LIGHT,
    SCREEN_SIZE,
    TOKEN_RGB,
    clear_font_cache,
)
from monopoly.ui.win_screen import (
    COLUMNS,
    EMPTY_TEXT,
    MORTGAGED_STATUS,
    NO_WINNER_NOTE,
    PLAY_AGAIN,
    QUIT,
    WinScreen,
    WinState,
    _tally,
    describe_result,
)

#: Board indices of the deeds these tests hand out.
MEDITERRANEAN, BALTIC = 1, 3
ORIENTAL, VERMONT, CONNECTICUT = 6, 8, 9
BOARDWALK = 39


def click(pos) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": pos})


def motion(pos) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEMOTION, {"pos": pos})


def colours_in(surface: pygame.Surface, rect: pygame.Rect) -> set:
    """Every RGB triple inside ``rect``."""
    patch = surface.subsurface(rect).copy()
    return {
        tuple(patch.get_at((x, y))[:3])
        for x in range(patch.get_width())
        for y in range(patch.get_height())
    }


class ScreenTestCase(unittest.TestCase):
    """A finished two-handed game: Ada standing, Bob bankrupt."""

    def setUp(self):
        pygame.init()
        clear_font_cache()
        self.surface = pygame.Surface(SCREEN_SIZE)
        self.deeds = build_properties()
        self.by_index = {deed.index: deed for deed in self.deeds}
        self.ada = Player("Ada", 1240, "red")
        self.bob = Player("Bob", 0, "blue", is_bankrupt=True)
        self.screen = WinScreen()

    def tearDown(self):
        clear_font_cache()
        pygame.font.quit()

    def give(self, *indices) -> None:
        for index in indices:
            self.ada.add_property(self.by_index[index])

    def show(self, *, winner: object = "ada") -> WinState:
        """Hand the screen a finished game and return the state it got."""
        player = self.ada if winner == "ada" else winner
        state = WinState(winner=player, players=[self.ada, self.bob])
        self.screen.result = state
        return state


class StateTest(ScreenTestCase):
    def test_it_shows_nothing_until_the_game_is_over(self):
        self.assertFalse(self.screen.visible)
        self.assertIsNone(self.screen.result)
        self.assertIsNone(self.screen.winner)
        self.assertEqual(self.screen.deeds, [])

    def test_a_result_makes_it_visible(self):
        state = self.show()
        self.assertTrue(self.screen.visible)
        self.assertIs(self.screen.result, state)
        self.assertIs(self.screen.winner, self.ada)

    def test_a_table_with_nobody_left_is_still_a_result(self):
        self.show(winner=None)
        self.assertTrue(self.screen.visible, "no winner is not the same as no game over")
        self.assertIsNone(self.screen.winner)
        self.assertEqual(self.screen.deeds, [])

    def test_clearing_the_result_hides_it_again(self):
        self.give(BALTIC)
        self.show()
        self.screen.result = None
        self.assertFalse(self.screen.visible)
        self.assertEqual(self.screen.deeds, [])

    def test_the_deeds_are_the_winners_in_board_order(self):
        self.give(BOARDWALK, MEDITERRANEAN, VERMONT)
        self.show()
        self.assertEqual(
            [deed.index for deed in self.screen.deeds],
            [MEDITERRANEAN, VERMONT, BOARDWALK],
        )

    def test_it_reads_the_roster_without_touching_it(self):
        self.give(BALTIC)
        self.show()
        self.assertEqual(self.ada.cash, 1240)
        self.assertEqual([d.index for d in self.ada.properties], [BALTIC])
        self.assertIs(self.by_index[BALTIC].owner, self.ada)

    def test_two_states_over_the_same_game_compare_equal(self):
        """``main`` leans on this to avoid rebuilding the screen every frame."""
        first = WinState(winner=self.ada, players=[self.ada, self.bob])
        second = WinState(winner=self.ada, players=[self.ada, self.bob])
        self.assertEqual(first, second)
        self.assertNotEqual(first, WinState(winner=self.bob, players=[self.ada]))
        self.assertNotEqual(first, WinState())


class LayoutTest(ScreenTestCase):
    def test_the_overlay_fills_the_window(self):
        self.assertEqual(self.screen.rect.size, SCREEN_SIZE)

    def test_the_card_sits_inside_the_overlay(self):
        self.assertTrue(self.screen.rect.contains(self.screen.card_rect))
        self.assertGreater(self.screen.card_rect.width, 0)

    def test_the_blocks_stack_down_the_card(self):
        card = self.screen.card_rect
        blocks = [
            self.screen.heading_rect,
            self.screen.banner_rect,
            self.screen.stats_rect,
            self.screen.list_rect,
            self.screen.footer_rect,
        ]
        for block in blocks:
            self.assertTrue(card.contains(block), block)
            self.assertGreater(block.height, 0, block)
        for above, below in zip(blocks, blocks[1:]):
            self.assertLessEqual(above.bottom, below.top, (above, below))

    def test_the_buttons_sit_in_the_footer_side_by_side(self):
        footer = self.screen.footer_rect
        self.assertTrue(footer.contains(self.screen.play_again.rect))
        self.assertTrue(footer.contains(self.screen.quit.rect))
        self.assertLess(self.screen.play_again.rect.right, self.screen.quit.rect.left)

    def test_play_again_is_the_primary_button(self):
        self.assertTrue(self.screen.play_again.primary)
        self.assertFalse(self.screen.quit.primary)
        self.assertTrue(self.screen.play_again.enabled)
        self.assertTrue(self.screen.quit.enabled)

    def test_rows_fill_a_column_top_to_bottom_then_move_right(self):
        rows = self.screen.rows_per_column
        first = self.screen.row_rect(0)
        second = self.screen.row_rect(1)
        next_column = self.screen.row_rect(rows)
        self.assertEqual(first.left, second.left)
        self.assertGreater(second.top, first.top)
        self.assertGreater(next_column.left, first.left)
        self.assertEqual(next_column.top, first.top)

    def test_every_row_that_fits_stays_inside_the_list(self):
        self.give(*[deed.index for deed in self.deeds])
        self.show()
        for i in range(len(self.screen.shown_deeds)):
            self.assertTrue(
                self.screen.list_rect.contains(self.screen.row_rect(i)), i
            )

    def test_the_whole_board_fits_without_overflowing(self):
        self.give(*[deed.index for deed in self.deeds])
        self.show()
        self.assertEqual(len(self.screen.deeds), 28)
        self.assertGreaterEqual(self.screen.capacity, 28)
        self.assertEqual(self.screen.overflow, 0)
        self.assertEqual(len(self.screen.shown_deeds), 28)

    def test_capacity_is_the_columns_times_the_rows(self):
        self.assertEqual(
            self.screen.capacity, self.screen.rows_per_column * COLUMNS
        )

    def test_a_short_card_reports_what_it_could_not_show(self):
        screen = WinScreen((0, 0, 900, 460))
        self.give(*[deed.index for deed in self.deeds])
        screen.result = WinState(winner=self.ada, players=[self.ada, self.bob])
        self.assertLess(screen.capacity, 28)
        self.assertEqual(len(screen.shown_deeds), screen.capacity)
        self.assertEqual(screen.overflow, 28 - screen.capacity)

    def test_the_columns_split_the_list_width(self):
        total = self.screen.column_width * COLUMNS
        self.assertLessEqual(total, self.screen.list_rect.width)
        self.assertGreater(self.screen.column_width, 0)


class EventTest(ScreenTestCase):
    def setUp(self):
        super().setUp()
        self.keys: list[str] = []
        self.screen.on_close = self.keys.append

    def test_a_click_on_play_again_reports_itself(self):
        self.show()
        key = self.screen.handle_event(click(self.screen.play_again.rect.center))
        self.assertEqual(key, PLAY_AGAIN)
        self.assertEqual(self.keys, [PLAY_AGAIN])

    def test_a_click_on_quit_reports_itself(self):
        self.show()
        key = self.screen.handle_event(click(self.screen.quit.rect.center))
        self.assertEqual(key, QUIT)
        self.assertEqual(self.keys, [QUIT])

    def test_the_choice_is_remembered_for_the_caller(self):
        self.show()
        self.assertIsNone(self.screen.choice)
        self.screen.handle_event(click(self.screen.play_again.rect.center))
        self.assertEqual(self.screen.choice, PLAY_AGAIN)

    def test_a_click_anywhere_else_chooses_nothing(self):
        self.show()
        self.assertIsNone(self.screen.handle_event(click((5, 5))))
        self.assertIsNone(self.screen.handle_event(click(self.screen.banner_rect.center)))
        self.assertIsNone(self.screen.choice)
        self.assertEqual(self.keys, [])

    def test_a_hidden_screen_swallows_nothing(self):
        pos = self.screen.play_again.rect.center
        self.assertIsNone(self.screen.handle_event(click(pos)))
        self.assertIsNone(self.screen.choice)
        self.assertEqual(self.keys, [])

    def test_a_no_winner_screen_still_answers(self):
        self.show(winner=None)
        self.assertEqual(
            self.screen.handle_event(click(self.screen.quit.rect.center)), QUIT
        )

    def test_hover_is_tracked_and_consumes_nothing(self):
        self.show()
        self.assertIsNone(self.screen.handle_event(motion(self.screen.quit.rect.center)))
        self.assertTrue(self.screen.quit.hovered)
        self.assertFalse(self.screen.play_again.hovered)


class DrawTest(ScreenTestCase):
    def test_a_hidden_screen_draws_nothing(self):
        self.surface.fill((0, 0, 0))
        self.screen.draw(self.surface)
        self.assertEqual(tuple(self.surface.get_at((400, 400)))[:3], (0, 0, 0))

    def test_the_card_covers_the_middle_of_the_screen(self):
        self.show()
        self.screen.draw(self.surface)
        self.assertEqual(
            tuple(self.surface.get_at(self.screen.card_rect.center))[:3], PANEL
        )

    def test_the_scrim_darkens_what_is_left_of_the_board(self):
        self.surface.fill((255, 255, 255))
        self.show()
        self.screen.draw(self.surface)
        outside = self.surface.get_at((5, 5))
        self.assertLess(outside.r, 60)
        self.assertLess(outside.g, 60)
        self.assertLess(outside.b, 60)

    def test_the_winners_name_is_drawn_in_their_token_colour(self):
        self.show()
        self.screen.draw(self.surface)
        self.assertIn(
            TOKEN_RGB["red"], colours_in(self.surface, self.screen.banner_rect)
        )

    def test_a_deed_row_carries_its_group_colour(self):
        self.give(MEDITERRANEAN)
        self.show()
        self.screen.draw(self.surface)
        row = self.screen.row_rect(0)
        self.assertEqual(
            tuple(self.surface.get_at((row.left + 2, row.centery)))[:3],
            GROUP_COLORS["brown"],
        )
        self.assertEqual(
            tuple(self.surface.get_at((row.centerx, row.top + 2)))[:3], PANEL_LIGHT
        )

    def test_houses_are_drawn_on_a_built_lot(self):
        self.give(ORIENTAL)
        self.by_index[ORIENTAL].houses = 3
        self.show()
        self.screen.draw(self.surface)
        self.assertIn(HOUSE_COLOR, colours_in(self.surface, self.screen.row_rect(0)))

    def test_a_hotel_is_drawn_on_an_upgraded_lot(self):
        self.give(ORIENTAL)
        self.by_index[ORIENTAL].has_hotel = True
        self.show()
        self.screen.draw(self.surface)
        self.assertIn(HOTEL_COLOR, colours_in(self.surface, self.screen.row_rect(0)))

    def test_a_mortgaged_deed_is_badged_in_the_danger_colour(self):
        self.give(BALTIC)
        self.by_index[BALTIC].mortgaged = True
        self.show()
        self.screen.draw(self.surface)
        self.assertIn(DANGER, colours_in(self.surface, self.screen.row_rect(0)))

    def test_the_whole_board_in_one_hand_draws(self):
        self.give(*[deed.index for deed in self.deeds])
        self.by_index[BOARDWALK].has_hotel = True
        self.by_index[MEDITERRANEAN].mortgaged = True
        self.show()
        self.screen.draw(self.surface)
        last = self.screen.row_rect(len(self.screen.shown_deeds) - 1)
        self.assertIn(PANEL_LIGHT, colours_in(self.surface, last))

    def test_a_winner_with_no_deeds_says_so(self):
        self.show()
        self.assertEqual(self.screen.deeds, [])
        self.screen.draw(self.surface)
        self.assertTrue(EMPTY_TEXT)

    def test_a_table_with_nobody_left_draws_too(self):
        self.show(winner=None)
        self.screen.draw(self.surface)
        self.assertEqual(
            tuple(self.surface.get_at(self.screen.card_rect.center))[:3], PANEL
        )

    def test_an_overflowing_list_draws(self):
        screen = WinScreen((0, 0, 900, 460))
        self.give(*[deed.index for deed in self.deeds])
        screen.result = WinState(winner=self.ada, players=[self.ada, self.bob])
        self.assertGreater(screen.overflow, 0)
        screen.draw(self.surface)

    def test_the_buttons_reach_the_pixels(self):
        self.show()
        self.surface.fill((0, 0, 0))
        self.screen.draw(self.surface)
        for button in (self.screen.play_again, self.screen.quit):
            self.assertGreater(len(colours_in(self.surface, button.rect)), 1, button.label)


class DescribeTest(ScreenTestCase):
    def test_a_winner_is_summarised_with_their_stats(self):
        self.give(MEDITERRANEAN, BALTIC)
        line = describe_result(self.show())
        self.assertIn("Ada", line)
        self.assertIn("$1,240", line)
        self.assertIn("2 deeds", line)
        self.assertIn(f"${self.ada.net_worth():,}", line)

    def test_an_empty_table_is_summarised_too(self):
        self.assertEqual(describe_result(self.show(winner=None)), NO_WINNER_NOTE)

    def test_the_mortgaged_status_is_the_label_the_rows_print(self):
        self.assertEqual(MORTGAGED_STATUS, "mortgaged")

    def test_the_heading_counts_the_table(self):
        self.assertEqual(_tally([self.ada, self.bob]), "2 players -- 1 bankrupt")

    def test_a_one_handed_game_is_counted_in_the_singular(self):
        self.assertEqual(_tally([self.bob]), "1 player -- 1 bankrupt")


if __name__ == "__main__":
    unittest.main()
