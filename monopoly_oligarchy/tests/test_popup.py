"""Phase 7 tests: the modal popup.

The popup is the other half of the deal :class:`monopoly.game.Prompt` strikes:
the game says what it is asking and which answers are open, and the popup turns
that into a box with buttons and a click back into a choice key. So these tests
cover the geometry, the button row a prompt produces, what a click reports, and
that the box and its scrim actually reach the pixels.

Everything runs on a plain ``Surface``; no window is opened.
"""

from __future__ import annotations

import unittest

import pygame

from monopoly.game import (
    AUCTION_KEY,
    BUY_KEY,
    CARD_KEY,
    OK_KEY,
    PAY_KEY,
    PROMPT_BUY,
    PROMPT_CARD,
    PROMPT_JAIL,
    ROLL_KEY,
    Choice,
    Prompt,
)
from monopoly.ui.popup import (
    BUTTON_GAP,
    BUTTON_H,
    MAX_PER_ROW,
    POPUP_CENTER,
    POPUP_SIZE,
    Popup,
)
from monopoly.ui.theme import PANEL, clear_font_cache, get_font

BUY_PROMPT = Prompt(
    kind=PROMPT_BUY,
    title="Baltic Avenue",
    text="Baltic Avenue is for sale at $60. Buy it?",
    options=(Choice(BUY_KEY, "Buy $60"), Choice(AUCTION_KEY, "Auction")),
)

POOR_PROMPT = Prompt(
    kind=PROMPT_BUY,
    title="Boardwalk",
    text="Boardwalk is for sale at $400. Buy it?",
    options=(Choice(BUY_KEY, "Buy $400", enabled=False), Choice(AUCTION_KEY, "Auction")),
)

CARD_PROMPT = Prompt(
    kind=PROMPT_CARD,
    title="Chance",
    text=(
        "Advance token to the nearest Railroad and pay owner twice the rental "
        "to which they are otherwise entitled. If Railroad is unowned, you may "
        "buy it from the Bank."
    ),
    options=(Choice(OK_KEY, "OK"),),
)

#: Phase 8's jail prompt: the first with more choices than fit one row.
JAIL_PROMPT = Prompt(
    kind=PROMPT_JAIL,
    title="In Jail",
    text="Ada is in Jail -- roll 1 of 3. Doubles get you out without paying.",
    options=(
        Choice(PAY_KEY, "Pay $50 & Roll"),
        Choice(CARD_KEY, "Use Jail Card", enabled=False),
        Choice(ROLL_KEY, "Roll for Doubles"),
    ),
)


def click(pos, button: int = 1) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": button})


def motion(pos) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEMOTION, {"pos": pos, "rel": (0, 0)})


class PopupTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        clear_font_cache()

    def setUp(self):
        self.popup = Popup()
        self.surface = pygame.Surface((1280, 800))


class LayoutTest(PopupTestCase):
    def test_the_box_sits_over_the_board_by_default(self):
        self.assertEqual(self.popup.rect.size, POPUP_SIZE)
        self.assertEqual(self.popup.rect.center, POPUP_CENTER)

    def test_an_explicit_rect_is_honoured(self):
        popup = Popup((10, 20, 200, 120))
        self.assertEqual(popup.rect, pygame.Rect(10, 20, 200, 120))

    def test_the_blocks_stack_inside_the_box(self):
        popup = self.popup
        self.assertTrue(popup.rect.contains(popup.title_rect))
        self.assertTrue(popup.rect.contains(popup.body_rect))
        self.assertTrue(popup.rect.contains(popup.buttons_rect))

    def test_the_blocks_do_not_overlap(self):
        popup = self.popup
        self.assertLessEqual(popup.title_rect.bottom, popup.body_rect.top)
        self.assertLessEqual(popup.body_rect.bottom, popup.buttons_rect.top)

    def test_the_body_has_room_to_draw_in(self):
        self.assertGreater(self.popup.body_rect.height, 0)


class PromptTest(PopupTestCase):
    def test_a_fresh_popup_shows_nothing(self):
        self.assertIsNone(self.popup.prompt)
        self.assertFalse(self.popup.visible)
        self.assertEqual(self.popup.buttons, [])

    def test_setting_a_prompt_makes_it_visible(self):
        self.popup.prompt = BUY_PROMPT
        self.assertTrue(self.popup.visible)
        self.assertIs(self.popup.prompt, BUY_PROMPT)

    def test_one_button_per_choice(self):
        self.popup.prompt = BUY_PROMPT
        self.assertEqual(len(self.popup.buttons), 2)
        self.assertEqual(
            [b.label for b in self.popup.buttons], ["Buy $60", "Auction"]
        )

    def test_clearing_the_prompt_drops_the_buttons(self):
        self.popup.prompt = BUY_PROMPT
        self.popup.prompt = None
        self.assertFalse(self.popup.visible)
        self.assertEqual(self.popup.buttons, [])

    def test_a_disabled_choice_makes_a_disabled_button(self):
        self.popup.prompt = POOR_PROMPT
        self.assertFalse(self.popup.buttons[0].enabled)
        self.assertTrue(self.popup.buttons[1].enabled)

    def test_buy_and_ok_are_the_primary_buttons(self):
        self.popup.prompt = BUY_PROMPT
        self.assertTrue(self.popup.buttons[0].primary)
        self.assertFalse(self.popup.buttons[1].primary)
        self.popup.prompt = CARD_PROMPT
        self.assertTrue(self.popup.buttons[0].primary)

    def test_the_buttons_fill_their_strip_without_overlapping(self):
        self.popup.prompt = BUY_PROMPT
        first, second = (b.rect for b in self.popup.buttons)
        strip = self.popup.buttons_rect
        self.assertEqual(first.width, second.width)
        self.assertEqual(first.left, strip.left)
        self.assertLessEqual(first.right, second.left)
        self.assertLessEqual(second.right, strip.right)
        self.assertEqual(first.top, strip.top)

    def test_a_single_choice_spans_the_strip(self):
        self.popup.prompt = CARD_PROMPT
        button = self.popup.buttons[0]
        self.assertEqual(button.rect.left, self.popup.buttons_rect.left)
        self.assertLessEqual(button.rect.right, self.popup.buttons_rect.right)

    def test_a_prompt_with_no_choices_has_no_buttons(self):
        self.popup.prompt = Prompt(kind=PROMPT_CARD, title="t", text="t", options=())
        self.assertEqual(self.popup.buttons, [])


class WrappedChoicesTest(PopupTestCase):
    """Phase 8: three choices do not fit one row, so the row wraps.

    Three buttons across a 520px box leave about 148px each -- not enough for
    "Roll for Doubles" -- so the choices are laid two to a row and the odd one
    out spans the width underneath.
    """

    def setUp(self):
        super().setUp()
        self.popup.prompt = JAIL_PROMPT

    def test_the_choices_are_grouped_two_to_a_row(self):
        self.assertEqual(
            [len(row) for row in self.popup.choice_rows], [MAX_PER_ROW, 1]
        )

    def test_the_block_grows_a_row_instead_of_squeezing_the_buttons(self):
        block = self.popup.buttons_rect
        self.assertEqual(block.height, 2 * BUTTON_H + BUTTON_GAP)
        self.assertEqual(block.bottom, Popup().buttons_rect.bottom, "still bottom-set")

    def test_one_button_per_choice_in_prompt_order(self):
        self.assertEqual(
            [b.label for b in self.popup.buttons],
            ["Pay $50 & Roll", "Use Jail Card", "Roll for Doubles"],
        )

    def test_the_first_two_share_the_top_row(self):
        pay, card, _ = (b.rect for b in self.popup.buttons)
        self.assertEqual(pay.top, self.popup.buttons_rect.top)
        self.assertEqual(pay.top, card.top)
        self.assertEqual(pay.width, card.width)
        self.assertLess(pay.right, card.left)

    def test_the_third_spans_the_bottom_row(self):
        pay, _, roll = (b.rect for b in self.popup.buttons)
        self.assertEqual(roll.width, self.popup.buttons_rect.width)
        self.assertEqual(roll.bottom, self.popup.buttons_rect.bottom)
        self.assertEqual(roll.top - pay.bottom, BUTTON_GAP)

    def test_every_button_stays_inside_the_block(self):
        for button in self.popup.buttons:
            with self.subTest(label=button.label):
                self.assertTrue(self.popup.buttons_rect.contains(button.rect))

    def test_no_two_buttons_overlap(self):
        rects = [b.rect for b in self.popup.buttons]
        for i, first in enumerate(rects):
            for second in rects[i + 1:]:
                self.assertFalse(first.colliderect(second))

    def test_every_label_fits_its_button(self):
        font = get_font(20, bold=True)
        for button in self.popup.buttons:
            with self.subTest(label=button.label):
                self.assertLessEqual(font.size(button.label)[0], button.rect.width - 8)

    def test_the_body_still_has_room_above_them(self):
        self.assertGreater(self.popup.body_rect.height, 0)
        self.assertLessEqual(self.popup.body_rect.bottom, self.popup.buttons_rect.top)
        self.assertTrue(self.popup.rect.contains(self.popup.buttons_rect))

    def test_the_roll_out_is_the_primary_button(self):
        self.assertEqual(
            [b.primary for b in self.popup.buttons], [False, False, True]
        )

    def test_a_disabled_choice_is_still_disabled_on_the_second_row_layout(self):
        self.assertFalse(self.popup.buttons[1].enabled)

    def test_a_click_on_the_wrapped_button_reports_its_key(self):
        self.assertEqual(
            self.popup.handle_event(click(self.popup.buttons[2].rect.center)),
            ROLL_KEY,
        )

    def test_a_click_on_the_first_row_reports_its_key(self):
        self.assertEqual(
            self.popup.handle_event(click(self.popup.buttons[0].rect.center)),
            PAY_KEY,
        )

    def test_the_disabled_choice_swallows_nothing(self):
        self.assertIsNone(
            self.popup.handle_event(click(self.popup.buttons[1].rect.center))
        )

    def test_a_two_choice_prompt_is_unchanged_by_the_wrapping(self):
        one_row = Popup()
        one_row.prompt = BUY_PROMPT
        self.assertEqual(one_row.buttons_rect.height, BUTTON_H)
        self.assertEqual(len(one_row.choice_rows), 1)

    def test_going_back_to_a_smaller_prompt_shrinks_the_block_again(self):
        self.popup.prompt = BUY_PROMPT
        self.assertEqual(self.popup.buttons_rect.height, BUTTON_H)
        self.assertEqual(len(self.popup.buttons), 2)

    def test_the_wrapped_buttons_are_drawn(self):
        self.surface.fill(PANEL)
        self.popup.draw(self.surface)
        for button in self.popup.buttons:
            with self.subTest(label=button.label):
                patch = self.surface.subsurface(button.rect)
                self.assertNotEqual(
                    pygame.transform.average_color(patch)[:3], PANEL
                )

    def test_the_body_text_does_not_spill_into_the_buttons(self):
        self.popup.draw(self.surface)
        gap = pygame.Rect(
            self.popup.body_rect.left,
            self.popup.body_rect.bottom,
            self.popup.body_rect.width,
            self.popup.buttons_rect.top - self.popup.body_rect.bottom,
        )
        if gap.height > 0:
            patch = self.surface.subsurface(gap)
            self.assertEqual(pygame.transform.average_color(patch)[:3], PANEL)


class EventTest(PopupTestCase):
    def setUp(self):
        super().setUp()
        self.fired = []
        self.popup.on_choice = self.fired.append

    def center(self, index: int):
        return self.popup.buttons[index].rect.center

    def test_a_click_reports_the_choice_key(self):
        self.popup.prompt = BUY_PROMPT
        self.assertEqual(self.popup.handle_event(click(self.center(0))), BUY_KEY)
        self.assertEqual(self.fired, [BUY_KEY])

    def test_the_second_choice_reports_its_own_key(self):
        self.popup.prompt = BUY_PROMPT
        self.assertEqual(self.popup.handle_event(click(self.center(1))), AUCTION_KEY)

    def test_a_click_off_the_buttons_reports_nothing(self):
        self.popup.prompt = BUY_PROMPT
        self.assertIsNone(self.popup.handle_event(click((5, 5))))
        self.assertEqual(self.fired, [])

    def test_a_disabled_button_cannot_be_clicked(self):
        self.popup.prompt = POOR_PROMPT
        self.assertIsNone(self.popup.handle_event(click(self.center(0))))
        self.assertEqual(self.fired, [])

    def test_events_are_ignored_while_nothing_is_showing(self):
        self.assertIsNone(self.popup.handle_event(click((400, 380))))

    def test_hover_is_tracked_but_reports_nothing(self):
        self.popup.prompt = BUY_PROMPT
        self.assertIsNone(self.popup.handle_event(motion(self.center(0))))
        self.assertTrue(self.popup.buttons[0].hovered)

    def test_a_right_click_is_not_a_choice(self):
        self.popup.prompt = BUY_PROMPT
        self.assertIsNone(self.popup.handle_event(click(self.center(0), button=3)))


class DrawTest(PopupTestCase):
    def test_nothing_is_drawn_without_a_prompt(self):
        self.surface.fill((7, 9, 11))
        self.popup.draw(self.surface)
        self.assertEqual(self.surface.get_at((400, 380))[:3], (7, 9, 11))

    def test_the_box_is_painted_in_the_panel_colour(self):
        self.popup.prompt = BUY_PROMPT
        self.popup.draw(self.surface)
        inside = (self.popup.rect.centerx, self.popup.body_rect.bottom - 2)
        self.assertEqual(self.surface.get_at(inside)[:3], PANEL)

    def test_the_rest_of_the_screen_is_dimmed(self):
        self.surface.fill((255, 255, 255))
        self.popup.prompt = BUY_PROMPT
        self.popup.draw(self.surface)
        outside = self.surface.get_at((20, 20))[:3]
        self.assertLess(max(outside), 255)
        self.assertGreater(max(outside), 0)

    def test_the_title_reaches_the_pixels(self):
        self.surface.fill(PANEL)
        self.popup.prompt = BUY_PROMPT
        self.popup.draw(self.surface)
        title = self.surface.subsurface(self.popup.title_rect)
        self.assertNotEqual(
            pygame.transform.average_color(title)[:3], PANEL, "title row is blank"
        )

    def test_a_long_card_draws_without_spilling_out(self):
        self.popup.prompt = CARD_PROMPT
        self.popup.draw(self.surface)
        gap = pygame.Rect(
            self.popup.body_rect.left,
            self.popup.body_rect.bottom,
            self.popup.body_rect.width,
            self.popup.buttons_rect.top - self.popup.body_rect.bottom,
        )
        if gap.height > 0:
            patch = self.surface.subsurface(gap)
            self.assertEqual(pygame.transform.average_color(patch)[:3], PANEL)

    def test_the_buttons_are_drawn(self):
        self.surface.fill(PANEL)
        self.popup.prompt = BUY_PROMPT
        self.popup.draw(self.surface)
        patch = self.surface.subsurface(self.popup.buttons[0].rect)
        self.assertNotEqual(pygame.transform.average_color(patch)[:3], PANEL)


if __name__ == "__main__":
    unittest.main()
