"""Tests for the on-disk action log.

Two things are checked here, and they are quite different in kind.

The first is that the log *writes what happened*: a game played through
:mod:`monopoly.game` leaves a transcript with the roll, the purchase, the
build and the bankruptcy in it. The tests read the file back and grep it.

The second is that :func:`monopoly.actionlog.audit` is a real safety net --
that it notices a change nothing announced (which is what "the houses
disappeared" looks like from the outside) and that it notices a broken
conservation law (houses that are neither on the board nor in the box).

Every test opens its own log file in a temporary directory and calls
:func:`~monopoly.actionlog.reset_for_tests` afterwards, so no test can see
another's handlers or another's remembered census.
"""

from __future__ import annotations

import logging
import random
import tempfile
import unittest
from pathlib import Path

from monopoly import actionlog
from monopoly.building import Bank, BuildPlan
from monopoly.dice import Dice
from monopoly.game import Game, State
from monopoly.player import Player
from monopoly.property import build_properties

BROWN = (1, 3)


class LogTestCase(unittest.TestCase):
    """A fresh log file per test, torn down afterwards."""

    def setUp(self) -> None:
        self._dir = tempfile.TemporaryDirectory()
        self.addCleanup(self._dir.cleanup)
        self.addCleanup(actionlog.reset_for_tests)
        actionlog.reset_for_tests()
        self.path = Path(self._dir.name) / "test.log"
        actionlog.configure(self.path, level=logging.DEBUG)

    def read(self) -> str:
        """Everything written so far, flushed."""
        for handler in logging.getLogger(actionlog.LOGGER_NAME).handlers:
            handler.flush()
        return self.path.read_text(encoding="utf-8")

    def lines(self, needle: str) -> list[str]:
        return [line for line in self.read().splitlines() if needle in line]


class ConfigureTest(LogTestCase):
    def test_configure_opens_the_named_file(self):
        self.assertTrue(self.path.exists())
        self.assertEqual(actionlog.log_path(), self.path)
        self.assertTrue(actionlog.is_configured())

    def test_configure_is_idempotent(self):
        again = Path(self._dir.name) / "rival.log"
        self.assertEqual(actionlog.configure(again), self.path)
        self.assertFalse(again.exists())

    def test_nothing_is_written_before_configure(self):
        actionlog.reset_for_tests()
        quiet = Path(self._dir.name) / "quiet.log"
        actionlog.event("test", "ignored", value=1)
        self.assertFalse(quiet.exists())


class EventTest(LogTestCase):
    def test_an_event_writes_category_action_and_fields(self):
        actionlog.event("test", "thing", player="Ada", amount=1500)
        line = self.lines("test.thing")[0]
        self.assertIn("player=Ada", line)
        self.assertIn("amount=1,500", line)

    def test_none_fields_are_left_out(self):
        actionlog.event("test", "thing", creditor=None, payer="Ada")
        line = self.lines("test.thing")[0]
        self.assertNotIn("creditor", line)
        self.assertIn("payer=Ada", line)

    def test_a_field_may_be_called_level(self):
        # ``level`` is a building level all over the codebase, so it must not
        # collide with the severity argument.
        actionlog.event("test", "thing", level=3)
        self.assertIn("level=3", self.lines("test.thing")[0])

    def test_levels_map_onto_logging_levels(self):
        actionlog.debug("test", "quiet")
        actionlog.warn("test", "loud")
        actionlog.error("test", "louder")
        text = self.read()
        self.assertIn("DEBUG", text)
        self.assertIn("WARNING", text)
        self.assertIn("ERROR", text)


class AuditTest(LogTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.properties = build_properties()
        self.bank = Bank()
        self.ada = Player("Ada", 1500, "red")
        self.deeds = [p for p in self.properties if p.index in BROWN]
        for deed in self.deeds:
            self.ada.add_property(deed)
        actionlog.audit(self.bank, self.properties, "setup", [self.ada])

    def test_the_first_walk_reports_nothing(self):
        actionlog.forget_board()
        self.assertEqual(
            actionlog.audit(self.bank, self.properties, "first", [self.ada]), []
        )

    def test_a_silent_building_change_is_reported(self):
        # Exactly the shape of the bug this log exists for: a house vanishes
        # and nothing announced it.
        self.deeds[0].houses = 3
        self.bank.houses -= 3
        actionlog.audit(self.bank, self.properties, "check", [self.ada])
        self.deeds[0].houses = 0  # ...and now it is gone again

        changes = actionlog.audit(self.bank, self.properties, "check", [self.ada])
        self.assertEqual(len(changes), 1)
        self.assertIn("3h", changes[0])
        self.assertIn("0h", changes[0])
        self.assertIn("audit.changed", self.read())

    def test_an_owner_change_is_reported(self):
        bo = Player("Bo", 1500, "blue")
        bo.add_property(self.deeds[0])
        changes = actionlog.audit(
            self.bank, self.properties, "check", [self.ada, bo]
        )
        self.assertTrue(any("Ada" in c and "Bo" in c for c in changes))

    def test_a_cash_change_is_reported(self):
        self.ada.pay(200)
        changes = actionlog.audit(self.bank, self.properties, "check", [self.ada])
        self.assertTrue(any("$1,500->$1,300" in c for c in changes))

    def test_missing_houses_break_the_supply_check(self):
        self.deeds[0].houses = 2  # on the board but never taken from the box
        actionlog.audit(self.bank, self.properties, "check", [self.ada])
        self.assertIn("house_supply_broken", self.read())

    def test_missing_hotels_break_the_supply_check(self):
        self.deeds[0].has_hotel = True
        actionlog.audit(self.bank, self.properties, "check", [self.ada])
        self.assertIn("hotel_supply_broken", self.read())

    def test_a_balanced_board_breaks_nothing(self):
        self.deeds[0].houses = 4
        self.bank.houses -= 4
        actionlog.audit(self.bank, self.properties, "check", [self.ada])
        self.assertNotIn("supply_broken", self.read())

    def test_the_audit_never_raises(self):
        class Broken:
            index = 0
            name = "Broken"

            @property
            def owner(self):
                raise RuntimeError("boom")

        self.assertEqual(actionlog.audit(self.bank, [Broken()], "check"), [])
        self.assertIn("audit.failed", self.read())


class BuildPlanLoggingTest(LogTestCase):
    def test_a_commit_writes_every_lot_it_moved(self):
        properties = build_properties()
        bank = Bank()
        ada = Player("Ada", 1500, "red")
        for deed in [p for p in properties if p.index in BROWN]:
            ada.add_property(deed)
        plan = BuildPlan(ada, properties, bank)
        plan.add(plan.all_lots[0])
        plan.add(plan.all_lots[1])
        self.assertTrue(plan.commit())

        line = self.lines("build.commit ")[0]
        self.assertIn("player=Ada", line)
        self.assertIn("0->1", line)
        self.assertIn("bank_after=30h/12H", line)
        self.assertNotIn("supply_broken", self.read())


class WholeGameLoggingTest(LogTestCase):
    """A real game, played to the end, leaves a usable transcript."""

    def play(self) -> Game:
        rng = random.Random(11)
        players = [
            Player("Ada", 400, "red"),
            Player("Bo", 400, "blue"),
        ]
        game = Game(players, rng=rng, dice=Dice(rng, roll_ms=0), step_ms=0)
        game.start()
        now = 0
        for _ in range(4000):
            now += 10
            game.update(now)
            if game.state is State.GAME_OVER:
                break
            if game.auction is not None:
                game.pass_bid()
                continue
            if game.prompt is not None:
                enabled = [c for c in game.prompt.options if c.enabled]
                game.choose(enabled[0].key)
                continue
            actions = game.available_actions()
            if not actions:
                continue
            game.perform(sorted(actions, key=lambda a: a.value)[0], now)
        return game

    def test_the_transcript_covers_a_whole_game(self):
        game = self.play()
        text = self.read()
        for needle in (
            "game.new",
            "game.start",
            "turn.begin",
            "dice.rolled",
            "move.land",
            "action.perform",
            "turn.end",
        ):
            self.assertIn(needle, text, needle)
        self.assertTrue(game.log)

    def test_no_invariant_is_broken_during_an_ordinary_game(self):
        self.play()
        self.assertNotIn("supply_broken", self.read())

    def test_every_cash_move_is_accounted_for(self):
        self.play()
        # Each ``money.charge`` has the ``cash.pay`` that made it above it.
        self.assertTrue(self.lines("cash.pay"))
        self.assertTrue(self.lines("money.charge"))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
