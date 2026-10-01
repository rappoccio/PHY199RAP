"""Phase 9 tests: the Build button's place in the turn loop.

``test_building.py`` covers the rules on their own; this file covers how they
join the game -- when the button is live, what opening the screen does to the
rest of the turn, and that Confirm and Cancel land where they should. The
board is un-animated exactly as in ``test_game.py``, and no pygame is imported.
"""

from __future__ import annotations

import unittest

from monopoly.building import HOTEL_SUPPLY, HOUSE_SUPPLY, Bank, BuildPlan
from monopoly.game import Action, Game, State
from monopoly.player import Player
from monopoly.property import HOTEL_LEVEL, MAX_HOUSES

from tests.test_game import make_game, take_turn

BROWN = (1, 3)
LIGHT_BLUE = (6, 8, 9)


def give(game: Game, player: Player, indices) -> list:
    """Hand ``player`` the deeds at ``indices``; return them in board order."""
    deeds = [game.deed(i) for i in indices]
    for deed in deeds:
        player.add_property(deed)
    return deeds


def in_player_actions(game: Game) -> None:
    """Take a turn that lands somewhere harmless and leaves the turn open."""
    take_turn(game)


class BankTest(unittest.TestCase):
    def test_a_game_opens_the_box(self):
        game = make_game()
        self.assertEqual(game.bank.houses, HOUSE_SUPPLY)
        self.assertEqual(game.bank.hotels, HOTEL_SUPPLY)

    def test_a_bank_can_be_handed_in(self):
        bank = Bank(houses=4, hotels=1)
        game = make_game(bank=bank)
        self.assertIs(game.bank, bank)


class ButtonTest(unittest.TestCase):
    def setUp(self):
        # Income Tax at index 4: a landing with no prompt and no doubles.
        self.game = make_game(rolls=[(1, 3)])
        in_player_actions(self.game)

    def test_without_a_whole_group_there_is_nothing_to_build(self):
        self.assertFalse(self.game.can_build())
        self.assertNotIn(Action.BUILD, self.game.available_actions())

    def test_a_whole_group_lights_the_button(self):
        give(self.game, self.game.current, BROWN)
        self.assertTrue(self.game.can_build())
        self.assertIn(Action.BUILD, self.game.available_actions())

    def test_a_mortgaged_lot_puts_the_button_out(self):
        lots = give(self.game, self.game.current, BROWN)
        lots[0].mortgaged = True
        self.assertFalse(self.game.can_build())

    def test_the_button_is_the_current_players(self):
        give(self.game, self.game.players[1], BROWN)
        self.assertFalse(self.game.can_build())

    def test_there_is_no_building_before_the_roll(self):
        game = make_game()
        give(game, game.current, BROWN)
        self.assertIs(game.state, State.PLAYER_TURN_START)
        self.assertEqual(game.available_actions(), frozenset({Action.ROLL}))

    def test_a_jailed_player_may_still_build(self):
        game = make_game(rolls=[(1, 2), (2, 3)])
        give(game, game.current, BROWN)
        game.current.in_jail = True
        game._begin_turn()
        game.choose("roll")  # misses the doubles, stays in Jail
        game.update(0)
        self.assertIs(game.state, State.PLAYER_ACTIONS)
        self.assertIn(Action.BUILD, game.available_actions())


class OpenTest(unittest.TestCase):
    def setUp(self):
        self.game = make_game(rolls=[(1, 3)])
        in_player_actions(self.game)
        self.lots = give(self.game, self.game.current, BROWN)

    def test_perform_opens_the_screen(self):
        self.assertTrue(self.game.perform(Action.BUILD))
        self.assertIsInstance(self.game.build, BuildPlan)
        self.assertIs(self.game.build.player, self.game.current)
        self.assertEqual(self.game.build.groups, ["brown"])

    def test_an_open_screen_is_modal(self):
        self.game.perform(Action.BUILD)
        self.assertEqual(self.game.available_actions(), frozenset())
        self.assertFalse(self.game.perform(Action.END_TURN))
        self.assertIs(self.game.state, State.PLAYER_ACTIONS)

    def test_the_draft_starts_from_the_board(self):
        self.lots[0].houses = 2
        self.lots[1].houses = 2
        plan = self.game.open_build()
        self.assertEqual([plan.level(lot) for lot in self.lots], [2, 2])
        self.assertFalse(plan.changed)

    def test_the_draft_shares_the_games_bank(self):
        self.game.bank.houses = 5
        plan = self.game.open_build()
        self.assertIs(plan.bank, self.game.bank)
        self.assertEqual(plan.houses, 5)

    def test_opening_mid_roll_raises(self):
        game = make_game()
        give(game, game.current, BROWN)
        with self.assertRaises(RuntimeError):
            game.open_build()

    def test_opening_over_a_prompt_raises(self):
        game = make_game(rolls=[(1, 2)])  # Baltic Avenue, unowned
        take_turn(game)
        self.assertIsNotNone(game.prompt)
        game.state = State.PLAYER_ACTIONS
        with self.assertRaises(RuntimeError):
            game.open_build()

    def test_a_registered_handler_still_wins(self):
        seen = []
        self.game.action_handlers[Action.BUILD] = seen.append
        self.assertTrue(self.game.perform(Action.BUILD))
        self.assertEqual(seen, [self.game])
        self.assertIsNone(self.game.build)


class CloseTest(unittest.TestCase):
    def setUp(self):
        self.game = make_game(rolls=[(1, 3)])
        in_player_actions(self.game)
        self.player = self.game.current
        self.lots = give(self.game, self.player, BROWN)
        self.cash = self.player.cash
        self.plan = self.game.open_build()

    def test_confirm_builds_and_charges(self):
        self.plan.add(self.lots[0])
        self.plan.add(self.lots[1])
        self.assertTrue(self.game.close_build(commit=True))
        self.assertIsNone(self.game.build)
        self.assertEqual([lot.houses for lot in self.lots], [1, 1])
        self.assertEqual(self.player.cash, self.cash - 100)
        self.assertEqual(self.game.bank.houses, HOUSE_SUPPLY - 2)

    def test_confirm_logs_what_it_did(self):
        self.plan.add(self.lots[0])
        self.game.close_build(commit=True)
        self.assertIn("build 1", self.game.message)
        self.assertIn("$50", self.game.message)
        self.assertIn(self.player.name, self.game.message)

    def test_cancel_throws_the_draft_away(self):
        self.plan.add(self.lots[0])
        self.assertFalse(self.game.close_build())
        self.assertIsNone(self.game.build)
        self.assertEqual(self.lots[0].houses, 0)
        self.assertEqual(self.player.cash, self.cash)
        self.assertEqual(self.game.bank.houses, HOUSE_SUPPLY)

    def test_confirming_an_untouched_draft_changes_nothing(self):
        self.assertFalse(self.game.close_build(commit=True))
        self.assertEqual(self.player.cash, self.cash)

    def test_closing_a_screen_that_is_not_open_raises(self):
        self.game.close_build()
        with self.assertRaises(RuntimeError):
            self.game.close_build()

    def test_the_turn_carries_on_afterwards(self):
        self.plan.add(self.lots[0])
        self.game.close_build(commit=True)
        self.assertIn(Action.END_TURN, self.game.available_actions())
        self.assertTrue(self.game.perform(Action.END_TURN))
        self.assertIs(self.game.current, self.game.players[1])

    def test_a_screen_left_open_does_not_survive_the_turn(self):
        self.game.build = self.plan
        self.game.end_turn()
        self.assertIsNone(self.game.build)
        self.assertNotEqual(self.game.available_actions(), frozenset())


class RentTest(unittest.TestCase):
    """The point of building: the rent the next tenant pays."""

    def setUp(self):
        self.game = make_game(rolls=[(1, 3)], cash=5000)
        in_player_actions(self.game)
        self.owner = self.game.players[1]
        self.lots = give(self.game, self.owner, LIGHT_BLUE)

    def build_to(self, level: int) -> None:
        plan = BuildPlan(self.owner, self.game.properties, self.game.bank)
        for _ in range(level):
            for lot in self.lots:
                self.assertTrue(plan.add(lot))
        self.assertTrue(plan.commit())

    def test_an_unimproved_monopoly_charges_double(self):
        # Oriental Avenue (index 6) rents at $6, doubled for the monopoly.
        game = make_game(rolls=[(3, 3)], cash=5000)
        take_turn(game)
        owner = game.players[1]
        give(game, owner, LIGHT_BLUE)
        self.assertEqual(game.deed(6).current_rent(), 12)

    def test_three_houses_charge_the_table_rate(self):
        self.build_to(3)
        self.assertEqual(self.game.deed(6).current_rent(), 270)

    def test_a_tenant_pays_the_improved_rent(self):
        self.build_to(3)
        game = self.game
        tenant = game.current
        cash = tenant.cash
        owner_cash = self.owner.cash
        tenant.position = 5
        game._start_move(1)  # onto Oriental Avenue
        game.update(0)
        self.assertEqual(tenant.cash, cash - 270)
        self.assertEqual(self.owner.cash, owner_cash + 270)

    def test_a_hotel_charges_the_top_rate(self):
        self.build_to(HOTEL_LEVEL)
        self.assertEqual(self.game.deed(6).current_rent(), 550)
        self.assertEqual(self.game.bank.hotels, HOTEL_SUPPLY - 3)
        self.assertEqual(self.game.bank.houses, HOUSE_SUPPLY)


class SupplyAcrossPlayersTest(unittest.TestCase):
    """One player's houses are houses nobody else can have."""

    def setUp(self):
        self.game = make_game(rolls=[(1, 3)], cash=5000)
        in_player_actions(self.game)
        self.ada, self.bob = self.game.players
        self.ada_lots = give(self.game, self.ada, LIGHT_BLUE)
        self.bob_lots = give(self.game, self.bob, BROWN)

    def test_an_empty_box_blocks_the_other_player(self):
        self.game.bank.houses = 2
        plan = BuildPlan(self.ada, self.game.properties, self.game.bank)
        for lot in self.ada_lots[:2]:
            self.assertTrue(plan.add(lot))
        self.assertTrue(plan.commit())
        self.assertEqual(self.game.bank.houses, 0)

        bobs = BuildPlan(self.bob, self.game.properties, self.game.bank)
        self.assertFalse(bobs.can_add(self.bob_lots[0]))

    def test_selling_back_frees_the_box_again(self):
        self.game.bank.houses = 1
        plan = BuildPlan(self.ada, self.game.properties, self.game.bank)
        plan.add(self.ada_lots[0])
        plan.commit()

        bobs = BuildPlan(self.bob, self.game.properties, self.game.bank)
        self.assertFalse(bobs.can_add(self.bob_lots[0]))

        back = BuildPlan(self.ada, self.game.properties, self.game.bank)
        back.remove(self.ada_lots[0])
        back.commit()
        self.assertEqual(self.game.bank.houses, 1)

        bobs = BuildPlan(self.bob, self.game.properties, self.game.bank)
        self.assertTrue(bobs.can_add(self.bob_lots[0]))


class RepairsTest(unittest.TestCase):
    """The "pay per building" cards read what Phase 9 put on the board."""

    def test_a_repairs_card_prices_real_buildings(self):
        game = make_game(rolls=[(1, 3)], cash=5000)
        take_turn(game)
        player = game.current
        lots = give(game, player, LIGHT_BLUE)
        plan = BuildPlan(player, game.properties, game.bank)
        for _ in range(MAX_HOUSES):
            for lot in lots:
                plan.add(lot)
        plan.add(lots[0])  # one hotel, two lots of four houses
        plan.commit()

        cash = player.cash
        game._pay_per_building(
            type("C", (), {"per_house": 25, "per_hotel": 100})()
        )
        self.assertEqual(player.cash, cash - (8 * 25 + 100))


class WholeGameTest(unittest.TestCase):
    """A game played end to end by a bot that builds whenever it can.

    Nothing here checks a particular number -- the point is that the building
    rules hold at *every* point of a real game rather than only in a fixture:
    the box never goes negative, nobody ever spends money they do not have,
    and no group is ever left unevenly built. A broken invariant shows up as
    the failing assertion inside the loop, not as a crash a hundred turns on.
    """

    TURNS = 400

    def setUp(self):
        self.game = make_game(cash=5000, names=("Ada", "Bob", "Cleo"))
        self.stock = (HOUSE_SUPPLY, HOTEL_SUPPLY)

    def check_invariants(self) -> None:
        game = self.game
        self.assertGreaterEqual(game.bank.houses, 0)
        self.assertGreaterEqual(game.bank.hotels, 0)
        houses, hotels = 0, 0
        for deed in game.properties:
            self.assertGreaterEqual(deed.houses, 0)
            self.assertLessEqual(deed.houses, MAX_HOUSES)
            if deed.has_hotel:
                self.assertEqual(deed.houses, 0)
            if deed.building_level:
                self.assertIsNotNone(deed.owner, f"{deed.name} is built but unowned")
                self.assertFalse(deed.mortgaged, f"{deed.name} is built and mortgaged")
            houses += deed.house_count
            hotels += deed.hotel_count
        # Buildings are pieces: every one is either on the board or in the box.
        self.assertEqual((houses + game.bank.houses, hotels + game.bank.hotels),
                         self.stock)
        for player in game.players:
            self.assertGreaterEqual(player.cash, 0)
        self.check_even_building()

    def check_even_building(self) -> None:
        """No lot of a group may stand more than one building above another."""
        by_group: dict[str, list[int]] = {}
        for deed in self.game.properties:
            if deed.is_property:
                by_group.setdefault(deed.group, []).append(deed.building_level)
        for group, levels in by_group.items():
            self.assertLessEqual(max(levels) - min(levels), 1, group)

    def build_everything(self) -> None:
        """Open the build screen and pour cash into it until nothing is legal."""
        game = self.game
        if not game.can_build():
            return
        plan = game.open_build()
        for _ in range(64):
            for lot in plan.all_lots:
                if plan.can_add(lot):
                    self.assertTrue(plan.add(lot))
                    break
            else:
                break
        game.close_build(commit=True)

    def test_a_bot_that_always_builds_never_breaks_the_rules(self):
        game = self.game
        self.stock = (game.bank.houses, game.bank.hotels)
        built = False
        for _ in range(self.TURNS):
            if game.state is State.GAME_OVER:
                break
            while game.prompt is not None:
                # Always buy what is for sale, and acknowledge everything else.
                options = [c for c in game.prompt.options if c.enabled]
                game.choose(options[0].key)
                game.update(0)
            while game.auction is not None:
                # Phase 10: the bot never bids -- it buys at the asking price
                # when it can, so a sale only happens when it cannot pay.
                game.pass_bid()
            if game.state is State.PLAYER_TURN_START:
                game.perform(Action.ROLL, 0)
                game.update(0)
                continue
            if game.state is State.PLAYER_ACTIONS:
                built = built or game.can_build()
                self.build_everything()
                self.check_invariants()
                game.perform(Action.END_TURN)
        self.assertTrue(built, "the bot never assembled a group -- test is toothless")
        self.check_invariants()

    def test_the_bot_really_puts_buildings_on_the_board(self):
        self.test_a_bot_that_always_builds_never_breaks_the_rules()
        houses, hotels = 0, 0
        for deed in self.game.properties:
            houses += deed.house_count
            hotels += deed.hotel_count
        self.assertGreater(hotels, 0, "no group was ever built all the way up")

    def test_a_short_box_holds_through_a_whole_game(self):
        """The same game with almost no buildings in the box.

        A greedy bot with money and a nearly empty box is the case the supply
        rules exist for: it hits the limit on nearly every turn, so this is
        where a counter that drifts would show up.
        """
        self.game = make_game(cash=5000, names=("Ada", "Bob", "Cleo"))
        self.game.bank.houses = 6
        self.game.bank.hotels = 1
        self.test_a_bot_that_always_builds_never_breaks_the_rules()
        standing = sum(d.building_level for d in self.game.properties)
        self.assertGreater(standing, 0, "the bot built nothing at all")
        self.assertLessEqual(self.game.bank.houses, 6)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
