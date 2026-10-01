"""Phase 13 tests: the forced sale and the settlement.

:mod:`monopoly.bankruptcy` is the rules on their own -- what a player can be
made to raise, and where everything goes when even that is not enough. No
game and no turn order here, and no pygame either; ``test_bankruptcy_game.py``
covers the join to :class:`monopoly.game.Game`.

The board is the real one from ``data/spaces.json``, so the numbers are the
real numbers: Mediterranean mortgages for $30, Baltic for $30, Boardwalk for
$200, and a brown house costs $50 (so it sells back for $25).
"""

from __future__ import annotations

import unittest

from monopoly.bankruptcy import (
    Settlement,
    describe,
    mortgage,
    raise_cash,
    sell_all_buildings,
    settle,
)
from monopoly.building import HOTEL_SUPPLY, HOUSE_SUPPLY, Bank
from monopoly.player import Player
from monopoly.property import build_properties

TOKENS = ("red", "blue", "green")
NAMES = ("Ada", "Bob", "Cleo")

#: Board indices used below.
MEDITERRANEAN = 1
BALTIC = 3
READING = 5
ORIENTAL = 6
VERMONT = 8
CONNECTICUT = 9
ELECTRIC = 12
PARK_PLACE = 37
BOARDWALK = 39


class BankruptcyTestCase(unittest.TestCase):
    """Ada, Bob and a fresh board with a full box of buildings."""

    cash = (1500, 1500, 1500)

    def setUp(self):
        self.properties = build_properties()
        self.bank = Bank()
        self.players = [
            Player(n, c, t) for n, c, t in zip(NAMES, self.cash, TOKENS)
        ]
        self.ada, self.bob, self.cleo = self.players

    def deed(self, index):
        return next(d for d in self.properties if d.index == index)

    def give(self, player, *indices):
        """Hand ``player`` the deeds at ``indices``; returns them in order."""
        deeds = [self.deed(i) for i in indices]
        for deed in deeds:
            player.add_property(deed)
        return deeds

    def build(self, deed, houses=0, *, hotel=False):
        """Stand buildings on ``deed``, taking them out of the box."""
        if hotel:
            deed.has_hotel = True
            self.bank.hotels -= 1
        else:
            deed.houses = houses
            self.bank.houses -= houses


class SellAllBuildingsTest(BankruptcyTestCase):
    def test_nothing_standing_raises_nothing(self):
        self.give(self.ada, MEDITERRANEAN, BALTIC)
        self.assertEqual(sell_all_buildings(self.ada, self.bank), 0)
        self.assertEqual(self.ada.cash, 1500)

    def test_houses_sell_back_at_half_price(self):
        brown = self.give(self.ada, MEDITERRANEAN, BALTIC)
        self.build(brown[0], 3)
        self.build(brown[1], 2)
        # Five brown houses at $50 each, back at $25 each.
        self.assertEqual(sell_all_buildings(self.ada, self.bank), 125)
        self.assertEqual(self.ada.cash, 1500 + 125)

    def test_the_houses_go_back_in_the_box(self):
        brown = self.give(self.ada, MEDITERRANEAN, BALTIC)
        self.build(brown[0], 4)
        self.build(brown[1], 1)
        self.assertEqual(self.bank.houses, HOUSE_SUPPLY - 5)
        sell_all_buildings(self.ada, self.bank)
        self.assertEqual(self.bank.houses, HOUSE_SUPPLY)

    def test_the_lots_are_left_bare(self):
        brown = self.give(self.ada, MEDITERRANEAN, BALTIC)
        self.build(brown[0], 4)
        self.build(brown[1], hotel=True)
        sell_all_buildings(self.ada, self.bank)
        for deed in brown:
            self.assertEqual((deed.houses, deed.has_hotel), (0, False))
            self.assertEqual(deed.building_level, 0)

    def test_a_hotel_goes_back_as_a_hotel(self):
        """It is not stepped down to four houses -- the lot is cleared."""
        board = self.give(self.ada, PARK_PLACE, BOARDWALK)
        self.build(board[1], hotel=True)
        self.bank.houses = 0  # and no houses to stand it back up with
        raised = sell_all_buildings(self.ada, self.bank)
        self.assertEqual(raised, 5 * 200 // 2, "five dark-blue houses, half back")
        self.assertEqual(self.bank.hotels, HOTEL_SUPPLY)
        self.assertEqual(self.bank.houses, 0, "a hotel takes no houses with it")

    def test_only_this_player_is_stripped(self):
        mine = self.give(self.ada, MEDITERRANEAN)[0]
        theirs = self.give(self.bob, BALTIC)[0]
        self.build(mine, 1)
        self.build(theirs, 1)
        sell_all_buildings(self.ada, self.bank)
        self.assertEqual(theirs.houses, 1)
        self.assertEqual(self.bob.cash, 1500)

    def test_the_sale_matches_what_liquidation_value_promised(self):
        brown = self.give(self.ada, MEDITERRANEAN, BALTIC)
        self.build(brown[0], 4)
        self.build(brown[1], hotel=True)
        expected = self.ada.liquidation_value()
        raised = sell_all_buildings(self.ada, self.bank)
        mortgages = sum(d.mortgage_value for d in self.ada.properties)
        self.assertEqual(1500 + raised + mortgages, expected)


class MortgageTest(BankruptcyTestCase):
    def test_mortgaging_pays_the_deed_value(self):
        deed = self.give(self.ada, BOARDWALK)[0]
        self.assertEqual(mortgage(deed), 200)
        self.assertTrue(deed.mortgaged)
        self.assertEqual(self.ada.cash, 1700)

    def test_a_mortgaged_deed_raises_nothing_twice(self):
        deed = self.give(self.ada, BOARDWALK)[0]
        mortgage(deed)
        self.assertEqual(mortgage(deed), 0)
        self.assertEqual(self.ada.cash, 1700)

    def test_an_ownerless_deed_raises_nothing(self):
        self.assertEqual(mortgage(self.deed(BOARDWALK)), 0)
        self.assertFalse(self.deed(BOARDWALK).mortgaged)

    def test_a_built_on_deed_cannot_be_mortgaged(self):
        deed = self.give(self.ada, BOARDWALK)[0]
        self.build(deed, 1)
        with self.assertRaises(ValueError):
            mortgage(deed)
        self.assertFalse(deed.mortgaged)

    def test_a_hotel_blocks_it_too(self):
        deed = self.give(self.ada, BOARDWALK)[0]
        self.build(deed, hotel=True)
        with self.assertRaises(ValueError):
            mortgage(deed)

    def test_a_mortgaged_deed_earns_no_rent(self):
        deed = self.give(self.ada, BOARDWALK)[0]
        self.assertGreater(deed.current_rent(), 0)
        mortgage(deed)
        self.assertEqual(deed.current_rent(), 0)


class RaiseCashTest(BankruptcyTestCase):
    cash = (0, 1500, 1500)

    def test_a_player_who_already_has_it_sells_nothing(self):
        self.ada.cash = 100
        deed = self.give(self.ada, BOARDWALK)[0]
        self.assertEqual(raise_cash(self.ada, 100, self.bank), 0)
        self.assertFalse(deed.mortgaged)

    def test_one_deed_is_enough_for_a_small_debt(self):
        deeds = self.give(self.ada, MEDITERRANEAN, BALTIC, BOARDWALK)
        self.assertEqual(raise_cash(self.ada, 20, self.bank), 30)
        self.assertTrue(deeds[0].mortgaged, "board order: Mediterranean first")
        self.assertFalse(deeds[1].mortgaged, "and it stops as soon as it can")
        self.assertFalse(deeds[2].mortgaged)
        self.assertEqual(self.ada.cash, 30)

    def test_deeds_are_mortgaged_in_board_order(self):
        self.give(self.ada, BOARDWALK, MEDITERRANEAN, BALTIC)
        raise_cash(self.ada, 60, self.bank)
        self.assertEqual(
            [d.name for d in self.ada.properties if d.mortgaged],
            ["Mediterranean Avenue", "Baltic Avenue"],
        )
        self.assertFalse(self.deed(BOARDWALK).mortgaged)

    def test_the_buildings_go_first_even_for_a_small_debt(self):
        """A forced sale is all-or-nothing on buildings, by design."""
        brown = self.give(self.ada, MEDITERRANEAN, BALTIC)
        self.build(brown[0], 1)
        self.assertEqual(raise_cash(self.ada, 10, self.bank), 25)
        self.assertEqual(brown[0].houses, 0)
        self.assertFalse(brown[0].mortgaged, "$25 already covers $10")

    def test_buildings_first_then_deeds(self):
        brown = self.give(self.ada, MEDITERRANEAN, BALTIC)
        self.build(brown[0], 2)
        self.build(brown[1], 2)
        # $100 of houses, then Mediterranean's $30 to reach $120.
        self.assertEqual(raise_cash(self.ada, 120, self.bank), 130)
        self.assertTrue(brown[0].mortgaged)
        self.assertFalse(brown[1].mortgaged)

    def test_stripping_everything_reaches_the_liquidation_value(self):
        self.give(self.ada, MEDITERRANEAN, BALTIC, BOARDWALK, READING)
        self.build(self.deed(MEDITERRANEAN), 2)
        target = self.ada.liquidation_value()
        self.assertEqual(raise_cash(self.ada, target, self.bank), target)
        self.assertEqual(self.ada.cash, target)
        self.assertTrue(all(d.mortgaged for d in self.ada.properties))

    def test_a_target_out_of_reach_raises_everything_there_is(self):
        self.give(self.ada, MEDITERRANEAN)
        self.assertFalse(self.ada.can_raise(1000))
        self.assertEqual(raise_cash(self.ada, 1000, self.bank), 30)
        self.assertEqual(self.ada.cash, 30, "there was simply no more")

    def test_a_negative_target_is_refused(self):
        with self.assertRaises(ValueError):
            raise_cash(self.ada, -1, self.bank)

    def test_nothing_to_sell_raises_nothing(self):
        self.assertEqual(raise_cash(self.ada, 50, self.bank), 0)
        self.assertEqual(self.ada.cash, 0)


class SettleToPlayerTest(BankruptcyTestCase):
    """A debt owed to another player: everything goes to the creditor."""

    def setUp(self):
        super().setUp()
        self.ada.cash = 40
        self.deeds = self.give(self.ada, MEDITERRANEAN, BALTIC, READING)
        self.result = None

    def run_settlement(self, amount=500):
        self.result = settle(self.ada, self.bob, amount, self.bank)
        return self.result

    def test_the_deeds_change_hands(self):
        self.run_settlement()
        for deed in self.deeds:
            self.assertIs(deed.owner, self.bob)
            self.assertIn(deed, self.bob.properties)
        self.assertEqual(self.ada.properties, [])

    def test_the_cash_changes_hands(self):
        self.run_settlement()
        self.assertEqual(self.ada.cash, 0)
        self.assertEqual(self.bob.cash, 1500 + 40)

    def test_a_mortgaged_deed_transfers_as_it_stands(self):
        mortgage(self.deeds[0])  # +$30 to Ada, before the wind-up
        self.run_settlement()
        self.assertIs(self.deeds[0].owner, self.bob)
        self.assertTrue(self.deeds[0].mortgaged, "the creditor takes it as-is")

    def test_the_buildings_are_sold_before_the_transfer(self):
        self.build(self.deeds[0], 3)
        self.build(self.deeds[1], 3)
        result = self.run_settlement()
        self.assertEqual(result.buildings, 6 * 25)
        self.assertEqual(self.bob.cash, 1500 + 40 + 150)
        self.assertEqual(self.bank.houses, HOUSE_SUPPLY)
        for deed in self.deeds[:2]:
            self.assertEqual(deed.building_level, 0)

    def test_the_creditor_is_never_handed_a_building(self):
        self.build(self.deeds[0], 4)
        self.run_settlement()
        self.assertEqual(
            sum(d.buildings_value for d in self.bob.properties), 0
        )

    def test_jail_cards_go_with_everything_else(self):
        self.ada.goojf_cards = 2
        result = self.run_settlement()
        self.assertEqual(result.goojf, 2)
        self.assertEqual(self.ada.goojf_cards, 0)
        self.assertEqual(self.bob.goojf_cards, 2)

    def test_a_mover_is_used_when_one_is_given(self):
        self.ada.goojf_cards = 1
        moved = []
        settle(
            self.ada,
            self.bob,
            10,
            self.bank,
            on_goojf=lambda g, t, n: moved.append((g, t, n)) or n,
        )
        self.assertEqual(moved, [(self.ada, self.bob, 1)])

    def test_the_mover_is_left_alone_when_there_are_no_cards(self):
        called = []
        settle(self.ada, self.bob, 10, self.bank, on_goojf=lambda *a: called.append(a))
        self.assertEqual(called, [])

    def test_the_debtor_is_marked_bankrupt(self):
        self.run_settlement()
        self.assertTrue(self.ada.is_bankrupt)
        self.assertFalse(self.bob.is_bankrupt)

    def test_the_token_stays_where_it_fell(self):
        self.ada.position = 24
        self.run_settlement()
        self.assertEqual(self.ada.position, 24, "the board stops drawing it")

    def test_the_settlement_records_what_moved(self):
        result = self.run_settlement(amount=321)
        self.assertIsInstance(result, Settlement)
        self.assertIs(result.debtor, self.ada)
        self.assertIs(result.creditor, self.bob)
        self.assertEqual(result.amount, 321)
        self.assertEqual(result.cash, 40)
        self.assertEqual([d.name for d in result.deeds], [d.name for d in self.deeds])
        self.assertFalse(result.to_bank)

    def test_the_deeds_are_recorded_in_board_order(self):
        result = self.run_settlement()
        self.assertEqual(
            [d.index for d in result.deeds], sorted(d.index for d in result.deeds)
        )

    def test_the_value_taken_is_cash_plus_deeds(self):
        result = self.run_settlement()
        self.assertEqual(result.value, 40 + 60 + 60 + 200)

    def test_a_mortgaged_deed_counts_at_its_mortgage_value(self):
        mortgage(self.deeds[2])  # Reading Railroad, $100
        result = self.run_settlement()
        self.assertEqual(result.value, 40 + 100 + 60 + 60 + 100)

    def test_settling_twice_is_refused(self):
        self.run_settlement()
        with self.assertRaises(ValueError):
            settle(self.ada, self.bob, 10, self.bank)

    def test_a_player_cannot_be_their_own_creditor(self):
        with self.assertRaises(ValueError):
            settle(self.ada, self.ada, 10, self.bank)

    def test_a_negative_debt_is_refused(self):
        with self.assertRaises(ValueError):
            settle(self.ada, self.bob, -1, self.bank)

    def test_nobody_else_is_touched(self):
        self.run_settlement()
        self.assertEqual(self.cleo.cash, 1500)
        self.assertEqual(self.cleo.properties, [])
        self.assertFalse(self.cleo.is_bankrupt)


class SettleToBankTest(BankruptcyTestCase):
    """A debt owed to the bank: the deeds go back on the shelf."""

    def setUp(self):
        super().setUp()
        self.ada.cash = 25
        self.deeds = self.give(self.ada, ORIENTAL, VERMONT, ELECTRIC)

    def test_the_deeds_become_unowned(self):
        settle(self.ada, None, 300, self.bank)
        for deed in self.deeds:
            self.assertIsNone(deed.owner)
        self.assertEqual(self.ada.properties, [])

    def test_a_returned_deed_is_no_longer_mortgaged(self):
        mortgage(self.deeds[0])
        settle(self.ada, None, 300, self.bank)
        self.assertFalse(
            self.deeds[0].mortgaged, "the bank's shelf holds it at list price"
        )

    def test_the_cash_leaves_the_game(self):
        before = sum(p.cash for p in self.players)
        settle(self.ada, None, 300, self.bank)
        self.assertEqual(self.ada.cash, 0)
        self.assertEqual(sum(p.cash for p in self.players), before - 25)

    def test_the_buildings_go_back_in_the_box(self):
        self.give(self.ada, CONNECTICUT)  # the light blues, whole
        for index in (ORIENTAL, VERMONT, CONNECTICUT):
            self.build(self.deed(index), 3)
        self.assertEqual(self.bank.houses, HOUSE_SUPPLY - 9)
        settle(self.ada, None, 300, self.bank)
        self.assertEqual(self.bank.houses, HOUSE_SUPPLY)
        self.assertEqual(self.bank.hotels, HOTEL_SUPPLY)

    def test_the_building_money_is_still_the_debtors_first(self):
        self.build(self.deeds[0], 2)  # $100 of light-blue houses -> $50 back
        result = settle(self.ada, None, 300, self.bank)
        self.assertEqual(result.buildings, 50)
        self.assertEqual(result.cash, 75, "$25 in hand plus the $50 raised")

    def test_jail_cards_go_nowhere_without_a_mover(self):
        self.ada.goojf_cards = 1
        result = settle(self.ada, None, 300, self.bank)
        self.assertEqual(result.goojf, 1)
        self.assertEqual(self.ada.goojf_cards, 0)

    def test_the_mover_is_told_there_is_no_creditor(self):
        self.ada.goojf_cards = 2
        seen = []
        settle(
            self.ada,
            None,
            300,
            self.bank,
            on_goojf=lambda g, t, n: seen.append((g, t, n)) or n,
        )
        self.assertEqual(seen, [(self.ada, None, 2)])

    def test_the_settlement_says_it_went_to_the_bank(self):
        result = settle(self.ada, None, 300, self.bank)
        self.assertTrue(result.to_bank)
        self.assertIsNone(result.creditor)

    def test_the_debtor_is_marked_bankrupt(self):
        settle(self.ada, None, 300, self.bank)
        self.assertTrue(self.ada.is_bankrupt)


class SettleWithNothingTest(BankruptcyTestCase):
    """The commonest bankruptcy of all: no deeds, no buildings, no cash."""

    cash = (0, 1500, 1500)

    def test_a_player_with_nothing_still_settles(self):
        result = settle(self.ada, self.bob, 200, self.bank)
        self.assertEqual((result.cash, result.deeds, result.goojf), (0, (), 0))
        self.assertEqual(result.buildings, 0)
        self.assertTrue(self.ada.is_bankrupt)
        self.assertEqual(self.bob.cash, 1500)

    def test_the_value_of_nothing_is_nothing(self):
        self.assertEqual(settle(self.ada, None, 200, self.bank).value, 0)


class DescribeTest(BankruptcyTestCase):
    def test_a_full_haul_reads_as_one_line(self):
        self.ada.cash = 40
        self.give(self.ada, MEDITERRANEAN, BALTIC)
        self.ada.goojf_cards = 1
        result = settle(self.ada, self.bob, 500, self.bank)
        self.assertEqual(
            describe(result), "Ada hands $40, 2 deeds, 1 jail card to Bob."
        )

    def test_one_of_each_is_singular(self):
        self.ada.cash = 0
        self.give(self.ada, BOARDWALK)
        result = settle(self.ada, self.bob, 500, self.bank)
        self.assertEqual(describe(result), "Ada hands 1 deed to Bob.")

    def test_the_bank_is_named_as_the_taker(self):
        self.ada.cash = 7
        result = settle(self.ada, None, 500, self.bank)
        self.assertEqual(describe(result), "Ada hands $7 to the bank.")

    def test_nothing_at_all_is_said_so(self):
        self.ada.cash = 0
        result = settle(self.ada, self.bob, 500, self.bank)
        self.assertEqual(describe(result), "Ada hands nothing to Bob.")

    def test_big_numbers_are_grouped(self):
        self.ada.cash = 12_345
        result = settle(self.ada, None, 500, self.bank)
        self.assertIn("$12,345", describe(result))


if __name__ == "__main__":
    unittest.main()
