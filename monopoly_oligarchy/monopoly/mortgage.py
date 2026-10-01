"""Phase 12: mortgaging and lifting a mortgage.

:class:`MortgageLedger` is the **draft** the mortgage screen edits, exactly as
:class:`~monopoly.building.BuildPlan` is the draft the build screen edits and
:class:`~monopoly.trade.Trade` the draft the trade screen edits. It imports no
pygame, so a whole round of mortgaging can be played out in a test without a
surface.

The draft matters here for the same reason it matters to a build plan, and for
one more besides:

* **Confirm is atomic.** Every flag flips and the money moves in one go, so a
  screenful of clicks either all happens or none of it does.
* **Cancel is free.** The draft is priced against the *board*, never against
  the clicks that got there, so mortgaging a lot and changing your mind is an
  undo rather than a $30 payout followed by a $33 bill. Only a mortgage that
  was really standing when the screen opened is ever lifted at 110%.
* **One side of the draft funds the other.** A player with $0 in hand can
  mortgage Baltic to lift the mortgage on Mediterranean in the same visit,
  because :meth:`MortgageLedger.can_unmortgage` asks whether the *running
  total* is covered rather than whether the cash is in hand right now.

The two rules the plan lays down:

* **Mortgaging needs a bare group.** No house or hotel may be standing on any
  lot of the deed's colour group -- the same rule a trade applies, and the
  same helper (:func:`monopoly.trade.group_is_bare`) is asked. Selling the
  buildings off first is the build screen's job (Phase 9), not this one's.
  Railroads and utilities carry no buildings, so they are always free to
  mortgage.
* **Lifting one costs 110%**, rounded up to the dollar. That is
  :attr:`monopoly.property.Property.unmortgage_cost`, and the bank wants it in
  cash: there is no mortgaging your way out of a mortgage you cannot afford.

A deed that arrives already mortgaged -- traded in (Phase 11) or inherited
from a bankruptcy (Phase 13) -- is listed like any other and may be lifted at
the same 110%, or left as it is. Left as it is, it earns its new owner nothing:
:meth:`monopoly.property.Property.current_rent` returns ``0`` for a mortgaged
deed whoever holds it.
"""

from __future__ import annotations

from typing import Optional, Sequence

from monopoly import actionlog
from monopoly.player import Player
from monopoly.property import Property
from monopoly.trade import group_is_bare

#: Why a row is dark, in the words the screen prints beside it.
BUILT_REASON = "buildings on the group"
CASH_REASON = "not enough cash"

#: What :func:`describe` calls a draft that changes nothing.
NO_CHANGES = "No changes."


def holdings(player: Player, properties: Sequence[Property]) -> list[Property]:
    """Every deed ``player`` owns, in board order, mortgageable or not.

    The screen lists all of them -- the plan asks for "all owned properties
    with status" -- and draws the ones that cannot move greyed out, so an
    owner can see *why* a lot is stuck rather than watch it go missing.
    """
    return sorted(
        (p for p in properties if p.owner is player), key=lambda p: p.index
    )


def mortgageable(
    player: Player, properties: Sequence[Property]
) -> list[Property]:
    """The deeds ``player`` could mortgage right now, in board order."""
    return [
        deed
        for deed in holdings(player, properties)
        if not deed.mortgaged and group_is_bare(deed, properties)
    ]


def liftable(player: Player, properties: Sequence[Property]) -> list[Property]:
    """The mortgages ``player`` could afford to lift right now, board order."""
    return [
        deed
        for deed in holdings(player, properties)
        if deed.mortgaged and player.cash >= deed.unmortgage_cost
    ]


def has_business(player: Player, properties: Sequence[Property]) -> bool:
    """Whether ``player`` has anything at all to do on the mortgage screen.

    This is what lights the Mortgage button, and it is deliberately the same
    shape as :func:`monopoly.building.buildable_groups`: a button that opens a
    screen with nothing on it should not be live. Owning deeds is not enough
    -- a table whose every lot is behind houses, or whose every mortgage is
    out of reach, leaves nothing to click.
    """
    return bool(
        mortgageable(player, properties) or liftable(player, properties)
    )


class MortgageLedger:
    """A draft set of mortgage changes for one player, applied all at once.

    Built from the board as it stands, edited with :meth:`mortgage` /
    :meth:`unmortgage` / :meth:`toggle`, then either thrown away or handed to
    :meth:`commit`. :attr:`cost` is what the player *would* pay -- negative
    when the draft pays out, which is the usual direction.
    """

    def __init__(self, player: Player, properties: Sequence[Property]) -> None:
        self.player = player
        self.properties = list(properties)
        #: Every deed the player owns, in board order.
        self.deeds = holdings(player, self.properties)
        self.states: dict[Property, bool] = {}
        self.reset()
        actionlog.event(
            "mortgage", "open", player=player.name, cash=player.cash,
            deeds=len(self.deeds),
            held=", ".join(actionlog.deed_state(d) for d in self.deeds)
            or "(none)",
        )

    # --- the draft ----------------------------------------------------------
    def reset(self) -> None:
        """Throw the draft away and start again from the board as it is."""
        self.states = {deed: deed.mortgaged for deed in self.deeds}

    @property
    def is_empty(self) -> bool:
        """Whether the player holds no deeds at all."""
        return not self.deeds

    @property
    def changed(self) -> bool:
        """Whether the draft differs from the flags on the board."""
        return any(state != deed.mortgaged for deed, state in self.states.items())

    def state(self, deed: Property) -> bool:
        """The draft's mortgage flag for ``deed``."""
        return self.states.get(deed, deed.mortgaged)

    # --- price --------------------------------------------------------------
    @property
    def cost(self) -> int:
        """What committing the draft would cost; negative when it pays out.

        Priced against the board, so a deed the draft mortgaged and then
        lifted again contributes nothing.
        """
        return sum(_deed_cost(deed, state) for deed, state in self.states.items())

    def _cost_if(self, deed: Property, state: bool) -> int:
        """What the draft would cost with ``deed`` left at ``state``."""
        return (
            self.cost
            - _deed_cost(deed, self.states[deed])
            + _deed_cost(deed, state)
        )

    @property
    def charge(self) -> int:
        """Cash the player owes (``0`` when the draft pays out)."""
        return max(0, self.cost)

    @property
    def refund(self) -> int:
        """Cash coming back to the player (``0`` when the draft costs money)."""
        return max(0, -self.cost)

    @property
    def proceeds(self) -> int:
        """Everything the bank hands over, before anything is paid back."""
        return sum(
            deed.mortgage_value
            for deed, state in self.states.items()
            if state and not deed.mortgaged
        )

    @property
    def interest(self) -> int:
        """Everything the bank is owed for the mortgages the draft lifts."""
        return sum(
            deed.unmortgage_cost
            for deed, state in self.states.items()
            if deed.mortgaged and not state
        )

    # --- editing ------------------------------------------------------------
    def can_mortgage(self, deed: Property) -> bool:
        """Whether ``deed`` may be mortgaged right now.

        No cash question is asked: mortgaging only ever pays money *in*, so it
        can never push the draft's total past what the player holds.
        """
        if self.states.get(deed, True):
            return False  # not ours, or already mortgaged in the draft
        return group_is_bare(deed, self.properties)

    def can_unmortgage(self, deed: Property) -> bool:
        """Whether ``deed``'s mortgage may be lifted right now.

        Priced against the running total, so a mortgage taken out earlier in
        the same draft lifts for nothing and a real one needs the 110% to be
        covered by what the player will be holding when Confirm is pressed.
        """
        if not self.states.get(deed, False):
            return False  # not ours, or not mortgaged in the draft
        return self._cost_if(deed, False) <= self.player.cash

    def can_toggle(self, deed: Property) -> bool:
        """Whether ``deed``'s row is live at all."""
        return self.can_mortgage(deed) or self.can_unmortgage(deed)

    def blocker(self, deed: Property) -> Optional[str]:
        """Why ``deed``'s row is dark, or ``None`` when it can be clicked."""
        if deed not in self.states:
            return None
        if self.states[deed]:
            return None if self.can_unmortgage(deed) else CASH_REASON
        return None if self.can_mortgage(deed) else BUILT_REASON

    def mortgage(self, deed: Property) -> bool:
        """Mortgage ``deed`` in the draft; ``False`` if that is not legal."""
        if not self.can_mortgage(deed):
            actionlog.debug(
                "mortgage", "take_refused", player=self.player.name,
                deed=deed.name, reason=self.blocker(deed) or "not held",
            )
            return False
        self.states[deed] = True
        actionlog.debug(
            "mortgage", "draft_take", player=self.player.name, deed=deed.name,
            raises=deed.mortgage_value, cost=self.cost,
        )
        return True

    def unmortgage(self, deed: Property) -> bool:
        """Lift ``deed``'s mortgage in the draft; ``False`` if not legal."""
        if not self.can_unmortgage(deed):
            actionlog.debug(
                "mortgage", "lift_refused", player=self.player.name,
                deed=deed.name, reason=self.blocker(deed) or "not mortgaged",
            )
            return False
        self.states[deed] = False
        actionlog.debug(
            "mortgage", "draft_lift", player=self.player.name, deed=deed.name,
            costs=deed.unmortgage_cost, cost=self.cost,
        )
        return True

    def toggle(self, deed: Property) -> bool:
        """Flip ``deed`` either way; ``False`` if neither way is legal."""
        if self.states.get(deed, False):
            return self.unmortgage(deed)
        return self.mortgage(deed)

    # --- committing ---------------------------------------------------------
    def commit(self) -> bool:
        """Apply the whole draft at once: every flag and the money together.

        ``False`` -- and nothing changes -- when there is nothing to do or the
        cash has gone since the draft was made. Neither is reachable from the
        mortgage screen, which only offers a click it has already priced.
        """
        if not self.changed:
            actionlog.debug(
                "mortgage", "commit_noop", player=self.player.name,
                reason="nothing changed",
            )
            return False
        # Read the price once: applying the draft is what makes it zero.
        charge, refund = self.charge, self.refund
        if charge and not self.player.can_pay(charge):
            actionlog.warn(
                "mortgage", "commit_refused", player=self.player.name,
                charge=charge, cash=self.player.cash, reason="cash gone",
            )
            return False
        actionlog.event(
            "mortgage", "commit", player=self.player.name, charge=charge,
            refund=refund, cash_before=self.player.cash,
            taken=", ".join(d.name for d in taken(self)) or "(none)",
            lifted=", ".join(d.name for d in lifted(self)) or "(none)",
        )
        for deed, state in self.states.items():
            deed.mortgaged = state
        if charge:
            self.player.pay(charge)
        elif refund:
            self.player.receive(refund)
        return True


def _deed_cost(deed: Property, state: bool) -> int:
    """What leaving ``deed`` at ``state`` would cost; negative pays out."""
    if state == deed.mortgaged:
        return 0
    if state:
        return -deed.mortgage_value
    return deed.unmortgage_cost


def taken(ledger: MortgageLedger) -> list[Property]:
    """The deeds the draft mortgages, in board order."""
    return [
        deed
        for deed, state in ledger.states.items()
        if state and not deed.mortgaged
    ]


def lifted(ledger: MortgageLedger) -> list[Property]:
    """The deeds the draft frees, in board order."""
    return [
        deed
        for deed, state in ledger.states.items()
        if deed.mortgaged and not state
    ]


def describe(ledger: MortgageLedger) -> str:
    """A one-line account of what committing ``ledger`` would do."""
    if not ledger.changed:
        return NO_CHANGES
    parts = []
    names = [deed.name for deed in taken(ledger)]
    if names:
        parts.append(f"mortgage {', '.join(names)}")
    names = [deed.name for deed in lifted(ledger)]
    if names:
        parts.append(f"lift {', '.join(names)}")
    if ledger.charge:
        money = f"pay ${ledger.charge:,}"
    elif ledger.refund:
        money = f"receive ${ledger.refund:,}"
    else:
        money = "no money changes hands"
    return f"{', '.join(parts)} -- {money}."
