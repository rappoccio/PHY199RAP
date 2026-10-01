"""Phase 1 tests: the 40 board spaces in ``data/spaces.json``.

These lock the board down against the canonical US Monopoly deed values so
later phases (rent, building, mortgaging) can trust the numbers they read.
"""

from __future__ import annotations

import unittest

from monopoly.data_loader import (
    BOARD_SIZE,
    COLOR_GROUPS,
    DEED_TYPES,
    SPACE_TYPES,
    load_spaces,
)

# name, color, price, mortgage, house_cost, rent[6]
CANONICAL_PROPERTIES = {
    1: ("Mediterranean Avenue", "brown", 60, 30, 50, [2, 10, 30, 90, 160, 250]),
    3: ("Baltic Avenue", "brown", 60, 30, 50, [4, 20, 60, 180, 320, 450]),
    6: ("Oriental Avenue", "light_blue", 100, 50, 50, [6, 30, 90, 270, 400, 550]),
    8: ("Vermont Avenue", "light_blue", 100, 50, 50, [6, 30, 90, 270, 400, 550]),
    9: ("Connecticut Avenue", "light_blue", 120, 60, 50, [8, 40, 100, 300, 450, 600]),
    11: ("St. Charles Place", "pink", 140, 70, 100, [10, 50, 150, 450, 625, 750]),
    13: ("States Avenue", "pink", 140, 70, 100, [10, 50, 150, 450, 625, 750]),
    14: ("Virginia Avenue", "pink", 160, 80, 100, [12, 60, 180, 500, 700, 900]),
    16: ("St. James Place", "orange", 180, 90, 100, [14, 70, 200, 550, 750, 950]),
    18: ("Tennessee Avenue", "orange", 180, 90, 100, [14, 70, 200, 550, 750, 950]),
    19: ("New York Avenue", "orange", 200, 100, 100, [16, 80, 220, 600, 800, 1000]),
    21: ("Kentucky Avenue", "red", 220, 110, 150, [18, 90, 250, 700, 875, 1050]),
    23: ("Indiana Avenue", "red", 220, 110, 150, [18, 90, 250, 700, 875, 1050]),
    24: ("Illinois Avenue", "red", 240, 120, 150, [20, 100, 300, 750, 925, 1100]),
    26: ("Atlantic Avenue", "yellow", 260, 130, 150, [22, 110, 330, 800, 975, 1150]),
    27: ("Ventnor Avenue", "yellow", 260, 130, 150, [22, 110, 330, 800, 975, 1150]),
    29: ("Marvin Gardens", "yellow", 280, 140, 150, [24, 120, 360, 850, 1025, 1200]),
    31: ("Pacific Avenue", "green", 300, 150, 200, [26, 130, 390, 900, 1100, 1275]),
    32: ("North Carolina Avenue", "green", 300, 150, 200, [26, 130, 390, 900, 1100, 1275]),
    34: ("Pennsylvania Avenue", "green", 320, 160, 200, [28, 150, 450, 1000, 1200, 1400]),
    37: ("Park Place", "dark_blue", 350, 175, 200, [35, 175, 500, 1100, 1300, 1500]),
    39: ("Boardwalk", "dark_blue", 400, 200, 200, [50, 200, 600, 1400, 1700, 2000]),
}

EXPECTED_GROUP_SIZES = {
    "brown": 2,
    "light_blue": 3,
    "pink": 3,
    "orange": 3,
    "red": 3,
    "yellow": 3,
    "green": 3,
    "dark_blue": 2,
}

CORNERS = {0: "go", 10: "jail", 20: "free_parking", 30: "go_to_jail"}

RAILROAD_INDICES = (5, 15, 25, 35)
UTILITY_INDICES = (12, 28)
CHANCE_INDICES = (7, 22, 36)
COMMUNITY_CHEST_INDICES = (2, 17, 33)
TAX_AMOUNTS = {4: 200, 38: 100}


class TestBoardShape(unittest.TestCase):
    def setUp(self) -> None:
        self.spaces = load_spaces()

    def test_has_forty_spaces(self) -> None:
        self.assertEqual(len(self.spaces), BOARD_SIZE)

    def test_indices_are_sequential_and_match_position(self) -> None:
        for position, space in enumerate(self.spaces):
            self.assertEqual(space["index"], position)

    def test_every_space_has_a_name_and_known_type(self) -> None:
        for space in self.spaces:
            self.assertTrue(space.get("name"), f"space {space['index']} has no name")
            self.assertIn(space["type"], SPACE_TYPES, space["name"])

    def test_corners_are_in_the_right_places(self) -> None:
        for index, expected_type in CORNERS.items():
            self.assertEqual(self.spaces[index]["type"], expected_type)

    def test_space_type_counts(self) -> None:
        counts: dict[str, int] = {}
        for space in self.spaces:
            counts[space["type"]] = counts.get(space["type"], 0) + 1
        self.assertEqual(
            counts,
            {
                "go": 1,
                "property": 22,
                "railroad": 4,
                "utility": 2,
                "tax": 2,
                "chance": 3,
                "community_chest": 3,
                "jail": 1,
                "go_to_jail": 1,
                "free_parking": 1,
            },
        )

    def test_special_spaces_sit_at_canonical_indices(self) -> None:
        for index in RAILROAD_INDICES:
            self.assertEqual(self.spaces[index]["type"], "railroad")
        for index in UTILITY_INDICES:
            self.assertEqual(self.spaces[index]["type"], "utility")
        for index in CHANCE_INDICES:
            self.assertEqual(self.spaces[index]["type"], "chance")
        for index in COMMUNITY_CHEST_INDICES:
            self.assertEqual(self.spaces[index]["type"], "community_chest")

    def test_names_of_deeds_are_unique(self) -> None:
        names = [s["name"] for s in self.spaces if s["type"] in DEED_TYPES]
        self.assertEqual(len(names), len(set(names)))


class TestProperties(unittest.TestCase):
    def setUp(self) -> None:
        self.spaces = load_spaces()
        self.properties = {s["index"]: s for s in self.spaces if s["type"] == "property"}

    def test_property_indices_match_canonical_board(self) -> None:
        self.assertEqual(sorted(self.properties), sorted(CANONICAL_PROPERTIES))

    def test_property_values_match_canonical_board(self) -> None:
        for index, expected in CANONICAL_PROPERTIES.items():
            name, color, price, mortgage, house_cost, rent = expected
            space = self.properties[index]
            with self.subTest(space=name):
                self.assertEqual(space["name"], name)
                self.assertEqual(space["color"], color)
                self.assertEqual(space["price"], price)
                self.assertEqual(space["mortgage"], mortgage)
                self.assertEqual(space["house_cost"], house_cost)
                self.assertEqual(space["rent"], rent)

    def test_mortgage_is_half_price(self) -> None:
        for space in self.properties.values():
            with self.subTest(space=space["name"]):
                self.assertEqual(space["mortgage"] * 2, space["price"])

    def test_rent_table_has_six_entries_and_strictly_increases(self) -> None:
        for space in self.properties.values():
            with self.subTest(space=space["name"]):
                rent = space["rent"]
                self.assertEqual(len(rent), 6)
                self.assertTrue(all(isinstance(value, int) for value in rent))
                for lower, higher in zip(rent, rent[1:]):
                    self.assertLess(lower, higher)

    def test_colors_are_the_eight_standard_groups(self) -> None:
        colors = {space["color"] for space in self.properties.values()}
        self.assertEqual(colors, set(COLOR_GROUPS))

    def test_group_size_matches_actual_number_of_properties_in_group(self) -> None:
        actual: dict[str, int] = {}
        for space in self.properties.values():
            actual[space["color"]] = actual.get(space["color"], 0) + 1
        self.assertEqual(actual, EXPECTED_GROUP_SIZES)
        for space in self.properties.values():
            with self.subTest(space=space["name"]):
                self.assertEqual(space["group_size"], actual[space["color"]])

    def test_properties_in_a_group_share_a_house_cost(self) -> None:
        by_color: dict[str, set[int]] = {}
        for space in self.properties.values():
            by_color.setdefault(space["color"], set()).add(space["house_cost"])
        for color, costs in by_color.items():
            with self.subTest(color=color):
                self.assertEqual(len(costs), 1)


class TestRailroadsAndUtilities(unittest.TestCase):
    def setUp(self) -> None:
        self.spaces = load_spaces()

    def test_railroads(self) -> None:
        railroads = [s for s in self.spaces if s["type"] == "railroad"]
        self.assertEqual(len(railroads), 4)
        for space in railroads:
            with self.subTest(space=space["name"]):
                self.assertEqual(space["price"], 200)
                self.assertEqual(space["mortgage"], 100)
                self.assertEqual(space["rent"], [25, 50, 100, 200])
                self.assertEqual(space["group_size"], 4)
                self.assertNotIn("color", space)
                self.assertNotIn("house_cost", space)

    def test_utilities(self) -> None:
        utilities = [s for s in self.spaces if s["type"] == "utility"]
        self.assertEqual(len(utilities), 2)
        for space in utilities:
            with self.subTest(space=space["name"]):
                self.assertEqual(space["price"], 150)
                self.assertEqual(space["mortgage"], 75)
                self.assertEqual(space["multipliers"], [4, 10])
                self.assertEqual(space["group_size"], 2)
                self.assertNotIn("color", space)
                self.assertNotIn("house_cost", space)


class TestTaxAndSpecialSpaces(unittest.TestCase):
    def setUp(self) -> None:
        self.spaces = load_spaces()

    def test_tax_spaces_have_amounts(self) -> None:
        for index, amount in TAX_AMOUNTS.items():
            space = self.spaces[index]
            with self.subTest(space=space["name"]):
                self.assertEqual(space["type"], "tax")
                self.assertEqual(space["amount"], amount)

    def test_non_deed_spaces_carry_no_price(self) -> None:
        for space in self.spaces:
            if space["type"] not in DEED_TYPES:
                with self.subTest(space=space["name"]):
                    self.assertNotIn("price", space)


class TestLoaderIsolation(unittest.TestCase):
    def test_mutating_a_loaded_space_does_not_affect_the_next_load(self) -> None:
        first = load_spaces()
        first[1]["price"] = 999_999
        self.assertEqual(load_spaces()[1]["price"], 60)


if __name__ == "__main__":
    unittest.main()
