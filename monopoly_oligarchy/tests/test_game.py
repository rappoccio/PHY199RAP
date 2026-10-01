"""Phase 7 tests: the turn loop.

Every test here plays a real game, just an un-animated one: the dice settle on
the first ``update`` (``roll_ms=0``) and the token teleports rather than walking
(``step_ms=0``), so one :meth:`Game.update` carries a turn all the way from the
roll to the landing. Two tests at the end put the animation back to check that
the timing works too.

The rolls themselves are scripted through :class:`ScriptedRandom`, which feeds
:func:`monopoly.dice.roll` a queue of faces, so "Ada rolls a 3 and a 4" is
written literally rather than hunted for with a seed. ``game.py`` imports no
pygame, and neither does this file.
"""

from __future__ import annotations

import random
import unittest

from monopoly.cards import Card, Deck
from monopoly.data_loader import BOARD_SIZE
from monopoly.dice import Dice
from monopoly.game import (
    AUCTION_KEY,
    BUY_KEY,
    DEFERRED_ACTIONS,
    GO_SALARY,
    JAIL_FINE,
    JAIL_INDEX,
    OK_KEY,
    PROMPT_BUY,
    PROMPT_CARD,
    PROMPT_INFO,
    ROLL_KEY,
    Action,
    Choice,
    Debt,
    Game,
    Prompt,
    State,
    nearest_ahead,
)
from monopoly.player import Player

TOKENS = ("red", "blue", "green", "yellow", "purple", "orange")


class ScriptedRandom(random.Random):
    """A generator whose ``randint`` hands out a queued list of dice faces.

    Everything else (``shuffle``, used by the decks) falls through to the real
    generator, so stacking the dice never disturbs the card order.
    """

    def __init__(self, faces=(), seed: int = 0) -> None:
        super().__init__(seed)
        self.faces = list(faces)

    def randint(self, a: int, b: int) -> int:
        return self.faces.pop(0) if self.faces else super().randint(a, b)


def make_game(
    *,
    rolls=(),
    cash: int = 1500,
    names=("Ada", "Bob"),
    start: bool = True,
    **kwargs,
) -> Game:
    """A started game with scripted dice and no animation.

    ``rolls`` is a list of ``(d1, d2)`` pairs, consumed in order.
    """
    faces = [face for pair in rolls for face in pair]
    rng = ScriptedRandom(faces)
    players = [Player(n, cash, t) for n, t in zip(names, TOKENS)]
    game = Game(
        players,
        dice=Dice(rng, roll_ms=0),
        rng=rng,
        step_ms=0,
        **kwargs,
    )
    if start:
        game.start()
    return game


def one_card_deck(card: dict) -> Deck:
    """A deck holding a single known card, so a draw is deterministic."""
    return Deck([Card.from_dict(card)], shuffle=False)


def take_turn(game: Game, now: int = 0) -> None:
    """Roll and let everything that follows resolve."""
    game.perform(Action.ROLL, now)
    game.update(now)


def pass_out_auction(game: Game) -> None:
    """Have every bidder pass, so an open sale ends with the deed unsold.

    That is what declining a deed used to do on its own, before Phase 10 put
    an auction in between.
    """
    for _ in range(len(game.players) + 1):
        if game.auction is None:
            return
        game.pass_bid()
    raise AssertionError("the auction would not settle")


def answer(game: Game, key: str) -> None:
    """Answer the open prompt and let any movement it causes resolve.

    Declining a deed opens a Phase 10 auction, which is modal. Unless a test
    is about the sale itself it only wants the turn to carry on, so a sale
    opened here is settled the quiet way, with everybody passing.
    """
    game.choose(key)
    game.update(0)
    pass_out_auction(game)


class SetupTest(unittest.TestCase):
    def test_a_game_needs_players(self):
        with self.assertRaises(ValueError):
            Game([])

    def test_negative_step_ms_is_rejected(self):
        with self.assertRaises(ValueError):
            Game([Player("Ada", 1500, "red")], step_ms=-1)

    def test_state_before_start(self):
        game = make_game(start=False)
        self.assertIs(game.state, State.SETUP)
        self.assertEqual(game.available_actions(), frozenset())

    def test_start_opens_the_first_turn(self):
        game = make_game()
        self.assertIs(game.state, State.PLAYER_TURN_START)
        self.assertIs(game.current, game.players[0])
        self.assertIn("Ada", game.message)

    def test_start_twice_raises(self):
        game = make_game()
        with self.assertRaises(RuntimeError):
            game.start()

    def test_the_board_comes_with_its_deeds(self):
        game = make_game()
        self.assertEqual(len(game.properties), 28)
        self.assertEqual(game.deed(1).name, "Mediterranean Avenue")
        self.assertIsNone(game.deed(0), "Go carries no deed")

    def test_space_lookup(self):
        self.assertEqual(make_game().space(JAIL_INDEX)["type"], "jail")

    def test_everyone_starts_on_go_with_their_stake(self):
        game = make_game(cash=750)
        for player in game.players:
            self.assertEqual((player.position, player.cash), (0, 750))


class AvailableActionsTest(unittest.TestCase):
    def test_only_roll_at_the_start_of_a_turn(self):
        game = make_game()
        self.assertEqual(game.available_actions(), frozenset({Action.ROLL}))

    def test_nothing_while_the_dice_are_in_the_air(self):
        game = make_game(rolls=[(1, 2)])
        game.dice = Dice(game.rng, roll_ms=400)
        game.perform(Action.ROLL, 0)
        self.assertIs(game.state, State.ROLLING)
        self.assertEqual(game.available_actions(), frozenset())

    def test_end_turn_once_the_landing_is_resolved(self):
        game = make_game(rolls=[(2, 2)])  # Income Tax
        take_turn(game)
        self.assertIs(game.state, State.PLAYER_ACTIONS)
        self.assertEqual(
            game.available_actions(),
            frozenset({Action.END_TURN, Action.TRADE}),
        )

    def test_a_prompt_blocks_every_action(self):
        game = make_game(rolls=[(1, 2)])  # Baltic Avenue, unowned
        take_turn(game)
        self.assertIsNotNone(game.prompt)
        self.assertEqual(game.available_actions(), frozenset())

    def test_nothing_is_deferred_any_more(self):
        # Phase 9 took BUILD off the deferred list (test_building.py), Phase 11
        # took TRADE (test_trade_game.py) and Phase 12 took MORTGAGE
        # (test_mortgage_game.py), so the list is empty and every button is
        # decided here.
        self.assertEqual(DEFERRED_ACTIONS, ())
        game = make_game(rolls=[(2, 2)])
        take_turn(game)
        # Ada owns nothing and holds no whole group, so two of the three are
        # dark on their own account -- registering a handler does not change
        # that, it only changes what pressing them would do.
        game.action_handlers[Action.MORTGAGE] = lambda g: None
        self.assertNotIn(Action.MORTGAGE, game.available_actions())
        self.assertNotIn(Action.BUILD, game.available_actions())
        self.assertIn(Action.TRADE, game.available_actions())

    def test_a_registered_handler_is_what_perform_calls(self):
        game = make_game(rolls=[(2, 2)])
        take_turn(game)
        game.current.add_property(game.deed(3))  # so Mortgage is legal at all
        seen = []
        game.action_handlers[Action.MORTGAGE] = seen.append
        self.assertTrue(game.perform(Action.MORTGAGE))
        self.assertEqual(seen, [game])
        self.assertIsNone(game.mortgage, "the handler wins, so no draft opened")

    def test_perform_refuses_an_illegal_action(self):
        game = make_game()
        self.assertFalse(game.perform(Action.END_TURN))
        self.assertIs(game.state, State.PLAYER_TURN_START)

    def test_rolling_out_of_turn_raises(self):
        game = make_game(rolls=[(2, 2)])
        take_turn(game)
        with self.assertRaises(RuntimeError):
            game.roll_dice(0)

    def test_ending_a_turn_that_has_not_started_raises(self):
        with self.assertRaises(RuntimeError):
            make_game().end_turn()


class MovementTest(unittest.TestCase):
    def test_a_roll_moves_the_token(self):
        game = make_game(rolls=[(2, 2)])
        take_turn(game)
        self.assertEqual(game.current.position, 4)

    def test_the_roll_is_reported(self):
        game = make_game(rolls=[(2, 3)])
        take_turn(game)
        self.assertTrue(
            any("2 + 3 = 5" in line for line in game.log), game.log
        )

    def test_last_roll_is_readable_afterwards(self):
        game = make_game(rolls=[(6, 1)])
        take_turn(game)
        self.assertEqual(game.last_roll, (6, 1))
        self.assertEqual(game.last_total, 7)

    def test_passing_go_pays_the_salary(self):
        game = make_game(rolls=[(1, 3)])
        game.current.position = 38
        take_turn(game)
        self.assertEqual(game.current.position, 2)
        self.assertEqual(game.current.cash, 1500 + GO_SALARY)

    def test_landing_exactly_on_go_pays_the_salary(self):
        game = make_game(rolls=[(2, 3)])
        game.current.position = 35
        take_turn(game)
        self.assertEqual(game.current.position, 0)
        self.assertEqual(game.current.cash, 1500 + GO_SALARY)

    def test_not_passing_go_pays_nothing(self):
        game = make_game(rolls=[(2, 2)])
        take_turn(game)
        self.assertEqual(game.current.cash, 1500 - 200)  # Income Tax only

    def test_walking_backwards_never_pays_the_go_salary(self):
        """No Chance space sits near Go, so the walk is driven directly."""
        game = make_game()
        game.current.position = 2
        game._start_move(-3)
        game.update(0)
        self.assertEqual(game.current.position, BOARD_SIZE - 1)
        self.assertEqual(game.current.cash, 1500)

    def test_nearest_ahead_wraps_and_never_returns_where_you_stand(self):
        spaces = make_game().spaces
        self.assertEqual(nearest_ahead(spaces, 7, "railroad"), 15)
        self.assertEqual(nearest_ahead(spaces, 36, "railroad"), 5)
        self.assertEqual(nearest_ahead(spaces, 5, "railroad"), 15)
        self.assertEqual(nearest_ahead(spaces, 7, "utility"), 12)
        self.assertEqual(nearest_ahead(spaces, 22, "utility"), 28)

    def test_nearest_ahead_rejects_a_group_that_is_not_on_the_board(self):
        with self.assertRaises(ValueError):
            nearest_ahead(make_game().spaces, 0, "casino")


class DoublesTest(unittest.TestCase):
    def test_doubles_earn_another_turn_for_the_same_player(self):
        game = make_game(rolls=[(2, 2), (1, 2)])
        take_turn(game)
        self.assertEqual(game.current.doubles_streak, 1)
        game.end_turn()
        self.assertIs(game.current, game.players[0])
        self.assertIs(game.state, State.PLAYER_TURN_START)

    def test_a_plain_roll_passes_the_turn_on(self):
        game = make_game(rolls=[(2, 3)])
        game.current.position = 35  # lands on Go, nothing to resolve
        take_turn(game)
        game.end_turn()
        self.assertIs(game.current, game.players[1])

    def test_a_plain_roll_clears_the_streak(self):
        game = make_game(rolls=[(2, 2), (1, 2)])
        take_turn(game)
        game.end_turn()
        take_turn(game)  # 1 + 2, not doubles
        self.assertEqual(game.players[0].doubles_streak, 0)

    def test_three_doubles_go_to_jail(self):
        game = make_game(rolls=[(2, 2), (2, 2), (2, 2)])
        take_turn(game)  # -> 4, Income Tax
        game.end_turn()
        take_turn(game)  # -> 8, Vermont Avenue
        answer(game, AUCTION_KEY)
        game.end_turn()
        take_turn(game)  # third double
        player = game.players[0]
        self.assertTrue(player.in_jail)
        self.assertEqual(player.position, JAIL_INDEX)
        self.assertEqual(player.doubles_streak, 0)
        self.assertIn("Jail", game.message)

    def test_three_doubles_skip_the_landing_and_end_the_turn(self):
        game = make_game(rolls=[(2, 2), (2, 2), (2, 2)])
        take_turn(game)
        game.end_turn()
        take_turn(game)
        answer(game, AUCTION_KEY)
        game.end_turn()
        take_turn(game)
        self.assertIs(game.state, State.PLAYER_ACTIONS)
        game.end_turn()
        self.assertIs(game.current, game.players[1], "no extra turn from the third")


class JailTest(unittest.TestCase):
    """The roll-for-doubles branch, which Phase 7 had to implement early.

    Phase 8 put the three ways out behind a ``PROMPT_JAIL``, so a jailed turn
    now opens on a prompt rather than on a live Roll button; these tests answer
    it with "Roll for Doubles" and otherwise check what they always did.
    :mod:`tests.test_jail` covers the other two answers.
    """

    def jailed_game(self, rolls) -> Game:
        game = make_game(rolls=rolls)
        game._go_to_jail(game.current)
        game._begin_turn()
        return game

    def jail_roll(self, game: Game) -> None:
        """Answer the open jail prompt with "Roll for Doubles"."""
        answer(game, ROLL_KEY)

    def test_the_go_to_jail_space_sends_you_there(self):
        game = make_game(rolls=[(2, 3)])
        game.current.position = 25
        take_turn(game)
        self.assertEqual(game.current.position, JAIL_INDEX)
        self.assertTrue(game.current.in_jail)

    def test_jail_is_not_the_same_as_visiting(self):
        game = make_game(rolls=[(5, 5), (1, 2)])
        game.current.position = 0
        take_turn(game)  # 0 -> 10, just visiting
        self.assertEqual(game.current.position, JAIL_INDEX)
        self.assertFalse(game.current.in_jail)

    def test_the_turn_opens_with_the_jail_count(self):
        game = self.jailed_game([(1, 2)])
        self.assertIn("Jail", game.message)
        self.assertEqual(game.available_actions(), frozenset())

    def test_doubles_release_the_player_and_move_them(self):
        game = self.jailed_game([(3, 3)])
        self.jail_roll(game)
        player = game.players[0]
        self.assertFalse(player.in_jail)
        self.assertEqual(player.position, JAIL_INDEX + 6)

    def test_doubles_out_of_jail_do_not_earn_another_turn(self):
        game = self.jailed_game([(3, 3)])
        self.jail_roll(game)
        answer(game, AUCTION_KEY)  # St. James Place is for sale
        game.end_turn()
        self.assertIs(game.current, game.players[1])

    def test_a_failed_roll_keeps_the_player_put(self):
        game = self.jailed_game([(1, 2)])
        self.jail_roll(game)
        player = game.players[0]
        self.assertTrue(player.in_jail)
        self.assertEqual(player.position, JAIL_INDEX)
        self.assertEqual(player.jail_turns, 1)
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    def test_two_failed_rolls_leave_the_player_in_jail(self):
        game = self.jailed_game([(1, 2), (1, 2)])
        self.jail_roll(game)
        game.end_turn()
        game.seat = 0
        game._begin_turn()
        self.jail_roll(game)
        self.assertTrue(game.players[0].in_jail)
        self.assertEqual(game.players[0].jail_turns, 2)

    def test_the_third_failure_forces_the_fine_and_moves(self):
        game = self.jailed_game([(1, 2), (1, 2), (1, 2)])
        for _ in range(3):
            game.seat = 0
            game._begin_turn()
            self.jail_roll(game)
        player = game.players[0]
        self.assertFalse(player.in_jail)
        self.assertEqual(player.jail_turns, 0)
        self.assertEqual(player.cash, 1500 - JAIL_FINE)
        self.assertEqual(player.position, JAIL_INDEX + 3)

    def test_going_to_jail_wipes_the_doubles_streak(self):
        game = make_game(rolls=[(2, 3)])
        game.current.position = 25
        game.current.doubles_streak = 2
        take_turn(game)
        self.assertEqual(game.current.doubles_streak, 0)


class BuyTest(unittest.TestCase):
    def landed_on_baltic(self, cash: int = 1500) -> Game:
        game = make_game(rolls=[(1, 2)], cash=cash)
        take_turn(game)
        return game

    def test_an_unowned_deed_prompts(self):
        game = self.landed_on_baltic()
        prompt = game.prompt
        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.kind, PROMPT_BUY)
        self.assertIs(prompt.deed, game.deed(3))
        self.assertEqual([o.key for o in prompt.options], [BUY_KEY, AUCTION_KEY])

    def test_buying_takes_the_cash_and_hands_over_the_deed(self):
        game = self.landed_on_baltic()
        answer(game, BUY_KEY)
        deed = game.deed(3)
        self.assertIs(deed.owner, game.players[0])
        self.assertIn(deed, game.players[0].properties)
        self.assertEqual(game.players[0].cash, 1500 - 60)
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    def test_the_buy_button_is_disabled_when_the_cash_is_short(self):
        game = self.landed_on_baltic(cash=59)
        buy = game.prompt.options[0]
        self.assertFalse(buy.enabled)
        with self.assertRaises(ValueError):
            game.choose(BUY_KEY)

    def test_declining_leaves_the_deed_unowned(self):
        game = self.landed_on_baltic()
        answer(game, AUCTION_KEY)
        self.assertIsNone(game.deed(3).owner)
        self.assertEqual(game.players[0].cash, 1500)

    def test_declining_calls_the_auction_hook(self):
        game = self.landed_on_baltic()
        seen = []
        game.on_auction = lambda g, deed: seen.append(deed)
        answer(game, AUCTION_KEY)
        self.assertEqual(seen, [game.deed(3)])

    def test_an_unknown_choice_raises(self):
        game = self.landed_on_baltic()
        with self.assertRaises(ValueError):
            game.choose("nope")

    def test_choosing_with_no_prompt_raises(self):
        with self.assertRaises(RuntimeError):
            make_game().choose(OK_KEY)

    def test_landing_on_your_own_deed_costs_nothing(self):
        game = make_game(rolls=[(1, 2)])
        game.current.add_property(game.deed(3))
        take_turn(game)
        self.assertIsNone(game.prompt)
        self.assertEqual(game.current.cash, 1500)
        self.assertIn("already owns", game.message)
        self.assertIs(game.state, State.PLAYER_ACTIONS)


class RentTest(unittest.TestCase):
    def game_where_bob_owns(self, index: int, rolls) -> Game:
        game = make_game(rolls=rolls)
        deed = game.deed(index)
        game.players[1].add_property(deed)
        return game

    def test_rent_moves_from_tenant_to_owner(self):
        game = self.game_where_bob_owns(3, [(1, 2)])
        take_turn(game)
        self.assertEqual(game.players[0].cash, 1500 - 4)
        self.assertEqual(game.players[1].cash, 1500 + 4)
        self.assertIn("rent", game.message)

    def test_a_monopoly_doubles_the_base_rent(self):
        game = self.game_where_bob_owns(3, [(1, 2)])
        game.players[1].add_property(game.deed(1))
        take_turn(game)
        self.assertEqual(game.players[0].cash, 1500 - 8)

    def test_a_mortgaged_deed_collects_nothing(self):
        game = self.game_where_bob_owns(3, [(1, 2)])
        game.deed(3).mortgaged = True
        take_turn(game)
        self.assertEqual(game.players[0].cash, 1500)
        self.assertIn("mortgaged", game.message)

    def test_railroad_rent_scales_with_the_holding(self):
        game = self.game_where_bob_owns(5, [(2, 3)])
        game.players[1].add_property(game.deed(15))
        take_turn(game)
        self.assertEqual(game.players[0].cash, 1500 - 50)

    def test_utility_rent_multiplies_the_roll_that_brought_you(self):
        game = self.game_where_bob_owns(12, [(3, 4)])
        game.current.position = 5
        take_turn(game)
        self.assertEqual(game.current.position, 12)
        self.assertEqual(game.players[0].cash, 1500 - 4 * 7)

    def test_both_utilities_charge_ten_times_the_roll(self):
        game = self.game_where_bob_owns(12, [(3, 4)])
        game.players[1].add_property(game.deed(28))
        game.current.position = 5
        take_turn(game)
        self.assertEqual(game.players[0].cash, 1500 - 10 * 7)

    def test_houses_raise_the_rent(self):
        game = self.game_where_bob_owns(3, [(1, 2)])
        game.players[1].add_property(game.deed(1))
        game.deed(3).houses = 2
        take_turn(game)
        self.assertEqual(game.players[0].cash, 1500 - 60)


class TaxAndCornersTest(unittest.TestCase):
    def test_income_tax(self):
        game = make_game(rolls=[(2, 2)])
        take_turn(game)
        self.assertEqual(game.current.cash, 1500 - 200)

    def test_luxury_tax(self):
        game = make_game(rolls=[(1, 2)])
        game.current.position = 35
        take_turn(game)
        self.assertEqual(game.current.position, 38)
        self.assertEqual(game.current.cash, 1500 - 100)

    def test_free_parking_does_nothing(self):
        game = make_game(rolls=[(4, 6)])
        game.current.position = 10
        take_turn(game)
        self.assertEqual(game.current.position, 20)
        self.assertEqual(game.current.cash, 1500)
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    def test_landing_on_go_is_announced(self):
        game = make_game(rolls=[(2, 3)])
        game.current.position = 35
        take_turn(game)
        self.assertIn("Go", game.message)


class CardTest(unittest.TestCase):
    """Cards are driven by stacking a one-card deck under a Chance space."""

    def game_drawing(self, card: dict, *, rolls=((3, 4),), deck="chance", **kwargs):
        """A game whose ``deck`` holds only ``card``, rolled onto that space."""
        game = make_game(rolls=list(rolls), **{deck: one_card_deck(card)}, **kwargs)
        take_turn(game)
        return game

    def test_a_chance_space_prompts_with_the_card(self):
        game = self.game_drawing({"text": "Nice.", "action": "collect", "amount": 50})
        self.assertEqual(game.current.position, 7)
        self.assertEqual(game.prompt.kind, PROMPT_CARD)
        self.assertEqual(game.prompt.title, "Chance")
        self.assertEqual(game.prompt.text, "Nice.")
        self.assertEqual([o.key for o in game.prompt.options], [OK_KEY])

    def test_a_community_chest_space_prompts_too(self):
        game = self.game_drawing(
            {"text": "Chest.", "action": "collect", "amount": 5},
            rolls=((1, 1),),
            deck="community_chest",
        )
        self.assertEqual(game.current.position, 2)
        self.assertEqual(game.prompt.title, "Community Chest")

    def test_collect(self):
        game = self.game_drawing({"text": "", "action": "collect", "amount": 150})
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].cash, 1500 + 150)
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    def test_pay(self):
        game = self.game_drawing({"text": "", "action": "pay", "amount": 15})
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].cash, 1500 - 15)

    def test_move_to_go_collects_the_salary(self):
        game = self.game_drawing(
            {"text": "", "action": "move_to", "destination": 0, "collect_go": True}
        )
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].position, 0)
        self.assertEqual(game.players[0].cash, 1500 + GO_SALARY)

    def test_move_to_without_collect_go_pays_nothing(self):
        game = self.game_drawing(
            {"text": "", "action": "move_to", "destination": 39, "collect_go": False}
        )
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].position, 39)
        self.assertEqual(game.players[0].cash, 1500)
        self.assertEqual(game.prompt.kind, PROMPT_BUY, "Boardwalk is for sale")

    def test_move_relative_goes_backwards(self):
        deck = one_card_deck(
            {"text": "", "action": "move_relative", "offset": -3, "collect_go": False}
        )
        chest = one_card_deck({"text": "Chest.", "action": "collect", "amount": 0})
        game = make_game(rolls=[(1, 2)], chance=deck, community_chest=chest)
        game.current.position = 33
        take_turn(game)  # -> 36, Chance
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].position, 33)


    def test_a_card_can_land_you_on_another_card_space(self):
        chance = one_card_deck(
            {"text": "Back 3.", "action": "move_relative", "offset": -3}
        )
        chest = one_card_deck({"text": "Chest.", "action": "collect", "amount": 7})
        game = make_game(rolls=[(3, 3)], chance=chance, community_chest=chest)
        game.current.position = 30
        take_turn(game)  # -> 36, Chance
        self.assertEqual(game.prompt.title, "Chance")
        answer(game, OK_KEY)  # back 3 -> 33, Community Chest
        self.assertEqual(game.players[0].position, 33)
        self.assertEqual(game.prompt.title, "Community Chest")
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].cash, 1507)

    def test_go_to_jail_card(self):
        game = self.game_drawing({"text": "", "action": "go_to_jail"})
        answer(game, OK_KEY)
        self.assertTrue(game.players[0].in_jail)
        self.assertEqual(game.players[0].position, JAIL_INDEX)

    def test_get_out_of_jail_card_is_kept(self):
        deck = one_card_deck({"text": "GOOJF", "action": "get_out_of_jail"})
        game = make_game(rolls=[(3, 4)], chance=deck)
        take_turn(game)
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].goojf_cards, 1)
        self.assertEqual(len(deck), 0)
        self.assertEqual(len(deck.held), 1)

    def test_a_kept_card_goes_back_under_its_own_deck(self):
        deck = one_card_deck({"text": "GOOJF", "action": "get_out_of_jail"})
        game = make_game(rolls=[(3, 4)], chance=deck)
        take_turn(game)
        answer(game, OK_KEY)
        self.assertTrue(game.return_goojf(game.players[0]))
        self.assertEqual(game.players[0].goojf_cards, 0)
        self.assertEqual(len(deck), 1)

    def test_returning_a_card_nobody_holds_reports_false(self):
        game = make_game()
        self.assertFalse(game.return_goojf(game.players[0]))

    def test_pay_per_building(self):
        game = self.game_drawing(
            {
                "text": "",
                "action": "pay_per_building",
                "per_house": 25,
                "per_hotel": 100,
            }
        )
        player = game.players[0]
        player.add_property(game.deed(1))
        player.add_property(game.deed(3))
        game.deed(1).houses = 3
        game.deed(3).has_hotel = True
        answer(game, OK_KEY)
        self.assertEqual(player.cash, 1500 - (3 * 25 + 100))

    def test_pay_per_building_with_nothing_built_costs_nothing(self):
        game = self.game_drawing(
            {"text": "", "action": "pay_per_building", "per_house": 25, "per_hotel": 100}
        )
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].cash, 1500)

    def test_collect_from_players(self):
        game = self.game_drawing(
            {"text": "", "action": "collect_from_players", "amount": 10},
            names=("Ada", "Bob", "Cal"),
        )
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].cash, 1500 + 20)
        self.assertEqual(game.players[1].cash, 1490)
        self.assertEqual(game.players[2].cash, 1490)

    def test_pay_to_players(self):
        game = self.game_drawing(
            {"text": "", "action": "pay_to_players", "amount": 50},
            names=("Ada", "Bob", "Cal"),
        )
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].cash, 1500 - 100)
        self.assertEqual(game.players[1].cash, 1550)

    def test_a_bankrupt_player_neither_pays_nor_collects(self):
        game = self.game_drawing(
            {"text": "", "action": "collect_from_players", "amount": 10},
            names=("Ada", "Bob", "Cal"),
        )
        game.players[2].is_bankrupt = True
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].cash, 1510)
        self.assertEqual(game.players[2].cash, 1500)


class NearestCardTest(unittest.TestCase):
    """The ``move_to_nearest`` action the plan flagged for this phase."""

    def test_nearest_railroad_is_ahead_of_you(self):
        deck = one_card_deck(
            {
                "text": "",
                "action": "move_to_nearest",
                "group": "railroad",
                "collect_go": True,
                "rent_multiplier": 2,
            }
        )
        game = make_game(rolls=[(3, 4)], chance=deck)
        take_turn(game)  # -> 7, Chance
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].position, 15)

    def test_nearest_railroad_charges_double_rent(self):
        deck = one_card_deck(
            {
                "text": "",
                "action": "move_to_nearest",
                "group": "railroad",
                "rent_multiplier": 2,
            }
        )
        game = make_game(rolls=[(3, 4)], chance=deck)
        game.players[1].add_property(game.deed(15))
        take_turn(game)
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].cash, 1500 - 2 * 25)
        self.assertEqual(game.players[1].cash, 1500 + 2 * 25)

    def test_an_unowned_nearest_railroad_is_still_for_sale(self):
        deck = one_card_deck(
            {"text": "", "action": "move_to_nearest", "group": "railroad"}
        )
        game = make_game(rolls=[(3, 4)], chance=deck)
        take_turn(game)
        answer(game, OK_KEY)
        self.assertEqual(game.prompt.kind, PROMPT_BUY)
        self.assertIs(game.prompt.deed, game.deed(15))

    def test_nearest_utility_throws_again_and_pays_ten_times(self):
        deck = one_card_deck(
            {
                "text": "",
                "action": "move_to_nearest",
                "group": "utility",
                "roll_multiplier": 10,
            }
        )
        # The first pair moves Ada to Chance; the second is the extra throw the
        # card calls for.
        game = make_game(rolls=[(3, 4), (6, 2)], chance=deck)
        game.players[1].add_property(game.deed(12))
        take_turn(game)
        answer(game, OK_KEY)
        self.assertEqual(game.players[0].position, 12)
        self.assertEqual(game.players[0].cash, 1500 - 10 * 8)

    def test_the_multiplier_does_not_leak_into_the_next_landing(self):
        deck = one_card_deck(
            {
                "text": "",
                "action": "move_to_nearest",
                "group": "railroad",
                "rent_multiplier": 2,
            }
        )
        game = make_game(rolls=[(3, 4), (1, 2)], chance=deck)
        game.players[1].add_property(game.deed(15))
        game.players[1].add_property(game.deed(18))
        take_turn(game)
        answer(game, OK_KEY)
        game.end_turn()
        game.seat = 0
        game._begin_turn()
        take_turn(game)  # 15 -> 18, Tennessee Avenue at plain rent
        self.assertEqual(game.players[0].cash, 1500 - 50 - 14)


class TurnOrderTest(unittest.TestCase):
    #: 4 + 6 from Go is "just visiting" -- a plain roll with nothing to resolve.
    QUIET_ROLL = (4, 6)

    def test_the_seat_advances(self):
        game = make_game(rolls=[self.QUIET_ROLL], names=("Ada", "Bob", "Cal"))
        take_turn(game)
        game.end_turn()
        self.assertIs(game.current, game.players[1])

    def test_bankrupt_seats_are_skipped(self):
        game = make_game(rolls=[self.QUIET_ROLL], names=("Ada", "Bob", "Cal"))
        game.players[1].is_bankrupt = True
        take_turn(game)
        game.end_turn()
        self.assertIs(game.current, game.players[2])

    def test_the_last_player_standing_wins(self):
        game = make_game(rolls=[self.QUIET_ROLL])
        game.players[1].is_bankrupt = True
        take_turn(game)
        game.end_turn()
        self.assertIs(game.state, State.GAME_OVER)
        self.assertIs(game.winner, game.players[0])
        self.assertIn("wins", game.message)

    def test_nothing_is_available_once_the_game_is_over(self):
        game = make_game(rolls=[self.QUIET_ROLL])
        game.players[1].is_bankrupt = True
        take_turn(game)
        game.end_turn()
        self.assertEqual(game.available_actions(), frozenset())

    def test_a_new_turn_clears_the_previous_landing(self):
        game = make_game(rolls=[(1, 2), (2, 2)])
        take_turn(game)
        answer(game, AUCTION_KEY)
        game.end_turn()
        self.assertFalse(game.rolled)
        self.assertIsNone(game.prompt)
        self.assertIs(game.state, State.PLAYER_TURN_START)


class ShortfallTest(unittest.TestCase):
    """Taking what there is and recording the rest.

    Phase 7 stopped there; Phase 13 answers the debt on the spot, so these
    now check the handover itself and leave the settling to
    :mod:`tests.test_bankruptcy_game`. A registered ``on_shortfall`` still
    holds the answer open, which is how the first two look at a live
    :class:`Debt` at all.
    """

    @staticmethod
    def hold(game: Game) -> list[Debt]:
        """Register a hook that only records, so the debt stays outstanding."""
        seen: list[Debt] = []
        game.on_shortfall = lambda g, debt: seen.append(debt)
        return seen

    def test_a_debt_beyond_the_cash_empties_the_player(self):
        game = make_game(rolls=[(2, 2)], cash=50)  # Income Tax, $200
        self.hold(game)
        take_turn(game)
        self.assertEqual(game.current.cash, 0)
        self.assertIsInstance(game.debt, Debt)
        self.assertEqual(game.debt.amount, 150)
        self.assertIsNone(game.debt.creditor)

    def test_the_creditor_still_gets_what_there_was(self):
        game = make_game(rolls=[(1, 2)], cash=3)
        self.hold(game)
        game.players[1].add_property(game.deed(3))  # Baltic, $4 rent
        take_turn(game)
        self.assertEqual(game.players[0].cash, 0)
        self.assertEqual(game.players[1].cash, 3 + 3)
        self.assertEqual(game.debt.amount, 1)
        self.assertIs(game.debt.creditor, game.players[1])

    def test_the_shortfall_hook_is_called(self):
        game = make_game(rolls=[(2, 2)], cash=50)
        seen = []
        game.on_shortfall = lambda g, debt: seen.append(debt)
        take_turn(game)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0].amount, 150)

    def test_a_payment_that_fits_records_no_debt(self):
        game = make_game(rolls=[(2, 2)])
        take_turn(game)
        self.assertIsNone(game.debt)


class AnimationTest(unittest.TestCase):
    """With the animation on, one update is no longer one whole turn."""

    def animated_game(self, rolls) -> Game:
        faces = [f for pair in rolls for f in pair]
        rng = ScriptedRandom(faces)
        players = [Player("Ada", 1500, "red"), Player("Bob", 1500, "blue")]
        game = Game(
            players, dice=Dice(rng, roll_ms=400), rng=rng, step_ms=100
        )
        game.start()
        return game

    def test_the_dice_hold_the_game_in_rolling(self):
        game = self.animated_game([(2, 2)])
        game.perform(Action.ROLL, 0)
        game.update(100)
        self.assertIs(game.state, State.ROLLING)
        self.assertEqual(game.current.position, 0)
        game.update(400)
        self.assertIs(game.state, State.MOVING)

    def test_the_token_walks_one_space_per_step(self):
        game = self.animated_game([(2, 2)])
        game.perform(Action.ROLL, 0)
        game.update(400)  # the dice settle; the walk starts its first step
        self.assertEqual(game.current.position, 0)
        game.update(500)
        self.assertEqual(game.current.position, 1)
        game.update(550)
        self.assertEqual(game.current.position, 1, "too soon for the next")
        game.update(600)
        self.assertEqual(game.current.position, 2)

    def test_update_reports_whether_anything_happened(self):
        game = self.animated_game([(2, 2)])
        self.assertFalse(game.update(0), "nothing in flight")
        game.perform(Action.ROLL, 0)
        self.assertFalse(game.update(100), "still rolling")
        self.assertTrue(game.update(400))

    def test_the_walk_finishes_and_lands(self):
        game = self.animated_game([(2, 2)])
        game.perform(Action.ROLL, 0)
        for now in range(0, 1200, 50):
            game.update(400 + now)
        self.assertEqual(game.current.position, 4)
        self.assertIs(game.state, State.PLAYER_ACTIONS)
        self.assertEqual(game.current.cash, 1500 - 200)


class MessageTest(unittest.TestCase):
    def test_every_message_is_logged(self):
        game = make_game(rolls=[(2, 2)])
        take_turn(game)
        self.assertEqual(game.message, game.log[-1])
        self.assertGreater(len(game.log), 2)

    def test_the_log_is_capped(self):
        game = make_game()
        for i in range(400):
            game._say(f"line {i}")
        self.assertEqual(len(game.log), 200)
        self.assertEqual(game.log[-1], "line 399")


class PromptTest(unittest.TestCase):
    def test_an_enabled_choice_comes_back(self):
        prompt = Prompt(
            kind=PROMPT_BUY,
            title="Baltic Avenue",
            text="Buy it?",
            options=(Choice(BUY_KEY, "Buy $60"), Choice(AUCTION_KEY, "Auction")),
        )
        self.assertEqual(prompt.choice(BUY_KEY).label, "Buy $60")

    def test_a_disabled_choice_cannot_be_picked(self):
        prompt = Prompt(
            kind=PROMPT_BUY,
            title="Baltic Avenue",
            text="Buy it?",
            options=(Choice(BUY_KEY, "Buy $60", enabled=False),),
        )
        with self.assertRaises(ValueError):
            prompt.choice(BUY_KEY)

    def test_an_unknown_key_raises(self):
        prompt = Prompt(kind=PROMPT_CARD, title="t", text="t", options=())
        with self.assertRaises(ValueError):
            prompt.choice(OK_KEY)

    def test_an_info_prompt_just_hands_the_turn_back(self):
        """The seam a later phase uses for a plain "you have been told" box."""
        game = make_game(rolls=[(4, 6)])
        take_turn(game)
        game.prompt = Prompt(
            kind=PROMPT_INFO,
            title="Notice",
            text="Nothing happens.",
            options=(Choice(OK_KEY, "OK"),),
        )
        game.choose(OK_KEY)
        self.assertIsNone(game.prompt)
        self.assertIs(game.state, State.PLAYER_ACTIONS)


class FullGameTest(unittest.TestCase):
    """A long unattended game must never deadlock or leave the board."""

    def test_two_hundred_turns_of_seeded_play(self):
        rng = random.Random(2024)
        players = [Player(n, 1500, t) for n, t in zip("ABCD", TOKENS)]
        game = Game(players, dice=Dice(rng, roll_ms=0), rng=rng, step_ms=0)
        game.start()
        now = 0
        for _ in range(4000):
            now += 16
            game.update(now)
            if game.state is State.GAME_OVER:
                break
            if game.prompt is not None:
                keys = [o.key for o in game.prompt.options if o.enabled]
                # Buy whatever is offered, so the board really fills up.
                game.choose(BUY_KEY if BUY_KEY in keys else keys[0])
                continue
            actions = game.available_actions()
            if Action.ROLL in actions:
                game.perform(Action.ROLL, now)
            elif Action.END_TURN in actions:
                game.end_turn()
        for player in players:
            with self.subTest(player=player.name):
                self.assertTrue(0 <= player.position < BOARD_SIZE)
                self.assertGreaterEqual(player.cash, 0)
        owners = [d.owner for d in game.properties if d.owner is not None]
        for deed in game.properties:
            if deed.owner is not None:
                self.assertIn(deed, deed.owner.properties)
        self.assertTrue(owners, "a 4000-step game should have sold something")


if __name__ == "__main__":
    unittest.main()
