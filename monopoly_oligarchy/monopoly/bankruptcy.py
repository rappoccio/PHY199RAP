"""Phase 13: the forced sale, and the end of a player's game.

Like :mod:`monopoly.game`, :mod:`monopoly.building`, :mod:`monopoly.auction`
and :mod:`monopoly.trade`, nothing here imports pygame: a player can be wound
up in a test without a surface.

Two different things happen when a debt outruns the cash in hand, and this
module is both of them:

* **The forced sale.** :func:`raise_cash` is what a player who *could* have
  paid is made to do -- sell every building back to the bank at half price,
  then mortgage deeds, in board order, until the debt is covered. It stops the
  moment the money is there, so a $10 shortfall does not mortgage the whole
  board.
* **The bankruptcy.** :func:`settle` is what happens when even that is not
  enough. The buildings still go back in the box and the cash they raise is
  still credited to the debtor -- the plan is explicit that a creditor is
  never handed a building -- and then everything the debtor has left changes
  hands at once.

Who the debt is owed to decides where it all goes:

* **To another player**: the cash, the deeds (as-is, mortgaged or not) and any
  Get Out of Jail Free cards go to the creditor.
* **To the bank**: the cash simply leaves the game, the deeds go back to being
  unowned -- and unmortgaged, because a deed on the bank's shelf is for sale
  at its list price -- and the jail cards go back under their decks.

The one thing that cannot be done from here is putting a Get Out of Jail Free
card back under the *right* deck: like a trade (Phase 11), only
:class:`monopoly.game.Game` remembers which deck each card came from, so it
hands its own mover in as ``on_goojf``.

Every function takes what it needs and touches nothing else -- no game, no
turn order, no win condition. Marking the player bankrupt is the one flag
:func:`settle` sets; taking them out of the turn order and deciding whether
anybody is left is the game's business.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from monopoly import actionlog
from monopoly.building import Bank
from monopoly.player import Player
from monopoly.property import Property

#: The signature :class:`monopoly.game.Game` hands in as ``on_goojf``:
#: ``(debtor, creditor_or_None, count) -> cards actually moved``.
GoojfMover = Callable[[Player, Optional[Player], int], int]


@dataclass(frozen=True)
class Settlement:
    """What one bankruptcy moved, for the log and for Phase 14's win screen.

    A frozen record of a thing that has already happened: reading it changes
    nothing, and it stays true after the board has moved on.
    """

    debtor: Player
    creditor: Optional[Player]
    #: What was owed and could not be met, after every forced sale.
    amount: int
    #: Cash handed over -- what the debtor had left once the buildings sold.
    cash: int
    #: Deeds that changed hands, in board order.
    deeds: tuple[Property, ...]
    #: Get Out of Jail Free cards that went with them.
    goojf: int
    #: What the bank paid back for the buildings, before the transfer.
    buildings: int

    @property
    def to_bank(self) -> bool:
        """Whether the debt was owed to the bank rather than to a player."""
        return self.creditor is None

    @property
    def value(self) -> int:
        """Everything the creditor (or the bank) took: cash plus deed value."""
        return self.cash + sum(
            d.mortgage_value if d.mortgaged else d.price for d in self.deeds
        )


# --- the forced sale --------------------------------------------------------
def sell_all_buildings(player: Player, bank: Bank) -> int:
    """Sell every building ``player`` owns back to the bank; returns the cash.

    All of them, in one go, which is why no even-selling rule applies and why
    a hotel needs no houses in the box to come down: the lot is not stepping
    back to four houses, it is being cleared. The pieces go back in the box
    exactly as they came out -- a hotel as one hotel, houses as houses.
    """
    raised = 0
    razed = []
    for deed in player.properties:
        if deed.building_level == 0:
            continue
        if deed.has_hotel:
            bank.hotels += 1
        else:
            bank.houses += deed.houses
        raised += deed.building_sale_value
        razed.append(f"{deed.name} {deed.building_level}->0")
        deed.has_hotel = False
        deed.houses = 0
    if razed:
        actionlog.event(
            "bankruptcy", "sell_all_buildings", player=player.name,
            raised=raised, razed="; ".join(razed),
            bank_after=f"{bank.houses}h/{bank.hotels}H",
            trace=actionlog.where(),
        )
    if raised:
        player.receive(raised)
    return raised


def mortgage(deed: Property) -> int:
    """Mortgage ``deed`` for its owner; returns the cash the bank pays.

    ``0`` when there is nothing to raise -- an ownerless or already-mortgaged
    deed. A deed still carrying buildings cannot be mortgaged at all, which is
    why :func:`raise_cash` sells every building first.
    """
    if deed.owner is None or deed.mortgaged:
        return 0
    if deed.houses or deed.has_hotel:
        actionlog.error(
            "bankruptcy", "mortgage_blocked", deed=deed.name,
            level=deed.building_level, owner=deed.owner.name,
            trace=actionlog.where(),
        )
        raise ValueError(f"{deed.name} still carries buildings")
    deed.mortgaged = True
    deed.owner.receive(deed.mortgage_value)
    actionlog.event(
        "bankruptcy", "forced_mortgage", deed=deed.name,
        owner=deed.owner.name, raised=deed.mortgage_value,
    )
    return deed.mortgage_value


def raise_cash(player: Player, target: int, bank: Bank) -> int:
    """Force sales until ``player`` holds ``target`` in cash; returns the cash raised.

    Buildings first (all of them), then deeds mortgaged one at a time in board
    order, stopping the moment the target is reached. Raising nothing is a
    perfectly ordinary answer: a player who already has the cash is not made
    to sell anything.

    The ceiling is :meth:`~monopoly.player.Player.liquidation_value`, and the
    two agree exactly -- so a target that method says is reachable is always
    reached.
    """
    if target < 0:
        raise ValueError(f"target must not be negative, got {target}")
    if player.cash >= target:
        return 0
    actionlog.event(
        "bankruptcy", "raise_cash", player=player.name, target=target,
        cash=player.cash, shortfall=target - player.cash,
        standing=actionlog.buildings_of(player),
        liquidation=player.liquidation_value(),
    )
    raised = sell_all_buildings(player, bank)
    for deed in sorted(player.properties, key=lambda d: d.index):
        if player.cash >= target:
            break
        raised += mortgage(deed)
    actionlog.event(
        "bankruptcy", "raise_cash_done", player=player.name, target=target,
        raised=raised, cash=player.cash, met=player.cash >= target,
    )
    return raised


# --- the bankruptcy ---------------------------------------------------------
def settle(
    debtor: Player,
    creditor: Optional[Player],
    amount: int,
    bank: Bank,
    *,
    on_goojf: Optional[GoojfMover] = None,
) -> Settlement:
    """Wind ``debtor`` up over an ``amount`` they cannot meet.

    Everything moves together, and afterwards the debtor holds nothing at all:
    no cash, no deeds, no jail cards, and ``is_bankrupt`` set. Their token
    stays where it fell -- the board simply stops drawing it.

    ``creditor`` of ``None`` means the debt was owed to the bank.
    """
    if debtor.is_bankrupt:
        raise ValueError(f"{debtor.name} is already bankrupt")
    if creditor is debtor:
        raise ValueError("a player cannot be their own creditor")
    if amount < 0:
        raise ValueError(f"amount must not be negative, got {amount}")

    actionlog.event(
        "bankruptcy", "settle", debtor=debtor.name,
        creditor=creditor.name if creditor is not None else "the bank",
        amount=amount, cash=debtor.cash, deeds=len(debtor.properties),
        goojf=debtor.goojf_cards, standing=actionlog.buildings_of(debtor),
        trace=actionlog.where(),
    )
    # The buildings come down first: the plan is explicit that a creditor
    # takes deeds, never houses, and the cash they raise is the debtor's.
    buildings = sell_all_buildings(debtor, bank)

    deeds = tuple(sorted(debtor.properties, key=lambda d: d.index))
    cash = debtor.cash
    cards = debtor.goojf_cards

    debtor.cash = 0
    if creditor is not None and cash:
        creditor.receive(cash)

    for deed in deeds:
        if creditor is not None:
            creditor.add_property(deed)  # detaches it from the debtor
        else:
            debtor.remove_property(deed)
            deed.mortgaged = False

    if cards:
        if on_goojf is not None:
            on_goojf(debtor, creditor, cards)
        else:
            debtor.goojf_cards = 0
            if creditor is not None:
                creditor.goojf_cards += cards

    debtor.is_bankrupt = True
    actionlog.event(
        "bankruptcy", "settled", debtor=debtor.name,
        creditor=creditor.name if creditor is not None else "the bank",
        cash=cash, buildings_sold_for=buildings, goojf=cards,
        deeds=", ".join(d.name for d in deeds) or "(none)",
    )
    return Settlement(
        debtor=debtor,
        creditor=creditor,
        amount=amount,
        cash=cash,
        deeds=deeds,
        goojf=cards,
        buildings=buildings,
    )


def describe(settlement: Settlement) -> str:
    """A one-line account of what a settlement moved, for the transcript."""
    parts = []
    if settlement.cash:
        parts.append(f"${settlement.cash:,}")
    if settlement.deeds:
        count = len(settlement.deeds)
        parts.append(f"{count} deed{'s' if count != 1 else ''}")
    if settlement.goojf:
        count = settlement.goojf
        parts.append(f"{count} jail card{'s' if count != 1 else ''}")
    haul = ", ".join(parts) if parts else "nothing"
    where = "the bank" if settlement.to_bank else settlement.creditor.name
    return f"{settlement.debtor.name} hands {haul} to {where}."
