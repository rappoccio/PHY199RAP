"""Phase 2 tests: the ``Property`` title-deed class.

These pin the rent formulas (base, monopoly, houses, hotel, railroad, utility)
and the derived deed values so that every later phase -- landing, building,
mortgaging, trading -- can rely on them.
"""

from __future__ import annotations

import unittest

from monopoly.data_loader import COLOR_GROUPS, load_spaces
from monopoly.player import Player
from monopoly.property import (
    HOTEL_LEVEL,
    MAX_HOUSES,
    Property,
    build_properties,
    properties_in_group,
)

BOARDWALK = 39
PARK_PLACE = 37
MEDITERRANEAN = 1
BALTIC = 3
READING_RAILROAD = 5
ELECTRIC_COMPANY = 12
WATER_WORKS = 28

RAILROAD_INDICES = (5, 15, 25, 35)
UTILITY_INDICES = (12, 28)


def board() -> dict[int, Property]:
    """Every deed on the real board, keyed by space index."""
    return {prop.index: prop for prop in build_properties()}


def owned_by(name: str, *props: Property, cash: int = 1500) -> Player:
    """A player holding ``props``."""
    player = Player(name=name, cash=cash, token_color="red")
    for prop in props:
        player.add_property(prop)
    return player


class TestConstruction(unittest.TestCase):
    def test_board_has_twenty_eight_deeds(self) -> None:
        deeds = build_properties()
        self.assertEqual(len(deeds), 28)
        self.assertEqual([d.index for d in deeds], sorted(d.index for d in deeds))

    def test_deed_counts_by_type(self) -> None:
        deeds = build_properties()
        counts = {
            kind: sum(1 for d in deeds if d.type == kind)
            for kind in ("property", "railroad", "utility")
        }
        self.assertEqual(counts["property"], 22)
        self.assertEqual(counts["railroad"], 4)
        self.assertEqual(counts["utility"], 2)

    def test_colour_properties_carry_their_colour_as_group(self) -> None:
        for prop in build_properties():
            with self.subTest(deed=prop.name):
                if prop.is_property:
                    self.assertIn(prop.group, COLOR_GROUPS)
                else:
                    self.assertEqual(prop.group, prop.type)

    def test_fields_match_the_source_space(self) -> None:
        boardwalk = board()[BOARDWALK]
        self.assertEqual(boardwalk.name, "Boardwalk")
        self.assertEqual(boardwalk.group, "dark_blue")
        self.assertEqual(boardwalk.price, 400)
        self.assertEqual(boardwalk.mortgage_value, 200)
        self.assertEqual(boardwalk.house_cost, 200)
        self.assertEqual(boardwalk.rent, (50, 200, 600, 1400, 1700, 2000))
        self.assertEqual(boardwalk.group_size, 2)

    def test_railroads_and_utilities_carry_their_rent_data(self) -> None:
        deeds = board()
        self.assertEqual(deeds[READING_RAILROAD].rent, (25, 50, 100, 200))
        self.assertEqual(deeds[READING_RAILROAD].group_size, 4)
        self.assertEqual(deeds[ELECTRIC_COMPANY].multipliers, (4, 10))
        self.assertEqual(deeds[ELECTRIC_COMPANY].group_size, 2)

    def test_new_deed_starts_unowned_and_undeveloped(self) -> None:
        boardwalk = board()[BOARDWALK]
        self.assertIsNone(boardwalk.owner)
        self.assertEqual(boardwalk.houses, 0)
        self.assertFalse(boardwalk.has_hotel)
        self.assertFalse(boardwalk.mortgaged)

    def test_non_deed_space_is_rejected(self) -> None:
        go = next(s for s in load_spaces() if s["type"] == "go")
        with self.assertRaises(ValueError):
            Property.from_space(go)

    def test_deeds_compare_by_identity(self) -> None:
        one, two = board()[BOARDWALK], board()[BOARDWALK]
        self.assertNotEqual(one, two)
        self.assertEqual(one, one)
        self.assertEqual(len({one, two, one}), 2)

    def test_repr_does_not_recurse_through_owner(self) -> None:
        boardwalk = board()[BOARDWALK]
        owned_by("Ada", boardwalk)
        self.assertIn("Boardwalk", repr(boardwalk))


class TestDeedValues(unittest.TestCase):
    def test_unmortgage_cost_adds_ten_percent_rounded_up(self) -> None:
        deeds = board()
        expected = {
            MEDITERRANEAN: 33,  # 30 + 10%
            ELECTRIC_COMPANY: 83,  # 75 + 10% = 82.5, rounded up
            READING_RAILROAD: 110,
            BOARDWALK: 220,
        }
        for index, cost in expected.items():
            with self.subTest(deed=deeds[index].name):
                self.assertEqual(deeds[index].unmortgage_cost, cost)

    def test_unmortgage_cost_is_never_below_the_mortgage_value(self) -> None:
        for prop in build_properties():
            with self.subTest(deed=prop.name):
                self.assertGreater(prop.unmortgage_cost, prop.mortgage_value)

    def test_build_cost_is_the_house_cost(self) -> None:
        deeds = board()
        self.assertEqual(deeds[MEDITERRANEAN].build_cost, 50)
        self.assertEqual(deeds[BOARDWALK].build_cost, 200)

    def test_building_level_and_counts(self) -> None:
        lot = board()[BOARDWALK]
        self.assertEqual(lot.building_level, 0)
        lot.houses = 3
        self.assertEqual(lot.building_level, 3)
        self.assertEqual(lot.house_count, 3)
        self.assertEqual(lot.hotel_count, 0)
        lot.houses = 0
        lot.has_hotel = True
        self.assertEqual(lot.building_level, HOTEL_LEVEL)
        self.assertEqual(lot.house_count, 0)
        self.assertEqual(lot.hotel_count, 1)

    def test_building_values(self) -> None:
        lot = board()[BOARDWALK]  # house_cost 200
        self.assertEqual(lot.buildings_value, 0)
        self.assertEqual(lot.building_sale_value, 0)
        lot.houses = MAX_HOUSES
        self.assertEqual(lot.buildings_value, 800)
        self.assertEqual(lot.building_sale_value, 400)
        lot.houses = 0
        lot.has_hotel = True
        self.assertEqual(lot.buildings_value, 1000)
        self.assertEqual(lot.building_sale_value, 500)


class TestPropertyRent(unittest.TestCase):
    def test_unowned_deed_collects_nothing(self) -> None:
        self.assertEqual(board()[BOARDWALK].current_rent(), 0)

    def test_base_rent_without_a_monopoly(self) -> None:
        deeds = board()
        owned_by("Ada", deeds[BOARDWALK])
        self.assertEqual(deeds[BOARDWALK].current_rent(), 50)

    def test_base_rent_doubles_with_a_monopoly(self) -> None:
        deeds = board()
        owned_by("Ada", deeds[BOARDWALK], deeds[PARK_PLACE])
        self.assertEqual(deeds[BOARDWALK].current_rent(), 100)
        self.assertEqual(deeds[PARK_PLACE].current_rent(), 70)

    def test_monopoly_double_survives_a_mortgage_elsewhere_in_the_group(self) -> None:
        deeds = board()
        owned_by("Ada", deeds[BOARDWALK], deeds[PARK_PLACE])
        deeds[PARK_PLACE].mortgaged = True
        self.assertEqual(deeds[BOARDWALK].current_rent(), 100)
        self.assertEqual(deeds[PARK_PLACE].current_rent(), 0)

    def test_split_group_pays_base_rent(self) -> None:
        deeds = board()
        owned_by("Ada", deeds[BOARDWALK])
        owned_by("Grace", deeds[PARK_PLACE])
        self.assertEqual(deeds[BOARDWALK].current_rent(), 50)
        self.assertEqual(deeds[PARK_PLACE].current_rent(), 35)

    def test_house_and_hotel_rent_follows_the_rent_table(self) -> None:
        deeds = board()
        boardwalk = deeds[BOARDWALK]
        owned_by("Ada", boardwalk, deeds[PARK_PLACE])
        for houses, rent in enumerate((200, 600, 1400, 1700), start=1):
            boardwalk.houses = houses
            with self.subTest(houses=houses):
                self.assertEqual(boardwalk.current_rent(), rent)
        boardwalk.houses = 0
        boardwalk.has_hotel = True
        self.assertEqual(boardwalk.current_rent(), 2000)

    def test_rent_table_is_used_for_every_colour_deed(self) -> None:
        deeds = board()
        by_group: dict[str, list[Property]] = {}
        for prop in deeds.values():
            by_group.setdefault(prop.group, []).append(prop)
        for group in COLOR_GROUPS:
            lots = by_group[group]
            owner = owned_by("Ada", *lots)
            for lot in lots:
                lot.houses = 2
                with self.subTest(deed=lot.name):
                    self.assertEqual(lot.current_rent(owner), lot.rent[2])

    def test_mortgaged_deed_collects_nothing_even_with_buildings(self) -> None:
        deeds = board()
        boardwalk = deeds[BOARDWALK]
        owned_by("Ada", boardwalk, deeds[PARK_PLACE])
        boardwalk.has_hotel = True
        boardwalk.mortgaged = True
        self.assertEqual(boardwalk.current_rent(), 0)

    def test_explicit_owner_argument_prices_a_hypothetical_owner(self) -> None:
        # Passing an owner asks "what would this deed earn in that hand?",
        # counting the deed itself as part of their holdings.
        deeds = board()
        ada = owned_by("Ada", deeds[BOARDWALK])
        challenger = owned_by("Grace", deeds[PARK_PLACE])
        self.assertEqual(deeds[BOARDWALK].current_rent(ada), 50)
        self.assertEqual(deeds[BOARDWALK].current_rent(challenger), 100)


class TestRailroadRent(unittest.TestCase):
    def test_rent_doubles_with_each_extra_railroad(self) -> None:
        for count, rent in enumerate((25, 50, 100, 200), start=1):
            deeds = board()
            held = [deeds[i] for i in RAILROAD_INDICES[:count]]
            owned_by("Ada", *held)
            with self.subTest(railroads=count):
                self.assertEqual(held[0].current_rent(), rent)

    def test_mortgaged_railroad_still_counts_toward_the_others(self) -> None:
        deeds = board()
        held = [deeds[i] for i in RAILROAD_INDICES]
        owned_by("Ada", *held)
        held[1].mortgaged = True
        self.assertEqual(held[0].current_rent(), 200)
        self.assertEqual(held[1].current_rent(), 0)

    def test_railroad_rent_ignores_the_dice(self) -> None:
        deeds = board()
        rr = deeds[READING_RAILROAD]
        owned_by("Ada", rr)
        self.assertEqual(rr.current_rent(dice_total=9), 25)


class TestUtilityRent(unittest.TestCase):
    def test_one_utility_charges_four_times_the_roll(self) -> None:
        deeds = board()
        electric = deeds[ELECTRIC_COMPANY]
        owned_by("Ada", electric)
        self.assertEqual(electric.current_rent(dice_total=7), 28)

    def test_both_utilities_charge_ten_times_the_roll(self) -> None:
        deeds = board()
        electric, water = deeds[ELECTRIC_COMPANY], deeds[WATER_WORKS]
        owned_by("Ada", electric, water)
        self.assertEqual(electric.current_rent(dice_total=7), 70)
        self.assertEqual(water.current_rent(dice_total=2), 20)

    def test_mortgaged_utility_still_counts_toward_the_other(self) -> None:
        deeds = board()
        electric, water = deeds[ELECTRIC_COMPANY], deeds[WATER_WORKS]
        owned_by("Ada", electric, water)
        water.mortgaged = True
        self.assertEqual(electric.current_rent(dice_total=5), 50)
        self.assertEqual(water.current_rent(dice_total=5), 0)

    def test_utility_rent_requires_the_dice_total(self) -> None:
        deeds = board()
        electric = deeds[ELECTRIC_COMPANY]
        owned_by("Ada", electric)
        with self.assertRaises(ValueError):
            electric.current_rent()

    def test_unowned_utility_needs_no_dice(self) -> None:
        self.assertEqual(board()[ELECTRIC_COMPANY].current_rent(), 0)


class TestGroupHelpers(unittest.TestCase):
    def test_properties_in_group_returns_board_order(self) -> None:
        deeds = build_properties()
        self.assertEqual(
            [p.index for p in properties_in_group(deeds, "railroad")],
            list(RAILROAD_INDICES),
        )
        self.assertEqual(
            [p.index for p in properties_in_group(deeds, "utility")],
            list(UTILITY_INDICES),
        )
        self.assertEqual(
            [p.name for p in properties_in_group(deeds, "dark_blue")],
            ["Park Place", "Boardwalk"],
        )

    def test_every_group_is_complete(self) -> None:
        deeds = build_properties()
        for group in (*COLOR_GROUPS, "railroad", "utility"):
            members = properties_in_group(deeds, group)
            with self.subTest(group=group):
                self.assertTrue(members)
                self.assertEqual(len(members), members[0].group_size)

    def test_build_properties_accepts_a_custom_space_list(self) -> None:
        spaces = [s for s in load_spaces() if s["index"] in (0, 1, 3, 4)]
        deeds = build_properties(spaces)
        self.assertEqual([d.index for d in deeds], [MEDITERRANEAN, BALTIC])


if __name__ == "__main__":
    unittest.main()
