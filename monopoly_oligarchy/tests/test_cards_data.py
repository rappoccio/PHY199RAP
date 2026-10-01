"""Phase 1 tests: the Chance and Community Chest decks.

Each card is validated against the action schema the Phase 7 card executor
will dispatch on, so a malformed card fails here rather than mid-game.
"""

from __future__ import annotations

import unittest

from monopoly.data_loader import (
    BOARD_SIZE,
    CARD_ACTIONS,
    load_chance,
    load_community_chest,
)

DECK_SIZE = 16

# action -> required keys beyond "text"/"action"
REQUIRED_FIELDS = {
    "move_to": ("destination",),
    "move_to_nearest": ("group",),
    "move_relative": ("offset",),
    "collect": ("amount",),
    "pay": ("amount",),
    "pay_per_building": ("per_house", "per_hotel"),
    "get_out_of_jail": (),
    "go_to_jail": (),
    "collect_from_players": ("amount",),
    "pay_to_players": ("amount",),
}


class CardDeckTestMixin:
    """Shared structural checks applied to both decks."""

    deck_name = ""

    def load(self) -> list[dict]:
        raise NotImplementedError

    def setUp(self) -> None:
        self.cards = self.load()

    def test_deck_has_sixteen_cards(self) -> None:
        self.assertEqual(len(self.cards), DECK_SIZE)

    def test_every_card_has_non_empty_text(self) -> None:
        for card in self.cards:
            self.assertTrue(card.get("text", "").strip(), card)

    def test_every_action_is_known(self) -> None:
        for card in self.cards:
            with self.subTest(card=card["text"]):
                self.assertIn(card["action"], CARD_ACTIONS)

    def test_every_card_carries_the_fields_its_action_needs(self) -> None:
        for card in self.cards:
            with self.subTest(card=card["text"]):
                for field in REQUIRED_FIELDS[card["action"]]:
                    self.assertIn(field, card)

    def test_no_card_carries_unexpected_fields(self) -> None:
        optional = {"collect_go", "rent_multiplier", "roll_multiplier"}
        for card in self.cards:
            with self.subTest(card=card["text"]):
                allowed = {"text", "action"} | set(REQUIRED_FIELDS[card["action"]]) | optional
                self.assertLessEqual(set(card), allowed)

    def test_destinations_are_valid_board_indices(self) -> None:
        for card in self.cards:
            if card["action"] == "move_to":
                with self.subTest(card=card["text"]):
                    self.assertIn(card["destination"], range(BOARD_SIZE))

    def test_money_amounts_are_positive_integers(self) -> None:
        money_fields = ("amount", "per_house", "per_hotel")
        for card in self.cards:
            for field in money_fields:
                if field in card:
                    with self.subTest(card=card["text"], field=field):
                        self.assertIsInstance(card[field], int)
                        self.assertGreater(card[field], 0)

    def test_exactly_one_get_out_of_jail_free_card(self) -> None:
        actions = [card["action"] for card in self.cards]
        self.assertEqual(actions.count("get_out_of_jail"), 1)

    def test_exactly_one_go_to_jail_card(self) -> None:
        actions = [card["action"] for card in self.cards]
        self.assertEqual(actions.count("go_to_jail"), 1)

    def test_cards_that_move_the_player_declare_go_handling(self) -> None:
        movers = {"move_to", "move_to_nearest", "move_relative"}
        for card in self.cards:
            if card["action"] in movers:
                with self.subTest(card=card["text"]):
                    self.assertIn("collect_go", card)
                    self.assertIsInstance(card["collect_go"], bool)


class TestChanceDeck(CardDeckTestMixin, unittest.TestCase):
    deck_name = "chance"

    def load(self) -> list[dict]:
        return load_chance()

    def test_advance_to_go_collects_two_hundred(self) -> None:
        card = next(c for c in self.cards if c["text"].startswith("Advance to Go"))
        self.assertEqual(card["destination"], 0)
        self.assertTrue(card["collect_go"])

    def test_two_nearest_railroad_cards_pay_double_rent(self) -> None:
        railroad_cards = [
            c
            for c in self.cards
            if c["action"] == "move_to_nearest" and c["group"] == "railroad"
        ]
        self.assertEqual(len(railroad_cards), 2)
        for card in railroad_cards:
            self.assertEqual(card["rent_multiplier"], 2)

    def test_one_nearest_utility_card_pays_ten_times_the_roll(self) -> None:
        utility_cards = [
            c
            for c in self.cards
            if c["action"] == "move_to_nearest" and c["group"] == "utility"
        ]
        self.assertEqual(len(utility_cards), 1)
        self.assertEqual(utility_cards[0]["roll_multiplier"], 10)

    def test_nearest_groups_are_railroad_or_utility(self) -> None:
        for card in self.cards:
            if card["action"] == "move_to_nearest":
                self.assertIn(card["group"], {"railroad", "utility"})

    def test_go_back_three_spaces_does_not_collect_go(self) -> None:
        card = next(c for c in self.cards if c["action"] == "move_relative")
        self.assertEqual(card["offset"], -3)
        self.assertFalse(card["collect_go"])

    def test_general_repairs_amounts(self) -> None:
        card = next(c for c in self.cards if c["action"] == "pay_per_building")
        self.assertEqual(card["per_house"], 25)
        self.assertEqual(card["per_hotel"], 100)

    def test_chairman_pays_every_other_player(self) -> None:
        card = next(c for c in self.cards if c["action"] == "pay_to_players")
        self.assertEqual(card["amount"], 50)

    def test_deck_contains_no_collect_from_players_card(self) -> None:
        actions = {card["action"] for card in self.cards}
        self.assertNotIn("collect_from_players", actions)


class TestCommunityChestDeck(CardDeckTestMixin, unittest.TestCase):
    deck_name = "community_chest"

    def load(self) -> list[dict]:
        return load_community_chest()

    def test_advance_to_go_collects_two_hundred(self) -> None:
        card = next(c for c in self.cards if c["text"].startswith("Advance to Go"))
        self.assertEqual(card["destination"], 0)
        self.assertTrue(card["collect_go"])

    def test_birthday_collects_from_every_player(self) -> None:
        card = next(c for c in self.cards if c["action"] == "collect_from_players")
        self.assertEqual(card["amount"], 10)

    def test_street_repairs_amounts(self) -> None:
        card = next(c for c in self.cards if c["action"] == "pay_per_building")
        self.assertEqual(card["per_house"], 40)
        self.assertEqual(card["per_hotel"], 115)

    def test_deck_has_no_nearest_group_movement(self) -> None:
        actions = {card["action"] for card in self.cards}
        self.assertNotIn("move_to_nearest", actions)


class TestDecksTogether(unittest.TestCase):
    def test_exactly_two_get_out_of_jail_free_cards_exist_in_the_game(self) -> None:
        both = load_chance() + load_community_chest()
        actions = [card["action"] for card in both]
        self.assertEqual(actions.count("get_out_of_jail"), 2)

    def test_card_text_is_unique_within_each_deck_except_paired_railroad_cards(self) -> None:
        chest_texts = [card["text"] for card in load_community_chest()]
        self.assertEqual(len(chest_texts), len(set(chest_texts)))

        chance_texts = [card["text"] for card in load_chance()]
        duplicates = [t for t in set(chance_texts) if chance_texts.count(t) > 1]
        self.assertEqual(len(duplicates), 1)
        self.assertIn("nearest Railroad", duplicates[0])

    def test_loader_returns_independent_copies(self) -> None:
        deck = load_chance()
        deck[0]["amount"] = 999_999
        self.assertNotIn("amount", load_chance()[0])


if __name__ == "__main__":
    unittest.main()
