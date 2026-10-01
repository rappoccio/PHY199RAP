"""Phase 12 tests: the mortgage rules.

:class:`monopoly.mortgage.MortgageLedger` on its own, with no game and no
pygame around it: which deeds it lists, which rows it will let move, what a
draft costs, that Confirm moves every flag and the money together, and that
Cancel leaves the board exactly as it was.

The two rules under test are the plan's: a lot may only be mortgaged while no
building stands anywhere in its colour group, and lifting a mortgage costs
110% of what the bank paid out, in cash.
"""

from __future__ import annotations

import unittest

from monopoly.mortgage import (
    BUILT_REASON,
    CASH_REASON,
    NO_CHANGES,
    MortgageLedger,
    describe,
    has_business,
    holdings,
    liftable,
    lifted,
    mortgageable,
    taken,
)
from monopoly.player import Player
from monopoly.property import build_properties

# Board indices, by group.
MEDITERRANEAN, BALTIC = 1, 3
ORIENTAL, VERMONT, CONNECTICUT = 6, 8, 9
READING = 5
KENTUCKY = 21
ELECTRIC = 12
BOARDWALK = 39

BROWN = (MEDITERRANEAN, BALTIC)


class LedgerTestCase(unittest.TestCase):
    """One player, a fresh board, and a helper for handing deeds over."""

    cash = 1500

    def setUp(self):
        self.properties = build_properties()
        self.ada = Player("Ada", self.cash, "red")
        self.bob = Player("Bob", self.cash, "blue")

    def deed(self, index: int):
        for prop in self.properties:
            if prop.index == index:
                return prop
        raise AssertionError(f"no deed at {index}")

    def give(self, player: Player, *indices: int) -> list:
        deeds = [self.deed(i) for i in indices]
        for deed in deeds:
            player.add_property(deed)
        return deeds

    def ledger(self, player=None) -> MortgageLedger:
        return MortgageLedger(
            player if player is not None else self.ada, self.properties
        )


# --- the module's own questions --------------------------------------------
class HoldingsTest(LedgerTestCase):
    def test_a_player_with_nothing_holds_nothing(self):
        self.assertEqual(holdings(self.ada, self.properties), [])

    def test_deeds_come_back_in_board_order(self):
        self.give(self.ada, BOARDWALK, BALTIC, READING)
        self.assertEqual(
            [d.index for d in holdings(self.ada, self.properties)],
            [BALTIC, READING, BOARDWALK],
        )

    def test_somebody_elses_deeds_are_not_listed(self):
        self.give(self.bob, BALTIC)
        self.assertEqual(holdings(self.ada, self.properties), [])

    def test_a_mortgaged_deed_is_still_listed(self):
        self.give(self.ada, BALTIC)[0].mortgaged = True
        self.assertEqual(
            [d.index for d in holdings(self.ada, self.properties)], [BALTIC]
        )


class MortgageableTest(LedgerTestCase):
    def test_a_bare_lot_can_be_mortgaged(self):
        self.give(self.ada, BALTIC)
        self.assertEqual(
            [d.index for d in mortgageable(self.ada, self.properties)], [BALTIC]
        )

    def test_a_built_group_takes_every_one_of_its_lots_off_the_list(self):
        lots = self.give(self.ada, *BROWN)
        lots[0].houses = 1
        self.assertEqual(mortgageable(self.ada, self.properties), [])

    def test_a_built_group_does_not_block_another_group(self):
        brown = self.give(self.ada, *BROWN)
        self.give(self.ada, READING)
        brown[1].has_hotel = True
        self.assertEqual(
            [d.index for d in mortgageable(self.ada, self.properties)], [READING]
        )

    def test_an_already_mortgaged_deed_is_not_on_the_list(self):
        self.give(self.ada, BALTIC)[0].mortgaged = True
        self.assertEqual(mortgageable(self.ada, self.properties), [])

    def test_a_railroad_is_never_built_on_so_never_blocked(self):
        self.give(self.ada, READING, ELECTRIC)
        self.assertEqual(len(mortgageable(self.ada, self.properties)), 2)


class LiftableTest(LedgerTestCase):
    def test_nothing_mortgaged_is_nothing_to_lift(self):
        self.give(self.ada, BALTIC)
        self.assertEqual(liftable(self.ada, self.properties), [])

    def test_a_mortgage_within_reach_is_liftable(self):
        self.give(self.ada, BALTIC)[0].mortgaged = True
        self.assertEqual(
            [d.index for d in liftable(self.ada, self.properties)], [BALTIC]
        )

    def test_a_mortgage_out_of_reach_is_not(self):
        self.ada.cash = 32  # Baltic lifts for $33
        self.give(self.ada, BALTIC)[0].mortgaged = True
        self.assertEqual(liftable(self.ada, self.properties), [])

    def test_the_price_is_110_percent_exactly(self):
        self.ada.cash = 33
        self.give(self.ada, BALTIC)[0].mortgaged = True
        self.assertEqual(len(liftable(self.ada, self.properties)), 1)


class HasBusinessTest(LedgerTestCase):
    def test_a_player_with_no_deeds_has_nothing_to_do(self):
        self.assertFalse(has_business(self.ada, self.properties))

    def test_one_free_lot_is_enough(self):
        self.give(self.ada, BALTIC)
        self.assertTrue(has_business(self.ada, self.properties))

    def test_one_affordable_mortgage_is_enough(self):
        self.give(self.ada, BALTIC)[0].mortgaged = True
        self.assertTrue(has_business(self.ada, self.properties))

    def test_deeds_behind_houses_and_no_cash_leave_nothing_to_do(self):
        self.ada.cash = 0
        lots = self.give(self.ada, *BROWN)
        lots[0].houses = 1
        lots[1].mortgaged = True
        self.assertFalse(has_business(self.ada, self.properties))


# --- the draft -------------------------------------------------------------
class DraftTest(LedgerTestCase):
    def test_an_empty_hand_makes_an_empty_ledger(self):
        ledger = self.ledger()
        self.assertTrue(ledger.is_empty)
        self.assertEqual(ledger.deeds, [])
        self.assertFalse(ledger.changed)

    def test_the_draft_starts_from_the_board(self):
        deeds = self.give(self.ada, *BROWN)
        deeds[0].mortgaged = True
        ledger = self.ledger()
        self.assertEqual([ledger.state(d) for d in deeds], [True, False])
        self.assertFalse(ledger.changed)
        self.assertEqual(ledger.cost, 0)

    def test_the_rows_are_in_board_order(self):
        self.give(self.ada, BOARDWALK, BALTIC)
        self.assertEqual(
            [d.index for d in self.ledger().deeds], [BALTIC, BOARDWALK]
        )

    def test_mortgaging_shows_up_in_the_draft_only(self):
        deed = self.give(self.ada, BALTIC)[0]
        ledger = self.ledger()
        self.assertTrue(ledger.mortgage(deed))
        self.assertTrue(ledger.state(deed))
        self.assertTrue(ledger.changed)
        self.assertFalse(deed.mortgaged, "the board is untouched until Confirm")
        self.assertEqual(self.ada.cash, self.cash, "and so is the wallet")

    def test_reset_throws_the_draft_away(self):
        deed = self.give(self.ada, BALTIC)[0]
        ledger = self.ledger()
        ledger.mortgage(deed)
        ledger.reset()
        self.assertFalse(ledger.changed)
        self.assertFalse(ledger.state(deed))

    def test_a_deed_the_ledger_does_not_know_reports_the_board(self):
        deed = self.give(self.bob, BALTIC)[0]
        deed.mortgaged = True
        ledger = self.ledger()
        self.assertTrue(ledger.state(deed))
        self.assertFalse(ledger.can_mortgage(deed))
        self.assertFalse(ledger.can_unmortgage(deed))
        self.assertIsNone(ledger.blocker(deed))


class CanMortgageTest(LedgerTestCase):
    def test_a_bare_lot_may_be_mortgaged(self):
        deed = self.give(self.ada, BALTIC)[0]
        ledger = self.ledger()
        self.assertTrue(ledger.can_mortgage(deed))
        self.assertIsNone(ledger.blocker(deed))

    def test_a_lot_with_a_house_on_its_group_may_not(self):
        lots = self.give(self.ada, *BROWN)
        lots[0].houses = 1
        ledger = self.ledger()
        for lot in lots:
            self.assertFalse(ledger.can_mortgage(lot), lot.name)
            self.assertEqual(ledger.blocker(lot), BUILT_REASON)

    def test_a_hotel_blocks_its_group_too(self):
        lots = self.give(self.ada, *BROWN)
        lots[1].has_hotel = True
        self.assertFalse(self.ledger().can_mortgage(lots[0]))

    def test_the_group_counts_lots_the_player_does_not_own(self):
        # Ada holds Oriental; Bob holds Vermont with a house on it. Even
        # building means that cannot happen in a real game, but the rule is
        # about the group, not about the holder.
        ada_lot = self.give(self.ada, ORIENTAL)[0]
        self.give(self.bob, VERMONT)[0].houses = 1
        self.assertFalse(self.ledger().can_mortgage(ada_lot))

    def test_a_deed_already_mortgaged_in_the_draft_may_not_be_again(self):
        deed = self.give(self.ada, BALTIC)[0]
        ledger = self.ledger()
        ledger.mortgage(deed)
        self.assertFalse(ledger.can_mortgage(deed))
        self.assertFalse(ledger.mortgage(deed))

    def test_mortgaging_never_asks_about_cash(self):
        self.ada.cash = 0
        deed = self.give(self.ada, BOARDWALK)[0]
        self.assertTrue(self.ledger().can_mortgage(deed))


class CanUnmortgageTest(LedgerTestCase):
    def test_a_free_lot_has_no_mortgage_to_lift(self):
        deed = self.give(self.ada, BALTIC)[0]
        self.assertFalse(self.ledger().can_unmortgage(deed))

    def test_a_mortgage_lifts_when_the_cash_is_there(self):
        deed = self.give(self.ada, BALTIC)[0]
        deed.mortgaged = True
        ledger = self.ledger()
        self.assertTrue(ledger.can_unmortgage(deed))
        self.assertIsNone(ledger.blocker(deed))

    def test_a_mortgage_stays_put_when_it_is_not(self):
        self.ada.cash = 32
        deed = self.give(self.ada, BALTIC)[0]
        deed.mortgaged = True
        ledger = self.ledger()
        self.assertFalse(ledger.can_unmortgage(deed))
        self.assertEqual(ledger.blocker(deed), CASH_REASON)
        self.assertFalse(ledger.unmortgage(deed))

    def test_buildings_do_not_stop_a_mortgage_being_lifted(self):
        # Lifting a mortgage only ever helps the group, so the bare-group rule
        # is asked of mortgaging, never of unmortgaging.
        lots = self.give(self.ada, *BROWN)
        lots[0].mortgaged = True
        lots[1].houses = 2
        self.assertTrue(self.ledger().can_unmortgage(lots[0]))

    def test_one_mortgage_can_pay_to_lift_another(self):
        self.ada.cash = 0
        med, baltic = self.give(self.ada, *BROWN)
        med.mortgaged = True
        ledger = self.ledger()
        self.assertFalse(ledger.can_unmortgage(med), "$0 will not lift $33")
        self.assertTrue(ledger.mortgage(baltic), "but Baltic raises $30...")
        self.assertFalse(
            ledger.can_unmortgage(med), "...which is still $3 short of $33"
        )
        self.ada.cash = 3
        self.assertTrue(ledger.can_unmortgage(med))

    def test_a_mortgage_can_pay_for_a_lift_outright(self):
        # Kentucky raises $110, which is exactly what lifting Reading costs,
        # so a player with nothing in hand can still do both.
        self.ada.cash = 0
        reading, kentucky = self.give(self.ada, READING, KENTUCKY)
        reading.mortgaged = True
        ledger = self.ledger()
        self.assertFalse(ledger.can_unmortgage(reading))
        ledger.mortgage(kentucky)
        self.assertTrue(ledger.can_unmortgage(reading))
        self.assertTrue(ledger.unmortgage(reading))
        self.assertTrue(ledger.commit())
        self.assertEqual(self.ada.cash, 0)
        self.assertFalse(reading.mortgaged)
        self.assertTrue(kentucky.mortgaged)

    def test_undoing_a_mortgage_taken_in_the_same_draft_is_free(self):
        self.ada.cash = 0
        deed = self.give(self.ada, BOARDWALK)[0]
        ledger = self.ledger()
        ledger.mortgage(deed)
        self.assertTrue(
            ledger.can_unmortgage(deed), "an undo costs nothing, not $220"
        )
        self.assertTrue(ledger.unmortgage(deed))
        self.assertFalse(ledger.changed)
        self.assertEqual(ledger.cost, 0)


class ToggleTest(LedgerTestCase):
    def test_a_toggle_mortgages_a_free_lot(self):
        deed = self.give(self.ada, BALTIC)[0]
        ledger = self.ledger()
        self.assertTrue(ledger.toggle(deed))
        self.assertTrue(ledger.state(deed))

    def test_a_toggle_lifts_a_mortgaged_one(self):
        deed = self.give(self.ada, BALTIC)[0]
        deed.mortgaged = True
        ledger = self.ledger()
        self.assertTrue(ledger.toggle(deed))
        self.assertFalse(ledger.state(deed))

    def test_a_toggle_nobody_may_make_reports_false(self):
        lots = self.give(self.ada, *BROWN)
        lots[0].houses = 1
        ledger = self.ledger()
        self.assertFalse(ledger.toggle(lots[1]))
        self.assertFalse(ledger.can_toggle(lots[1]))

    def test_two_toggles_are_an_undo(self):
        deed = self.give(self.ada, BALTIC)[0]
        ledger = self.ledger()
        ledger.toggle(deed)
        ledger.toggle(deed)
        self.assertFalse(ledger.changed)


class PriceTest(LedgerTestCase):
    def test_a_mortgage_pays_out(self):
        deed = self.give(self.ada, BALTIC)[0]
        ledger = self.ledger()
        ledger.mortgage(deed)
        self.assertEqual(ledger.cost, -30)
        self.assertEqual(ledger.refund, 30)
        self.assertEqual(ledger.charge, 0)
        self.assertEqual(ledger.proceeds, 30)
        self.assertEqual(ledger.interest, 0)

    def test_lifting_one_costs_110_percent(self):
        deed = self.give(self.ada, BALTIC)[0]
        deed.mortgaged = True
        ledger = self.ledger()
        ledger.unmortgage(deed)
        self.assertEqual(ledger.cost, 33)
        self.assertEqual(ledger.charge, 33)
        self.assertEqual(ledger.refund, 0)
        self.assertEqual(ledger.interest, 33)
        self.assertEqual(ledger.proceeds, 0)

    def test_the_interest_rounds_up_to_the_dollar(self):
        # Electric Company: $75 mortgage, so $82.50 becomes $83.
        deed = self.give(self.ada, ELECTRIC)[0]
        deed.mortgaged = True
        ledger = self.ledger()
        ledger.unmortgage(deed)
        self.assertEqual(ledger.cost, 83)

    def test_both_directions_at_once_net_off(self):
        med, baltic = self.give(self.ada, *BROWN)
        med.mortgaged = True
        ledger = self.ledger()
        ledger.unmortgage(med)  # -$33
        ledger.mortgage(baltic)  # +$30
        self.assertEqual(ledger.cost, 3)
        self.assertEqual(ledger.proceeds, 30)
        self.assertEqual(ledger.interest, 33)

    def test_an_untouched_draft_is_free(self):
        self.give(self.ada, *BROWN)
        self.assertEqual(self.ledger().cost, 0)


class CommitTest(LedgerTestCase):
    def test_committing_nothing_reports_false(self):
        self.give(self.ada, BALTIC)
        self.assertFalse(self.ledger().commit())

    def test_a_mortgage_flips_the_flag_and_pays_out(self):
        deed = self.give(self.ada, BALTIC)[0]
        ledger = self.ledger()
        ledger.mortgage(deed)
        self.assertTrue(ledger.commit())
        self.assertTrue(deed.mortgaged)
        self.assertEqual(self.ada.cash, self.cash + 30)

    def test_lifting_one_clears_the_flag_and_charges_110_percent(self):
        deed = self.give(self.ada, BALTIC)[0]
        deed.mortgaged = True
        ledger = self.ledger()
        ledger.unmortgage(deed)
        self.assertTrue(ledger.commit())
        self.assertFalse(deed.mortgaged)
        self.assertEqual(self.ada.cash, self.cash - 33)

    def test_a_whole_screenful_lands_at_once(self):
        deeds = self.give(self.ada, MEDITERRANEAN, BALTIC, READING)
        ledger = self.ledger()
        for deed in deeds:
            ledger.mortgage(deed)
        self.assertTrue(ledger.commit())
        self.assertTrue(all(d.mortgaged for d in deeds))
        self.assertEqual(self.ada.cash, self.cash + 30 + 30 + 100)

    def test_both_directions_settle_on_the_net(self):
        med, baltic = self.give(self.ada, *BROWN)
        med.mortgaged = True
        ledger = self.ledger()
        ledger.unmortgage(med)
        ledger.mortgage(baltic)
        self.assertTrue(ledger.commit())
        self.assertFalse(med.mortgaged)
        self.assertTrue(baltic.mortgaged)
        self.assertEqual(self.ada.cash, self.cash - 3)

    def test_committing_an_undone_draft_changes_nothing(self):
        deed = self.give(self.ada, BALTIC)[0]
        ledger = self.ledger()
        ledger.mortgage(deed)
        ledger.unmortgage(deed)
        self.assertFalse(ledger.commit())
        self.assertFalse(deed.mortgaged)
        self.assertEqual(self.ada.cash, self.cash)

    def test_cash_that_went_missing_stops_the_commit(self):
        deed = self.give(self.ada, BALTIC)[0]
        deed.mortgaged = True
        ledger = self.ledger()
        ledger.unmortgage(deed)
        self.ada.cash = 0  # a rent bill between the draft and Confirm
        self.assertFalse(ledger.commit())
        self.assertTrue(deed.mortgaged, "nothing half-happened")
        self.assertEqual(self.ada.cash, 0)

    def test_a_committed_ledger_is_back_in_step_with_the_board(self):
        deed = self.give(self.ada, BALTIC)[0]
        ledger = self.ledger()
        ledger.mortgage(deed)
        ledger.commit()
        self.assertFalse(ledger.changed)
        self.assertEqual(ledger.cost, 0)


class RentTest(LedgerTestCase):
    """The point of the whole thing: a mortgaged deed earns nothing."""

    def test_a_mortgaged_lot_collects_no_rent(self):
        deed = self.give(self.ada, BALTIC)[0]
        self.assertEqual(deed.current_rent(), 4)
        ledger = self.ledger()
        ledger.mortgage(deed)
        ledger.commit()
        self.assertEqual(deed.current_rent(), 0)

    def test_lifting_the_mortgage_turns_the_rent_back_on(self):
        deed = self.give(self.ada, BALTIC)[0]
        deed.mortgaged = True
        ledger = self.ledger()
        ledger.unmortgage(deed)
        ledger.commit()
        self.assertEqual(deed.current_rent(), 4)

    def test_a_mortgaged_lot_does_not_break_its_groups_monopoly(self):
        med, baltic = self.give(self.ada, *BROWN)
        ledger = self.ledger()
        ledger.mortgage(med)
        ledger.commit()
        self.assertEqual(med.current_rent(), 0)
        self.assertEqual(baltic.current_rent(), 8, "still double, still a monopoly")

    def test_an_inherited_mortgage_may_be_lifted_by_its_new_owner(self):
        # The plan's last line: a mortgaged deed that changes hands (a trade,
        # a bankruptcy) is the new owner's to lift at the same 110%, or to
        # leave alone and collect nothing on.
        deed = self.give(self.bob, BALTIC)[0]
        deed.mortgaged = True
        self.ada.add_property(deed)
        self.assertEqual(deed.current_rent(), 0)
        ledger = self.ledger()
        self.assertIn(deed, ledger.deeds)
        self.assertTrue(ledger.unmortgage(deed))
        ledger.commit()
        self.assertEqual(self.ada.cash, self.cash - 33)
        self.assertEqual(deed.current_rent(), 4)


class DescribeTest(LedgerTestCase):
    def test_an_untouched_draft_says_so(self):
        self.give(self.ada, BALTIC)
        self.assertEqual(describe(self.ledger()), NO_CHANGES)

    def test_a_mortgage_reads_as_one(self):
        deed = self.give(self.ada, BALTIC)[0]
        ledger = self.ledger()
        ledger.mortgage(deed)
        line = describe(ledger)
        self.assertIn("mortgage Baltic Avenue", line)
        self.assertIn("receive $30", line)

    def test_a_lift_reads_as_one(self):
        deed = self.give(self.ada, BALTIC)[0]
        deed.mortgaged = True
        ledger = self.ledger()
        ledger.unmortgage(deed)
        line = describe(ledger)
        self.assertIn("lift Baltic Avenue", line)
        self.assertIn("pay $33", line)

    def test_both_halves_are_named_in_board_order(self):
        med, baltic = self.give(self.ada, *BROWN)
        med.mortgaged = True
        ledger = self.ledger()
        ledger.unmortgage(med)
        ledger.mortgage(baltic)
        line = describe(ledger)
        self.assertIn("mortgage Baltic Avenue", line)
        self.assertIn("lift Mediterranean Avenue", line)
        self.assertIn("pay $3", line)

    def test_a_draft_that_nets_to_nothing_says_that_too(self):
        # Lifting Reading costs $110 and mortgaging Kentucky raises exactly
        # $110, so this draft moves two flags and no money.
        reading, kentucky = self.give(self.ada, READING, KENTUCKY)
        reading.mortgaged = True
        ledger = self.ledger()
        ledger.unmortgage(reading)
        ledger.mortgage(kentucky)
        self.assertTrue(ledger.changed)
        self.assertEqual(ledger.cost, 0)
        self.assertIn("no money changes hands", describe(ledger))

    def test_taken_and_lifted_list_the_two_halves(self):
        med, baltic = self.give(self.ada, *BROWN)
        med.mortgaged = True
        ledger = self.ledger()
        ledger.unmortgage(med)
        ledger.mortgage(baltic)
        self.assertEqual([d.index for d in taken(ledger)], [BALTIC])
        self.assertEqual([d.index for d in lifted(ledger)], [MEDITERRANEAN])


class LiquidationTest(LedgerTestCase):
    """Phase 12 and Phase 13 have to agree on what a deed is worth."""

    def test_mortgaging_spends_the_deeds_liquidation_value(self):
        deed = self.give(self.ada, BALTIC)[0]
        before = self.ada.liquidation_value()
        ledger = self.ledger()
        ledger.mortgage(deed)
        ledger.commit()
        self.assertEqual(
            self.ada.liquidation_value(),
            before,
            "cash in hand replaced the deed's mortgage value, penny for penny",
        )

    def test_a_mortgaged_deed_counts_at_its_mortgage_value(self):
        deed = self.give(self.ada, BOARDWALK)[0]
        ledger = self.ledger()
        ledger.mortgage(deed)
        ledger.commit()
        self.assertEqual(
            self.ada.net_worth(), self.cash + 200 + deed.mortgage_value
        )


if __name__ == "__main__":
    unittest.main()
