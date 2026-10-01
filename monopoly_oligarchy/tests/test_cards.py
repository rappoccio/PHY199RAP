"""Phase 7 tests: the Chance and Community Chest decks.

Two things are being pinned down here. First, that :class:`Card` accepts every
action the shipped decks actually use and rejects anything else, so a typo in a
deck file fails loudly at load rather than silently doing nothing at the table.
Second, that :class:`Deck` cycles -- draw from the top, discard to the bottom --
with the one exception the rules make for Get Out of Jail Free, which leaves the
pile while a player holds it.

No pygame, no surface: the decks are pure rules.
"""

from __future__ import annotations

import random
import unittest

from monopoly.cards import (
    CHANCE,
    COMMUNITY_CHEST,
    Card,
    Deck,
    build_cards,
)
from monopoly.data_loader import CARD_ACTIONS, load_chance, load_community_chest

GOOJF = {
    "text": "Get Out of Jail Free.",
    "action": "get_out_of_jail",
}

PAY_50 = {"text": "Pay $50.", "action": "pay", "amount": 50}
COLLECT_20 = {"text": "Collect $20.", "action": "collect", "amount": 20}


def plain(n: int) -> list[Card]:
    """``n`` distinguishable, non-keepable cards."""
    return [Card(text=f"card {i}", action="collect", amount=i) for i in range(n)]


class CardTest(unittest.TestCase):
    def test_from_dict_reads_the_payload(self):
        card = Card.from_dict(
            {
                "text": "Advance to Illinois Avenue.",
                "action": "move_to",
                "destination": 24,
                "collect_go": True,
            }
        )
        self.assertEqual(card.action, "move_to")
        self.assertEqual(card.destination, 24)
        self.assertTrue(card.collect_go)

    def test_unset_payload_keys_default_rather_than_raise(self):
        card = Card.from_dict(PAY_50)
        self.assertEqual(card.amount, 50)
        self.assertEqual(card.destination, 0)
        self.assertEqual(card.offset, 0)
        self.assertEqual(card.group, "")
        self.assertFalse(card.collect_go)

    def test_rent_multiplier_defaults_to_one(self):
        """So a card's multiplier can be applied unconditionally."""
        self.assertEqual(Card.from_dict(PAY_50).rent_multiplier, 1)

    def test_unknown_action_is_rejected(self):
        with self.assertRaises(ValueError):
            Card.from_dict({"text": "?", "action": "teleport"})

    def test_missing_action_is_rejected(self):
        with self.assertRaises(ValueError):
            Card.from_dict({"text": "?"})

    def test_unrecognised_keys_are_ignored(self):
        card = Card.from_dict(dict(PAY_50, colour="blue"))
        self.assertEqual(card.amount, 50)

    def test_cards_are_frozen(self):
        card = Card.from_dict(PAY_50)
        with self.assertRaises(Exception):
            card.amount = 1

    def test_keepable_is_only_get_out_of_jail(self):
        self.assertTrue(Card.from_dict(GOOJF).keepable)
        self.assertFalse(Card.from_dict(PAY_50).keepable)

    def test_moves_covers_the_three_movement_actions(self):
        for action in ("move_to", "move_to_nearest", "move_relative"):
            with self.subTest(action=action):
                self.assertTrue(Card(text="", action=action).moves)
        for action in ("collect", "pay", "go_to_jail", "get_out_of_jail"):
            with self.subTest(action=action):
                self.assertFalse(Card(text="", action=action).moves)


class RealDeckDataTest(unittest.TestCase):
    """The shipped deck files must survive :func:`build_cards` intact."""

    def test_both_decks_load(self):
        self.assertEqual(len(build_cards(load_chance())), 16)
        self.assertEqual(len(build_cards(load_community_chest())), 16)

    def test_every_action_used_is_a_known_action(self):
        for card in build_cards(load_chance()) + build_cards(load_community_chest()):
            with self.subTest(card=card.text):
                self.assertIn(card.action, CARD_ACTIONS)

    def test_move_to_nearest_cards_name_a_group(self):
        nearest = [c for c in build_cards(load_chance()) if c.action == "move_to_nearest"]
        self.assertEqual(len(nearest), 3)
        for card in nearest:
            with self.subTest(card=card.text):
                self.assertIn(card.group, ("railroad", "utility"))

    def test_named_constructors(self):
        chance = Deck.chance(random.Random(1))
        chest = Deck.community_chest(random.Random(1))
        self.assertEqual(chance.name, CHANCE)
        self.assertEqual(chest.name, COMMUNITY_CHEST)
        self.assertEqual(len(chance), 16)
        self.assertEqual(len(chest), 16)


class DeckTest(unittest.TestCase):
    def setUp(self):
        self.deck = Deck(plain(4), shuffle=False)

    def test_empty_deck_is_rejected(self):
        with self.assertRaises(ValueError):
            Deck([])

    def test_draw_takes_the_top_card(self):
        top = self.deck.top
        self.assertIs(self.deck.draw(), top)

    def test_ordinary_draw_keeps_the_pile_the_same_size(self):
        self.deck.draw()
        self.assertEqual(len(self.deck), 4)

    def test_a_drawn_card_goes_to_the_bottom(self):
        card = self.deck.draw()
        self.assertIs(self.deck.cards[-1], card)

    def test_a_full_cycle_sees_every_card_once(self):
        drawn = [self.deck.draw() for _ in range(4)]
        self.assertEqual({c.text for c in drawn}, {c.text for c in plain(4)})

    def test_the_cycle_then_repeats_in_the_same_order(self):
        first = [self.deck.draw().text for _ in range(4)]
        second = [self.deck.draw().text for _ in range(4)]
        self.assertEqual(first, second)

    def test_shuffle_is_reproducible_from_a_seed(self):
        cards = plain(10)
        one = Deck(cards, rng=random.Random(99))
        two = Deck(cards, rng=random.Random(99))
        self.assertEqual([c.text for c in one.cards], [c.text for c in two.cards])

    def test_shuffle_false_keeps_file_order(self):
        cards = plain(5)
        deck = Deck(cards, shuffle=False)
        self.assertEqual([c.text for c in deck.cards], [c.text for c in cards])


class KeepableCardTest(unittest.TestCase):
    """Get Out of Jail Free leaves the pile until it is spent."""

    def setUp(self):
        self.goojf = Card.from_dict(GOOJF)
        self.deck = Deck([self.goojf] + plain(3), shuffle=False)

    def test_drawing_it_shrinks_the_pile(self):
        self.deck.draw()
        self.assertEqual(len(self.deck), 3)

    def test_it_is_listed_as_held(self):
        card = self.deck.draw()
        self.assertEqual(self.deck.held, (card,))

    def test_it_cannot_be_drawn_twice(self):
        self.deck.draw()
        rest = [self.deck.draw() for _ in range(6)]
        self.assertNotIn(self.goojf, rest)

    def test_returning_it_puts_it_at_the_bottom(self):
        card = self.deck.draw()
        self.deck.return_card(card)
        self.assertEqual(len(self.deck), 4)
        self.assertIs(self.deck.cards[-1], card)
        self.assertEqual(self.deck.held, ())

    def test_returning_a_card_that_is_not_held_raises(self):
        with self.assertRaises(ValueError):
            self.deck.return_card(self.goojf)

    def test_reset_takes_every_card_back(self):
        self.deck.draw()
        self.deck.reset()
        self.assertEqual(len(self.deck), 4)
        self.assertEqual(self.deck.held, ())

    def test_drawing_an_exhausted_deck_raises(self):
        deck = Deck([self.goojf], shuffle=False)
        deck.draw()
        with self.assertRaises(RuntimeError):
            deck.draw()


if __name__ == "__main__":
    unittest.main()
