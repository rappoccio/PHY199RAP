"""Phase 10 tests: the auction screen.

The screen is the other half of the deal :class:`monopoly.auction.Auction`
strikes: the sale says who is being asked and what they may bid, and the
screen turns that into a field, two buttons and a click back into a move. So
these tests cover the geometry, what the field is filled with as the turn goes
round, which buttons come back live, what a click reports, and that the panel
and its scrim actually reach the pixels.

Everything runs on a plain ``Surface``; no window is opened.
"""

from __future__ import annotations

import unittest

import pygame

from monopoly.auction import Auction
from monopoly.player import Player
from monopoly.property import build_properties
from monopoly.ui.auction_screen import (
    BID,
    PASS,
    RAISES,
    SCREEN_CENTER,
    SCREEN_SIZE,
    AuctionScreen,
)
from monopoly.ui.theme import PANEL, clear_font_cache

TOKENS = ("red", "blue", "green", "yellow")


def click(pos, button: int = 1) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": button})


def motion(pos) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEMOTION, {"pos": pos, "rel": (0, 0)})


def key(code, unicode_: str = "") -> pygame.event.Event:
    return pygame.event.Event(
        pygame.KEYDOWN, {"key": code, "mod": 0, "unicode": unicode_}
    )


def typed(text: str) -> list[pygame.event.Event]:
    return [key(ord(c), c) for c in text]


class ScreenTestCase(unittest.TestCase):
    """A screen showing a three-handed sale of Baltic Avenue."""

    cash = (1500, 1500, 1500)

    @classmethod
    def setUpClass(cls):
        pygame.init()
        clear_font_cache()

    def setUp(self):
        self.deed = next(d for d in build_properties() if d.index == 3)
        self.players = [
            Player(n, c, t)
            for n, c, t in zip(("Ada", "Bob", "Cleo"), self.cash, TOKENS)
        ]
        self.screen = AuctionScreen()
        self.surface = pygame.Surface((1280, 800))

    def show(self, **kwargs) -> Auction:
        sale = Auction(self.deed, self.players, **kwargs)
        self.screen.auction = sale
        return sale

    def press(self, button) -> None:
        self.screen.handle_event(click(button.rect.center))


class LayoutTest(ScreenTestCase):
    def test_the_panel_sits_over_the_board_by_default(self):
        self.assertEqual(self.screen.rect.size, SCREEN_SIZE)
        self.assertEqual(self.screen.rect.center, SCREEN_CENTER)

    def test_an_explicit_rect_is_honoured(self):
        screen = AuctionScreen((10, 20, 300, 400))
        self.assertEqual(screen.rect, pygame.Rect(10, 20, 300, 400))

    def test_the_blocks_stack_inside_the_panel(self):
        screen = self.screen
        for rect in (
            screen.title_rect,
            screen.status_rect,
            screen.list_rect,
            screen.footer_rect,
            screen.field_rect,
            screen.bid.rect,
            screen.pass_button.rect,
        ):
            self.assertTrue(screen.rect.contains(rect), rect)

    def test_the_blocks_do_not_overlap(self):
        screen = self.screen
        self.assertLessEqual(screen.title_rect.bottom, screen.status_rect.top)
        self.assertLessEqual(screen.status_rect.bottom, screen.list_rect.top)
        self.assertLessEqual(screen.list_rect.bottom, screen.footer_rect.top)

    def test_no_two_controls_sit_on_top_of_each_other(self):
        screen = self.screen
        controls = [screen.field_rect, screen.bid.rect, screen.pass_button.rect]
        controls += [b.rect for b in screen.raises]
        for i, first in enumerate(controls):
            for second in controls[i + 1 :]:
                self.assertFalse(first.colliderect(second), (first, second))

    def test_there_is_room_for_a_full_table(self):
        self.assertGreaterEqual(self.screen.visible_rows, 6)

    def test_the_rows_run_down_the_list(self):
        screen = self.screen
        self.assertLess(screen.row_rect(0).top, screen.row_rect(1).top)
        self.assertTrue(screen.list_rect.contains(screen.row_rect(0)))


class VisibilityTest(ScreenTestCase):
    def test_a_screen_with_no_sale_shows_nothing(self):
        self.assertFalse(self.screen.visible)
        self.screen.draw(self.surface)
        self.assertEqual(
            pygame.transform.average_color(self.surface)[:3], (0, 0, 0)
        )

    def test_a_sale_makes_it_visible(self):
        self.show()
        self.assertTrue(self.screen.visible)

    def test_clearing_the_sale_hides_it_again(self):
        self.show()
        self.screen.auction = None
        self.assertFalse(self.screen.visible)

    def test_a_hidden_screen_swallows_nothing(self):
        self.assertIsNone(self.screen.handle_event(click((400, 400))))
        self.assertIsNone(self.screen.handle_event(key(pygame.K_RETURN)))


class FieldTest(ScreenTestCase):
    def test_the_field_opens_at_the_asking_price(self):
        sale = self.show()
        self.assertEqual(self.screen.amount, sale.min_bid)
        self.assertEqual(self.screen.field.value, "1")

    def test_it_refills_when_the_turn_moves_on(self):
        sale = self.show()
        sale.bid(50)
        self.screen.sync()
        self.assertEqual(self.screen.amount, 51)

    def test_it_leaves_a_typed_number_alone_between_syncs(self):
        self.show()
        self.screen.amount = 200
        self.screen.sync()
        self.assertEqual(self.screen.amount, 200, "the price has not moved")

    def test_only_digits_go_in(self):
        self.show()
        self.screen.field.text = ""
        for event in typed("12x3"):
            self.screen.handle_event(event)
        self.assertEqual(self.screen.amount, 123)

    def test_an_empty_field_reads_as_nothing(self):
        self.show()
        self.screen.field.text = ""
        self.assertEqual(self.screen.amount, 0)

    def test_a_quick_raise_adds_to_what_is_there(self):
        self.show()
        self.screen.amount = 100
        self.press(self.screen.raises[1])
        self.assertEqual(self.screen.amount, 100 + RAISES[1])

    def test_a_quick_raise_never_drops_below_the_asking_price(self):
        sale = self.show()
        sale.bid(300)
        self.screen.sync()
        self.screen.field.text = "0"
        self.press(self.screen.raises[0])
        self.assertEqual(self.screen.amount, sale.min_bid)

    def test_a_quick_raise_reports_nothing_and_keeps_the_screen_open(self):
        self.show()
        self.assertIsNone(
            self.screen.handle_event(click(self.screen.raises[0].rect.center))
        )

    def test_typing_reports_nothing(self):
        self.show()
        self.assertIsNone(self.screen.handle_event(key(pygame.K_5, "5")))


class ButtonStateTest(ScreenTestCase):
    def test_both_buttons_are_live_on_an_open_sale(self):
        self.show()
        self.assertTrue(self.screen.bid.enabled)
        self.assertTrue(self.screen.pass_button.enabled)

    def test_bidding_goes_dark_below_the_asking_price(self):
        sale = self.show()
        sale.bid(100)
        self.screen.sync()
        self.screen.field.text = "100"
        self.screen.refresh()
        self.assertFalse(self.screen.bid.enabled)
        self.assertTrue(self.screen.pass_button.enabled, "passing is always open")

    def test_bidding_goes_dark_beyond_the_bidder_s_cash(self):
        self.show()
        self.screen.field.text = "1501"
        self.screen.refresh()
        self.assertFalse(self.screen.bid.enabled)

    def test_an_empty_field_is_not_a_bid(self):
        self.show()
        self.screen.field.text = ""
        self.screen.refresh()
        self.assertFalse(self.screen.bid.enabled)

    def test_the_poorest_bidder_is_priced_out_of_their_own_turn(self):
        self.players[0].cash = 0
        sale = self.show()
        self.assertIs(sale.bidder, self.players[1], "Ada never gets asked")
        self.assertTrue(self.screen.bid.enabled)

    def test_a_settled_sale_puts_every_button_out(self):
        sale = self.show()
        while not sale.finished:
            sale.withdraw()
        self.screen.sync()
        self.assertFalse(self.screen.bid.enabled)
        self.assertFalse(self.screen.pass_button.enabled)
        for button in self.screen.raises:
            self.assertFalse(button.enabled)

    def test_the_field_follows_the_bidder_s_own_wallet(self):
        self.players[1].cash = 40
        sale = self.show()
        sale.bid(20)  # Ada, so Bob is asked next with only $40
        self.screen.sync()
        self.screen.field.text = "45"
        self.screen.refresh()
        self.assertFalse(self.screen.bid.enabled, "Bob cannot find $45")
        self.screen.field.text = "40"
        self.screen.refresh()
        self.assertTrue(self.screen.bid.enabled)


class ClickTest(ScreenTestCase):
    def test_bid_reports_itself(self):
        self.show()
        self.assertEqual(
            self.screen.handle_event(click(self.screen.bid.rect.center)), BID
        )

    def test_pass_reports_itself(self):
        self.show()
        self.assertEqual(
            self.screen.handle_event(click(self.screen.pass_button.rect.center)),
            PASS,
        )

    def test_a_dark_bid_button_reports_nothing(self):
        self.show()
        self.screen.field.text = "0"
        self.screen.refresh()
        self.assertIsNone(
            self.screen.handle_event(click(self.screen.bid.rect.center))
        )

    def test_the_screen_never_settles_the_sale_itself(self):
        sale = self.show()
        self.press(self.screen.bid)
        self.press(self.screen.pass_button)
        self.assertFalse(sale.finished, "only the game moves the sale on")
        self.assertIsNone(self.deed.owner)

    def test_enter_is_the_bid_button(self):
        self.show()
        self.assertEqual(self.screen.handle_event(key(pygame.K_RETURN)), BID)
        self.assertEqual(self.screen.handle_event(key(pygame.K_KP_ENTER)), BID)

    def test_enter_does_nothing_when_the_bid_would_be_refused(self):
        self.show()
        self.screen.field.text = "99999"
        self.screen.refresh()
        self.assertIsNone(self.screen.handle_event(key(pygame.K_RETURN)))

    def test_a_click_outside_reports_nothing(self):
        self.show()
        self.assertIsNone(self.screen.handle_event(click((5, 5))))

    def test_hovering_reports_nothing(self):
        self.show()
        self.assertIsNone(
            self.screen.handle_event(motion(self.screen.bid.rect.center))
        )
        self.assertTrue(self.screen.bid.hovered)

    def test_the_on_close_hook_fires_with_the_key(self):
        seen = []
        screen = AuctionScreen(on_close=seen.append)
        screen.auction = Auction(self.deed, self.players)
        screen.handle_event(click(screen.pass_button.rect.center))
        self.assertEqual(seen, [PASS])


class DrawTest(ScreenTestCase):
    def test_the_panel_reaches_the_pixels(self):
        self.show()
        self.screen.draw(self.surface)
        self.assertEqual(self.surface.get_at(SCREEN_CENTER)[:3], PANEL)

    def test_the_board_behind_it_is_dimmed(self):
        self.surface.fill((255, 255, 255))
        self.show()
        self.screen.draw(self.surface)
        corner = self.surface.get_at((5, 5))[:3]
        self.assertLess(max(corner), 255, "the scrim should darken the board")

    def test_a_settled_sale_still_draws(self):
        sale = self.show()
        while not sale.finished:
            sale.withdraw()
        self.screen.sync()
        self.screen.draw(self.surface)
        self.assertEqual(self.surface.get_at(SCREEN_CENTER)[:3], PANEL)

    def test_a_full_table_draws(self):
        self.players = [
            Player(f"Player {i}", 1500, TOKENS[i % len(TOKENS)]) for i in range(6)
        ]
        sale = self.show()
        self.screen.draw(self.surface)
        self.assertEqual(len(sale.bidders), 6)
        # Six rows reach the middle of the box, so probe the gutter beside
        # them instead: what matters is that the panel is under them all.
        gutter = (self.screen.rect.left + 8, self.screen.rect.centery)
        self.assertEqual(self.surface.get_at(gutter)[:3], PANEL)
        self.assertLessEqual(
            self.screen.row_rect(5).bottom,
            self.screen.list_rect.bottom,
            "the last row must still fit the window",
        )

    def test_a_long_name_does_not_stop_it(self):
        self.players[0].name = "A" * 60
        self.show()
        self.screen.draw(self.surface)
        self.assertEqual(self.surface.get_at(SCREEN_CENTER)[:3], PANEL)

    def test_the_caret_blinks_on_the_clock(self):
        self.show()
        self.screen.update(0)
        self.assertTrue(self.screen.field.caret_visible)
        self.screen.update(600)
        self.assertFalse(self.screen.field.caret_visible)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
