"""Strategic bot player for Monopoly: Custom Stake Edition.

:class:`BotStrategy` is a stateless evaluator -- it makes decisions from the
board state it is handed and changes nothing itself.  The ``bot_act`` function
in :mod:`monopoly.main` is the only caller; it paces actions with a timer so
a human watching can follow what the bot is doing.

Strategy overview
-----------------
* **Buying**: buy any deed the bot can afford while keeping a $200 cash
  reserve, weighted toward deeds that complete or advance a colour group.
* **Auctions**: bid up to the face price of the deed, or up to 110 % of face
  price when it would complete a monopoly, never leaving less than $200 in hand;
  raise in $50 steps so a sale between bots does not crawl.
* **Building**: spread houses across each monopoly group following the
  even-building rule; stop when the remaining cash would fall below 30 % of
  the starting amount or $300, whichever is larger.
* **Mortgaging**: mortgage the cheapest deeds first when cash drops below
  $150; lift mortgages when cash is ample (> $800).
* **Actions**: prefer building when possible, mortgage when pinched for cash,
  otherwise end the turn.
* **Jail**: pay the fine once two turns have passed; use a card immediately if
  available.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from monopoly.auction import Auction
    from monopoly.building import BuildPlan
    from monopoly.game import Game, Prompt
    from monopoly.mortgage import MortgageLedger
    from monopoly.player import Player
    from monopoly.property import Property

from monopoly import actionlog
from monopoly.game import (
    Action,
    BUY_KEY,
    AUCTION_KEY,
    OK_KEY,
    PAY_KEY,
    CARD_KEY,
    ROLL_KEY,
    PROMPT_BUY,
    PROMPT_CARD,
    PROMPT_JAIL,
    PROMPT_INFO,
)

#: Cash the bot tries never to drop below after any spending decision.
CASH_FLOOR = 200
#: Minimum cash before the bot considers mortgaging properties.
MORTGAGE_THRESHOLD = 150
#: Minimum cash before the bot lifts a mortgage.
UNMORTGAGE_THRESHOLD = 800
#: Fraction of cash the bot keeps as a building reserve (the rest it can spend).
BUILD_RESERVE_FRACTION = 0.30
#: How much a bot raises the standing bid by. The auction's own increment is
#: the standard $1, which makes a bot-versus-bot sale crawl up a dollar at a
#: time; bidding in $50 steps settles the same deed in a handful of rounds.
BID_STEP = 50


class BotStrategy:
    """Stateless evaluator -- create one, call its methods, discard it."""

    # ------------------------------------------------------------------ prompts

    def prompt_choice(self, prompt, player) -> str:
        """Return the key the bot should send to :meth:`~monopoly.game.Game.choose`."""
        if prompt.kind == PROMPT_BUY:
            key = self._buy_key(prompt, player)
        elif prompt.kind == PROMPT_JAIL:
            key = self._jail_key(prompt, player)
        elif prompt.kind == PROMPT_CARD:
            key = self._card_key(prompt, player)
        else:  # PROMPT_INFO -- just dismiss.
            key = OK_KEY
        actionlog.event(
            "bot", "prompt_choice", player=player.name, kind=prompt.kind,
            key=key, cash=player.cash,
        )
        return key

    def _buy_key(self, prompt, player) -> str:
        """BUY_KEY when the bot wants the deed; AUCTION_KEY otherwise."""
        enabled_keys = {c.key for c in prompt.options if c.enabled}
        if BUY_KEY not in enabled_keys:
            return AUCTION_KEY if AUCTION_KEY in enabled_keys else OK_KEY

        deed = prompt.deed
        if deed is None:
            return AUCTION_KEY if AUCTION_KEY in enabled_keys else OK_KEY

        # Only buy when a comfortable reserve remains.
        if player.cash - deed.price < CASH_FLOOR:
            return AUCTION_KEY if AUCTION_KEY in enabled_keys else OK_KEY

        # Always prefer deeds that advance or complete a monopoly.
        owned_in_group = sum(
            1 for p in player.properties if p.group == deed.group
        )
        if owned_in_group >= 1:
            return BUY_KEY

        # Buy single deeds too, so long as the reserve is comfortable.
        if player.cash - deed.price >= CASH_FLOOR * 2:
            return BUY_KEY

        return AUCTION_KEY if AUCTION_KEY in enabled_keys else OK_KEY

    def _jail_key(self, prompt, player) -> str:
        """Decide how to handle being in jail."""
        enabled_keys = {c.key for c in prompt.options if c.enabled}

        # Use a card immediately if available -- it is free.
        if CARD_KEY in enabled_keys:
            return CARD_KEY

        # Pay the fine once we have been waiting long enough (>= 2 jail turns)
        # or when we have monopolies to exploit (get moving sooner).
        has_monopoly = bool(player.monopolies(player.properties))
        if PAY_KEY in enabled_keys:
            if player.jail_turns >= 2 or has_monopoly:
                if player.cash - 50 >= CASH_FLOOR:
                    return PAY_KEY

        # Otherwise roll for doubles.
        if ROLL_KEY in enabled_keys:
            return ROLL_KEY

        # Fallback: first available key.
        return next(iter(enabled_keys), OK_KEY)

    def _card_key(self, prompt, player) -> str:
        """Community chest / chance card -- just dismiss."""
        enabled_keys = {c.key for c in prompt.options if c.enabled}
        return OK_KEY if OK_KEY in enabled_keys else next(iter(enabled_keys), OK_KEY)

    # ----------------------------------------------------------------- auctions

    def auction_bid(self, auction, player) -> Optional[int]:
        """Return a bid amount, or ``None`` to pass.

        The bot bids up to the deed's face price when it would not complete a
        monopoly, and up to 110 % of face price when it would.  It never bids
        more than it can afford after keeping :data:`CASH_FLOOR` in hand.

        It raises the standing bid by :data:`BID_STEP` rather than by the
        auction's $1 minimum, so a table of bots reaches the price nobody will
        beat in a few rounds instead of a few hundred. The last bid before the
        ceiling is the ceiling itself, so nothing is given up by stepping
        coarsely.
        """
        deed = auction.deed

        # Decide ceiling based on strategic value.
        owned_in_group = sum(1 for p in player.properties if p.group == deed.group)
        group_size = deed.group_size
        would_monopolise = (owned_in_group == group_size - 1)

        ceiling = deed.price * 110 // 100 if would_monopolise else deed.price
        # Never leave less than CASH_FLOOR in hand.
        ceiling = min(ceiling, player.cash - CASH_FLOOR)

        min_bid = auction.min_bid
        if min_bid > ceiling or min_bid > player.cash:
            actionlog.event(
                "bot", "auction_pass", player=player.name, deed=deed.name,
                min_bid=min_bid, ceiling=ceiling, cash=player.cash,
            )
            return None  # pass

        # A whole step over the standing bid, but never past what we will pay.
        amount = min(max(min_bid, auction.high_bid + BID_STEP), ceiling)
        actionlog.event(
            "bot", "auction_bid", player=player.name, deed=deed.name,
            amount=amount, ceiling=ceiling, cash=player.cash,
            monopolising=would_monopolise,
        )
        return amount

    # ------------------------------------------------------------------ building

    def plan_build(self, plan, player) -> None:
        """Add as many buildings as the bot can afford while keeping a reserve.

        The even-building rule is enforced by :meth:`~BuildPlan.can_add`; we
        just keep asking until nothing more can be added within the budget.
        """
        reserve = max(300, int(player.cash * BUILD_RESERVE_FRACTION))
        budget = player.cash - reserve  # how much we are allowed to spend
        actionlog.event(
            "bot", "plan_build", player=player.name, cash=player.cash,
            reserve=reserve, budget=budget, lots=len(plan.all_lots),
            standing=actionlog.buildings_of(player),
        )

        if budget <= 0:
            return

        # Keep adding buildings one at a time until we run out of budget or
        # legal moves.  Prioritise the most expensive lots (higher rents).
        changed = True
        while changed:
            changed = False
            for deed in sorted(plan.all_lots, key=lambda d: -d.price):
                if not plan.can_add(deed):
                    continue
                # Estimate the extra cost; if within budget, add it.
                next_cost = plan.cost + deed.build_cost
                if next_cost > budget:
                    continue
                plan.add(deed)
                changed = True
                break  # restart so the even-building rule is re-evaluated
        actionlog.event(
            "bot", "plan_build_done", player=player.name, cost=plan.cost,
            budget=budget, changed=plan.changed,
        )

    # ----------------------------------------------------------------- mortgaging

    def plan_mortgage(self, ledger, player) -> None:
        """Toggle mortgages: mortgage cheap deeds when short of cash, lift them
        when flush."""
        actionlog.event(
            "bot", "plan_mortgage", player=player.name, cash=player.cash,
            deeds=len(ledger.deeds),
        )
        if player.cash < MORTGAGE_THRESHOLD:
            # Mortgage the lowest-value (cheapest) deeds first.
            for deed in sorted(ledger.deeds, key=lambda d: d.mortgage_value):
                if ledger.can_mortgage(deed) and player.cash < MORTGAGE_THRESHOLD:
                    ledger.mortgage(deed)
        elif player.cash > UNMORTGAGE_THRESHOLD:
            # Lift mortgages starting from the most valuable.
            for deed in sorted(ledger.deeds, key=lambda d: -d.mortgage_value):
                if ledger.can_unmortgage(deed):
                    ledger.unmortgage(deed)

    # ------------------------------------------------------------------ actions

    def choose_action(self, game, actions) -> Action:
        """Pick which :class:`~monopoly.game.Action` the bot performs this step."""
        player = game.current
        chosen = self._pick_action(game, actions, player)
        actionlog.event(
            "bot", "choose_action", player=player.name, what=chosen.value,
            cash=player.cash,
            available=",".join(sorted(a.value for a in actions)) or "(none)",
        )
        return chosen

    def _pick_action(self, game, actions, player) -> Action:
        """The decision itself; :meth:`choose_action` logs what comes back."""
        # Always roll when that is the only option.
        if Action.ROLL in actions:
            return Action.ROLL

        # In PLAYER_ACTIONS, decide whether to build, mortgage or end the turn.
        if Action.BUILD in actions and self._should_build(player):
            return Action.BUILD

        if Action.MORTGAGE in actions and self._should_mortgage(player):
            return Action.MORTGAGE

        # Trades are complex; bots skip them for now.
        return Action.END_TURN

    def _should_build(self, player) -> bool:
        """True when the bot has enough cash to usefully build."""
        reserve = max(300, int(player.cash * BUILD_RESERVE_FRACTION))
        return player.cash > reserve + 50  # at least one house budget

    def _should_mortgage(self, player) -> bool:
        """True when the bot is low enough on cash that mortgaging helps."""
        return player.cash < MORTGAGE_THRESHOLD
