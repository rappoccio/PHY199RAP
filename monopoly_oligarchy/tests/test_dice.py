"""Phase 5 tests: the dice and their roll animation.

No pygame here -- ``dice.py`` is pure Python, and the animation is driven by
millisecond stamps the tests supply themselves, so a roll can be stepped
frame by frame without a clock.
"""

from __future__ import annotations

import random
import unittest

from monopoly.dice import (
    FLICKER_MS,
    RESTING_FACES,
    ROLL_MS,
    SIDES,
    Dice,
    is_doubles,
    roll,
)


class TestRoll(unittest.TestCase):
    def test_returns_two_dice(self) -> None:
        self.assertEqual(len(roll()), 2)

    def test_faces_are_in_range(self) -> None:
        for _ in range(200):
            for face in roll():
                self.assertIn(face, range(1, SIDES + 1))

    def test_faces_are_integers(self) -> None:
        for face in roll():
            self.assertIsInstance(face, int)

    def test_every_face_turns_up_eventually(self) -> None:
        seen = set()
        for _ in range(500):
            seen.update(roll())
        self.assertEqual(seen, set(range(1, SIDES + 1)))

    def test_both_dice_are_rolled_independently(self) -> None:
        rolls = [roll() for _ in range(200)]
        self.assertTrue(any(d1 != d2 for d1, d2 in rolls))
        self.assertTrue(any(d1 == d2 for d1, d2 in rolls))

    def test_seeded_rng_is_reproducible(self) -> None:
        first = [roll(random.Random(7)) for _ in range(1)]
        second = [roll(random.Random(7)) for _ in range(1)]
        self.assertEqual(first, second)

    def test_seeded_sequence_is_reproducible(self) -> None:
        a = random.Random(1234)
        b = random.Random(1234)
        self.assertEqual([roll(a) for _ in range(20)], [roll(b) for _ in range(20)])


class TestIsDoubles(unittest.TestCase):
    def test_matching_faces_are_doubles(self) -> None:
        for face in range(1, SIDES + 1):
            self.assertTrue(is_doubles(face, face))

    def test_differing_faces_are_not(self) -> None:
        self.assertFalse(is_doubles(1, 2))
        self.assertFalse(is_doubles(6, 5))


class DiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.dice = Dice(random.Random(42))

    def settle(self, start: int = 0) -> None:
        """Run one roll from ``start`` to the moment it settles."""
        self.dice.start(start)
        self.dice.update(start + self.dice.roll_ms)


class TestDiceConstruction(DiceTestCase):
    def test_rejects_negative_roll_ms(self) -> None:
        with self.assertRaises(ValueError):
            Dice(roll_ms=-1)

    def test_rejects_zero_flicker_ms(self) -> None:
        with self.assertRaises(ValueError):
            Dice(flicker_ms=0)

    def test_default_timings_come_from_the_module(self) -> None:
        dice = Dice()
        self.assertEqual(dice.roll_ms, ROLL_MS)
        self.assertEqual(dice.flicker_ms, FLICKER_MS)

    def test_animation_is_brief(self) -> None:
        # The plan calls for a roughly 0.4s animation.
        self.assertEqual(ROLL_MS, 400)

    def test_supplies_its_own_rng_when_none_is_given(self) -> None:
        dice = Dice()
        dice.start(0)
        self.assertTrue(dice.finish())
        self.assertIn(dice.total, range(2, 2 * SIDES + 1))


class TestDiceBeforeAnyRoll(DiceTestCase):
    def test_is_not_rolling(self) -> None:
        self.assertFalse(self.dice.rolling)

    def test_has_not_settled(self) -> None:
        self.assertFalse(self.dice.settled)

    def test_shows_resting_faces(self) -> None:
        self.assertEqual(self.dice.faces, RESTING_FACES)

    def test_result_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            self.dice.result

    def test_total_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            self.dice.total

    def test_doubles_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            self.dice.doubles

    def test_update_reports_nothing(self) -> None:
        self.assertFalse(self.dice.update(999))

    def test_finish_reports_nothing(self) -> None:
        self.assertFalse(self.dice.finish())


class TestDiceRolling(DiceTestCase):
    def test_start_begins_the_animation(self) -> None:
        self.dice.start(1000)
        self.assertTrue(self.dice.rolling)
        self.assertFalse(self.dice.settled)

    def test_result_is_unreadable_mid_roll(self) -> None:
        self.dice.start(1000)
        self.dice.update(1000 + ROLL_MS // 2)
        with self.assertRaises(RuntimeError):
            self.dice.result

    def test_update_before_the_end_keeps_rolling(self) -> None:
        self.dice.start(1000)
        self.assertFalse(self.dice.update(1000 + ROLL_MS - 1))
        self.assertTrue(self.dice.rolling)

    def test_update_at_the_end_settles(self) -> None:
        self.dice.start(1000)
        self.assertTrue(self.dice.update(1000 + ROLL_MS))
        self.assertTrue(self.dice.settled)

    def test_update_reports_the_settle_only_once(self) -> None:
        self.dice.start(1000)
        self.dice.update(1000 + ROLL_MS)
        self.assertFalse(self.dice.update(1000 + ROLL_MS + 100))

    def test_starting_twice_raises(self) -> None:
        self.dice.start(0)
        with self.assertRaises(RuntimeError):
            self.dice.start(10)

    def test_a_new_roll_can_start_once_settled(self) -> None:
        self.settle(0)
        first = self.dice.result
        self.dice.start(1000)
        self.assertTrue(self.dice.rolling)
        self.dice.update(1000 + ROLL_MS)
        self.assertIsNotNone(self.dice.result)
        self.assertIsNotNone(first)

    def test_elapsed_tracks_the_clock(self) -> None:
        self.dice.start(500)
        self.dice.update(700)
        self.assertEqual(self.dice.elapsed, 200)

    def test_elapsed_never_goes_negative(self) -> None:
        self.dice.start(500)
        self.dice.update(400)
        self.assertEqual(self.dice.elapsed, 0)

    def test_progress_runs_from_zero_to_one(self) -> None:
        self.dice.start(0)
        self.assertEqual(self.dice.progress, 0.0)
        self.dice.update(ROLL_MS // 2)
        self.assertAlmostEqual(self.dice.progress, 0.5, places=2)
        self.dice.update(ROLL_MS)
        self.assertEqual(self.dice.progress, 1.0)

    def test_progress_is_one_when_idle(self) -> None:
        self.assertEqual(self.dice.progress, 1.0)


class TestDiceResult(DiceTestCase):
    def test_total_is_the_sum_of_the_faces(self) -> None:
        self.settle()
        self.assertEqual(self.dice.total, sum(self.dice.result))

    def test_total_is_in_range(self) -> None:
        for start in range(0, 10_000, 1000):
            dice = Dice(random.Random(start))
            dice.start(start)
            dice.update(start + ROLL_MS)
            self.assertIn(dice.total, range(2, 2 * SIDES + 1))

    def test_doubles_agrees_with_the_faces(self) -> None:
        for seed in range(30):
            dice = Dice(random.Random(seed))
            dice.start(0)
            dice.finish()
            self.assertEqual(dice.doubles, is_doubles(*dice.result))

    def test_result_is_stable_across_reads(self) -> None:
        self.settle()
        self.assertEqual(self.dice.result, self.dice.result)

    def test_faces_show_the_result_once_settled(self) -> None:
        self.settle()
        self.assertEqual(self.dice.faces, self.dice.result)

    def test_result_is_decided_when_the_roll_starts(self) -> None:
        # Two dice with the same seed must agree even though one of them ran
        # the whole animation and the other was cut short.
        animated = Dice(random.Random(9))
        instant = Dice(random.Random(9))
        animated.start(0)
        for now in range(0, ROLL_MS + 1, 16):
            animated.update(now)
        instant.start(0)
        instant.finish()
        self.assertEqual(animated.result, instant.result)


class TestDiceAnimation(DiceTestCase):
    def test_faces_stay_in_range_while_rolling(self) -> None:
        self.dice.start(0)
        for now in range(0, ROLL_MS, 5):
            self.dice.update(now)
            for face in self.dice.faces:
                self.assertIn(face, range(1, SIDES + 1))

    def test_faces_are_a_pure_function_of_elapsed_time(self) -> None:
        self.dice.start(0)
        self.dice.update(ROLL_MS // 2)
        self.assertEqual(self.dice.faces, self.dice.faces)

    def test_faces_change_during_the_roll(self) -> None:
        self.dice.start(0)
        seen = set()
        for now in range(0, ROLL_MS, FLICKER_MS):
            self.dice.update(now)
            seen.add(self.dice.faces)
        self.assertGreater(len(seen), 1)

    def test_consecutive_flicker_steps_differ(self) -> None:
        self.dice.start(0)
        previous = None
        for step in range(ROLL_MS // FLICKER_MS):
            self.dice.update(step * FLICKER_MS)
            faces = self.dice.faces
            self.assertNotEqual(faces, previous)
            previous = faces

    def test_faces_hold_steady_within_one_flicker_step(self) -> None:
        self.dice.start(0)
        self.dice.update(0)
        first = self.dice.faces
        self.dice.update(FLICKER_MS - 1)
        self.assertEqual(self.dice.faces, first)

    def test_flicker_does_not_disturb_the_roll_sequence(self) -> None:
        # A seeded game must play out identically however many frames the
        # animation happened to draw.
        animated = Dice(random.Random(5))
        skipped = Dice(random.Random(5))
        for i in range(10):
            base = i * 1000
            animated.start(base)
            for now in range(base, base + ROLL_MS, 7):
                animated.update(now)
            animated.update(base + ROLL_MS)
            skipped.start(base)
            skipped.finish()
            self.assertEqual(animated.result, skipped.result)

    def test_instant_mode_settles_on_the_first_update(self) -> None:
        dice = Dice(random.Random(3), roll_ms=0)
        dice.start(0)
        self.assertTrue(dice.update(0))
        self.assertTrue(dice.settled)

    def test_a_long_animation_still_has_flicker_frames(self) -> None:
        dice = Dice(random.Random(3), roll_ms=1000, flicker_ms=100)
        dice.start(0)
        dice.update(999)
        self.assertIn(dice.faces[0], range(1, SIDES + 1))
        self.assertTrue(dice.rolling)


class TestDiceControl(DiceTestCase):
    def test_finish_cuts_the_animation_short(self) -> None:
        self.dice.start(0)
        self.dice.update(10)
        self.assertTrue(self.dice.finish())
        self.assertTrue(self.dice.settled)
        self.assertFalse(self.dice.rolling)

    def test_finish_keeps_the_result(self) -> None:
        self.dice.start(0)
        self.dice.finish()
        first = self.dice.result
        self.assertEqual(self.dice.result, first)

    def test_finish_is_idempotent(self) -> None:
        self.dice.start(0)
        self.assertTrue(self.dice.finish())
        self.assertFalse(self.dice.finish())

    def test_reset_clears_the_roll(self) -> None:
        self.settle()
        self.dice.reset()
        self.assertFalse(self.dice.settled)
        self.assertFalse(self.dice.rolling)
        self.assertEqual(self.dice.faces, RESTING_FACES)
        with self.assertRaises(RuntimeError):
            self.dice.result

    def test_reset_allows_a_fresh_roll(self) -> None:
        self.dice.start(0)
        self.dice.reset()
        self.dice.start(0)
        self.assertTrue(self.dice.rolling)


if __name__ == "__main__":
    unittest.main()
