"""Phase 12 tests: the Mortgage button's place in the turn loop.

``test_mortgage.py`` covers the rules on their own; this file covers how they
join the game -- when the button is live, what opening the screen does to the
rest of the turn, that Confirm and Cancel land where they should, and that the
five modal surfaces still refuse to open over one another. The board is
un-animated exactly as in ``test_game.py``, and no pygame is imported.

:class:`SoakTest` at the end is the "keeps working throughout the game" half:
whole games played out by bots that buy, bid, build **and** mortgage, with
every invariant re-checked after every step.
"""

from __future__ import annotations

import random
import unittest

from monopoly.building import HOTEL_SUPPLY, HOUSE_SUPPLY
from monopoly.game import Action, Game, State
from monopoly.mortgage import CASH_REASON, MortgageLedger
from monopoly.player import Player

from tests.test_game import make_game, take_turn

MEDITERRANEAN, BALTIC = 1, 3
BOARDWALK = 39
BROWN = (MEDITERRANEAN, BALTIC)


def give(game: Game, player: Player, indices) -> list:
    """Hand ``player`` the deeds at ``indices``; return them in board order."""
    deeds = [game.deed(i) for i in indices]
    for deed in deeds:
        player.add_property(deed)
    return deeds


def open_turn(**kwargs) -> Game:
    """A game sitting in PLAYER_ACTIONS, on Income Tax with no prompt up."""
    game = make_game(rolls=[(1, 3)], **kwargs)
    take_turn(game)
    assert game.state is State.PLAYER_ACTIONS
    return game


class ButtonTest(unittest.TestCase):
    def setUp(self):
        self.game = open_turn()

    def test_a_player_with_no_deeds_has_no_button(self):
        self.assertFalse(self.game.can_mortgage())
        self.assertNotIn(Action.MORTGAGE, self.game.available_actions())

    def test_one_deed_lights_it(self):
        give(self.game, self.game.current, [BALTIC])
        self.assertTrue(self.game.can_mortgage())
        self.assertIn(Action.MORTGAGE, self.game.available_actions())

    def test_a_mortgaged_deed_lights_it_too(self):
        give(self.game, self.game.current, [BALTIC])[0].mortgaged = True
        self.assertTrue(self.game.can_mortgage())

    def test_deeds_behind_houses_put_it_out(self):
        lots = give(self.game, self.game.current, BROWN)
        lots[0].houses = 1
        lots[1].mortgaged = True
        self.game.current.cash = 0
        self.assertFalse(self.game.can_mortgage())

    def test_the_button_is_the_current_players(self):
        give(self.game, self.game.players[1], [BALTIC])
        self.assertFalse(self.game.can_mortgage())

    def test_there_is_no_mortgaging_before_the_roll(self):
        game = make_game()
        give(game, game.current, [BALTIC])
        self.assertIs(game.state, State.PLAYER_TURN_START)
        self.assertEqual(game.available_actions(), frozenset({Action.ROLL}))

    def test_a_jailed_player_may_still_mortgage(self):
        game = make_game(rolls=[(1, 2), (2, 3)])
        give(game, game.current, [BALTIC])
        game.current.in_jail = True
        game._begin_turn()
        game.choose("roll")  # misses the doubles, stays in Jail
        game.update(0)
        self.assertIs(game.state, State.PLAYER_ACTIONS)
        self.assertIn(Action.MORTGAGE, game.available_actions())

    def test_a_mortgage_that_empties_the_list_puts_the_button_out(self):
        deed = give(self.game, self.game.current, [BALTIC])[0]
        self.game.current.cash = 0
        ledger = self.game.open_mortgage()
        ledger.mortgage(deed)
        self.game.close_mortgage(commit=True)
        # $30 in hand will not lift the $33 mortgage it just paid for, and
        # there is nothing else to mortgage.
        self.assertEqual(self.game.current.cash, 30)
        self.assertFalse(self.game.can_mortgage())


class OpenTest(unittest.TestCase):
    def setUp(self):
        self.game = open_turn()
        self.deeds = give(self.game, self.game.current, BROWN)

    def test_perform_opens_the_screen(self):
        self.assertTrue(self.game.perform(Action.MORTGAGE))
        self.assertIsInstance(self.game.mortgage, MortgageLedger)
        self.assertIs(self.game.mortgage.player, self.game.current)
        self.assertEqual(self.game.mortgage.deeds, self.deeds)

    def test_an_open_screen_is_modal(self):
        self.game.perform(Action.MORTGAGE)
        self.assertEqual(self.game.available_actions(), frozenset())
        self.assertFalse(self.game.perform(Action.END_TURN))
        self.assertIs(self.game.state, State.PLAYER_ACTIONS)

    def test_the_draft_starts_from_the_board(self):
        self.deeds[0].mortgaged = True
        ledger = self.game.open_mortgage()
        self.assertEqual([ledger.state(d) for d in self.deeds], [True, False])
        self.assertFalse(ledger.changed)

    def test_the_draft_sees_the_games_own_deeds(self):
        ledger = self.game.open_mortgage()
        self.assertEqual(ledger.properties, self.game.properties)

    def test_opening_twice_raises(self):
        self.game.open_mortgage()
        with self.assertRaises(RuntimeError):
            self.game.open_mortgage()

    def test_opening_out_of_turn_raises(self):
        game = make_game()
        give(game, game.current, [BALTIC])
        with self.assertRaises(RuntimeError):
            game.open_mortgage()

    def test_opening_over_a_prompt_raises(self):
        game = make_game(rolls=[(1, 2)])  # Baltic Avenue, unowned
        take_turn(game)
        self.assertIsNotNone(game.prompt)
        game.state = State.PLAYER_ACTIONS
        with self.assertRaises(RuntimeError):
            game.open_mortgage()

    def test_a_registered_handler_still_wins(self):
        seen = []
        self.game.action_handlers[Action.MORTGAGE] = seen.append
        self.assertTrue(self.game.perform(Action.MORTGAGE))
        self.assertEqual(seen, [self.game])
        self.assertIsNone(self.game.mortgage)


class ModalTest(unittest.TestCase):
    """The five modal surfaces refuse to open over one another."""

    def setUp(self):
        self.game = open_turn()
        give(self.game, self.game.current, BROWN)
        self.game.open_mortgage()

    def test_the_build_screen_will_not_open_over_it(self):
        with self.assertRaises(RuntimeError):
            self.game.open_build()

    def test_a_trade_will_not_open_over_it(self):
        with self.assertRaises(RuntimeError):
            self.game.open_trade()

    def test_an_auction_will_not_open_over_it(self):
        with self.assertRaises(RuntimeError):
            self.game.open_auction(self.game.deed(BOARDWALK))

    def test_the_mortgage_screen_will_not_open_over_a_build_draft(self):
        self.game.close_mortgage()
        self.game.open_build()
        with self.assertRaises(RuntimeError):
            self.game.open_mortgage()

    def test_the_mortgage_screen_will_not_open_over_a_trade(self):
        self.game.close_mortgage()
        self.game.open_trade()
        with self.assertRaises(RuntimeError):
            self.game.open_mortgage()

    def test_the_mortgage_screen_will_not_open_over_an_auction(self):
        self.game.close_mortgage()
        self.game.open_auction(self.game.deed(BOARDWALK))
        with self.assertRaises(RuntimeError):
            self.game.open_mortgage()


class CloseTest(unittest.TestCase):
    def setUp(self):
        self.game = open_turn()
        self.deeds = give(self.game, self.game.current, BROWN)
        self.cash = self.game.current.cash

    def test_closing_an_unopened_screen_raises(self):
        with self.assertRaises(RuntimeError):
            self.game.close_mortgage()

    def test_cancel_drops_the_whole_draft(self):
        ledger = self.game.open_mortgage()
        ledger.mortgage(self.deeds[0])
        self.assertFalse(self.game.close_mortgage(commit=False))
        self.assertIsNone(self.game.mortgage)
        self.assertFalse(self.deeds[0].mortgaged)
        self.assertEqual(self.game.current.cash, self.cash)

    def test_confirm_flips_the_flags_and_pays_out(self):
        ledger = self.game.open_mortgage()
        for deed in self.deeds:
            ledger.mortgage(deed)
        self.assertTrue(self.game.close_mortgage(commit=True))
        self.assertIsNone(self.game.mortgage)
        self.assertTrue(all(d.mortgaged for d in self.deeds))
        self.assertEqual(self.game.current.cash, self.cash + 60)

    def test_confirm_on_an_untouched_draft_reports_false(self):
        self.game.open_mortgage()
        self.assertFalse(self.game.close_mortgage(commit=True))
        self.assertIsNone(self.game.mortgage)

    def test_confirm_lifts_a_mortgage_at_110_percent(self):
        self.deeds[0].mortgaged = True
        ledger = self.game.open_mortgage()
        ledger.unmortgage(self.deeds[0])
        self.assertTrue(self.game.close_mortgage(commit=True))
        self.assertFalse(self.deeds[0].mortgaged)
        self.assertEqual(self.game.current.cash, self.cash - 33)

    def test_the_transcript_says_what_happened(self):
        ledger = self.game.open_mortgage()
        ledger.mortgage(self.deeds[1])
        self.game.close_mortgage(commit=True)
        line = self.game.log[-1]
        self.assertIn("Ada", line)
        self.assertIn("mortgage Baltic Avenue", line)
        self.assertIn("receive $30", line)

    def test_a_cancelled_draft_says_nothing(self):
        before = list(self.game.log)
        ledger = self.game.open_mortgage()
        ledger.mortgage(self.deeds[0])
        self.game.close_mortgage(commit=False)
        self.assertEqual(self.game.log, before)

    def test_the_turn_carries_on_afterwards(self):
        ledger = self.game.open_mortgage()
        ledger.mortgage(self.deeds[0])
        self.game.close_mortgage(commit=True)
        self.assertIs(self.game.state, State.PLAYER_ACTIONS)
        self.assertIn(Action.END_TURN, self.game.available_actions())
        self.game.end_turn()
        self.assertIs(self.game.current, self.game.players[1])


class TurnTest(unittest.TestCase):
    def test_a_new_turn_clears_a_screen_left_open(self):
        game = open_turn()
        give(game, game.current, BROWN)
        game.open_mortgage()
        game.state = State.PLAYER_ACTIONS
        game._begin_turn()
        self.assertIsNone(game.mortgage)

    def test_mortgaging_can_be_done_after_building(self):
        game = open_turn()
        lots = give(game, game.current, BROWN)
        plan = game.open_build()
        plan.add(lots[0])
        plan.add(lots[1])
        game.close_build(commit=True)
        self.assertFalse(game.can_mortgage(), "houses are standing on the group")
        plan = game.open_build()
        plan.remove(lots[1])
        plan.remove(lots[0])
        game.close_build(commit=True)
        self.assertTrue(game.can_mortgage(), "and now the group is bare again")


class RentTest(unittest.TestCase):
    """A mortgaged deed charges no rent, played out through the turn loop."""

    def test_a_tenant_landing_on_a_mortgaged_lot_pays_nothing(self):
        # Ada rolls a 3 onto Baltic Avenue, which Bob owns and has mortgaged.
        game = make_game(rolls=[(1, 2)])
        deed = give(game, game.players[1], [BALTIC])[0]
        ledger = MortgageLedger(game.players[1], game.properties)
        ledger.mortgage(deed)
        ledger.commit()
        bob_cash = game.players[1].cash
        ada_cash = game.players[0].cash
        take_turn(game)
        self.assertEqual(game.players[0].cash, ada_cash, "no rent was charged")
        self.assertEqual(game.players[1].cash, bob_cash)
        self.assertIn("is mortgaged, so no rent is owed", game.log[-1])

    def test_lifting_it_turns_the_rent_back_on(self):
        game = make_game(rolls=[(1, 2)])
        deed = give(game, game.players[1], [BALTIC])[0]
        deed.mortgaged = True
        game.seat = 1
        game.state = State.PLAYER_ACTIONS
        ledger = game.open_mortgage()
        ledger.unmortgage(deed)
        game.close_mortgage(commit=True)
        game.seat = 0
        game._begin_turn()
        ada_cash = game.players[0].cash
        take_turn(game)
        self.assertEqual(game.players[0].cash, ada_cash - 4)


class InheritedTest(unittest.TestCase):
    """The plan's last line: a mortgaged deed that changes hands.

    Its new owner may lift it at the same 110%, or leave it alone -- and while
    they leave it alone it earns them nothing.
    """

    def test_a_mortgaged_deed_traded_in_can_be_lifted_by_its_new_owner(self):
        game = open_turn()
        ada, bob = game.players
        deed = give(game, bob, [BALTIC])[0]
        deed.mortgaged = True
        trade = game.open_trade(partner=bob)
        trade.add_deed(deed)
        game.propose_trade()
        self.assertTrue(game.accept_trade())
        self.assertIs(deed.owner, ada)
        self.assertTrue(deed.mortgaged, "it travelled as-is")

        cash = ada.cash
        ledger = game.open_mortgage()
        self.assertIn(deed, ledger.deeds)
        self.assertTrue(ledger.unmortgage(deed))
        self.assertTrue(game.close_mortgage(commit=True))
        self.assertFalse(deed.mortgaged)
        self.assertEqual(ada.cash, cash - 33)

    def test_a_mortgaged_deed_left_alone_earns_its_new_owner_nothing(self):
        game = open_turn()
        ada, bob = game.players
        deed = give(game, bob, [BALTIC])[0]
        deed.mortgaged = True
        trade = game.open_trade(partner=bob)
        trade.add_deed(deed)
        game.propose_trade()
        game.accept_trade()
        self.assertEqual(deed.current_rent(), 0)

    def test_a_deed_inherited_from_a_bankruptcy_can_be_lifted(self):
        # Bob owes Ada more than he can raise, so his deeds -- including the
        # mortgaged one -- pass to her as they stand.
        game = open_turn()
        ada, bob = game.players
        deed = give(game, bob, [BALTIC])[0]
        deed.mortgaged = True
        bob.cash = 0
        game._charge(bob, 500, creditor=ada)
        self.assertTrue(bob.is_bankrupt)
        self.assertIs(deed.owner, ada)
        self.assertTrue(deed.mortgaged, "the deed transferred as-is")

        game.seat = 0
        game.state = State.PLAYER_ACTIONS
        cash = ada.cash
        ledger = game.open_mortgage()
        self.assertTrue(ledger.unmortgage(deed))
        self.assertTrue(game.close_mortgage(commit=True))
        self.assertFalse(deed.mortgaged)
        self.assertEqual(ada.cash, cash - 33)

    def test_a_deed_the_bank_took_back_comes_off_the_screen(self):
        game = open_turn()
        ada, bob = game.players
        deed = give(game, bob, [BALTIC])[0]
        deed.mortgaged = True
        bob.cash = 0
        game._charge(bob, 500)  # owed to the bank, so the deed goes on the shelf
        self.assertTrue(bob.is_bankrupt)
        self.assertIsNone(deed.owner)
        self.assertFalse(deed.mortgaged, "a deed on the shelf is for sale")
        game.seat = 0
        game.state = State.PLAYER_ACTIONS
        self.assertFalse(game.can_mortgage())


class ForcedSaleTest(unittest.TestCase):
    """Phase 13's forced sale mortgages deeds too; the two must agree."""

    def test_a_forced_mortgage_shows_up_on_the_screen_as_liftable(self):
        game = open_turn()
        ada = game.current
        deeds = give(game, ada, BROWN)
        ada.cash = 0
        game._charge(ada, 50)  # $60 of mortgage value covers it
        self.assertFalse(ada.is_bankrupt)
        self.assertTrue(any(d.mortgaged for d in deeds))

        game.state = State.PLAYER_ACTIONS
        ledger = game.open_mortgage()
        forced = [d for d in deeds if d.mortgaged]
        for deed in forced:
            self.assertTrue(ledger.state(deed))
            # $10 change from the forced sale will not lift a $33 mortgage.
            self.assertEqual(ledger.blocker(deed), CASH_REASON)
        game.close_mortgage()
        ada.cash = 100  # and now it will
        ledger = game.open_mortgage()
        self.assertTrue(ledger.can_unmortgage(forced[0]))
        self.assertIsNone(ledger.blocker(forced[0]))

    def test_the_forced_sale_never_mortgages_a_built_lot(self):
        game = open_turn()
        ada = game.current
        lots = give(game, ada, BROWN)
        plan = game.open_build()
        plan.add(lots[0])
        plan.add(lots[1])
        game.close_build(commit=True)
        ada.cash = 0
        game._charge(ada, 60)
        for lot in lots:
            if lot.mortgaged:
                self.assertEqual(
                    lot.building_level, 0, f"{lot.name} kept a house"
                )


class SoakTest(unittest.TestCase):
    """Whole games played out by bots that buy, bid, build and mortgage.

    The mortgaging is what these add over ``test_bankruptcy_game.py``'s soak:
    a table that keeps flipping deeds either way is the one where a stale
    flag, a double payout or a lot mortgaged out from under its houses would
    show up. The invariants are checked after every step of the game.
    """

    TURNS = 300

    def check_invariants(self, game: Game) -> None:
        for player in game.players:
            self.assertGreaterEqual(player.cash, 0, f"{player.name} overdrew")
        for deed in game.properties:
            if deed.owner is None:
                self.assertFalse(
                    deed.mortgaged, f"{deed.name} is on the shelf, mortgaged"
                )
                self.assertEqual(deed.building_level, 0)
                continue
            self.assertFalse(
                deed.owner.is_bankrupt, f"{deed.name} is held by a dead hand"
            )
            if deed.mortgaged:
                # The rule the whole phase turns on: a mortgaged lot cannot be
                # standing under a building, its own or its neighbours'.
                self.assertEqual(
                    deed.building_level, 0, f"{deed.name} is mortgaged and built on"
                )
                group = [p for p in game.properties if p.group == deed.group]
                self.assertTrue(
                    all(p.building_level == 0 for p in group),
                    f"{deed.name} is mortgaged under its group's buildings",
                )
                self.assertEqual(
                    deed.current_rent(dice_total=7),
                    0,
                    f"{deed.name} is mortgaged and still charging rent",
                )
        houses = sum(d.house_count for d in game.properties)
        hotels = sum(d.hotel_count for d in game.properties)
        self.assertEqual(game.bank.houses + houses, HOUSE_SUPPLY)
        self.assertEqual(game.bank.hotels + hotels, HOTEL_SUPPLY)

    def play(self, seed: int, cash: int, names=("Ada", "Bob", "Cleo")) -> Game:
        rng = random.Random(seed)
        game = make_game(cash=cash, names=names)
        #: How many deeds each way the bots actually moved, and how many
        #: drafts they threw away.
        self.mortgaged = 0
        self.lifted = 0
        self.cancelled = 0

        steps = 0
        turns = 0
        while turns < self.TURNS and game.state is not State.GAME_OVER:
            steps += 1
            self.assertLess(steps, 200 * self.TURNS, "the turn loop is spinning")
            game.update(0)
            self.check_invariants(game)
            if game.state is State.GAME_OVER:
                break

            if game.auction is not None:
                if rng.random() < 0.5 and game.bid(game.auction.min_bid):
                    continue
                game.pass_bid()
                continue
            if game.prompt is not None:
                options = [c.key for c in game.prompt.options if c.enabled]
                game.choose(rng.choice(options))
                continue

            actions = game.available_actions()
            if Action.BUILD in actions and rng.random() < 0.6:
                self.build_something(game, rng)
                continue
            if Action.MORTGAGE in actions and rng.random() < 0.5:
                self.mortgage_something(game, rng)
                continue
            if Action.ROLL in actions:
                game.perform(Action.ROLL)
            elif Action.END_TURN in actions:
                game.perform(Action.END_TURN)
                turns += 1
            else:
                self.fail(f"stuck in {game.state.value} with nothing to do")

        self.check_invariants(game)
        self.turns = turns
        return game

    @staticmethod
    def build_something(game: Game, rng: random.Random) -> None:
        plan = game.open_build()
        for _ in range(rng.randint(1, 5)):
            lots = [lot for lot in plan.all_lots if plan.can_add(lot)]
            if not lots:
                break
            plan.add(rng.choice(lots))
        game.close_build(commit=plan.changed)

    def mortgage_something(self, game: Game, rng: random.Random) -> None:
        """Flip a few deeds either way, and audit what Confirm or Cancel did.

        This is where the accounting is actually checked: the draft says what
        it would cost before the click, and the wallet has to agree with that
        to the dollar afterwards. Half the drafts are cancelled instead, which
        has to leave every flag and every dollar exactly as it was.
        """
        player = game.current
        ledger = game.open_mortgage()
        for _ in range(rng.randint(1, 4)):
            live = [d for d in ledger.deeds if ledger.can_toggle(d)]
            if not live:
                break
            ledger.toggle(rng.choice(live))
        if not ledger.changed:
            game.close_mortgage(commit=False)
            return

        # Read all of this before committing: the draft goes level with the
        # board the moment the flags flip.
        cost = ledger.cost
        taken = [d for d, s in ledger.states.items() if s and not d.mortgaged]
        freed = [d for d, s in ledger.states.items() if d.mortgaged and not s]
        before = player.cash
        flags = {d: d.mortgaged for d in ledger.deeds}

        if rng.random() < 0.5:
            self.assertFalse(game.close_mortgage(commit=False))
            self.assertEqual(player.cash, before, "Cancel moved money")
            self.assertEqual(
                {d: d.mortgaged for d in flags}, flags, "Cancel flipped a flag"
            )
            self.cancelled += 1
            return

        self.assertTrue(game.close_mortgage(commit=True))
        self.assertEqual(
            player.cash, before - cost, "the bank paid the wrong amount"
        )
        for deed in taken:
            self.assertTrue(deed.mortgaged, f"{deed.name} was not mortgaged")
        for deed in freed:
            self.assertFalse(deed.mortgaged, f"{deed.name} was not freed")
        self.mortgaged += len(taken)
        self.lifted += len(freed)

    def test_a_rich_table_plays_itself_out(self):
        self.play(seed=7, cash=2500)
        self.assertGreater(self.mortgaged, 0, "nobody ever mortgaged anything")
        self.assertGreater(self.lifted, 0, "nobody ever lifted a mortgage")

    def test_a_poor_table_plays_itself_out_to_a_winner(self):
        """A game that really ends, with the mortgaging running all the way.

        Phase 13's forced sale mortgages deeds behind the players' backs while
        this is going on, so it is also the check that the two halves of the
        mortgage flag never disagree.
        """
        game = self.play(seed=1, cash=300)
        self.assertIs(game.state, State.GAME_OVER)
        self.assertEqual(len(game.active_players), 1)
        self.assertIs(game.winner, game.active_players[0])
        self.assertGreater(self.mortgaged, 0, "nobody ever mortgaged anything")
        self.assertGreater(self.lifted, 0, "nobody ever lifted a mortgage")

    def test_a_six_handed_game_holds_together(self):
        game = self.play(
            seed=11,
            cash=1200,
            names=("Ada", "Bob", "Cleo", "Dan", "Eve", "Fay"),
        )
        self.assertGreater(self.mortgaged, 0)
        self.assertEqual(len(game.players), 6)

    def test_cancelled_drafts_happen_and_leave_nothing_behind(self):
        """The Cancel half of :meth:`mortgage_something`, actually exercised.

        The per-draft audit lives in the bot, so this only has to prove the
        bot really took both branches -- otherwise a leaky Cancel could sit
        there unnoticed.
        """
        game = self.play(seed=5, cash=1500)
        self.assertGreater(self.cancelled, 0, "no draft was ever cancelled")
        self.assertGreater(self.mortgaged, 0, "no draft was ever committed")
        self.assertIsNot(game.state, State.SETUP)


if __name__ == "__main__":
    unittest.main()
