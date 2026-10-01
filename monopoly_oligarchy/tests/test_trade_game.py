"""Phase 11 tests: the trade's place in the turn loop.

``test_trade.py`` covers the deal on its own; this file covers how it joins
the game -- that the Trade button is live again, that the screen is modal
while it is open, that accepting really swaps the deeds and the cash, and that
a Get Out of Jail Free card carries its deck with it. The board is un-animated
exactly as in ``test_game.py``, and no pygame is imported.
"""

from __future__ import annotations

import random
import unittest

from monopoly.building import buildable_groups
from monopoly.game import OK_KEY, Action, Game, State
from monopoly.trade import ACCEPTED, CANCELLED, DRAFT, PARTNER, REJECTED, Trade

from tests.test_game import answer, make_game, one_card_deck, take_turn

#: Rolls used below, chosen for where they land the first player.
TAX = (1, 3)  # 0 -> 4, Income Tax: a landing with no deed and no prompt
BALTIC = (1, 2)  # 0 -> 3, Baltic Avenue, unowned
CHANCE = (3, 4)  # 0 -> 7, Chance

MEDITERRANEAN = 1
BALTIC_INDEX = 3
READING = 5
ORIENTAL = 6


def open_turn(**kwargs) -> Game:
    """A started game whose first player is mid-turn with nothing pending."""
    game = make_game(rolls=[TAX], **kwargs)
    take_turn(game)
    return game


def drafted(**kwargs) -> tuple[Game, Trade]:
    """An open trade with Baltic Avenue, Ada's, on the table."""
    game = open_turn(**kwargs)
    game.current.add_property(game.deed(BALTIC_INDEX))
    trade = game.open_trade()
    trade.add_deed(game.deed(BALTIC_INDEX))
    return game, trade


class ButtonTest(unittest.TestCase):
    def test_trade_is_live_once_the_landing_is_resolved(self):
        game = open_turn()
        self.assertIn(Action.TRADE, game.available_actions())

    def test_trade_is_not_offered_before_the_roll(self):
        game = make_game()
        self.assertNotIn(Action.TRADE, game.available_actions())

    def test_a_table_of_one_has_nobody_to_trade_with(self):
        game = make_game(rolls=[TAX], names=("Ada",))
        take_turn(game)
        self.assertFalse(game.can_trade())
        self.assertNotIn(Action.TRADE, game.available_actions())

    def test_a_bankrupt_seat_does_not_count_as_a_partner(self):
        game = open_turn()
        game.players[1].is_bankrupt = True
        self.assertFalse(game.can_trade())

    def test_pressing_trade_opens_the_screen(self):
        game = open_turn()
        self.assertTrue(game.perform(Action.TRADE))
        self.assertIsInstance(game.trade, Trade)

    def test_a_registered_handler_still_wins(self):
        game = open_turn()
        seen = []
        game.action_handlers[Action.TRADE] = seen.append
        self.assertTrue(game.perform(Action.TRADE))
        self.assertEqual(seen, [game])
        self.assertIsNone(game.trade)


class OpeningTest(unittest.TestCase):
    def setUp(self):
        self.game = open_turn()

    def test_the_player_on_turn_is_the_proposer(self):
        trade = self.game.open_trade()
        self.assertIs(trade.proposer, self.game.current)

    def test_a_two_handed_game_needs_no_partner_chosen(self):
        trade = self.game.open_trade()
        self.assertIs(trade.partner, self.game.players[1])
        self.assertEqual(trade.phase, DRAFT)

    def test_a_bigger_table_asks_who_first(self):
        game = make_game(rolls=[TAX], names=("Ada", "Bob", "Cleo"))
        take_turn(game)
        trade = game.open_trade()
        self.assertEqual(trade.phase, PARTNER)
        self.assertEqual([p.name for p in trade.candidates], ["Bob", "Cleo"])

    def test_a_partner_can_be_named_up_front(self):
        game = make_game(rolls=[TAX], names=("Ada", "Bob", "Cleo"))
        take_turn(game)
        trade = game.open_trade(game.players[2])
        self.assertIs(trade.partner, game.players[2])

    def test_a_bankrupt_seat_is_not_invited(self):
        game = make_game(rolls=[TAX], names=("Ada", "Bob", "Cleo"))
        take_turn(game)
        game.players[1].is_bankrupt = True
        trade = game.open_trade()
        self.assertEqual([p.name for p in trade.candidates], ["Cleo"])

    def test_the_whole_board_is_visible_to_the_deal(self):
        trade = self.game.open_trade()
        self.assertEqual(len(trade.properties), len(self.game.properties))

    def test_trading_before_the_roll_raises(self):
        game = make_game()
        with self.assertRaises(RuntimeError):
            game.open_trade()

    def test_two_trades_cannot_run_at_once(self):
        self.game.open_trade()
        with self.assertRaises(RuntimeError):
            self.game.open_trade()

    def test_a_trade_cannot_open_over_a_prompt(self):
        game = make_game(rolls=[BALTIC])
        take_turn(game)  # the buy prompt is up
        self.assertIsNotNone(game.prompt)
        with self.assertRaises(RuntimeError):
            game.open_trade()

    def test_a_trade_cannot_open_over_the_build_screen(self):
        game = open_turn()
        for index in (MEDITERRANEAN, BALTIC_INDEX):
            game.current.add_property(game.deed(index))
        game.open_build()
        with self.assertRaises(RuntimeError):
            game.open_trade()

    def test_a_trade_cannot_open_over_an_auction(self):
        game = open_turn()
        game.open_auction(game.deed(ORIENTAL))
        self.assertIsNotNone(game.auction)
        with self.assertRaises(RuntimeError):
            game.open_trade()


class ModalityTest(unittest.TestCase):
    """An open trade stops the turn moving on underneath it."""

    def setUp(self):
        self.game = open_turn()
        self.trade = self.game.open_trade()

    def test_no_action_is_available(self):
        self.assertEqual(self.game.available_actions(), frozenset())

    def test_the_turn_cannot_be_ended(self):
        self.assertFalse(self.game.perform(Action.END_TURN))
        self.assertIsNotNone(self.game.trade)

    def test_the_build_screen_cannot_be_opened(self):
        with self.assertRaises(RuntimeError):
            self.game.open_build()

    def test_an_auction_cannot_be_opened(self):
        with self.assertRaises(RuntimeError):
            self.game.open_auction(self.game.deed(ORIENTAL))

    def test_the_turn_is_still_where_it_was(self):
        self.assertIs(self.game.state, State.PLAYER_ACTIONS)

    def test_closing_it_gives_the_turn_back(self):
        self.game.close_trade()
        self.assertIn(Action.END_TURN, self.game.available_actions())
        self.assertIn(Action.TRADE, self.game.available_actions())

    def test_proposing_with_no_trade_open_raises(self):
        game = open_turn()
        with self.assertRaises(RuntimeError):
            game.propose_trade()

    def test_accepting_with_no_trade_open_raises(self):
        game = open_turn()
        with self.assertRaises(RuntimeError):
            game.accept_trade()

    def test_closing_with_no_trade_open_raises(self):
        game = open_turn()
        with self.assertRaises(RuntimeError):
            game.close_trade()


class ProposeTest(unittest.TestCase):
    def setUp(self):
        self.game, self.trade = drafted()

    def test_proposing_hands_the_offer_to_the_partner(self):
        self.assertTrue(self.game.propose_trade())
        self.assertEqual(self.trade.phase, "review")

    def test_the_offer_is_written_into_the_log(self):
        self.game.propose_trade()
        self.assertIn("Offer to Bob", self.game.log[-1])
        self.assertIn("Baltic Avenue", self.game.log[-1])

    def test_an_empty_offer_is_refused(self):
        game = open_turn()
        game.open_trade()
        self.assertFalse(game.propose_trade())
        self.assertIsNotNone(game.trade)

    def test_the_screen_stays_open_on_a_proposal(self):
        self.game.propose_trade()
        self.assertIs(self.game.trade, self.trade)
        self.assertEqual(self.game.available_actions(), frozenset())

    def test_nothing_has_moved_yet(self):
        self.game.propose_trade()
        self.assertIs(self.game.deed(BALTIC_INDEX).owner, self.game.players[0])


class AcceptTest(unittest.TestCase):
    def setUp(self):
        self.game, self.trade = drafted()
        self.ada, self.bob = self.game.players

    def test_accepting_swaps_the_deed_and_shuts_the_screen(self):
        self.game.propose_trade()
        self.assertTrue(self.game.accept_trade())
        self.assertIsNone(self.game.trade)
        self.assertIs(self.game.deed(BALTIC_INDEX).owner, self.bob)
        self.assertEqual(self.trade.result, ACCEPTED)

    def test_the_deal_is_written_into_the_log(self):
        self.game.propose_trade()
        self.game.accept_trade()
        self.assertIn("Trade agreed", self.game.log[-1])
        self.assertIn("Baltic Avenue", self.game.log[-1])

    def test_cash_moves_with_it(self):
        # Ada opened by paying $200 Income Tax, so she is on $1,300.
        self.trade.set_cash(self.bob, 200)
        self.game.propose_trade()
        self.game.accept_trade()
        self.assertEqual(self.bob.cash, 1300)
        self.assertEqual(self.ada.cash, 1500)

    def test_a_draft_cannot_be_accepted(self):
        self.assertFalse(self.game.accept_trade())
        self.assertIs(self.game.trade, self.trade, "the screen stays open")

    def test_the_turn_picks_up_afterwards(self):
        self.game.propose_trade()
        self.game.accept_trade()
        self.assertIs(self.game.state, State.PLAYER_ACTIONS)
        self.assertIn(Action.END_TURN, self.game.available_actions())

    def test_another_trade_may_follow(self):
        self.game.propose_trade()
        self.game.accept_trade()
        self.assertTrue(self.game.perform(Action.TRADE))

    def test_a_completed_group_becomes_buildable(self):
        self.bob.add_property(self.game.deed(MEDITERRANEAN))
        self.assertEqual(buildable_groups(self.bob, self.game.properties), [])
        self.game.propose_trade()
        self.game.accept_trade()
        self.assertTrue(self.bob.has_monopoly("brown", self.game.properties))
        self.assertEqual(
            buildable_groups(self.bob, self.game.properties), ["brown"]
        )


class CloseTest(unittest.TestCase):
    def setUp(self):
        self.game, self.trade = drafted()

    def test_cancelling_a_draft_moves_nothing(self):
        self.game.close_trade()
        self.assertIsNone(self.game.trade)
        self.assertEqual(self.trade.result, CANCELLED)
        self.assertIs(self.game.deed(BALTIC_INDEX).owner, self.game.players[0])

    def test_cancelling_is_written_into_the_log(self):
        self.game.close_trade()
        self.assertIn("calls the trade off", self.game.log[-1])

    def test_rejecting_an_offer_moves_nothing(self):
        self.game.propose_trade()
        self.game.close_trade(rejected=True)
        self.assertIsNone(self.game.trade)
        self.assertEqual(self.trade.result, REJECTED)
        self.assertIs(self.game.deed(BALTIC_INDEX).owner, self.game.players[0])

    def test_rejecting_is_written_into_the_log(self):
        self.game.propose_trade()
        self.game.close_trade(rejected=True)
        self.assertIn("Bob turns the offer down", self.game.log[-1])

    def test_rejecting_a_draft_falls_back_to_cancelling(self):
        self.game.close_trade(rejected=True)
        self.assertEqual(self.trade.result, CANCELLED)

    def test_a_new_turn_clears_any_screen_left_open(self):
        self.game.close_trade()
        self.game.end_turn()
        self.assertIsNone(self.game.trade)


class JailCardTest(unittest.TestCase):
    """A traded Get Out of Jail Free card keeps its deck with it."""

    def setUp(self):
        self.deck = one_card_deck(
            {"text": "Get Out of Jail Free.", "action": "get_out_of_jail"}
        )
        self.game = make_game(rolls=[CHANCE], chance=self.deck)
        take_turn(self.game)
        answer(self.game, OK_KEY)  # Ada keeps the card
        self.ada, self.bob = self.game.players

    def trade_the_card(self) -> None:
        trade = self.game.open_trade()
        trade.set_goojf(self.ada, 1)
        self.game.propose_trade()
        self.game.accept_trade()

    def test_the_card_is_ada_s_to_start_with(self):
        self.assertEqual(self.ada.goojf_cards, 1)
        self.assertEqual(self.bob.goojf_cards, 0)

    def test_trading_it_moves_the_count(self):
        self.trade_the_card()
        self.assertEqual(self.ada.goojf_cards, 0)
        self.assertEqual(self.bob.goojf_cards, 1)

    def test_the_new_owner_can_play_it(self):
        self.trade_the_card()
        self.assertTrue(self.game.return_goojf(self.bob))
        self.assertEqual(self.bob.goojf_cards, 0)

    def test_the_old_owner_cannot(self):
        self.trade_the_card()
        self.assertFalse(self.game.return_goojf(self.ada))

    def test_playing_it_puts_it_back_under_its_own_deck(self):
        self.trade_the_card()
        before = len(self.deck.cards)
        self.game.return_goojf(self.bob)
        self.assertEqual(len(self.deck.cards), before + 1)

    def test_transfer_moves_no_more_than_are_held(self):
        moved = self.game.transfer_goojf(self.ada, self.bob, 5)
        self.assertEqual(moved, 1)
        self.assertEqual(self.bob.goojf_cards, 1)

    def test_transfer_from_an_empty_hand_moves_nothing(self):
        self.assertEqual(self.game.transfer_goojf(self.bob, self.ada, 1), 0)
        self.assertEqual(self.ada.goojf_cards, 1)

    def test_only_the_asked_for_number_moves(self):
        self.assertEqual(self.game.transfer_goojf(self.ada, self.bob, 0), 0)
        self.assertEqual(self.ada.goojf_cards, 1)


class BuildingsBlockTradingTest(unittest.TestCase):
    """The standard rule: sell the group's buildings before trading its lots."""

    def setUp(self):
        self.game = open_turn()
        self.ada = self.game.players[0]
        for index in (MEDITERRANEAN, BALTIC_INDEX):
            self.ada.add_property(self.game.deed(index))

    def test_a_bare_group_trades(self):
        trade = self.game.open_trade()
        self.assertTrue(trade.add_deed(self.game.deed(BALTIC_INDEX)))

    def test_a_house_anywhere_in_the_group_stops_it(self):
        plan = self.game.open_build()
        plan.add(self.game.deed(MEDITERRANEAN))
        self.game.close_build(commit=True)
        trade = self.game.open_trade()
        self.assertFalse(trade.add_deed(self.game.deed(BALTIC_INDEX)))
        self.assertFalse(trade.add_deed(self.game.deed(MEDITERRANEAN)))

    def test_selling_the_house_frees_the_group_again(self):
        plan = self.game.open_build()
        plan.add(self.game.deed(MEDITERRANEAN))
        self.game.close_build(commit=True)
        plan = self.game.open_build()
        plan.remove(self.game.deed(MEDITERRANEAN))
        self.game.close_build(commit=True)
        trade = self.game.open_trade()
        self.assertTrue(trade.add_deed(self.game.deed(BALTIC_INDEX)))

    def test_another_group_is_unaffected(self):
        self.ada.add_property(self.game.deed(READING))
        plan = self.game.open_build()
        plan.add(self.game.deed(MEDITERRANEAN))
        self.game.close_build(commit=True)
        trade = self.game.open_trade()
        self.assertTrue(trade.add_deed(self.game.deed(READING)))


class WholeTurnTest(unittest.TestCase):
    """A trade struck mid-turn, then the turn played out to its end."""

    def test_a_deal_and_then_an_ordinary_end_of_turn(self):
        game = make_game(rolls=[TAX, TAX])
        take_turn(game)
        ada, bob = game.players
        ada.add_property(game.deed(BALTIC_INDEX))
        bob.add_property(game.deed(ORIENTAL))

        trade = game.open_trade()
        trade.add_deed(game.deed(BALTIC_INDEX))
        trade.add_deed(game.deed(ORIENTAL))
        trade.set_cash(ada, 50)
        self.assertTrue(game.propose_trade())
        self.assertTrue(game.accept_trade())

        self.assertIs(game.deed(BALTIC_INDEX).owner, bob)
        self.assertIs(game.deed(ORIENTAL).owner, ada)
        # Ada opened by paying $200 Income Tax, then $50 across the table.
        self.assertEqual(ada.cash, 1250)
        self.assertEqual(bob.cash, 1550)

        game.end_turn()
        self.assertIs(game.current, bob)
        self.assertIsNone(game.trade)

    def test_every_deed_still_has_at_most_one_owner(self):
        game = make_game(rolls=[TAX])
        take_turn(game)
        ada, bob = game.players
        for index in (MEDITERRANEAN, BALTIC_INDEX, READING):
            ada.add_property(game.deed(index))
        trade = game.open_trade()
        for index in (MEDITERRANEAN, READING):
            trade.add_deed(game.deed(index))
        game.propose_trade()
        game.accept_trade()

        for deed in game.properties:
            holders = [p for p in game.players if deed in p.properties]
            self.assertLessEqual(len(holders), 1)
            if deed.owner is not None:
                self.assertEqual(holders, [deed.owner])
        self.assertEqual(
            sorted(d.index for d in bob.properties), [MEDITERRANEAN, READING]
        )
        self.assertEqual([d.index for d in ada.properties], [BALTIC_INDEX])


class WholeGameTest(unittest.TestCase):
    """Three hands play 300 turns, trading whatever the dice leave them.

    The point is not any one deal but that trading holds up wherever it turns
    up in a real turn: every deed is either the bank's or in exactly one
    hand, nobody ever overdraws, the table's total cash is untouched by a
    swap, and the jail cards the deck handed out are all still accounted for.
    """

    TURNS = 300

    def check_invariants(self, game: Game) -> None:
        for player in game.players:
            self.assertGreaterEqual(player.cash, 0, f"{player.name} overdrew")
            self.assertGreaterEqual(player.goojf_cards, 0)
        for deed in game.properties:
            holders = [p for p in game.players if deed in p.properties]
            if deed.owner is None:
                self.assertEqual(holders, [], f"{deed.name} is held by a ghost")
            else:
                self.assertEqual(
                    [deed.owner], holders, f"{deed.name} is in the wrong hand"
                )
        trade = game.trade
        if trade is not None:
            self.assertTrue(trade.open, "a closed deal is taken off the table")
            for side in trade.sides:
                self.assertLessEqual(side.cash, side.player.cash)
                self.assertLessEqual(side.goojf, side.player.goojf_cards)
                for deed in side.deeds:
                    self.assertIs(deed.owner, side.player)

    def draft(self, game: Game, rng: random.Random) -> None:
        """Put a random but legal offer together for whoever is proposing."""
        trade = game.trade
        for side in trade.sides:
            player = side.player
            for deed in trade.tradable(player):
                if rng.random() < 0.3:
                    self.assertTrue(trade.add_deed(deed))
            if player.cash and rng.random() < 0.4:
                self.assertTrue(trade.set_cash(player, rng.randint(1, player.cash)))
            if player.goojf_cards and rng.random() < 0.5:
                self.assertTrue(trade.set_goojf(player, 1))

    def settle(self, game: Game, rng: random.Random, stats: dict) -> None:
        """Accept the offer on the table, checking the books balance."""
        trade = game.trade
        cash_before = sum(p.cash for p in game.players)
        cards_before = sum(p.goojf_cards for p in game.players)
        moving = [(deed, deed.owner) for side in trade.sides for deed in side.deeds]
        if not game.accept_trade():
            game.close_trade(rejected=True)
            return
        stats["accepted"] += 1
        self.assertEqual(
            sum(p.cash for p in game.players),
            cash_before,
            "cash crossed the table rather than appearing or vanishing",
        )
        self.assertEqual(sum(p.goojf_cards for p in game.players), cards_before)
        for deed, was in moving:
            self.assertIsNot(deed.owner, was, f"{deed.name} did not change hands")
            stats["deeds"] += 1

    def play(self, seed: int, trade_chance: float) -> Game:
        rng = random.Random(seed)
        game = make_game(cash=1500, names=("Ada", "Bob", "Cleo"))
        stats = {"opened": 0, "proposed": 0, "accepted": 0, "deeds": 0}
        steps = 0
        turns = 0
        offered = False
        while turns < self.TURNS and game.state is not State.GAME_OVER:
            steps += 1
            self.assertLess(steps, 200 * self.TURNS, "the turn loop is spinning")
            game.update(0)
            self.check_invariants(game)

            if game.auction is not None:
                game.pass_bid()  # sales are test_auction_game.py's business
                continue

            if game.trade is not None:
                trade = game.trade
                if trade.phase == PARTNER:
                    self.assertTrue(
                        trade.choose_partner(rng.choice(trade.candidates))
                    )
                elif trade.phase == DRAFT:
                    self.draft(game, rng)
                    if game.propose_trade():
                        stats["proposed"] += 1
                    else:
                        game.close_trade()
                else:
                    self.settle(game, rng, stats)
                continue

            if game.prompt is not None:
                options = [c.key for c in game.prompt.options if c.enabled]
                game.choose(rng.choice(options))
                continue

            actions = game.available_actions()
            if Action.ROLL in actions:
                offered = False
                game.perform(Action.ROLL)
            elif (
                not offered
                and Action.TRADE in actions
                and rng.random() < trade_chance
            ):
                offered = True
                stats["opened"] += 1
                game.perform(Action.TRADE)
            elif Action.END_TURN in actions:
                game.perform(Action.END_TURN)
                turns += 1
            else:
                self.fail(f"stuck in {game.state.value} with nothing to do")

        self.check_invariants(game)
        self.stats = stats
        return game

    def test_a_table_that_always_trades_never_breaks_the_rules(self):
        self.play(seed=3, trade_chance=1.0)
        self.assertGreater(self.stats["opened"], 0, "no trade was ever opened")
        self.assertGreater(self.stats["accepted"], 0, "no deal was ever struck")
        self.assertGreater(self.stats["deeds"], 0, "no deed ever changed hands")

    def test_a_table_that_never_trades_never_breaks_the_rules(self):
        self.play(seed=13, trade_chance=0.0)
        self.assertEqual(self.stats["opened"], 0)

    def test_a_table_that_trades_at_random_never_breaks_the_rules(self):
        game = self.play(seed=57, trade_chance=0.5)
        self.assertGreater(self.stats["opened"], 0)
        owned = [d for d in game.properties if d.owner is not None]
        self.assertGreater(len(owned), 0)

    def test_the_table_s_cash_is_only_ever_moved_around_by_a_trade(self):
        """Every deed is somewhere sensible once the dust settles."""
        game = self.play(seed=21, trade_chance=0.7)
        for player in game.players:
            for deed in player.properties:
                self.assertIs(deed.owner, player)
        self.assertEqual(
            len({id(d) for p in game.players for d in p.properties}),
            sum(len(p.properties) for p in game.players),
            "no deed is in two hands at once",
        )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
