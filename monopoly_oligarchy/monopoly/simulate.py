"""Command line front end to the headless simulator.

    python3 -m monopoly.simulate 1500 1500
    python3 -m monopoly.simulate 3000 1000 1000 1000 -n 500
    python3 -m monopoly.simulate 2500 2000 500 -n 2000 -j 8 --csv runs.csv

The argument list is the starting stake of each seat, in seat order: between
two and six of them, summing to $1,500 per player (see
:func:`monopoly.headless.check_stakes`). That is the experiment this edition
exists to run -- the pot is fixed, and only its division changes -- so the
check is on by default and ``--any-total`` turns it off.

One game prints one line. Many games print a table: what each seat's stake
bought it in win probability, and how long the games took.

Every game is seeded from ``--seed`` plus its index, so a run is reproducible
whatever ``--jobs`` is set to, and any single game in it can be replayed on
its own with ``--seed`` set to the seed the CSV records.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from monopoly.headless import (
    DEFAULT_MAX_TURNS,
    MAX_PLAYERS,
    MIN_PLAYERS,
    STALLED,
    STANDARD_STAKE,
    TIMEOUT,
    WIN,
    Result,
    check_stakes,
    play,
)

#: Games below which spreading the work over processes costs more than it
#: saves. Only consulted when ``--jobs`` is left at its ``0`` (auto) default.
PARALLEL_THRESHOLD = 20

#: What ``--decide-timeouts`` credits an unfinished game to: nobody (the
#: honest default) or whoever was ahead on net worth when the cap ran out.
DECIDE_NOBODY = "nobody"
DECIDE_LEADER = "leader"


# --- running a batch --------------------------------------------------------
@dataclass(frozen=True)
class Job:
    """Everything one worker needs to play one game."""

    cash: tuple[int, ...]
    seed: int
    max_turns: int
    exact_total: bool


def _run(job: Job) -> Result:
    """Play one game. Top level so :mod:`multiprocessing` can pickle it."""
    return play(
        job.cash,
        seed=job.seed,
        max_turns=job.max_turns,
        exact_total=job.exact_total,
    )


def run_batch(
    cash: Sequence[int],
    games: int,
    *,
    seed: int = 0,
    max_turns: int = DEFAULT_MAX_TURNS,
    jobs: int = 0,
    exact_total: bool = True,
    progress: Optional[object] = None,
) -> list[Result]:
    """Play ``games`` games and return every result, in order.

    ``jobs`` is how many worker processes to spread the games over; ``0``
    picks one process for a small batch and one per core for a large one.
    Game *i* is always seeded ``seed + i``, so the batch is reproducible
    regardless of how it was divided up.
    """
    if games < 1:
        raise ValueError(f"games must be positive, got {games}")
    batch = [
        Job(tuple(int(c) for c in cash), seed + i, max_turns, exact_total)
        for i in range(games)
    ]
    workers = _worker_count(jobs, games)

    results: list[Result] = []
    if workers <= 1:
        for job in batch:
            results.append(_run(job))
            _tick(progress, len(results), games)
        return results

    import multiprocessing as mp

    # A chunk per worker per few games keeps a slow game from leaving one
    # worker running alone at the end of the batch. "spawn" rather than the
    # platform default: forking a process that has already started threads --
    # which anything running this from inside a pygame session has -- is a
    # documented way to deadlock, and a fresh interpreter costs a fraction of
    # a second against a batch worth parallelising at all.
    chunk = max(1, games // (workers * 8))
    with mp.get_context("spawn").Pool(workers) as pool:
        for result in pool.imap(_run, batch, chunksize=chunk):
            results.append(result)
            _tick(progress, len(results), games)
    return results


def _worker_count(jobs: int, games: int) -> int:
    if jobs > 0:
        return min(jobs, games)
    if games < PARALLEL_THRESHOLD:
        return 1
    import os

    return min(os.cpu_count() or 1, games)


def _tick(progress, done: int, total: int) -> None:
    """Redraw the one-line progress counter, if there is one."""
    if progress is None:
        return
    if done != total and done % 25:
        return
    print(f"\r  {done}/{total} games", end="", file=progress, flush=True)
    if done == total:
        print("\r" + " " * 24 + "\r", end="", file=progress, flush=True)


# --- statistics -------------------------------------------------------------
@dataclass(frozen=True)
class SeatStats:
    """What one seat's stake bought it across the batch."""

    seat: int
    name: str
    stake: int
    wins: int
    games: int
    #: Turns taken by the games this seat won.
    turns: tuple[int, ...]

    @property
    def win_rate(self) -> float:
        return self.wins / self.games if self.games else 0.0

    @property
    def error(self) -> float:
        """One standard error on :attr:`win_rate` (binomial)."""
        if not self.games:
            return 0.0
        p = self.win_rate
        return math.sqrt(max(p * (1.0 - p), 0.0) / self.games)

    @property
    def mean_turns(self) -> Optional[float]:
        return statistics.fmean(self.turns) if self.turns else None

    @property
    def median_turns(self) -> Optional[float]:
        return statistics.median(self.turns) if self.turns else None


@dataclass(frozen=True)
class Summary:
    """The whole batch, reduced to what the table and the JSON both print."""

    cash: tuple[int, ...]
    names: tuple[str, ...]
    games: int
    seats: tuple[SeatStats, ...]
    decided: int
    timeouts: int
    stalls: int
    #: Turns taken by every game that was actually won, sorted.
    turns: tuple[int, ...]
    elapsed: float
    decide_timeouts: str
    seed: int
    max_turns: int

    @property
    def undecided(self) -> int:
        return self.games - self.decided


def summarise(
    results: Sequence[Result],
    *,
    elapsed: float = 0.0,
    decide_timeouts: str = DECIDE_NOBODY,
    seed: int = 0,
    max_turns: int = DEFAULT_MAX_TURNS,
) -> Summary:
    """Reduce a batch of results to per-seat and whole-batch statistics.

    ``decide_timeouts`` says what to do with a game that hit the turn cap:
    leave it out of every seat's win count (:data:`DECIDE_NOBODY`), or credit
    it to whoever was ahead on net worth (:data:`DECIDE_LEADER`). A stalled
    game is never credited to anybody -- it is a bug, not a result.
    """
    if not results:
        raise ValueError("there are no results to summarise")
    first = results[0]
    seats = range(len(first.cash))
    wins = {seat: 0 for seat in seats}
    seat_turns: dict[int, list[int]] = {seat: [] for seat in seats}
    turns: list[int] = []
    decided = timeouts = stalls = 0

    for result in results:
        if result.status == WIN:
            winner = result.winner
            decided += 1
            # Only a game that really finished says anything about how long a
            # game takes, so the turn distributions are built from these.
            if winner is not None:
                turns.append(result.turns)
                seat_turns[winner].append(result.turns)
        elif result.status == TIMEOUT:
            timeouts += 1
            winner = result.leader if decide_timeouts == DECIDE_LEADER else None
        else:  # STALLED
            stalls += 1
            winner = None
        if winner is not None:
            wins[winner] += 1

    return Summary(
        cash=first.cash,
        names=first.names,
        games=len(results),
        seats=tuple(
            SeatStats(
                seat=seat,
                name=first.names[seat],
                stake=first.cash[seat],
                wins=wins[seat],
                games=len(results),
                turns=tuple(seat_turns[seat]),
            )
            for seat in seats
        ),
        decided=decided,
        timeouts=timeouts,
        stalls=stalls,
        turns=tuple(sorted(turns)),
        elapsed=elapsed,
        decide_timeouts=decide_timeouts,
        seed=seed,
        max_turns=max_turns,
    )


def percentile(values: Sequence[float], fraction: float) -> Optional[float]:
    """The ``fraction`` quantile of ``values`` (already sorted), or ``None``."""
    if not values:
        return None
    index = min(len(values) - 1, max(0, int(round(fraction * (len(values) - 1)))))
    return values[index]


# --- printing ---------------------------------------------------------------
def format_one(result: Result) -> str:
    """The single-game line: who won, and how long it took."""
    stakes = "  ".join(
        f"{name} ${cash:,}" for name, cash in zip(result.names, result.cash)
    )
    if result.winner is None:
        outcome = {
            TIMEOUT: f"no winner after {result.turns} turns (turn cap)",
            STALLED: f"no winner: the game wedged after {result.turns} turns",
        }.get(result.status, "no winner")
        lead = result.leader
        tail = (
            f"; ahead on net worth: {result.names[lead]} "
            f"${result.net_worths[lead]:,}"
        )
        return f"{stakes}\n{outcome}{tail}"
    return (
        f"{stakes}\n"
        f"winner {result.winner_name} (seat {result.winner + 1}) "
        f"in {result.turns} turns / {result.rounds} rounds, "
        f"net worth ${result.net_worths[result.winner]:,}"
    )


def format_summary(summary: Summary) -> str:
    """The many-games table."""
    lines: list[str] = []
    total = sum(summary.cash)
    lines.append(
        f"{len(summary.cash)} players, {summary.games:,} games, "
        f"seed {summary.seed}, turn cap {summary.max_turns:,}"
    )
    lines.append(f"pot ${total:,} (${STANDARD_STAKE:,} per player)")
    lines.append("")
    lines.append(
        f"{'seat':>4}  {'name':<8} {'stake':>9}  {'wins':>6}  "
        f"{'win rate':>16}  {'mean turns':>10}  {'median':>7}"
    )
    lines.append("-" * 70)
    for seat in summary.seats:
        mean = seat.mean_turns
        median = seat.median_turns
        stake = "$" + format(seat.stake, ",")
        lines.append(
            f"{seat.seat + 1:>4}  {seat.name:<8} {stake:>9}  "
            f"{seat.wins:>6}  "
            f"{seat.win_rate * 100:>8.2f} +- {seat.error * 100:<4.2f}%  "
            f"{(f'{mean:.0f}' if mean is not None else '-'):>10}  "
            f"{(f'{median:.0f}' if median is not None else '-'):>7}"
        )
    lines.append("-" * 70)

    undecided = summary.undecided
    share = summary.decided / summary.games * 100 if summary.games else 0.0
    lines.append(
        f"decided {summary.decided:,}/{summary.games:,} ({share:.1f}%)   "
        f"turn-cap draws {summary.timeouts:,}   wedged {summary.stalls:,}"
    )
    if summary.decide_timeouts == DECIDE_LEADER:
        lines.append(
            "turn-cap draws are credited to whoever led on net worth "
            "(--decide-timeouts leader)"
        )
    if summary.turns:
        lines.append(
            f"turns per game won: mean {statistics.fmean(summary.turns):.0f}  "
            f"median {statistics.median(summary.turns):.0f}  "
            f"p10 {percentile(summary.turns, 0.10):.0f}  "
            f"p90 {percentile(summary.turns, 0.90):.0f}  "
            f"max {summary.turns[-1]:,}"
        )
    if undecided and summary.decide_timeouts == DECIDE_NOBODY:
        lines.append(
            f"note: {undecided:,} game(s) reached the turn cap without a "
            "winner; raise --max-turns or use --decide-timeouts leader"
        )
    if summary.elapsed:
        rate = summary.games / summary.elapsed
        lines.append(f"{summary.elapsed:.1f} s elapsed ({rate:.1f} games/s)")
    return "\n".join(lines)


def summary_json(summary: Summary) -> str:
    """The same numbers as :func:`format_summary`, for a plotting script."""
    payload = {
        "players": len(summary.cash),
        "stakes": list(summary.cash),
        "names": list(summary.names),
        "games": summary.games,
        "seed": summary.seed,
        "max_turns": summary.max_turns,
        "decide_timeouts": summary.decide_timeouts,
        "decided": summary.decided,
        "timeouts": summary.timeouts,
        "stalls": summary.stalls,
        "elapsed_s": round(summary.elapsed, 3),
        "seats": [
            {
                "seat": seat.seat + 1,
                "name": seat.name,
                "stake": seat.stake,
                "wins": seat.wins,
                "win_rate": seat.win_rate,
                "win_rate_error": seat.error,
                "mean_turns": seat.mean_turns,
                "median_turns": seat.median_turns,
            }
            for seat in summary.seats
        ],
        "turns": {
            "mean": statistics.fmean(summary.turns) if summary.turns else None,
            "median": statistics.median(summary.turns) if summary.turns else None,
            "p10": percentile(summary.turns, 0.10),
            "p90": percentile(summary.turns, 0.90),
            "max": summary.turns[-1] if summary.turns else None,
        },
    }
    return json.dumps(payload, indent=2)


def write_csv(results: Iterable[Result], stream) -> None:
    """One row per game: the stakes that were played and what came of them."""
    results = list(results)
    seats = len(results[0].cash) if results else 0
    writer = csv.writer(stream)
    writer.writerow(
        ["seed", "status", "winner_seat", "winner_name", "turns", "rounds"]
        + [f"cash{i + 1}" for i in range(seats)]
        + [f"net_worth{i + 1}" for i in range(seats)]
        + [f"bankrupt{i + 1}" for i in range(seats)]
    )
    for result in results:
        writer.writerow(
            [
                result.seed,
                result.status,
                "" if result.winner is None else result.winner + 1,
                result.winner_name or "",
                result.turns,
                result.rounds,
            ]
            + list(result.cash)
            + list(result.net_worths)
            + [int(flag) for flag in result.bankrupt]
        )


# --- the command line -------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 -m monopoly.simulate",
        description=(
            "Play headless games of bot Monopoly and report who wins and how "
            "long it takes."
        ),
        epilog=(
            "The stakes must sum to $%d per player unless --any-total is "
            "given." % STANDARD_STAKE
        ),
    )
    parser.add_argument(
        "cash",
        metavar="CASH",
        type=int,
        nargs="+",
        help=(
            f"starting cash per seat, {MIN_PLAYERS}-{MAX_PLAYERS} values "
            f"summing to {STANDARD_STAKE} x the number of seats"
        ),
    )
    parser.add_argument(
        "-n", "--games", type=int, default=1, help="how many games to play (default 1)"
    )
    parser.add_argument(
        "-s", "--seed", type=int, default=0,
        help="seed of the first game; game i uses seed+i (default 0)",
    )
    parser.add_argument(
        "-j", "--jobs", type=int, default=0,
        help="worker processes; 0 picks one per core for a large batch (default 0)",
    )
    parser.add_argument(
        "--max-turns", type=int, default=DEFAULT_MAX_TURNS,
        help=f"player turns before a game is called a draw (default {DEFAULT_MAX_TURNS})",
    )
    parser.add_argument(
        "--decide-timeouts", choices=(DECIDE_NOBODY, DECIDE_LEADER),
        default=DECIDE_NOBODY,
        help=(
            "who a turn-cap draw counts as a win for: nobody (default) or the "
            "seat leading on net worth"
        ),
    )
    parser.add_argument(
        "--any-total", action="store_true",
        help="allow stakes that do not sum to the standard pot",
    )
    parser.add_argument(
        "--csv", metavar="PATH",
        help="write one row per game to PATH ('-' for stdout)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="print the summary as JSON instead of a table",
    )
    parser.add_argument(
        "-q", "--quiet", action="store_true",
        help="print nothing but the summary (no progress counter)",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        check_stakes(args.cash, exact_total=not args.any_total)
    except ValueError as exc:
        parser.error(str(exc))
    if args.games < 1:
        parser.error(f"--games must be positive, got {args.games}")
    if args.max_turns < 1:
        parser.error(f"--max-turns must be positive, got {args.max_turns}")

    progress = None if args.quiet or args.games < PARALLEL_THRESHOLD else sys.stderr
    started = time.perf_counter()
    results = run_batch(
        args.cash,
        args.games,
        seed=args.seed,
        max_turns=args.max_turns,
        jobs=args.jobs,
        exact_total=not args.any_total,
        progress=progress,
    )
    elapsed = time.perf_counter() - started

    if args.csv:
        if args.csv == "-":
            write_csv(results, sys.stdout)
        else:
            with open(args.csv, "w", newline="") as stream:
                write_csv(results, stream)
            if not args.quiet:
                print(f"wrote {len(results):,} rows to {args.csv}")

    summary = summarise(
        results,
        elapsed=elapsed,
        decide_timeouts=args.decide_timeouts,
        seed=args.seed,
        max_turns=args.max_turns,
    )
    if args.json:
        print(summary_json(summary))
    elif args.games == 1:
        print(format_one(results[0]))
    else:
        print(format_summary(summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
