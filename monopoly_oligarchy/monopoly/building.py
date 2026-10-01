"""Phase 9: houses, hotels and the bank's supply of them.

Two things live here, and neither imports pygame -- like :mod:`monopoly.game`
the building rules are plain Python, so a whole build can be planned and
committed in a test without a surface.

:class:`Bank` is the board's stock of buildings: 32 houses and 12 hotels, and
no more. Running the bank dry is a real part of the game -- a player holding
four houses on every lot of a group can block everyone else from building at
all -- so the supply is counted rather than assumed infinite.

:class:`BuildPlan` is the **draft** the build screen edits. Nothing it does
touches a deed, the bank or a wallet until :meth:`BuildPlan.commit`; up to
then it is a private set of +/- clicks that can be abandoned with
:meth:`BuildPlan.reset`. That is what makes the plan's "Confirm executes all
queued changes atomically" possible, and it is why every rule the screen has
to enforce -- even building, the supply, and the player's cash -- is asked of
the *draft* rather than of the board:

* **Even building.** A house may only go onto the lot of a group with the
  fewest buildings, and may only come off the lot with the most. Applied one
  click at a time that is the whole rule, including the hotel: a lot reaches
  four houses only once every lot has four, so the fifth payment (the hotel)
  can only be made when the group is full.
* **The supply.** Building a hotel hands four houses *back* to the bank and
  takes one hotel out. Selling one does the reverse -- which is why a hotel
  cannot be sold when fewer than four houses are left in the box: the lot
  would have nothing to stand on.
* **Cash.** A lot can only be improved while the plan's running total is still
  covered by the player's cash, so Confirm can never fail.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from monopoly import actionlog
from monopoly.player import Player
from monopoly.property import (
    HOTEL_LEVEL,
    MAX_HOUSES,
    Property,
    properties_in_group,
)

#: Buildings the bank starts with. The standard set.
HOUSE_SUPPLY = 32
HOTEL_SUPPLY = 12


@dataclass
class Bank:
    """The bank's stock of buildings.

    Houses and hotels are physical pieces: a hotel placed on a lot puts its
    four houses back in the box, and a hotel sold takes four out again.
    """

    houses: int = HOUSE_SUPPLY
    hotels: int = HOTEL_SUPPLY

    def reset(self) -> None:
        """Put every building back in the box."""
        actionlog.event(
            "bank", "reset", was_houses=self.houses, was_hotels=self.hotels
        )
        self.houses = HOUSE_SUPPLY
        self.hotels = HOTEL_SUPPLY


def buildable_groups(
    player: Player, properties: Sequence[Property]
) -> list[str]:
    """The colour groups ``player`` may build on, in board order.

    A group qualifies when the player holds every lot in it and none of them
    is mortgaged. Railroads and utilities never qualify: they carry no houses,
    whoever owns them all.
    """
    groups: list[str] = []
    for prop in sorted(properties, key=lambda p: p.index):
        if not prop.is_property or prop.group in groups:
            continue
        lots = [p for p in properties if p.group == prop.group]
        if len(lots) != prop.group_size:
            continue
        if all(p.owner is player and not p.mortgaged for p in lots):
            groups.append(prop.group)
    return groups


class BuildPlan:
    """A draft set of building changes for one player, applied all at once.

    The plan is created from the board as it stands, edited with :meth:`add`
    and :meth:`remove`, and then either thrown away or handed to
    :meth:`commit`. Its ``houses`` / ``hotels`` counters are what the bank
    *would* hold, and :attr:`cost` is what the player *would* pay -- negative
    when the draft sells more than it buys.
    """

    def __init__(
        self,
        player: Player,
        properties: Sequence[Property],
        bank: Optional[Bank] = None,
    ) -> None:
        self.player = player
        self.properties = list(properties)
        self.bank = bank if bank is not None else Bank()
        self.groups = buildable_groups(player, self.properties)
        self.lots: dict[str, list[Property]] = {
            group: properties_in_group(self.properties, group)
            for group in self.groups
        }
        self.levels: dict[Property, int] = {}
        self.houses = 0
        self.hotels = 0
        self.reset()
        actionlog.event(
            "build", "open", player=player.name, cash=player.cash,
            groups=",".join(self.groups) or "(none)",
            standing=actionlog.buildings_of(player),
            bank_houses=self.bank.houses, bank_hotels=self.bank.hotels,
        )

    # --- the draft ----------------------------------------------------------
    def reset(self) -> None:
        """Throw the draft away and start again from the board as it is."""
        self.levels = {
            lot: lot.building_level for lots in self.lots.values() for lot in lots
        }
        self.houses = self.bank.houses
        self.hotels = self.bank.hotels
        actionlog.debug(
            "build", "draft_reset", player=self.player.name,
            lots=len(self.levels), bank_houses=self.houses,
            bank_hotels=self.hotels,
        )

    @property
    def all_lots(self) -> list[Property]:
        """Every lot the plan can touch, grouped and in board order."""
        return [lot for group in self.groups for lot in self.lots[group]]

    @property
    def is_empty(self) -> bool:
        """Whether the player has nothing to build on at all."""
        return not self.groups

    @property
    def changed(self) -> bool:
        """Whether the draft differs from what is standing on the board."""
        return any(level != lot.building_level for lot, level in self.levels.items())

    def level(self, deed: Property) -> int:
        """The draft's building level for ``deed`` (0-4 houses, 5 a hotel)."""
        return self.levels.get(deed, deed.building_level)

    def group_levels(self, group: str) -> list[int]:
        """The draft's levels across ``group``, in board order."""
        return [self.levels[lot] for lot in self.lots[group]]

    # --- price --------------------------------------------------------------
    @property
    def cost(self) -> int:
        """What committing the draft would cost; negative when it pays out.

        Priced against the **board**, not against the clicks that got here, so
        ``+`` followed by ``-`` on the same lot is a free undo rather than an
        instant half-price loss. Only a building that was really standing when
        the screen opened is ever sold at half price.
        """
        return sum(self._lot_cost(lot, level) for lot, level in self.levels.items())

    def _lot_cost(self, deed: Property, level: int) -> int:
        """What it would cost to leave ``deed`` at ``level``."""
        delta = level - deed.building_level
        if delta > 0:
            return delta * deed.build_cost
        return delta * self.sale_price(deed)  # delta <= 0, so this is a refund

    def _step_cost(self, deed: Property, delta: int) -> int:
        """What one ``+`` or ``-`` click on ``deed`` would add to the total."""
        level = self.levels[deed]
        return self._lot_cost(deed, level + delta) - self._lot_cost(deed, level)

    # --- editing ------------------------------------------------------------
    def can_add(self, deed: Property) -> bool:
        """Whether one more building may go onto ``deed`` right now."""
        if deed not in self.levels:
            return False
        level = self.levels[deed]
        if level >= HOTEL_LEVEL:
            return False
        if level > min(self.group_levels(deed.group)):
            return False  # even building: the group's other lots are behind
        if level == MAX_HOUSES:
            if self.hotels < 1:
                return False
        elif self.houses < 1:
            return False
        return self.cost + self._step_cost(deed, 1) <= self.player.cash

    def add(self, deed: Property) -> bool:
        """Put one more building on ``deed``; ``False`` if that is not legal."""
        if not self.can_add(deed):
            actionlog.debug(
                "build", "add_refused", player=self.player.name, deed=deed.name,
                level=self.level(deed), cash=self.player.cash, cost=self.cost,
                draft_houses=self.houses, draft_hotels=self.hotels,
            )
            return False
        level = self.levels[deed]
        if level == MAX_HOUSES:
            self.hotels -= 1
            self.houses += MAX_HOUSES  # the four houses go back in the box
        else:
            self.houses -= 1
        self.levels[deed] = level + 1
        actionlog.debug(
            "build", "draft_add", player=self.player.name, deed=deed.name,
            frm=level, to=level + 1, cost=self.cost,
            draft_houses=self.houses, draft_hotels=self.hotels,
        )
        return True

    def can_remove(self, deed: Property) -> bool:
        """Whether a building may come off ``deed`` right now."""
        if deed not in self.levels:
            return False
        level = self.levels[deed]
        if level <= 0:
            return False
        if level < max(self.group_levels(deed.group)):
            return False  # even building: sell from the tallest lot first
        # Breaking a hotel means standing four houses back up on the lot.
        return level != HOTEL_LEVEL or self.houses >= MAX_HOUSES

    def remove(self, deed: Property) -> bool:
        """Sell one building off ``deed``; ``False`` if that is not legal."""
        if not self.can_remove(deed):
            actionlog.debug(
                "build", "remove_refused", player=self.player.name,
                deed=deed.name, level=self.level(deed),
                draft_houses=self.houses,
            )
            return False
        level = self.levels[deed]
        if level == HOTEL_LEVEL:
            self.hotels += 1
            self.houses -= MAX_HOUSES
        else:
            self.houses += 1
        self.levels[deed] = level - 1
        actionlog.debug(
            "build", "draft_remove", player=self.player.name, deed=deed.name,
            frm=level, to=level - 1, cost=self.cost,
            draft_houses=self.houses, draft_hotels=self.hotels,
        )
        return True

    @staticmethod
    def sale_price(deed: Property) -> int:
        """What the bank pays back for one building on ``deed`` -- half price."""
        return deed.build_cost // 2

    # --- committing ---------------------------------------------------------
    @property
    def refund(self) -> int:
        """Cash coming back to the player (``0`` when the draft costs money)."""
        return max(0, -self.cost)

    @property
    def charge(self) -> int:
        """Cash the player owes (``0`` when the draft pays out)."""
        return max(0, self.cost)

    def standing(self) -> tuple[int, int]:
        """``(houses, hotels)`` the draft would leave standing on its lots."""
        levels = self.levels.values()
        houses = sum(level for level in levels if level < HOTEL_LEVEL)
        hotels = sum(1 for level in levels if level == HOTEL_LEVEL)
        return houses, hotels

    def commit(self) -> bool:
        """Apply the whole draft at once: deeds, bank and cash together.

        ``False`` -- and nothing changes -- when there is nothing to do or the
        cash has gone since the draft was made. Neither is reachable from the
        build screen, which only offers a click it has already priced.
        """
        if not self.changed:
            actionlog.debug(
                "build", "commit_noop", player=self.player.name,
                reason="nothing changed",
            )
            return False
        # Read the price once: applying the draft is what makes it zero.
        charge, refund = self.charge, self.refund
        if charge and not self.player.can_pay(charge):
            actionlog.warn(
                "build", "commit_refused", player=self.player.name,
                charge=charge, cash=self.player.cash, reason="cash gone",
            )
            return False
        moves = [
            f"{lot.name} {lot.building_level}->{level}"
            for lot, level in self.levels.items()
            if level != lot.building_level
        ]
        actionlog.event(
            "build", "commit", player=self.player.name, charge=charge,
            refund=refund, cash_before=self.player.cash,
            moves="; ".join(moves),
            bank_before=f"{self.bank.houses}h/{self.bank.hotels}H",
            bank_after=f"{self.houses}h/{self.hotels}H",
        )
        for lot, level in self.levels.items():
            lot.has_hotel = level == HOTEL_LEVEL
            lot.houses = 0 if lot.has_hotel else level
        self.bank.houses = self.houses
        self.bank.hotels = self.hotels
        if charge:
            self.player.pay(charge)
        elif refund:
            self.player.receive(refund)
        actionlog.audit(
            self.bank, self.properties, "build.commit", [self.player]
        )
        return True


def describe_plan(plan: BuildPlan) -> str:
    """A one-line account of what committing ``plan`` would do."""
    if not plan.changed:
        return "No changes."
    built = sum(
        max(0, level - lot.building_level) for lot, level in plan.levels.items()
    )
    sold = sum(
        max(0, lot.building_level - level) for lot, level in plan.levels.items()
    )
    parts = []
    if built:
        parts.append(f"build {built}")
    if sold:
        parts.append(f"sell {sold}")
    money = f"pay ${plan.charge:,}" if plan.charge else f"receive ${plan.refund:,}"
    return f"{', '.join(parts)} -- {money}."


def total_buildings(properties: Iterable[Property]) -> tuple[int, int]:
    """``(houses, hotels)`` standing on ``properties``."""
    houses = sum(p.house_count for p in properties)
    hotels = sum(p.hotel_count for p in properties)
    return houses, hotels
