"""Phase 10: the auction.

When a player lands on an unowned deed and declines to buy it, the bank puts
it up for auction. :class:`Auction` is that sale, and -- like
:mod:`monopoly.game`, :mod:`monopoly.dice` and :mod:`monopoly.building` -- it
imports no pygame, so a whole auction can be run in a test without a surface.

The rules it holds to:

* **Everyone bids**, including the player who declined. The turn opens on that
  player and goes round the table in seat order; bankrupt players are not in
  the room at all.
* **The opening bid is $1**, and every later bid must beat the standing one by
  at least the increment. A player can never bid more cash than they hold --
  there is no borrowing against deeds here, so the winner can always pay.
* **Passing is final.** A bidder who drops out does not get another turn, and
  the sale ends when nobody is left to answer the standing bid.
* **A bidder who cannot reach the next bid drops out automatically.** Nothing
  is asked of a player with $0 in an auction whose price has already passed
  them; without this the round could never come back to a full table.
* **If everybody passes without a bid the deed stays unowned** -- exactly as
  it was before the sale.

Money and deeds do not move here. :class:`Auction` says who won and at what
price; :meth:`monopoly.game.Game._settle_auction` is what charges the winner
and hands over the deed, the same way :class:`~monopoly.building.BuildPlan`
leaves the board alone until it is committed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from monopoly import actionlog
from monopoly.player import Player
from monopoly.property import Property

#: The lowest opening bid, and the least a new bid must beat the standing one
#: by. Both are the standard $1.
MIN_BID = 1
BID_INCREMENT = 1


@dataclass(frozen=True)
class Bid:
    """One accepted bid, kept in :attr:`Auction.history` in order."""

    player: Player
    amount: int


class Auction:
    """One deed under the hammer.

    The caller drives it with :meth:`bid` and :meth:`withdraw`, both of which
    act for :attr:`bidder` -- whoever the round is waiting on. When
    :attr:`finished` goes true the sale is over and :attr:`winner` /
    :attr:`price` say how it ended; ``winner`` is ``None`` when nobody bid.
    """

    def __init__(
        self,
        deed: Property,
        bidders: Sequence[Player],
        *,
        minimum: int = MIN_BID,
        increment: int = BID_INCREMENT,
    ) -> None:
        if minimum < 1:
            raise ValueError(f"the opening bid must be at least $1, got {minimum}")
        if increment < 1:
            raise ValueError(f"the increment must be at least $1, got {increment}")
        seats = [p for p in bidders if not p.is_bankrupt]
        if not seats:
            raise ValueError("an auction needs at least one bidder")
        self.deed = deed
        #: Everyone in the room, in the order they are asked.
        self.bidders: list[Player] = seats
        self.minimum = minimum
        self.increment = increment

        self.high_bid = 0
        self.high_bidder: Optional[Player] = None
        #: Who has dropped out, in the order they did.
        self.passed: list[Player] = []
        self.history: list[Bid] = []
        #: A plain-language transcript, for the screen and the game's log.
        self.log: list[str] = []
        self.finished = False
        self.winner: Optional[Player] = None

        self._turn = 0
        # Nobody may be able to afford even $1, in which case the sale is
        # over before it starts.
        self._advance(step=False)

    # --- where the round stands ---------------------------------------------
    @property
    def bidder(self) -> Optional[Player]:
        """Whoever the round is waiting on, or ``None`` once it is over."""
        if self.finished:
            return None
        return self.bidders[self._turn]

    @property
    def remaining(self) -> list[Player]:
        """Everyone who has not dropped out, in seat order."""
        return [p for p in self.bidders if not self.has_passed(p)]

    @property
    def min_bid(self) -> int:
        """The least a bid would have to be to be accepted right now."""
        if self.high_bidder is None:
            return self.minimum
        return self.high_bid + self.increment

    @property
    def price(self) -> int:
        """What the winner owes (``0`` when the deed went unsold)."""
        return self.high_bid if self.winner is not None else 0

    @property
    def sold(self) -> bool:
        """Whether the sale ended with a buyer."""
        return self.winner is not None

    def has_passed(self, player: Player) -> bool:
        """Whether ``player`` has dropped out of this sale."""
        return any(p is player for p in self.passed)

    def can_afford(self, player: Player) -> bool:
        """Whether ``player`` holds the cash for the next legal bid."""
        return player.cash >= self.min_bid

    def can_bid(self, amount: int, player: Optional[Player] = None) -> bool:
        """Whether ``amount`` would be accepted from ``player`` right now.

        ``player`` defaults to whoever the round is waiting on, which is the
        only one who may bid at all.
        """
        if self.finished:
            return False
        player = self.bidder if player is None else player
        if player is None or player is not self.bidder:
            return False
        return self.min_bid <= amount <= player.cash

    # --- driving it ---------------------------------------------------------
    def bid(self, amount: int) -> bool:
        """Take ``amount`` from the current bidder; ``False`` if it is illegal.

        An illegal bid changes nothing at all -- the round is still waiting on
        the same player, who may try again with a number they can make good.
        """
        if not self.can_bid(amount):
            bidder = self.bidder
            actionlog.debug(
                "auction", "bid_refused", deed=self.deed.name,
                bidder=getattr(bidder, "name", "-"), amount=amount,
                min_bid=self.min_bid,
                cash=getattr(bidder, "cash", None),
            )
            return False
        player = self.bidder
        assert player is not None
        self.high_bid = amount
        self.high_bidder = player
        self.history.append(Bid(player, amount))
        self._note(f"{player.name} bids ${amount:,}.")
        actionlog.event(
            "auction", "bid", deed=self.deed.name, bidder=player.name,
            amount=amount, cash=player.cash,
        )
        self._advance()
        return True

    def withdraw(self) -> bool:
        """Drop the current bidder out of the sale for good."""
        player = self.bidder
        if player is None:
            return False
        actionlog.event(
            "auction", "pass", deed=self.deed.name, bidder=player.name,
            high_bid=self.high_bid,
        )
        self._drop(player, f"{player.name} passes.")
        self._advance()
        return True

    # --- the round ----------------------------------------------------------
    def _advance(self, step: bool = True) -> None:
        """Hand the turn on, dropping anyone who cannot reach the price.

        ``step=False`` opens the round on the first seat instead of moving off
        the current one.
        """
        if step:
            self._step()
        # Each pass through either ends the sale or removes somebody, so the
        # bound is generous rather than load-bearing.
        for _ in range(2 * len(self.bidders) + 2):
            if self._finish_if_over():
                return
            player = self.bidders[self._turn]
            if self.has_passed(player):
                self._step()
                continue
            if not self.can_afford(player):
                self._drop(
                    player,
                    f"{player.name} cannot reach ${self.min_bid:,} and drops out.",
                )
                self._step()
                continue
            return
        raise RuntimeError("the auction could not find a bidder or an end")

    def _step(self) -> None:
        self._turn = (self._turn + 1) % len(self.bidders)

    def _drop(self, player: Player, note: str) -> None:
        if not self.has_passed(player):
            self.passed.append(player)
            self._note(note)

    def _finish_if_over(self) -> bool:
        """Close the sale if there is nobody left to answer the standing bid."""
        if self.finished:
            return True
        live = self.remaining
        if live and (len(live) > 1 or self.high_bidder is None):
            return False
        self.finished = True
        self.winner = self.high_bidder
        actionlog.event(
            "auction", "finished", deed=self.deed.name,
            winner=self.winner.name if self.winner is not None else "(nobody)",
            price=self.high_bid if self.winner is not None else 0,
        )
        if self.winner is not None:
            self._note(
                f"{self.winner.name} takes {self.deed.name} "
                f"for ${self.high_bid:,}."
            )
        else:
            self._note(f"Nobody bid; {self.deed.name} stays unowned.")
        return True

    def _note(self, text: str) -> None:
        self.log.append(text)

    @property
    def last_note(self) -> str:
        """The most recent transcript line (``""`` before there is one)."""
        return self.log[-1] if self.log else ""


def summarise(auction: Auction) -> str:
    """A one-line account of where an auction stands, for the screen."""
    if auction.finished:
        if auction.winner is None:
            return f"No bids -- {auction.deed.name} stays with the bank."
        return f"Sold to {auction.winner.name} for ${auction.price:,}."
    if auction.high_bidder is None:
        return f"No bids yet -- opening at ${auction.min_bid:,}."
    return (
        f"High bid ${auction.high_bid:,} ({auction.high_bidder.name}) -- "
        f"next ${auction.min_bid:,}."
    )
