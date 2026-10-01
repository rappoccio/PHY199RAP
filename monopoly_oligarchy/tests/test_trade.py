"""Phase 11 tests: the trading rules.

:class:`monopoly.trade.Trade` is the deal on its own -- who it is with, what
may go on the table, and what happens when it is settled. Nothing is wired to
a turn here, and no pygame is imported; ``test_trade_game.py`` covers the
join to :class:`monopoly.game.Game` and ``test_trade_screen.py`` the panel.

A trade *does* move deeds and cash when it is accepted -- unlike an auction,
which only says who won -- so the tests below check both halves: that nothing
moves before Accept, and that everything moves together on it.
"""

from __future__ import annotations

import unittest

from monopoly.player import Player
from monopoly.property import build_properties
from monopoly.trade import (
    ACCEPTED,
    CANCELLED,
    CLOSED,
    DRAFT,
    NOTHING,
    PARTNER,
    REJECTED,
    REVIEW,
    Offer,
    Trade,
    describe,
    group_is_bare,
    summarise_offer,
)

TOKENS = ("red", "blue", "green", "yellow")
NAMES = ("Ada", "Bob", "Cleo", "Dai")

#: Board indices used below.
MEDITERRANEAN = 1
BALTIC = 3
READING = 5
ORIENTAL = 6
VERMONT = 8
CONNECTICUT = 9


class TradeTestCase(unittest.TestCase):
    """Ada and Bob, each with $1,500 and a fresh board between them."""

    cash = (1500, 1500)

    def setUp(self):
        self.deeds = build_properties()
        self.players = [
            Player(n, c, t) for n, c, t in zip(NAMES, self.cash, TOKENS)
        ]
        self.ada, self.bob = self.players[0], self.players[1]

    def deed(self, index):
        return next(d for d in self.deeds if d.index == index)

    def give(self, player, *indices):
        for index in indices:
            player.add_property(self.deed(index))

    def trade(self, **kwargs) -> Trade:
        return Trade(self.ada, self.players, self.deeds, **kwargs)

    def ready(self, **kwargs) -> Trade:
        """A drafted deal with Baltic Avenue on Ada's side of the table."""
        self.give(self.ada, BALTIC)
        deal = self.trade(**kwargs)
        deal.add_deed(self.deed(BALTIC))
        return deal

    def proposed(self, **kwargs) -> Trade:
        deal = self.ready(**kwargs)
        deal.propose()
        return deal


class OpeningTest(TradeTestCase):
    def test_a_two_handed_table_has_no_partner_to_choose(self):
        deal = self.trade()
        self.assertIs(deal.partner, self.bob)
        self.assertEqual(deal.phase, DRAFT)

    def test_a_bigger_table_asks_who_first(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        deal = Trade(players[0], players, self.deeds)
        self.assertIsNone(deal.partner)
        self.assertEqual(deal.phase, PARTNER)
        self.assertEqual([p.name for p in deal.candidates], ["Bob", "Cleo", "Dai"])

    def test_a_partner_given_up_front_is_taken(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        deal = Trade(players[0], players, self.deeds, partner=players[2])
        self.assertIs(deal.partner, players[2])
        self.assertEqual(deal.phase, DRAFT)

    def test_choosing_a_partner_opens_the_draft(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        deal = Trade(players[0], players, self.deeds)
        self.assertTrue(deal.choose_partner(players[1]))
        self.assertIs(deal.partner, players[1])
        self.assertEqual(deal.phase, DRAFT)

    def test_a_stranger_cannot_be_chosen(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        deal = Trade(players[0], players, self.deeds)
        self.assertFalse(deal.choose_partner(Player("Eve", 1500, "purple")))
        self.assertIsNone(deal.partner)

    def test_the_proposer_is_not_their_own_partner(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        deal = Trade(players[0], players, self.deeds)
        self.assertNotIn(players[0], deal.candidates)
        self.assertFalse(deal.choose_partner(players[0]))

    def test_a_bankrupt_player_is_not_a_candidate(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        players[1].is_bankrupt = True
        deal = Trade(players[0], players, self.deeds)
        self.assertEqual([p.name for p in deal.candidates], ["Cleo", "Dai"])

    def test_a_trade_needs_somebody_to_trade_with(self):
        with self.assertRaises(ValueError):
            Trade(self.ada, [self.ada], self.deeds)

    def test_a_table_of_bankrupts_is_no_table_at_all(self):
        self.bob.is_bankrupt = True
        with self.assertRaises(ValueError):
            self.trade()

    def test_the_partner_cannot_be_changed_once_drafting_starts(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        deal = Trade(players[0], players, self.deeds, partner=players[1])
        self.assertFalse(deal.choose_partner(players[2]))
        self.assertIs(deal.partner, players[1])

    def test_both_columns_start_empty(self):
        deal = self.trade()
        for side in deal.sides:
            self.assertTrue(side.is_empty)
        self.assertTrue(deal.is_empty)

    def test_only_one_column_exists_before_a_partner(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        deal = Trade(players[0], players, self.deeds)
        self.assertEqual(len(deal.sides), 1)
        self.assertIsNone(deal.theirs)


class HoldingsTest(TradeTestCase):
    def test_holdings_are_in_board_order(self):
        self.give(self.ada, ORIENTAL, MEDITERRANEAN, READING)
        deal = self.trade()
        self.assertEqual(
            [d.index for d in deal.holdings(self.ada)],
            [MEDITERRANEAN, READING, ORIENTAL],
        )

    def test_holdings_are_empty_for_a_player_with_no_deeds(self):
        self.assertEqual(self.trade().holdings(self.bob), [])

    def test_tradable_is_everything_when_nothing_is_built(self):
        self.give(self.ada, MEDITERRANEAN, BALTIC)
        deal = self.trade()
        self.assertEqual(deal.tradable(self.ada), deal.holdings(self.ada))

    def test_a_built_group_is_held_back_from_tradable(self):
        self.give(self.ada, MEDITERRANEAN, BALTIC, READING)
        self.deed(BALTIC).houses = 1
        deal = self.trade()
        self.assertEqual([d.index for d in deal.tradable(self.ada)], [READING])

    def test_holdings_still_list_a_built_lot(self):
        self.give(self.ada, MEDITERRANEAN, BALTIC)
        self.deed(BALTIC).houses = 1
        deal = self.trade()
        self.assertEqual(len(deal.holdings(self.ada)), 2)


class GroupIsBareTest(TradeTestCase):
    def test_a_bare_group_is_bare(self):
        self.assertTrue(group_is_bare(self.deed(BALTIC), self.deeds))

    def test_a_house_anywhere_in_the_group_counts(self):
        self.deed(MEDITERRANEAN).houses = 1
        self.assertFalse(group_is_bare(self.deed(BALTIC), self.deeds))

    def test_a_hotel_counts_too(self):
        self.deed(MEDITERRANEAN).has_hotel = True
        self.assertFalse(group_is_bare(self.deed(BALTIC), self.deeds))

    def test_another_group_is_untouched(self):
        self.deed(MEDITERRANEAN).houses = 1
        self.assertTrue(group_is_bare(self.deed(ORIENTAL), self.deeds))

    def test_a_railroad_is_always_bare(self):
        self.assertTrue(group_is_bare(self.deed(READING), self.deeds))


class DeedsOnTheTableTest(TradeTestCase):
    def setUp(self):
        super().setUp()
        self.give(self.ada, BALTIC, READING)
        self.give(self.bob, ORIENTAL)
        self.deal = self.trade()

    def test_a_deed_goes_onto_its_owner_s_side(self):
        self.assertTrue(self.deal.add_deed(self.deed(BALTIC)))
        self.assertTrue(self.deal.mine.holds(self.deed(BALTIC)))
        self.assertFalse(self.deal.theirs.holds(self.deed(BALTIC)))

    def test_the_partner_s_deed_goes_onto_theirs(self):
        self.assertTrue(self.deal.add_deed(self.deed(ORIENTAL)))
        self.assertTrue(self.deal.theirs.holds(self.deed(ORIENTAL)))

    def test_an_unowned_deed_cannot_be_offered(self):
        self.assertFalse(self.deal.can_offer(self.deed(VERMONT)))
        self.assertFalse(self.deal.add_deed(self.deed(VERMONT)))

    def test_a_third_party_s_deed_cannot_be_offered(self):
        cleo = Player("Cleo", 1500, "green")
        cleo.add_property(self.deed(VERMONT))
        self.assertFalse(self.deal.add_deed(self.deed(VERMONT)))

    def test_a_deed_cannot_go_on_twice(self):
        self.deal.add_deed(self.deed(BALTIC))
        self.assertFalse(self.deal.add_deed(self.deed(BALTIC)))
        self.assertEqual(len(self.deal.mine.deeds), 1)

    def test_a_deed_comes_back_off(self):
        self.deal.add_deed(self.deed(BALTIC))
        self.assertTrue(self.deal.remove_deed(self.deed(BALTIC)))
        self.assertFalse(self.deal.is_offered(self.deed(BALTIC)))

    def test_taking_off_a_deed_that_is_not_on_does_nothing(self):
        self.assertFalse(self.deal.remove_deed(self.deed(BALTIC)))

    def test_toggle_flips_it_both_ways(self):
        self.assertTrue(self.deal.toggle(self.deed(BALTIC)))
        self.assertTrue(self.deal.is_offered(self.deed(BALTIC)))
        self.assertTrue(self.deal.toggle(self.deed(BALTIC)))
        self.assertFalse(self.deal.is_offered(self.deed(BALTIC)))

    def test_toggling_something_untradable_refuses(self):
        self.assertFalse(self.deal.toggle(self.deed(VERMONT)))

    def test_deeds_stay_in_board_order(self):
        self.deal.add_deed(self.deed(READING))
        self.deal.add_deed(self.deed(BALTIC))
        self.assertEqual([d.index for d in self.deal.mine.deeds], [BALTIC, READING])

    def test_a_built_group_cannot_be_traded_from(self):
        self.give(self.ada, MEDITERRANEAN)
        self.deed(MEDITERRANEAN).houses = 1
        self.assertFalse(self.deal.can_offer(self.deed(BALTIC)))
        self.assertFalse(self.deal.add_deed(self.deed(BALTIC)))

    def test_a_mortgaged_deed_trades_freely(self):
        self.deed(BALTIC).mortgaged = True
        self.assertTrue(self.deal.add_deed(self.deed(BALTIC)))

    def test_nothing_may_be_offered_once_the_offer_is_out(self):
        self.deal.add_deed(self.deed(BALTIC))
        self.deal.propose()
        self.assertFalse(self.deal.can_offer(self.deed(READING)))
        self.assertFalse(self.deal.add_deed(self.deed(READING)))
        self.assertFalse(self.deal.remove_deed(self.deed(BALTIC)))

    def test_side_of_names_the_column(self):
        self.assertIs(self.deal.side_of(self.deed(BALTIC)), self.deal.mine)
        self.assertIs(self.deal.side_of(self.deed(ORIENTAL)), self.deal.theirs)
        self.assertIsNone(self.deal.side_of(self.deed(VERMONT)))


class CashTest(TradeTestCase):
    cash = (1500, 200)

    def setUp(self):
        super().setUp()
        self.deal = self.trade()

    def test_cash_goes_on_the_table(self):
        self.assertTrue(self.deal.set_cash(self.ada, 500))
        self.assertEqual(self.deal.mine.cash, 500)

    def test_more_than_is_held_is_refused(self):
        self.assertFalse(self.deal.set_cash(self.bob, 201))
        self.assertEqual(self.deal.theirs.cash, 0)

    def test_exactly_what_is_held_is_fine(self):
        self.assertTrue(self.deal.set_cash(self.bob, 200))

    def test_a_negative_amount_is_refused(self):
        self.assertFalse(self.deal.set_cash(self.ada, -1))

    def test_zero_takes_the_cash_back_off(self):
        self.deal.set_cash(self.ada, 500)
        self.assertTrue(self.deal.set_cash(self.ada, 0))
        self.assertTrue(self.deal.mine.is_empty)

    def test_a_stranger_has_no_column(self):
        with self.assertRaises(ValueError):
            self.deal.set_cash(Player("Eve", 100, "purple"), 10)

    def test_cash_is_frozen_once_the_offer_is_out(self):
        self.deal.set_cash(self.ada, 500)
        self.deal.propose()
        self.assertFalse(self.deal.set_cash(self.ada, 600))
        self.assertEqual(self.deal.mine.cash, 500)

    def test_nothing_is_taken_from_the_wallet_yet(self):
        self.deal.set_cash(self.ada, 500)
        self.assertEqual(self.ada.cash, 1500)


class JailCardTest(TradeTestCase):
    def setUp(self):
        super().setUp()
        self.ada.goojf_cards = 2
        self.deal = self.trade()

    def test_a_card_goes_on_the_table(self):
        self.assertTrue(self.deal.set_goojf(self.ada, 1))
        self.assertEqual(self.deal.mine.goojf, 1)

    def test_both_cards_may_go_on(self):
        self.assertTrue(self.deal.set_goojf(self.ada, 2))

    def test_more_cards_than_are_held_is_refused(self):
        self.assertFalse(self.deal.set_goojf(self.ada, 3))
        self.assertEqual(self.deal.mine.goojf, 0)

    def test_a_player_with_no_cards_can_offer_none(self):
        self.assertFalse(self.deal.set_goojf(self.bob, 1))

    def test_a_negative_count_is_refused(self):
        self.assertFalse(self.deal.set_goojf(self.ada, -1))

    def test_cards_are_frozen_once_the_offer_is_out(self):
        self.deal.set_goojf(self.ada, 1)
        self.deal.propose()
        self.assertFalse(self.deal.set_goojf(self.ada, 2))

    def test_nothing_leaves_the_hand_yet(self):
        self.deal.set_goojf(self.ada, 2)
        self.assertEqual(self.ada.goojf_cards, 2)


class ValidityTest(TradeTestCase):
    def test_an_empty_offer_is_not_a_deal(self):
        deal = self.trade()
        self.assertTrue(deal.is_empty)
        self.assertFalse(deal.is_valid)
        self.assertIn("Nothing is on the table.", deal.problems())

    def test_a_one_sided_gift_is_a_deal(self):
        deal = self.ready()
        self.assertTrue(deal.is_valid)
        self.assertEqual(deal.problems(), [])

    def test_cash_alone_is_a_deal(self):
        deal = self.trade()
        deal.set_cash(self.ada, 1)
        self.assertTrue(deal.is_valid)

    def test_no_partner_is_the_only_complaint(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        deal = Trade(players[0], players, self.deeds)
        self.assertEqual(deal.problems(), ["Choose somebody to trade with."])

    def test_cash_that_has_since_been_spent_is_caught(self):
        deal = self.trade()
        deal.set_cash(self.ada, 1500)
        self.ada.pay(100)
        self.assertFalse(deal.is_valid)
        self.assertIn("Ada has only $1,400.", deal.problems())

    def test_a_card_that_has_since_been_played_is_caught(self):
        self.ada.goojf_cards = 1
        deal = self.trade()
        deal.set_goojf(self.ada, 1)
        self.ada.goojf_cards = 0
        self.assertFalse(deal.is_valid)
        self.assertIn("Ada holds 0 jail card(s).", deal.problems())

    def test_a_deed_that_has_since_moved_is_caught(self):
        deal = self.ready()
        self.bob.add_property(self.deed(BALTIC))
        self.assertFalse(deal.is_valid)
        self.assertIn("Ada no longer owns Baltic Avenue.", deal.problems())

    def test_a_deed_built_on_since_the_draft_is_caught(self):
        self.give(self.ada, MEDITERRANEAN)
        deal = self.ready()
        self.deed(MEDITERRANEAN).houses = 1
        self.assertFalse(deal.is_valid)
        self.assertIn(
            "Baltic Avenue still has buildings on its group.", deal.problems()
        )


class ProposeTest(TradeTestCase):
    def test_proposing_hands_the_offer_over(self):
        deal = self.ready()
        self.assertTrue(deal.propose())
        self.assertEqual(deal.phase, REVIEW)
        self.assertFalse(deal.editable)

    def test_an_empty_offer_cannot_be_proposed(self):
        deal = self.trade()
        self.assertFalse(deal.propose())
        self.assertEqual(deal.phase, DRAFT)

    def test_an_offer_cannot_be_proposed_twice(self):
        deal = self.proposed()
        self.assertFalse(deal.propose())

    def test_nothing_moves_on_proposing(self):
        deal = self.proposed()
        self.assertIs(self.deed(BALTIC).owner, self.ada)
        self.assertEqual(self.bob.properties, [])

    def test_a_partnerless_trade_cannot_be_proposed(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        deal = Trade(players[0], players, self.deeds)
        self.assertFalse(deal.propose())


class AcceptTest(TradeTestCase):
    cash = (1500, 800)

    def test_a_deed_changes_hands(self):
        deal = self.proposed()
        self.assertTrue(deal.accept())
        self.assertIs(self.deed(BALTIC).owner, self.bob)
        self.assertIn(self.deed(BALTIC), self.bob.properties)
        self.assertNotIn(self.deed(BALTIC), self.ada.properties)

    def test_the_deal_closes_as_accepted(self):
        deal = self.proposed()
        deal.accept()
        self.assertEqual(deal.phase, CLOSED)
        self.assertEqual(deal.result, ACCEPTED)
        self.assertFalse(deal.open)

    def test_deeds_cross_in_both_directions(self):
        self.give(self.ada, BALTIC)
        self.give(self.bob, ORIENTAL)
        deal = self.trade()
        deal.add_deed(self.deed(BALTIC))
        deal.add_deed(self.deed(ORIENTAL))
        deal.propose()
        deal.accept()
        self.assertIs(self.deed(BALTIC).owner, self.bob)
        self.assertIs(self.deed(ORIENTAL).owner, self.ada)

    def test_cash_moves_the_way_it_was_offered(self):
        deal = self.trade()
        deal.set_cash(self.ada, 300)
        deal.propose()
        deal.accept()
        self.assertEqual(self.ada.cash, 1200)
        self.assertEqual(self.bob.cash, 1100)

    def test_cash_on_both_sides_nets_out(self):
        deal = self.trade()
        deal.set_cash(self.ada, 300)
        deal.set_cash(self.bob, 500)
        deal.propose()
        deal.accept()
        self.assertEqual(self.ada.cash, 1700)
        self.assertEqual(self.bob.cash, 600)

    def test_equal_cash_on_both_sides_cancels(self):
        deal = self.trade()
        deal.set_cash(self.ada, 300)
        deal.set_cash(self.bob, 300)
        deal.propose()
        deal.accept()
        self.assertEqual(self.ada.cash, 1500)
        self.assertEqual(self.bob.cash, 800)

    def test_a_jail_card_changes_hands(self):
        self.ada.goojf_cards = 1
        deal = self.trade()
        deal.set_goojf(self.ada, 1)
        deal.propose()
        deal.accept()
        self.assertEqual(self.ada.goojf_cards, 0)
        self.assertEqual(self.bob.goojf_cards, 1)

    def test_cards_cross_in_both_directions(self):
        self.ada.goojf_cards = 1
        self.bob.goojf_cards = 1
        deal = self.trade()
        deal.set_goojf(self.ada, 1)
        deal.set_goojf(self.bob, 1)
        deal.propose()
        deal.accept()
        self.assertEqual(self.ada.goojf_cards, 1)
        self.assertEqual(self.bob.goojf_cards, 1)

    def test_the_card_hook_is_what_moves_them_when_one_is_given(self):
        moves = []
        self.ada.goojf_cards = 2
        deal = self.trade(on_goojf=lambda g, t, n: moves.append((g.name, t.name, n)))
        deal.set_goojf(self.ada, 2)
        deal.propose()
        deal.accept()
        self.assertEqual(moves, [("Ada", "Bob", 2)])
        # The hook owns the counters entirely; the trade does not touch them.
        self.assertEqual(self.ada.goojf_cards, 2)

    def test_everything_moves_at_once(self):
        self.give(self.ada, BALTIC)
        self.give(self.bob, ORIENTAL)
        self.ada.goojf_cards = 1
        deal = self.trade()
        deal.add_deed(self.deed(BALTIC))
        deal.add_deed(self.deed(ORIENTAL))
        deal.set_cash(self.ada, 100)
        deal.set_goojf(self.ada, 1)
        deal.propose()
        self.assertTrue(deal.accept())
        self.assertIs(self.deed(BALTIC).owner, self.bob)
        self.assertIs(self.deed(ORIENTAL).owner, self.ada)
        self.assertEqual(self.ada.cash, 1400)
        self.assertEqual(self.bob.cash, 900)
        self.assertEqual(self.bob.goojf_cards, 1)

    def test_a_mortgaged_deed_arrives_still_mortgaged(self):
        self.deed(BALTIC).mortgaged = True
        deal = self.proposed()
        deal.accept()
        self.assertIs(self.deed(BALTIC).owner, self.bob)
        self.assertTrue(self.deed(BALTIC).mortgaged)

    def test_a_trade_can_complete_a_monopoly(self):
        self.give(self.ada, BALTIC)
        self.give(self.bob, MEDITERRANEAN)
        deal = self.trade()
        deal.add_deed(self.deed(BALTIC))
        deal.propose()
        deal.accept()
        self.assertTrue(self.bob.has_monopoly("brown", self.deeds))

    def test_a_draft_cannot_be_accepted(self):
        deal = self.ready()
        self.assertFalse(deal.accept())
        self.assertIs(self.deed(BALTIC).owner, self.ada)

    def test_an_accepted_deal_cannot_be_accepted_again(self):
        deal = self.proposed()
        deal.accept()
        self.assertFalse(deal.accept())

    def test_a_board_that_moved_under_the_offer_stops_the_swap(self):
        deal = self.proposed()
        self.ada.pay(1500)
        deal.mine.cash = 10  # as if the wallet had emptied after proposing
        self.assertFalse(deal.accept())
        self.assertIs(self.deed(BALTIC).owner, self.ada, "nothing half-moved")
        self.assertEqual(deal.phase, REVIEW)


class RejectAndCancelTest(TradeTestCase):
    def test_rejecting_closes_it_with_nothing_moved(self):
        deal = self.proposed()
        self.assertTrue(deal.reject())
        self.assertEqual(deal.phase, CLOSED)
        self.assertEqual(deal.result, REJECTED)
        self.assertIs(self.deed(BALTIC).owner, self.ada)

    def test_a_draft_cannot_be_rejected(self):
        deal = self.ready()
        self.assertFalse(deal.reject())
        self.assertEqual(deal.phase, DRAFT)

    def test_cancelling_a_draft_closes_it(self):
        deal = self.ready()
        self.assertTrue(deal.cancel())
        self.assertEqual(deal.result, CANCELLED)

    def test_cancelling_before_a_partner_closes_it(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        deal = Trade(players[0], players, self.deeds)
        self.assertTrue(deal.cancel())
        self.assertEqual(deal.result, CANCELLED)

    def test_cancelling_an_offer_under_review_closes_it(self):
        deal = self.proposed()
        self.assertTrue(deal.cancel())
        self.assertEqual(deal.result, CANCELLED)
        self.assertIs(self.deed(BALTIC).owner, self.ada)

    def test_a_closed_deal_stays_closed(self):
        deal = self.ready()
        deal.cancel()
        self.assertFalse(deal.cancel())
        self.assertFalse(deal.propose())
        self.assertFalse(deal.accept())
        self.assertFalse(deal.editable)


class OfferTest(TradeTestCase):
    def test_an_empty_offer_knows_it(self):
        self.assertTrue(Offer(self.ada).is_empty)

    def test_cash_alone_is_not_empty(self):
        self.assertFalse(Offer(self.ada, cash=1).is_empty)

    def test_a_card_alone_is_not_empty(self):
        self.assertFalse(Offer(self.ada, goojf=1).is_empty)

    def test_a_deed_alone_is_not_empty(self):
        self.assertFalse(Offer(self.ada, deeds=[self.deed(BALTIC)]).is_empty)

    def test_holds_compares_by_identity(self):
        offer = Offer(self.ada, deeds=[self.deed(BALTIC)])
        self.assertTrue(offer.holds(self.deed(BALTIC)))
        self.assertFalse(offer.holds(self.deed(READING)))

    def test_offer_finds_a_player_s_column(self):
        deal = self.trade()
        self.assertIs(deal.offer(self.ada), deal.mine)
        self.assertIs(deal.offer(self.bob), deal.theirs)


class WordsTest(TradeTestCase):
    def test_nothing_reads_as_nothing(self):
        self.assertEqual(summarise_offer(Offer(self.ada)), NOTHING)
        self.assertEqual(summarise_offer(None), NOTHING)

    def test_a_deed_reads_by_name(self):
        offer = Offer(self.ada, deeds=[self.deed(BALTIC)])
        self.assertEqual(summarise_offer(offer), "Baltic Avenue")

    def test_everything_is_listed_in_turn(self):
        offer = Offer(self.ada, cash=50, goojf=1, deeds=[self.deed(BALTIC)])
        self.assertEqual(summarise_offer(offer), "Baltic Avenue, $50, 1 jail card")

    def test_several_cards_are_plural(self):
        self.assertEqual(summarise_offer(Offer(self.ada, goojf=2)), "2 jail cards")

    def test_big_money_is_grouped(self):
        self.assertEqual(summarise_offer(Offer(self.ada, cash=1500)), "$1,500")

    def test_describe_names_both_sides(self):
        deal = self.ready()
        deal.set_cash(self.bob, 200)
        self.assertEqual(
            describe(deal), "Ada gives Baltic Avenue; Bob gives $200."
        )

    def test_describe_before_a_partner_says_so(self):
        players = [Player(n, 1500, t) for n, t in zip(NAMES, TOKENS)]
        deal = Trade(players[0], players, self.deeds)
        self.assertIn("looking for a trade", describe(deal))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
