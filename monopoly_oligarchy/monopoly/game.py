"""Phase 7: the turn loop.

:class:`Game` is the rules engine. It owns the roster, the deeds, the dice and
the two card decks, and walks one turn through the states the plan lays out::

    SETUP -> PLAYER_TURN_START -> ROLLING -> MOVING -> LAND_ACTION
          -> PLAYER_ACTIONS -> END_TURN -> (PLAYER_TURN_START | GAME_OVER)

**No pygame is imported here.** Like :mod:`monopoly.dice`, the rules stay pure
Python so a whole game can be played out in a test without a surface: hand the
game a ``Dice`` with ``roll_ms=0`` and a seeded ``random.Random`` and every
roll, card and landing is reproducible. ``main.py`` owns the window and does
nothing but pump events into :meth:`Game.perform` / :meth:`Game.choose` and
draw what :meth:`Game.available_actions` and :attr:`Game.prompt` describe.

Two things the game deliberately does *not* decide:

* **Which buttons exist** is the HUD's business; which of them are *legal* is
  this module's. :meth:`available_actions` is the whole answer. Nothing is
  deferred any more -- every button the HUD draws is decided here -- but
  :attr:`Game.action_handlers` is still consulted first, so a caller that
  wants its own answer to Build, Mortgage or Trade keeps it.
* **Modal questions** ("buy it or auction it?", "here is your card", "how are
  you getting out of Jail?") are handed out as a :class:`Prompt` and answered
  with :meth:`choose`. While a prompt is up no action is available, which is
  what makes it modal; drawing it is :mod:`monopoly.ui.popup`'s job.

Phase 8 added the last of those: a jailed player's turn opens on a
:data:`PROMPT_JAIL` offering the fine, a Get Out of Jail Free card or a roll
for doubles. Every answer ends in a roll, so there is still exactly one way a
turn begins.

Phase 9 added a second modal thing to :attr:`Game.build`: the
:class:`~monopoly.building.BuildPlan` behind the Build button. It is a draft,
not a transaction -- :meth:`Game.open_build` starts one, the screen edits it,
and :meth:`Game.close_build` either commits the lot atomically or throws it
away. The rules it enforces live in :mod:`monopoly.building`; the bank's stock
of houses and hotels lives in :attr:`Game.bank`.

Phase 10 added the third modal thing, :attr:`Game.auction`. Declining an
unowned deed no longer merely fires a hook: the bank puts the deed under the
hammer, and :meth:`Game.bid` / :meth:`Game.pass_bid` drive the round until it
settles itself. The rules live in :mod:`monopoly.auction`, and as with a build
draft no money moves until the sale is over.

Phase 11 added the fourth, :attr:`Game.trade`, and took :data:`Action.TRADE`
off the deferred list in the process -- trading is decided here now, the way
building has been since Phase 9. :meth:`Game.open_trade` starts a deal, the
screen drafts it, and :meth:`Game.accept_trade` is what swaps the deeds, the
cash and the jail cards. The rules live in :mod:`monopoly.trade`.

Phase 12 added the fifth, :attr:`Game.mortgage`, and took the last entry off
the deferred list with it -- :data:`DEFERRED_ACTIONS` is empty now.
:meth:`Game.open_mortgage` starts a draft, the screen edits it, and
:meth:`Game.close_mortgage` either flips every flag and moves the money at
once or throws the lot away. The rules live in :mod:`monopoly.mortgage`.

Phase 13 added nothing modal at all. A debt that outruns the cash in hand no
longer merely sits in :attr:`Game.debt` waiting for somebody to notice it:
:meth:`Game.settle_debt` answers it on the spot -- by forced sale if the
player can still find the money, and by bankruptcy if they cannot. The rules
live in :mod:`monopoly.bankruptcy`; what this file adds is where a settled
debt leaves the turn -- a bankrupt player's turn ends the moment their landing
is over, and a table with one player left is over altogether. As with
:attr:`on_auction`, a registered :attr:`on_shortfall` still wins, so a caller
that wants its own answer to a debt keeps it.

"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional, Sequence

from monopoly import actionlog
from monopoly.auction import Auction
from monopoly.bankruptcy import Settlement, raise_cash, settle
from monopoly.bankruptcy import describe as describe_settlement
from monopoly.building import Bank, BuildPlan, buildable_groups, describe_plan
from monopoly.cards import CHANCE, COMMUNITY_CHEST, Card, Deck
from monopoly.data_loader import BOARD_SIZE, DEED_TYPES, load_spaces
from monopoly.dice import Dice, roll
from monopoly.mortgage import MortgageLedger, has_business
from monopoly.mortgage import describe as describe_mortgage
from monopoly.player import Player
from monopoly.property import Property, build_properties
from monopoly.trade import Trade
from monopoly.trade import describe as describe_trade

#: Salary for passing (or landing on) Go.
GO_SALARY = 200
GO_INDEX = 0

#: Where Jail is, and what it costs to buy your way out.
JAIL_INDEX = 10
JAIL_FINE = 50

#: Failed doubles rolls a jailed player gets before the fine is forced.
JAIL_MAX_TURNS = 3

#: Doubles in a row that send a player to Jail.
MAX_DOUBLES = 3

#: Milliseconds the token rests on each space while it walks. ``0`` teleports.
STEP_MS = 90

#: Safety valve on :meth:`Game.update`: how many state steps one call may take
#: before it gives up and waits for the next frame. Only reachable with
#: ``STEP_MS == 0``, where a whole move resolves inside a single update.
MAX_STEPS_PER_UPDATE = 256

#: How many lines of :attr:`Game.log` are kept.
LOG_LIMIT = 200


class State(Enum):
    """Where in a turn the game is."""

    SETUP = "setup"
    PLAYER_TURN_START = "player_turn_start"
    ROLLING = "rolling"
    MOVING = "moving"
    LAND_ACTION = "land_action"
    PLAYER_ACTIONS = "player_actions"
    END_TURN = "end_turn"
    GAME_OVER = "game_over"


class Action(Enum):
    """A move the current player can ask for.

    Defined here rather than in the HUD because *which actions exist* is a
    rules question; :mod:`monopoly.ui.hud` re-exports this enum and uses each
    member's value as its button label.
    """

    ROLL = "Roll Dice"
    BUILD = "Build"
    MORTGAGE = "Mortgage"
    TRADE = "Trade"
    END_TURN = "End Turn"


#: Actions no phase has rules for yet: each would appear only once a later
#: phase registered a callable for it in :attr:`Game.action_handlers`. Phase 9
#: took :data:`Action.BUILD` off this list, Phase 11 took
#: :data:`Action.TRADE` and Phase 12 took :data:`Action.MORTGAGE`, so nothing
#: is left on it. The mechanism stays: a handler registered for any action is
#: still what :meth:`Game.perform` calls, and still lights its button.
DEFERRED_ACTIONS: tuple[Action, ...] = ()

# --- prompts ---------------------------------------------------------------
#: Buy this unowned deed, or send it to auction.
PROMPT_BUY = "buy"
#: A drawn Chance / Community Chest card, waiting to be acknowledged.
PROMPT_CARD = "card"
#: How a jailed player is getting out this turn.
PROMPT_JAIL = "jail"
#: Anything else that just needs an OK.
PROMPT_INFO = "info"

BUY_KEY = "buy"
AUCTION_KEY = "auction"
OK_KEY = "ok"
#: The three :data:`PROMPT_JAIL` answers.
PAY_KEY = "pay"
CARD_KEY = "card"
ROLL_KEY = "roll"


@dataclass(frozen=True)
class Choice:
    """One button on a prompt. A disabled choice is drawn but never fires."""

    key: str
    label: str
    enabled: bool = True


@dataclass(frozen=True)
class Prompt:
    """A modal question the game is waiting on an answer to.

    ``deed`` and ``card`` carry the subject of a :data:`PROMPT_BUY` /
    :data:`PROMPT_CARD` prompt so that :meth:`Game.choose` does not need any
    state of its own to resolve it.
    """

    kind: str
    title: str
    text: str
    options: tuple[Choice, ...]
    deed: Optional[Property] = None
    card: Optional[Card] = None

    def choice(self, key: str) -> Choice:
        """The choice named ``key``; raises if it is unknown or disabled."""
        for option in self.options:
            if option.key == key:
                if not option.enabled:
                    raise ValueError(f"choice {key!r} is disabled")
                return option
        raise ValueError(f"no choice {key!r} on this prompt")


@dataclass
class Debt:
    """A payment that could not be met in full.

    :meth:`Game._charge` takes every dollar the payer had and records what is
    still owed. Phase 13 answers it at once -- :meth:`Game.settle_debt` either
    forces the sales that cover it or declares the bankruptcy -- so a debt is
    outstanding only for as long as that takes, unless
    :attr:`Game.on_shortfall` is registered and takes the answer over.
    """

    payer: Player
    amount: int
    creditor: Optional[Player] = None


class Game:
    """One game of Monopoly: the roster, the board state and the turn loop."""

    def __init__(
        self,
        players: Sequence[Player],
        *,
        spaces: Optional[Sequence[dict]] = None,
        properties: Optional[Sequence[Property]] = None,
        dice: Optional[Dice] = None,
        rng: Optional[random.Random] = None,
        chance: Optional[Deck] = None,
        community_chest: Optional[Deck] = None,
        bank: Optional[Bank] = None,
        step_ms: int = STEP_MS,
    ) -> None:
        if not players:
            raise ValueError("a game needs at least one player")
        if step_ms < 0:
            raise ValueError("step_ms cannot be negative")
        self.players = list(players)
        self.spaces = list(spaces) if spaces is not None else load_spaces()
        self.properties = (
            list(properties) if properties is not None else build_properties(self.spaces)
        )
        self.rng = rng if rng is not None else random.Random()
        self.dice = dice if dice is not None else Dice(self.rng)
        self.chance = chance if chance is not None else Deck.chance(self.rng)
        self.community_chest = (
            community_chest
            if community_chest is not None
            else Deck.community_chest(self.rng)
        )
        #: The board's stock of houses and hotels (Phase 9).
        self.bank = bank if bank is not None else Bank()
        self.step_ms = step_ms

        self._by_index = {p.index: p for p in self.properties}

        #: Hooks later phases fill in. ``action_handlers`` maps a deferred
        #: action to ``handler(game)``; the other two are called with the game
        #: and the deed / debt in question.
        self.action_handlers: dict[Action, Callable[["Game"], None]] = {}
        self.on_auction: Optional[Callable[["Game", Property], None]] = None
        self.on_shortfall: Optional[Callable[["Game", Debt], None]] = None

        self.state = State.SETUP
        self.seat = 0
        self.message = ""
        self.log: list[str] = []
        self.prompt: Optional[Prompt] = None
        #: The open build screen's draft, or ``None``. Modal, like ``prompt``.
        self.build: Optional[BuildPlan] = None
        #: The sale in progress, or ``None``. Modal too (Phase 10).
        self.auction: Optional[Auction] = None
        #: The deal on the table, or ``None``. Modal as well (Phase 11).
        self.trade: Optional[Trade] = None
        #: The open mortgage screen's draft, or ``None``. Modal too (Phase 12).
        self.mortgage: Optional[MortgageLedger] = None
        self.rolled = False
        self.winner: Optional[Player] = None
        #: The debt still outstanding, or ``None``. Cleared as soon as
        #: :meth:`settle_debt` has answered it, one way or the other.
        self.debt: Optional[Debt] = None
        #: The last bankruptcy this game settled (Phase 13), for the log and
        #: for Phase 14's win screen.
        self.last_settlement: Optional[Settlement] = None
        self.last_roll: Optional[tuple[int, int]] = None

        self._now = 0
        self._extra_turn = False
        self._steps_left = 0
        self._step_dir = 1
        self._collect_go = True
        self._last_step_ms = 0
        self._rent_multiplier = 1
        self._roll_multiplier = 0
        self._goojf_held: list[tuple[Player, Deck, Card]] = []

        actionlog.forget_board()
        actionlog.event(
            "game", "new",
            players="; ".join(
                f"{p.name}(${p.cash:,}{', bot' if p.is_bot else ''})"
                for p in self.players
            ),
            deeds=len(self.properties), step_ms=self.step_ms,
            bank=f"{self.bank.houses}h/{self.bank.hotels}H",
        )
        actionlog.audit(self.bank, self.properties, "game.new", self.players)

    # --- roster -------------------------------------------------------------
    @property
    def current(self) -> Player:
        """Whose turn it is."""
        return self.players[self.seat]

    @property
    def active_players(self) -> list[Player]:
        """Everyone still in the game, in seat order."""
        return [p for p in self.players if not p.is_bankrupt]

    @property
    def last_total(self) -> int:
        """The total of the last settled roll (``0`` before the first)."""
        return sum(self.last_roll) if self.last_roll else 0

    # --- board --------------------------------------------------------------
    def space(self, index: int) -> dict:
        """The board space at ``index``."""
        return self.spaces[index]

    def deed(self, index: int) -> Optional[Property]:
        """The title deed at ``index``, or ``None`` for a space without one."""
        return self._by_index.get(index)

    # --- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        """Leave SETUP and open the first player's turn."""
        if self.state is not State.SETUP:
            raise RuntimeError("the game has already started")
        actionlog.event("game", "start", seats=len(self.players))
        self.seat = 0
        self._begin_turn()

    def update(self, now_ms: int) -> bool:
        """Advance any animation in flight; ``True`` if anything moved.

        Safe -- and expected -- to call every frame. It runs the state machine
        as far as it can without waiting, so an un-animated game
        (``step_ms=0``, ``Dice(roll_ms=0)``) resolves a whole roll, walk and
        landing inside one call.
        """
        self._now = now_ms
        progressed = False
        for _ in range(MAX_STEPS_PER_UPDATE):
            if self.state is State.ROLLING:
                if not self.dice.update(now_ms):
                    break
                self._resolve_roll()
            elif self.state is State.MOVING:
                if not self._step_move(now_ms):
                    break
            else:
                break
            progressed = True
        return progressed

    # --- what the player may do ---------------------------------------------
    def available_actions(self) -> frozenset[Action]:
        """The actions whose HUD buttons are live right now.

        Empty while a prompt, the build screen, an auction, a trade or the
        mortgage screen is up (that is what makes each of them modal) and
        while the dice or the token are in motion.
        """
        if self.prompt is not None or self.build is not None:
            return frozenset()
        if self.auction is not None or self.trade is not None:
            return frozenset()
        if self.mortgage is not None:
            return frozenset()
        if self.state is State.PLAYER_TURN_START:
            return frozenset({Action.ROLL})
        if self.state is State.PLAYER_ACTIONS:
            actions = {Action.END_TURN}
            actions |= {a for a in DEFERRED_ACTIONS if a in self.action_handlers}
            if self.can_build():
                actions.add(Action.BUILD)
            if self.can_trade():
                actions.add(Action.TRADE)
            if self.can_mortgage():
                actions.add(Action.MORTGAGE)
            return frozenset(actions)
        return frozenset()

    def can_build(self) -> bool:
        """Whether the current player has any lot to build on or sell from.

        That is one question, not two: a group may be built on only while it
        is held whole and unmortgaged, and mortgaging a lot requires the group
        to be bare -- so a group carrying buildings is always one the owner
        may also sell from.
        """
        return bool(buildable_groups(self.current, self.properties))

    def can_trade(self) -> bool:
        """Whether there is anybody left for the current player to deal with.

        Nothing more is asked: a player with no deeds and no cash still has a
        seat at the table, and a deal where only one side gives anything up is
        a perfectly ordinary gift.
        """
        return len(self.active_players) > 1

    def can_mortgage(self) -> bool:
        """Whether the current player has a deed to mortgage or a mortgage to lift.

        Owning deeds is not enough, the same way owning a lot is not enough to
        light the Build button: a player whose every group carries houses and
        whose every mortgage is out of reach has nothing to click, so the
        button stays dark. The rule itself lives in
        :func:`monopoly.mortgage.has_business`.
        """
        return has_business(self.current, self.properties)

    def perform(self, action: Action, now_ms: Optional[int] = None) -> bool:
        """Run ``action``; ``False`` (and nothing happens) if it is not legal."""
        if now_ms is not None:
            self._now = now_ms
        if action not in self.available_actions():
            actionlog.debug(
                "action", "refused", player=self.current.name,
                requested=action.value, state=self.state.value,
                available=",".join(sorted(a.value for a in self.available_actions()))
                or "(none)",
            )
            return False
        actionlog.event(
            "action", "perform", player=self.current.name, what=action.value,
            state=self.state.value, cash=self.current.cash,
        )
        if action is Action.ROLL:
            self.roll_dice(self._now)
        elif action is Action.END_TURN:
            self.end_turn()
        elif action is Action.BUILD and action not in self.action_handlers:
            self.open_build()
        elif action is Action.TRADE and action not in self.action_handlers:
            self.open_trade()
        elif action is Action.MORTGAGE and action not in self.action_handlers:
            self.open_mortgage()
        else:
            self.action_handlers[action](self)
        return True

    def roll_dice(self, now_ms: int = 0) -> None:
        """Start the roll that opens the current player's move."""
        if self.state is not State.PLAYER_TURN_START or self.prompt is not None:
            raise RuntimeError(f"cannot roll from {self.state.value}")
        self._now = now_ms
        self.dice.start(now_ms)
        actionlog.debug(
            "turn", "roll_started", player=self.current.name,
            position=self.current.position,
        )
        self.state = State.ROLLING
        self._say(f"{self.current.name} rolls...")

    def end_turn(self) -> None:
        """Close the turn: another go on doubles, otherwise the next seat."""
        if self.state is not State.PLAYER_ACTIONS:
            raise RuntimeError(f"cannot end the turn from {self.state.value}")
        self.state = State.END_TURN
        player = self.current
        actionlog.event(
            "turn", "end", player=player.name, cash=player.cash,
            position=player.position, net_worth=player.net_worth(),
            buildings=actionlog.buildings_of(player),
            again=self._extra_turn,
        )
        actionlog.audit(
            self.bank, self.properties, "turn.end", self.players
        )
        if self._extra_turn and not player.in_jail and not player.is_bankrupt:
            self._say(f"{player.name} rolled doubles and goes again.")
            self._begin_turn()
            return
        player.doubles_streak = 0
        self._advance_turn()

    # --- building -----------------------------------------------------------
    def open_build(self) -> BuildPlan:
        """Open the build screen on a fresh draft for the current player.

        The draft is modal in exactly the way a :class:`Prompt` is: while it
        is open :meth:`available_actions` is empty, so the turn cannot move on
        underneath it. Nothing is charged and nothing is built until
        :meth:`close_build` is called with ``commit=True``.
        """
        if self.state is not State.PLAYER_ACTIONS:
            raise RuntimeError(f"cannot build from {self.state.value}")
        if self.prompt is not None:
            raise RuntimeError("cannot build while a prompt is open")
        if self.auction is not None:
            raise RuntimeError("cannot build while an auction is running")
        if self.trade is not None:
            raise RuntimeError("cannot build while a trade is on the table")
        if self.mortgage is not None:
            raise RuntimeError("cannot build while the mortgage screen is open")
        self.build = BuildPlan(self.current, self.properties, self.bank)
        return self.build

    def close_build(self, commit: bool = False) -> bool:
        """Shut the build screen; ``True`` if anything was actually built.

        ``commit=False`` is Cancel -- the whole draft is dropped and the board
        is exactly as it was.
        """
        plan = self.build
        if plan is None:
            raise RuntimeError("the build screen is not open")
        self.build = None
        if not commit:
            actionlog.event(
                "build", "cancelled", player=plan.player.name,
                would_have=describe_plan(plan),
            )
            return False
        summary = describe_plan(plan)
        if not plan.commit():
            actionlog.warn(
                "build", "commit_failed", player=plan.player.name,
                summary=summary, cash=plan.player.cash,
            )
            return False
        self._say(f"{plan.player.name}: {summary}")
        return True

    def choose(self, key: str) -> None:
        """Answer the open prompt with one of its choices."""
        prompt = self.prompt
        if prompt is None:
            raise RuntimeError("there is no prompt to answer")
        prompt.choice(key)
        actionlog.event(
            "prompt", "answer", player=self.current.name, kind=prompt.kind,
            key=key, title=prompt.title,
            deed=prompt.deed.name if prompt.deed is not None else None,
        )
        self.prompt = None
        if prompt.kind == PROMPT_BUY:
            assert prompt.deed is not None
            if key == BUY_KEY:
                self._buy(prompt.deed)
            else:
                self._decline(prompt.deed)
        elif prompt.kind == PROMPT_CARD:
            assert prompt.card is not None
            self._execute_card(prompt.card)
        elif prompt.kind == PROMPT_JAIL:
            self._answer_jail(key)
        else:
            self._enter_player_actions()

    # --- turn plumbing ------------------------------------------------------
    def _begin_turn(self) -> None:
        self.rolled = False
        self._extra_turn = False
        self.prompt = None
        self.build = None
        self.auction = None
        self.trade = None
        self.mortgage = None
        self._rent_multiplier = 1
        self._roll_multiplier = 0
        player = self.current
        self.state = State.PLAYER_TURN_START
        actionlog.event(
            "turn", "begin", player=player.name, seat=self.seat,
            cash=player.cash, position=player.position,
            in_jail=player.in_jail, deeds=len(player.properties),
            buildings=actionlog.buildings_of(player),
            bank=f"{self.bank.houses}h/{self.bank.hotels}H",
        )
        actionlog.audit(self.bank, self.properties, "turn.begin", self.players)
        if player.in_jail:
            self._say(
                f"{player.name} is in Jail "
                f"(attempt {player.jail_turns + 1} of {JAIL_MAX_TURNS})."
            )
            self._prompt_jail(player)
        else:
            self._say(f"{player.name}'s turn.")

    def _advance_turn(self) -> None:
        if len(self.active_players) <= 1:
            self._end_game()
            return
        seat = self.seat
        for _ in range(len(self.players)):
            seat = (seat + 1) % len(self.players)
            if not self.players[seat].is_bankrupt:
                break
        actionlog.debug(
            "turn", "advance", frm=self.players[self.seat].name,
            to=self.players[seat].name, seat=seat,
        )
        self.seat = seat
        self._begin_turn()

    def _end_game(self) -> None:
        """Close the game on whoever is left standing.

        Reached two ways: the turn order running out of players to hand on to,
        and a Phase 13 bankruptcy that leaves one player at the table. Nobody
        left at all is possible too -- a one-handed game whose player goes
        bankrupt to the bank -- and then there is simply no winner.
        """
        active = self.active_players
        self.winner = active[0] if active else None
        self.state = State.GAME_OVER
        actionlog.event(
            "game", "over",
            winner=self.winner.name if self.winner is not None else "(nobody)",
            standings="; ".join(
                f"{p.name} ${p.net_worth():,}"
                + (" BANKRUPT" if p.is_bankrupt else "")
                for p in self.players
            ),
        )
        actionlog.audit(self.bank, self.properties, "game.over", self.players)
        if self.winner is not None:
            self._say(f"{self.winner.name} wins with ${self.winner.net_worth():,}.")
        else:
            self._say("Everybody is bankrupt; the bank wins.")

    def _enter_player_actions(self) -> None:
        """Land action is over; the player may build/trade, then End Turn.

        Unless there is nothing left for them to do: a player bankrupted by
        the landing they just made has no turn to finish, so the game hands
        straight on to the next seat -- or is over already.
        """
        self._rent_multiplier = 1
        self._roll_multiplier = 0
        self.rolled = True
        if self.state is State.GAME_OVER:
            return
        if self.current.is_bankrupt:
            self._advance_turn()
            return
        self.state = State.PLAYER_ACTIONS

    # --- rolling ------------------------------------------------------------
    def _resolve_roll(self) -> None:
        d1, d2 = self.dice.result
        total = d1 + d2
        self.last_roll = (d1, d2)
        player = self.current
        actionlog.event(
            "dice", "rolled", player=player.name, d1=d1, d2=d2, total=total,
            doubles=self.dice.doubles, streak=player.doubles_streak,
            in_jail=player.in_jail, position=player.position,
        )

        if player.in_jail:
            self._jail_roll(self.dice.doubles, total)
            return

        if self.dice.doubles:
            player.doubles_streak += 1
            if player.doubles_streak >= MAX_DOUBLES:
                self._say(
                    f"{player.name} rolled a third double in a row and goes to Jail."
                )
                self._go_to_jail(player)
                self._enter_player_actions()
                return
            self._extra_turn = True
        else:
            player.doubles_streak = 0
            self._extra_turn = False

        doubles_note = " (doubles!)" if self.dice.doubles else ""
        self._say(f"{player.name} rolled {d1} + {d2} = {total}{doubles_note}.")
        self._start_move(total)

    # --- jail ---------------------------------------------------------------
    def _prompt_jail(self, player: Player) -> None:
        """Open a jailed player's turn on the three ways out.

        A choice is disabled rather than allowed to fail: no $50 in hand, no
        card in hand. "Roll for Doubles" is always open -- it is the answer
        that costs nothing, and on the third attempt it is the *only* way the
        fine can be forced onto a player who cannot pay it.
        """
        attempt = player.jail_turns + 1
        note = (
            f"Miss again and the ${JAIL_FINE} fine is forced."
            if attempt >= JAIL_MAX_TURNS
            else "Doubles get you out without paying."
        )
        self.prompt = Prompt(
            kind=PROMPT_JAIL,
            title="In Jail",
            text=(
                f"{player.name} is in Jail -- roll {attempt} of "
                f"{JAIL_MAX_TURNS}. {note}"
            ),
            options=(
                Choice(
                    PAY_KEY,
                    f"Pay ${JAIL_FINE} & Roll",
                    player.cash >= JAIL_FINE,
                ),
                Choice(CARD_KEY, "Use Jail Card", player.goojf_cards > 0),
                Choice(ROLL_KEY, "Roll for Doubles"),
            ),
        )

    def _answer_jail(self, key: str) -> None:
        """Carry out a jail choice. Every one of them ends in a roll.

        Buying or carding your way out happens *before* the dice, so the roll
        that follows is an ordinary one -- doubles on it earn another turn,
        exactly as they would for a player who was never locked up.
        """
        player = self.current
        if key == PAY_KEY:
            self._say(f"{player.name} pays the ${JAIL_FINE} fine and leaves Jail.")
            self._charge(player, JAIL_FINE)
            self._leave_jail(player)
        elif key == CARD_KEY:
            self.return_goojf(player)
            self._say(
                f"{player.name} plays a Get Out of Jail Free card and leaves Jail."
            )
            self._leave_jail(player)
        self.roll_dice(self._now)

    def _jail_roll(self, doubles: bool, total: int) -> None:
        """A jailed player's roll: doubles frees them, three failures cost $50.

        Reached only by the "Roll for Doubles" answer -- the other two leave
        Jail before the dice are thrown.
        """
        player = self.current
        self._extra_turn = False
        if doubles:
            self._leave_jail(player)
            self._say(f"{player.name} rolled doubles and leaves Jail.")
            self._start_move(total)
            return
        if player.jail_turns < JAIL_MAX_TURNS - 1:
            player.jail_turns += 1
            self._say(f"{player.name} missed the doubles and stays in Jail.")
            self._enter_player_actions()
            return
        self._say(
            f"{player.name} missed a third time, pays ${JAIL_FINE} and leaves Jail."
        )
        self._charge(player, JAIL_FINE)
        self._leave_jail(player)
        if player.is_bankrupt:
            # The forced fine is the one charge a player can be bankrupted by
            # without choosing to make it, and there is then no move to walk.
            self._enter_player_actions()
            return
        self._start_move(total)

    def _go_to_jail(self, player: Player) -> None:
        """Send ``player`` straight to Jail, doubles streak and all."""
        actionlog.event(
            "jail", "enter", player=player.name, frm=player.position,
            streak=player.doubles_streak,
        )
        player.position = JAIL_INDEX
        player.in_jail = True
        player.jail_turns = 0
        player.doubles_streak = 0
        self._extra_turn = False

    def _leave_jail(self, player: Player) -> None:
        """Open the cell. The player rolls and moves like anybody else."""
        actionlog.event(
            "jail", "leave", player=player.name, turns_served=player.jail_turns
        )
        player.in_jail = False
        player.jail_turns = 0
        player.doubles_streak = 0

    # --- moving -------------------------------------------------------------
    def _start_move(self, steps: int, *, collect_go: bool = True) -> None:
        """Walk the current player ``steps`` spaces (negative walks backwards)."""
        self._steps_left = abs(steps)
        self._step_dir = 1 if steps >= 0 else -1
        #: Going backwards never pays the Go salary, whichever way past it.
        self._collect_go = collect_go and steps >= 0
        self._last_step_ms = self._now
        self.state = State.MOVING

    def _step_move(self, now_ms: int) -> bool:
        """Take one space of the walk; ``False`` while waiting on the clock."""
        if self._steps_left <= 0:
            self._arrive()
            return True
        if self.step_ms > 0 and now_ms - self._last_step_ms < self.step_ms:
            return False
        self._last_step_ms = now_ms
        player = self.current
        player.position = (player.position + self._step_dir) % BOARD_SIZE
        self._steps_left -= 1
        if self._collect_go and self._step_dir > 0 and player.position == GO_INDEX:
            player.receive(GO_SALARY)
            actionlog.event(
                "money", "go_salary", player=player.name, amount=GO_SALARY,
                cash=player.cash,
            )
            self._say(f"{player.name} passes Go and collects ${GO_SALARY}.")
        return True

    def _arrive(self) -> None:
        self.state = State.LAND_ACTION
        self._land()

    # --- landing ------------------------------------------------------------
    def _land(self) -> None:
        player = self.current
        space = self.space(player.position)
        kind = space["type"]
        actionlog.event(
            "move", "land", player=player.name, index=player.position,
            space=space["name"], kind=kind, cash=player.cash,
        )

        if kind in DEED_TYPES:
            deed = self.deed(player.position)
            assert deed is not None
            self._land_deed(player, deed)
            return
        if kind in (CHANCE, COMMUNITY_CHEST):
            self._draw_card(kind)
            return
        if kind == "go_to_jail":
            self._say(f"{player.name} goes directly to Jail.")
            self._go_to_jail(player)
        elif kind == "tax":
            amount = space["amount"]
            self._say(f"{player.name} pays ${amount} {space['name']}.")
            self._charge(player, amount)
        elif kind == "go":
            self._say(f"{player.name} landed on Go.")
        elif kind == "free_parking":
            self._say(f"{player.name} rests on Free Parking.")
        else:  # jail
            self._say(f"{player.name} is just visiting Jail.")
        self._enter_player_actions()

    def _land_deed(self, player: Player, deed: Property) -> None:
        owner = deed.owner
        actionlog.debug(
            "move", "land_deed", player=player.name,
            deed=actionlog.deed_state(deed),
        )
        if owner is None:
            self._prompt_buy(deed)
            return
        if owner is player:
            self._say(f"{player.name} already owns {deed.name}.")
        elif deed.mortgaged:
            self._say(f"{deed.name} is mortgaged, so no rent is owed.")
        else:
            rent = self._rent_for(deed)
            actionlog.event(
                "rent", "due", tenant=player.name, owner=owner.name,
                deed=deed.name, amount=rent, level=deed.building_level,
                multiplier=self._rent_multiplier, dice=self.last_total,
            )
            self._say(
                f"{player.name} pays ${rent:,} rent to {owner.name} "
                f"for {deed.name}."
            )
            self._charge(player, rent, owner)
        self._enter_player_actions()

    def _rent_for(self, deed: Property) -> int:
        """Rent owed on ``deed``, including any multiplier a card imposed."""
        if deed.is_utility and self._roll_multiplier:
            d1, d2 = roll(self.rng)
            self._say(f"Throwing again for the utility: {d1} + {d2}.")
            return self._roll_multiplier * (d1 + d2)
        rent = deed.current_rent(dice_total=self.last_total)
        return rent * self._rent_multiplier

    def _prompt_buy(self, deed: Property) -> None:
        player = self.current
        self._say(f"{deed.name} is unowned (${deed.price}).")
        self.prompt = Prompt(
            kind=PROMPT_BUY,
            title=deed.name,
            text=f"{deed.name} is for sale at ${deed.price}. Buy it?",
            options=(
                Choice(BUY_KEY, f"Buy ${deed.price}", player.cash >= deed.price),
                Choice(AUCTION_KEY, "Auction"),
            ),
            deed=deed,
        )

    def _buy(self, deed: Property) -> None:
        player = self.current
        if self._charge(player, deed.price):
            player.add_property(deed)
            actionlog.event(
                "deed", "bought", player=player.name, deed=deed.name,
                price=deed.price, cash=player.cash,
            )
            self._say(f"{player.name} buys {deed.name} for ${deed.price}.")
        self._enter_player_actions()

    def _decline(self, deed: Property) -> None:
        """The player passed on an unowned deed, so the bank auctions it.

        :attr:`on_auction` still wins if something registered one -- a caller
        that wants its own sale (or none at all) keeps that -- and the turn
        only moves on once nothing is left open: an auction is modal, so
        PLAYER_ACTIONS waits for :meth:`_settle_auction`.
        """
        actionlog.event(
            "deed", "declined", player=self.current.name, deed=deed.name,
            price=deed.price, cash=self.current.cash,
        )
        self._say(f"{self.current.name} declines {deed.name}.")
        if self.on_auction is not None:
            self.on_auction(self, deed)
        else:
            self.open_auction(deed)
        if self.auction is None and self.state is State.LAND_ACTION:
            self._enter_player_actions()

    # --- auction ------------------------------------------------------------
    def open_auction(self, deed: Property) -> Auction:
        """Put ``deed`` under the hammer, starting with the current player.

        Modal in the same way a prompt or a build draft is: while the sale
        runs :meth:`available_actions` is empty, so the turn cannot move on
        underneath it. A sale nobody can afford to open settles at once.
        """
        if self.auction is not None:
            raise RuntimeError("an auction is already running")
        if self.prompt is not None:
            raise RuntimeError("cannot auction while a prompt is open")
        if self.build is not None:
            raise RuntimeError("cannot auction while the build screen is open")
        if self.trade is not None:
            raise RuntimeError("cannot auction while a trade is on the table")
        if self.mortgage is not None:
            raise RuntimeError("cannot auction while the mortgage screen is open")
        auction = Auction(deed, self._auction_order())
        self.auction = auction
        actionlog.event(
            "auction", "open", deed=deed.name, list_price=deed.price,
            bidders="; ".join(f"{p.name}(${p.cash:,})" for p in auction.bidders),
        )
        self._say(f"{deed.name} goes to auction (list ${deed.price}).")
        self._echo_auction(auction, 0)
        self._settle_auction()
        return auction

    def _auction_order(self) -> list[Player]:
        """Everyone still in the game, starting with whoever is on turn.

        The player who declined bids first -- declining is passing on the
        asking price, not on the deed.
        """
        active = self.active_players
        if self.current in active:
            start = active.index(self.current)
            return active[start:] + active[:start]
        return active

    def bid(self, amount: int) -> bool:
        """Bid ``amount`` for the current bidder; ``False`` if it is illegal.

        An illegal bid -- below the asking price, or beyond the bidder's cash
        -- changes nothing, so the screen can offer it and let the rules say
        no.
        """
        auction = self._running_auction()
        seen = len(auction.log)
        if not auction.bid(amount):
            return False
        self._echo_auction(auction, seen)
        self._settle_auction()
        return True

    def pass_bid(self) -> bool:
        """Drop the current bidder out of the sale for good."""
        auction = self._running_auction()
        seen = len(auction.log)
        if not auction.withdraw():
            return False
        self._echo_auction(auction, seen)
        self._settle_auction()
        return True

    def _echo_auction(self, auction: Auction, seen: int) -> None:
        """Mirror the sale's new transcript lines into the game's own log.

        Its closing line is left out: :meth:`_settle_auction` restates that
        one once the deed and the money have really moved.
        """
        lines = auction.log[seen:]
        if auction.finished and lines:
            lines = lines[:-1]
        for line in lines:
            self._say(line)

    def _running_auction(self) -> Auction:
        if self.auction is None:
            raise RuntimeError("there is no auction to bid in")
        return self.auction

    def _settle_auction(self) -> None:
        """Close a finished sale: the winner pays the bank and takes the deed.

        A bid is never accepted beyond the bidder's cash, so the charge here
        cannot fail -- the winner can always pay. Nothing happens at all while
        the round is still going.
        """
        auction = self.auction
        if auction is None or not auction.finished:
            return
        self.auction = None
        winner, price, deed = auction.winner, auction.price, auction.deed
        if winner is None:
            self._say(f"Nobody bid; {deed.name} stays with the bank.")
        else:
            self._charge(winner, price)
            winner.add_property(deed)
            actionlog.event(
                "auction", "settled", deed=deed.name, winner=winner.name,
                price=price, cash=winner.cash,
            )
            self._say(f"{winner.name} wins {deed.name} at auction for ${price:,}.")
        if self.state is State.LAND_ACTION:
            self._enter_player_actions()

    # --- trading ------------------------------------------------------------
    def open_trade(self, partner: Optional[Player] = None) -> Trade:
        """Open a deal for the current player, modal like the build screen.

        ``partner`` may be left out, in which case the screen asks who the
        deal is with -- unless there is only one other player left, where
        there is nothing to ask. Nothing moves until :meth:`accept_trade`.
        """
        if self.state is not State.PLAYER_ACTIONS:
            raise RuntimeError(f"cannot trade from {self.state.value}")
        if self.prompt is not None:
            raise RuntimeError("cannot trade while a prompt is open")
        if self.build is not None:
            raise RuntimeError("cannot trade while the build screen is open")
        if self.auction is not None:
            raise RuntimeError("cannot trade while an auction is running")
        if self.trade is not None:
            raise RuntimeError("a trade is already on the table")
        if self.mortgage is not None:
            raise RuntimeError("cannot trade while the mortgage screen is open")
        self.trade = Trade(
            self.current,
            self.active_players,
            self.properties,
            partner=partner,
            on_goojf=self.transfer_goojf,
        )
        actionlog.event(
            "trade", "open", proposer=self.current.name,
            partner=partner.name if partner is not None else "(unchosen)",
        )
        return self.trade

    def propose_trade(self) -> bool:
        """Put the drafted offer to the partner; ``False`` if it is not legal."""
        trade = self._open_trade()
        if not trade.propose():
            return False
        self._say(f"Offer to {trade.partner.name}: {describe_trade(trade)}")
        return True

    def accept_trade(self) -> bool:
        """Settle the offer on the table and shut the screen.

        ``False`` -- and the trade stays open -- when the deal could not be
        settled, which the screen never offers: Accept is only live on an
        offer :class:`~monopoly.trade.Trade` has already said is good.
        """
        trade = self._open_trade()
        summary = describe_trade(trade)
        if not trade.accept():
            return False
        self.trade = None
        actionlog.audit(
            self.bank, self.properties, "trade.accept", self.players
        )
        self._say(f"Trade agreed -- {summary}")
        return True

    def close_trade(self, *, rejected: bool = False) -> None:
        """Shut the trade screen without a deal: Reject, or the proposer's Cancel."""
        trade = self._open_trade()
        partner = trade.partner
        if rejected and trade.reject():
            self._say(f"{partner.name} turns the offer down.")
        else:
            trade.cancel()
            self._say(f"{trade.proposer.name} calls the trade off.")
        self.trade = None

    def transfer_goojf(self, giver: Player, taker: Player, count: int) -> int:
        """Hand ``count`` Get Out of Jail Free cards over; returns how many moved.

        The count on a :class:`~monopoly.player.Player` is only half the story
        -- the game also remembers which deck each card came from, so that
        playing it later puts it back under the right one. A trade goes
        through here so both halves stay in step.
        """
        moved = 0
        for i, (holder, deck, card) in enumerate(self._goojf_held):
            if moved >= count:
                break
            if holder is not giver:
                continue
            self._goojf_held[i] = (taker, deck, card)
            giver.goojf_cards -= 1
            taker.goojf_cards += 1
            moved += 1
        return moved

    def _open_trade(self) -> Trade:
        if self.trade is None:
            raise RuntimeError("there is no trade on the table")
        return self.trade

    # --- mortgaging ---------------------------------------------------------
    def open_mortgage(self) -> MortgageLedger:
        """Open the mortgage screen on a fresh draft for the current player.

        Modal in exactly the way the build screen is: while it is open
        :meth:`available_actions` is empty, so the turn cannot move on
        underneath it. No flag flips and no money moves until
        :meth:`close_mortgage` is called with ``commit=True``.
        """
        if self.state is not State.PLAYER_ACTIONS:
            raise RuntimeError(f"cannot mortgage from {self.state.value}")
        if self.prompt is not None:
            raise RuntimeError("cannot mortgage while a prompt is open")
        if self.build is not None:
            raise RuntimeError("cannot mortgage while the build screen is open")
        if self.auction is not None:
            raise RuntimeError("cannot mortgage while an auction is running")
        if self.trade is not None:
            raise RuntimeError("cannot mortgage while a trade is on the table")
        if self.mortgage is not None:
            raise RuntimeError("the mortgage screen is already open")
        self.mortgage = MortgageLedger(self.current, self.properties)
        return self.mortgage

    def close_mortgage(self, commit: bool = False) -> bool:
        """Shut the mortgage screen; ``True`` if anything actually changed.

        ``commit=False`` is Cancel -- the whole draft is dropped and every
        deed is exactly as it was.
        """
        ledger = self.mortgage
        if ledger is None:
            raise RuntimeError("the mortgage screen is not open")
        self.mortgage = None
        if not commit:
            actionlog.event(
                "mortgage", "cancelled", player=ledger.player.name,
                would_have=describe_mortgage(ledger),
            )
            return False
        summary = describe_mortgage(ledger)
        if not ledger.commit():
            actionlog.warn(
                "mortgage", "commit_failed", player=ledger.player.name,
                summary=summary, cash=ledger.player.cash,
            )
            return False
        actionlog.audit(
            self.bank, self.properties, "mortgage.commit", self.players
        )
        self._say(f"{ledger.player.name}: {summary}")
        return True

    # --- cards --------------------------------------------------------------
    def _draw_card(self, kind: str) -> None:
        deck = self.chance if kind == CHANCE else self.community_chest
        card = deck.draw()
        title = "Chance" if kind == CHANCE else "Community Chest"
        actionlog.event(
            "card", "drawn", player=self.current.name, deck=title,
            action=card.action, text=card.text,
        )
        self._say(f"{self.current.name} draws {title}: {card.text}")
        self.prompt = Prompt(
            kind=PROMPT_CARD,
            title=title,
            text=card.text,
            options=(Choice(OK_KEY, "OK"),),
            card=card,
        )

    def _execute_card(self, card: Card) -> None:
        """Carry out a drawn card. A card that moves re-enters MOVING."""
        player = self.current
        action = card.action
        actionlog.debug(
            "card", "execute", player=player.name, action=action,
            text=card.text, cash=player.cash, position=player.position,
        )

        if action == "move_to":
            self._start_move(
                (card.destination - player.position) % BOARD_SIZE,
                collect_go=card.collect_go,
            )
            return
        if action == "move_to_nearest":
            self._move_to_nearest(card)
            return
        if action == "move_relative":
            self._start_move(card.offset, collect_go=card.collect_go)
            return

        if action == "collect":
            player.receive(card.amount)
            self._say(f"{player.name} collects ${card.amount}.")
        elif action == "pay":
            self._say(f"{player.name} pays ${card.amount}.")
            self._charge(player, card.amount)
        elif action == "pay_per_building":
            self._pay_per_building(card)
        elif action == "get_out_of_jail":
            self._keep_goojf(player, card)
        elif action == "go_to_jail":
            self._say(f"{player.name} goes directly to Jail.")
            self._go_to_jail(player)
        elif action == "collect_from_players":
            self._collect_from_players(card.amount)
        elif action == "pay_to_players":
            self._pay_to_players(card.amount)
        self._enter_player_actions()

    def _move_to_nearest(self, card: Card) -> None:
        player = self.current
        target = nearest_ahead(self.spaces, player.position, card.group)
        self._rent_multiplier = max(1, card.rent_multiplier)
        self._roll_multiplier = card.roll_multiplier
        self._start_move(
            (target - player.position) % BOARD_SIZE, collect_go=card.collect_go
        )

    def _pay_per_building(self, card: Card) -> None:
        player = self.current
        houses = sum(p.house_count for p in player.properties)
        hotels = sum(p.hotel_count for p in player.properties)
        amount = houses * card.per_house + hotels * card.per_hotel
        actionlog.event(
            "card", "repairs", player=player.name, houses=houses,
            hotels=hotels, amount=amount,
            standing=actionlog.buildings_of(player),
        )
        self._say(
            f"{player.name} pays ${amount:,} for repairs "
            f"({houses} houses, {hotels} hotels)."
        )
        self._charge(player, amount)

    def _collect_from_players(self, amount: int) -> None:
        player = self.current
        for other in self.active_players:
            if other is not player:
                self._charge(other, amount, player)
        self._say(f"{player.name} collects ${amount} from every player.")

    def _pay_to_players(self, amount: int) -> None:
        """Pay ``amount`` to each other player, in seat order.

        A player who cannot pay everybody goes bankrupt to whoever they were
        paying when the money ran out, and the ones further round the table
        are simply never paid -- there is nothing left to pay them with.
        """
        player = self.current
        for other in self.active_players:
            if other is player:
                continue
            self._charge(player, amount, other)
            if player.is_bankrupt:
                return
        self._say(f"{player.name} pays ${amount} to every player.")

    def _keep_goojf(self, player: Player, card: Card) -> None:
        # The player is still standing on the space that dealt the card, which
        # is the only reliable way to tell the two decks' identical Get Out of
        # Jail Free cards apart.
        kind = self.space(player.position)["type"]
        deck = self.chance if kind == CHANCE else self.community_chest
        player.goojf_cards += 1
        self._goojf_held.append((player, deck, card))
        actionlog.event(
            "goojf", "kept", player=player.name, held=player.goojf_cards
        )
        self._say(f"{player.name} keeps a Get Out of Jail Free card.")

    def return_goojf(self, player: Player) -> bool:
        """Spend one of ``player``'s cards, putting it back under its deck.

        The :data:`PROMPT_JAIL` "Use Jail Card" answer calls this; ``False``
        means the player had none, which is why that choice is offered
        disabled rather than left to fail.
        """
        for i, (holder, deck, card) in enumerate(self._goojf_held):
            if holder is player:
                del self._goojf_held[i]
                player.goojf_cards -= 1
                deck.return_card(card)
                actionlog.event(
                    "goojf", "returned", player=player.name,
                    held=player.goojf_cards,
                )
                return True
        return False

    # --- money --------------------------------------------------------------
    def _charge(
        self, payer: Player, amount: int, creditor: Optional[Player] = None
    ) -> bool:
        """Move ``amount`` from ``payer`` to ``creditor`` (or the bank).

        Returns ``False`` when the cash in hand was not there. In that case
        every dollar the payer had is handed over, the shortfall is recorded
        in :attr:`debt`, and :meth:`settle_debt` answers it -- with a forced
        sale, or with the payer's bankruptcy. A ``False`` therefore does not
        mean the creditor went unpaid: it means the payment cost the payer
        more than cash.

        Nothing at all is taken from a player who is already bankrupt. They
        have nothing to take, and their debts died with their game.
        """
        if amount <= 0:
            return True
        if payer.is_bankrupt:
            actionlog.debug(
                "money", "charge_skipped", payer=payer.name, amount=amount,
                reason="already bankrupt",
            )
            return False
        to = creditor.name if creditor is not None else "the bank"
        if payer.pay(amount):
            if creditor is not None:
                creditor.receive(amount)
            actionlog.event(
                "money", "charge", payer=payer.name, to=to, amount=amount,
                cash=payer.cash,
            )
            return True
        paid, short = payer.cash, amount - payer.cash
        payer.cash = 0
        if creditor is not None and paid:
            creditor.receive(paid)
        actionlog.event(
            "money", "shortfall", payer=payer.name, to=to, amount=amount,
            paid=paid, short=short,
            liquidation=payer.liquidation_value(),
            standing=actionlog.buildings_of(payer),
        )
        self.debt = Debt(payer, short, creditor)
        self._say(f"{payer.name} is ${short:,} short of ${amount:,}.")
        if self.on_shortfall is not None:
            self.on_shortfall(self, self.debt)
        else:
            self.settle_debt()
        return False

    # --- debts and bankruptcy (Phase 13) ------------------------------------
    def settle_debt(self) -> bool:
        """Answer the outstanding debt; ``True`` if it was paid in the end.

        A player who could have paid is made to: every building goes back to
        the bank at half price and deeds are mortgaged, in board order, until
        the money is there -- and then the creditor is paid in full. A player
        who could not, even stripped bare, goes bankrupt.

        Called by :meth:`_charge` unless :attr:`on_shortfall` has taken the
        answer over, in which case that hook may call this itself.
        """
        debt = self.debt
        if debt is None:
            raise RuntimeError("there is no debt to settle")
        payer = debt.payer
        actionlog.event(
            "debt", "settling", payer=payer.name, amount=debt.amount,
            creditor=debt.creditor.name if debt.creditor is not None else "the bank",
            cash=payer.cash, liquidation=payer.liquidation_value(),
        )
        if not payer.can_raise(debt.amount):
            self._declare_bankrupt(debt)
            return False

        raised = raise_cash(payer, debt.amount, self.bank)
        if raised:
            self._say(f"{payer.name} sells and mortgages to raise ${raised:,}.")
        payer.pay(debt.amount)
        if debt.creditor is not None:
            debt.creditor.receive(debt.amount)
        where = "the bank" if debt.creditor is None else debt.creditor.name
        self._say(f"{payer.name} settles the ${debt.amount:,} owed to {where}.")
        actionlog.event(
            "debt", "settled", payer=payer.name, amount=debt.amount,
            to=where, raised=raised, cash=payer.cash,
            standing=actionlog.buildings_of(payer),
        )
        actionlog.audit(
            self.bank, self.properties, "debt.settled", self.players
        )
        self.debt = None
        return True

    def _declare_bankrupt(self, debt: Debt) -> None:
        """Wind ``debt.payer`` up and take them out of the game.

        The turn order needs nothing done to it -- :attr:`active_players` is
        what it is drawn from, and that skips the bankrupt. Two things are
        left over, and they are handled at either end of this: whether anybody
        is still playing, decided here, and whose turn it now is, decided by
        :meth:`_enter_player_actions` once the landing that caused all this
        has finished resolving.
        """
        payer = debt.payer
        self.debt = None
        self._say(
            f"{payer.name} cannot cover ${debt.amount:,} and is bankrupt."
        )
        settlement = settle(
            payer,
            debt.creditor,
            debt.amount,
            self.bank,
            on_goojf=self._hand_over_goojf,
        )
        self.last_settlement = settlement
        actionlog.audit(
            self.bank, self.properties, "bankruptcy.settled", self.players
        )
        self._say(describe_settlement(settlement))
        self._say(f"{payer.name} is out of the game.")
        if len(self.active_players) <= 1:
            self._end_game()

    def _hand_over_goojf(
        self, giver: Player, taker: Optional[Player], count: int
    ) -> int:
        """Move a bankrupt player's jail cards on; returns how many moved.

        To a creditor they change hands like any traded card. To the bank they
        go back under the deck they were drawn from, which is the whole reason
        :mod:`monopoly.bankruptcy` asks rather than doing it itself.
        """
        if taker is not None:
            return self.transfer_goojf(giver, taker, count)
        moved = 0
        while moved < count and self.return_goojf(giver):
            moved += 1
        return moved

    # --- messages -----------------------------------------------------------
    def _say(self, text: str) -> None:
        """Set the HUD's one-line message and append it to the log."""
        self.message = text
        self.log.append(text)
        actionlog.debug("narrate", "say", text=text)
        if len(self.log) > LOG_LIMIT:
            del self.log[: len(self.log) - LOG_LIMIT]


def nearest_ahead(spaces: Sequence[dict], position: int, kind: str) -> int:
    """The next space of type ``kind`` strictly ahead of ``position``.

    "Ahead" wraps, and never returns ``position`` itself: a player standing on
    a railroad who draws "advance to the nearest Railroad" moves to the *next*
    one.
    """
    candidates = [s["index"] for s in spaces if s["type"] == kind]
    if not candidates:
        raise ValueError(f"no {kind!r} spaces on this board")
    return min(candidates, key=lambda i: (i - position) % BOARD_SIZE or BOARD_SIZE)
