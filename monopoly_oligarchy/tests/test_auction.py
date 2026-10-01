"""Phase 10 tests: the auction rules.

:class:`monopoly.auction.Auction` is the sale on its own -- who is asked, what
they may bid, and how the round ends. Nothing here touches the board: the
auction never moves a deed or a dollar, so every test below checks that the
deed is exactly as it was when the hammer fell. Wiring the sale into a turn is
``test_auction_game.py``'s job, and no pygame is imported by either.
"""

from __future__ import annotations

import unittest

from monopoly.auction import (
    BID_INCREMENT,
    MIN_BID,
    Auction,
    Bid,
    summarise,
)
from monopoly.player import Player
from monopoly.property import build_properties

TOKENS = ("red", "blue", "green", "yellow")


def deeds():
    return build_properties()


def baltic():
    """Baltic Avenue: $60 on the board, and unowned."""
    return next(d for d in deeds() if d.index == 3)


def roster(*cash: int) -> list[Player]:
    """One player per amount, named Ada, Bob, Cleo, Dai."""
    names = ("Ada", "Bob", "Cleo", "Dai")
    return [Player(n, c, t) for n, c, t in zip(names, cash, TOKENS)]


def auction(*cash: int, **kwargs) -> Auction:
    """A sale of Baltic Avenue between players with the given wallets."""
    return Auction(baltic(), roster(*cash), **kwargs)


class OpeningTest(unittest.TestCase):
    def test_the_round_opens_on_the_first_bidder(self):
        sale = auction(500, 500)
        self.assertIs(sale.bidder, sale.bidders[0])
        self.assertEqual(sale.bidder.name, "Ada")

    def test_nothing_is_bid_to_start_with(self):
        sale = auction(500, 500)
        self.assertEqual(sale.high_bid, 0)
        self.assertIsNone(sale.high_bidder)
        self.assertEqual(sale.history, [])
        self.assertFalse(sale.finished)
        self.assertFalse(sale.sold)

    def test_the_opening_price_is_a_dollar(self):
        self.assertEqual(auction(500, 500).min_bid, MIN_BID)
        self.assertEqual(MIN_BID, 1)

    def test_everybody_is_still_in(self):
        sale = auction(500, 500, 500)
        self.assertEqual(sale.remaining, sale.bidders)
        self.assertEqual(sale.passed, [])
        for player in sale.bidders:
            self.assertFalse(sale.has_passed(player))

    def test_a_bankrupt_player_is_not_in_the_room(self):
        players = roster(500, 500, 500)
        players[1].is_bankrupt = True
        sale = Auction(baltic(), players)
        self.assertEqual([p.name for p in sale.bidders], ["Ada", "Cleo"])

    def test_a_sale_needs_somebody_to_bid(self):
        with self.assertRaises(ValueError):
            Auction(baltic(), [])

    def test_a_room_of_bankrupts_is_no_room_at_all(self):
        player = roster(500)[0]
        player.is_bankrupt = True
        with self.assertRaises(ValueError):
            Auction(baltic(), [player])

    def test_the_opening_price_cannot_be_free(self):
        with self.assertRaises(ValueError):
            auction(500, 500, minimum=0)

    def test_the_increment_cannot_be_nothing(self):
        with self.assertRaises(ValueError):
            auction(500, 500, increment=0)

    def test_a_house_minimum_and_increment_are_honoured(self):
        sale = auction(500, 500, minimum=10, increment=5)
        self.assertEqual(sale.min_bid, 10)
        sale.bid(10)
        self.assertEqual(sale.min_bid, 15)


class BiddingTest(unittest.TestCase):
    def setUp(self):
        self.sale = auction(500, 500, 500)

    def test_a_bid_takes_the_lead_and_hands_the_turn_on(self):
        self.assertTrue(self.sale.bid(50))
        self.assertEqual(self.sale.high_bid, 50)
        self.assertIs(self.sale.high_bidder, self.sale.bidders[0])
        self.assertIs(self.sale.bidder, self.sale.bidders[1])

    def test_the_price_climbs_by_the_increment(self):
        self.sale.bid(50)
        self.assertEqual(self.sale.min_bid, 50 + BID_INCREMENT)

    def test_the_history_keeps_every_bid_in_order(self):
        self.sale.bid(50)
        self.sale.bid(80)
        self.assertEqual(
            self.sale.history,
            [Bid(self.sale.bidders[0], 50), Bid(self.sale.bidders[1], 80)],
        )

    def test_a_bid_below_the_asking_price_is_refused(self):
        self.sale.bid(50)
        self.assertFalse(self.sale.bid(50))
        self.assertEqual(self.sale.high_bid, 50)
        self.assertIs(self.sale.bidder, self.sale.bidders[1], "still their turn")

    def test_the_opening_bid_cannot_be_nothing(self):
        self.assertFalse(self.sale.bid(0))
        self.assertIsNone(self.sale.high_bidder)

    def test_nobody_bids_cash_they_do_not_have(self):
        sale = auction(40, 500)
        self.assertFalse(sale.bid(41))
        self.assertTrue(sale.bid(40), "every last dollar is allowed")

    def test_a_refused_bid_leaves_no_trace(self):
        self.sale.bid(700)
        self.assertEqual(self.sale.history, [])
        self.assertEqual(self.sale.log, [])
        self.assertIs(self.sale.bidder, self.sale.bidders[0])

    def test_can_bid_answers_for_the_player_on_turn(self):
        sale = self.sale
        self.assertTrue(sale.can_bid(1))
        self.assertFalse(sale.can_bid(0))
        self.assertFalse(sale.can_bid(501))
        self.assertFalse(
            sale.can_bid(50, sale.bidders[1]), "it is not their turn"
        )
        self.assertTrue(sale.can_bid(50, sale.bidders[0]))

    def test_the_round_goes_back_round_the_table(self):
        sale = self.sale
        sale.bid(10)
        sale.bid(20)
        sale.bid(30)
        self.assertIs(sale.bidder, sale.bidders[0], "back to Ada for a fourth")
        self.assertEqual(sale.high_bid, 30)

    def test_the_leader_is_never_asked_to_outbid_themselves(self):
        sale = self.sale
        sale.bid(10)
        sale.withdraw()  # Bob
        self.assertIsNot(sale.bidder, sale.high_bidder)
        sale.withdraw()  # Cleo, and Ada's bid stands
        self.assertTrue(sale.finished)


class PassingTest(unittest.TestCase):
    def test_passing_takes_a_player_out_for_good(self):
        sale = auction(500, 500, 500)
        first = sale.bidder
        self.assertTrue(sale.withdraw())
        self.assertTrue(sale.has_passed(first))
        self.assertNotIn(first, sale.remaining)
        sale.bid(10)
        sale.bid(20)
        self.assertIsNot(sale.bidder, first, "a passed player is never asked again")

    def test_a_pass_hands_the_turn_to_the_next_seat(self):
        sale = auction(500, 500, 500)
        sale.withdraw()
        self.assertIs(sale.bidder, sale.bidders[1])

    def test_everybody_passing_leaves_the_deed_unsold(self):
        sale = auction(500, 500)
        sale.withdraw()
        sale.withdraw()
        self.assertTrue(sale.finished)
        self.assertIsNone(sale.winner)
        self.assertFalse(sale.sold)
        self.assertEqual(sale.price, 0)

    def test_the_last_bidder_standing_wins(self):
        sale = auction(500, 500, 500)
        sale.bid(75)
        sale.withdraw()
        sale.withdraw()
        self.assertTrue(sale.finished)
        self.assertIs(sale.winner, sale.bidders[0])
        self.assertEqual(sale.price, 75)
        self.assertTrue(sale.sold)

    def test_the_sale_is_over_for_good(self):
        sale = auction(500, 500)
        sale.withdraw()
        sale.withdraw()
        self.assertIsNone(sale.bidder)
        self.assertFalse(sale.withdraw())
        self.assertFalse(sale.bid(100))
        self.assertFalse(sale.can_bid(100))


class DropOutTest(unittest.TestCase):
    """A bidder who cannot reach the asking price is out automatically.

    Without that the round would stall on a player with nothing to offer, and
    a table where nobody can afford a dollar would never settle at all.
    """

    def test_a_bidder_who_cannot_afford_the_opening_never_gets_asked(self):
        sale = auction(0, 500)
        self.assertIs(sale.bidder, sale.bidders[1])
        self.assertTrue(sale.has_passed(sale.bidders[0]))

    def test_a_table_that_cannot_afford_a_dollar_settles_at_once(self):
        sale = auction(0, 0)
        self.assertTrue(sale.finished)
        self.assertIsNone(sale.winner)
        self.assertEqual(sale.remaining, [])

    def test_a_bidder_priced_out_mid_round_drops_out(self):
        sale = auction(500, 30)
        sale.bid(40)  # Ada, beyond anything Bob can answer
        self.assertTrue(sale.has_passed(sale.bidders[1]))
        self.assertTrue(sale.finished)
        self.assertIs(sale.winner, sale.bidders[0])

    def test_dropping_out_is_said_out_loud(self):
        sale = auction(500, 30)
        sale.bid(40)
        self.assertIn("Bob cannot reach $41", sale.log[1])

    def test_a_lone_bidder_may_still_take_it(self):
        sale = auction(500)
        self.assertFalse(sale.finished, "a one-handed sale is still a sale")
        sale.bid(1)
        self.assertTrue(sale.finished)
        self.assertIs(sale.winner, sale.bidders[0])

    def test_a_lone_bidder_may_also_walk_away(self):
        sale = auction(500)
        sale.withdraw()
        self.assertTrue(sale.finished)
        self.assertIsNone(sale.winner)


class TranscriptTest(unittest.TestCase):
    def test_every_move_is_written_down(self):
        sale = auction(500, 500)
        sale.bid(20)
        sale.withdraw()
        self.assertEqual(
            sale.log,
            [
                "Ada bids $20.",
                "Bob passes.",
                "Ada takes Baltic Avenue for $20.",
            ],
        )
        self.assertEqual(sale.last_note, "Ada takes Baltic Avenue for $20.")

    def test_an_empty_sale_says_so(self):
        sale = auction(500, 500)
        sale.withdraw()
        sale.withdraw()
        self.assertIn("Nobody bid", sale.log[-1])

    def test_there_is_nothing_to_say_before_the_first_move(self):
        self.assertEqual(auction(500, 500).last_note, "")

    def test_big_numbers_are_printed_with_commas(self):
        sale = auction(5000, 5000)
        sale.bid(1200)
        self.assertIn("$1,200", sale.log[0])


class SummaryTest(unittest.TestCase):
    def test_before_a_bid_it_names_the_opening_price(self):
        self.assertIn("opening at $1", summarise(auction(500, 500)))

    def test_during_the_sale_it_names_the_leader(self):
        sale = auction(500, 500)
        sale.bid(60)
        text = summarise(sale)
        self.assertIn("$60", text)
        self.assertIn("Ada", text)
        self.assertIn("next $61", text)

    def test_afterwards_it_names_the_buyer(self):
        sale = auction(500, 500)
        sale.bid(60)
        sale.withdraw()
        self.assertEqual(summarise(sale), "Sold to Ada for $60.")

    def test_an_unsold_deed_goes_back_to_the_bank(self):
        sale = auction(500, 500)
        sale.withdraw()
        sale.withdraw()
        self.assertIn("stays with the bank", summarise(sale))


class NothingMovesTest(unittest.TestCase):
    """The sale decides; the game settles. Nothing here touches the board."""

    def test_the_deed_is_untouched_by_a_win(self):
        deed = baltic()
        players = roster(500, 500)
        sale = Auction(deed, players)
        sale.bid(300)
        sale.withdraw()
        self.assertIs(sale.winner, players[0])
        self.assertIsNone(deed.owner)
        self.assertEqual(players[0].cash, 500)
        self.assertEqual(players[0].properties, [])

    def test_the_deed_is_untouched_by_an_empty_sale(self):
        deed = baltic()
        players = roster(500, 500)
        sale = Auction(deed, players)
        sale.withdraw()
        sale.withdraw()
        self.assertIsNone(deed.owner)
        self.assertEqual([p.cash for p in players], [500, 500])


class BiddingWarTest(unittest.TestCase):
    """A long round-robin, to check the turn never lands somewhere silly."""

    def test_a_four_handed_war_ends_with_the_deepest_pocket(self):
        sale = auction(100, 200, 300, 400)
        price = 0
        while not sale.finished:
            price += 25
            if not sale.bid(price):
                sale.withdraw()
        self.assertIs(sale.winner, sale.bidders[3], "Dai has the most money")
        self.assertLessEqual(sale.price, 400)
        self.assertEqual(len(sale.remaining), 1)

    def test_every_bid_beat_the_one_before_it(self):
        sale = auction(100, 200, 300, 400)
        price = 0
        while not sale.finished:
            price += 25
            if not sale.bid(price):
                sale.withdraw()
        amounts = [bid.amount for bid in sale.history]
        self.assertEqual(amounts, sorted(set(amounts)))

    def test_nobody_is_asked_after_they_pass(self):
        sale = auction(500, 500, 500, 500)
        asked: list = []
        price = 0
        while not sale.finished:
            asked.append(sale.bidder)
            self.assertFalse(sale.has_passed(sale.bidder))
            price += 100
            if not sale.bid(price):
                sale.withdraw()
        self.assertTrue(sale.finished)
        self.assertIs(asked[-1], sale.winner, "the last one asked is the buyer")
        self.assertEqual(len(sale.remaining), 1)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
