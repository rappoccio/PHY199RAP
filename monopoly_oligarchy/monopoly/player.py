"""Phase 2: the player.

``Player`` holds one participant's cash, token, board position and deeds, plus
the jail and doubles bookkeeping the turn loop (Phase 7/8) will drive.

Money handling is deliberately split in two so that later phases can keep the
forced-sale rules in one place:

* :meth:`Player.can_pay` / :meth:`Player.pay` look at **cash only**. ``pay``
  refuses -- and leaves the balance untouched -- when the cash is not there.
* :meth:`Player.can_raise` asks the wider question ("could this debt be met
  after selling every building and mortgaging every deed?"). A ``False`` from
  it is what will mean bankruptcy in Phase 13; a ``True`` means the player must
  be made to liquidate first.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from monopoly import actionlog
from monopoly.property import Property


@dataclass(eq=False)
class Player:
    """One player. Instances compare by identity, like :class:`Property`."""

    name: str
    cash: int
    token_color: str
    position: int = 0
    properties: list[Property] = field(default_factory=list, repr=False)
    goojf_cards: int = 0
    in_jail: bool = False
    jail_turns: int = 0
    is_bankrupt: bool = False
    doubles_streak: int = 0
    is_bot: bool = False

    # --- money --------------------------------------------------------------
    def can_pay(self, amount: int) -> bool:
        """Whether ``amount`` is covered by cash in hand alone."""
        _check_amount(amount)
        return self.cash >= amount

    def pay(self, amount: int) -> bool:
        """Deduct ``amount`` if the cash is there.

        Returns ``False`` without touching the balance when it is not, leaving
        the caller to run the liquidation / bankruptcy path.
        """
        _check_amount(amount)
        if self.cash < amount:
            actionlog.debug(
                "cash", "pay_refused", player=self.name, amount=amount,
                cash=self.cash,
            )
            return False
        before = self.cash
        self.cash -= amount
        actionlog.debug(
            "cash", "pay", player=self.name, amount=amount,
            before=before, after=self.cash,
        )
        return True

    def receive(self, amount: int) -> None:
        """Credit ``amount`` to the player."""
        _check_amount(amount)
        before = self.cash
        self.cash += amount
        actionlog.debug(
            "cash", "receive", player=self.name, amount=amount,
            before=before, after=self.cash,
        )

    def can_raise(self, amount: int) -> bool:
        """Whether ``amount`` is reachable after full liquidation."""
        _check_amount(amount)
        return self.liquidation_value() >= amount

    def liquidation_value(self) -> int:
        """Cash plus every dollar the bank would pay to strip the player bare.

        That is: sell all buildings back at half price, then mortgage every
        unmortgaged deed. Already-mortgaged deeds raise nothing.
        """
        total = self.cash
        for prop in self.properties:
            total += prop.building_sale_value
            if not prop.mortgaged:
                total += prop.mortgage_value
        return total

    def net_worth(self) -> int:
        """Cash plus deed and building value, for tiebreaks and the HUD.

        Deeds count at face price, or at their mortgage value while mortgaged;
        buildings count at what was paid for them.
        """
        total = self.cash
        for prop in self.properties:
            total += prop.mortgage_value if prop.mortgaged else prop.price
            total += prop.buildings_value
        return total

    # --- deeds --------------------------------------------------------------
    def add_property(self, prop: Property) -> None:
        """Take ownership of ``prop``, detaching it from any previous owner."""
        if prop.owner is self:
            return
        previous = prop.owner
        if previous is not None:
            previous.remove_property(prop)
        prop.owner = self
        self.properties.append(prop)
        actionlog.event(
            "deed", "acquired", deed=prop.name, to=self.name,
            **({"frm": previous.name} if previous is not None else {}),
            level=prop.building_level, mortgaged=prop.mortgaged,
        )

    def remove_property(self, prop: Property) -> None:
        """Give up ``prop``. The deed is left ownerless."""
        for i, held in enumerate(self.properties):
            if held is prop:
                del self.properties[i]
                break
        else:
            actionlog.warn(
                "deed", "remove_missing", deed=prop.name, player=self.name,
                trace=actionlog.where(),
            )
            raise ValueError(f"{self.name} does not hold {prop.name}")
        prop.owner = None
        actionlog.debug(
            "deed", "released", deed=prop.name, frm=self.name,
            level=prop.building_level,
        )

    def owned_in_group(
        self, group: str, all_properties: Iterable[Property]
    ) -> list[Property]:
        """The deeds of ``group`` this player owns, in board order."""
        return sorted(
            (p for p in all_properties if p.group == group and p.owner is self),
            key=lambda p: p.index,
        )

    def has_monopoly(self, group: str, all_properties: Sequence[Property]) -> bool:
        """Whether this player holds every deed in ``group``.

        Mortgage status is ignored: a mortgaged lot still belongs to the group.
        """
        in_group = [p for p in all_properties if p.group == group]
        if not in_group or len(in_group) != in_group[0].group_size:
            return False
        return all(p.owner is self for p in in_group)

    def monopolies(self, all_properties: Sequence[Property]) -> list[str]:
        """Every group key this player holds completely, in board order."""
        seen: list[str] = []
        for prop in sorted(all_properties, key=lambda p: p.index):
            if prop.group not in seen and self.has_monopoly(prop.group, all_properties):
                seen.append(prop.group)
        return seen


def _check_amount(amount: int) -> None:
    if amount < 0:
        raise ValueError(f"amount must not be negative, got {amount}")
