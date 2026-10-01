"""Phase 9 tests: houses, hotels, the bank's supply and the build draft.

Everything here is pure rules -- :mod:`monopoly.building` imports no pygame,
so a whole build is planned, priced and committed without a surface. The build
*screen* is tested separately in ``test_build_screen.py``, and the Build
button's place in the turn loop in ``test_build_game.py``.

The board is the real one from ``data/spaces.json``, so the prices are the
real prices: brown houses cost $50, orange $100, dark blue $200.
"""

from __future__ import annotations

import unittest

from monopoly.building import (
    HOTEL_SUPPLY,
    HOUSE_SUPPLY,
    Bank,
    BuildPlan,
    buildable_groups,
    describe_plan,
    total_buildings,
)
from monopoly.player import Player
from monopoly.property import HOTEL_LEVEL, MAX_HOUSES, build_properties

#: Board indices of the groups the tests build on.
BROWN = (1, 3)
LIGHT_BLUE = (6, 8, 9)
ORANGE = (16, 18, 19)
DARK_BLUE = (37, 39)
RAILROADS = (5, 15, 25, 35)


def make_board():
    """A fresh set of deeds and a fresh bank."""
    return build_properties(), Bank()


def give(player: Player, properties, indices) -> list:
    """Hand ``player`` every deed at ``indices``; return them in board order."""
    deeds = [p for p in properties if p.index in indices]
    for deed in deeds:
        player.add_property(deed)
    return sorted(deeds, key=lambda p: p.index)


class BankTest(unittest.TestCase):
    def test_a_fresh_bank_holds_the_standard_set(self):
        bank = Bank()
        self.assertEqual(bank.houses, HOUSE_SUPPLY)
        self.assertEqual(bank.hotels, HOTEL_SUPPLY)
        self.assertEqual((HOUSE_SUPPLY, HOTEL_SUPPLY), (32, 12))

    def test_reset_puts_every_building_back_in_the_box(self):
        bank = Bank(houses=3, hotels=0)
        bank.reset()
        self.assertEqual((bank.houses, bank.hotels), (HOUSE_SUPPLY, HOTEL_SUPPLY))


class BuildableGroupsTest(unittest.TestCase):
    def setUp(self):
        self.properties, self.bank = make_board()
        self.ada = Player("Ada", 1500, "red")
        self.bob = Player("Bob", 1500, "blue")

    def test_owning_nothing_builds_nothing(self):
        self.assertEqual(buildable_groups(self.ada, self.properties), [])

    def test_a_part_group_does_not_qualify(self):
        give(self.ada, self.properties, (1,))
        self.assertEqual(buildable_groups(self.ada, self.properties), [])

    def test_a_whole_group_qualifies(self):
        give(self.ada, self.properties, BROWN)
        self.assertEqual(buildable_groups(self.ada, self.properties), ["brown"])

    def test_a_mortgaged_lot_disqualifies_its_group(self):
        lots = give(self.ada, self.properties, BROWN)
        lots[0].mortgaged = True
        self.assertEqual(buildable_groups(self.ada, self.properties), [])

    def test_groups_come_back_in_board_order(self):
        give(self.ada, self.properties, ORANGE)
        give(self.ada, self.properties, BROWN)
        self.assertEqual(
            buildable_groups(self.ada, self.properties), ["brown", "orange"]
        )

    def test_railroads_never_qualify(self):
        give(self.ada, self.properties, RAILROADS)
        self.assertEqual(buildable_groups(self.ada, self.properties), [])

    def test_another_players_group_is_not_yours(self):
        give(self.bob, self.properties, BROWN)
        self.assertEqual(buildable_groups(self.ada, self.properties), [])


class PlanTestCase(unittest.TestCase):
    """A player holding the brown group, with cash to spend on it."""

    cash = 1500
    groups = (BROWN,)

    def setUp(self):
        self.properties, self.bank = make_board()
        self.ada = Player("Ada", self.cash, "red")
        self.lots = []
        for group in self.groups:
            self.lots.extend(give(self.ada, self.properties, group))
        self.plan = self.new_plan()

    def new_plan(self) -> BuildPlan:
        return BuildPlan(self.ada, self.properties, self.bank)

    def build(self, *deeds) -> None:
        """Add one building to each deed in turn, asserting each is legal."""
        for deed in deeds:
            self.assertTrue(self.plan.add(deed), f"could not build on {deed.name}")

    def sell(self, *deeds) -> None:
        for deed in deeds:
            self.assertTrue(self.plan.remove(deed), f"could not sell on {deed.name}")

    def to_hotel(self, *deeds) -> None:
        """Take every named lot from bare ground to a hotel, evenly."""
        for _ in range(HOTEL_LEVEL):
            for deed in deeds:
                self.build(deed)


class DraftTest(PlanTestCase):
    def test_a_fresh_plan_starts_from_the_board(self):
        self.assertEqual(self.plan.groups, ["brown"])
        self.assertEqual(self.plan.all_lots, self.lots)
        self.assertEqual([self.plan.level(lot) for lot in self.lots], [0, 0])
        self.assertFalse(self.plan.changed)
        self.assertEqual(self.plan.cost, 0)

    def test_a_plan_with_no_group_is_empty(self):
        plan = BuildPlan(Player("Bob", 1500, "blue"), self.properties, self.bank)
        self.assertTrue(plan.is_empty)
        self.assertEqual(plan.all_lots, [])
        self.assertFalse(plan.changed)

    def test_a_plan_mirrors_the_banks_stock(self):
        self.bank.houses = 7
        self.bank.hotels = 2
        plan = self.new_plan()
        self.assertEqual((plan.houses, plan.hotels), (7, 2))

    def test_building_does_not_touch_the_board_until_commit(self):
        self.build(self.lots[0])
        self.assertEqual(self.plan.level(self.lots[0]), 1)
        self.assertEqual(self.lots[0].houses, 0)
        self.assertEqual(self.ada.cash, self.cash)
        self.assertEqual(self.bank.houses, HOUSE_SUPPLY)

    def test_a_draft_that_differs_is_changed(self):
        self.build(self.lots[0])
        self.assertTrue(self.plan.changed)

    def test_reset_throws_the_draft_away(self):
        self.build(self.lots[0], self.lots[1])
        self.plan.reset()
        self.assertFalse(self.plan.changed)
        self.assertEqual(self.plan.cost, 0)
        self.assertEqual(self.plan.houses, HOUSE_SUPPLY)

    def test_level_of_a_deed_outside_the_plan_reads_the_board(self):
        other = next(p for p in self.properties if p.index == 39)
        other.houses = 3
        self.assertEqual(self.plan.level(other), 3)

    def test_standing_counts_the_drafts_buildings(self):
        self.to_hotel(*self.lots)
        self.assertEqual(self.plan.standing(), (0, 2))
        self.sell(self.lots[0])
        self.assertEqual(self.plan.standing(), (4, 1))


class EvenBuildTest(PlanTestCase):
    def test_the_first_house_may_go_on_either_lot(self):
        self.assertTrue(self.plan.can_add(self.lots[0]))
        self.assertTrue(self.plan.can_add(self.lots[1]))

    def test_a_second_house_cannot_go_on_the_same_lot(self):
        self.build(self.lots[0])
        self.assertFalse(self.plan.can_add(self.lots[0]))
        self.assertTrue(self.plan.can_add(self.lots[1]))

    def test_the_lot_reopens_once_the_group_is_level(self):
        self.build(self.lots[0], self.lots[1])
        self.assertTrue(self.plan.can_add(self.lots[0]))

    def test_add_refuses_rather_than_raises(self):
        self.build(self.lots[0])
        self.assertFalse(self.plan.add(self.lots[0]))
        self.assertEqual(self.plan.level(self.lots[0]), 1)
        self.assertEqual(self.plan.cost, 50)

    def test_selling_comes_off_the_tallest_lot_first(self):
        self.build(self.lots[0], self.lots[1], self.lots[0])
        self.assertTrue(self.plan.can_remove(self.lots[0]))
        self.assertFalse(self.plan.can_remove(self.lots[1]))

    def test_a_bare_lot_has_nothing_to_sell(self):
        self.assertFalse(self.plan.can_remove(self.lots[0]))
        self.assertFalse(self.plan.remove(self.lots[0]))

    def test_a_deed_outside_the_plan_can_be_neither_built_nor_sold(self):
        other = next(p for p in self.properties if p.index == 39)
        self.assertFalse(self.plan.can_add(other))
        self.assertFalse(self.plan.can_remove(other))
        self.assertFalse(self.plan.add(other))
        self.assertFalse(self.plan.remove(other))


class HotelTest(PlanTestCase):
    def test_the_fifth_building_is_a_hotel(self):
        self.to_hotel(*self.lots)
        self.assertEqual(self.plan.level(self.lots[0]), HOTEL_LEVEL)
        self.assertEqual(self.plan.level(self.lots[1]), HOTEL_LEVEL)

    def test_a_hotel_is_the_top_of_the_lot(self):
        self.to_hotel(*self.lots)
        self.assertFalse(self.plan.can_add(self.lots[0]))

    def test_a_hotel_hands_its_four_houses_back(self):
        for _ in range(MAX_HOUSES):
            self.build(*self.lots)
        self.assertEqual(self.plan.houses, HOUSE_SUPPLY - 8)
        self.build(self.lots[0])
        self.assertEqual(self.plan.houses, HOUSE_SUPPLY - 4)
        self.assertEqual(self.plan.hotels, HOTEL_SUPPLY - 1)

    def test_a_hotel_costs_one_more_house_payment(self):
        self.to_hotel(self.lots[0], self.lots[1])
        self.assertEqual(self.plan.cost, 10 * 50)

    def test_selling_a_hotel_stands_four_houses_back_up(self):
        self.to_hotel(*self.lots)
        self.sell(self.lots[0])
        self.assertEqual(self.plan.level(self.lots[0]), MAX_HOUSES)
        self.assertEqual(self.plan.hotels, HOTEL_SUPPLY - 1)

    def test_a_hotel_cannot_be_sold_when_the_box_is_short_of_houses(self):
        self.to_hotel(*self.lots)
        self.plan.commit()
        self.bank.houses = MAX_HOUSES - 1  # the other players hold the rest
        plan = self.new_plan()
        self.assertFalse(plan.can_remove(self.lots[0]))
        self.assertFalse(plan.remove(self.lots[0]))

    def test_the_fourth_returned_house_unblocks_the_hotel(self):
        self.to_hotel(*self.lots)
        self.plan.commit()
        self.bank.houses = MAX_HOUSES
        plan = self.new_plan()
        self.assertTrue(plan.remove(self.lots[0]))
        self.assertEqual(plan.houses, 0)

    def test_a_hotel_unwinds_for_five_half_price_houses(self):
        self.to_hotel(*self.lots)
        self.plan.commit()
        plan = self.new_plan()
        for _ in range(HOTEL_LEVEL):  # both lots come down together
            for lot in self.lots:
                self.assertTrue(plan.remove(lot))
        self.assertEqual([plan.level(lot) for lot in self.lots], [0, 0])
        self.assertEqual(plan.cost, -(2 * HOTEL_LEVEL * 25))


class SupplyTest(PlanTestCase):
    groups = (BROWN, LIGHT_BLUE, ORANGE)
    cash = 10_000

    def test_the_last_house_stops_everybody(self):
        self.bank.houses = 1
        self.plan = self.new_plan()
        self.build(self.lots[0])
        self.assertEqual(self.plan.houses, 0)
        for lot in self.plan.all_lots:
            self.assertFalse(self.plan.can_add(lot))

    def test_selling_a_house_puts_it_back_for_the_next_lot(self):
        self.bank.houses = 1
        self.plan = self.new_plan()
        self.build(self.lots[0])
        self.sell(self.lots[0])
        self.assertEqual(self.plan.houses, 1)
        self.assertTrue(self.plan.can_add(self.lots[1]))

    def test_the_last_hotel_cannot_be_doubled(self):
        self.bank.hotels = 0
        self.plan = self.new_plan()
        for _ in range(MAX_HOUSES):
            self.build(self.lots[0], self.lots[1])
        self.assertFalse(self.plan.can_add(self.lots[0]))

    def test_building_out_a_group_never_overdraws_the_box(self):
        self.to_hotel(*self.plan.all_lots)
        self.assertGreaterEqual(self.plan.houses, 0)
        self.assertGreaterEqual(self.plan.hotels, 0)
        self.plan.commit()
        self.assertEqual(self.bank.hotels, HOTEL_SUPPLY - len(self.lots))
        self.assertEqual(self.bank.houses, HOUSE_SUPPLY)


class CashTest(PlanTestCase):
    cash = 120

    def test_a_lot_beyond_the_players_cash_is_closed(self):
        self.build(self.lots[0], self.lots[1])  # $100 of $120
        self.assertEqual(self.plan.cost, 100)
        self.assertFalse(self.plan.can_add(self.lots[0]))

    def test_undoing_a_queued_house_costs_nothing(self):
        self.build(self.lots[0])
        self.assertEqual(self.plan.cost, 50)
        self.sell(self.lots[0])
        self.assertEqual(self.plan.cost, 0)
        self.assertFalse(self.plan.changed)

    def test_only_a_building_that_was_really_there_sells_at_half_price(self):
        self.lots[0].houses = 1
        self.lots[1].houses = 1
        plan = self.new_plan()
        plan.remove(plan.all_lots[0])
        self.assertEqual(plan.cost, -25)
        plan.add(plan.all_lots[0])  # put it straight back: no loss either way
        self.assertEqual(plan.cost, 0)

    def test_the_running_total_is_split_into_charge_and_refund(self):
        self.build(self.lots[0])
        self.assertEqual((self.plan.charge, self.plan.refund), (50, 0))
        self.sell(self.lots[0])
        self.assertEqual((self.plan.charge, self.plan.refund), (0, 0))
        self.lots[0].houses = 1
        plan = self.new_plan()
        plan.remove(self.lots[0])
        self.assertEqual((plan.charge, plan.refund), (0, 25))


class RefundFundsBuildingTest(PlanTestCase):
    """A broke player selling one group's houses to improve another."""

    groups = (BROWN, ORANGE)
    cash = 0

    def setUp(self):
        super().setUp()
        for lot in self.lots:
            if lot.group == "brown":
                lot.houses = MAX_HOUSES
        self.bank.houses = HOUSE_SUPPLY - 2 * MAX_HOUSES
        self.plan = self.new_plan()
        self.brown = [lot for lot in self.plan.all_lots if lot.group == "brown"]
        self.orange = [lot for lot in self.plan.all_lots if lot.group == "orange"]

    def test_with_no_cash_nothing_can_be_built(self):
        self.assertFalse(self.plan.can_add(self.orange[0]))

    def test_four_brown_houses_pay_for_one_orange_one(self):
        for _ in range(2):  # evenly, two houses off each brown lot
            for lot in self.brown:
                self.assertTrue(self.plan.remove(lot))
        self.assertEqual(self.plan.cost, -100)
        self.assertTrue(self.plan.can_add(self.orange[0]))
        self.build(self.orange[0])
        self.assertEqual(self.plan.cost, 0)

    def test_the_whole_swap_commits_at_once(self):
        for _ in range(2):
            for lot in self.brown:
                self.plan.remove(lot)
        self.plan.add(self.orange[0])
        self.assertTrue(self.plan.commit())
        self.assertEqual([lot.houses for lot in self.brown], [2, 2])
        self.assertEqual(self.orange[0].houses, 1)
        self.assertEqual(self.ada.cash, 0)


class CommitTest(PlanTestCase):
    def test_committing_nothing_does_nothing(self):
        self.assertFalse(self.plan.commit())
        self.assertEqual(self.ada.cash, self.cash)

    def test_commit_moves_deeds_bank_and_cash_together(self):
        self.build(self.lots[0], self.lots[1], self.lots[0])
        self.assertTrue(self.plan.commit())
        self.assertEqual([lot.houses for lot in self.lots], [2, 1])
        self.assertEqual(self.bank.houses, HOUSE_SUPPLY - 3)
        self.assertEqual(self.ada.cash, self.cash - 150)

    def test_commit_flips_a_lot_to_a_hotel(self):
        self.to_hotel(*self.lots)
        self.plan.commit()
        for lot in self.lots:
            self.assertTrue(lot.has_hotel)
            self.assertEqual(lot.houses, 0)
            self.assertEqual(lot.building_level, HOTEL_LEVEL)
        self.assertEqual(total_buildings(self.properties), (0, 2))

    def test_commit_refunds_a_sale(self):
        self.to_hotel(*self.lots)
        self.plan.commit()
        cash = self.ada.cash
        self.assertEqual(self.bank.houses, HOUSE_SUPPLY)  # both hotels' houses
        plan = self.new_plan()
        plan.remove(self.lots[0])
        self.assertTrue(plan.commit())
        self.assertEqual(self.ada.cash, cash + 25)
        self.assertFalse(self.lots[0].has_hotel)
        self.assertEqual(self.lots[0].houses, MAX_HOUSES)
        self.assertEqual(self.bank.houses, HOUSE_SUPPLY - MAX_HOUSES)
        self.assertEqual(self.bank.hotels, HOTEL_SUPPLY - 1)

    def test_a_second_commit_is_a_no_op(self):
        self.build(self.lots[0])
        self.assertTrue(self.plan.commit())
        self.assertFalse(self.plan.commit())
        self.assertEqual(self.ada.cash, self.cash - 50)

    def test_commit_refuses_when_the_cash_went_away(self):
        self.build(self.lots[0])
        self.ada.cash = 10
        self.assertFalse(self.plan.commit())
        self.assertEqual(self.lots[0].houses, 0)
        self.assertEqual(self.bank.houses, HOUSE_SUPPLY)
        self.assertEqual(self.ada.cash, 10)

    def test_building_raises_the_rent(self):
        self.assertEqual(self.lots[0].current_rent(), 4)  # monopoly, unimproved
        self.build(self.lots[0], self.lots[1])
        self.plan.commit()
        self.assertEqual(self.lots[0].current_rent(), 10)

    def test_a_hotel_charges_the_top_of_the_rent_table(self):
        self.to_hotel(*self.lots)
        self.plan.commit()
        self.assertEqual(self.lots[1].current_rent(), 450)  # Baltic, hotel


class DescribeTest(PlanTestCase):
    def test_an_untouched_plan_says_so(self):
        self.assertEqual(describe_plan(self.plan), "No changes.")

    def test_a_purchase_reads_as_a_payment(self):
        self.build(self.lots[0], self.lots[1])
        self.assertEqual(describe_plan(self.plan), "build 2 -- pay $100.")

    def test_a_sale_reads_as_a_refund(self):
        self.build(self.lots[0], self.lots[1])
        self.plan.commit()
        plan = self.new_plan()
        plan.remove(self.lots[0])
        self.assertEqual(describe_plan(plan), "sell 1 -- receive $25.")

    def test_only_the_net_change_is_described(self):
        self.lots[0].houses = 1
        self.lots[1].houses = 1
        plan = self.new_plan()
        plan.remove(plan.all_lots[0])
        plan.remove(plan.all_lots[1])
        plan.add(plan.all_lots[0])  # undone, so it is neither built nor sold
        self.assertEqual(describe_plan(plan), "sell 1 -- receive $25.")

    def test_a_mixed_plan_names_both_sides(self):
        lots = give(self.ada, self.properties, ORANGE)
        for lot in lots:
            lot.houses = 1
        self.ada.cash = 1000
        plan = self.new_plan()
        for lot in lots:
            plan.remove(lot)
        plan.add(self.lots[0])
        self.assertIn("build 1", describe_plan(plan))
        self.assertIn("sell 3", describe_plan(plan))


class TotalBuildingsTest(unittest.TestCase):
    def test_an_empty_board_carries_nothing(self):
        properties, _ = make_board()
        self.assertEqual(total_buildings(properties), (0, 0))

    def test_houses_and_hotels_are_counted_apart(self):
        properties, _ = make_board()
        by_index = {p.index: p for p in properties}
        by_index[1].houses = 3
        by_index[3].has_hotel = True
        self.assertEqual(total_buildings(properties), (3, 1))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
