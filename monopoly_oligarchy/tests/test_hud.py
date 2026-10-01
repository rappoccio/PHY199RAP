"""Phase 6 tests: the right-hand HUD panel.

The HUD is handed a :class:`HudState` and draws exactly that -- it decides no
rules of its own -- so these tests cover three things: the panel's geometry,
what a state does to the action buttons and the deed list, and what actually
lands on the pixels (token colours, group chips, houses and hotels).

Everything runs on a plain ``Surface``; no window is opened.
"""

from __future__ import annotations

import random
import unittest

import pygame

from monopoly.dice import Dice
from monopoly.player import Player
from monopoly.property import build_properties
from monopoly.ui.dice_view import die_rects, dice_size
from monopoly.ui.hud import (
    ACTION_ROWS,
    EMPTY_LIST_TEXT,
    MAX_OTHER_PLAYERS,
    PRIMARY_ACTIONS,
    Action,
    Hud,
    HudState,
    deed_label,
    token_rgb,
)
from monopoly.ui.renderer import HUD_RECT, Renderer
from monopoly.ui.theme import (
    ACCENT,
    DANGER,
    GROUP_COLORS,
    HOTEL_COLOR,
    HOUSE_COLOR,
    PANEL,
    SPACE_BG,
    TEXT,
    TEXT_MUTED,
    TOKEN_RGB,
    SCREEN_SIZE,
    clear_font_cache,
)


def click(pos, button: int = 1) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": button})


def motion(pos) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEMOTION, {"pos": pos, "rel": (0, 0)})


def wheel(y: int) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEWHEEL, {"x": 0, "y": y, "flipped": False})


def rgb(surface: pygame.Surface, pos) -> tuple[int, int, int]:
    return tuple(surface.get_at(pos))[:3]


def has_color(surface: pygame.Surface, rect: pygame.Rect, color) -> bool:
    """Whether ``color`` appears anywhere inside ``rect``."""
    for x in range(rect.left, rect.right):
        for y in range(rect.top, rect.bottom):
            if rgb(surface, (x, y)) == tuple(color):
                return True
    return False


def count_color(surface: pygame.Surface, rect: pygame.Rect, color) -> int:
    """How many pixels of ``color`` are inside ``rect``."""
    total = 0
    for x in range(rect.left, rect.right):
        for y in range(rect.top, rect.bottom):
            if rgb(surface, (x, y)) == tuple(color):
                total += 1
    return total


class HudTestCase(unittest.TestCase):
    """Fonts are needed to draw; no display is."""

    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        # Another module may have shut the font module down; anything cached
        # before that is freed memory.
        clear_font_cache()

    def setUp(self) -> None:
        self.properties = build_properties()
        self.deeds = {p.index: p for p in self.properties}
        #: Every deed on the board -- more than the list can show at once.
        self.all_deeds = [p.index for p in self.properties]
        self.ada = Player("Ada", 1500, "red")
        self.bob = Player("Bob", 900, "blue")
        self.cy = Player("Cy", 250, "green")
        self.players = [self.ada, self.bob, self.cy]
        self.hud = Hud(HUD_RECT)

    def surface(self) -> pygame.Surface:
        return pygame.Surface(SCREEN_SIZE)

    def give(self, player: Player, *indexes: int) -> None:
        for index in indexes:
            player.add_property(self.deeds[index])

    def show(self, **kwargs) -> pygame.Surface:
        """Set a state built from ``kwargs`` and draw one frame."""
        kwargs.setdefault("players", self.players)
        kwargs.setdefault("current", self.ada)
        kwargs.setdefault("properties", self.properties)
        self.hud.state = HudState(**kwargs)
        surface = self.surface()
        self.hud.draw(surface)
        return surface


class TestLayout(HudTestCase):
    def test_the_panel_takes_the_rect_it_is_given(self) -> None:
        self.assertEqual(self.hud.rect, HUD_RECT)

    def test_every_block_sits_inside_the_panel(self) -> None:
        blocks = (
            self.hud.header_rect,
            self.hud.dice_rect,
            self.hud.message_rect,
            self.hud.list_title_rect,
            self.hud.property_list_rect,
            self.hud.buttons_rect,
            self.hud.roster_rect,
        )
        for block in blocks:
            with self.subTest(block=block):
                self.assertTrue(HUD_RECT.contains(block))

    def test_the_blocks_stack_top_to_bottom_without_overlapping(self) -> None:
        order = (
            self.hud.header_rect,
            self.hud.dice_rect,
            self.hud.message_rect,
            self.hud.list_title_rect,
            self.hud.property_list_rect,
            self.hud.buttons_rect,
            self.hud.roster_rect,
        )
        for above, below in zip(order, order[1:]):
            with self.subTest(above=above, below=below):
                self.assertLessEqual(above.bottom, below.top)

    def test_the_deed_list_has_room_for_several_rows(self) -> None:
        self.assertGreaterEqual(self.hud.visible_rows, 4)

    def test_every_visible_row_fits_the_deed_list(self) -> None:
        for row in range(self.hud.visible_rows):
            with self.subTest(row=row):
                self.assertTrue(
                    self.hud.property_list_rect.contains(self.hud.row_rect(row))
                )

    def test_a_panel_of_another_size_relays_itself(self) -> None:
        hud = Hud((0, 0, 400, 600))
        self.assertTrue(hud.rect.contains(hud.buttons_rect))
        self.assertTrue(hud.rect.contains(hud.roster_rect))
        self.assertGreaterEqual(hud.visible_rows, 1)


class TestButtonLayout(HudTestCase):
    def test_every_action_has_a_button(self) -> None:
        self.assertEqual(set(self.hud.buttons), set(Action))
        self.assertEqual(
            sum(len(row) for row in ACTION_ROWS), len(Action)
        )

    def test_buttons_are_labelled_by_their_action(self) -> None:
        for action, button in self.hud.buttons.items():
            with self.subTest(action=action):
                self.assertEqual(button.label, action.value)

    def test_buttons_sit_inside_the_button_block(self) -> None:
        for action, button in self.hud.buttons.items():
            with self.subTest(action=action):
                self.assertTrue(self.hud.buttons_rect.contains(button.rect))

    def test_no_two_buttons_overlap(self) -> None:
        rects = [b.rect for b in self.hud.buttons.values()]
        for i, first in enumerate(rects):
            for second in rects[i + 1:]:
                self.assertFalse(first.colliderect(second))

    def test_roll_spans_the_panel_and_the_pairs_split_it(self) -> None:
        roll = self.hud.buttons[Action.ROLL]
        self.assertEqual(roll.rect.width, self.hud.buttons_rect.width)
        build = self.hud.buttons[Action.BUILD].rect
        mortgage = self.hud.buttons[Action.MORTGAGE].rect
        self.assertEqual(build.top, mortgage.top)
        self.assertLess(build.right, mortgage.left)

    def test_roll_and_end_turn_are_the_primary_buttons(self) -> None:
        for action, button in self.hud.buttons.items():
            with self.subTest(action=action):
                self.assertEqual(button.primary, action in PRIMARY_ACTIONS)


class TestState(HudTestCase):
    def test_a_fresh_hud_has_every_button_disabled(self) -> None:
        self.assertFalse(any(b.enabled for b in self.hud.buttons.values()))

    def test_a_state_enables_exactly_the_available_actions(self) -> None:
        self.hud.state = HudState(available=frozenset({Action.ROLL, Action.TRADE}))
        enabled = {a for a, b in self.hud.buttons.items() if b.enabled}
        self.assertEqual(enabled, {Action.ROLL, Action.TRADE})

    def test_a_later_state_disables_what_it_leaves_out(self) -> None:
        self.hud.state = HudState(available=frozenset({Action.ROLL}))
        self.hud.state = HudState(available=frozenset({Action.END_TURN}))
        self.assertFalse(self.hud.buttons[Action.ROLL].enabled)
        self.assertTrue(self.hud.buttons[Action.END_TURN].enabled)

    def test_a_hud_can_be_built_with_a_state(self) -> None:
        hud = Hud(HUD_RECT, state=HudState(available=frozenset({Action.BUILD})))
        self.assertTrue(hud.buttons[Action.BUILD].enabled)

    def test_is_available_answers_for_the_state(self) -> None:
        state = HudState(available=frozenset({Action.BUILD}))
        self.assertTrue(state.is_available(Action.BUILD))
        self.assertFalse(state.is_available(Action.ROLL))

    def test_deeds_are_the_current_players_in_board_order(self) -> None:
        self.give(self.ada, 39, 1, 5)
        self.give(self.bob, 6)
        self.hud.state = HudState(players=self.players, current=self.ada)
        self.assertEqual([d.index for d in self.hud.deeds], [1, 5, 39])

    def test_deeds_are_empty_without_a_current_player(self) -> None:
        self.give(self.ada, 1)
        self.hud.state = HudState(players=self.players)
        self.assertEqual(self.hud.deeds, [])

    def test_others_is_every_player_but_the_current_one(self) -> None:
        self.hud.state = HudState(players=self.players, current=self.bob)
        self.assertEqual(self.hud.others, [self.ada, self.cy])

    def test_without_a_current_player_everyone_is_an_other(self) -> None:
        self.hud.state = HudState(players=self.players)
        self.assertEqual(self.hud.others, self.players)


class TestScrolling(HudTestCase):
    def test_a_short_list_cannot_scroll(self) -> None:
        self.give(self.ada, 1, 3)
        self.hud.state = HudState(players=self.players, current=self.ada)
        self.assertEqual(self.hud.max_scroll, 0)
        self.hud.scroll_by(5)
        self.assertEqual(self.hud.scroll, 0)

    def test_a_long_list_scrolls_to_its_last_page(self) -> None:
        self.give(self.ada, *self.all_deeds)
        self.hud.state = HudState(players=self.players, current=self.ada)
        expected = len(self.hud.deeds) - self.hud.visible_rows
        self.assertEqual(self.hud.max_scroll, expected)
        self.hud.scroll_by(1000)
        self.assertEqual(self.hud.scroll, expected)

    def test_scrolling_stops_at_the_top(self) -> None:
        self.give(self.ada, *self.all_deeds)
        self.hud.state = HudState(players=self.players, current=self.ada)
        self.hud.scroll_by(3)
        self.hud.scroll_by(-99)
        self.assertEqual(self.hud.scroll, 0)

    def test_the_wheel_scrolls_the_list(self) -> None:
        self.give(self.ada, *self.all_deeds)
        self.hud.state = HudState(players=self.players, current=self.ada)
        self.assertIsNone(self.hud.handle_event(wheel(-1)))
        self.assertEqual(self.hud.scroll, 1)
        self.hud.handle_event(wheel(1))
        self.assertEqual(self.hud.scroll, 0)

    def test_a_new_state_clamps_a_scroll_that_no_longer_fits(self) -> None:
        self.give(self.ada, *self.all_deeds)
        self.hud.state = HudState(players=self.players, current=self.ada)
        self.hud.scroll_by(1000)
        self.assertGreater(self.hud.scroll, 0)
        # Ada is bankrupted out of everything but one deed.
        for deed in list(self.ada.properties)[1:]:
            self.ada.remove_property(deed)
        self.hud.state = HudState(players=self.players, current=self.ada)
        self.assertEqual(self.hud.scroll, 0)


class TestEvents(HudTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.fired: list[Action] = []
        self.hud.on_action = self.fired.append

    def center(self, action: Action):
        return self.hud.buttons[action].rect.center

    def test_clicking_an_enabled_button_reports_and_fires(self) -> None:
        self.hud.state = HudState(available=frozenset({Action.ROLL}))
        self.assertIs(self.hud.handle_event(click(self.center(Action.ROLL))), Action.ROLL)
        self.assertEqual(self.fired, [Action.ROLL])

    def test_clicking_a_disabled_button_does_nothing(self) -> None:
        self.hud.state = HudState(available=frozenset({Action.ROLL}))
        self.assertIsNone(self.hud.handle_event(click(self.center(Action.BUILD))))
        self.assertEqual(self.fired, [])

    def test_clicking_the_panel_background_does_nothing(self) -> None:
        self.hud.state = HudState(available=frozenset(Action))
        self.assertIsNone(self.hud.handle_event(click(self.hud.header_rect.center)))
        self.assertEqual(self.fired, [])

    def test_every_action_can_be_clicked(self) -> None:
        self.hud.state = HudState(available=frozenset(Action))
        for action in Action:
            with self.subTest(action=action):
                self.assertIs(self.hud.handle_event(click(self.center(action))), action)
        self.assertEqual(self.fired, list(Action))

    def test_hover_is_tracked_without_reporting_an_action(self) -> None:
        self.hud.state = HudState(available=frozenset({Action.ROLL}))
        self.assertIsNone(self.hud.handle_event(motion(self.center(Action.ROLL))))
        self.assertTrue(self.hud.buttons[Action.ROLL].hovered)
        self.assertEqual(self.fired, [])

    def test_a_hud_without_a_callback_still_reports(self) -> None:
        hud = Hud(HUD_RECT, state=HudState(available=frozenset({Action.END_TURN})))
        self.assertIs(
            hud.handle_event(click(hud.buttons[Action.END_TURN].rect.center)),
            Action.END_TURN,
        )


class TestDrawing(HudTestCase):
    def test_the_panel_is_filled_and_bordered(self) -> None:
        surface = self.show()
        self.assertEqual(rgb(surface, (HUD_RECT.left + 6, HUD_RECT.centery)), PANEL)

    def test_an_empty_state_draws_without_a_player(self) -> None:
        surface = self.surface()
        Hud(HUD_RECT).draw(surface)
        self.assertEqual(rgb(surface, (HUD_RECT.left + 6, HUD_RECT.centery)), PANEL)

    def test_the_header_shows_the_current_players_token(self) -> None:
        surface = self.show(current=self.bob)
        self.assertTrue(has_color(surface, self.hud.header_rect, TOKEN_RGB["blue"]))

    def test_the_header_shows_cash_in_the_accent_colour(self) -> None:
        surface = self.show()
        self.assertTrue(has_color(surface, self.hud.header_rect, ACCENT))

    def test_the_dice_are_drawn_in_their_block(self) -> None:
        dice = Dice(random.Random(1), roll_ms=0)
        surface = self.show(dice=dice)
        width = dice_size()[0]
        left, _ = die_rects(
            (self.hud.dice_rect.centerx - width // 2, self.hud.dice_rect.top)
        )
        self.assertEqual(rgb(surface, (left.left + 8, left.centery)), SPACE_BG)

    def test_a_state_without_dice_leaves_the_block_empty(self) -> None:
        surface = self.show()
        self.assertFalse(has_color(surface, self.hud.dice_rect, SPACE_BG))

    def test_a_message_is_drawn(self) -> None:
        blank = self.show(message="")
        written = self.show(message="Ada pays $50 rent to Bob")
        self.assertNotEqual(
            pygame.image.tostring(blank.subsurface(self.hud.message_rect), "RGB"),
            pygame.image.tostring(written.subsurface(self.hud.message_rect), "RGB"),
        )

    def test_an_over_long_message_stays_inside_the_panel(self) -> None:
        surface = self.show(message="Ada " * 200)
        outside = pygame.Rect(
            self.hud.message_rect.right, self.hud.message_rect.top,
            HUD_RECT.right - self.hud.message_rect.right, self.hud.message_rect.height,
        )
        self.assertFalse(has_color(surface, outside, TEXT))


class TestDeedList(HudTestCase):
    def test_an_empty_list_says_so(self) -> None:
        empty = self.show()
        self.assertTrue(EMPTY_LIST_TEXT)
        self.assertFalse(
            has_color(empty, self.hud.row_rect(0), GROUP_COLORS["brown"])
        )

    def test_each_deed_gets_a_chip_in_its_group_colour(self) -> None:
        self.give(self.ada, 1, 6, 5)  # brown, light blue, railroad
        surface = self.show()
        for row, group in enumerate(("brown", "railroad", "light_blue")):
            with self.subTest(row=row):
                self.assertTrue(
                    has_color(surface, self.hud.row_rect(row), GROUP_COLORS[group])
                )

    def test_houses_are_drawn_one_marker_each(self) -> None:
        self.give(self.ada, 1)
        self.deeds[1].houses = 3
        surface = self.show()
        row = self.hud.row_rect(0)
        self.assertEqual(count_color(surface, row, HOUSE_COLOR), 3 * 8 * 8)

    def test_a_hotel_replaces_the_houses(self) -> None:
        self.give(self.ada, 1)
        self.deeds[1].has_hotel = True
        surface = self.show()
        row = self.hud.row_rect(0)
        self.assertTrue(has_color(surface, row, HOTEL_COLOR))
        self.assertFalse(has_color(surface, row, HOUSE_COLOR))

    def test_a_mortgaged_deed_is_badged(self) -> None:
        self.give(self.ada, 1)
        self.deeds[1].mortgaged = True
        surface = self.show()
        self.assertTrue(has_color(surface, self.hud.row_rect(0), DANGER))

    def test_an_unmortgaged_deed_is_not_badged(self) -> None:
        self.give(self.ada, 1)
        surface = self.show()
        self.assertFalse(has_color(surface, self.hud.row_rect(0), DANGER))

    def test_a_completed_group_outlines_its_chips(self) -> None:
        self.give(self.ada, 1)
        partial = self.show()
        self.give(self.ada, 3)
        whole = self.show()
        self.assertFalse(has_color(partial, self.hud.chip_rect(0), TEXT))
        self.assertTrue(has_color(whole, self.hud.chip_rect(0), TEXT))

    def test_only_a_window_of_a_long_list_is_drawn(self) -> None:
        self.give(self.ada, 1, 3, 5, 6, 8, 9, 11, 12, 13, 14)
        surface = self.show()
        rows = self.hud.visible_rows
        self.assertLess(rows, len(self.hud.deeds))
        below = pygame.Rect(
            self.hud.property_list_rect.left,
            self.hud.row_rect(rows - 1).bottom,
            self.hud.property_list_rect.width,
            self.hud.buttons_rect.top - self.hud.row_rect(rows - 1).bottom,
        )
        self.assertFalse(has_color(surface, below, GROUP_COLORS["pink"]))

    def test_scrolling_changes_which_deeds_are_drawn(self) -> None:
        self.give(self.ada, 1, 3, 5, 6, 8, 9, 11, 12, 13, 14)
        top = self.show()
        self.assertTrue(has_color(top, self.hud.row_rect(0), GROUP_COLORS["brown"]))
        self.hud.scroll_by(3)
        surface = self.surface()
        self.hud.draw(surface)
        self.assertTrue(
            has_color(surface, self.hud.row_rect(0), GROUP_COLORS["light_blue"])
        )
        self.assertFalse(
            has_color(surface, self.hud.row_rect(0), GROUP_COLORS["brown"])
        )

    def test_long_names_are_abbreviated(self) -> None:
        self.assertEqual(deed_label(self.deeds[5]), "Reading RR")
        self.assertEqual(deed_label(self.deeds[1]), "Mediterranean Avenue")


class TestRoster(HudTestCase):
    def test_every_other_player_gets_a_token(self) -> None:
        surface = self.show()
        for color in ("blue", "green"):
            with self.subTest(color=color):
                self.assertTrue(
                    has_color(surface, self.hud.roster_rect, TOKEN_RGB[color])
                )

    def test_the_current_player_is_not_listed_again(self) -> None:
        surface = self.show()
        self.assertFalse(has_color(surface, self.hud.roster_rect, TOKEN_RGB["red"]))

    def test_a_bankrupt_player_is_greyed_out(self) -> None:
        self.bob.is_bankrupt = True
        surface = self.show()
        self.assertFalse(has_color(surface, self.hud.roster_rect, TOKEN_RGB["blue"]))
        self.assertTrue(has_color(surface, self.hud.roster_rect, TEXT_MUTED))

    def test_a_full_table_fits_the_roster_block(self) -> None:
        colors = ("red", "blue", "green", "yellow", "purple", "orange")
        players = [Player(f"Player {i}", 1500, c) for i, c in enumerate(colors)]
        self.hud.state = HudState(players=players, current=players[0])
        self.assertEqual(len(self.hud.others), MAX_OTHER_PLAYERS)
        surface = self.surface()
        self.hud.draw(surface)
        for color in colors[1:]:
            with self.subTest(color=color):
                self.assertTrue(
                    has_color(surface, self.hud.roster_rect, TOKEN_RGB[color])
                )

    def test_nothing_is_drawn_below_the_roster(self) -> None:
        surface = self.show()
        below = pygame.Rect(
            HUD_RECT.left + 3,
            self.hud.roster_rect.bottom,
            HUD_RECT.width - 6,
            HUD_RECT.bottom - self.hud.roster_rect.bottom - 3,
        )
        self.assertFalse(has_color(surface, below, TOKEN_RGB["blue"]))

    def test_an_unknown_token_colour_falls_back(self) -> None:
        self.assertIsInstance(token_rgb(Player("Zed", 10, "chartreuse")), tuple)


class TestWithRenderer(HudTestCase):
    """The HUD is what ``Renderer`` has been waiting for since Phase 4."""

    def test_the_renderer_draws_the_hud_into_the_panel(self) -> None:
        self.hud.state = HudState(
            players=self.players, current=self.ada, properties=self.properties
        )
        surface = self.surface()
        Renderer(surface).draw(self.players, self.properties, hud=self.hud)
        self.assertTrue(has_color(surface, self.hud.header_rect, TOKEN_RGB["red"]))

    def test_the_board_is_untouched_by_the_hud(self) -> None:
        self.hud.state = HudState(players=self.players, current=self.ada)
        surface = self.surface()
        renderer = Renderer(surface)
        renderer.draw(self.players, self.properties, hud=self.hud)
        board = renderer.board.render(self.players, self.properties)
        for point in ((4, 4), (400, 400), (795, 795)):
            with self.subTest(point=point):
                self.assertEqual(rgb(surface, point), rgb(board, point))


if __name__ == "__main__":
    unittest.main()
