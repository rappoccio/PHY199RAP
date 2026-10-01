"""Phase 2 tests: the ``Player`` class.

These pin down the money rules (cash-only payment vs. full liquidation),
deed ownership bookkeeping, and the group/monopoly queries that the rent,
building and trading phases all depend on.
"""

from __future__ import annotations

import unittest

from monopoly.player import Player
from monopoly.property import build_properties

MEDITERRANEAN = 1
BALTIC = 3
ORIENTAL = 6
VERMONT = 8
CONNECTICUT = 9
READING_RAILROAD = 5
ELECTRIC_COMPANY = 12
BOARDWALK = 39
PARK_PLACE = 37


class PlayerTestCase(unittest.TestCase):
    """Shared fixture: a fresh board of deeds and two players."""

    def setUp(self) -> None:
        self.deeds = build_properties()
        self.by_index = {prop.index: prop for prop in self.deeds}
        self.ada = Player(name="Ada", cash=1500, token_color="red")
        self.grace = Player(name="Grace", cash=1500, token_color="blue")

    def deed(self, index: int):
        return self.by_index[index]


class TestDefaults(PlayerTestCase):
    def test_new_player_starts_at_go_with_nothing(self) -> None:
        self.assertEqual(self.ada.position, 0)
        self.assertEqual(self.ada.properties, [])
        self.assertEqual(self.ada.goojf_cards, 0)
        self.assertFalse(self.ada.in_jail)
        self.assertEqual(self.ada.jail_turns, 0)
        self.assertFalse(self.ada.is_bankrupt)
        self.assertEqual(self.ada.doubles_streak, 0)

    def test_starting_cash_is_whatever_the_game_manager_set(self) -> None:
        # The one rules change: the operator picks each player's opening cash.
        tycoon = Player(name="Tycoon", cash=25000, token_color="green")
        pauper = Player(name="Pauper", cash=1, token_color="yellow")
        self.assertEqual(tycoon.cash, 25000)
        self.assertEqual(pauper.cash, 1)

    def test_players_compare_by_identity(self) -> None:
        twin = Player(name="Ada", cash=1500, token_color="red")
        self.assertNotEqual(self.ada, twin)
        self.assertEqual(self.ada, self.ada)
        self.assertEqual(len({self.ada, twin}), 2)

    def test_players_do_not_share_a_property_list(self) -> None:
        self.ada.add_property(self.deed(BOARDWALK))
        self.assertEqual(self.grace.properties, [])

    def test_repr_does_not_recurse_through_properties(self) -> None:
        self.ada.add_property(self.deed(BOARDWALK))
        self.assertIn("Ada", repr(self.ada))


class TestMoney(PlayerTestCase):
    def test_pay_deducts_when_affordable(self) -> None:
        self.assertTrue(self.ada.pay(500))
        self.assertEqual(self.ada.cash, 1000)

    def test_pay_the_exact_balance_is_allowed(self) -> None:
        self.assertTrue(self.ada.pay(1500))
        self.assertEqual(self.ada.cash, 0)

    def test_pay_refuses_and_leaves_the_balance_untouched(self) -> None:
        self.assertFalse(self.ada.pay(1501))
        self.assertEqual(self.ada.cash, 1500)

    def test_receive_credits_cash(self) -> None:
        self.ada.receive(200)
        self.assertEqual(self.ada.cash, 1700)

    def test_can_pay_looks_at_cash_only(self) -> None:
        self.ada.cash = 10
        self.ada.add_property(self.deed(BOARDWALK))  # worth $200 mortgaged
        self.assertFalse(self.ada.can_pay(100))
        self.assertTrue(self.ada.can_pay(10))

    def test_negative_amounts_are_rejected(self) -> None:
        for call in (self.ada.pay, self.ada.receive, self.ada.can_pay, self.ada.can_raise):
            with self.subTest(method=call.__name__):
                with self.assertRaises(ValueError):
                    call(-1)
        self.assertEqual(self.ada.cash, 1500)

    def test_zero_is_always_payable(self) -> None:
        self.ada.cash = 0
        self.assertTrue(self.ada.can_pay(0))
        self.assertTrue(self.ada.pay(0))
        self.assertEqual(self.ada.cash, 0)


class TestLiquidation(PlayerTestCase):
    def test_liquidation_value_is_cash_when_landless(self) -> None:
        self.assertEqual(self.ada.liquidation_value(), 1500)

    def test_liquidation_value_adds_mortgage_proceeds(self) -> None:
        self.ada.cash = 100
        self.ada.add_property(self.deed(BOARDWALK))  # mortgage 200
        self.ada.add_property(self.deed(PARK_PLACE))  # mortgage 175
        self.assertEqual(self.ada.liquidation_value(), 475)

    def test_already_mortgaged_deeds_raise_nothing(self) -> None:
        self.ada.cash = 100
        boardwalk = self.deed(BOARDWALK)
        self.ada.add_property(boardwalk)
        boardwalk.mortgaged = True
        self.assertEqual(self.ada.liquidation_value(), 100)

    def test_buildings_sell_back_at_half_price(self) -> None:
        self.ada.cash = 0
        boardwalk = self.deed(BOARDWALK)  # house_cost 200, mortgage 200
        self.ada.add_property(boardwalk)
        boardwalk.houses = 3
        # 3 houses * $100 back + $200 mortgage
        self.assertEqual(self.ada.liquidation_value(), 500)

    def test_mortgaged_deed_still_sells_its_buildings(self) -> None:
        self.ada.cash = 0
        boardwalk = self.deed(BOARDWALK)
        self.ada.add_property(boardwalk)
        boardwalk.has_hotel = True
        boardwalk.mortgaged = True
        self.assertEqual(self.ada.liquidation_value(), 500)

    def test_can_raise_spans_cash_and_assets(self) -> None:
        self.ada.cash = 50
        self.ada.add_property(self.deed(BOARDWALK))  # mortgage 200
        self.assertTrue(self.ada.can_raise(250))
        self.assertFalse(self.ada.can_raise(251))
        # ...while the cash alone falls well short.
        self.assertFalse(self.ada.can_pay(250))


class TestNetWorth(PlayerTestCase):
    def test_net_worth_of_a_landless_player_is_cash(self) -> None:
        self.assertEqual(self.ada.net_worth(), 1500)

    def test_deeds_count_at_face_price(self) -> None:
        self.ada.add_property(self.deed(BOARDWALK))  # 400
        self.ada.add_property(self.deed(READING_RAILROAD))  # 200
        self.assertEqual(self.ada.net_worth(), 2100)

    def test_mortgaged_deeds_count_at_their_mortgage_value(self) -> None:
        boardwalk = self.deed(BOARDWALK)
        self.ada.add_property(boardwalk)
        boardwalk.mortgaged = True
        self.assertEqual(self.ada.net_worth(), 1700)

    def test_buildings_count_at_purchase_cost(self) -> None:
        boardwalk = self.deed(BOARDWALK)
        self.ada.add_property(boardwalk)
        boardwalk.houses = 2
        self.assertEqual(self.ada.net_worth(), 1500 + 400 + 400)
        boardwalk.houses = 0
        boardwalk.has_hotel = True
        self.assertEqual(self.ada.net_worth(), 1500 + 400 + 1000)


class TestDeedOwnership(PlayerTestCase):
    def test_add_property_sets_the_owner_both_ways(self) -> None:
        boardwalk = self.deed(BOARDWALK)
        self.ada.add_property(boardwalk)
        self.assertIs(boardwalk.owner, self.ada)
        self.assertIn(boardwalk, self.ada.properties)

    def test_adding_twice_is_a_no_op(self) -> None:
        boardwalk = self.deed(BOARDWALK)
        self.ada.add_property(boardwalk)
        self.ada.add_property(boardwalk)
        self.assertEqual(len(self.ada.properties), 1)

    def test_add_property_moves_the_deed_off_its_old_owner(self) -> None:
        boardwalk = self.deed(BOARDWALK)
        self.ada.add_property(boardwalk)
        self.grace.add_property(boardwalk)
        self.assertIs(boardwalk.owner, self.grace)
        self.assertEqual(self.ada.properties, [])
        self.assertEqual(self.grace.properties, [boardwalk])

    def test_remove_property_leaves_the_deed_unowned(self) -> None:
        boardwalk = self.deed(BOARDWALK)
        self.ada.add_property(boardwalk)
        self.ada.remove_property(boardwalk)
        self.assertIsNone(boardwalk.owner)
        self.assertEqual(self.ada.properties, [])

    def test_removing_a_deed_you_do_not_hold_is_an_error(self) -> None:
        boardwalk = self.deed(BOARDWALK)
        self.grace.add_property(boardwalk)
        with self.assertRaises(ValueError):
            self.ada.remove_property(boardwalk)
        self.assertIs(boardwalk.owner, self.grace)


class TestGroupQueries(PlayerTestCase):
    def test_owned_in_group_returns_board_order(self) -> None:
        for index in (CONNECTICUT, ORIENTAL):
            self.ada.add_property(self.deed(index))
        self.grace.add_property(self.deed(VERMONT))
        self.assertEqual(
            [p.index for p in self.ada.owned_in_group("light_blue", self.deeds)],
            [ORIENTAL, CONNECTICUT],
        )
        self.assertEqual(
            [p.index for p in self.grace.owned_in_group("light_blue", self.deeds)],
            [VERMONT],
        )

    def test_owned_in_group_is_empty_for_an_untouched_group(self) -> None:
        self.assertEqual(self.ada.owned_in_group("orange", self.deeds), [])

    def test_has_monopoly_needs_every_deed_in_the_group(self) -> None:
        self.ada.add_property(self.deed(ORIENTAL))
        self.ada.add_property(self.deed(VERMONT))
        self.assertFalse(self.ada.has_monopoly("light_blue", self.deeds))
        self.ada.add_property(self.deed(CONNECTICUT))
        self.assertTrue(self.ada.has_monopoly("light_blue", self.deeds))

    def test_monopoly_survives_a_mortgage(self) -> None:
        for index in (MEDITERRANEAN, BALTIC):
            self.ada.add_property(self.deed(index))
        self.deed(BALTIC).mortgaged = True
        self.assertTrue(self.ada.has_monopoly("brown", self.deeds))

    def test_one_deed_in_another_hand_breaks_the_monopoly(self) -> None:
        self.ada.add_property(self.deed(ORIENTAL))
        self.ada.add_property(self.deed(VERMONT))
        self.grace.add_property(self.deed(CONNECTICUT))
        self.assertFalse(self.ada.has_monopoly("light_blue", self.deeds))
        self.assertFalse(self.grace.has_monopoly("light_blue", self.deeds))

    def test_railroads_and_utilities_form_groups_too(self) -> None:
        railroads = [p for p in self.deeds if p.group == "railroad"]
        for rr in railroads:
            self.ada.add_property(rr)
        self.assertTrue(self.ada.has_monopoly("railroad", self.deeds))
        self.assertFalse(self.ada.has_monopoly("utility", self.deeds))
        self.ada.add_property(self.deed(ELECTRIC_COMPANY))
        self.assertFalse(self.ada.has_monopoly("utility", self.deeds))

    def test_unknown_group_is_not_a_monopoly(self) -> None:
        self.assertFalse(self.ada.has_monopoly("chartreuse", self.deeds))

    def test_monopolies_lists_complete_groups_in_board_order(self) -> None:
        for index in (MEDITERRANEAN, BALTIC, PARK_PLACE, BOARDWALK, ORIENTAL):
            self.ada.add_property(self.deed(index))
        self.assertEqual(self.ada.monopolies(self.deeds), ["brown", "dark_blue"])

    def test_monopolies_is_empty_without_a_complete_group(self) -> None:
        self.ada.add_property(self.deed(BOARDWALK))
        self.assertEqual(self.ada.monopolies(self.deeds), [])


if __name__ == "__main__":
    unittest.main()
