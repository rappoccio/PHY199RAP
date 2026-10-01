"""Phase 11 tests: the trade screen.

The screen is the other half of the deal :class:`monopoly.trade.Trade` strikes:
the trade says who may put up what, and the screen turns that into a partner
list, two columns of checkboxes and a click back into a move. So these tests
cover the geometry, which widgets come back live in each phase, what a click
does to the draft, what the footer reports, and that the panel and its scrim
actually reach the pixels.

Everything runs on a plain ``Surface``; no window is opened.
"""

from __future__ import annotations

import unittest

import pygame

from monopoly.player import Player
from monopoly.property import build_properties
from monopoly.trade import DRAFT, PARTNER, REVIEW, Trade
from monopoly.ui.trade_screen import (
    ACCEPT,
    BUILT_BADGE,
    CANCEL,
    MORTGAGE_BADGE,
    NAME_X,
    PROPOSE,
    REJECT,
    SCREEN_CENTER,
    SCREEN_SIZE,
    TradeScreen,
    _badge,
    _status,
    _title,
    row_flags,
)
from monopoly.ui.theme import ACCENT, DANGER, PANEL, clear_font_cache

TOKENS = ("red", "blue", "green", "yellow")
NAMES = ("Ada", "Bob", "Cleo", "Dai")

MEDITERRANEAN = 1
BALTIC = 3
READING = 5
ORIENTAL = 6


def click(pos, button: int = 1) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": button})


def motion(pos) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEMOTION, {"pos": pos, "rel": (0, 0)})


def wheel(y: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEWHEEL, {"x": 0, "y": y, "flipped": False})


def key(code, unicode_: str = "") -> pygame.event.Event:
    return pygame.event.Event(
        pygame.KEYDOWN, {"key": code, "mod": 0, "unicode": unicode_}
    )


def typed(text: str) -> list[pygame.event.Event]:
    return [key(ord(c), c) for c in text]


class ScreenTestCase(unittest.TestCase):
    """A screen showing a two-handed deal between Ada and Bob."""

    seats = 2
    cash = (1500, 1500, 1500, 1500)

    @classmethod
    def setUpClass(cls):
        pygame.init()
        clear_font_cache()

    def setUp(self):
        self.deeds = build_properties()
        self.players = [
            Player(n, c, t)
            for n, c, t in zip(NAMES[: self.seats], self.cash, TOKENS)
        ]
        self.ada, self.bob = self.players[0], self.players[1]
        self.screen = TradeScreen()
        self.surface = pygame.Surface((1280, 800))

    def deed(self, index):
        return next(d for d in self.deeds if d.index == index)

    def give(self, player, *indices):
        for index in indices:
            player.add_property(self.deed(index))

    def show(self, **kwargs) -> Trade:
        trade = Trade(self.ada, self.players, self.deeds, **kwargs)
        self.screen.trade = trade
        return trade

    def press(self, button) -> None:
        self.screen.handle_event(click(button.rect.center))

    def row_of(self, deed):
        """The visible row rectangle showing ``deed``, or ``None``."""
        for _column, shown, rect in self.screen.rows:
            if shown is deed:
                return rect
        return None


class LayoutTest(ScreenTestCase):
    def test_the_panel_sits_over_the_board_by_default(self):
        self.assertEqual(self.screen.rect.size, SCREEN_SIZE)
        self.assertEqual(self.screen.rect.center, SCREEN_CENTER)

    def test_an_explicit_rect_is_honoured(self):
        screen = TradeScreen((10, 20, 300, 400))
        self.assertEqual(screen.rect, pygame.Rect(10, 20, 300, 400))

    def test_the_blocks_stack_inside_the_panel(self):
        self.show()
        rects = [
            self.screen.title_rect,
            self.screen.status_rect,
            self.screen.body_rect,
            self.screen.footer_rect,
        ]
        for rect in rects:
            self.assertTrue(self.screen.rect.contains(rect), rect)
        for above, below in zip(rects, rects[1:]):
            self.assertLessEqual(above.bottom, below.top)

    def test_the_two_columns_split_the_body(self):
        self.show()
        left, right = self.screen.column_rect(0), self.screen.column_rect(1)
        self.assertEqual(left.width, right.width)
        self.assertLess(left.right, right.left)
        self.assertTrue(self.screen.body_rect.contains(left))
        self.assertTrue(self.screen.body_rect.contains(right))

    def test_a_column_stacks_its_cash_cards_and_deeds(self):
        self.show()
        cash = self.screen.cash_rect(0)
        cards = self.screen.goojf_rect(0)
        deeds = self.screen.list_rect(0)
        self.assertLessEqual(cash.bottom, cards.top)
        self.assertLessEqual(cards.bottom, deeds.top)
        self.assertTrue(self.screen.column_rect(0).contains(deeds))

    def test_the_jail_steps_sit_inside_their_row(self):
        self.show()
        row = self.screen.goojf_rect(0)
        minus = self.screen.goojf_step_rect(0, False)
        plus = self.screen.goojf_step_rect(0, True)
        self.assertTrue(row.contains(minus))
        self.assertTrue(row.contains(plus))
        self.assertFalse(minus.colliderect(plus))

    def test_the_footer_buttons_do_not_overlap(self):
        self.show()
        self.assertFalse(
            self.screen.primary.rect.colliderect(self.screen.secondary.rect)
        )
        for button in (self.screen.primary, self.screen.secondary):
            self.assertTrue(self.screen.footer_rect.contains(button.rect))

    def test_deed_rows_stack_without_overlapping(self):
        self.give(self.ada, MEDITERRANEAN, BALTIC, READING)
        self.show()
        rects = [r for c, _d, r in self.screen.rows if c == 0]
        self.assertEqual(len(rects), 3)
        for above, below in zip(rects, rects[1:]):
            self.assertLess(above.bottom, below.top)
        for rect in rects:
            self.assertTrue(self.screen.list_rect(0).contains(rect))

    def test_a_checkbox_sits_inside_its_row(self):
        self.give(self.ada, BALTIC)
        self.show()
        rect = self.row_of(self.deed(BALTIC))
        self.assertTrue(rect.contains(self.screen.box_rect(rect)))

    def test_the_chip_clears_both_the_checkbox_and_the_name(self):
        self.give(self.ada, BALTIC)
        self.show()
        rect = self.row_of(self.deed(BALTIC))
        chip = self.screen.chip_rect(rect)
        self.assertTrue(rect.contains(chip))
        self.assertFalse(chip.colliderect(self.screen.box_rect(rect)))
        self.assertLessEqual(chip.right, rect.left + NAME_X)

    def test_partner_buttons_stack_inside_the_body(self):
        screen = TradeScreen()
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        screen.trade = Trade(players[0], players, self.deeds)
        rects = [b.rect for b in screen.partner_buttons]
        self.assertEqual(len(rects), 3)
        for rect in rects:
            self.assertTrue(screen.body_rect.contains(rect))
        for above, below in zip(rects, rects[1:]):
            self.assertLess(above.bottom, below.top)


class VisibilityTest(ScreenTestCase):
    def test_a_screen_with_no_trade_shows_nothing(self):
        self.assertFalse(self.screen.visible)
        self.assertIsNone(self.screen.phase)
        self.assertEqual(self.screen.rows, [])

    def test_showing_a_trade_makes_it_visible(self):
        self.show()
        self.assertTrue(self.screen.visible)
        self.assertEqual(self.screen.phase, DRAFT)

    def test_clearing_it_hides_it_again(self):
        self.show()
        self.screen.trade = None
        self.assertFalse(self.screen.visible)
        self.assertEqual(self.screen.rows, [])

    def test_an_idle_screen_swallows_nothing(self):
        self.assertIsNone(self.screen.handle_event(click((400, 400))))

    def test_an_idle_screen_draws_nothing(self):
        before = pygame.transform.average_color(self.surface)
        self.screen.draw(self.surface)
        self.assertEqual(pygame.transform.average_color(self.surface), before)


class PartnerPhaseTest(ScreenTestCase):
    seats = 4

    def setUp(self):
        super().setUp()
        self.trade = self.show()

    def test_the_deal_opens_on_the_partner_question(self):
        self.assertEqual(self.screen.phase, PARTNER)
        self.assertEqual(len(self.screen.partner_buttons), 3)

    def test_no_deed_rows_are_drawn_yet(self):
        self.assertEqual(self.screen.rows, [])

    def test_a_candidate_s_button_names_them(self):
        self.assertIn("Bob", self.screen.partner_buttons[0].label)

    def test_a_button_counts_their_deeds(self):
        self.give(self.players[1], BALTIC, READING)
        self.screen.trade = self.trade  # rebuild the buttons
        self.assertIn("2 deeds", self.screen.partner_buttons[0].label)

    def test_clicking_one_settles_the_partner(self):
        self.press(self.screen.partner_buttons[1])
        self.assertIs(self.trade.partner, self.players[2])
        self.assertEqual(self.screen.phase, DRAFT)

    def test_choosing_opens_the_two_columns(self):
        self.press(self.screen.partner_buttons[0])
        self.assertIs(self.screen.player(1), self.players[1])

    def test_a_partner_click_reports_nothing(self):
        button = self.screen.partner_buttons[0]
        self.assertIsNone(self.screen.handle_event(click(button.rect.center)))

    def test_propose_is_dead_before_a_partner_is_chosen(self):
        self.assertFalse(self.screen.primary.enabled)

    def test_cancel_still_works(self):
        self.assertTrue(self.screen.secondary.enabled)
        self.assertEqual(
            self.screen.handle_event(click(self.screen.secondary.rect.center)),
            CANCEL,
        )

    def test_the_title_asks_the_question(self):
        self.assertIn("who with", _title(self.trade))

    def test_a_two_handed_table_never_asks(self):
        screen = TradeScreen()
        screen.trade = Trade(self.ada, self.players[:2], self.deeds)
        self.assertEqual(screen.phase, DRAFT)
        self.assertEqual(screen.partner_buttons, [])


class DeedRowTest(ScreenTestCase):
    def setUp(self):
        super().setUp()
        self.give(self.ada, MEDITERRANEAN, BALTIC)
        self.give(self.bob, ORIENTAL)
        self.trade = self.show()

    def test_each_side_lists_its_own_deeds(self):
        mine = [d for c, d, _r in self.screen.rows if c == 0]
        theirs = [d for c, d, _r in self.screen.rows if c == 1]
        self.assertEqual([d.index for d in mine], [MEDITERRANEAN, BALTIC])
        self.assertEqual([d.index for d in theirs], [ORIENTAL])

    def test_clicking_a_row_puts_the_deed_up(self):
        rect = self.row_of(self.deed(BALTIC))
        self.screen.handle_event(click(rect.center))
        self.assertTrue(self.trade.is_offered(self.deed(BALTIC)))

    def test_clicking_it_again_takes_it_back(self):
        rect = self.row_of(self.deed(BALTIC))
        self.screen.handle_event(click(rect.center))
        self.screen.handle_event(click(rect.center))
        self.assertFalse(self.trade.is_offered(self.deed(BALTIC)))

    def test_a_row_click_reports_nothing(self):
        rect = self.row_of(self.deed(BALTIC))
        self.assertIsNone(self.screen.handle_event(click(rect.center)))

    def test_the_partner_s_row_works_too(self):
        rect = self.row_of(self.deed(ORIENTAL))
        self.screen.handle_event(click(rect.center))
        self.assertTrue(self.trade.theirs.holds(self.deed(ORIENTAL)))

    def test_a_right_click_does_nothing(self):
        rect = self.row_of(self.deed(BALTIC))
        self.screen.handle_event(click(rect.center, button=3))
        self.assertFalse(self.trade.is_offered(self.deed(BALTIC)))

    def test_a_built_group_is_listed_but_dead(self):
        self.deed(MEDITERRANEAN).houses = 1
        self.screen.trade = self.trade
        rect = self.row_of(self.deed(BALTIC))
        self.assertIsNotNone(rect, "the deed is still shown")
        self.screen.handle_event(click(rect.center))
        self.assertFalse(self.trade.is_offered(self.deed(BALTIC)))

    def test_a_dead_row_still_swallows_its_click(self):
        self.deed(MEDITERRANEAN).houses = 1
        self.screen.trade = self.trade
        rect = self.row_of(self.deed(BALTIC))
        self.assertIsNone(self.screen.handle_event(click(rect.center)))

    def test_nothing_is_clickable_once_the_offer_is_out(self):
        self.trade.add_deed(self.deed(BALTIC))
        self.trade.propose()
        self.screen.sync()
        rect = self.row_of(self.deed(MEDITERRANEAN))
        self.screen.handle_event(click(rect.center))
        self.assertFalse(self.trade.is_offered(self.deed(MEDITERRANEAN)))

    def test_a_click_in_open_space_changes_nothing(self):
        self.screen.handle_event(click(self.screen.body_rect.bottomleft))
        self.assertTrue(self.trade.is_empty)


class ScrollTest(ScreenTestCase):
    def setUp(self):
        super().setUp()
        # Every deed on the board in one hand, so the column must scroll.
        for deed in self.deeds:
            self.ada.add_property(deed)
        self.trade = self.show()

    def test_only_a_windowful_is_built(self):
        rows = [r for r in self.screen.rows if r[0] == 0]
        self.assertEqual(len(rows), self.screen.visible_rows)
        self.assertLess(len(rows), len(self.deeds))

    def test_there_is_somewhere_to_scroll_to(self):
        self.assertGreater(self.screen.max_scroll(0), 0)

    def test_the_wheel_moves_the_column_under_the_pointer(self):
        self.screen.handle_event(motion(self.screen.list_rect(0).center))
        self.screen.handle_event(wheel(-1))
        self.assertEqual(self.screen.scroll[0], 1)
        self.assertEqual(self.screen.scroll[1], 0)

    def test_scrolling_shows_the_next_deed(self):
        first = self.screen.rows[0][1]
        self.screen.handle_event(motion(self.screen.list_rect(0).center))
        self.screen.handle_event(wheel(-1))
        self.assertIsNot(self.screen.rows[0][1], first)

    def test_the_wheel_over_nothing_moves_both(self):
        self.screen.handle_event(motion(self.screen.footer_rect.center))
        self.screen.handle_event(wheel(-1))
        self.assertEqual(self.screen.scroll[0], 1)

    def test_scrolling_stops_at_the_top(self):
        self.screen.scroll_by(0, -5)
        self.assertEqual(self.screen.scroll[0], 0)

    def test_scrolling_stops_at_the_bottom(self):
        self.screen.scroll_by(0, 500)
        self.assertEqual(self.screen.scroll[0], self.screen.max_scroll(0))

    def test_an_empty_column_has_nowhere_to_scroll(self):
        self.assertEqual(self.screen.max_scroll(1), 0)

    def test_a_scrolled_row_is_the_one_that_is_clicked(self):
        self.screen.scroll_by(0, 3)
        _column, deed, rect = self.screen.rows[0]
        self.screen.handle_event(click(rect.center))
        self.assertTrue(self.trade.is_offered(deed))

    def test_a_new_trade_starts_back_at_the_top(self):
        self.screen.scroll_by(0, 3)
        self.screen.trade = self.trade
        self.assertEqual(self.screen.scroll, [0, 0])

    def test_a_wheel_event_reports_nothing(self):
        self.assertIsNone(self.screen.handle_event(wheel(-1)))


class CashFieldTest(ScreenTestCase):
    cash = (1500, 200)

    def setUp(self):
        super().setUp()
        self.trade = self.show()

    def focus(self, column: int) -> None:
        self.screen.handle_event(click(self.screen.cash_rect(column).center))

    def type_into(self, column: int, text: str) -> None:
        self.focus(column)
        for event in typed(text):
            self.screen.handle_event(event)

    def test_typing_puts_the_cash_on_the_table(self):
        self.type_into(0, "250")
        self.assertEqual(self.trade.mine.cash, 250)

    def test_the_partner_s_field_fills_their_column(self):
        self.type_into(1, "100")
        self.assertEqual(self.trade.theirs.cash, 100)

    def test_more_than_is_held_is_clamped(self):
        self.type_into(1, "900")
        self.assertEqual(self.trade.theirs.cash, 200)
        self.assertEqual(self.screen.fields[1].value, "200")

    def test_typing_reports_nothing(self):
        self.focus(0)
        self.assertIsNone(self.screen.handle_event(key(ord("5"), "5")))

    def test_clearing_the_field_takes_the_cash_back_off(self):
        self.type_into(0, "250")
        for _ in range(3):
            self.screen.handle_event(key(pygame.K_BACKSPACE))
        self.assertEqual(self.trade.mine.cash, 0)

    def test_the_field_is_refilled_from_the_offer(self):
        self.trade.set_cash(self.ada, 400)
        self.screen.trade = self.trade
        self.assertEqual(self.screen.fields[0].value, "400")

    def test_an_empty_offer_leaves_the_field_blank(self):
        self.assertEqual(self.screen.fields[0].value, "")

    def test_cash_alone_lights_propose(self):
        self.assertFalse(self.screen.primary.enabled)
        self.type_into(0, "1")
        self.assertTrue(self.screen.primary.enabled)

    def test_the_field_is_frozen_once_the_offer_is_out(self):
        self.type_into(0, "250")
        self.trade.propose()
        self.screen.sync()
        self.type_into(0, "9")
        self.assertEqual(self.trade.mine.cash, 250)


class JailCardTest(ScreenTestCase):
    def setUp(self):
        super().setUp()
        self.ada.goojf_cards = 2
        self.trade = self.show()

    def step(self, column: int, plus: bool) -> None:
        self.press(self.screen.goojf_buttons[(column, plus)])

    def test_plus_puts_a_card_up(self):
        self.step(0, True)
        self.assertEqual(self.trade.mine.goojf, 1)

    def test_minus_takes_it_back(self):
        self.step(0, True)
        self.step(0, False)
        self.assertEqual(self.trade.mine.goojf, 0)

    def test_minus_is_dead_at_zero(self):
        self.assertFalse(self.screen.goojf_buttons[(0, False)].enabled)

    def test_plus_is_dead_at_the_last_card(self):
        self.step(0, True)
        self.step(0, True)
        self.assertEqual(self.trade.mine.goojf, 2)
        self.assertFalse(self.screen.goojf_buttons[(0, True)].enabled)

    def test_a_player_with_no_cards_has_both_dead(self):
        self.assertFalse(self.screen.goojf_buttons[(1, True)].enabled)
        self.assertFalse(self.screen.goojf_buttons[(1, False)].enabled)

    def test_a_step_reports_nothing(self):
        button = self.screen.goojf_buttons[(0, True)]
        self.assertIsNone(self.screen.handle_event(click(button.rect.center)))

    def test_a_card_alone_lights_propose(self):
        self.step(0, True)
        self.assertTrue(self.screen.primary.enabled)

    def test_the_steps_are_dead_once_the_offer_is_out(self):
        self.step(0, True)
        self.trade.propose()
        self.screen.sync()
        self.assertFalse(self.screen.goojf_buttons[(0, True)].enabled)
        self.step(0, True)
        self.assertEqual(self.trade.mine.goojf, 1)


class FooterTest(ScreenTestCase):
    def setUp(self):
        super().setUp()
        self.give(self.ada, BALTIC)
        self.trade = self.show()

    def test_the_draft_offers_propose_and_cancel(self):
        self.assertEqual(self.screen.primary.label, "Propose")
        self.assertEqual(self.screen.secondary.label, "Cancel")

    def test_propose_is_dead_on_an_empty_offer(self):
        self.assertFalse(self.screen.primary.enabled)

    def test_propose_lights_up_once_something_is_on_the_table(self):
        self.screen.handle_event(click(self.row_of(self.deed(BALTIC)).center))
        self.assertTrue(self.screen.primary.enabled)

    def test_pressing_propose_reports_it(self):
        self.trade.add_deed(self.deed(BALTIC))
        self.screen.refresh()
        self.assertEqual(
            self.screen.handle_event(click(self.screen.primary.rect.center)),
            PROPOSE,
        )

    def test_a_dead_propose_reports_nothing(self):
        self.assertIsNone(
            self.screen.handle_event(click(self.screen.primary.rect.center))
        )

    def test_pressing_cancel_reports_it(self):
        self.assertEqual(
            self.screen.handle_event(click(self.screen.secondary.rect.center)),
            CANCEL,
        )

    def test_the_review_offers_accept_and_reject(self):
        self.trade.add_deed(self.deed(BALTIC))
        self.trade.propose()
        self.screen.sync()
        self.assertEqual(self.screen.primary.label, "Accept")
        self.assertEqual(self.screen.secondary.label, "Reject")

    def test_pressing_accept_reports_it(self):
        self.trade.add_deed(self.deed(BALTIC))
        self.trade.propose()
        self.screen.sync()
        self.assertEqual(
            self.screen.handle_event(click(self.screen.primary.rect.center)),
            ACCEPT,
        )

    def test_pressing_reject_reports_it(self):
        self.trade.add_deed(self.deed(BALTIC))
        self.trade.propose()
        self.screen.sync()
        self.assertEqual(
            self.screen.handle_event(click(self.screen.secondary.rect.center)),
            REJECT,
        )

    def test_accept_is_dead_when_the_board_moved_under_the_offer(self):
        self.trade.add_deed(self.deed(BALTIC))
        self.trade.propose()
        self.bob.add_property(self.deed(BALTIC))
        self.screen.sync()
        self.assertFalse(self.screen.primary.enabled)

    def test_the_closing_callback_fires(self):
        seen = []
        self.screen.on_close = seen.append
        self.screen.handle_event(click(self.screen.secondary.rect.center))
        self.assertEqual(seen, [CANCEL])

    def test_hovering_does_not_close_anything(self):
        self.assertIsNone(
            self.screen.handle_event(motion(self.screen.secondary.rect.center))
        )


class SyncTest(ScreenTestCase):
    def setUp(self):
        super().setUp()
        self.give(self.ada, BALTIC)
        self.trade = self.show()

    def test_sync_follows_a_proposal(self):
        self.trade.add_deed(self.deed(BALTIC))
        self.trade.propose()
        self.assertEqual(self.screen.primary.label, "Propose")
        self.screen.sync()
        self.assertEqual(self.screen.phase, REVIEW)
        self.assertEqual(self.screen.primary.label, "Accept")

    def test_sync_is_idempotent(self):
        self.screen.sync()
        self.screen.sync()
        self.assertEqual(self.screen.phase, DRAFT)

    def test_sync_does_not_stamp_on_a_half_typed_field(self):
        field = self.screen.fields[0]
        field.text = "12"
        self.screen.sync()
        self.assertEqual(field.value, "12")

    def test_a_proposal_leaves_the_field_showing_the_offer(self):
        self.trade.set_cash(self.ada, 300)
        self.trade.propose()
        self.screen.sync()
        self.assertEqual(self.screen.fields[0].value, "300")

    def test_sync_with_nothing_to_show_is_harmless(self):
        self.screen.trade = None
        self.screen.sync()
        self.assertFalse(self.screen.visible)


class WordsTest(ScreenTestCase):
    def setUp(self):
        super().setUp()
        self.give(self.ada, BALTIC)
        self.trade = self.show()

    def test_the_draft_is_titled_for_the_proposer(self):
        self.assertEqual(_title(self.trade), "Trade -- Ada")

    def test_the_review_is_titled_for_the_partner(self):
        self.trade.add_deed(self.deed(BALTIC))
        self.trade.propose()
        self.assertEqual(_title(self.trade), "Offer to Bob")

    def test_an_empty_offer_complains(self):
        note, color = _status(self.trade)
        self.assertEqual(color, DANGER)
        self.assertIn("Nothing is on the table", note)

    def test_a_good_offer_says_so(self):
        self.trade.add_deed(self.deed(BALTIC))
        note, color = _status(self.trade)
        self.assertEqual(color, ACCENT)
        self.assertIn("propose", note)

    def test_a_review_asks_the_partner(self):
        self.trade.add_deed(self.deed(BALTIC))
        self.trade.propose()
        note, _color = _status(self.trade)
        self.assertIn("Bob", note)

    def test_a_plain_deed_wears_no_badge(self):
        self.assertEqual(_badge(self.deed(BALTIC), True)[0], "")

    def test_a_mortgaged_deed_is_flagged(self):
        self.deed(BALTIC).mortgaged = True
        self.assertEqual(_badge(self.deed(BALTIC), True)[0], MORTGAGE_BADGE)

    def test_a_built_group_is_flagged(self):
        self.assertEqual(_badge(self.deed(BALTIC), False)[0], BUILT_BADGE)

    def test_a_row_reads_as_tradable_and_unticked_to_start_with(self):
        self.assertEqual(row_flags(self.trade, self.deed(BALTIC)), (True, False))

    def test_a_row_on_the_table_reads_as_ticked(self):
        self.trade.add_deed(self.deed(BALTIC))
        self.assertEqual(row_flags(self.trade, self.deed(BALTIC)), (True, True))

    def test_a_built_group_reads_as_untradable(self):
        self.give(self.ada, MEDITERRANEAN)
        self.deed(MEDITERRANEAN).houses = 1
        self.assertEqual(row_flags(self.trade, self.deed(BALTIC))[0], False)

    def test_a_review_does_not_flag_every_row_as_built(self):
        # The screen once asked ``can_offer``, which goes false for the whole
        # board the moment the offer is out -- so a read-only review claimed
        # every lot was stuck behind houses.
        self.trade.add_deed(self.deed(BALTIC))
        self.trade.propose()
        self.assertEqual(row_flags(self.trade, self.deed(BALTIC)), (True, True))
        self.assertEqual(_badge(self.deed(BALTIC), True)[0], "")


class DrawTest(ScreenTestCase):
    def test_the_panel_reaches_the_pixels(self):
        self.give(self.ada, MEDITERRANEAN, BALTIC)
        self.give(self.bob, ORIENTAL)
        self.show()
        self.screen.draw(self.surface)
        self.assertEqual(self.surface.get_at(SCREEN_CENTER)[:3], PANEL)

    def test_the_scrim_darkens_the_board_behind_it(self):
        self.surface.fill((255, 255, 255))
        self.show()
        self.screen.draw(self.surface)
        corner = self.surface.get_at((5, 5))[:3]
        self.assertLess(sum(corner), 3 * 255)

    def test_the_partner_phase_draws(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        self.screen.trade = Trade(players[0], players, self.deeds)
        self.screen.draw(self.surface)
        self.assertEqual(self.surface.get_at(SCREEN_CENTER)[:3], PANEL)

    def test_a_review_draws(self):
        self.give(self.ada, BALTIC)
        trade = self.show()
        trade.add_deed(self.deed(BALTIC))
        trade.propose()
        self.screen.sync()
        self.screen.draw(self.surface)
        self.assertNotEqual(
            pygame.transform.average_color(self.surface)[:3], (0, 0, 0)
        )

    def test_an_empty_column_draws_its_note(self):
        self.show()
        self.screen.draw(self.surface)
        self.assertEqual(self.screen.rows, [])

    def test_a_ticked_row_draws(self):
        self.give(self.ada, BALTIC)
        trade = self.show()
        trade.add_deed(self.deed(BALTIC))
        self.screen.refresh()
        self.screen.draw(self.surface)
        self.assertTrue(trade.is_offered(self.deed(BALTIC)))

    def test_a_mortgaged_row_draws_its_badge(self):
        self.give(self.ada, BALTIC)
        self.deed(BALTIC).mortgaged = True
        self.show()
        self.screen.draw(self.surface)
        self.assertEqual(self.surface.get_at(SCREEN_CENTER)[:3], PANEL)

    def test_a_built_row_draws_greyed(self):
        self.give(self.ada, MEDITERRANEAN, BALTIC)
        self.deed(MEDITERRANEAN).houses = 1
        self.show()
        self.screen.draw(self.surface)
        self.assertEqual(self.surface.get_at(SCREEN_CENTER)[:3], PANEL)

    def test_a_long_roster_of_deeds_draws(self):
        for deed in self.deeds:
            self.ada.add_property(deed)
        self.show()
        self.screen.draw(self.surface)
        self.assertEqual(self.surface.get_at(SCREEN_CENTER)[:3], PANEL)

    def test_the_caret_blinks_with_the_clock(self):
        self.show()
        self.screen.fields[0].focused = True
        self.screen.update(0)
        self.assertTrue(self.screen.fields[0].caret_visible)
        self.screen.update(600)
        self.assertFalse(self.screen.fields[0].caret_visible)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
