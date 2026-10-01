"""Tests for the simulation command line.

The engine is tested in ``test_headless.py``; what is checked here is the
layer around it -- batching and seeding, the statistics drawn off a batch, the
CSV and JSON it writes, and the arguments it refuses.

Results are built by hand wherever the statistics are the subject, so that a
table's numbers are pinned to known input rather than to whatever the dice
happened to do.
"""

from __future__ import annotations

import io
import json
import unittest

from monopoly import simulate
from monopoly.headless import STALLED, TIMEOUT, WIN, Result


def result(
    winner=None, *, status=WIN, turns=100, cash=(2000, 1000), nets=(5000, 0), seed=0
) -> Result:
    """One made-up game, so a statistic can be checked against known input."""
    return Result(
        cash=cash,
        names=tuple(f"P{i + 1}" for i in range(len(cash))),
        winner=winner,
        turns=turns,
        rounds=turns // 2,
        status=status,
        net_worths=nets,
        bankrupt=tuple(i != winner for i in range(len(cash))),
        seed=seed,
    )


class TestRunBatch(unittest.TestCase):
    def test_every_game_gets_its_own_seed_in_order(self) -> None:
        results = simulate.run_batch([1500, 1500], 4, seed=100, max_turns=30)
        self.assertEqual([r.seed for r in results], [100, 101, 102, 103])

    def test_a_batch_is_the_same_however_it_is_divided_up(self) -> None:
        serial = simulate.run_batch([2000, 1000], 6, seed=7, max_turns=60, jobs=1)
        parallel = simulate.run_batch([2000, 1000], 6, seed=7, max_turns=60, jobs=3)
        self.assertEqual(serial, parallel)

    def test_an_empty_batch_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            simulate.run_batch([1500, 1500], 0)

    def test_a_small_batch_stays_in_one_process(self) -> None:
        self.assertEqual(simulate._worker_count(0, 5), 1)
        self.assertGreaterEqual(simulate._worker_count(0, 10_000), 1)
        self.assertEqual(simulate._worker_count(8, 3), 3)


class TestSummarise(unittest.TestCase):
    def test_wins_are_counted_per_seat(self) -> None:
        summary = simulate.summarise(
            [result(0), result(0), result(1), result(0, status=TIMEOUT)]
        )
        self.assertEqual([s.wins for s in summary.seats], [2, 1])
        self.assertAlmostEqual(summary.seats[0].win_rate, 0.5)
        self.assertEqual(summary.decided, 3)
        self.assertEqual(summary.timeouts, 1)
        self.assertEqual(summary.undecided, 1)

    def test_a_turn_cap_draw_counts_for_nobody_by_default(self) -> None:
        summary = simulate.summarise([result(None, status=TIMEOUT, nets=(9, 4))])
        self.assertEqual([s.wins for s in summary.seats], [0, 0])
        self.assertEqual(summary.decided, 0)

    def test_a_turn_cap_draw_can_be_credited_to_the_leader(self) -> None:
        summary = simulate.summarise(
            [result(None, status=TIMEOUT, nets=(4, 9))],
            decide_timeouts=simulate.DECIDE_LEADER,
        )
        self.assertEqual([s.wins for s in summary.seats], [0, 1])
        # Still not a decided game: nobody actually won it.
        self.assertEqual(summary.decided, 0)
        self.assertEqual(summary.turns, ())

    def test_a_wedged_game_counts_for_nobody_either_way(self) -> None:
        summary = simulate.summarise(
            [result(None, status=STALLED, nets=(9, 4))],
            decide_timeouts=simulate.DECIDE_LEADER,
        )
        self.assertEqual([s.wins for s in summary.seats], [0, 0])
        self.assertEqual(summary.stalls, 1)

    def test_turns_come_only_from_games_that_were_won(self) -> None:
        summary = simulate.summarise(
            [
                result(0, turns=50),
                result(1, turns=150),
                result(None, status=TIMEOUT, turns=9999),
            ]
        )
        self.assertEqual(summary.turns, (50, 150))
        self.assertEqual(summary.seats[0].mean_turns, 50)
        self.assertIsNone(
            simulate.summarise([result(None, status=TIMEOUT)]).seats[0].mean_turns
        )

    def test_the_win_rate_carries_a_binomial_error(self) -> None:
        summary = simulate.summarise([result(0)] * 75 + [result(1)] * 25)
        self.assertAlmostEqual(summary.seats[0].win_rate, 0.75)
        self.assertAlmostEqual(summary.seats[0].error, 0.0433, places=3)

    def test_nothing_to_summarise_is_refused(self) -> None:
        with self.assertRaises(ValueError):
            simulate.summarise([])


class TestPercentile(unittest.TestCase):
    def test_it_reads_off_a_sorted_sample(self) -> None:
        values = list(range(1, 100))
        self.assertEqual(simulate.percentile(values, 0.0), 1)
        self.assertEqual(simulate.percentile(values, 1.0), 99)
        self.assertEqual(simulate.percentile(values, 0.5), 50)
        self.assertEqual(simulate.percentile(values, 0.9), 89)

    def test_an_empty_sample_has_none(self) -> None:
        self.assertIsNone(simulate.percentile([], 0.5))


class TestOutput(unittest.TestCase):
    def test_the_single_game_line_names_the_winner_and_the_turns(self) -> None:
        text = simulate.format_one(result(0, turns=87))
        self.assertIn("winner P1", text)
        self.assertIn("87 turns", text)

    def test_the_single_game_line_says_when_nobody_won(self) -> None:
        text = simulate.format_one(result(None, status=TIMEOUT, nets=(4, 9)))
        self.assertIn("no winner", text)
        self.assertIn("ahead on net worth: P2", text)

    def test_the_table_has_a_row_per_seat(self) -> None:
        text = simulate.format_summary(
            simulate.summarise([result(0), result(1)], elapsed=1.5)
        )
        self.assertIn("$2,000", text)
        self.assertIn("$1,000", text)
        self.assertIn("50.00", text)
        self.assertIn("games/s", text)

    def test_json_carries_the_same_numbers(self) -> None:
        payload = json.loads(
            simulate.summary_json(simulate.summarise([result(0), result(1)]))
        )
        self.assertEqual(payload["players"], 2)
        self.assertEqual(payload["stakes"], [2000, 1000])
        self.assertEqual(payload["seats"][0]["wins"], 1)
        self.assertEqual(payload["turns"]["median"], 100)

    def test_the_csv_has_a_header_and_a_row_per_game(self) -> None:
        stream = io.StringIO()
        simulate.write_csv([result(0, seed=3), result(None, status=TIMEOUT)], stream)
        rows = stream.getvalue().splitlines()
        self.assertEqual(len(rows), 3)
        self.assertTrue(rows[0].startswith("seed,status,winner_seat"))
        self.assertIn("cash1,cash2", rows[0])
        self.assertIn("3,win,1,P1", rows[1])
        self.assertIn(",timeout,,", rows[2])


class TestMain(unittest.TestCase):
    def run_cli(self, argv) -> tuple[int, str]:
        out = io.StringIO()
        import contextlib

        with contextlib.redirect_stdout(out):
            code = simulate.main(argv)
        return code, out.getvalue()

    def test_one_game_prints_one_outcome(self) -> None:
        code, text = self.run_cli(["1500", "1500", "--seed", "1", "-q"])
        self.assertEqual(code, 0)
        self.assertIn("winner", text)

    def test_many_games_print_the_table(self) -> None:
        code, text = self.run_cli(
            ["2000", "1000", "-n", "4", "--max-turns", "60", "-q", "-j", "1"]
        )
        self.assertEqual(code, 0)
        self.assertIn("seat", text)
        self.assertIn("win rate", text)

    def test_json_is_valid(self) -> None:
        _, text = self.run_cli(
            ["1500", "1500", "-n", "2", "--max-turns", "40", "--json", "-q", "-j", "1"]
        )
        self.assertEqual(json.loads(text)["games"], 2)

    def test_the_csv_can_go_to_stdout(self) -> None:
        _, text = self.run_cli(
            ["1500", "1500", "-n", "2", "--max-turns", "40", "--csv", "-", "-q",
             "-j", "1", "--json"]
        )
        self.assertIn("seed,status,winner_seat", text)

    def test_a_pot_that_does_not_add_up_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            simulate.main(["1500", "1000"])

    def test_any_total_lets_it_through(self) -> None:
        code, text = self.run_cli(
            ["300", "200", "--any-total", "--max-turns", "40", "-q"]
        )
        self.assertEqual(code, 0)
        self.assertTrue(text.strip())

    def test_a_bad_batch_size_is_refused(self) -> None:
        with self.assertRaises(SystemExit):
            simulate.main(["1500", "1500", "-n", "0"])
        with self.assertRaises(SystemExit):
            simulate.main(["1500", "1500", "--max-turns", "0"])


if __name__ == "__main__":
    unittest.main()
