"""The headless simulator: a whole game played with no window at all.

``main.py`` drives a game from a pygame event loop at 60 frames a second and
paces the bots so a human can follow them. This module drives the *same*
:class:`~monopoly.game.Game` as fast as the CPU will run it, with every seat
played by :class:`~monopoly.bot.BotStrategy`, and reports who won and how long
it took. Nothing here imports pygame -- like :mod:`monopoly.game` and
:mod:`monopoly.dice`, it is pure rules -- so a study of thousands of games
needs no display, no window and no SDL.

Two pieces live here:

* :func:`bot_step` performs exactly **one** bot decision against whatever the
  game is holding -- an open auction, a prompt, the build or mortgage screen,
  or the plain action list. It is the single source of truth for *what a bot
  does next*: ``main.bot_act`` is this function plus a delay timer.
* :func:`play` runs one game to the end and returns a :class:`Result`.

A game is driven by alternating the two things that can move it: the game's
own animation clock (:meth:`Game.update`, which resolves the roll and the
walk) and one bot decision. With ``step_ms=0`` and ``roll_ms=0`` neither waits
for a frame, so a game resolves in a few thousand iterations of a plain
``while`` loop.

Counting turns
--------------
:attr:`Result.turns` counts *player turns*: one per seat that comes on turn,
with a doubles re-roll counted as part of the turn that earned it (that is
what it is). :attr:`Result.rounds` counts circuits of the table, incremented
whenever the turn passes to a seat at or before the one it came from.

Not every game ends. Bots do not trade, so a board can settle into a stalemate
nobody can win; :data:`DEFAULT_MAX_TURNS` caps a game and the result comes
back as :data:`TIMEOUT` with :attr:`Result.leader` naming whoever was ahead on
net worth. A caller collecting statistics should count those separately rather
than pretend the leader won.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional, Sequence

from monopoly import actionlog
from monopoly.bot import BotStrategy
from monopoly.dice import Dice
from monopoly.game import Action, Game, State
from monopoly.player import Player

#: The seat counts a game may be set up with, as on the setup screen.
MIN_PLAYERS = 2
MAX_PLAYERS = 6

#: The standard opening bank, per player. A roster of ``N`` players is
#: expected to share ``STANDARD_STAKE * N`` between them however it likes.
STANDARD_STAKE = 1500

#: Token colours in seat order, mirroring ``ui.theme.TOKEN_COLORS`` -- which
#: cannot be imported here, because importing it would drag in pygame.
TOKEN_COLORS = ("red", "blue", "green", "yellow", "purple", "orange")

#: Player turns a game gets before :func:`play` calls it a draw.
DEFAULT_MAX_TURNS = 2000

#: Consecutive iterations in which neither the game nor any bot moves before
#: :func:`play` gives up on it. One is already suspicious; a handful means the
#: loop is genuinely wedged and no further iteration will help.
STALL_LIMIT = 8

#: Milliseconds the driver's clock advances per iteration. Nothing headless
#: waits on it -- the dice settle instantly and the token teleports -- but the
#: game is handed a monotonic clock all the same, as a real loop would.
TICK_MS = 1000

#: :attr:`Result.status` values: somebody won, the turn cap ran out, or the
#: loop wedged (a bug; reported rather than raised so one bad game cannot take
#: a ten-thousand-game study down with it).
WIN = "win"
TIMEOUT = "timeout"
STALLED = "stalled"


# --- one bot decision -------------------------------------------------------
def bot_step(game: Game, strategy: Optional[BotStrategy] = None,
             now_ms: int = 0) -> bool:
    """Perform one action for whichever bot the game is waiting on.

    Returns ``True`` when something was done, ``False`` when the game is not
    waiting on a bot -- a human is on turn, a human is the standing bidder, or
    there is nothing to decide because the dice or the token are still moving.

    The order of the checks is the order the game's modal surfaces take
    priority in: an auction first (its bidder is often *not* the player on
    turn), then a prompt, then the build and mortgage screens, then the plain
    action list.
    """
    strategy = strategy if strategy is not None else BotStrategy()

    # Auctions: the bidder may not be game.current.
    if game.auction is not None:
        bidder = game.auction.bidder
        if bidder is None or not bidder.is_bot:
            return False
        amount = strategy.auction_bid(game.auction, bidder)
        actionlog.debug(
            "bot", "act", player=bidder.name, doing="auction",
            amount=amount if amount is not None else "pass",
        )
        if amount is None:
            game.pass_bid()
        else:
            game.bid(amount)
        return True

    player = game.current
    if not getattr(player, "is_bot", False):
        return False

    # An open prompt (buy / jail / card / info).
    if game.prompt is not None:
        key = strategy.prompt_choice(game.prompt, player)
        actionlog.debug("bot", "act", player=player.name, doing="prompt", key=key)
        game.choose(key)
        return True

    # The build screen: plan, then commit. Nothing to build means the bot has
    # already had its go at building, so end the turn rather than re-open it.
    if game.build is not None:
        strategy.plan_build(game.build, player)
        changed = game.build.changed
        actionlog.debug(
            "bot", "act", player=player.name, doing="build", committing=changed,
        )
        game.close_build(commit=changed)
        if not changed:
            game.perform(Action.END_TURN, now_ms)
        return True

    # The mortgage screen: the same shape.
    if game.mortgage is not None:
        strategy.plan_mortgage(game.mortgage, player)
        changed = game.mortgage.changed
        actionlog.debug(
            "bot", "act", player=player.name, doing="mortgage", committing=changed,
        )
        game.close_mortgage(commit=changed)
        if not changed:
            game.perform(Action.END_TURN, now_ms)
        return True

    actions = game.available_actions()
    if not actions:
        return False

    action = strategy.choose_action(game, actions)
    actionlog.debug(
        "bot", "act", player=player.name, doing="action", what=action.value,
    )
    if action is Action.BUILD:
        game.open_build()  # decided on the next step
    elif action is Action.MORTGAGE:
        game.open_mortgage()  # likewise
    elif action in actions:
        game.perform(action, now_ms)
    else:
        game.perform(Action.END_TURN, now_ms)
    return True


# --- the game, with a turn counter on it ------------------------------------
class TrackedGame(Game):
    """A :class:`~monopoly.game.Game` that counts the turns it has played.

    The count cannot be kept in the driver loop because a turn is not a loop
    iteration: a turn may take one iteration or twenty, and a doubles re-roll
    takes several without being a new turn. Both hooks the turn order really
    passes through are overridden instead.
    """

    #: Class-level defaults, so the counters read sensibly on a game that was
    #: built but never started.
    turns = 0
    rounds = 0

    def start(self) -> None:
        super().start()
        self.turns = 1
        self.rounds = 1

    def _advance_turn(self) -> None:
        before = self.seat
        super()._advance_turn()
        if self.state is State.GAME_OVER:
            return
        self.turns += 1
        if self.seat <= before:
            self.rounds += 1


# --- results ----------------------------------------------------------------
@dataclass(frozen=True)
class Result:
    """What one simulated game came to."""

    #: The starting cash each seat was given, in seat order.
    cash: tuple[int, ...]
    names: tuple[str, ...]
    #: The seat that won, or ``None`` when nobody did (a timeout, a stall, or
    #: the everybody-went-bankrupt game the rules do allow).
    winner: Optional[int]
    #: Player turns and table circuits played.
    turns: int
    rounds: int
    #: :data:`WIN`, :data:`TIMEOUT` or :data:`STALLED`.
    status: str
    #: Every seat's closing net worth, in seat order.
    net_worths: tuple[int, ...]
    #: Seats that went bankrupt, as a flag per seat.
    bankrupt: tuple[bool, ...]
    seed: Optional[int]

    @property
    def winner_name(self) -> Optional[str]:
        return None if self.winner is None else self.names[self.winner]

    @property
    def leader(self) -> int:
        """The seat that was ahead on net worth when the game stopped.

        The same seat as :attr:`winner` in a game that was won, and the only
        answer there is to "who was winning?" in one that was not. Ties go to
        the earlier seat.
        """
        return max(range(len(self.net_worths)), key=lambda i: self.net_worths[i])

    def __str__(self) -> str:
        who = self.winner_name or f"nobody ({self.status})"
        return f"{who} in {self.turns} turns ({self.rounds} rounds)"


# --- setting a game up ------------------------------------------------------
def check_stakes(cash: Sequence[int], *, exact_total: bool = True) -> None:
    """Raise :class:`ValueError` unless ``cash`` is a playable roster.

    ``exact_total`` is the one house rule this edition adds: the seats share a
    fixed pot of ``STANDARD_STAKE`` per player, so how the money is split is
    the experiment and how much of it there is stays constant.
    """
    if not MIN_PLAYERS <= len(cash) <= MAX_PLAYERS:
        raise ValueError(
            f"a game needs {MIN_PLAYERS}-{MAX_PLAYERS} players, got {len(cash)}"
        )
    for seat, amount in enumerate(cash):
        if amount <= 0:
            raise ValueError(
                f"seat {seat + 1}: starting cash must be positive, got {amount}"
            )
    if exact_total:
        expected = STANDARD_STAKE * len(cash)
        total = sum(cash)
        if total != expected:
            raise ValueError(
                f"{len(cash)} players must share ${expected:,} "
                f"({STANDARD_STAKE:,} each), got ${total:,}"
            )


def build_players(
    cash: Sequence[int], names: Optional[Sequence[str]] = None
) -> list[Player]:
    """One bot per entry in ``cash``, in seat order."""
    if names is not None and len(names) != len(cash):
        raise ValueError(
            f"got {len(names)} names for {len(cash)} seats"
        )
    return [
        Player(
            name=names[seat] if names is not None else f"P{seat + 1}",
            cash=int(amount),
            token_color=TOKEN_COLORS[seat],
            is_bot=True,
        )
        for seat, amount in enumerate(cash)
    ]


def new_game(
    cash: Sequence[int],
    *,
    seed: Optional[int] = None,
    names: Optional[Sequence[str]] = None,
) -> TrackedGame:
    """A started game of bots, with every clock wound down to zero.

    One :class:`random.Random` seeds the dice and both decks, so a seed fixes
    the whole game: the same seed and the same stakes replay move for move.
    """
    rng = random.Random(seed)
    return TrackedGame(
        build_players(cash, names),
        rng=rng,
        dice=Dice(rng, roll_ms=0),
        step_ms=0,
    )


# --- playing one -----------------------------------------------------------
def play(
    cash: Sequence[int],
    *,
    seed: Optional[int] = None,
    max_turns: int = DEFAULT_MAX_TURNS,
    names: Optional[Sequence[str]] = None,
    exact_total: bool = True,
) -> Result:
    """Play one game of bots to the end and report how it went.

    ``max_turns`` caps a game that will not finish; ``exact_total`` enforces
    the shared-pot house rule (see :func:`check_stakes`).
    """
    check_stakes(cash, exact_total=exact_total)
    if max_turns < 1:
        raise ValueError(f"max_turns must be positive, got {max_turns}")

    game = new_game(cash, seed=seed, names=names)
    game.start()

    status = WIN
    now = 0
    stalls = 0
    while game.state is not State.GAME_OVER:
        if game.turns > max_turns:
            status = TIMEOUT
            break
        now += TICK_MS
        moved = game.update(now)
        if bot_step(game, now_ms=now):
            moved = True
        if moved:
            stalls = 0
            continue
        stalls += 1
        if stalls >= STALL_LIMIT:
            status = STALLED
            break

    winner = game.winner
    return Result(
        cash=tuple(int(c) for c in cash),
        names=tuple(p.name for p in game.players),
        winner=game.players.index(winner) if winner is not None else None,
        turns=game.turns,
        rounds=game.rounds,
        status=status,
        net_worths=tuple(p.net_worth() for p in game.players),
        bankrupt=tuple(p.is_bankrupt for p in game.players),
        seed=seed,
    )
