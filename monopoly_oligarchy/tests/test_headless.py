"""Tests for the headless simulator.

Three things are pinned down here: that a roster is validated the way the
setup screen validates one, that a game really does play itself to the end
without a window, and that a seed makes a game reproducible move for move --
which is what lets a statistics run be replayed and a surprising game be
re-examined on its own.

Nothing in this file imports pygame, and nothing it imports does either.
"""

from __future__ import annotations

import unittest

from monopoly import headless
from monopoly.game import Action, State


class TestCheckStakes(unittest.TestCase):
    def test_standard_rosters_are_accepted(self) -> None:
        for seats in range(headless.MIN_PLAYERS, headless.MAX_PLAYERS + 1):
            headless.check_stakes([headless.STANDARD_STAKE] * seats)

    def test_uneven_split_of_the_right_pot_is_accepted(self) -> None:
        headless.check_stakes([2500, 1000, 1000, 1000, 1000, 2500])

    def test_too_few_or_too_many_players_are_refused(self) -> None:
        with self.assertRaises(ValueError):
            headless.check_stakes([1500])
        with self.assertRaises(ValueError):
            headless.check_stakes([1500] * 7)

    def test_the_pot_must_be_1500_a_head(self) -> None:
        with self.assertRaises(ValueError) as caught:
            headless.check_stakes([1500, 1000])
        self.assertIn("3,000", str(caught.exception))

    def test_any_total_is_allowed_when_the_check_is_off(self) -> None:
        headless.check_stakes([100, 50], exact_total=False)

    def test_a_seat_must_start_with_something(self) -> None:
        with self.assertRaises(ValueError):
            headless.check_stakes([3000, 0])
        with self.assertRaises(ValueError):
            headless.check_stakes([4000, -1000], exact_total=False)


class TestBuildPlayers(unittest.TestCase):
    def test_every_seat_is_a_bot_with_its_own_stake_and_colour(self) -> None:
        players = headless.build_players([2000, 1000, 3000])
        self.assertEqual([p.cash for p in players], [2000, 1000, 3000])
        self.assertEqual([p.name for p in players], ["P1", "P2", "P3"])
        self.assertTrue(all(p.is_bot for p in players))
        self.assertEqual(len({p.token_color for p in players}), 3)

    def test_names_may_be_given(self) -> None:
        players = headless.build_players([1500, 1500], names=["Ada", "Grace"])
        self.assertEqual([p.name for p in players], ["Ada", "Grace"])

    def test_a_name_per_seat_or_none_at_all(self) -> None:
        with self.assertRaises(ValueError):
            headless.build_players([1500, 1500], names=["Ada"])


class TestTrackedGame(unittest.TestCase):
    def test_a_fresh_game_has_played_nothing(self) -> None:
        game = headless.new_game([1500, 1500], seed=1)
        self.assertEqual((game.turns, game.rounds), (0, 0))
        game.start()
        self.assertEqual((game.turns, game.rounds), (1, 1))

    def test_a_turn_is_counted_per_seat_and_a_round_per_circuit(self) -> None:
        game = headless.new_game([1500, 1500, 1500], seed=2)
        game.start()
        for _ in range(4):
            game._advance_turn()
        self.assertEqual(game.turns, 5)
        self.assertEqual(game.rounds, 2)  # seats 1,2,3 | 1,2

    def test_a_doubles_re_roll_is_not_a_new_turn(self) -> None:
        game = headless.new_game([1500, 1500], seed=3)
        game.start()
        game.state = State.PLAYER_ACTIONS
        game._extra_turn = True
        game.end_turn()
        self.assertEqual(game.seat, 0)
        self.assertEqual(game.turns, 1)

    def test_the_last_turn_of_a_finished_game_is_not_double_counted(self) -> None:
        game = headless.new_game([1500, 1500], seed=4)
        game.start()
        game.players[1].is_bankrupt = True
        game._advance_turn()
        self.assertIs(game.state, State.GAME_OVER)
        self.assertEqual(game.turns, 1)


class TestBotStep(unittest.TestCase):
    def test_it_rolls_when_that_is_all_there_is_to_do(self) -> None:
        game = headless.new_game([1500, 1500], seed=5)
        game.start()
        self.assertIn(Action.ROLL, game.available_actions())
        self.assertTrue(headless.bot_step(game))
        self.assertIs(game.state, State.ROLLING)

    def test_it_leaves_a_human_alone(self) -> None:
        game = headless.new_game([1500, 1500], seed=6)
        game.players[0].is_bot = False
        game.start()
        self.assertFalse(headless.bot_step(game))
        self.assertIs(game.state, State.PLAYER_TURN_START)

    def test_it_does_nothing_while_the_token_is_moving(self) -> None:
        game = headless.new_game([1500, 1500], seed=7)
        game.start()
        game.state = State.MOVING
        self.assertFalse(headless.bot_step(game))


class TestPlay(unittest.TestCase):
    def test_a_game_plays_itself_to_a_winner(self) -> None:
        result = headless.play([1500, 1500], seed=1)
        self.assertEqual(result.status, headless.WIN)
        self.assertIsNotNone(result.winner)
        self.assertGreater(result.turns, 0)
        self.assertGreaterEqual(result.turns, result.rounds)
        # The loser is bankrupt and the winner is not.
        self.assertTrue(result.bankrupt[1 - result.winner])
        self.assertFalse(result.bankrupt[result.winner])
        self.assertEqual(result.leader, result.winner)

    def test_the_same_seed_replays_the_same_game(self) -> None:
        first = headless.play([2000, 1000], seed=12)
        again = headless.play([2000, 1000], seed=12)
        self.assertEqual(first, again)

    def test_different_seeds_give_different_games(self) -> None:
        turns = {headless.play([1500, 1500], seed=s).turns for s in range(6)}
        self.assertGreater(len(turns), 1)

    def test_the_turn_cap_stops_a_game_that_will_not_end(self) -> None:
        result = headless.play([1500, 1500], seed=13, max_turns=5)
        self.assertEqual(result.status, headless.TIMEOUT)
        self.assertIsNone(result.winner)
        self.assertIsNone(result.winner_name)
        self.assertLessEqual(result.turns, 6)
        # Nobody won, but somebody was ahead.
        self.assertIn(result.leader, (0, 1))

    def test_the_result_carries_the_roster_it_was_played_with(self) -> None:
        result = headless.play([2500, 500], seed=14, names=["Ada", "Grace"])
        self.assertEqual(result.cash, (2500, 500))
        self.assertEqual(result.names, ("Ada", "Grace"))
        self.assertEqual(result.seed, 14)
        self.assertEqual(len(result.net_worths), 2)

    def test_it_refuses_a_roster_the_setup_screen_would_refuse(self) -> None:
        with self.assertRaises(ValueError):
            headless.play([1500, 1000], seed=15)
        with self.assertRaises(ValueError):
            headless.play([1500, 1500], seed=15, max_turns=0)

    def test_six_seats_play(self) -> None:
        result = headless.play([1500] * 6, seed=16, max_turns=400)
        self.assertIn(result.status, (headless.WIN, headless.TIMEOUT))
        self.assertEqual(len(result.net_worths), 6)


class TestBigStakesWin(unittest.TestCase):
    """The simulator's reason for existing: money should show up as wins."""

    def test_a_far_bigger_stake_wins_more_often(self) -> None:
        rich = poor = 0
        for seed in range(40):
            result = headless.play([2800, 200], seed=seed, max_turns=600)
            if result.winner == 0:
                rich += 1
            elif result.winner == 1:
                poor += 1
        self.assertGreater(rich, poor)


if __name__ == "__main__":
    unittest.main()
