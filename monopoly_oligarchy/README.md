# Monopoly — Custom Stake Edition

A full game of Monopoly in pygame, with one rules change: **the players do not
all start with $1,500**. Before any board appears, the setup screen asks how
many players there are (2–6) and what each one's opening stake is; the seats
share a fixed pot of $1,500 per player, however they like to divide it.

That change is the experiment. The question the code exists to answer is what
a bigger opening stake actually buys you — in win probability, and in how long
the game takes — and answering it takes thousands of games, not one game
watched at 60 frames a second. Hence the headless simulator below.

The implementation plan, phase by phase, is in [`PLAN.md`](PLAN.md).

## Install

```bash
pip install -r requirements.txt     # pygame >= 2.6, and nothing else
```

The simulator needs **no pygame at all** — `game.py` is pure rules, so a game
can be played with no window, no SDL and no display. Only the windowed game
and its UI tests need it installed.

## Play it

```bash
python3 -m monopoly.main
```

Space rolls, Enter ends the turn, Esc quits. Any seat can be toggled from
Human to Bot on the setup screen. A full transcript of everything that happens
to the board is written to `logs/monopoly-YYYYmmdd-HHMMSS.log`.

## Simulate it

`monopoly/simulate.py` plays whole games of bots as fast as the CPU will run
them and reports who won and how long it took. The positional arguments are
the opening stakes, in seat order:

```bash
python3 -m monopoly.simulate 1500 1500                       # one game
python3 -m monopoly.simulate 3000 1000 1000 1000 -n 500 -j 8 # 500 games, 8 cores
python3 -m monopoly.simulate 2500 2000 500 -n 2000 --csv runs.csv
```

Between two and six stakes, summing to $1,500 per player (`--any-total` turns
that check off). One game prints one line:

```
P1 $1,500  P2 $1,500
winner P2 (seat 2) in 91 turns / 46 rounds, net worth $7,286
```

Many games print what each seat's stake bought it:

```
4 players, 200 games, seed 0, turn cap 2,000
pot $6,000 ($1,500 per player)

seat  name         stake    wins          win rate  mean turns   median
----------------------------------------------------------------------
   1  P1          $3,000     155     77.50 +- 2.95%         147      137
   2  P2          $1,000       5      2.50 +- 1.10%         327      217
   3  P3          $1,000       7      3.50 +- 1.30%         299      322
   4  P4          $1,000       2      1.00 +- 0.70%         348      348
----------------------------------------------------------------------
decided 169/200 (84.5%)   turn-cap draws 31   wedged 0
turns per game won: mean 161  median 142  p10 79  p90 245  max 541
1.6 s elapsed (122.7 games/s)
```

The `+-` is one binomial standard error on the win rate. **Mean turns is the
mean over the games that seat won**, not over all games, so a seat that won
twice has a meaningless one; the whole-batch turn distribution underneath it
is drawn from every game that was won by anybody.

### Options

| flag | what it does |
| --- | --- |
| `-n, --games N` | how many games to play (default 1) |
| `-s, --seed S` | seed of the first game; game *i* uses `S + i` (default 0) |
| `-j, --jobs J` | worker processes; `0` picks one per core for a large batch |
| `--max-turns T` | player turns before a game is called a draw (default 2000) |
| `--decide-timeouts {nobody,leader}` | who a turn-cap draw counts as a win for |
| `--any-total` | allow stakes that do not sum to the standard pot |
| `--csv PATH` | write one row per game to `PATH` (`-` for stdout) |
| `--json` | print the summary as JSON instead of a table |
| `-q, --quiet` | no progress counter |

About 100–120 games a second on eight cores. Game *i* is always seeded
`--seed + i`, so a run is reproducible **whatever `--jobs` is set to**, and any
single game in it can be replayed on its own from the seed the CSV records.

### Turns, and what counts as one

`turns` counts **player turns**: one per seat that comes on turn, with a
doubles re-roll counted as part of the turn that earned it, because that is
what it is. `rounds` counts circuits of the table. A two-player game of 91
turns is 46 rounds.

### Getting the data out

`--csv` writes a row per game, ready for pandas or gnuplot:

```
seed,status,winner_seat,winner_name,turns,rounds,cash1,cash2,net_worth1,net_worth2,bankrupt1,bankrupt2
0,timeout,,,2001,1001,2000,1000,34560,39810,0,0
1,win,1,P1,116,58,2000,1000,7242,0,0,1
2,win,2,P2,117,59,2000,1000,0,7054,1,0
```

`--json` prints the summary — per-seat win rates and errors, the turn
quantiles, the status counts — as one object, for a script that sweeps a range
of splits and plots the result:

```bash
for rich in 1500 2000 2500 3000 3500 4000 4500 5000 5500; do
  poor=$(( 6000 - rich ))
  python3 -m monopoly.simulate $rich $poor -n 500 -q --json > "sweep-$rich.json"
done
```

### Not every game ends

Bots do not trade, so a monopoly forms only when the dice hand somebody a
whole colour group, and a board where nobody holds one can run forever. At
equal stakes and the default cap, **78 % of two-player games decide, falling
to 28 % at six players** — and raising the cap to 20,000 turns moves the
two-player number by nothing at all, so those boards are genuinely stuck
rather than merely slow.

Such a game comes back as `timeout` and is counted separately (`turn-cap
draws` in the table). It is never silently credited to whoever happened to be
ahead: `--decide-timeouts leader` asks for that convention explicitly, for a
study that needs every game to have a winner. `wedged` counts games where the
driver itself stopped making progress — a bug, reported rather than raised so
that one bad game cannot take a ten-thousand-game run down with it. Nothing
has produced one yet.

### As a library

```python
from monopoly import headless

result = headless.play([3000, 1000, 1000, 1000], seed=42)
print(result.winner, result.winner_name, result.turns, result.status)
```

`monopoly/headless.py` also carries `bot_step(game)`, which performs exactly
one bot decision against whatever the game is holding — an open auction, a
prompt, the build or mortgage screen, or the plain action list. It is the
single source of truth for what a bot does next: `main.bot_act` is that
function plus the 700 ms delay a human watcher needs.

`monopoly/simulate.py` exposes the batch layer: `run_batch()` to play many
games, `summarise()` to reduce them, and `format_summary()` / `summary_json()`
/ `write_csv()` to print them.

## Tests

```bash
./run_tests.sh                     # everything, in the pygame container
```

1,644 tests. Most of the suite needs pygame, so `run_tests.sh` runs it inside
a container (`$MONOPOLY_CONTAINER`, default `angry_goodall`) that has pygame
installed and the project bind-mounted. The simulator's own tests need nothing
but the standard library, so they run anywhere:

```bash
python3 -m unittest tests.test_headless tests.test_simulate
```
