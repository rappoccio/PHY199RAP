"""Phase 10 tests: the auction's place in the turn loop.

``test_auction.py`` covers the sale on its own; this file covers how it joins
the game -- that declining a deed really opens one, that the sale is modal
while it runs, that the winner pays the bank and takes the deed, and that the
turn picks up again afterwards. The board is un-animated exactly as in
``test_game.py``, and no pygame is imported.
"""

from __future__ import annotations

import random
import unittest

from monopoly.auction import Auction
from monopoly.game import AUCTION_KEY, BUY_KEY, Action, Game, State

from tests.test_game import make_game, take_turn

#: Rolls used below, chosen for where they land the first player.
BALTIC = (1, 2)  # 0 -> 3, Baltic Avenue, $60 and unowned
TAX = (1, 3)  # 0 -> 4, Income Tax: a landing with no deed and no prompt


def declined(rolls=(BALTIC,), **kwargs) -> Game:
    """A game whose first player has just passed on Baltic Avenue."""
    game = make_game(rolls=list(rolls), **kwargs)
    take_turn(game)
    game.choose(AUCTION_KEY)
    game.update(0)
    return game


def pass_everyone(game: Game) -> None:
    """Let the open sale die of disinterest."""
    while game.auction is not None:
        game.pass_bid()


class OpeningTest(unittest.TestCase):
    def setUp(self):
        self.game = declined()

    def test_declining_puts_the_deed_under_the_hammer(self):
        self.assertIsInstance(self.game.auction, Auction)
        self.assertIs(self.game.auction.deed, self.game.deed(3))

    def test_the_deed_is_still_the_bank_s_while_it_runs(self):
        self.assertIsNone(self.game.deed(3).owner)

    def test_the_player_who_declined_bids_first(self):
        self.assertIs(self.game.auction.bidder, self.game.players[0])

    def test_everybody_is_in_the_room(self):
        self.assertEqual(self.game.auction.bidders, self.game.players)

    def test_the_sale_starts_from_whoever_is_on_turn(self):
        game = make_game(rolls=[TAX, BALTIC], names=("Ada", "Bob", "Cleo"))
        take_turn(game)
        game.end_turn()  # Ada is done; Bob is up
        take_turn(game)
        game.choose(AUCTION_KEY)
        self.assertEqual(
            [p.name for p in game.auction.bidders], ["Bob", "Cleo", "Ada"]
        )

    def test_a_bankrupt_seat_is_not_invited(self):
        game = make_game(rolls=[BALTIC], names=("Ada", "Bob", "Cleo"))
        game.players[1].is_bankrupt = True
        take_turn(game)
        game.choose(AUCTION_KEY)
        self.assertEqual([p.name for p in game.auction.bidders], ["Ada", "Cleo"])

    def test_the_sale_is_announced(self):
        self.assertIn("goes to auction", self.game.log[-1])

    def test_the_turn_waits_for_the_sale(self):
        self.assertIs(self.game.state, State.LAND_ACTION)


class ModalityTest(unittest.TestCase):
    """A running sale stops the turn moving on underneath it."""

    def setUp(self):
        self.game = declined()

    def test_no_action_is_available(self):
        self.assertEqual(self.game.available_actions(), frozenset())

    def test_the_turn_cannot_be_ended(self):
        self.assertFalse(self.game.perform(Action.END_TURN))
        self.assertIsNotNone(self.game.auction)

    def test_the_build_screen_cannot_be_opened(self):
        with self.assertRaises(RuntimeError):
            self.game.open_build()

    def test_two_sales_cannot_run_at_once(self):
        with self.assertRaises(RuntimeError):
            self.game.open_auction(self.game.deed(1))

    def test_a_sale_cannot_open_over_a_prompt(self):
        game = make_game(rolls=[BALTIC])
        take_turn(game)  # the buy prompt is up
        self.assertIsNotNone(game.prompt)
        with self.assertRaises(RuntimeError):
            game.open_auction(game.deed(1))

    def test_a_sale_cannot_open_over_the_build_screen(self):
        game = make_game(rolls=[TAX])
        take_turn(game)
        for index in (1, 3):
            game.current.add_property(game.deed(index))
        game.open_build()
        with self.assertRaises(RuntimeError):
            game.open_auction(game.deed(6))

    def test_bidding_with_no_sale_running_raises(self):
        game = make_game()
        with self.assertRaises(RuntimeError):
            game.bid(10)
        with self.assertRaises(RuntimeError):
            game.pass_bid()


class SettlingTest(unittest.TestCase):
    def test_the_winner_pays_the_bank_and_takes_the_deed(self):
        game = declined()
        game.bid(40)
        game.pass_bid()  # Bob drops out, so Ada's bid stands
        deed = game.deed(3)
        self.assertIs(deed.owner, game.players[0])
        self.assertIn(deed, game.players[0].properties)
        self.assertEqual(game.players[0].cash, 1500 - 40)
        self.assertIsNone(game.auction)

    def test_a_deed_can_go_for_less_than_it_is_worth(self):
        game = declined()
        game.bid(1)
        game.pass_bid()
        self.assertEqual(game.players[0].cash, 1499)
        self.assertEqual(game.deed(3).price, 60, "the list price never changes")

    def test_somebody_other_than_the_roller_can_win_it(self):
        game = declined()
        game.pass_bid()  # Ada wants nothing to do with it
        game.bid(75)  # Bob does
        self.assertIs(game.deed(3).owner, game.players[1])
        self.assertEqual(game.players[1].cash, 1500 - 75)
        self.assertEqual(game.players[0].cash, 1500)

    def test_nobody_bidding_leaves_the_deed_with_the_bank(self):
        game = declined()
        pass_everyone(game)
        self.assertIsNone(game.deed(3).owner)
        self.assertEqual([p.cash for p in game.players], [1500, 1500])
        self.assertIn("Nobody bid", game.message)

    def test_the_result_is_written_into_the_log(self):
        game = declined()
        game.bid(40)
        game.pass_bid()
        self.assertIn("Ada bids $40.", game.log)
        self.assertIn("Bob passes.", game.log)
        self.assertEqual(
            game.message, "Ada wins Baltic Avenue at auction for $40."
        )

    def test_the_sale_s_own_closing_line_is_not_said_twice(self):
        game = declined()
        game.bid(40)
        game.pass_bid()
        self.assertNotIn("Ada takes Baltic Avenue for $40.", game.log)

    def test_an_illegal_bid_changes_nothing(self):
        game = declined()
        self.assertFalse(game.bid(0))
        self.assertFalse(game.bid(1501))
        self.assertIsNotNone(game.auction)
        self.assertIs(game.auction.bidder, game.players[0])
        self.assertEqual(game.players[0].cash, 1500)

    def test_a_sale_nobody_can_open_settles_on_the_spot(self):
        game = declined(cash=0)
        self.assertIsNone(game.auction)
        self.assertIsNone(game.deed(3).owner)
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    def test_the_turn_carries_on_afterwards(self):
        game = declined()
        game.bid(40)
        game.pass_bid()
        self.assertIs(game.state, State.PLAYER_ACTIONS)
        self.assertEqual(
            game.available_actions(),
            # Mortgage is live because Ada now holds the deed she just won
            # (Phase 12); Build is not, because one lot is not a group.
            frozenset({Action.END_TURN, Action.TRADE, Action.MORTGAGE}),
        )
        game.end_turn()
        self.assertIs(game.current, game.players[1])

    def test_a_group_won_at_auction_lights_the_build_button(self):
        game = declined()
        game.current.add_property(game.deed(1))  # Mediterranean, the other brown
        game.bid(40)
        game.pass_bid()
        self.assertTrue(game.can_build())
        self.assertIn(Action.BUILD, game.available_actions())


class BiddingWarTest(unittest.TestCase):
    def setUp(self):
        self.game = make_game(rolls=[BALTIC], names=("Ada", "Bob", "Cleo"))
        take_turn(self.game)
        self.game.choose(AUCTION_KEY)

    def test_the_price_climbs_until_two_players_drop_out(self):
        game = self.game
        game.bid(50)
        game.bid(100)
        game.bid(150)
        game.pass_bid()  # Ada
        game.pass_bid()  # Bob, leaving Cleo
        self.assertIs(game.deed(3).owner, game.players[2])
        self.assertEqual(game.players[2].cash, 1500 - 150)

    def test_a_passed_player_is_never_asked_again(self):
        game = self.game
        game.pass_bid()  # Ada
        game.bid(20)  # Bob
        game.bid(30)  # Cleo
        self.assertIs(game.auction.bidder, game.players[1], "not back to Ada")

    def test_the_losers_keep_their_money(self):
        game = self.game
        game.bid(50)
        game.bid(100)
        game.pass_bid()  # Cleo
        game.pass_bid()  # Ada, so Bob's $100 stands
        self.assertEqual([p.cash for p in game.players], [1500, 1400, 1500])


class HookTest(unittest.TestCase):
    """``on_auction`` still wins: a caller may run its own sale, or none."""

    def test_a_registered_hook_replaces_the_built_in_sale(self):
        game = make_game(rolls=[BALTIC])
        seen = []
        game.on_auction = lambda g, deed: seen.append(deed)
        take_turn(game)
        game.choose(AUCTION_KEY)
        self.assertEqual(seen, [game.deed(3)])
        self.assertIsNone(game.auction, "the hook decided not to hold one")
        self.assertIs(game.state, State.PLAYER_ACTIONS, "so the turn moves on")

    def test_a_hook_may_open_a_sale_of_its_own(self):
        game = make_game(rolls=[BALTIC])
        game.on_auction = lambda g, deed: g.open_auction(deed)
        take_turn(game)
        game.choose(AUCTION_KEY)
        self.assertIsNotNone(game.auction)
        self.assertIs(game.state, State.LAND_ACTION, "and the turn waits for it")


class TurnHygieneTest(unittest.TestCase):
    def test_a_new_turn_starts_with_no_sale_hanging_over_it(self):
        game = declined()
        game.auction = None  # as if something dropped the sale mid-flight
        game.state = State.PLAYER_ACTIONS
        game.end_turn()
        self.assertIsNone(game.auction)
        self.assertEqual(game.available_actions(), frozenset({Action.ROLL}))

    def test_buying_outright_never_opens_a_sale(self):
        game = make_game(rolls=[BALTIC])
        take_turn(game)
        game.choose(BUY_KEY)
        self.assertIsNone(game.auction)
        self.assertIs(game.deed(3).owner, game.players[0])

    def test_landing_on_an_owned_deed_never_opens_a_sale(self):
        game = make_game(rolls=[BALTIC])
        game.players[1].add_property(game.deed(3))
        take_turn(game)
        self.assertIsNone(game.auction)
        self.assertIsNone(game.prompt)


class WholeGameTest(unittest.TestCase):
    """A game played end to end by bots that auction and bid at random.

    The point is not any one number but that the sale holds up wherever it
    turns up in a real turn: every deed is either the bank's or in exactly
    one player's hand, nobody ever spends money they do not have, and a
    winner's payment always matches the price that was struck.
    """

    TURNS = 300

    def check_invariants(self, game: Game) -> None:
        for player in game.players:
            self.assertGreaterEqual(player.cash, 0, f"{player.name} overdrew")
        for deed in game.properties:
            if deed.owner is None:
                for player in game.players:
                    self.assertNotIn(deed, player.properties)
                continue
            holders = [p for p in game.players if deed in p.properties]
            self.assertEqual(
                [deed.owner], holders, f"{deed.name} is held by the wrong hand"
            )
        auction = game.auction
        if auction is not None:
            self.assertIsNone(auction.deed.owner, "an unsold deed has no owner")
            self.assertFalse(auction.finished, "a settled sale is closed at once")
            self.assertIsNotNone(auction.bidder)
            self.assertFalse(auction.has_passed(auction.bidder))
            self.assertLessEqual(auction.high_bid, 10_000)

    def play(self, seed: int, bid_chance: float) -> Game:
        rng = random.Random(seed)
        game = make_game(cash=1500, names=("Ada", "Bob", "Cleo"))
        sales = {"held": 0, "sold": 0}
        steps = 0
        turns = 0
        while turns < self.TURNS and game.state is not State.GAME_OVER:
            steps += 1
            self.assertLess(steps, 200 * self.TURNS, "the turn loop is spinning")
            game.update(0)
            self.check_invariants(game)

            if game.auction is not None:
                auction = game.auction
                bidder, price = auction.bidder, auction.min_bid
                cash_before = bidder.cash
                if rng.random() < bid_chance and game.bid(price):
                    if game.auction is None and auction.winner is bidder:
                        sales["sold"] += 1
                        self.assertEqual(bidder.cash, cash_before - price)
                        self.assertIs(auction.deed.owner, bidder)
                else:
                    game.pass_bid()
                continue

            if game.prompt is not None:
                options = [c.key for c in game.prompt.options if c.enabled]
                # Decline about half the deeds on offer, to hold a sale.
                if AUCTION_KEY in options and rng.random() < 0.5:
                    key = AUCTION_KEY
                    sales["held"] += 1
                else:
                    key = rng.choice(options)
                game.choose(key)
                continue

            actions = game.available_actions()
            if Action.ROLL in actions:
                game.perform(Action.ROLL)
            elif Action.END_TURN in actions:
                game.perform(Action.END_TURN)
                turns += 1
            else:
                self.fail(f"stuck in {game.state.value} with nothing to do")

        self.check_invariants(game)
        self.sales = sales
        return game

    def test_a_table_that_always_bids_never_breaks_the_rules(self):
        self.play(seed=7, bid_chance=1.0)
        self.assertGreater(self.sales["held"], 0, "no deed was ever auctioned")
        self.assertGreater(self.sales["sold"], 0, "no auction ever sold anything")

    def test_a_table_that_never_bids_never_breaks_the_rules(self):
        self.play(seed=11, bid_chance=0.0)
        self.assertGreater(self.sales["held"], 0, "no deed was ever auctioned")
        self.assertEqual(self.sales["sold"], 0)

    def test_a_table_that_bids_at_random_never_breaks_the_rules(self):
        game = self.play(seed=99, bid_chance=0.5)
        self.assertGreater(self.sales["held"], 0, "no deed was ever auctioned")
        owned = [d for d in game.properties if d.owner is not None]
        self.assertGreater(len(owned), 0)

    def test_every_dollar_bid_leaves_the_table(self):
        """Cash only ever moves for a reason, so the books have to balance."""
        game = self.play(seed=5, bid_chance=0.8)
        for player in game.players:
            self.assertGreaterEqual(player.cash, 0)
            self.assertEqual(
                player.net_worth(),
                player.cash + sum(d.price for d in player.properties),
                "nothing bought at auction is mortgaged or built on yet",
            )


class LoneBidderTest(unittest.TestCase):
    """A one-handed game still holds a sale -- against the bank, in effect."""

    def test_the_only_player_may_take_it(self):
        game = make_game(rolls=[BALTIC], names=("Ada",), start=False)
        game.start()
        take_turn(game)
        game.choose(AUCTION_KEY)
        self.assertIsNotNone(game.auction)
        game.bid(1)
        self.assertIs(game.deed(3).owner, game.players[0])
        self.assertEqual(game.players[0].cash, 1499)

    def test_the_only_player_may_also_walk_away(self):
        game = make_game(rolls=[BALTIC], names=("Ada",))
        take_turn(game)
        game.choose(AUCTION_KEY)
        game.pass_bid()
        self.assertIsNone(game.deed(3).owner)
        self.assertIs(game.state, State.PLAYER_ACTIONS)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
