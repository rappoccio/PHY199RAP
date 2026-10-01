"""Phase 3 tests: the Game Manager setup screen.

The screen is exercised the way the operator would: synthesised clicks and
keystrokes fed to :meth:`GameManager.handle_event`, then assertions about the
stage it reached and the :class:`~monopoly.player.Player` objects it produced.

The starting-cash entry is the one rules change in this edition, so the cash
field gets the most attention here.
"""

from __future__ import annotations

import os
import unittest

import pygame

from monopoly.game_manager import (
    DEFAULT_CASH,
    MAX_CASH_DIGITS,
    MAX_NAME_LENGTH,
    MAX_PLAYERS,
    MIN_PLAYERS,
    GameManager,
    Stage,
    run,
)
from monopoly.player import Player
from monopoly.ui.theme import SCREEN_SIZE, TOKEN_COLORS, clear_font_cache


def click(pos, button: int = 1) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": button})


def key(k: int, unicode: str = "", mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, {"key": k, "unicode": unicode, "mod": mod})


TAB = key(pygame.K_TAB, "\t")
SHIFT_TAB = key(pygame.K_TAB, "\t", mod=pygame.KMOD_LSHIFT)
ENTER = key(pygame.K_RETURN, "\r")
ESCAPE = key(pygame.K_ESCAPE, "\x1b")
BACKSPACE = key(pygame.K_BACKSPACE)


class SetupTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        # Another module may have shut the font module down; fonts cached
        # before that are freed memory.
        clear_font_cache()

    def setUp(self) -> None:
        self.manager = GameManager()

    # --- helpers ------------------------------------------------------------
    def send(self, *events) -> None:
        for event in events:
            self.manager.handle_event(event)

    def type_text(self, text: str) -> None:
        for char in text:
            self.send(key(ord(char) if len(char) == 1 else 0, char))

    def click_count(self, count: int) -> None:
        button = self.manager.count_buttons[count - MIN_PLAYERS]
        self.assertEqual(button.label, str(count))
        self.send(click(button.rect.center))

    def clear_field(self) -> None:
        for _ in range(max(MAX_NAME_LENGTH, MAX_CASH_DIGITS)):
            self.send(BACKSPACE)

    def fill(self, *rows) -> None:
        """Type ``(name, cash)`` rows, starting from the first field."""
        self.manager.focus(0)
        for name, cash in rows:
            self.clear_field()
            self.type_text(name)
            self.send(TAB)
            self.clear_field()
            self.type_text(str(cash))
            self.send(TAB)


class TestCountScreen(SetupTestCase):
    def test_starts_on_the_count_screen_with_nothing_chosen(self) -> None:
        self.assertEqual(self.manager.stage, Stage.COUNT)
        self.assertEqual(self.manager.entries, [])
        self.assertEqual(self.manager.players, [])
        self.assertFalse(self.manager.is_valid)

    def test_has_one_button_per_legal_player_count(self) -> None:
        labels = [b.label for b in self.manager.count_buttons]
        self.assertEqual(labels, [str(n) for n in range(MIN_PLAYERS, MAX_PLAYERS + 1)])

    def test_count_buttons_do_not_overlap_and_fit_on_screen(self) -> None:
        screen = pygame.Rect((0, 0), SCREEN_SIZE)
        rects = [b.rect for b in self.manager.count_buttons]
        for i, rect in enumerate(rects):
            with self.subTest(button=i):
                self.assertTrue(screen.contains(rect))
                self.assertEqual(rect.collidelistall(rects), [i])

    def test_clicking_a_count_opens_that_many_rows(self) -> None:
        for count in range(MIN_PLAYERS, MAX_PLAYERS + 1):
            with self.subTest(count=count):
                self.setUp()
                self.click_count(count)
                self.assertEqual(self.manager.stage, Stage.DETAILS)
                self.assertEqual(len(self.manager.entries), count)

    def test_number_keys_pick_a_count_too(self) -> None:
        self.send(key(pygame.K_4, "4"))
        self.assertEqual(self.manager.stage, Stage.DETAILS)
        self.assertEqual(len(self.manager.entries), 4)

    def test_out_of_range_number_keys_are_ignored(self) -> None:
        for digit in ("0", "1", "7", "9"):
            with self.subTest(digit=digit):
                self.send(key(ord(digit), digit))
                self.assertEqual(self.manager.stage, Stage.COUNT)

    def test_clicking_empty_space_does_nothing(self) -> None:
        self.send(click((5, 5)))
        self.assertEqual(self.manager.stage, Stage.COUNT)

    def test_select_count_rejects_illegal_counts(self) -> None:
        for count in (-1, 0, 1, 7, 99):
            with self.subTest(count=count):
                with self.assertRaises(ValueError):
                    self.manager.select_count(count)

    def test_quit_event_is_recorded(self) -> None:
        self.send(pygame.event.Event(pygame.QUIT))
        self.assertTrue(self.manager.quit_requested)


class TestDetailsScreen(SetupTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manager.select_count(3)

    def test_each_seat_starts_with_the_default_stake(self) -> None:
        for entry in self.manager.entries:
            with self.subTest(seat=entry.seat):
                self.assertEqual(entry.cash_input.text, str(DEFAULT_CASH))
                self.assertEqual(entry.cash, DEFAULT_CASH)

    def test_seats_get_distinct_token_colors_in_order(self) -> None:
        colors = [entry.token_color for entry in self.manager.entries]
        self.assertEqual(colors, [name for name, _ in TOKEN_COLORS[:3]])
        self.assertEqual(len(set(colors)), 3)

    def test_name_starts_empty_with_a_seat_placeholder(self) -> None:
        entry = self.manager.entries[0]
        self.assertEqual(entry.name_input.text, "")
        self.assertEqual(entry.name_input.placeholder, "Player 1")

    def test_first_name_field_has_focus(self) -> None:
        self.assertEqual(self.manager.focused_index, 0)

    def test_field_rects_do_not_overlap(self) -> None:
        rects = [field.rect for field in self.manager.fields]
        for i, rect in enumerate(rects):
            with self.subTest(field=i):
                self.assertEqual(rect.collidelistall(rects), [i])

    def test_typing_only_reaches_the_focused_field(self) -> None:
        self.type_text("Ada")
        self.assertEqual(self.manager.entries[0].name, "Ada")
        self.assertEqual(self.manager.entries[1].name, "")

    def test_tab_walks_forward_and_wraps(self) -> None:
        for expected in range(1, 6):
            self.send(TAB)
            self.assertEqual(self.manager.focused_index, expected)
        self.send(TAB)
        self.assertEqual(self.manager.focused_index, 0)

    def test_shift_tab_walks_backward_and_wraps(self) -> None:
        self.send(SHIFT_TAB)
        self.assertEqual(self.manager.focused_index, 5)
        self.send(SHIFT_TAB)
        self.assertEqual(self.manager.focused_index, 4)

    def test_tab_does_not_type_a_tab_character(self) -> None:
        self.send(TAB)
        self.assertEqual(self.manager.entries[0].name_input.text, "")

    def test_clicking_a_field_focuses_it(self) -> None:
        target = self.manager.entries[2].cash_input
        self.send(click(target.rect.center))
        self.assertEqual(self.manager.focused_index, 5)
        self.type_text("7")
        self.assertEqual(target.text, str(DEFAULT_CASH) + "7")

    def test_enter_advances_one_field_at_a_time(self) -> None:
        self.send(ENTER)
        self.assertEqual(self.manager.focused_index, 1)
        self.send(ENTER)
        self.assertEqual(self.manager.focused_index, 2)

    def test_escape_returns_to_the_count_screen(self) -> None:
        self.send(ESCAPE)
        self.assertEqual(self.manager.stage, Stage.COUNT)
        self.assertIsNone(self.manager.focused_index)

    def test_back_button_returns_to_the_count_screen(self) -> None:
        self.send(click(self.manager.back_button.rect.center))
        self.assertEqual(self.manager.stage, Stage.COUNT)

    def test_returning_keeps_what_was_typed(self) -> None:
        self.type_text("Ada")
        self.send(ESCAPE)
        self.click_count(3)
        self.assertEqual(self.manager.entries[0].name, "Ada")

    def test_shrinking_the_count_drops_the_extra_seats(self) -> None:
        self.fill(("Ada", 1500), ("Grace", 900), ("Linus", 100))
        self.send(ESCAPE)
        self.click_count(2)
        self.assertEqual([e.name for e in self.manager.entries], ["Ada", "Grace"])

    def test_growing_the_count_adds_fresh_seats(self) -> None:
        self.type_text("Ada")
        self.send(ESCAPE)
        self.click_count(5)
        self.assertEqual(len(self.manager.entries), 5)
        self.assertEqual(self.manager.entries[0].name, "Ada")
        self.assertEqual(self.manager.entries[4].name, "")
        self.assertEqual(self.manager.entries[4].cash, DEFAULT_CASH)


class TestValidation(SetupTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manager.select_count(2)

    def test_blank_names_block_the_start(self) -> None:
        self.assertFalse(self.manager.is_valid)
        self.assertEqual(len(self.manager.validation_errors), 2)
        self.assertIn("name", self.manager.validation_errors[0])

    def test_whitespace_only_name_is_blank(self) -> None:
        self.fill(("   ", 1500), ("Grace", 1500))
        self.assertFalse(self.manager.is_valid)

    def test_filled_rows_validate(self) -> None:
        self.fill(("Ada", 1500), ("Grace", 1500))
        self.assertEqual(self.manager.validation_errors, [])
        self.assertTrue(self.manager.is_valid)

    def test_empty_cash_is_rejected(self) -> None:
        self.fill(("Ada", ""), ("Grace", 1500))
        self.assertFalse(self.manager.is_valid)
        self.assertIn("cash", self.manager.validation_errors[0])

    def test_zero_cash_is_rejected(self) -> None:
        self.fill(("Ada", 0), ("Grace", 1500))
        self.assertFalse(self.manager.is_valid)
        self.assertIn("cash", self.manager.validation_errors[0])

    def test_one_dollar_is_a_legal_stake(self) -> None:
        self.fill(("Ada", 1), ("Grace", 1500))
        self.assertTrue(self.manager.is_valid)
        self.assertEqual(self.manager.entries[0].cash, 1)

    def test_cash_field_refuses_non_digits(self) -> None:
        self.manager.focus(1)
        self.clear_field()
        self.type_text("-25.5abc")
        self.assertEqual(self.manager.entries[0].cash_input.text, "255")

    def test_cash_field_is_capped_in_length(self) -> None:
        self.manager.focus(1)
        self.clear_field()
        self.type_text("1" * (MAX_CASH_DIGITS + 4))
        self.assertEqual(
            self.manager.entries[0].cash_input.text, "1" * MAX_CASH_DIGITS
        )

    def test_name_field_is_capped_in_length(self) -> None:
        self.type_text("A" * (MAX_NAME_LENGTH + 5))
        self.assertEqual(len(self.manager.entries[0].name), MAX_NAME_LENGTH)

    def test_start_button_is_disabled_until_valid(self) -> None:
        self.manager.draw(pygame.Surface(SCREEN_SIZE))
        self.assertFalse(self.manager.start_button.enabled)
        self.fill(("Ada", 1500), ("Grace", 1500))
        self.manager.draw(pygame.Surface(SCREEN_SIZE))
        self.assertTrue(self.manager.start_button.enabled)

    def test_clicking_a_disabled_start_does_nothing(self) -> None:
        self.send(click(self.manager.start_button.rect.center))
        self.assertEqual(self.manager.stage, Stage.DETAILS)
        self.assertEqual(self.manager.players, [])

    def test_start_refuses_while_invalid(self) -> None:
        self.assertFalse(self.manager.start())
        self.assertEqual(self.manager.stage, Stage.DETAILS)

    def test_enter_on_the_last_field_does_not_start_an_invalid_roster(self) -> None:
        self.manager.focus(len(self.manager.fields) - 1)
        self.send(ENTER)
        self.assertEqual(self.manager.stage, Stage.DETAILS)
        self.assertEqual(self.manager.focused_index, 0)


class TestStartingTheGame(SetupTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.manager.select_count(3)
        self.fill(("Ada", 2500), ("Grace", 1500), ("Linus", 50))

    def test_start_button_builds_the_roster(self) -> None:
        self.send(click(self.manager.start_button.rect.center))
        self.assertEqual(self.manager.stage, Stage.DONE)
        self.assertEqual(len(self.manager.players), 3)

    def test_enter_on_the_last_field_starts_the_game(self) -> None:
        self.manager.focus(len(self.manager.fields) - 1)
        self.send(ENTER)
        self.assertEqual(self.manager.stage, Stage.DONE)

    def test_players_carry_the_entered_names_and_stakes(self) -> None:
        self.assertTrue(self.manager.start())
        names = [(p.name, p.cash) for p in self.manager.players]
        self.assertEqual(names, [("Ada", 2500), ("Grace", 1500), ("Linus", 50)])

    def test_players_are_real_player_objects_at_go(self) -> None:
        self.manager.start()
        for player in self.manager.players:
            with self.subTest(player=player.name):
                self.assertIsInstance(player, Player)
                self.assertEqual(player.position, 0)
                self.assertFalse(player.in_jail)
                self.assertFalse(player.is_bankrupt)
                self.assertEqual(player.properties, [])
                self.assertEqual(player.goojf_cards, 0)

    def test_players_get_distinct_tokens(self) -> None:
        self.manager.start()
        colors = [p.token_color for p in self.manager.players]
        self.assertEqual(len(set(colors)), len(colors))

    def test_names_are_stripped(self) -> None:
        self.manager.focus(0)
        self.clear_field()
        self.type_text("  Ada  ")
        self.manager.start()
        self.assertEqual(self.manager.players[0].name, "Ada")

    def test_events_after_start_are_ignored(self) -> None:
        self.manager.start()
        roster = list(self.manager.players)
        self.send(ESCAPE, TAB, click((640, 400)))
        self.assertEqual(self.manager.stage, Stage.DONE)
        self.assertEqual(self.manager.players, roster)

    def test_quit_still_registers_after_start(self) -> None:
        self.manager.start()
        self.send(pygame.event.Event(pygame.QUIT))
        self.assertTrue(self.manager.quit_requested)

    def test_reset_returns_to_a_blank_count_screen(self) -> None:
        self.manager.start()
        self.manager.reset()
        self.assertEqual(self.manager.stage, Stage.COUNT)
        self.assertEqual(self.manager.entries, [])
        self.assertEqual(self.manager.players, [])
        self.assertFalse(self.manager.is_valid)


class TestRendering(SetupTestCase):
    def test_draws_every_stage_without_error(self) -> None:
        surface = pygame.Surface(SCREEN_SIZE)
        self.manager.update(0)
        self.manager.draw(surface)  # count screen
        self.manager.select_count(MAX_PLAYERS)
        self.manager.update(250)
        self.manager.draw(surface)  # details screen, blank names -> error hint
        for i, entry in enumerate(self.manager.entries):
            entry.name_input.text = f"P{i}"
        self.manager.update(750)
        self.manager.draw(surface)  # details screen, valid
        self.manager.start()
        self.manager.draw(surface)

    def test_details_panel_and_buttons_stay_on_screen(self) -> None:
        screen = pygame.Rect((0, 0), SCREEN_SIZE)
        self.manager.select_count(MAX_PLAYERS)
        for rect in [f.rect for f in self.manager.fields] + [
            self.manager.back_button.rect,
            self.manager.start_button.rect,
        ]:
            with self.subTest(rect=tuple(rect)):
                self.assertTrue(screen.contains(rect))

    def test_buttons_do_not_overlap_the_fields(self) -> None:
        self.manager.select_count(MAX_PLAYERS)
        field_rects = [f.rect for f in self.manager.fields]
        for button in (self.manager.back_button, self.manager.start_button):
            with self.subTest(button=button.label):
                self.assertEqual(button.rect.collidelistall(field_rects), [])

    def test_footer_clears_the_roster_panel_at_every_seat_count(self) -> None:
        """Hint, error line and buttons must never print over the last rows."""
        screen = pygame.Rect((0, 0), SCREEN_SIZE)
        for count in range(MIN_PLAYERS, MAX_PLAYERS + 1):
            with self.subTest(players=count):
                manager = GameManager()
                manager.select_count(count)
                panel = manager.panel_rect()
                footer = manager.footer_top
                # The error line is the topmost footer item (footer - 46) and
                # sits about 9px above its own centre.
                self.assertGreater(footer - 46 - 9, panel.bottom)
                self.assertTrue(panel.contains(manager.entries[-1].name_input.rect))
                for button in (manager.back_button, manager.start_button):
                    self.assertEqual(button.rect.top, footer)
                    self.assertTrue(screen.contains(button.rect))

    def test_update_drives_the_caret_blink(self) -> None:
        self.manager.select_count(2)
        self.manager.update(0)
        focused = self.manager.fields[0]
        self.assertTrue(focused.caret_visible)
        self.manager.update(600)
        self.assertFalse(focused.caret_visible)


class _BoundedClock:
    """A ``pygame.time.Clock`` stand-in that fails instead of hanging."""

    def __init__(self, max_frames: int = 240) -> None:
        self.frames = 0
        self.max_frames = max_frames

    def tick(self, fps: int) -> int:
        self.frames += 1
        if self.frames > self.max_frames:
            raise AssertionError(
                f"setup loop still running after {self.max_frames} frames"
            )
        return 16


class TestRunLoop(SetupTestCase):
    """The real ``run`` loop, driven through pygame's own event queue."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()
        cls.surface = pygame.display.set_mode(SCREEN_SIZE)

    @classmethod
    def tearDownClass(cls) -> None:
        pygame.display.quit()

    def setUp(self) -> None:
        super().setUp()
        pygame.event.clear()

    def run_loop(self, clock=None):
        return run(self.surface, clock or _BoundedClock(), self.manager)

    def test_clicking_through_the_screens_returns_a_roster(self) -> None:
        pygame.event.post(click(self.manager.count_buttons[0].rect.center))
        for char in "Ada":
            pygame.event.post(key(ord(char), char))
        pygame.event.post(TAB)
        pygame.event.post(TAB)
        for char in "Grace":
            pygame.event.post(key(ord(char), char))
        pygame.event.post(click(self.manager.start_button.rect.center))

        players = self.run_loop()
        self.assertIsNotNone(players)
        self.assertEqual(
            [(p.name, p.cash) for p in players],
            [("Ada", DEFAULT_CASH), ("Grace", DEFAULT_CASH)],
        )
        self.assertEqual(self.manager.stage, Stage.DONE)

    def test_typed_stakes_reach_the_players(self) -> None:
        self.manager.select_count(2)
        self.manager.entries[0].name_input.text = "Ada"
        self.manager.entries[0].cash_input.text = "5000"
        self.manager.entries[1].name_input.text = "Grace"
        self.manager.entries[1].cash_input.text = "250"
        pygame.event.post(click(self.manager.start_button.rect.center))

        players = self.run_loop()
        self.assertEqual([p.cash for p in players], [5000, 250])

    def test_closing_the_window_cancels_setup(self) -> None:
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        self.assertIsNone(self.run_loop())

    def test_loop_exits_immediately_when_already_done(self) -> None:
        self.manager.select_count(2)
        self.manager.entries[0].name_input.text = "Ada"
        self.manager.entries[1].name_input.text = "Grace"
        self.manager.start()
        clock = _BoundedClock()
        self.assertEqual(self.run_loop(clock), self.manager.players)
        self.assertEqual(clock.frames, 0)


if __name__ == "__main__":
    unittest.main()
