"""Phase 2: the title deed.

``Property`` wraps one ownable board space (a colour property, a railroad or a
utility) and carries both its static deed values -- read from
``data/spaces.json`` via :mod:`monopoly.data_loader` -- and its mutable game
state (owner, buildings, mortgage flag).

Rent rules implemented here follow the standard US Monopoly rules:

* A mortgaged deed collects no rent at all.
* An unimproved colour property rents at double its base rate when its owner
  holds every deed in the colour group. Mortgaging one lot of a group does not
  break the monopoly for the *other* lots -- only the mortgaged lot itself
  stops earning.
* Railroad rent depends on how many of the four railroads the owner holds, and
  utility rent is a multiplier on the dice roll that moved the tenant there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable, Optional, Sequence

from monopoly.data_loader import DEED_TYPES, load_spaces

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to type checkers
    from monopoly.player import Player

#: Group keys used by the two non-colour deed types.
RAILROAD_GROUP = "railroad"
UTILITY_GROUP = "utility"

#: Houses that fit on one lot before it upgrades to a hotel.
MAX_HOUSES = 4

#: ``building_level`` of a lot carrying a hotel (index into the rent table).
HOTEL_LEVEL = 5

#: A hotel costs four houses plus one more payment of ``house_cost``.
HOTEL_HOUSE_EQUIVALENT = 5


def group_of(space: dict) -> str:
    """Return the group key for a deed ``space`` dict from ``spaces.json``."""
    if space["type"] == "property":
        return space["color"]
    return space["type"]


@dataclass(eq=False)
class Property:
    """One ownable board space.

    Instances compare by identity (``eq=False``) so that properties can live in
    sets, be compared with ``is``, and reference their owner without the
    dataclass machinery recursing through ``Player.properties``.
    """

    index: int
    name: str
    type: str
    group: str
    price: int
    mortgage_value: int
    group_size: int
    rent: tuple[int, ...] = ()
    multipliers: tuple[int, ...] = ()
    house_cost: int = 0

    # --- mutable game state -------------------------------------------------
    owner: Optional["Player"] = field(default=None, repr=False)
    houses: int = 0
    has_hotel: bool = False
    mortgaged: bool = False

    # --- construction -------------------------------------------------------
    @classmethod
    def from_space(cls, space: dict) -> "Property":
        """Build a deed from one ``spaces.json`` entry."""
        if space["type"] not in DEED_TYPES:
            raise ValueError(
                f"space {space['index']} ({space['name']}) is a "
                f"{space['type']!r} space and carries no deed"
            )
        return cls(
            index=space["index"],
            name=space["name"],
            type=space["type"],
            group=group_of(space),
            price=space["price"],
            mortgage_value=space["mortgage"],
            group_size=space["group_size"],
            rent=tuple(space.get("rent", ())),
            multipliers=tuple(space.get("multipliers", ())),
            house_cost=space.get("house_cost", 0),
        )

    # --- static deed values -------------------------------------------------
    @property
    def is_property(self) -> bool:
        return self.type == "property"

    @property
    def is_railroad(self) -> bool:
        return self.type == RAILROAD_GROUP

    @property
    def is_utility(self) -> bool:
        return self.type == UTILITY_GROUP

    @property
    def build_cost(self) -> int:
        """Cash charged per house (and per hotel upgrade) on this lot."""
        return self.house_cost

    @property
    def unmortgage_cost(self) -> int:
        """Mortgage value plus 10% interest, rounded up to a whole dollar."""
        return (self.mortgage_value * 11 + 9) // 10

    # --- building state -----------------------------------------------------
    @property
    def building_level(self) -> int:
        """0-4 houses, or :data:`HOTEL_LEVEL` for a hotel."""
        return HOTEL_LEVEL if self.has_hotel else self.houses

    @property
    def house_count(self) -> int:
        """Houses standing here (a hotel counts as zero houses)."""
        return 0 if self.has_hotel else self.houses

    @property
    def hotel_count(self) -> int:
        return 1 if self.has_hotel else 0

    @property
    def buildings_value(self) -> int:
        """Cash sunk into buildings here, at full purchase price."""
        if self.has_hotel:
            return HOTEL_HOUSE_EQUIVALENT * self.house_cost
        return self.houses * self.house_cost

    @property
    def building_sale_value(self) -> int:
        """Cash the bank pays back for every building here (half price)."""
        return self.buildings_value // 2

    # --- rent ---------------------------------------------------------------
    def current_rent(self, owner: Optional["Player"] = None, dice_total: int = 0) -> int:
        """Rent owed by a tenant landing here.

        ``owner`` defaults to the deed's own owner; passing one explicitly lets
        callers price a hypothetical owner. ``dice_total`` is only consulted for
        utilities, where it is required.
        """
        owner = self.owner if owner is None else owner
        if owner is None or self.mortgaged:
            return 0

        held = self._group_holdings(owner)
        if self.is_property:
            if self.has_hotel:
                return self.rent[HOTEL_LEVEL]
            if self.houses:
                return self.rent[self.houses]
            base = self.rent[0]
            return base * 2 if held == self.group_size else base
        if self.is_railroad:
            return self.rent[held - 1]
        if dice_total <= 0:
            raise ValueError(
                f"utility rent for {self.name} needs the dice total that moved "
                "the tenant here"
            )
        return self.multipliers[held - 1] * dice_total

    def _group_holdings(self, owner: "Player") -> int:
        """How many deeds of this group ``owner`` holds, counting this one."""
        held = [p for p in owner.properties if p.group == self.group]
        if self not in held:
            held.append(self)
        return min(len(held), self.group_size)


def properties_in_group(properties: Iterable[Property], group: str) -> list[Property]:
    """Every deed of ``group`` within ``properties``, in board order."""
    return sorted(
        (p for p in properties if p.group == group), key=lambda p: p.index
    )


def build_properties(spaces: Optional[Sequence[dict]] = None) -> list[Property]:
    """Every deed on the board, in board order.

    Defaults to the real board from ``data/spaces.json``; a caller may pass a
    space list of its own (tests do).
    """
    if spaces is None:
        spaces = load_spaces()
    return [Property.from_space(s) for s in spaces if s["type"] in DEED_TYPES]
