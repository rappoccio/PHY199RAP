"""Phase 7 tests: the glue in ``main.py``.

``main`` owns the window and nothing else, so there are only two things to
check. First :func:`~monopoly.main.hud_state`, which is the whole of the join
between a game that knows no pixels and a panel that knows no rules. Second
that :func:`~monopoly.main.run_game` really does draw a frame -- the loop is
where the board, the HUD, the popup and the four other modal surfaces meet
-- the build screen (Phase 9), an auction (10), a trade (11) and the mortgage
screen (12) -- and a wiring mistake there would not show up in any of the
module tests.

The frame tests open a real (dummy-driver) display, draw exactly one frame and
close it again.
"""

from __future__ import annotations

import contextlib
import io
import random
import unittest

import pygame

from unittest import mock

from monopoly import main as main_module
from monopoly.cards import Card, Deck
from monopoly.dice import Dice
from monopoly.game import JAIL_FINE, Action, Game, State
from monopoly.game_manager import Stage
from monopoly.main import KEY_ACTIONS, describe, hud_state, play, run_game, win_state
from monopoly.player import Player
from monopoly.ui.auction_screen import SCREEN_CENTER as AUCTION_CENTER
from monopoly.ui.auction_screen import AuctionScreen
from monopoly.ui.build_screen import SCREEN_CENTER as BUILD_CENTER
from monopoly.ui.build_screen import BuildScreen
from monopoly.ui.hud import Hud
from monopoly.ui.mortgage_screen import SCREEN_CENTER as MORTGAGE_CENTER
from monopoly.ui.mortgage_screen import MortgageScreen
from monopoly.ui.popup import POPUP_CENTER, Popup
from monopoly.ui.renderer import HUD_RECT
from monopoly.ui.theme import PANEL, SCREEN_SIZE, clear_font_cache
from monopoly.ui.trade_screen import SCREEN_CENTER as TRADE_CENTER
from monopoly.ui.trade_screen import TradeScreen
from monopoly.ui.win_screen import PLAY_AGAIN, QUIT, WinScreen, WinState


def make_game(**kwargs) -> Game:
    rng = random.Random(4)
    players = [Player("Ada", 1500, "red"), Player("Bob", 1200, "blue")]
    return Game(players, dice=Dice(rng, roll_ms=0), rng=rng, step_ms=0, **kwargs)


class FrameLimit(Exception):
    """Raised by :class:`CountingClock` when a loop will not end."""


class CountingClock:
    """A clock that fails the test rather than letting the loop spin forever.

    The win screen's two buttons are the only things that end ``run_game``
    without a QUIT, so the tests for them post no QUIT at all -- and a broken
    wiring would otherwise hang the suite instead of failing it.
    """

    def __init__(self, limit: int = 4) -> None:
        self.limit = limit
        self.frames = 0

    def tick(self, fps: int = 0) -> int:
        self.frames += 1
        if self.frames > self.limit:
            raise FrameLimit(f"{self.frames} frames drawn and the loop is still up")
        return 0


class DescribeTest(unittest.TestCase):
    def test_one_line_per_player(self):
        players = [Player("Ada", 1500, "red"), Player("Bob", 250, "blue")]
        lines = describe(players).splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("Ada", lines[0])
        self.assertIn("$1,500", lines[0])
        self.assertIn("blue", lines[1])


class HudStateTest(unittest.TestCase):
    def setUp(self):
        self.game = make_game()
        self.game.start()

    def test_it_carries_the_roster_and_the_board(self):
        state = hud_state(self.game)
        self.assertEqual(list(state.players), self.game.players)
        self.assertIs(state.current, self.game.current)
        self.assertEqual(len(state.properties), 28)
        self.assertIs(state.dice, self.game.dice)

    def test_it_carries_the_message(self):
        self.assertEqual(hud_state(self.game).message, self.game.message)

    def test_available_actions_come_straight_from_the_rules(self):
        self.assertEqual(hud_state(self.game).available, frozenset({Action.ROLL}))
        self.game.perform(Action.ROLL, 0)
        self.game.update(0)
        self.assertEqual(
            hud_state(self.game).available, self.game.available_actions()
        )

    def test_it_follows_the_turn_to_the_next_player(self):
        self.game.seat = 1
        self.assertIs(hud_state(self.game).current, self.game.players[1])


class KeyActionTest(unittest.TestCase):
    def test_space_rolls_and_enter_ends_the_turn(self):
        self.assertIs(KEY_ACTIONS[pygame.K_SPACE], Action.ROLL)
        self.assertIs(KEY_ACTIONS[pygame.K_RETURN], Action.END_TURN)
        self.assertIs(KEY_ACTIONS[pygame.K_KP_ENTER], Action.END_TURN)

    def test_nothing_else_is_bound(self):
        self.assertNotIn(pygame.K_ESCAPE, KEY_ACTIONS, "Esc quits, it is not an action")


class FrameTest(unittest.TestCase):
    """One real frame, so the board + HUD + popup wiring is exercised."""

    def setUp(self):
        pygame.init()
        clear_font_cache()
        self.surface = pygame.display.set_mode(SCREEN_SIZE)
        pygame.event.clear()

    def tearDown(self):
        pygame.event.clear()
        pygame.display.quit()

    def run_one_frame(self, game: Game, **kwargs) -> Game:
        """Draw a single frame: a QUIT still leaves the loop's draw to run."""
        pygame.event.post(pygame.event.Event(pygame.QUIT))
        return run_game(self.surface, game.players, game=game, **kwargs)

    def test_a_frame_draws_and_the_loop_exits(self):
        game = self.run_one_frame(make_game())
        self.assertIs(game.state, State.PLAYER_TURN_START)
        self.assertNotEqual(
            pygame.transform.average_color(self.surface)[:3], (0, 0, 0)
        )

    def test_run_game_starts_a_game_that_is_still_in_setup(self):
        game = make_game()
        self.assertIs(game.state, State.SETUP)
        self.run_one_frame(game)
        self.assertIsNot(game.state, State.SETUP)

    def test_a_started_game_is_not_restarted(self):
        game = make_game()
        game.start()
        game.seat = 1
        self.run_one_frame(game)
        self.assertEqual(game.seat, 1)

    def test_a_click_on_roll_dice_reaches_the_rules(self):
        game = make_game()
        game.start()
        pos = Hud(HUD_RECT).buttons[Action.ROLL].rect.center
        pygame.event.post(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1})
        )
        self.run_one_frame(game)
        self.assertIs(game.state, State.ROLLING)

    def test_the_space_bar_rolls_too(self):
        game = make_game()
        game.start()
        pygame.event.post(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE, "mod": 0})
        )
        self.run_one_frame(game)
        self.assertIs(game.state, State.ROLLING)

    def test_a_click_on_the_board_does_nothing(self):
        game = make_game()
        game.start()
        pygame.event.post(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": (400, 400), "button": 1})
        )
        self.run_one_frame(game)
        self.assertIs(game.state, State.PLAYER_TURN_START)

    def test_a_click_while_a_popup_is_open_answers_it(self):
        game = make_game()
        game.start()
        game._prompt_buy(game.deed(3))
        popup = Popup()
        popup.prompt = game.prompt
        pygame.event.post(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": popup.buttons[0].rect.center, "button": 1},
            )
        )
        self.run_one_frame(game)
        self.assertIsNone(game.prompt)
        self.assertIs(game.deed(3).owner, game.players[0])

    def test_a_frame_with_a_popup_open(self):
        game = make_game()
        game.start()
        game._prompt_buy(game.deed(3))  # as landing on Baltic Avenue would
        self.run_one_frame(game)
        self.assertIsNotNone(game.prompt, "the popup should still be waiting")
        self.assertEqual(self.surface.get_at(POPUP_CENTER)[:3], PANEL)

    def jailed(self) -> Game:
        """A started game whose current player is locked up, prompt open."""
        game = make_game()
        game.start()
        game._go_to_jail(game.current)
        game._begin_turn()
        return game

    def click_prompt(self, game: Game, index: int) -> None:
        """Post a click on the ``index``-th button of the open prompt."""
        popup = Popup()
        popup.prompt = game.prompt
        pygame.event.post(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": popup.buttons[index].rect.center, "button": 1},
            )
        )

    def test_a_jail_prompt_draws_too(self):
        game = self.jailed()
        self.run_one_frame(game)
        self.assertEqual(game.prompt.title, "In Jail")
        self.assertEqual(self.surface.get_at(POPUP_CENTER)[:3], PANEL)

    def test_a_click_on_roll_for_doubles_reaches_the_rules(self):
        game = self.jailed()
        self.click_prompt(game, 2)  # the wrapped, full-width bottom button
        self.run_one_frame(game)
        self.assertIsNone(game.prompt)
        self.assertIs(game.state, State.ROLLING)
        self.assertTrue(game.current.in_jail, "still inside until the dice land")

    def test_a_click_on_pay_the_fine_reaches_the_rules(self):
        game = self.jailed()
        cash = game.current.cash
        self.click_prompt(game, 0)
        self.run_one_frame(game)
        self.assertEqual(game.current.cash, cash - JAIL_FINE)
        self.assertFalse(game.current.in_jail)
        self.assertIs(game.state, State.ROLLING)

    def test_the_space_bar_does_not_skip_the_jail_prompt(self):
        game = self.jailed()
        pygame.event.post(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE, "mod": 0})
        )
        self.run_one_frame(game)
        self.assertIsNotNone(game.prompt, "the prompt is modal to the keyboard too")
        self.assertIs(game.state, State.PLAYER_TURN_START)

    # --- Phase 9: the build screen is the loop's second modal ---------------
    def building(self) -> Game:
        """A started game, mid-turn, with the current player holding brown."""
        game = make_game()
        game.start()
        game.perform(Action.ROLL, 0)
        game.update(0)
        game.prompt = None  # whatever it landed on, the turn is open now
        game.state = State.PLAYER_ACTIONS
        for index in (1, 3):
            game.current.add_property(game.deed(index))
        return game

    def click_build_step(self, game: Game, row: int, add: bool = True) -> None:
        """Post a click on the ``+`` (or ``-``) of the ``row``-th lot."""
        screen = BuildScreen()
        screen.plan = game.build
        buttons = screen.add_buttons if add else screen.remove_buttons
        pygame.event.post(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": buttons[row].rect.center, "button": 1},
            )
        )

    def test_a_click_on_build_opens_the_screen(self):
        game = self.building()
        pos = Hud(HUD_RECT).buttons[Action.BUILD].rect.center
        pygame.event.post(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1})
        )
        self.run_one_frame(game)
        self.assertIsNotNone(game.build)

    def test_a_frame_with_the_build_screen_open(self):
        game = self.building()
        game.open_build()
        self.run_one_frame(game)
        self.assertIsNotNone(game.build, "the screen should still be waiting")
        self.assertEqual(self.surface.get_at(BUILD_CENTER)[:3], PANEL)

    def test_a_click_on_plus_reaches_the_draft(self):
        game = self.building()
        plan = game.open_build()
        self.click_build_step(game, 1)  # row 0 is the group header
        self.run_one_frame(game)
        self.assertIs(game.build, plan, "a step click leaves the screen open")
        self.assertEqual(plan.level(game.deed(1)), 1)
        self.assertEqual(game.deed(1).houses, 0, "nothing is built until Confirm")

    def test_a_click_on_confirm_builds_for_real(self):
        game = self.building()
        cash = game.current.cash
        plan = game.open_build()
        plan.add(game.deed(1))
        screen = BuildScreen()
        screen.plan = plan
        pygame.event.post(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": screen.confirm.rect.center, "button": 1},
            )
        )
        self.run_one_frame(game)
        self.assertIsNone(game.build)
        self.assertEqual(game.deed(1).houses, 1)
        self.assertEqual(game.current.cash, cash - 50)

    def test_a_click_on_cancel_drops_the_draft(self):
        game = self.building()
        cash = game.current.cash
        plan = game.open_build()
        plan.add(game.deed(1))
        screen = BuildScreen()
        screen.plan = plan
        pygame.event.post(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": screen.cancel.rect.center, "button": 1},
            )
        )
        self.run_one_frame(game)
        self.assertIsNone(game.build)
        self.assertEqual(game.deed(1).houses, 0)
        self.assertEqual(game.current.cash, cash)

    def test_the_enter_key_does_not_end_a_turn_under_the_build_screen(self):
        game = self.building()
        game.open_build()
        pygame.event.post(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN, "mod": 0})
        )
        self.run_one_frame(game)
        self.assertIsNotNone(game.build, "the screen is modal to the keyboard too")
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    # --- Phase 10: the auction is the loop's third modal --------------------
    def auctioning(self) -> Game:
        """A started game, mid-turn, with Baltic Avenue under the hammer."""
        game = make_game()
        game.start()
        game.state = State.LAND_ACTION
        game.open_auction(game.deed(3))
        return game

    def post_click(self, pos) -> None:
        pygame.event.post(
            pygame.event.Event(pygame.MOUSEBUTTONDOWN, {"pos": pos, "button": 1})
        )

    def auction_screen(self, game: Game) -> AuctionScreen:
        """A screen laid out over the same sale, to find its buttons by."""
        screen = AuctionScreen()
        screen.auction = game.auction
        return screen

    def test_a_frame_with_an_auction_open(self):
        game = self.auctioning()
        self.run_one_frame(game)
        self.assertIsNotNone(game.auction, "the sale should still be waiting")
        self.assertEqual(self.surface.get_at(AUCTION_CENTER)[:3], PANEL)

    def test_a_click_on_bid_reaches_the_rules(self):
        game = self.auctioning()
        self.post_click(self.auction_screen(game).bid.rect.center)
        self.run_one_frame(game)
        self.assertIsNotNone(game.auction, "one bid does not end a two-hand sale")
        self.assertEqual(game.auction.high_bid, 1)
        self.assertIs(game.auction.high_bidder, game.players[0])
        self.assertIs(game.auction.bidder, game.players[1])

    def test_a_click_on_pass_reaches_the_rules(self):
        game = self.auctioning()
        self.post_click(self.auction_screen(game).pass_button.rect.center)
        self.run_one_frame(game)
        self.assertIsNotNone(game.auction)
        self.assertTrue(game.auction.has_passed(game.players[0]))

    def test_passing_all_the_way_round_closes_the_sale(self):
        game = self.auctioning()
        pos = self.auction_screen(game).pass_button.rect.center
        self.post_click(pos)
        self.post_click(pos)
        self.run_one_frame(game)
        self.assertIsNone(game.auction)
        self.assertIsNone(game.deed(3).owner)
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    def test_a_bid_nobody_answers_hands_over_the_deed(self):
        game = self.auctioning()
        screen = self.auction_screen(game)
        self.post_click(screen.bid.rect.center)
        self.post_click(screen.pass_button.rect.center)
        self.run_one_frame(game)
        self.assertIsNone(game.auction)
        self.assertIs(game.deed(3).owner, game.players[0])
        self.assertEqual(game.players[0].cash, 1500 - 1)

    def test_the_quick_raise_buttons_reach_the_field(self):
        game = self.auctioning()
        screen = self.auction_screen(game)
        self.post_click(screen.raises[-1].rect.center)
        self.post_click(screen.bid.rect.center)
        self.run_one_frame(game)
        self.assertEqual(game.auction.high_bid, 51, "$1 asking + $50 raise")

    def test_the_enter_key_bids_rather_than_ending_the_turn(self):
        game = self.auctioning()
        pygame.event.post(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN, "mod": 0})
        )
        self.run_one_frame(game)
        self.assertIsNotNone(game.auction, "the screen is modal to the keyboard too")
        self.assertEqual(game.auction.high_bid, 1)
        self.assertIs(game.state, State.LAND_ACTION)

    def test_the_panel_is_dead_while_the_sale_runs(self):
        game = self.auctioning()
        self.post_click(Hud(HUD_RECT).buttons[Action.ROLL].rect.center)
        self.run_one_frame(game)
        self.assertIsNotNone(game.auction)
        self.assertIs(game.state, State.LAND_ACTION)

    def test_declining_a_deed_in_the_loop_opens_the_sale(self):
        game = make_game()
        game.start()
        game._prompt_buy(game.deed(3))
        popup = Popup()
        popup.prompt = game.prompt
        self.post_click(popup.buttons[1].rect.center)  # the Auction button
        self.run_one_frame(game)
        self.assertIsNone(game.prompt)
        self.assertIsNotNone(game.auction)
        self.assertEqual(self.surface.get_at(AUCTION_CENTER)[:3], PANEL)

    # --- Phase 11: the trade is the loop's fourth modal ---------------------
    def trading(self) -> Game:
        """A started game, mid-turn, with a trade open and Ada holding Baltic."""
        game = make_game()
        game.start()
        game.state = State.PLAYER_ACTIONS
        game.current.add_property(game.deed(3))
        game.open_trade()
        return game

    def trade_screen(self, game: Game) -> TradeScreen:
        """A screen laid out over the same deal, to find its widgets by."""
        screen = TradeScreen()
        screen.trade = game.trade
        return screen

    def test_a_frame_with_a_trade_open(self):
        game = self.trading()
        self.run_one_frame(game)
        self.assertIsNotNone(game.trade, "the screen should still be waiting")
        self.assertEqual(self.surface.get_at(TRADE_CENTER)[:3], PANEL)

    def test_a_click_on_trade_opens_the_screen(self):
        game = make_game()
        game.start()
        game.state = State.PLAYER_ACTIONS
        self.post_click(Hud(HUD_RECT).buttons[Action.TRADE].rect.center)
        self.run_one_frame(game)
        self.assertIsNotNone(game.trade)

    def test_a_click_on_a_deed_row_reaches_the_draft(self):
        game = self.trading()
        screen = self.trade_screen(game)
        self.post_click(screen.rows[0][2].center)
        self.run_one_frame(game)
        self.assertIs(game.trade, screen.trade, "a row click leaves it open")
        self.assertTrue(game.trade.is_offered(game.deed(3)))
        self.assertIs(game.deed(3).owner, game.players[0], "nothing moves yet")

    def test_a_click_on_propose_hands_the_offer_over(self):
        game = self.trading()
        game.trade.add_deed(game.deed(3))
        self.post_click(self.trade_screen(game).primary.rect.center)
        self.run_one_frame(game)
        self.assertIsNotNone(game.trade)
        self.assertEqual(game.trade.phase, "review")
        self.assertIs(game.deed(3).owner, game.players[0], "nothing moves yet")

    def test_a_click_on_accept_settles_the_deal(self):
        game = self.trading()
        game.trade.add_deed(game.deed(3))
        game.propose_trade()
        self.post_click(self.trade_screen(game).primary.rect.center)
        self.run_one_frame(game)
        self.assertIsNone(game.trade)
        self.assertIs(game.deed(3).owner, game.players[1])

    def test_a_click_on_reject_drops_it(self):
        game = self.trading()
        game.trade.add_deed(game.deed(3))
        game.propose_trade()
        self.post_click(self.trade_screen(game).secondary.rect.center)
        self.run_one_frame(game)
        self.assertIsNone(game.trade)
        self.assertIs(game.deed(3).owner, game.players[0])

    def test_a_click_on_cancel_drops_the_offer(self):
        game = self.trading()
        game.trade.add_deed(game.deed(3))
        self.post_click(self.trade_screen(game).secondary.rect.center)
        self.run_one_frame(game)
        self.assertIsNone(game.trade)
        self.assertIs(game.deed(3).owner, game.players[0])

    def test_the_panel_is_dead_while_a_trade_is_open(self):
        game = self.trading()
        self.post_click(Hud(HUD_RECT).buttons[Action.END_TURN].rect.center)
        self.run_one_frame(game)
        self.assertIsNotNone(game.trade)
        self.assertIs(game.current, game.players[0])

    def test_the_enter_key_does_not_end_a_turn_under_the_trade_screen(self):
        game = self.trading()
        pygame.event.post(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN, "mod": 0})
        )
        self.run_one_frame(game)
        self.assertIsNotNone(game.trade, "the screen is modal to the keyboard too")
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    # --- Phase 12: the mortgage screen is the loop's fifth modal ------------
    def mortgaging(self) -> Game:
        """A started game, mid-turn, with the mortgage screen open on Baltic."""
        game = make_game()
        game.start()
        game.state = State.PLAYER_ACTIONS
        game.current.add_property(game.deed(3))
        game.open_mortgage()
        return game

    def mortgage_screen(self, game: Game) -> MortgageScreen:
        """A screen laid out over the same draft, to find its widgets by."""
        screen = MortgageScreen()
        screen.ledger = game.mortgage
        return screen

    def test_a_frame_with_the_mortgage_screen_open(self):
        game = self.mortgaging()
        self.run_one_frame(game)
        self.assertIsNotNone(game.mortgage, "the screen should still be waiting")
        self.assertEqual(self.surface.get_at(MORTGAGE_CENTER)[:3], PANEL)

    def test_a_click_on_mortgage_opens_the_screen(self):
        game = make_game()
        game.start()
        game.state = State.PLAYER_ACTIONS
        game.current.add_property(game.deed(3))
        self.post_click(Hud(HUD_RECT).buttons[Action.MORTGAGE].rect.center)
        self.run_one_frame(game)
        self.assertIsNotNone(game.mortgage)

    def test_a_click_on_a_deed_row_reaches_the_mortgage_draft(self):
        game = self.mortgaging()
        screen = self.mortgage_screen(game)
        self.post_click(screen.toggles[0].rect.center)
        self.run_one_frame(game)
        self.assertIs(game.mortgage, screen.ledger, "a row click leaves it open")
        self.assertTrue(game.mortgage.state(game.deed(3)))
        self.assertFalse(game.deed(3).mortgaged, "nothing moves yet")
        self.assertEqual(game.players[0].cash, 1500)

    def test_a_click_on_confirm_flips_the_flag_and_pays_out(self):
        game = self.mortgaging()
        game.mortgage.mortgage(game.deed(3))
        self.post_click(self.mortgage_screen(game).confirm.rect.center)
        self.run_one_frame(game)
        self.assertIsNone(game.mortgage)
        self.assertTrue(game.deed(3).mortgaged)
        self.assertEqual(game.players[0].cash, 1500 + 30)

    def test_a_click_on_cancel_drops_the_mortgage_draft(self):
        game = self.mortgaging()
        game.mortgage.mortgage(game.deed(3))
        self.post_click(self.mortgage_screen(game).cancel.rect.center)
        self.run_one_frame(game)
        self.assertIsNone(game.mortgage)
        self.assertFalse(game.deed(3).mortgaged)
        self.assertEqual(game.players[0].cash, 1500)

    def test_the_panel_is_dead_while_the_screen_is_open(self):
        game = self.mortgaging()
        self.post_click(Hud(HUD_RECT).buttons[Action.END_TURN].rect.center)
        self.run_one_frame(game)
        self.assertIsNotNone(game.mortgage)
        self.assertIs(game.current, game.players[0])

    def test_the_enter_key_does_not_end_a_turn_under_the_screen(self):
        game = self.mortgaging()
        pygame.event.post(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN, "mod": 0})
        )
        self.run_one_frame(game)
        self.assertIsNotNone(game.mortgage, "the screen is modal to the keyboard too")
        self.assertIs(game.state, State.PLAYER_ACTIONS)

    # --- Phase 14: the win screen is the loop's last modal ------------------
    def finished(self) -> Game:
        """A started game the second player has just gone bankrupt out of."""
        game = make_game()
        game.start()
        game.players[1].is_bankrupt = True
        game._advance_turn()  # the turn order runs out and the game is called
        self.assertIs(game.state, State.GAME_OVER)
        return game

    def test_the_overlay_stays_down_while_the_game_is_live(self):
        win = WinScreen()
        self.run_one_frame(make_game(), win=win)
        self.assertFalse(win.visible)
        self.assertIsNone(win.result)
        self.assertIsNone(win.choice)

    def test_a_frame_with_the_game_over_covers_the_board(self):
        win = WinScreen()
        game = self.finished()
        self.run_one_frame(game, win=win)
        self.assertTrue(win.visible)
        self.assertIs(win.winner, game.players[0])
        self.assertEqual(self.surface.get_at(win.card_rect.center)[:3], PANEL)

    def test_the_overlay_comes_up_the_moment_the_last_turn_ends(self):
        win = WinScreen()
        game = make_game()
        game.start()
        game.players[1].is_bankrupt = True
        game.state = State.PLAYER_ACTIONS
        game.rolled = True
        pygame.event.post(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN, "mod": 0})
        )
        self.run_one_frame(game, win=win)
        self.assertIs(game.state, State.GAME_OVER)
        self.assertTrue(win.visible, "the End Turn that ended the game raises it")
        self.assertEqual(self.surface.get_at(win.card_rect.center)[:3], PANEL)

    def test_a_click_on_play_again_ends_the_loop_and_reports_itself(self):
        win = WinScreen()
        game = self.finished()
        self.post_click(win.play_again.rect.center)
        run_game(
            self.surface, game.players, game=game, win=win, clock=CountingClock()
        )
        self.assertEqual(win.choice, PLAY_AGAIN)

    def test_a_click_on_quit_ends_the_loop_too(self):
        win = WinScreen()
        game = self.finished()
        self.post_click(win.quit.rect.center)
        run_game(
            self.surface, game.players, game=game, win=win, clock=CountingClock()
        )
        self.assertEqual(win.choice, QUIT)

    def test_the_panel_is_dead_once_the_game_is_over(self):
        win = WinScreen()
        game = self.finished()
        self.post_click(Hud(HUD_RECT).buttons[Action.ROLL].rect.center)
        self.run_one_frame(game, win=win)
        self.assertIsNone(win.choice, "the overlay swallowed the click")
        self.assertIs(game.state, State.GAME_OVER)

    def test_the_space_bar_rolls_nothing_once_the_game_is_over(self):
        win = WinScreen()
        game = self.finished()
        pygame.event.post(
            pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_SPACE, "mod": 0})
        )
        self.run_one_frame(game, win=win)
        self.assertIs(game.state, State.GAME_OVER)
        self.assertIsNone(game.prompt)

    def test_the_overlay_is_built_once_and_left_alone(self):
        """``sync_modals`` compares states, so hover survives the next frame."""
        win = WinScreen()
        game = self.finished()
        self.run_one_frame(game, win=win)
        first = win.result
        self.run_one_frame(game, win=win)
        self.assertIs(win.result, first)

    def test_a_card_prompt_draws_too(self):
        deck = Deck(
            [Card.from_dict({"text": "Bank pays you $50.", "action": "collect"})],
            shuffle=False,
        )
        game = make_game(chance=deck)
        game.start()
        game._draw_card("chance")
        self.run_one_frame(game)
        self.assertEqual(game.prompt.title, "Chance")
        self.assertEqual(self.surface.get_at(POPUP_CENTER)[:3], PANEL)


class WinStateTest(unittest.TestCase):
    """The join between a finished game and the overlay that ends it."""

    def test_a_live_game_has_no_result(self):
        game = make_game()
        self.assertIsNone(win_state(game))
        game.start()
        self.assertIsNone(win_state(game))

    def test_a_finished_game_carries_the_winner_and_the_roster(self):
        game = make_game()
        game.start()
        game.players[1].is_bankrupt = True
        game._advance_turn()
        state = win_state(game)
        self.assertIsNotNone(state)
        self.assertIs(state.winner, game.players[0])
        self.assertEqual(list(state.players), game.players)

    def test_a_table_with_nobody_left_is_still_a_result(self):
        lone = Player("Ada", 0, "red")
        game = Game([lone], step_ms=0)
        game.start()
        lone.is_bankrupt = True
        game._advance_turn()
        state = win_state(game)
        self.assertIsNotNone(state, "game over with no winner is still game over")
        self.assertIsNone(state.winner)
        self.assertEqual(list(state.players), [lone])

    def test_the_state_is_stable_frame_to_frame(self):
        game = make_game()
        game.start()
        game.players[1].is_bankrupt = True
        game._advance_turn()
        self.assertEqual(win_state(game), win_state(game))


class PlayTest(unittest.TestCase):
    """:func:`~monopoly.main.play`: setup, game, win screen, round again.

    The setup screen and the game loop are both covered elsewhere, so both are
    stubbed out here: a manager that is already finished (so
    :func:`monopoly.game_manager.run` returns its roster without drawing) and a
    ``run_game`` that answers the win screen the way a click would. What is
    left is the only thing ``play`` adds -- how many games get played, and
    whether the manager is reset between them.
    """

    class FakeManager:
        """A setup screen that has already been filled in.

        Each :meth:`reset` serves the next roster; when there are none left it
        reports the operator closing the window, which is what ends ``play``.
        """

        def __init__(self, *rosters: list[Player]) -> None:
            self.rosters = list(rosters)
            self.stage = Stage.DONE
            self.quit_requested = False
            self.resets = 0
            self.players = self.rosters.pop(0) if self.rosters else []

        def reset(self) -> None:
            self.resets += 1
            if self.rosters:
                self.players = self.rosters.pop(0)
            else:
                self.quit_requested = True

    def setUp(self):
        pygame.init()
        clear_font_cache()
        self.surface = pygame.Surface(SCREEN_SIZE)
        self.rosters: list[list[Player]] = []
        self.choices: list = []

    def tearDown(self):
        clear_font_cache()
        pygame.font.quit()

    def fake_run_game(self, surface, players, *, win=None, **kwargs):
        """Stand in for a whole game: the first player wins it."""
        self.rosters.append(list(players))
        win.result = WinState(winner=players[0], players=players)
        win.choice = self.choices.pop(0) if self.choices else QUIT
        return None

    def play(self, manager) -> int:
        with mock.patch.object(main_module, "run_game", self.fake_run_game):
            with contextlib.redirect_stdout(io.StringIO()) as out:
                code = play(self.surface, manager)
        self.output = out.getvalue()
        return code

    def roster(self, name: str) -> list[Player]:
        return [Player(name, 1500, "red"), Player("Bob", 1500, "blue")]

    def test_one_game_and_quit(self):
        manager = self.FakeManager(self.roster("Ada"))
        self.choices = [QUIT]
        self.assertEqual(self.play(manager), 0)
        self.assertEqual(len(self.rosters), 1)
        self.assertEqual(manager.resets, 0, "the first game needs no reset")

    def test_play_again_sets_the_table_up_a_second_time(self):
        manager = self.FakeManager(self.roster("Ada"), self.roster("Cy"))
        self.choices = [PLAY_AGAIN, QUIT]
        self.assertEqual(self.play(manager), 0)
        self.assertEqual([r[0].name for r in self.rosters], ["Ada", "Cy"])
        self.assertEqual(manager.resets, 1, "Play Again clears the setup screen")

    def test_play_again_keeps_going_as_long_as_it_is_pressed(self):
        manager = self.FakeManager(*[self.roster(n) for n in "ABCD"])
        self.choices = [PLAY_AGAIN, PLAY_AGAIN, PLAY_AGAIN, QUIT]
        self.assertEqual(self.play(manager), 0)
        self.assertEqual(len(self.rosters), 4)
        self.assertEqual(manager.resets, 3)

    def test_a_closed_window_ends_it_as_surely_as_quit(self):
        manager = self.FakeManager(self.roster("Ada"))
        self.choices = [None]  # the window was closed mid-game
        self.assertEqual(self.play(manager), 0)
        self.assertEqual(len(self.rosters), 1)

    def test_a_cancelled_setup_screen_plays_nothing(self):
        manager = self.FakeManager()
        manager.quit_requested = True
        self.assertEqual(self.play(manager), 1)
        self.assertEqual(self.rosters, [])
        self.assertIn("cancelled", self.output)

    def test_closing_the_setup_screen_after_play_again_ends_it(self):
        manager = self.FakeManager(self.roster("Ada"))
        self.choices = [PLAY_AGAIN]
        self.assertEqual(self.play(manager), 1, "no second roster: the window shut")
        self.assertEqual(len(self.rosters), 1)
        self.assertEqual(manager.resets, 1)

    def test_every_game_gets_a_win_screen_of_its_own(self):
        """Or the second game would open on the first one's winner."""
        seen = []

        def spy(surface, players, *, win=None, **kwargs):
            seen.append(win)
            return self.fake_run_game(surface, players, win=win, **kwargs)

        manager = self.FakeManager(self.roster("Ada"), self.roster("Cy"))
        self.choices = [PLAY_AGAIN, QUIT]
        with mock.patch.object(main_module, "run_game", spy):
            with contextlib.redirect_stdout(io.StringIO()):
                play(self.surface, manager)
        self.assertEqual(len(seen), 2)
        self.assertIsNot(seen[0], seen[1])

    def test_the_roster_and_the_result_are_printed(self):
        manager = self.FakeManager(self.roster("Ada"))
        self.choices = [QUIT]
        self.play(manager)
        self.assertIn("Starting game with 2 players", self.output)
        self.assertIn("Ada wins with $1,500", self.output)


if __name__ == "__main__":
    unittest.main()
