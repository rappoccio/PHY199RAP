"""Phase 9 tests: the build screen.

The screen is the other half of the deal :class:`monopoly.building.BuildPlan`
strikes: the plan says which lots exist and which ``+`` / ``-`` are legal, and
the screen turns that into rows of buttons and a click back into an edit. So
these tests cover the geometry, the rows a plan produces, which buttons come
back live, what a click does to the draft, and that the panel and its scrim
actually reach the pixels.

Everything runs on a plain ``Surface``; no window is opened.
"""

from __future__ import annotations

import unittest

import pygame

from monopoly.building import Bank, BuildPlan
from monopoly.player import Player
from monopoly.property import HOTEL_LEVEL, MAX_HOUSES, build_properties
from monopoly.ui.build_screen import (
    BUILDINGS_X,
    CANCEL,
    CONFIRM,
    NAME_W,
    NAME_X,
    SCREEN_CENTER,
    SCREEN_SIZE,
    BuildScreen,
)
from monopoly.ui.theme import HOUSE_COLOR, PANEL, clear_font_cache

BROWN = (1, 3)
LIGHT_BLUE = (6, 8, 9)
ORANGE = (16, 18, 19)
RED = (21, 23, 24)
YELLOW = (26, 27, 29)
GREEN = (31, 32, 34)


def click(pos, button: int = 1) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": button})


def motion(pos) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEMOTION, {"pos": pos, "rel": (0, 0)})


def wheel(y: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEWHEEL, {"x": 0, "y": y})


class ScreenTestCase(unittest.TestCase):
    """A screen showing one player's brown group, with room to build."""

    cash = 2000
    groups = (BROWN,)

    @classmethod
    def setUpClass(cls):
        pygame.init()
        clear_font_cache()

    def setUp(self):
        self.properties = build_properties()
        self.bank = Bank()
        self.ada = Player("Ada", self.cash, "red")
        self.lots = []
        for group in self.groups:
            for deed in (p for p in self.properties if p.index in group):
                self.ada.add_property(deed)
                self.lots.append(deed)
        self.lots.sort(key=lambda p: p.index)
        self.screen = BuildScreen()
        self.surface = pygame.Surface((1280, 800))

    def new_plan(self) -> BuildPlan:
        return BuildPlan(self.ada, self.properties, self.bank)

    def show(self) -> BuildPlan:
        plan = self.new_plan()
        self.screen.plan = plan
        return plan

    def lot_rows(self) -> list[int]:
        """The indices of the screen's lot rows, in order."""
        return [i for i, (kind, _) in enumerate(self.screen.rows) if kind == "lot"]

    def press_add(self, row: int) -> None:
        self.screen.handle_event(click(self.screen.add_buttons[row].rect.center))

    def press_remove(self, row: int) -> None:
        self.screen.handle_event(click(self.screen.remove_buttons[row].rect.center))


class LayoutTest(ScreenTestCase):
    def test_the_panel_sits_over_the_board_by_default(self):
        self.assertEqual(self.screen.rect.size, SCREEN_SIZE)
        self.assertEqual(self.screen.rect.center, SCREEN_CENTER)

    def test_an_explicit_rect_is_honoured(self):
        screen = BuildScreen((10, 20, 300, 400))
        self.assertEqual(screen.rect, pygame.Rect(10, 20, 300, 400))

    def test_the_blocks_stack_inside_the_panel(self):
        screen = self.screen
        for rect in (
            screen.title_rect,
            screen.supply_rect,
            screen.list_rect,
            screen.footer_rect,
        ):
            self.assertTrue(screen.rect.contains(rect), rect)

    def test_the_blocks_do_not_overlap(self):
        screen = self.screen
        self.assertLessEqual(screen.title_rect.bottom, screen.supply_rect.top)
        self.assertLessEqual(screen.supply_rect.bottom, screen.list_rect.top)
        self.assertLessEqual(screen.list_rect.bottom, screen.footer_rect.top)

    def test_the_list_has_room_to_draw_in(self):
        self.assertGreater(self.screen.list_rect.height, 100)

    def test_the_two_closing_buttons_sit_in_the_footer(self):
        screen = self.screen
        for button in (screen.confirm, screen.cancel):
            self.assertTrue(screen.footer_rect.contains(button.rect))
        self.assertLess(screen.cancel.rect.right, screen.confirm.rect.left)

    def test_a_lot_rows_steps_sit_at_its_right(self):
        self.show()
        row = self.lot_rows()[0]
        rect = self.screen.row_rect(row)
        minus, plus = self.screen.step_rects(row)
        self.assertTrue(rect.contains(minus))
        self.assertTrue(rect.contains(plus))
        self.assertLess(minus.right, plus.left)


class PlanTest(ScreenTestCase):
    def test_a_fresh_screen_shows_nothing(self):
        self.assertIsNone(self.screen.plan)
        self.assertFalse(self.screen.visible)
        self.assertEqual(self.screen.rows, [])
        self.assertEqual(self.screen.add_buttons, {})

    def test_setting_a_plan_makes_it_visible(self):
        self.show()
        self.assertTrue(self.screen.visible)
        self.assertTrue(self.screen.rows)

    def test_clearing_the_plan_hides_it_again(self):
        self.show()
        self.screen.plan = None
        self.assertFalse(self.screen.visible)
        self.assertEqual(self.screen.rows, [])
        self.assertEqual(self.screen.remove_buttons, {})
        self.assertFalse(self.screen.confirm.enabled)

    def test_a_group_header_leads_its_lots(self):
        self.show()
        self.assertEqual(self.screen.rows[0], ("group", "brown"))
        self.assertEqual(
            [item for kind, item in self.screen.rows if kind == "lot"], self.lots
        )

    def test_a_player_with_nothing_to_build_gets_an_empty_list(self):
        plan = BuildPlan(Player("Bob", 1500, "blue"), self.properties, self.bank)
        self.screen.plan = plan
        self.assertTrue(self.screen.visible)
        self.assertTrue(plan.is_empty)
        self.assertEqual(self.screen.rows, [])


class ButtonStateTest(ScreenTestCase):
    def test_every_lot_gets_a_pair_of_steps(self):
        self.show()
        rows = self.lot_rows()
        self.assertEqual(sorted(self.screen.add_buttons), rows)
        self.assertEqual(sorted(self.screen.remove_buttons), rows)

    def test_a_bare_group_can_be_built_but_not_sold(self):
        self.show()
        for row in self.lot_rows():
            self.assertTrue(self.screen.add_buttons[row].enabled)
            self.assertFalse(self.screen.remove_buttons[row].enabled)

    def test_the_even_build_rule_greys_the_neighbour(self):
        self.show()
        first, second = self.lot_rows()
        self.press_add(first)
        self.assertFalse(self.screen.add_buttons[first].enabled)
        self.assertTrue(self.screen.add_buttons[second].enabled)
        self.assertTrue(self.screen.remove_buttons[first].enabled)

    def test_a_broke_player_gets_no_plus(self):
        self.ada.cash = 0
        self.show()
        for row in self.lot_rows():
            self.assertFalse(self.screen.add_buttons[row].enabled)

    def test_an_empty_box_greys_every_plus(self):
        self.bank.houses = 0
        self.show()
        for row in self.lot_rows():
            self.assertFalse(self.screen.add_buttons[row].enabled)

    def test_confirm_wakes_up_once_the_draft_changes(self):
        self.show()
        self.assertFalse(self.screen.confirm.enabled)
        self.press_add(self.lot_rows()[0])
        self.assertTrue(self.screen.confirm.enabled)

    def test_undoing_the_draft_puts_confirm_back_to_sleep(self):
        self.show()
        row = self.lot_rows()[0]
        self.press_add(row)
        self.press_remove(row)
        self.assertFalse(self.screen.confirm.enabled)

    def test_cancel_is_always_live(self):
        self.show()
        self.assertTrue(self.screen.cancel.enabled)


class ClickTest(ScreenTestCase):
    def test_plus_builds_on_the_draft(self):
        plan = self.show()
        row = self.lot_rows()[0]
        self.press_add(row)
        self.assertEqual(plan.level(self.lots[0]), 1)
        self.assertEqual(plan.cost, 50)

    def test_minus_takes_it_off_again(self):
        plan = self.show()
        row = self.lot_rows()[0]
        self.press_add(row)
        self.press_remove(row)
        self.assertEqual(plan.level(self.lots[0]), 0)
        self.assertFalse(plan.changed)

    def test_a_step_click_reports_nothing_and_stays_open(self):
        self.show()
        row = self.lot_rows()[0]
        key = self.screen.handle_event(click(self.screen.add_buttons[row].rect.center))
        self.assertIsNone(key)
        self.assertTrue(self.screen.visible)

    def test_a_disabled_plus_does_nothing(self):
        plan = self.show()
        first, second = self.lot_rows()
        self.press_add(first)
        self.press_add(first)  # the even-build rule says no
        self.assertEqual(plan.level(self.lots[0]), 1)

    def test_confirm_reports_itself(self):
        self.show()
        self.press_add(self.lot_rows()[0])
        key = self.screen.handle_event(click(self.screen.confirm.rect.center))
        self.assertEqual(key, CONFIRM)

    def test_confirm_stays_quiet_while_nothing_has_changed(self):
        self.show()
        where = click(self.screen.confirm.rect.center)
        self.assertIsNone(self.screen.handle_event(where))

    def test_cancel_reports_itself(self):
        self.show()
        key = self.screen.handle_event(click(self.screen.cancel.rect.center))
        self.assertEqual(key, CANCEL)

    def test_a_click_elsewhere_reports_nothing(self):
        self.show()
        self.assertIsNone(self.screen.handle_event(click((5, 5))))

    def test_a_hidden_screen_swallows_nothing(self):
        self.assertIsNone(self.screen.handle_event(click((400, 400))))
        self.assertIsNone(self.screen.handle_event(wheel(1)))

    def test_hovering_never_reports_a_choice(self):
        self.show()
        where = motion(self.screen.confirm.rect.center)
        self.assertIsNone(self.screen.handle_event(where))
        self.assertTrue(self.screen.confirm.hovered is False)

    def test_on_close_fires_for_the_footer_buttons(self):
        seen = []
        self.screen.on_close = seen.append
        self.show()
        self.screen.handle_event(click(self.screen.cancel.rect.center))
        self.assertEqual(seen, [CANCEL])

    def test_building_to_a_hotel_through_the_buttons(self):
        plan = self.show()
        rows = self.lot_rows()
        for _ in range(HOTEL_LEVEL):
            for row in rows:
                self.press_add(row)
        self.assertEqual([plan.level(lot) for lot in self.lots], [HOTEL_LEVEL] * 2)
        self.assertEqual(plan.hotels, 10)
        self.assertEqual(plan.cost, 500)


class ScrollTest(ScreenTestCase):
    """Six whole groups will not fit the panel, so the list scrolls."""

    cash = 20_000
    groups = (BROWN, LIGHT_BLUE, ORANGE, RED, YELLOW, GREEN)

    def test_the_list_starts_at_the_top(self):
        self.show()
        self.assertEqual(self.screen.scroll, 0)
        self.assertEqual(self.screen.visible_rows[0], 0)

    def test_more_rows_than_fit(self):
        self.show()
        self.assertGreater(len(self.screen.rows), len(self.screen.visible_rows))
        self.assertGreater(self.screen.max_scroll, 0)

    def test_every_visible_row_is_inside_the_list(self):
        self.show()
        for row in self.screen.visible_rows:
            self.assertTrue(
                self.screen.list_rect.contains(self.screen.row_rect(row)),
                self.screen.rows[row],
            )

    def test_only_visible_lots_carry_buttons(self):
        self.show()
        visible = set(self.screen.visible_rows)
        self.assertTrue(set(self.screen.add_buttons) <= visible)
        self.assertLess(len(self.screen.add_buttons), len(self.lots))

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
        self.assertEqual(self.screen.visible_rows[-1], len(self.screen.rows) - 1)

    def test_a_scrolled_row_keeps_its_place_above_the_window(self):
        self.show()
        self.screen.scroll_by(3)
        self.assertLess(self.screen.row_rect(0).top, self.screen.list_rect.top)

    def test_scrolling_rebuilds_the_buttons_for_the_new_rows(self):
        self.show()
        before = set(self.screen.add_buttons)
        self.screen.scroll_by(4)
        self.assertNotEqual(before, set(self.screen.add_buttons))
        for row in self.screen.add_buttons:
            self.assertTrue(self.screen.list_rect.contains(self.screen.row_rect(row)))

    def test_a_new_plan_scrolls_back_to_the_top(self):
        self.show()
        self.screen.scroll_by(4)
        self.show()
        self.assertEqual(self.screen.scroll, 0)


class DrawTest(ScreenTestCase):
    def test_a_hidden_screen_draws_nothing(self):
        self.surface.fill((0, 0, 0))
        self.screen.draw(self.surface)
        self.assertEqual(tuple(self.surface.get_at((400, 400)))[:3], (0, 0, 0))

    def test_the_panel_reaches_the_pixels(self):
        self.show()
        self.surface.fill((255, 255, 255))
        self.screen.draw(self.surface)
        self.assertEqual(tuple(self.surface.get_at(self.screen.rect.center))[:3], PANEL)

    def test_the_scrim_dims_the_board_behind_it(self):
        self.show()
        self.surface.fill((255, 255, 255))
        self.screen.draw(self.surface)
        outside = self.surface.get_at((5, 5))
        self.assertLess(outside.r, 255)
        self.assertGreater(outside.r, 0)

    def test_the_empty_note_draws_without_rows(self):
        self.screen.plan = BuildPlan(
            Player("Bob", 1500, "blue"), self.properties, self.bank
        )
        self.screen.draw(self.surface)  # must not raise

    def test_a_full_board_of_buildings_draws(self):
        plan = self.show()
        for _ in range(HOTEL_LEVEL):
            for lot in self.lots:
                plan.add(lot)
        self.screen.refresh()
        self.screen.draw(self.surface)

    def test_the_name_column_does_not_reach_the_buildings(self):
        self.assertLessEqual(NAME_X + NAME_W, BUILDINGS_X)

    def test_a_long_name_is_cut_rather_than_drawn_over_its_houses(self):
        plan = self.show()
        for lot in self.lots:  # Mediterranean Avenue is the longest on the board
            plan.add(lot)
        self.screen.refresh()
        self.surface.fill((0, 0, 0))
        self.screen.draw(self.surface)
        row = self.lot_rows()[0]
        rect = self.screen.row_rect(row)
        house = (rect.left + BUILDINGS_X + 2, rect.centery)
        self.assertEqual(tuple(self.surface.get_at(house))[:3], HOUSE_COLOR)

    def test_houses_and_hotels_both_draw(self):
        plan = self.show()
        for _ in range(MAX_HOUSES):
            for lot in self.lots:
                plan.add(lot)
        self.screen.refresh()
        self.screen.draw(self.surface)
        plan.add(self.lots[0])
        self.screen.refresh()
        self.screen.draw(self.surface)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
