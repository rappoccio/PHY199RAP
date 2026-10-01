"""Phase 7: the Chance and Community Chest decks.

:class:`Card` is one card from ``data/chance.json`` or
``data/community_chest.json``, validated against the action schema in
:mod:`monopoly.data_loader`. :class:`Deck` is the pile it is drawn from: cards
come off the top and go to the bottom, so a full cycle sees every card once,
exactly like the cardboard ones.

The one exception is a Get Out of Jail Free card. It leaves the deck when it is
drawn and only comes back -- to the bottom -- when the player who holds it
spends it (:meth:`Deck.return_card`). Until then, drawing cannot hand out a
second copy of a card somebody is still holding.

No pygame here: the deck is pure rules, so the turn loop's card handling can be
tested without a surface.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from monopoly.data_loader import (
    CARD_ACTIONS,
    load_chance,
    load_community_chest,
)

#: The two deck names, matching the ``chance`` / ``community_chest`` space types.
CHANCE = "chance"
COMMUNITY_CHEST = "community_chest"

#: Actions whose card leaves the deck when drawn and returns when spent.
KEEPABLE_ACTIONS = frozenset({"get_out_of_jail"})


@dataclass(frozen=True)
class Card:
    """One card. Frozen, so a drawn card can never be edited by mistake.

    Only ``text`` and ``action`` are always present; the rest are the optional
    payload keys the nine-and-a-bit action types use, defaulted so that reading
    one that does not apply gives a harmless zero rather than a ``KeyError``.
    """

    text: str
    action: str
    #: ``move_to``: the space to land on.
    destination: int = 0
    #: ``move_relative``: signed number of spaces.
    offset: int = 0
    #: ``collect`` / ``pay`` / ``collect_from_players`` / ``pay_to_players``.
    amount: int = 0
    #: ``pay_per_building``.
    per_house: int = 0
    per_hotel: int = 0
    #: ``move_to_nearest``: ``"railroad"`` or ``"utility"``.
    group: str = ""
    #: ``move_to_nearest``: how the rent owed on arrival is scaled.
    rent_multiplier: int = 1
    roll_multiplier: int = 0
    #: Whether passing Go on the way pays the salary.
    collect_go: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "Card":
        """Build a card from one deck-file entry, rejecting unknown actions."""
        action = data.get("action")
        if action not in CARD_ACTIONS:
            raise ValueError(f"unknown card action {action!r} in {data.get('text')!r}")
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        known["action"] = action
        return cls(**known)

    @property
    def keepable(self) -> bool:
        """Whether this card is held by the player instead of going back."""
        return self.action in KEEPABLE_ACTIONS

    @property
    def moves(self) -> bool:
        """Whether resolving this card sends the player to another space."""
        return self.action in ("move_to", "move_to_nearest", "move_relative")


def build_cards(entries: Iterable[dict]) -> list[Card]:
    """Turn raw deck-file dicts into :class:`Card` objects, in file order."""
    return [Card.from_dict(entry) for entry in entries]


class Deck:
    """A draw pile that cycles: draw from the top, discard to the bottom."""

    def __init__(
        self,
        cards: Sequence[Card],
        *,
        name: str = "",
        rng: Optional[random.Random] = None,
        shuffle: bool = True,
    ) -> None:
        if not cards:
            raise ValueError("a deck needs at least one card")
        self.name = name
        self.rng = rng if rng is not None else random.Random()
        self._cards: list[Card] = list(cards)
        #: Cards drawn and kept by a player (Get Out of Jail Free).
        self._held: list[Card] = []
        if shuffle:
            self.shuffle()

    # --- construction -------------------------------------------------------
    @classmethod
    def chance(cls, rng: Optional[random.Random] = None, **kwargs) -> "Deck":
        return cls(build_cards(load_chance()), name=CHANCE, rng=rng, **kwargs)

    @classmethod
    def community_chest(
        cls, rng: Optional[random.Random] = None, **kwargs
    ) -> "Deck":
        return cls(
            build_cards(load_community_chest()),
            name=COMMUNITY_CHEST,
            rng=rng,
            **kwargs,
        )

    # --- state --------------------------------------------------------------
    def __len__(self) -> int:
        return len(self._cards)

    @property
    def cards(self) -> tuple[Card, ...]:
        """The pile as it stands, top card first."""
        return tuple(self._cards)

    @property
    def held(self) -> tuple[Card, ...]:
        """Cards currently out of the deck in a player's hand."""
        return tuple(self._held)

    @property
    def top(self) -> Card:
        """The card the next :meth:`draw` will return."""
        return self._cards[0]

    # --- drawing ------------------------------------------------------------
    def shuffle(self) -> None:
        """Shuffle the pile in place."""
        self.rng.shuffle(self._cards)

    def draw(self) -> Card:
        """Take the top card.

        Ordinary cards go straight to the bottom, so the pile always has the
        same length. A keepable card is held out until :meth:`return_card`.
        """
        if not self._cards:
            raise RuntimeError(f"{self.name or 'deck'} has no cards left to draw")
        card = self._cards.pop(0)
        if card.keepable:
            self._held.append(card)
        else:
            self._cards.append(card)
        return card

    def return_card(self, card: Card) -> None:
        """Put a held card back at the bottom of the pile."""
        for i, held in enumerate(self._held):
            if held is card or held == card:
                del self._held[i]
                break
        else:
            raise ValueError(f"{card.text!r} is not held out of this deck")
        self._cards.append(card)

    def reset(self) -> None:
        """Take every card back and reshuffle (used by "Play Again")."""
        self._cards.extend(self._held)
        self._held.clear()
        self.shuffle()
