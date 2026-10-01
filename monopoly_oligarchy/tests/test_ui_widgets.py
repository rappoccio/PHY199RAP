"""Phase 3 tests: the reusable ``Button`` and ``TextInput`` widgets.

Widgets are driven with synthesised pygame events, and drawn onto a plain
``Surface`` -- no window is opened, so these run anywhere pygame imports.
"""

from __future__ import annotations

import unittest

import pygame

from monopoly.ui.button import Button
from monopoly.ui.text_input import BLINK_MS, TextInput
from monopoly.ui.theme import clear_font_cache


def click(pos, button: int = 1) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": button})


def motion(pos) -> pygame.event.Event:
    return pygame.event.Event(pygame.MOUSEMOTION, {"pos": pos, "rel": (0, 0)})


def key(k: int, unicode: str = "", mod: int = 0) -> pygame.event.Event:
    return pygame.event.Event(pygame.KEYDOWN, {"key": k, "unicode": unicode, "mod": mod})


def type_text(widget, text: str) -> None:
    for char in text:
        widget.handle_event(key(ord(char) if len(char) == 1 else 0, char))


class WidgetTestCase(unittest.TestCase):
    """Fonts are needed for ``draw``; no display is."""

    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        # Another module may have shut the font module down; fonts cached
        # before that are freed memory.
        clear_font_cache()

    def surface(self) -> pygame.Surface:
        return pygame.Surface((1280, 800))


class TestButton(WidgetTestCase):
    def setUp(self) -> None:
        self.button = Button((100, 100, 200, 50), "Roll Dice")

    def test_left_click_inside_is_a_click(self) -> None:
        self.assertTrue(self.button.is_clicked(click((150, 120))))

    def test_click_outside_is_not(self) -> None:
        self.assertFalse(self.button.is_clicked(click((50, 120))))
        self.assertFalse(self.button.is_clicked(click((150, 400))))

    def test_right_click_is_not(self) -> None:
        self.assertFalse(self.button.is_clicked(click((150, 120), button=3)))

    def test_disabled_button_never_reports_a_click(self) -> None:
        self.button.enabled = False
        self.assertFalse(self.button.is_clicked(click((150, 120))))
        self.assertFalse(self.button.handle_event(click((150, 120))))

    def test_other_event_types_are_not_clicks(self) -> None:
        self.assertFalse(self.button.is_clicked(motion((150, 120))))
        self.assertFalse(self.button.is_clicked(key(pygame.K_RETURN, "\r")))

    def test_callback_fires_once_per_click(self) -> None:
        calls = []
        self.button.on_click = lambda: calls.append(1)
        self.assertTrue(self.button.handle_event(click((150, 120))))
        self.assertFalse(self.button.handle_event(click((10, 10))))
        self.assertEqual(len(calls), 1)

    def test_hover_tracks_the_mouse_without_consuming(self) -> None:
        self.assertFalse(self.button.handle_event(motion((150, 120))))
        self.assertTrue(self.button.hovered)
        self.button.handle_event(motion((10, 10)))
        self.assertFalse(self.button.hovered)

    def test_disabled_button_does_not_hover(self) -> None:
        self.button.enabled = False
        self.button.handle_event(motion((150, 120)))
        self.assertFalse(self.button.hovered)

    def test_draws_in_every_style(self) -> None:
        surface = self.surface()
        for enabled in (True, False):
            for primary in (True, False):
                with self.subTest(enabled=enabled, primary=primary):
                    self.button.enabled = enabled
                    self.button.primary = primary
                    self.button.draw(surface)
        # Something was actually painted inside the button's rect.
        self.assertNotEqual(surface.get_at((150, 120))[:3], (0, 0, 0))


class TestTextInput(WidgetTestCase):
    def setUp(self) -> None:
        self.field = TextInput((100, 100, 300, 40), placeholder="Player 1")
        self.field.focused = True

    def test_typing_appends_characters(self) -> None:
        type_text(self.field, "Ada")
        self.assertEqual(self.field.text, "Ada")

    def test_unfocused_field_ignores_keys(self) -> None:
        self.field.focused = False
        type_text(self.field, "Ada")
        self.assertEqual(self.field.text, "")

    def test_typing_consumes_the_event(self) -> None:
        self.assertTrue(self.field.handle_event(key(ord("A"), "A")))

    def test_backspace_deletes_before_the_caret(self) -> None:
        type_text(self.field, "Ada")
        self.field.handle_event(key(pygame.K_BACKSPACE))
        self.assertEqual(self.field.text, "Ad")

    def test_backspace_on_empty_field_is_harmless(self) -> None:
        self.field.handle_event(key(pygame.K_BACKSPACE))
        self.assertEqual(self.field.text, "")

    def test_caret_keys_edit_in_the_middle(self) -> None:
        type_text(self.field, "Ada")
        self.field.handle_event(key(pygame.K_LEFT))
        type_text(self.field, "!")
        self.assertEqual(self.field.text, "Ad!a")
        self.field.handle_event(key(pygame.K_HOME))
        self.field.handle_event(key(pygame.K_DELETE))
        self.assertEqual(self.field.text, "d!a")
        self.field.handle_event(key(pygame.K_END))
        type_text(self.field, "X")
        self.assertEqual(self.field.text, "d!aX")

    def test_caret_keys_stop_at_the_ends(self) -> None:
        type_text(self.field, "Ad")
        for _ in range(5):
            self.field.handle_event(key(pygame.K_LEFT))
        type_text(self.field, "X")
        self.assertEqual(self.field.text, "XAd")
        for _ in range(9):
            self.field.handle_event(key(pygame.K_RIGHT))
        type_text(self.field, "Y")
        self.assertEqual(self.field.text, "XAdY")

    def test_max_length_refuses_extra_characters(self) -> None:
        field = TextInput((0, 0, 100, 40), max_length=4, focused=True)
        type_text(field, "Boardwalk")
        self.assertEqual(field.text, "Boar")
        self.assertFalse(field.handle_event(key(ord("d"), "d")))

    def test_control_characters_are_not_inserted(self) -> None:
        self.field.handle_event(key(pygame.K_RETURN, "\r"))
        self.field.handle_event(key(pygame.K_TAB, "\t"))
        self.assertEqual(self.field.text, "")

    def test_digits_only_field_rejects_letters(self) -> None:
        cash = TextInput((0, 0, 100, 40), digits_only=True, focused=True)
        type_text(cash, "15a0b0")
        self.assertEqual(cash.text, "1500")

    def test_digits_only_initial_text_is_cleaned(self) -> None:
        cash = TextInput((0, 0, 100, 40), text="1500", digits_only=True)
        self.assertEqual(cash.text, "1500")

    def test_value_strips_whitespace(self) -> None:
        type_text(self.field, "  Ada  ")
        self.assertEqual(self.field.text, "  Ada  ")
        self.assertEqual(self.field.value, "Ada")

    def test_click_focuses_and_blurs(self) -> None:
        self.field.focused = False
        self.field.handle_event(click((150, 110)))
        self.assertTrue(self.field.focused)
        self.field.handle_event(click((900, 700)))
        self.assertFalse(self.field.focused)

    def test_clicks_are_never_consumed(self) -> None:
        self.assertFalse(self.field.handle_event(click((150, 110))))
        self.assertFalse(self.field.handle_event(click((900, 700))))

    def test_caret_blinks_while_focused(self) -> None:
        self.field.update(0)
        self.assertTrue(self.field.caret_visible)
        self.field.update(BLINK_MS + 10)
        self.assertFalse(self.field.caret_visible)
        self.field.update(2 * BLINK_MS + 10)
        self.assertTrue(self.field.caret_visible)

    def test_caret_hidden_when_not_focused(self) -> None:
        self.field.update(0)
        self.field.focused = False
        self.assertFalse(self.field.caret_visible)

    def test_typing_restarts_the_blink_so_the_caret_shows(self) -> None:
        self.field.update(BLINK_MS + 10)
        self.assertFalse(self.field.caret_visible)
        type_text(self.field, "A")
        self.assertTrue(self.field.caret_visible)

    def test_setting_text_moves_the_caret_to_the_end(self) -> None:
        self.field.text = "Grace"
        type_text(self.field, "!")
        self.assertEqual(self.field.text, "Grace!")

    def test_draws_empty_focused_and_filled(self) -> None:
        surface = self.surface()
        self.field.update(0)
        self.field.draw(surface)  # placeholder + caret
        type_text(self.field, "Ada")
        self.field.draw(surface)
        self.field.focused = False
        self.field.draw(surface)


if __name__ == "__main__":
    unittest.main()
