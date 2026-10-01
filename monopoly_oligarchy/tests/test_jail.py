"""Phase 8 tests: Jail.

Phase 7 had to write the roll-for-doubles branch early -- without it a jailed
player could never leave and the turn loop deadlocked -- so
:class:`tests.test_game.JailTest` already covers that path. This file covers
what Phase 8 added around it: the ``PROMPT_JAIL`` a jailed turn opens on, the
two answers that buy the cell open before the dice are thrown, and the way
every answer funnels back into a single roll.

The fixtures come from :mod:`tests.test_game` so a roll is written literally
("Ada rolls a 3 and a 4") and nothing is animated: ``roll_ms=0`` settles the
dice on the first ``update`` and ``step_ms=0`` teleports the token, so one
``update`` carries a turn from the roll to the landing. No pygame here either.
"""

from __future__ import annotations

import unittest

from monopoly.game import (
    CARD_KEY,
    JAIL_FINE,
    JAIL_INDEX,
    JAIL_MAX_TURNS,
    OK_KEY,
    PAY_KEY,
    PROMPT_BUY,
    PROMPT_CARD,
    PROMPT_JAIL,
    ROLL_KEY,
    Action,
    Game,
    State,
)
from tests.test_game import answer, make_game, one_card_deck, take_turn

#: Rolls used below, chosen for where they land a player who starts in Jail.
FAIL = (1, 2)  # not doubles: 10 -> 13, States Avenue
CLEAN = (4, 6)  # not doubles: 10 -> 20, Free Parking, which prompts nothing
DOUBLES = (5, 5)  # doubles: 10 -> 20, Free Parking
SHORT_DOUBLES = (3, 3)  # doubles: 10 -> 16, St. James Place


def jailed_game(rolls=(), *, cash: int = 1500, **kwargs) -> Game:
    """A started game whose first player is locked up, turn open."""
    game = make_game(rolls=rolls, cash=cash, **kwargs)
    game._go_to_jail(game.current)
    game._begin_turn()
    return game


def jailed_with_card(rolls=(), *, cash: int = 1500):
    """The same, after the first player has drawn Get Out of Jail Free.

    Returns the game and the one-card Chance deck, so a test can check the
    card really goes home again.
    """
    deck = one_card_deck({"text": "Get Out of Jail Free.", "action": "get_out_of_jail"})
    game = make_game(rolls=[(3, 4), *rolls], cash=cash, chance=deck)
    take_turn(game)  # 0 -> 7, Chance
    answer(game, OK_KEY)  # and the card is kept
    game._go_to_jail(game.current)
    game._begin_turn()
    return game, deck


def keys(game: Game) -> list[str]:
    return [option.key for option in game.prompt.options]


def choice(game: Game, key: str):
    return next(o for o in game.prompt.options if o.key == key)


class GoingToJailTest(unittest.TestCase):
    """Every road to the cell sets the same four things."""

    def test_the_go_to_jail_space_locks_everything_down(self):
        game = make_game(rolls=[(2, 3)])
        game.current.position = 25
        take_turn(game)  # -> 30, Go To Jail
        player = game.players[0]
        self.assertEqual(player.position, JAIL_INDEX)
        self.assertTrue(player.in_jail)
        self.assertEqual(player.jail_turns, 0)
        self.assertEqual(player.doubles_streak, 0)

    def test_the_go_to_jail_card_locks_everything_down(self):
        chance = one_card_deck({"text": "Go to Jail.", "action": "go_to_jail"})
        game = make_game(rolls=[(3, 4)], chance=chance)
        take_turn(game)  # -> 7, Chance
        answer(game, OK_KEY)
        player = game.players[0]
        self.assertEqual(player.position, JAIL_INDEX)
        self.assertTrue(player.in_jail)
        self.assertEqual(player.jail_turns, 0)

    def test_a_third_double_locks_everything_down(self):
        game = make_game(rolls=[(2, 2), (2, 2), (2, 2)])
        take_turn(game)  # -> 4, Income Tax
        game.end_turn()
        take_turn(game)  # -> 8, Vermont Avenue
        answer(game, "auction")
        game.end_turn()
        take_turn(game)  # the third double
        player = game.players[0]
        self.assertTrue(player.in_jail)
        self.assertEqual(player.doubles_streak, 0)

    def test_the_doubles_that_jail_you_earn_no_extra_turn(self):
        game = make_game(rolls=[(2, 3)])
        game.current.position = 25
        take_turn(game)  # -> 30, Go To Jail
        self.assertIs(game.state, State.PLAYER_ACTIONS)
        game.end_turn()
        self.assertIs(game.current, game.players[1])

    def test_landing_on_jail_is_only_visiting(self):
        game = make_game(rolls=[(4, 6)])
        take_turn(game)  # 0 -> 10
        self.assertEqual(game.current.position, JAIL_INDEX)
        self.assertFalse(game.current.in_jail)
        game.end_turn()
        game.seat = 0
        game._begin_turn()
        self.assertIsNone(game.prompt, "a visitor is not asked how they leave")


class JailPromptTest(unittest.TestCase):
    """What a jailed player is offered at the top of their turn."""

    def test_a_jailed_turn_opens_on_the_jail_prompt(self):
        game = jailed_game()
        self.assertIs(game.state, State.PLAYER_TURN_START)
        self.assertIsNotNone(game.prompt)
        self.assertEqual(game.prompt.kind, PROMPT_JAIL)

    def test_the_three_ways_out_are_offered_in_order(self):
        game = jailed_game()
        self.assertEqual(keys(game), [PAY_KEY, CARD_KEY, ROLL_KEY])

    def test_the_labels_name_the_fine_the_card_and_the_roll(self):
        game = jailed_game()
        labels = [o.label for o in game.prompt.options]
        self.assertIn(f"${JAIL_FINE}", labels[0])
        self.assertIn("Card", labels[1])
        self.assertIn("Doubles", labels[2])

    def test_the_prompt_is_modal(self):
        game = jailed_game()
        self.assertEqual(game.available_actions(), frozenset())
        self.assertFalse(game.perform(Action.ROLL))
        self.assertIsNotNone(game.prompt, "a rejected action leaves the prompt up")

    def test_rolling_for_doubles_is_always_open(self):
        game = jailed_game(cash=0)
        self.assertTrue(choice(game, ROLL_KEY).enabled)

    def test_the_fine_is_closed_to_a_player_who_cannot_pay_it(self):
        game = jailed_game(cash=JAIL_FINE - 1)
        self.assertFalse(choice(game, PAY_KEY).enabled)

    def test_the_fine_is_open_to_a_player_with_exactly_it(self):
        game = jailed_game(cash=JAIL_FINE)
        self.assertTrue(choice(game, PAY_KEY).enabled)

    def test_the_card_is_closed_to_a_player_holding_none(self):
        game = jailed_game()
        self.assertEqual(game.current.goojf_cards, 0)
        self.assertFalse(choice(game, CARD_KEY).enabled)

    def test_the_card_is_open_to_a_player_holding_one(self):
        game, _ = jailed_with_card()
        self.assertTrue(choice(game, CARD_KEY).enabled)

    def test_the_text_counts_the_attempt(self):
        game = jailed_game()
        self.assertIn(f"1 of {JAIL_MAX_TURNS}", game.prompt.text)
        self.assertIn(game.current.name, game.prompt.text)

    def test_the_last_attempt_says_the_fine_is_coming(self):
        game = jailed_game()
        game.current.jail_turns = JAIL_MAX_TURNS - 1
        game._begin_turn()
        self.assertIn(f"{JAIL_MAX_TURNS} of {JAIL_MAX_TURNS}", game.prompt.text)
        self.assertIn("forced", game.prompt.text)

    def test_a_free_player_is_asked_nothing_and_may_roll(self):
        game = make_game()
        self.assertIsNone(game.prompt)
        self.assertEqual(game.available_actions(), frozenset({Action.ROLL}))

    def test_the_prompt_is_about_no_deed_and_no_card(self):
        game = jailed_game()
        self.assertIsNone(game.prompt.deed)
        self.assertIsNone(game.prompt.card)

    def test_an_unknown_answer_is_refused(self):
        game = jailed_game()
        with self.assertRaises(ValueError):
            game.choose("bribe")
        self.assertIsNotNone(game.prompt)

    def test_a_closed_answer_is_refused(self):
        game = jailed_game(cash=0)
        with self.assertRaises(ValueError):
            game.choose(PAY_KEY)
        self.assertTrue(game.current.in_jail)
        self.assertIsNotNone(game.prompt)

    def test_the_prompt_is_gone_once_it_is_answered(self):
        game = jailed_game([FAIL])
        answer(game, ROLL_KEY)
        self.assertIsNone(game.prompt)


class PayTheFineTest(unittest.TestCase):
    """"Pay $50 & Roll": out first, then an ordinary roll."""

    def test_the_fine_is_deducted_and_the_cell_opens(self):
        game = jailed_game([CLEAN])
        answer(game, PAY_KEY)
        player = game.players[0]
        self.assertEqual(player.cash, 1500 - JAIL_FINE)
        self.assertFalse(player.in_jail)
        self.assertEqual(player.jail_turns, 0)

    def test_paying_rolls_and_moves(self):
        game = jailed_game([CLEAN])
        answer(game, PAY_KEY)
        self.assertEqual(game.players[0].position, JAIL_INDEX + 10)
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    def test_paying_and_rolling_doubles_earns_another_turn(self):
        game = jailed_game([DOUBLES])
        answer(game, PAY_KEY)
        self.assertEqual(game.players[0].doubles_streak, 1)
        game.end_turn()
        self.assertIs(game.current, game.players[0], "the fine bought a clean roll")
        self.assertIsNone(game.prompt, "and they are not asked about Jail again")

    def test_paying_late_still_clears_the_count(self):
        game = jailed_game([CLEAN])
        game.current.jail_turns = 2
        game._begin_turn()
        answer(game, PAY_KEY)
        self.assertEqual(game.players[0].jail_turns, 0)
        self.assertEqual(game.players[0].cash, 1500 - JAIL_FINE)

    def test_paying_is_reported(self):
        game = jailed_game([CLEAN])
        answer(game, PAY_KEY)
        self.assertTrue(
            any(f"${JAIL_FINE}" in line and "Jail" in line for line in game.log),
            game.log,
        )

    def test_the_fine_is_paid_once(self):
        game = jailed_game([CLEAN])
        answer(game, PAY_KEY)
        self.assertEqual(game.players[0].cash, 1500 - JAIL_FINE)
        self.assertIsNone(game.debt)


class JailCardTest(unittest.TestCase):
    """"Use Jail Card": the card is spent, not the cash."""

    def test_the_card_opens_the_cell_for_free(self):
        game, _ = jailed_with_card([CLEAN])
        cash = game.players[0].cash
        answer(game, CARD_KEY)
        player = game.players[0]
        self.assertFalse(player.in_jail)
        self.assertEqual(player.jail_turns, 0)
        self.assertEqual(player.cash, cash)

    def test_the_card_is_spent(self):
        game, _ = jailed_with_card([CLEAN])
        answer(game, CARD_KEY)
        self.assertEqual(game.players[0].goojf_cards, 0)

    def test_the_card_goes_back_under_its_own_deck(self):
        game, deck = jailed_with_card([CLEAN])
        self.assertEqual(len(deck), 0)
        answer(game, CARD_KEY)
        self.assertEqual(len(deck), 1)
        self.assertEqual(deck.held, ())

    def test_using_the_card_rolls_and_moves(self):
        game, _ = jailed_with_card([CLEAN])
        answer(game, CARD_KEY)
        self.assertEqual(game.players[0].position, JAIL_INDEX + 10)
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    def test_doubles_after_a_card_earn_another_turn(self):
        game, _ = jailed_with_card([DOUBLES])
        answer(game, CARD_KEY)
        game.end_turn()
        self.assertIs(game.current, game.players[0])

    def test_a_second_stretch_inside_finds_no_card_left(self):
        game, _ = jailed_with_card([CLEAN])
        answer(game, CARD_KEY)
        game._go_to_jail(game.players[0])
        game._begin_turn()
        self.assertFalse(choice(game, CARD_KEY).enabled)


class RollForDoublesTest(unittest.TestCase):
    """The branch Phase 7 wrote, now reached through the prompt."""

    def test_doubles_open_the_cell_and_move(self):
        game = jailed_game([SHORT_DOUBLES])
        answer(game, ROLL_KEY)
        player = game.players[0]
        self.assertFalse(player.in_jail)
        self.assertEqual(player.jail_turns, 0)
        self.assertEqual(player.position, JAIL_INDEX + 6)
        self.assertEqual(player.cash, 1500, "doubles cost nothing")

    def test_doubles_out_of_jail_earn_no_extra_turn(self):
        game = jailed_game([SHORT_DOUBLES])
        answer(game, ROLL_KEY)
        self.assertEqual(game.players[0].doubles_streak, 0)
        answer(game, "auction")  # St. James Place is for sale
        game.end_turn()
        self.assertIs(game.current, game.players[1])

    def test_a_miss_costs_a_turn_and_nothing_else(self):
        game = jailed_game([FAIL])
        answer(game, ROLL_KEY)
        player = game.players[0]
        self.assertTrue(player.in_jail)
        self.assertEqual(player.position, JAIL_INDEX)
        self.assertEqual(player.cash, 1500)
        self.assertEqual(player.jail_turns, 1)
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    def test_the_count_climbs_with_each_miss(self):
        game = jailed_game([FAIL, FAIL])
        for expected in (1, 2):
            answer(game, ROLL_KEY)
            self.assertEqual(game.players[0].jail_turns, expected)
            game.end_turn()
            game.seat = 0
            game._begin_turn()
        self.assertIn(f"{JAIL_MAX_TURNS} of {JAIL_MAX_TURNS}", game.prompt.text)

    def test_the_third_miss_forces_the_fine_and_moves(self):
        game = jailed_game([FAIL, FAIL, CLEAN])
        for _ in range(3):
            game.seat = 0
            game._begin_turn()
            answer(game, ROLL_KEY)
        player = game.players[0]
        self.assertFalse(player.in_jail)
        self.assertEqual(player.jail_turns, 0)
        self.assertEqual(player.cash, 1500 - JAIL_FINE)
        self.assertEqual(player.position, JAIL_INDEX + 10)

    def test_the_forced_fine_can_bankrupt(self):
        """Phase 13 answers the debt Phase 8 could only record.

        The forced fine is the one charge a player never chose to make, so it
        is the one that can end a game from inside the cell. With nothing to
        sell and nothing to mortgage, $10 does not cover $50.
        """
        game = jailed_game([FAIL, FAIL, CLEAN], cash=10)
        for _ in range(3):
            if game.state is State.GAME_OVER:
                break
            game.seat = 0
            game._begin_turn()
            answer(game, ROLL_KEY)
        player = game.players[0]
        self.assertFalse(player.in_jail, "the cell opens whether or not it is paid")
        self.assertTrue(player.is_bankrupt)
        self.assertEqual(player.cash, 0)
        self.assertIsNone(game.debt, "the debt died with the player's game")
        self.assertIsNone(
            game.last_settlement.creditor, "the fine is owed to the bank"
        )
        self.assertEqual(game.last_settlement.amount, JAIL_FINE - 10)


class JailTurnOrderTest(unittest.TestCase):
    """A jailed turn is still a turn: one prompt, one roll, one End Turn."""

    def test_a_missed_roll_still_passes_play_on(self):
        game = jailed_game([FAIL, CLEAN])
        answer(game, ROLL_KEY)
        game.end_turn()
        self.assertIs(game.current, game.players[1])
        self.assertIsNone(game.prompt, "the free player is asked nothing")
        take_turn(game)  # Bob: 0 -> 10, just visiting
        self.assertEqual(game.players[1].position, JAIL_INDEX)
        game.end_turn()
        self.assertIs(game.current, game.players[0])
        self.assertEqual(game.prompt.kind, PROMPT_JAIL, "Ada is asked again")
        self.assertIn(f"2 of {JAIL_MAX_TURNS}", game.prompt.text)

    def test_the_turn_after_release_is_an_ordinary_one(self):
        game = jailed_game([CLEAN, (1, 3), CLEAN])
        answer(game, PAY_KEY)  # out, 10 -> 20
        game.end_turn()
        take_turn(game)  # Bob: 0 -> 4, Income Tax
        game.end_turn()
        self.assertIs(game.current, game.players[0])
        self.assertIsNone(game.prompt)
        self.assertEqual(game.available_actions(), frozenset({Action.ROLL}))
        take_turn(game)  # 20 -> 30, Go To Jail
        self.assertTrue(game.players[0].in_jail, "and they can be jailed again")

    def test_a_jailed_player_is_skipped_once_bankrupt(self):
        game = jailed_game([CLEAN])
        game.players[0].is_bankrupt = True
        game.seat = 1
        game._begin_turn()
        game.perform(Action.ROLL)
        game.update(0)
        while game.prompt is not None:
            answer(game, "auction")
        game.end_turn()
        self.assertIs(game.current, game.players[1], "Ada is out; Bob plays on")
        self.assertIs(game.state, State.GAME_OVER)


class JailPromptRebuildTest(unittest.TestCase):
    """The prompt is rebuilt every turn, so it tracks the player's means."""

    def test_the_fine_closes_once_the_money_is_gone(self):
        game = jailed_game()
        self.assertTrue(choice(game, PAY_KEY).enabled)
        game.current.cash = 0
        game._begin_turn()
        self.assertFalse(choice(game, PAY_KEY).enabled)

    def test_a_deed_bought_on_the_way_in_does_not_pay_the_fine(self):
        game = jailed_game(cash=JAIL_FINE - 1)
        game.current.add_property(game.deed(1))
        game._begin_turn()
        self.assertFalse(
            choice(game, PAY_KEY).enabled,
            "the fine is cash only -- mortgaging is Phase 12's",
        )

    def test_every_jailed_turn_gets_a_fresh_prompt(self):
        game = jailed_game([FAIL])
        first = game.prompt
        answer(game, ROLL_KEY)
        game.end_turn()
        game.seat = 0
        game._begin_turn()
        self.assertIsNot(game.prompt, first)


class JailLandingTest(unittest.TestCase):
    """Leaving Jail lands on a space like any other move."""

    def test_a_deed_reached_from_jail_is_offered_for_sale(self):
        game = jailed_game([SHORT_DOUBLES])
        answer(game, ROLL_KEY)
        self.assertEqual(game.prompt.kind, PROMPT_BUY)
        self.assertEqual(game.prompt.deed.index, JAIL_INDEX + 6)

    def test_a_card_space_reached_from_jail_deals_a_card(self):
        chance = one_card_deck({"text": "Bank pays you $50.", "action": "collect",
                                "amount": 50})
        game = jailed_game([(6, 6)], chance=chance)
        answer(game, ROLL_KEY)  # doubles, 10 -> 22, Chance
        self.assertEqual(game.players[0].position, 22)
        self.assertEqual(game.prompt.kind, PROMPT_CARD)
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].cash, 1500 + 50)


class JailSoakTest(unittest.TestCase):
    """Play a long game on real dice and check Jail never drifts.

    The unit tests above each set one situation up by hand. This one plays a
    seeded four-handed game for hundreds of turns -- answering every prompt as
    it comes, buying, auctioning and bidding at random -- and re-checks the
    whole jail invariant after every single step. It is the guard against Phase 9 and
    everything after it quietly breaking the cell door.
    """

    TURNS = 400

    def check(self, game: Game, chance, chest) -> None:
        """Everything that must be true of Jail at every moment of a game."""
        for player in game.players:
            with self.subTest(player=player.name):
                if player.in_jail:
                    self.assertEqual(player.position, JAIL_INDEX)
                    self.assertLess(player.jail_turns, JAIL_MAX_TURNS)
                else:
                    self.assertEqual(
                        player.jail_turns, 0, "a freed player keeps no count"
                    )
                self.assertGreaterEqual(player.jail_turns, 0)
                self.assertGreaterEqual(player.goojf_cards, 0)

        # A keepable card leaves its deck on the draw but is not in anyone's
        # hand until the card prompt showing it has been acknowledged, so
        # exactly one card may be in limbo -- and only then.
        prompt = game.prompt
        limbo = int(
            prompt is not None
            and prompt.kind == PROMPT_CARD
            and prompt.card is not None
            and prompt.card.keepable
        )
        held = len(chance.held) + len(chest.held)
        self.assertEqual(
            sum(p.goojf_cards for p in game.players) + limbo,
            held,
            "every card out of a deck is in a hand or on the open prompt",
        )
        self.assertEqual(len(chance) + len(chance.held), self.chance_size)
        self.assertEqual(len(chest) + len(chest.held), self.chest_size)

        if game.state is State.PLAYER_TURN_START:
            asked = game.prompt is not None and game.prompt.kind == PROMPT_JAIL
            self.assertEqual(
                asked,
                game.current.in_jail,
                "a jailed turn opens on the jail prompt, and only a jailed one",
            )

    def test_jail_holds_up_over_a_long_game(self):
        import random

        from monopoly.cards import Deck

        rng = random.Random(1234)
        chance, chest = Deck.chance(rng), Deck.community_chest(rng)
        self.chance_size = len(chance)
        self.chest_size = len(chest)
        game = make_game(
            names=("Ada", "Bob", "Cleo", "Dai"),
            cash=2000,
            chance=chance,
            community_chest=chest,
        )
        seen = {"jailed": 0, "paid": 0, "carded": 0, "rolled": 0}
        turns = 0
        steps = 0

        while turns < self.TURNS and game.state is not State.GAME_OVER:
            steps += 1
            self.assertLess(steps, 200 * self.TURNS, "the turn loop is spinning")
            game.update(0)
            self.check(game, chance, chest)

            if game.prompt is not None:
                if game.prompt.kind == PROMPT_JAIL:
                    seen["jailed"] += 1
                open_keys = [o.key for o in game.prompt.options if o.enabled]
                self.assertTrue(open_keys, "a prompt always has a way out")
                key = rng.choice(open_keys)
                if game.prompt.kind == PROMPT_JAIL:
                    seen[{PAY_KEY: "paid", CARD_KEY: "carded", ROLL_KEY: "rolled"}[key]] += 1
                game.choose(key)
                continue

            if game.auction is not None:
                # Phase 10: a declined deed goes under the hammer. Bid the
                # asking price half the time, pass the rest.
                if rng.random() < 0.5 and game.bid(game.auction.min_bid):
                    continue
                game.pass_bid()
                continue

            actions = game.available_actions()
            if Action.ROLL in actions:
                game.perform(Action.ROLL)
            elif Action.END_TURN in actions:
                game.perform(Action.END_TURN)
                turns += 1
            else:
                self.fail(f"stuck in {game.state.value} with nothing to do")

        self.assertGreater(seen["jailed"], 0, "nobody ever went to Jail")
        for answer_name in ("paid", "rolled"):
            self.assertGreater(
                seen[answer_name], 0, f"the {answer_name} way out was never taken"
            )
        self.check(game, chance, chest)

    def test_the_cards_all_come_home_when_the_decks_reset(self):
        """A reset puts held Get Out of Jail Free cards back in the pile."""
        game, deck = jailed_with_card([CLEAN])
        self.assertEqual(len(deck), 0)
        deck.reset()
        self.assertEqual(len(deck), 1)
        self.assertEqual(deck.held, ())


if __name__ == "__main__":
    unittest.main()
