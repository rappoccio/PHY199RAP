"""Phase 13 tests: debts, forced sales and bankruptcy inside a real turn.

``test_bankruptcy.py`` covers the rules on their own. This file covers the
join: a debt raised by a landing is answered before the turn moves on, a
player who goes under leaves the turn order there and then, and a table with
one player left is over.

The fixtures are :mod:`tests.test_game`'s, so the dice are scripted and
nothing is animated -- one :meth:`Game.update` carries a turn from the roll
to the landing, and from the landing to the wind-up it causes. No pygame
here either.
"""

from __future__ import annotations

import random
import unittest

from monopoly.bankruptcy import Settlement
from monopoly.building import HOTEL_SUPPLY, HOUSE_SUPPLY
from monopoly.game import (
    AUCTION_KEY,
    JAIL_FINE,
    OK_KEY,
    Action,
    Debt,
    Game,
    State,
)
from monopoly.player import Player
from tests.test_game import (
    answer,
    make_game,
    one_card_deck,
    take_turn,
)

#: Rolls, by where they land a player starting on Go.
BALTIC = (1, 2)  # 0 -> 3, Baltic Avenue
INCOME_TAX = (1, 3)  # 0 -> 4, Income Tax, $200
TAX_DOUBLES = (2, 2)  # the same square, but doubles
THREE = (1, 2)  # three spaces from wherever the player stands

MEDITERRANEAN, BALTIC_INDEX, READING = 1, 3, 5
ORIENTAL, VERMONT, CONNECTICUT = 6, 8, 9
PARK_PLACE, BOARDWALK = 37, 39


class BankruptcyGameTestCase(unittest.TestCase):
    """Helpers shared by the cases below."""

    def three_handed(self, rolls=(), cash=1500) -> Game:
        return make_game(rolls=rolls, cash=cash, names=("Ada", "Bob", "Cleo"))

    def give(self, game: Game, player: Player, *indices):
        deeds = [game.deed(i) for i in indices]
        for deed in deeds:
            player.add_property(deed)
        return deeds

    def send_to(self, game: Game, index: int) -> None:
        """Stand the player on turn three spaces short of ``index``."""
        game.current.position = (index - 3) % 40


class RentBankruptcyTest(BankruptcyGameTestCase):
    """A rent the tenant cannot meet, owed to the landlord."""

    def test_the_tenant_goes_under(self):
        game = make_game(rolls=[BALTIC])
        ada, bob = game.players
        ada.cash = 1
        self.give(game, bob, BALTIC_INDEX)  # $4 rent
        take_turn(game)
        self.assertTrue(ada.is_bankrupt)
        self.assertEqual(ada.cash, 0)
        self.assertIsNone(game.debt, "the debt is answered, not left standing")

    def test_the_landlord_takes_what_there_was(self):
        game = make_game(rolls=[BALTIC])
        ada, bob = game.players
        ada.cash = 1
        self.give(game, bob, BALTIC_INDEX)
        take_turn(game)
        self.assertEqual(bob.cash, 1500 + 1, "every dollar Ada had")

    def test_the_deeds_follow_the_cash(self):
        game = self.three_handed(rolls=[THREE])
        ada, bob = game.players[0], game.players[1]
        ada.cash = 10
        self.give(game, ada, MEDITERRANEAN, BALTIC_INDEX)
        self.give(game, bob, PARK_PLACE, BOARDWALK)  # a monopoly: $100 rent
        self.send_to(game, BOARDWALK)
        take_turn(game)
        self.assertTrue(ada.is_bankrupt)
        self.assertEqual(ada.properties, [])
        self.assertEqual(
            sorted(d.index for d in bob.properties),
            [MEDITERRANEAN, BALTIC_INDEX, PARK_PLACE, BOARDWALK],
        )
        for deed in bob.properties:
            self.assertIs(deed.owner, bob)

    def test_the_buildings_come_down_before_the_deeds_move(self):
        game = self.three_handed(rolls=[THREE])
        ada, bob = game.players[0], game.players[1]
        ada.cash = 0
        browns = self.give(game, ada, MEDITERRANEAN, BALTIC_INDEX)
        for lot in browns:
            lot.houses = 2
            game.bank.houses -= 2
        boardwalk = self.give(game, bob, PARK_PLACE, BOARDWALK)[1]
        boardwalk.has_hotel = True
        game.bank.hotels -= 1
        self.send_to(game, BOARDWALK)
        take_turn(game)
        self.assertTrue(ada.is_bankrupt)
        for lot in browns:
            self.assertEqual(lot.building_level, 0)
            self.assertIs(lot.owner, bob)
        self.assertEqual(game.bank.houses, HOUSE_SUPPLY, "four houses, back in the box")
        self.assertEqual(bob.cash, 1500 + 100, "the half-price sale is Ada's money")

    def test_a_mortgaged_deed_transfers_still_mortgaged(self):
        game = self.three_handed(rolls=[THREE])
        ada, bob = game.players[0], game.players[1]
        ada.cash = 0
        deed = self.give(game, ada, READING)[0]
        deed.mortgaged = True
        self.give(game, bob, PARK_PLACE, BOARDWALK)
        self.send_to(game, BOARDWALK)
        take_turn(game)
        self.assertIs(deed.owner, bob)
        self.assertTrue(deed.mortgaged)


class ForcedSaleTest(BankruptcyGameTestCase):
    """A debt the player can still cover, if they are made to sell."""

    def test_a_deed_is_mortgaged_to_pay_the_rent(self):
        game = make_game(rolls=[BALTIC])
        ada, bob = game.players
        ada.cash = 1
        boardwalk = self.give(game, ada, BOARDWALK)[0]
        self.give(game, bob, BALTIC_INDEX)  # $4 rent
        take_turn(game)
        self.assertFalse(ada.is_bankrupt)
        self.assertTrue(boardwalk.mortgaged)
        self.assertEqual(ada.cash, 200 - 3)
        self.assertEqual(bob.cash, 1500 + 4, "the landlord is paid in full")
        self.assertIsNone(game.debt)

    def test_the_turn_carries_on_afterwards(self):
        game = make_game(rolls=[BALTIC])
        ada, bob = game.players
        ada.cash = 1
        self.give(game, ada, BOARDWALK)
        self.give(game, bob, BALTIC_INDEX)
        take_turn(game)
        self.assertIs(game.state, State.PLAYER_ACTIONS)
        self.assertIn(Action.END_TURN, game.available_actions())

    def test_the_tax_man_is_paid_the_same_way(self):
        game = make_game(rolls=[INCOME_TAX])
        ada = game.players[0]
        ada.cash = 50
        boardwalk = self.give(game, ada, BOARDWALK)[0]
        take_turn(game)
        self.assertFalse(ada.is_bankrupt)
        self.assertTrue(boardwalk.mortgaged)
        self.assertEqual(ada.cash, 250 - 200)

    def test_the_buildings_go_before_the_deeds(self):
        game = make_game(rolls=[INCOME_TAX])
        ada = game.players[0]
        ada.cash = 0
        browns = self.give(game, ada, MEDITERRANEAN, BALTIC_INDEX)
        for lot in browns:
            lot.houses = 4
            game.bank.houses -= 4
        take_turn(game)
        self.assertFalse(ada.is_bankrupt)
        self.assertEqual(ada.cash, 0, "$200 of houses covered $200 exactly")
        self.assertEqual(game.bank.houses, HOUSE_SUPPLY)
        for lot in browns:
            self.assertFalse(lot.mortgaged, "the houses were enough on their own")

    def test_it_stops_as_soon_as_the_money_is_there(self):
        game = make_game(rolls=[BALTIC])
        ada, bob = game.players
        ada.cash = 0
        deeds = self.give(game, ada, MEDITERRANEAN, READING, BOARDWALK)
        self.give(game, bob, BALTIC_INDEX)  # $4 rent
        take_turn(game)
        self.assertTrue(deeds[0].mortgaged, "Mediterranean, first in board order")
        self.assertFalse(deeds[1].mortgaged)
        self.assertFalse(deeds[2].mortgaged)

    def test_the_forced_sale_is_in_the_log(self):
        game = make_game(rolls=[INCOME_TAX])
        ada = game.players[0]
        ada.cash = 0
        self.give(game, ada, BOARDWALK)
        take_turn(game)
        self.assertTrue(
            any("raise $200" in line for line in game.log), game.log[-4:]
        )
        self.assertTrue(any("settles the $200" in line for line in game.log))

    def test_a_forced_sale_in_jail_still_opens_the_cell(self):
        game = make_game(rolls=[(1, 2), (1, 2), (1, 2)])
        ada = game.players[0]
        ada.cash = 0
        self.give(game, ada, BOARDWALK)
        game._go_to_jail(ada)
        for _ in range(3):
            game.seat = 0
            game._begin_turn()
            answer(game, "roll")
        self.assertFalse(ada.is_bankrupt)
        self.assertFalse(ada.in_jail)
        self.assertEqual(ada.cash, 200 - JAIL_FINE)


class BankDebtTest(BankruptcyGameTestCase):
    """A debt owed to the bank puts everything back on the shelf."""

    def make(self) -> Game:
        game = self.three_handed(rolls=[INCOME_TAX])
        ada = game.players[0]
        ada.cash = 50
        self.give(game, ada, ORIENTAL, VERMONT)  # $100 of mortgage value
        return game

    def test_the_player_goes_under(self):
        game = self.make()
        take_turn(game)
        self.assertTrue(game.players[0].is_bankrupt)
        self.assertIsNone(game.last_settlement.creditor)

    def test_the_deeds_go_back_to_being_unowned(self):
        game = self.make()
        take_turn(game)
        for index in (ORIENTAL, VERMONT):
            self.assertIsNone(game.deed(index).owner)
        for player in game.players:
            self.assertEqual(player.properties, [])

    def test_a_deed_on_the_shelf_is_no_longer_mortgaged(self):
        game = self.make()
        game.deed(ORIENTAL).mortgaged = True
        take_turn(game)
        self.assertFalse(game.deed(ORIENTAL).mortgaged)

    def test_the_other_players_gain_nothing(self):
        game = self.make()
        take_turn(game)
        for player in game.players[1:]:
            self.assertEqual(player.cash, 1500)
            self.assertEqual(player.properties, [])

    def test_a_returned_deed_can_be_bought_again(self):
        game = self.make()
        take_turn(game)  # Ada goes under owing the tax man
        game.seat = 1
        game._begin_turn()
        game.rng.faces.extend([1, 5])  # Bob rolls 6 -> Oriental Avenue
        take_turn(game)
        self.assertIsNotNone(game.prompt)
        self.assertIs(game.prompt.deed, game.deed(ORIENTAL))
        answer(game, "buy")
        self.assertIs(game.deed(ORIENTAL).owner, game.players[1])


class TurnOrderTest(BankruptcyGameTestCase):
    """A player who goes under leaves the order where they stand."""

    def bankrupt_ada(self, rolls=(INCOME_TAX,)) -> Game:
        game = self.three_handed(rolls=list(rolls))
        game.players[0].cash = 0
        take_turn(game)
        return game

    def test_the_bankrupt_turn_ends_at_once(self):
        game = self.bankrupt_ada()
        self.assertIs(game.state, State.PLAYER_TURN_START)
        self.assertIs(game.current, game.players[1], "Bob is up")

    def test_the_bankrupt_player_is_never_dealt_in_again(self):
        game = self.bankrupt_ada()
        self.assertEqual(game.active_players, game.players[1:])
        seats = []
        for _ in range(4):
            game.rng.faces.extend([4, 5])  # a quiet nine
            seats.append(game.current.name)
            self.assertFalse(game.current.is_bankrupt)
            take_turn(game)
            if game.prompt is not None:
                answer(game, AUCTION_KEY)
            game.end_turn()
        self.assertEqual(seats, ["Bob", "Cleo", "Bob", "Cleo"])

    def test_doubles_earn_a_bankrupt_player_nothing(self):
        game = self.bankrupt_ada(rolls=[TAX_DOUBLES])
        self.assertIs(game.current, game.players[1], "no second go for the ruined")

    def test_a_bankrupt_player_is_never_charged_again(self):
        game = self.bankrupt_ada()
        ada = game.players[0]
        settlement = game.last_settlement
        self.assertFalse(game._charge(ada, 100))
        self.assertEqual(ada.cash, 0)
        self.assertIsNone(game.debt, "no second debt from a finished game")
        self.assertIs(game.last_settlement, settlement)

    def test_the_transcript_says_what_happened(self):
        game = self.bankrupt_ada()
        joined = "\n".join(game.log)
        self.assertIn("Ada cannot cover $200 and is bankrupt.", joined)
        self.assertIn("Ada hands nothing to the bank.", joined)
        self.assertIn("Ada is out of the game.", joined)

    def test_the_settlement_is_kept(self):
        game = self.bankrupt_ada()
        self.assertIsInstance(game.last_settlement, Settlement)
        self.assertIs(game.last_settlement.debtor, game.players[0])
        self.assertEqual(game.last_settlement.amount, 200)


class WinConditionTest(BankruptcyGameTestCase):
    """One player left is the end of the game."""

    def test_the_last_player_standing_wins(self):
        game = make_game(rolls=[INCOME_TAX])
        game.players[0].cash = 0
        take_turn(game)
        self.assertIs(game.state, State.GAME_OVER)
        self.assertIs(game.winner, game.players[1])

    def test_the_win_is_announced_with_the_net_worth(self):
        game = make_game(rolls=[INCOME_TAX])
        game.players[0].cash = 0
        take_turn(game)
        self.assertIn("Bob wins with $1,500.", game.log)

    def test_nothing_is_available_once_it_is_over(self):
        game = make_game(rolls=[INCOME_TAX])
        game.players[0].cash = 0
        take_turn(game)
        self.assertEqual(game.available_actions(), frozenset())

    def test_the_winner_keeps_what_they_were_owed(self):
        game = make_game(rolls=[BALTIC])
        ada, bob = game.players
        ada.cash = 300
        self.give(game, bob, BALTIC_INDEX)
        self.give(game, ada, BOARDWALK)
        bob.cash = 0
        take_turn(game)  # Ada pays $4 and survives; nobody is out yet
        self.assertIs(game.state, State.PLAYER_ACTIONS)
        self.assertIsNone(game.winner)

    def test_three_players_keep_going_after_one_goes_under(self):
        game = self.three_handed(rolls=[INCOME_TAX])
        game.players[0].cash = 0
        take_turn(game)
        self.assertIsNot(game.state, State.GAME_OVER)
        self.assertIsNone(game.winner)
        self.assertEqual(len(game.active_players), 2)

    def test_a_lone_player_can_end_the_game_with_no_winner(self):
        game = make_game(rolls=[INCOME_TAX], names=("Ada",))
        game.players[0].cash = 0
        take_turn(game)
        self.assertIs(game.state, State.GAME_OVER)
        self.assertIsNone(game.winner)
        self.assertIn("Everybody is bankrupt; the bank wins.", game.log)

    def test_the_second_bankruptcy_ends_it(self):
        game = self.three_handed(rolls=[INCOME_TAX])
        game.players[0].cash = 0
        take_turn(game)  # Ada is out; Bob is up
        game.players[1].cash = 0
        game.rng.faces.extend(INCOME_TAX)
        take_turn(game)
        self.assertIs(game.state, State.GAME_OVER)
        self.assertIs(game.winner, game.players[2])


class ShortfallHookTest(BankruptcyGameTestCase):
    """A registered hook still takes the answer over, as Phase 7 promised."""

    def test_the_hook_holds_the_debt_open(self):
        game = make_game(rolls=[INCOME_TAX])
        game.players[0].cash = 0
        game.on_shortfall = lambda g, debt: None
        take_turn(game)
        self.assertIsInstance(game.debt, Debt)
        self.assertFalse(game.players[0].is_bankrupt)
        self.assertIsNone(game.last_settlement)

    def test_the_hook_may_settle_it_itself(self):
        game = make_game(rolls=[INCOME_TAX])
        game.players[0].cash = 0
        game.on_shortfall = lambda g, debt: g.settle_debt()
        take_turn(game)
        self.assertTrue(game.players[0].is_bankrupt)
        self.assertIsNone(game.debt)

    def test_settling_nothing_is_a_mistake(self):
        game = make_game()
        with self.assertRaises(RuntimeError):
            game.settle_debt()

    def test_settle_debt_says_whether_it_was_paid(self):
        game = make_game(rolls=[INCOME_TAX])
        ada = game.players[0]
        ada.cash = 0
        self.give(game, ada, BOARDWALK)
        game.on_shortfall = lambda g, debt: None
        take_turn(game)
        self.assertTrue(game.settle_debt())
        self.assertFalse(ada.is_bankrupt)

    def test_settle_debt_says_when_it_was_not(self):
        game = make_game(rolls=[INCOME_TAX])
        game.players[0].cash = 0
        game.on_shortfall = lambda g, debt: None
        take_turn(game)
        self.assertFalse(game.settle_debt())
        self.assertTrue(game.players[0].is_bankrupt)


class JailCardTest(BankruptcyGameTestCase):
    """The card the game -- not the player -- keeps track of."""

    def jailed_card_game(self, names=("Ada", "Bob", "Cleo")):
        """Ada holds a Get Out of Jail Free card from a one-card deck."""
        deck = one_card_deck(
            {"text": "Get Out of Jail Free.", "action": "get_out_of_jail"}
        )
        game = make_game(rolls=[(3, 4)], cash=1500, names=names, chance=deck)
        take_turn(game)  # 0 -> 7, Chance
        answer(game, OK_KEY)
        game.end_turn()
        return game, deck

    def test_the_creditor_takes_the_card(self):
        game, deck = self.jailed_card_game()
        ada, bob = game.players[0], game.players[1]
        self.assertEqual(ada.goojf_cards, 1)
        game.seat = 0
        game._begin_turn()
        ada.cash = 0
        self.give(game, bob, PARK_PLACE, BOARDWALK)
        self.send_to(game, BOARDWALK)
        game.rng.faces.extend(THREE)
        take_turn(game)
        self.assertTrue(ada.is_bankrupt)
        self.assertEqual(ada.goojf_cards, 0)
        self.assertEqual(bob.goojf_cards, 1)

    def test_the_creditors_card_still_goes_home_when_it_is_played(self):
        game, deck = self.jailed_card_game()
        ada, bob = game.players[0], game.players[1]
        game.seat = 0
        game._begin_turn()
        ada.cash = 0
        self.give(game, bob, PARK_PLACE, BOARDWALK)
        self.send_to(game, BOARDWALK)
        game.rng.faces.extend(THREE)
        take_turn(game)
        self.assertEqual(len(deck), 0, "the card is still out of the pile")
        self.assertTrue(game.return_goojf(bob), "and Bob can really play it")
        self.assertEqual(len(deck), 1)

    def test_the_bank_puts_the_card_back_under_its_deck(self):
        game, deck = self.jailed_card_game()
        ada = game.players[0]
        game.seat = 0
        game._begin_turn()
        ada.cash = 0
        ada.position = 0
        game.rng.faces.extend(INCOME_TAX)
        take_turn(game)
        self.assertTrue(ada.is_bankrupt)
        self.assertEqual(ada.goojf_cards, 0)
        self.assertEqual(len(deck), 1, "back at the bottom of the pile")
        self.assertEqual(deck.held, ())


class CardDebtTest(BankruptcyGameTestCase):
    """The two cards that move money between players."""

    def card_game(self, card: dict, *, rolls=((3, 4),), names=("Ada", "Bob", "Cleo")):
        return make_game(
            rolls=list(rolls),
            names=names,
            chance=one_card_deck(card),
        )

    def test_paying_every_player_stops_at_the_bankruptcy(self):
        game = self.card_game({"text": "Pay each player $50.", "action": "pay_to_players", "amount": 50})
        ada, bob, cleo = game.players
        ada.cash = 10
        take_turn(game)  # 0 -> 7, Chance
        answer(game, OK_KEY)
        self.assertTrue(ada.is_bankrupt)
        self.assertEqual(bob.cash, 1500 + 10, "Bob was owed first and took it all")
        self.assertEqual(cleo.cash, 1500, "there was nothing left for Cleo")

    def test_collecting_from_every_player_can_ruin_one_of_them(self):
        game = self.card_game(
            {"text": "Collect $50 from every player.", "action": "collect_from_players", "amount": 50}
        )
        ada, bob, cleo = game.players
        bob.cash = 10
        take_turn(game)
        answer(game, OK_KEY)
        self.assertTrue(bob.is_bankrupt)
        self.assertFalse(ada.is_bankrupt)
        self.assertEqual(cleo.cash, 1500 - 50)
        self.assertEqual(ada.cash, 1500 + 10 + 50)

    def test_the_payer_keeps_their_turn_when_somebody_else_goes_under(self):
        game = self.card_game(
            {"text": "Collect $50 from every player.", "action": "collect_from_players", "amount": 50}
        )
        game.players[1].cash = 0
        take_turn(game)
        answer(game, OK_KEY)
        self.assertIs(game.current, game.players[0])
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    def test_a_repair_bill_can_ruin_a_landlord(self):
        game = self.card_game(
            {
                "text": "Repairs: $25 per house, $100 per hotel.",
                "action": "pay_per_building",
                "per_house": 25,
                "per_hotel": 100,
            }
        )
        ada = game.players[0]
        ada.cash = 0
        browns = self.give(game, ada, MEDITERRANEAN, BALTIC_INDEX)
        for lot in browns:
            lot.houses = 4
            game.bank.houses -= 4
        take_turn(game)
        answer(game, OK_KEY)
        # $200 owed, $200 of houses to sell: exactly enough, and no bankruptcy.
        self.assertFalse(ada.is_bankrupt)
        self.assertEqual(ada.cash, 0)
        self.assertEqual(game.bank.houses, HOUSE_SUPPLY)


class BuildingSupplyTest(BankruptcyGameTestCase):
    """Every piece that comes off the board goes back in the box."""

    def test_a_hotel_comes_back_whole(self):
        game = self.three_handed(rolls=[THREE])
        ada, bob = game.players[0], game.players[1]
        ada.cash = 0
        lot = self.give(game, ada, MEDITERRANEAN)[0]
        lot.has_hotel = True
        boardwalk = self.give(game, bob, PARK_PLACE, BOARDWALK)[1]
        boardwalk.has_hotel = True  # $2,000 rent, far beyond any forced sale
        game.bank.hotels -= 2
        game.bank.houses = 0  # and no houses to stand Ada's hotel back up with
        self.send_to(game, BOARDWALK)
        take_turn(game)
        self.assertTrue(ada.is_bankrupt)
        self.assertEqual(
            game.bank.hotels, HOTEL_SUPPLY - 1, "Bob's hotel is still standing"
        )
        self.assertEqual(game.bank.houses, 0, "a hotel takes no houses with it")
        self.assertEqual(game.deed(MEDITERRANEAN).building_level, 0)
        self.assertIs(game.deed(MEDITERRANEAN).owner, bob)


class SoakTest(unittest.TestCase):
    """Whole games played out by bots that buy, bid and build.

    The building is what makes these worth running: rents nobody can pay are
    what bankrupt a table, and a forced sale that has houses to take down is
    the interesting one. The point is not any one number but that the
    invariants hold at every step of a game that ends the way a game ends --
    nobody overdraws, a bankrupt player holds nothing at all, every deed is
    the bank's or in exactly one live hand, and every house and hotel is
    either standing on the board or back in the box.
    """

    TURNS = 400

    def check_invariants(self, game: Game) -> None:
        for player in game.players:
            self.assertGreaterEqual(player.cash, 0, f"{player.name} overdrew")
            if player.is_bankrupt:
                self.assertEqual(player.cash, 0, f"{player.name} kept cash")
                self.assertEqual(
                    player.properties, [], f"{player.name} kept deeds"
                )
                self.assertEqual(
                    player.goojf_cards, 0, f"{player.name} kept a jail card"
                )
        for deed in game.properties:
            holders = [p for p in game.players if deed in p.properties]
            if deed.owner is None:
                self.assertEqual(holders, [], f"{deed.name} is held by a ghost")
                self.assertFalse(
                    deed.mortgaged, f"{deed.name} is on the shelf, mortgaged"
                )
                self.assertEqual(deed.building_level, 0)
            else:
                self.assertEqual([deed.owner], holders, f"{deed.name} misfiled")
                self.assertFalse(
                    deed.owner.is_bankrupt, f"{deed.name} is held by a dead hand"
                )
        houses = sum(d.house_count for d in game.properties)
        hotels = sum(d.hotel_count for d in game.properties)
        self.assertEqual(game.bank.houses + houses, HOUSE_SUPPLY)
        self.assertEqual(game.bank.hotels + hotels, HOTEL_SUPPLY)

    def play(self, seed: int, cash: int, names=("Ada", "Bob", "Cleo")) -> Game:
        rng = random.Random(seed)
        game = make_game(cash=cash, names=names)
        # Every debt the game settles for itself, counted as it goes: True
        # for one the forced sale covered, False for one that ended a game.
        self.settled: list[bool] = []
        settle_debt = game.settle_debt

        def counting_settle() -> bool:
            paid = settle_debt()
            self.settled.append(paid)
            self.assertIsNone(game.debt, "a settled debt is not left standing")
            return paid

        game.settle_debt = counting_settle

        steps = 0
        turns = 0
        while turns < self.TURNS and game.state is not State.GAME_OVER:
            steps += 1
            self.assertLess(steps, 200 * self.TURNS, "the turn loop is spinning")
            game.update(0)
            self.check_invariants(game)
            if game.state is State.GAME_OVER:
                break  # the landing that just resolved ended the game

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
            if Action.BUILD in actions and rng.random() < 0.8:
                self.build_something(game, rng)
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
        """Put a few buildings up, wherever the draft says one may go."""
        plan = game.open_build()
        for _ in range(rng.randint(1, 6)):
            lots = [lot for lot in plan.all_lots if plan.can_add(lot)]
            if not lots:
                break
            plan.add(rng.choice(lots))
        game.close_build(commit=plan.changed)

    def test_a_poor_table_plays_itself_out(self):
        game = self.play(seed=3, cash=400)
        self.assertTrue(
            any(p.is_bankrupt for p in game.players),
            "nobody went bankrupt on a $400 stake",
        )
        self.assertIn(True, self.settled, "no debt was ever met by a forced sale")
        self.assertIn(False, self.settled, "no debt ever ended a player's game")

    def test_a_game_that_ends_has_exactly_one_winner(self):
        game = self.play(seed=3, cash=900)
        self.assertIs(game.state, State.GAME_OVER)
        self.assertEqual(len(game.active_players), 1)
        self.assertIs(game.winner, game.active_players[0])
        self.assertIn("wins with", game.log[-1])
        self.assertEqual(
            self.settled.count(False),
            sum(p.is_bankrupt for p in game.players),
            "one bankruptcy per debt that could not be met",
        )

    def test_a_rich_table_survives_the_same_rules(self):
        game = self.play(seed=0, cash=1500)
        self.assertEqual(len(game.active_players), 3)
        self.assertIsNone(game.winner, "a game still in progress has no winner")

    def test_six_players_settle_down_to_one(self):
        game = self.play(
            seed=0,
            cash=400,
            names=("Ada", "Bob", "Cleo", "Dai", "Eve", "Fay"),
        )
        self.assertIs(game.state, State.GAME_OVER)
        self.assertEqual(len(game.active_players), 1)
        for player in game.players:
            if player.is_bankrupt:
                self.assertEqual(player.net_worth(), 0, f"{player.name} kept value")


if __name__ == "__main__":
    unittest.main()
