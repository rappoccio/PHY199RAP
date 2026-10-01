"""Phase 5 tests: drawing the dice.

Drawn onto a plain ``Surface`` -- no window is opened. The checks are about
geometry and pixels: pips land inside their die, every face has the right
number of them, and the animation's label appears only when it should.
"""

from __future__ import annotations

import random
import unittest

import pygame

from monopoly.dice import ROLL_MS, Dice
from monopoly.ui.dice_view import (
    DIE_GAP,
    DIE_SIZE,
    PIP_LAYOUT,
    die_rects,
    dice_size,
    draw_dice,
    draw_die,
    pip_centers,
)
from monopoly.ui.theme import BOARD_LINE, SPACE_BG, clear_font_cache


def rgb(surface: pygame.Surface, pos) -> tuple[int, int, int]:
    return tuple(surface.get_at(pos))[:3]


class DiceViewTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        clear_font_cache()

    def setUp(self) -> None:
        self.surface = pygame.Surface((400, 300))
        self.dice = Dice(random.Random(11))

    def settled(self, dice: Dice | None = None) -> Dice:
        dice = dice if dice is not None else self.dice
        dice.start(0)
        dice.finish()
        return dice


class TestLayout(DiceViewTestCase):
    def test_two_dice_sit_side_by_side(self) -> None:
        left, right = die_rects((10, 20))
        self.assertEqual(left.topleft, (10, 20))
        self.assertEqual(right.left, left.right + DIE_GAP)
        self.assertEqual(right.top, left.top)

    def test_dice_are_square(self) -> None:
        for rect in die_rects((0, 0)):
            self.assertEqual(rect.width, rect.height)
            self.assertEqual(rect.width, DIE_SIZE)

    def test_size_matches_the_rects(self) -> None:
        left, right = die_rects((0, 0))
        self.assertEqual(dice_size(), (left.union(right).width, left.height))

    def test_custom_size_and_gap_are_honoured(self) -> None:
        left, right = die_rects((0, 0), size=30, gap=5)
        self.assertEqual(left.width, 30)
        self.assertEqual(right.left, 35)
        self.assertEqual(dice_size(30, 5), (65, 30))


class TestPips(DiceViewTestCase):
    def test_every_face_has_its_own_pip_count(self) -> None:
        rect = pygame.Rect(0, 0, DIE_SIZE, DIE_SIZE)
        for face in range(1, 7):
            self.assertEqual(len(pip_centers(rect, face)), face)

    def test_pips_never_repeat_a_position(self) -> None:
        rect = pygame.Rect(0, 0, DIE_SIZE, DIE_SIZE)
        for face in range(1, 7):
            centers = pip_centers(rect, face)
            self.assertEqual(len(set(centers)), len(centers))

    def test_pips_stay_inside_the_die(self) -> None:
        rect = pygame.Rect(17, 23, DIE_SIZE, DIE_SIZE)
        for face in range(1, 7):
            for center in pip_centers(rect, face):
                self.assertTrue(rect.collidepoint(center))

    def test_pips_follow_the_die(self) -> None:
        here = pip_centers(pygame.Rect(0, 0, DIE_SIZE, DIE_SIZE), 5)
        there = pip_centers(pygame.Rect(100, 40, DIE_SIZE, DIE_SIZE), 5)
        self.assertEqual([(x + 100, y + 40) for x, y in here], there)

    def test_odd_faces_have_a_centre_pip(self) -> None:
        rect = pygame.Rect(0, 0, DIE_SIZE, DIE_SIZE)
        for face in (1, 3, 5):
            self.assertIn(rect.center, pip_centers(rect, face))

    def test_even_faces_have_no_centre_pip(self) -> None:
        rect = pygame.Rect(0, 0, DIE_SIZE, DIE_SIZE)
        for face in (2, 4, 6):
            self.assertNotIn(rect.center, pip_centers(rect, face))

    def test_layouts_are_symmetric_about_the_centre(self) -> None:
        for face, cells in PIP_LAYOUT.items():
            mirrored = {(2 - col, 2 - row) for col, row in cells}
            self.assertEqual(mirrored, set(cells), f"face {face}")

    def test_unknown_face_is_rejected(self) -> None:
        rect = pygame.Rect(0, 0, DIE_SIZE, DIE_SIZE)
        for face in (0, 7, -1):
            with self.assertRaises(ValueError):
                pip_centers(rect, face)


class TestDrawDie(DiceViewTestCase):
    def test_die_face_is_filled(self) -> None:
        rect = pygame.Rect(20, 20, DIE_SIZE, DIE_SIZE)
        draw_die(self.surface, rect, 2)
        self.assertEqual(rgb(self.surface, (rect.centerx, rect.top + 6)), SPACE_BG)

    def test_pips_are_drawn_dark(self) -> None:
        rect = pygame.Rect(20, 20, DIE_SIZE, DIE_SIZE)
        draw_die(self.surface, rect, 1)
        self.assertEqual(rgb(self.surface, rect.center), BOARD_LINE)

    def test_a_blank_area_is_left_blank(self) -> None:
        rect = pygame.Rect(20, 20, DIE_SIZE, DIE_SIZE)
        draw_die(self.surface, rect, 2)
        # Face 2's pips run corner to corner, so the centre stays pale.
        self.assertEqual(rgb(self.surface, rect.center), SPACE_BG)

    def test_nothing_is_drawn_outside_the_die(self) -> None:
        rect = pygame.Rect(100, 100, DIE_SIZE, DIE_SIZE)
        self.surface.fill((0, 0, 0))
        draw_die(self.surface, rect, 6)
        self.assertEqual(rgb(self.surface, (rect.left - 2, rect.centery)), (0, 0, 0))
        self.assertEqual(rgb(self.surface, (rect.centerx, rect.bottom + 2)), (0, 0, 0))


class TestDrawDice(DiceViewTestCase):
    def test_returns_the_area_it_covered(self) -> None:
        dice = self.settled()
        area = draw_dice(self.surface, dice, (10, 10), label=False)
        self.assertEqual(area.topleft, (10, 10))
        self.assertEqual(area.size, dice_size())

    def test_draws_both_dice(self) -> None:
        dice = self.settled()
        draw_dice(self.surface, dice, (10, 10), label=False)
        left, right = die_rects((10, 10))
        self.assertEqual(rgb(self.surface, (left.centerx, left.top + 6)), SPACE_BG)
        self.assertEqual(rgb(self.surface, (right.centerx, right.top + 6)), SPACE_BG)

    def test_unrolled_dice_still_draw(self) -> None:
        area = draw_dice(self.surface, Dice(), (10, 10))
        self.assertEqual(area.size, dice_size())

    def test_drawing_never_reads_the_result_mid_roll(self) -> None:
        self.dice.start(0)
        self.dice.update(ROLL_MS // 2)
        draw_dice(self.surface, self.dice, (10, 10))  # must not raise
        self.assertTrue(self.dice.rolling)

    def test_rolling_label_extends_the_area(self) -> None:
        self.dice.start(0)
        self.dice.update(10)
        labelled = draw_dice(self.surface, self.dice, (10, 10))
        self.assertGreater(labelled.height, dice_size()[1])

    def test_no_label_keeps_the_area_to_the_dice(self) -> None:
        self.dice.start(0)
        self.dice.update(10)
        bare = draw_dice(self.surface, self.dice, (10, 10), label=False)
        self.assertEqual(bare.size, dice_size())

    def test_doubles_are_announced(self) -> None:
        dice = Dice(random.Random(0))
        while True:
            dice.start(0)
            dice.finish()
            if dice.doubles:
                break
            dice.reset()
        area = draw_dice(self.surface, dice, (10, 10))
        self.assertGreater(area.height, dice_size()[1])

    def test_a_plain_settled_roll_has_no_label(self) -> None:
        dice = Dice(random.Random(0))
        while True:
            dice.start(0)
            dice.finish()
            if not dice.doubles:
                break
            dice.reset()
        area = draw_dice(self.surface, dice, (10, 10))
        self.assertEqual(area.size, dice_size())

    def test_custom_size_is_honoured(self) -> None:
        dice = self.settled()
        area = draw_dice(self.surface, dice, (0, 0), size=24, gap=4, label=False)
        self.assertEqual(area.size, dice_size(24, 4))


class TestHudWiring(DiceViewTestCase):
    """Phase 6 gave the dice a home: the HUD's dice block. Keep them in it."""

    def test_dice_sit_inside_the_hud_panel(self) -> None:
        from monopoly.ui.hud import Hud
        from monopoly.ui.renderer import HUD_RECT
        from monopoly.ui.theme import SCREEN_SIZE

        hud = Hud(HUD_RECT)
        topleft = (
            hud.dice_rect.centerx - dice_size()[0] // 2,
            hud.dice_rect.top,
        )
        screen = pygame.Surface(SCREEN_SIZE)
        area = draw_dice(screen, self.settled(), topleft)
        self.assertTrue(HUD_RECT.contains(area))
        self.assertTrue(hud.dice_rect.contains(area))


if __name__ == "__main__":
    unittest.main()
