"""Single entry point for reading the static game data in ``monopoly/data``.

Every other module reads board and card definitions through here so that the
file paths and the JSON schema live in exactly one place.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

BOARD_SIZE = 40

#: Space types that may appear in ``spaces.json``.
SPACE_TYPES = frozenset(
    {
        "go",
        "property",
        "railroad",
        "utility",
        "tax",
        "chance",
        "community_chest",
        "jail",
        "go_to_jail",
        "free_parking",
    }
)

#: Space types that carry a title deed a player can own.
DEED_TYPES = frozenset({"property", "railroad", "utility"})

#: Card actions that may appear in ``chance.json`` / ``community_chest.json``.
CARD_ACTIONS = frozenset(
    {
        "move_to",
        "move_to_nearest",
        "move_relative",
        "collect",
        "pay",
        "pay_per_building",
        "get_out_of_jail",
        "go_to_jail",
        "collect_from_players",
        "pay_to_players",
    }
)

#: The eight standard colour groups, in board order.
COLOR_GROUPS = (
    "brown",
    "light_blue",
    "pink",
    "orange",
    "red",
    "yellow",
    "green",
    "dark_blue",
)


def _load(filename: str) -> list[dict]:
    with open(DATA_DIR / filename, encoding="utf-8") as handle:
        return json.load(handle)


@lru_cache(maxsize=None)
def _cached(filename: str) -> tuple[dict, ...]:
    return tuple(_load(filename))


def load_spaces() -> list[dict]:
    """Return the 40 board spaces in board order (index 0 = Go)."""
    return [dict(space) for space in _cached("spaces.json")]


def load_chance() -> list[dict]:
    """Return the Chance deck in file order."""
    return [dict(card) for card in _cached("chance.json")]


def load_community_chest() -> list[dict]:
    """Return the Community Chest deck in file order."""
    return [dict(card) for card in _cached("community_chest.json")]
