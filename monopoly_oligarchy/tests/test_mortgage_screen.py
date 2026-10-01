"""Phase 12 tests: the mortgage screen.

The screen is the other half of the deal :class:`monopoly.mortgage.MortgageLedger`
strikes: the ledger says which deeds exist and which rows are live, and the
screen turns that into rows of buttons and a click back into an edit. So these
tests cover the geometry, the rows a ledger produces, which buttons come back
live, what a click does to the draft, and that the panel and its scrim actually
reach the pixels.

Everything runs on a plain ``Surface``; no window is opened.
"""

from __future__ import annotations

import unittest

import pygame

from monopoly.mortgage import BUILT_REASON, CASH_REASON, MortgageLedger
from monopoly.player import Player
from monopoly.property import build_properties
from monopoly.ui.mortgage_screen import (
    CANCEL,
    CONFIRM,
    LIFT_LABEL,
    MORTGAGE_LABEL,
    NAME_W,
    NAME_X,
    SCREEN_CENTER,
    SCREEN_SIZE,
    STATUS_X,
    TOGGLE_W,
    MortgageScreen,
    _status,
    _subtitle,
    _total_text,
)
from monopoly.ui.theme import ACCENT, DANGER, PANEL, TEXT_MUTED, clear_font_cache

MEDITERRANEAN, BALTIC = 1, 3
READING = 5
KENTUCKY = 21
BROWN = (MEDITERRANEAN, BALTIC)

#: Every deed on the board, for the scrolling tests.
EVERYTHING = tuple(p.index for p in build_properties())


def click(pos, button: int = 1) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": button})


def motion(pos) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEMOTION, {"pos": pos, "rel": (0, 0)})


def wheel(y: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEWHEEL, {"x": 0, "y": y})


class ScreenTestCase(unittest.TestCase):
    """A screen showing one player's brown group, all of it free to mortgage."""

    cash = 1500
    holdings = BROWN

    @classmethod
    def setUpClass(cls):
        pygame.init()
        clear_font_cache()

    def setUp(self):
        self.properties = build_properties()
        self.ada = Player("Ada", self.cash, "red")
        self.deeds = []
        for index in self.holdings:
            deed = self.deed(index)
            self.ada.add_property(deed)
            self.deeds.append(deed)
        self.deeds.sort(key=lambda p: p.index)
        self.screen = MortgageScreen()
        self.surface = pygame.Surface((1280, 800))

    def deed(self, index: int):
        for prop in self.properties:
            if prop.index == index:
                return prop
        raise AssertionError(f"no deed at {index}")

    def new_ledger(self, player=None) -> MortgageLedger:
        return MortgageLedger(
            player if player is not None else self.ada, self.properties
        )

    def show(self) -> MortgageLedger:
        ledger = self.new_ledger()
        self.screen.ledger = ledger
        return ledger

    def press(self, row: int) -> None:
        self.screen.handle_event(click(self.screen.toggles[row].rect.center))


class LayoutTest(ScreenTestCase):
    def test_the_panel_sits_over_the_board_by_default(self):
        self.assertEqual(self.screen.rect.size, SCREEN_SIZE)
        self.assertEqual(self.screen.rect.center, SCREEN_CENTER)

    def test_an_explicit_rect_is_honoured(self):
        screen = MortgageScreen((10, 20, 300, 400))
        self.assertEqual(screen.rect, pygame.Rect(10, 20, 300, 400))

    def test_the_blocks_stack_inside_the_panel(self):
        screen = self.screen
        for rect in (
            screen.title_rect,
            screen.subtitle_rect,
            screen.list_rect,
            screen.footer_rect,
        ):
            self.assertTrue(screen.rect.contains(rect), rect)

    def test_the_blocks_do_not_overlap(self):
        screen = self.screen
        self.assertLessEqual(screen.title_rect.bottom, screen.subtitle_rect.top)
        self.assertLessEqual(screen.subtitle_rect.bottom, screen.list_rect.top)
        self.assertLessEqual(screen.list_rect.bottom, screen.footer_rect.top)

    def test_the_list_has_room_to_draw_in(self):
        self.assertGreater(self.screen.list_rect.height, 100)

    def test_the_two_closing_buttons_sit_in_the_footer(self):
        screen = self.screen
        for button in (screen.confirm, screen.cancel):
            self.assertTrue(screen.footer_rect.contains(button.rect))
        self.assertLess(screen.cancel.rect.right, screen.confirm.rect.left)

    def test_a_rows_toggle_sits_at_its_right(self):
        self.show()
        rect = self.screen.row_rect(0)
        toggle = self.screen.toggle_rect(0)
        self.assertTrue(rect.contains(toggle))
        self.assertEqual(toggle.right, rect.right)
        self.assertEqual(toggle.width, TOGGLE_W)

    def test_the_rows_stack_without_overlapping(self):
        self.show()
        first, second = self.screen.row_rect(0), self.screen.row_rect(1)
        self.assertLess(first.bottom, second.top)

    def test_the_name_column_stops_short_of_the_status(self):
        self.assertLessEqual(NAME_X + NAME_W, STATUS_X)

    def test_the_status_column_stops_short_of_the_toggle(self):
        self.show()
        rect = self.screen.row_rect(0)
        self.assertLess(rect.left + STATUS_X, self.screen.toggle_rect(0).left)


class LedgerTest(ScreenTestCase):
    def test_a_fresh_screen_shows_nothing(self):
        self.assertIsNone(self.screen.ledger)
        self.assertFalse(self.screen.visible)
        self.assertEqual(self.screen.deeds, [])
        self.assertEqual(self.screen.toggles, {})

    def test_setting_a_ledger_makes_it_visible(self):
        self.show()
        self.assertTrue(self.screen.visible)
        self.assertEqual(self.screen.deeds, self.deeds)

    def test_clearing_it_hides_the_screen_again(self):
        self.show()
        self.screen.ledger = None
        self.assertFalse(self.screen.visible)
        self.assertEqual(self.screen.deeds, [])
        self.assertEqual(self.screen.toggles, {})
        self.assertFalse(self.screen.confirm.enabled)

    def test_the_rows_are_the_ledgers_deeds_in_order(self):
        ledger = self.show()
        self.assertEqual(self.screen.deeds, ledger.deeds)

    def test_a_player_with_no_deeds_gets_an_empty_list(self):
        ledger = self.new_ledger(Player("Bob", 1500, "blue"))
        self.screen.ledger = ledger
        self.assertTrue(self.screen.visible)
        self.assertTrue(ledger.is_empty)
        self.assertEqual(self.screen.deeds, [])
        self.assertEqual(self.screen.toggles, {})


class ButtonStateTest(ScreenTestCase):
    def test_every_deed_gets_a_toggle(self):
        self.show()
        self.assertEqual(sorted(self.screen.toggles), [0, 1])

    def test_a_free_lot_offers_to_be_mortgaged(self):
        self.show()
        for row in (0, 1):
            self.assertEqual(self.screen.toggles[row].label, MORTGAGE_LABEL)
            self.assertTrue(self.screen.toggles[row].enabled)

    def test_a_mortgaged_lot_offers_to_be_lifted(self):
        self.deeds[0].mortgaged = True
        self.show()
        self.assertEqual(self.screen.toggles[0].label, LIFT_LABEL)
        self.assertTrue(self.screen.toggles[0].enabled)

    def test_a_built_group_greys_every_row(self):
        self.deeds[0].houses = 1
        self.show()
        for row in (0, 1):
            self.assertFalse(self.screen.toggles[row].enabled)

    def test_a_mortgage_out_of_reach_is_greyed(self):
        self.ada.cash = 0
        self.deeds[0].mortgaged = True
        self.show()
        self.assertEqual(self.screen.toggles[0].label, LIFT_LABEL)
        self.assertFalse(self.screen.toggles[0].enabled)
        self.assertTrue(self.screen.toggles[1].enabled, "Baltic still mortgages")

    def test_confirm_is_dark_until_something_changes(self):
        self.show()
        self.assertFalse(self.screen.confirm.enabled)
        self.press(0)
        self.assertTrue(self.screen.confirm.enabled)

    def test_cancel_is_always_live(self):
        self.show()
        self.assertTrue(self.screen.cancel.enabled)

    def test_undoing_a_click_puts_confirm_out_again(self):
        self.show()
        self.press(0)
        self.press(0)
        self.assertFalse(self.screen.confirm.enabled)


class ClickTest(ScreenTestCase):
    def test_a_click_mortgages_in_the_draft_only(self):
        ledger = self.show()
        self.press(0)
        self.assertTrue(ledger.state(self.deeds[0]))
        self.assertFalse(self.deeds[0].mortgaged, "the board waits for Confirm")
        self.assertEqual(self.ada.cash, self.cash)

    def test_the_label_flips_after_the_click(self):
        self.show()
        self.press(0)
        self.assertEqual(self.screen.toggles[0].label, LIFT_LABEL)

    def test_a_click_reports_none_so_the_screen_stays_open(self):
        self.show()
        key = self.screen.handle_event(click(self.screen.toggles[0].rect.center))
        self.assertIsNone(key)

    def test_confirm_reports_confirm(self):
        self.show()
        self.press(0)
        key = self.screen.handle_event(click(self.screen.confirm.rect.center))
        self.assertEqual(key, CONFIRM)

    def test_cancel_reports_cancel(self):
        self.show()
        key = self.screen.handle_event(click(self.screen.cancel.rect.center))
        self.assertEqual(key, CANCEL)

    def test_a_dark_confirm_reports_nothing(self):
        self.show()
        key = self.screen.handle_event(click(self.screen.confirm.rect.center))
        self.assertIsNone(key)

    def test_a_greyed_row_swallows_its_click(self):
        self.deeds[0].houses = 1
        ledger = self.show()
        self.press(0)
        self.assertFalse(ledger.changed)

    def test_a_click_elsewhere_in_the_panel_does_nothing(self):
        ledger = self.show()
        self.screen.handle_event(click(self.screen.list_rect.topleft))
        self.assertFalse(ledger.changed)

    def test_a_hidden_screen_ignores_everything(self):
        self.assertIsNone(self.screen.handle_event(click((400, 400))))
        self.assertIsNone(self.screen.handle_event(wheel(-1)))

    def test_hovering_a_toggle_never_closes_the_screen(self):
        self.show()
        key = self.screen.handle_event(motion(self.screen.toggles[0].rect.center))
        self.assertIsNone(key)
        self.assertTrue(self.screen.toggles[0].hovered)

    def test_the_on_close_hook_fires_for_both_buttons(self):
        seen = []
        screen = MortgageScreen(on_close=seen.append)
        screen.ledger = self.new_ledger()
        screen.handle_event(click(screen.toggles[0].rect.center))
        screen.handle_event(click(screen.confirm.rect.center))
        screen.handle_event(click(screen.cancel.rect.center))
        self.assertEqual(seen, [CONFIRM, CANCEL])

    def test_one_click_can_pay_for_the_next(self):
        # Kentucky raises $110, exactly what lifting Reading costs, so the
        # second row only comes alive once the first has been clicked.
        self.ada.cash = 0
        reading = self.deed(READING)
        kentucky = self.deed(KENTUCKY)
        for deed in (reading, kentucky):
            self.ada.add_property(deed)
        reading.mortgaged = True
        ledger = self.show()
        rows = {deed: i for i, deed in enumerate(self.screen.deeds)}
        self.assertFalse(self.screen.toggles[rows[reading]].enabled)
        self.press(rows[kentucky])
        self.assertTrue(
            self.screen.toggles[rows[reading]].enabled,
            "the refresh after a click has to re-price the other rows",
        )
        self.press(rows[reading])
        self.assertEqual(ledger.cost, 0)


class ScrollTest(ScreenTestCase):
    """Twenty-eight deeds will not fit the panel, so the list scrolls."""

    holdings = EVERYTHING

    def test_more_rows_than_fit(self):
        self.show()
        self.assertGreater(len(self.screen.deeds), len(self.screen.visible_rows))
        self.assertGreater(self.screen.max_scroll, 0)

    def test_the_list_starts_at_the_top(self):
        self.show()
        self.assertEqual(self.screen.scroll, 0)
        self.assertEqual(self.screen.visible_rows[0], 0)

    def test_every_visible_row_is_inside_the_list(self):
        self.show()
        for row in self.screen.visible_rows:
            self.assertTrue(
                self.screen.list_rect.contains(self.screen.row_rect(row)),
                self.screen.deeds[row].name,
            )

    def test_only_visible_rows_carry_buttons(self):
        self.show()
        self.assertEqual(sorted(self.screen.toggles), self.screen.visible_rows)
        self.assertLess(len(self.screen.toggles), len(self.screen.deeds))

    def test_the_wheel_scrolls_the_list(self):
        self.show()
        self.screen.handle_event(wheel(-2))
        self.assertEqual(self.screen.scroll, 2)
        self.assertEqual(self.screen.visible_rows[0], 2)

    def test_scrolling_is_clamped_at_both_ends(self):
        self.show()
        self.screen.handle_event(wheel(5))
        self.assertEqual(self.screen.scroll, 0)
        self.screen.handle_event(wheel(-100))
        self.assertEqual(self.screen.scroll, self.screen.max_scroll)
        self.assertEqual(
            self.screen.visible_rows[-1], len(self.screen.deeds) - 1
        )

    def test_a_scrolled_row_keeps_its_place_above_the_window(self):
        self.show()
        self.screen.scroll_by(3)
        self.assertLess(self.screen.row_rect(0).top, self.screen.list_rect.top)

    def test_scrolling_rebuilds_the_buttons_for_the_new_rows(self):
        self.show()
        before = set(self.screen.toggles)
        self.screen.scroll_by(4)
        self.assertNotEqual(before, set(self.screen.toggles))
        for row in self.screen.toggles:
            self.assertTrue(
                self.screen.list_rect.contains(self.screen.row_rect(row))
            )

    def test_a_new_ledger_scrolls_back_to_the_top(self):
        self.show()
        self.screen.scroll_by(4)
        self.show()
        self.assertEqual(self.screen.scroll, 0)

    def test_a_scrolled_row_can_still_be_clicked(self):
        ledger = self.show()
        self.screen.scroll_by(4)
        row = self.screen.visible_rows[0]
        self.press(row)
        self.assertTrue(ledger.state(self.screen.deeds[row]))


class StatusTest(ScreenTestCase):
    def test_a_free_lot_shows_what_it_raises(self):
        ledger = self.show()
        text, color = _status(ledger, self.deeds[0])
        self.assertIn("$30", text)
        self.assertEqual(color, TEXT_MUTED)

    def test_a_mortgaged_lot_shows_what_it_costs_to_lift(self):
        self.deeds[0].mortgaged = True
        ledger = self.show()
        text, color = _status(ledger, self.deeds[0])
        self.assertIn("$33", text)
        self.assertEqual(color, DANGER)

    def test_a_built_group_shows_why_it_cannot_move(self):
        self.deeds[0].houses = 1
        ledger = self.show()
        self.assertEqual(_status(ledger, self.deeds[0])[0], BUILT_REASON)

    def test_a_mortgage_out_of_reach_says_so(self):
        self.ada.cash = 0
        self.deeds[0].mortgaged = True
        ledger = self.show()
        self.assertEqual(_status(ledger, self.deeds[0])[0], CASH_REASON)

    def test_the_status_follows_the_draft_not_the_board(self):
        ledger = self.show()
        ledger.mortgage(self.deeds[0])
        self.assertIn("$33", _status(ledger, self.deeds[0])[0])

    def test_the_subtitle_explains_itself_before_any_click(self):
        ledger = self.show()
        self.assertIn("110%", _subtitle(ledger))

    def test_the_subtitle_totals_the_draft_afterwards(self):
        ledger = self.show()
        ledger.mortgage(self.deeds[0])
        self.assertIn("$30", _subtitle(ledger))

    def test_an_untouched_total_reads_as_nothing(self):
        self.assertEqual(_total_text(self.show()), "$0")

    def test_a_mortgage_reads_as_a_payout(self):
        ledger = self.show()
        ledger.mortgage(self.deeds[0])
        self.assertEqual(_total_text(ledger), "+$30")

    def test_a_lift_reads_as_a_bill(self):
        self.deeds[0].mortgaged = True
        ledger = self.show()
        ledger.unmortgage(self.deeds[0])
        self.assertEqual(_total_text(ledger), "-$33")

    def test_an_undone_click_reads_as_nothing_again(self):
        ledger = self.show()
        ledger.mortgage(self.deeds[0])
        ledger.unmortgage(self.deeds[0])
        self.assertEqual(_total_text(ledger), "$0")


class DrawTest(ScreenTestCase):
    def test_a_hidden_screen_draws_nothing(self):
        self.surface.fill((0, 0, 0))
        self.screen.draw(self.surface)
        self.assertEqual(tuple(self.surface.get_at((400, 400)))[:3], (0, 0, 0))

    def test_the_panel_reaches_the_pixels(self):
        self.show()
        self.surface.fill((255, 255, 255))
        self.screen.draw(self.surface)
        self.assertEqual(
            tuple(self.surface.get_at(self.screen.rect.center))[:3], PANEL
        )

    def test_the_scrim_dims_the_board_behind_it(self):
        self.show()
        self.surface.fill((255, 255, 255))
        self.screen.draw(self.surface)
        outside = self.surface.get_at((5, 5))
        self.assertLess(outside.r, 255)
        self.assertGreater(outside.r, 0)

    def test_the_empty_note_draws_without_rows(self):
        self.screen.ledger = self.new_ledger(Player("Bob", 1500, "blue"))
        self.screen.draw(self.surface)  # must not raise

    def test_the_group_chip_reaches_the_pixels(self):
        self.show()
        self.surface.fill((0, 0, 0))
        self.screen.draw(self.surface)
        rect = self.screen.row_rect(0)
        chip = self.surface.get_at((rect.left + 2, rect.centery))
        self.assertEqual(tuple(chip)[:3], (124, 74, 46))  # brown

    def test_every_row_of_a_full_hand_draws(self):
        for index in EVERYTHING:
            deed = self.deed(index)
            if deed.owner is None:
                self.ada.add_property(deed)
        self.show()
        self.screen.draw(self.surface)  # must not raise

    def test_a_mortgaged_row_draws(self):
        self.deeds[0].mortgaged = True
        self.show()
        self.screen.draw(self.surface)

    def test_a_greyed_row_draws(self):
        self.deeds[0].has_hotel = True
        self.show()
        self.screen.draw(self.surface)

    def test_a_drafted_bill_draws_in_the_danger_colour(self):
        self.deeds[0].mortgaged = True
        ledger = self.show()
        ledger.unmortgage(self.deeds[0])
        self.assertEqual(ledger.charge, 33)
        self.screen.refresh()
        self.screen.draw(self.surface)

    def test_the_players_cash_is_on_the_panel(self):
        self.show()
        self.surface.fill((0, 0, 0))
        self.screen.draw(self.surface)
        strip = self.surface.subsurface(self.screen.title_rect).copy()
        colours = {tuple(strip.get_at((x, y))[:3]) for x in range(strip.get_width())
                   for y in range(strip.get_height())}
        self.assertIn(ACCENT, colours)


if __name__ == "__main__":
    unittest.main()
