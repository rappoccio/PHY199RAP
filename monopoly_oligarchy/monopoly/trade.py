"""Phase 11: the trade.

:class:`Trade` is one deal between the player on turn and one other player. It
imports no pygame -- like :mod:`monopoly.game`, :mod:`monopoly.building` and
:mod:`monopoly.auction` -- so a whole negotiation can be struck in a test
without a surface.

A trade moves through four phases, which are exactly the four things the
screen shows::

    PARTNER -> DRAFT -> REVIEW -> CLOSED

* **PARTNER**: who is this deal with? A table with only one other player left
  skips this, because there is nothing to choose.
* **DRAFT**: the proposer fills in both columns -- cash, deeds and Get Out of
  Jail Free cards on either side. Editing is only possible here.
* **REVIEW**: the offer is on the table and the partner answers it. The two
  columns are now read-only; the only moves left are Accept and Reject.
* **CLOSED**: it is over, and :attr:`Trade.result` says how -- :data:`ACCEPTED`,
  :data:`REJECTED` or :data:`CANCELLED`.

Like :class:`~monopoly.building.BuildPlan` the offer is a **draft**: nothing
moves until :meth:`Trade.accept`, and then the deeds, the cash and the cards
all move together. And like the build plan, every rule is asked of the draft
rather than left for the swap to discover:

* **You can only put up what you hold.** A deed's owner decides which column
  it can go in, cash is capped at the cash in hand, and a jail card at the
  cards in hand.
* **A deed carrying buildings cannot be traded**, and neither can its
  group-mates: the standard rule is that every building in a colour group goes
  back to the bank before any lot of it changes hands. Selling them is the
  build screen's job (Phase 9), not this one's.
* **A mortgaged deed trades freely**, still mortgaged. The new owner collects
  no rent on it until they lift the mortgage, which is Phase 12's business.
* **Something has to be on the table.** An empty offer cannot be proposed.

The one thing a trade cannot do alone is move a Get Out of Jail Free card:
:class:`~monopoly.player.Player` only counts them, while
:class:`monopoly.game.Game` knows which deck each one came from. So the game
hands its :meth:`~monopoly.game.Game.transfer_goojf` in as ``on_goojf`` and
the card goes back under the right deck when it is eventually played.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from monopoly import actionlog
from monopoly.player import Player
from monopoly.property import Property

#: The four phases of a deal, in the order they happen.
PARTNER = "partner"
DRAFT = "draft"
REVIEW = "review"
CLOSED = "closed"

#: How a closed deal ended.
ACCEPTED = "accepted"
REJECTED = "rejected"
CANCELLED = "cancelled"

#: What a side offering nothing is called, in the transcript and on screen.
NOTHING = "nothing"


@dataclass
class Offer:
    """One side of a deal: what this player is putting up.

    Nothing here is checked -- :class:`Trade` is what refuses an illegal edit
    -- so an ``Offer`` is only ever as good as the trade that owns it.
    """

    player: Player
    cash: int = 0
    goojf: int = 0
    deeds: list[Property] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        """Whether this side is giving up nothing at all."""
        return not self.cash and not self.goojf and not self.deeds

    def holds(self, deed: Property) -> bool:
        """Whether ``deed`` is on this side of the table."""
        return any(d is deed for d in self.deeds)


class Trade:
    """One deal between two players, drafted, proposed and then settled."""

    def __init__(
        self,
        proposer: Player,
        candidates: Sequence[Player],
        properties: Sequence[Property],
        *,
        partner: Optional[Player] = None,
        on_goojf: Optional[Callable[[Player, Player, int], None]] = None,
    ) -> None:
        seats = [p for p in candidates if p is not proposer and not p.is_bankrupt]
        if not seats:
            raise ValueError("a trade needs somebody to trade with")
        self.proposer = proposer
        #: Everyone the proposer could deal with, in seat order.
        self.candidates: list[Player] = seats
        self.properties = list(properties)
        self.on_goojf = on_goojf

        self.phase = PARTNER
        self.result: Optional[str] = None
        self.mine = Offer(proposer)
        self.theirs: Optional[Offer] = None

        # One other player left at the table is not a choice; take it.
        if partner is None and len(seats) == 1:
            partner = seats[0]
        if partner is not None:
            self.choose_partner(partner)

    # --- where the deal stands ----------------------------------------------
    @property
    def partner(self) -> Optional[Player]:
        """Who the deal is with, or ``None`` before one is chosen."""
        return self.theirs.player if self.theirs is not None else None

    @property
    def open(self) -> bool:
        """Whether the deal is still live."""
        return self.phase != CLOSED

    @property
    def editable(self) -> bool:
        """Whether the two columns may still be changed."""
        return self.phase == DRAFT

    @property
    def sides(self) -> list[Offer]:
        """Both columns, proposer first (just the one before a partner)."""
        return [self.mine] if self.theirs is None else [self.mine, self.theirs]

    def offer(self, player: Player) -> Offer:
        """The column belonging to ``player``; raises for anybody else."""
        for side in self.sides:
            if side.player is player:
                return side
        raise ValueError(f"{player.name} is not part of this trade")

    def side_of(self, deed: Property) -> Optional[Offer]:
        """The column ``deed`` would go in, or ``None`` if it cannot be traded."""
        for side in self.sides:
            if deed.owner is side.player:
                return side
        return None

    # --- choosing a partner -------------------------------------------------
    def choose_partner(self, player: Player) -> bool:
        """Settle who the deal is with; ``False`` if that is not on offer.

        Only possible before the drafting starts -- re-opening the question
        would mean silently dropping half of an offer already typed in.
        """
        if self.phase != PARTNER:
            return False
        if not any(p is player for p in self.candidates):
            return False
        self.theirs = Offer(player)
        self.phase = DRAFT
        return True

    # --- editing the draft --------------------------------------------------
    def holdings(self, player: Player) -> list[Property]:
        """Every deed ``player`` owns, in board order, tradable or not.

        The screen lists all of them and draws the ones :meth:`can_offer`
        refuses greyed out, so a player can see *why* a lot is not on offer
        rather than watch it go missing.
        """
        return sorted(
            (p for p in self.properties if p.owner is player),
            key=lambda p: p.index,
        )

    def tradable(self, player: Player) -> list[Property]:
        """The deeds ``player`` could put up, in board order.

        Everything they own, less any lot whose colour group still has a
        building standing on it.
        """
        return sorted(
            (
                p
                for p in self.properties
                if p.owner is player and group_is_bare(p, self.properties)
            ),
            key=lambda p: p.index,
        )

    def can_offer(self, deed: Property) -> bool:
        """Whether ``deed`` may be put on (or taken off) the table right now."""
        if not self.editable:
            return False
        side = self.side_of(deed)
        if side is None:
            return False
        return group_is_bare(deed, self.properties)

    def is_offered(self, deed: Property) -> bool:
        """Whether ``deed`` is on the table, on either side."""
        return any(side.holds(deed) for side in self.sides)

    def add_deed(self, deed: Property) -> bool:
        """Put ``deed`` up; ``False`` if it cannot be, or already is."""
        if not self.can_offer(deed) or self.is_offered(deed):
            return False
        side = self.side_of(deed)
        assert side is not None
        side.deeds.append(deed)
        side.deeds.sort(key=lambda p: p.index)
        return True

    def remove_deed(self, deed: Property) -> bool:
        """Take ``deed`` back off the table; ``False`` if it was not on it."""
        if not self.editable:
            return False
        for side in self.sides:
            for i, held in enumerate(side.deeds):
                if held is deed:
                    del side.deeds[i]
                    return True
        return False

    def toggle(self, deed: Property) -> bool:
        """Flip ``deed`` on or off the table; ``False`` if neither is legal."""
        if self.is_offered(deed):
            return self.remove_deed(deed)
        return self.add_deed(deed)

    def set_cash(self, player: Player, amount: int) -> bool:
        """Offer ``amount`` from ``player``; ``False`` if they cannot cover it."""
        if not self.editable:
            return False
        side = self.offer(player)
        if amount < 0 or amount > player.cash:
            return False
        side.cash = amount
        return True

    def set_goojf(self, player: Player, count: int) -> bool:
        """Offer ``count`` jail cards from ``player``; ``False`` if they lack them."""
        if not self.editable:
            return False
        side = self.offer(player)
        if count < 0 or count > player.goojf_cards:
            return False
        side.goojf = count
        return True

    # --- is it a deal at all? -----------------------------------------------
    @property
    def is_empty(self) -> bool:
        """Whether nothing whatever is on the table."""
        return all(side.is_empty for side in self.sides)

    def problems(self) -> list[str]:
        """Every reason this offer could not be settled, in plain language.

        Empty means it is good to go. The editing methods already refuse each
        of these, so the list is a second pair of eyes rather than the first:
        it is what makes :meth:`accept` unable to half-finish.
        """
        notes: list[str] = []
        if self.theirs is None:
            notes.append("Choose somebody to trade with.")
            return notes
        if self.is_empty:
            notes.append("Nothing is on the table.")
        for side in self.sides:
            player = side.player
            if side.cash > player.cash:
                notes.append(f"{player.name} has only ${player.cash:,}.")
            if side.goojf > player.goojf_cards:
                notes.append(
                    f"{player.name} holds {player.goojf_cards} jail card(s)."
                )
            for deed in side.deeds:
                if deed.owner is not player:
                    notes.append(f"{player.name} no longer owns {deed.name}.")
                elif not group_is_bare(deed, self.properties):
                    notes.append(f"{deed.name} still has buildings on its group.")
        return notes

    @property
    def is_valid(self) -> bool:
        """Whether the offer as it stands could be proposed and settled."""
        return not self.problems()

    # --- closing it ---------------------------------------------------------
    def propose(self) -> bool:
        """Put the offer to the partner; ``False`` if it is not a legal one."""
        if self.phase != DRAFT or not self.is_valid:
            actionlog.debug(
                "trade", "propose_refused", proposer=self.proposer.name,
                phase=self.phase, problems="; ".join(self.problems()) or "-",
            )
            return False
        self.phase = REVIEW
        actionlog.event(
            "trade", "proposed", proposer=self.proposer.name,
            partner=getattr(self.theirs.player, "name", "-"),
            gives=summarise_offer(self.mine),
            gets=summarise_offer(self.theirs),
        )
        return True

    def accept(self) -> bool:
        """Settle the deal: deeds, cash and cards all move at once.

        ``False`` -- and nothing moves -- from any phase but :data:`REVIEW`, or
        if the board has changed under the offer since it was proposed.
        """
        if self.phase != REVIEW or not self.is_valid:
            actionlog.warn(
                "trade", "accept_refused", proposer=self.proposer.name,
                phase=self.phase, problems="; ".join(self.problems()) or "-",
            )
            return False
        mine, theirs = self.mine, self.theirs
        assert theirs is not None
        actionlog.event(
            "trade", "accept", proposer=mine.player.name,
            partner=theirs.player.name,
            gives=summarise_offer(mine), gets=summarise_offer(theirs),
            deeds_given=", ".join(actionlog.deed_state(d) for d in mine.deeds)
            or "(none)",
            deeds_taken=", ".join(actionlog.deed_state(d) for d in theirs.deeds)
            or "(none)",
            trace=actionlog.where(),
        )

        for deed in list(mine.deeds):
            theirs.player.add_property(deed)
        for deed in list(theirs.deeds):
            mine.player.add_property(deed)

        net = mine.cash - theirs.cash
        if net > 0:
            mine.player.pay(net)
            theirs.player.receive(net)
        elif net < 0:
            theirs.player.pay(-net)
            mine.player.receive(-net)

        if mine.goojf:
            self._move_goojf(mine.player, theirs.player, mine.goojf)
        if theirs.goojf:
            self._move_goojf(theirs.player, mine.player, theirs.goojf)

        self._close(ACCEPTED)
        return True

    def reject(self) -> bool:
        """The partner turns the offer down."""
        if self.phase != REVIEW:
            return False
        self._close(REJECTED)
        return True

    def cancel(self) -> bool:
        """The proposer walks away, from any phase before it is settled."""
        if self.phase == CLOSED:
            return False
        self._close(CANCELLED)
        return True

    def _close(self, result: str) -> None:
        self.phase = CLOSED
        self.result = result
        actionlog.event(
            "trade", "closed", result=result, proposer=self.proposer.name,
            partner=getattr(self.theirs.player, "name", None)
            if self.theirs is not None
            else None,
        )

    def _move_goojf(self, giver: Player, taker: Player, count: int) -> None:
        """Hand ``count`` jail cards over, through the game's own bookkeeping."""
        actionlog.event(
            "trade", "goojf", frm=giver.name, to=taker.name, count=count
        )
        if self.on_goojf is not None:
            self.on_goojf(giver, taker, count)
            return
        giver.goojf_cards -= count
        taker.goojf_cards += count


def group_is_bare(deed: Property, properties: Sequence[Property]) -> bool:
    """Whether ``deed``'s colour group carries no buildings at all.

    Railroads and utilities are always bare: nothing is ever built on them,
    whoever holds them all.
    """
    if not deed.is_property:
        return True
    return all(
        p.building_level == 0 for p in properties if p.group == deed.group
    )


def summarise_offer(offer: Optional[Offer]) -> str:
    """One side of the table in words: ``"Baltic Avenue, $50, 1 jail card"``."""
    if offer is None or offer.is_empty:
        return NOTHING
    parts = [deed.name for deed in offer.deeds]
    if offer.cash:
        parts.append(f"${offer.cash:,}")
    if offer.goojf:
        parts.append(
            f"{offer.goojf} jail card" + ("s" if offer.goojf != 1 else "")
        )
    return ", ".join(parts)


def describe(trade: Trade) -> str:
    """A one-line account of the deal on the table, for the log and the screen."""
    if trade.theirs is None:
        return f"{trade.proposer.name} is looking for a trade."
    return (
        f"{trade.proposer.name} gives {summarise_offer(trade.mine)}; "
        f"{trade.partner.name} gives {summarise_offer(trade.theirs)}."
    )
