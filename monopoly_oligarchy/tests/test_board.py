"""Phase 4 tests: board geometry and the board surface.

The geometry half is pure arithmetic and needs no pygame display; the drawing
half renders onto plain ``Surface`` objects and reads pixels back, so it runs
headless in the ``angry_goodall`` container like every other suite here.
"""

from __future__ import annotations

import unittest

import pygame

from monopoly.board import (
    BOARD_PIXELS,
    BOTTOM,
    CORNER_SIZE,
    HOUSE_SIZE,
    LEFT,
    RIGHT,
    SPACE_WIDTH,
    STRIP_DEPTH,
    TOKEN_RADIUS,
    TOP,
    Board,
    body_rect,
    building_rects,
    display_name,
    group_color,
    is_corner,
    owner_pip_rect,
    rotation_of,
    side_of,
    space_at_point,
    space_label,
    space_rect,
    strip_rect,
    token_positions,
)
from monopoly.data_loader import BOARD_SIZE, load_spaces
from monopoly.player import Player
from monopoly.property import build_properties
from monopoly.ui.theme import (
    GROUP_COLORS,
    HOTEL_COLOR,
    HOUSE_COLOR,
    MORTGAGE_TINT,
    TOKEN_RGB,
    clear_font_cache,
    ellipsize,
    fit_text,
    get_font,
    wrap_text,
)

ALL = range(BOARD_SIZE)
BOARD_CENTRE = (BOARD_PIXELS // 2, BOARD_PIXELS // 2)


def rgb(surface: pygame.Surface, pos) -> tuple[int, int, int]:
    return tuple(surface.get_at(pos))[:3]


def colors_in(surface: pygame.Surface, rect: pygame.Rect) -> set:
    return {
        rgb(surface, (x, y))
        for x in range(rect.left, rect.right)
        for y in range(rect.top, rect.bottom)
    }


class TestGeometry(unittest.TestCase):
    def test_every_space_has_a_rect_inside_the_board(self) -> None:
        board = pygame.Rect(0, 0, BOARD_PIXELS, BOARD_PIXELS)
        for index in ALL:
            with self.subTest(index=index):
                self.assertTrue(board.contains(space_rect(index)))

    def test_index_must_be_on_the_board(self) -> None:
        for bad in (-1, BOARD_SIZE, 999):
            with self.subTest(index=bad):
                with self.assertRaises(ValueError):
                    space_rect(bad)

    def test_corners_are_square_and_in_the_four_corners(self) -> None:
        far = BOARD_PIXELS - CORNER_SIZE
        expected = {
            0: (far, far),  # Go, bottom right
            10: (0, far),  # Jail, bottom left
            20: (0, 0),  # Free Parking, top left
            30: (far, 0),  # Go To Jail, top right
        }
        for index, topleft in expected.items():
            with self.subTest(index=index):
                rect = space_rect(index)
                self.assertEqual(rect.topleft, topleft)
                self.assertEqual(rect.size, (CORNER_SIZE, CORNER_SIZE))
                self.assertTrue(is_corner(index))

    def test_side_spaces_are_narrow_rectangles(self) -> None:
        for index in ALL:
            if is_corner(index):
                continue
            rect = space_rect(index)
            long_side = (SPACE_WIDTH, CORNER_SIZE)
            with self.subTest(index=index):
                self.assertFalse(is_corner(index))
                if side_of(index) in (BOTTOM, TOP):
                    self.assertEqual(rect.size, long_side)
                else:
                    self.assertEqual(rect.size, long_side[::-1])

    def test_sides_hold_ten_spaces_each(self) -> None:
        counts = {BOTTOM: 0, LEFT: 0, TOP: 0, RIGHT: 0}
        for index in ALL:
            counts[side_of(index)] += 1
        self.assertEqual(counts, {BOTTOM: 11, LEFT: 9, TOP: 11, RIGHT: 9})

    def test_no_two_spaces_overlap(self) -> None:
        rects = [space_rect(i) for i in ALL]
        for i in ALL:
            for j in range(i + 1, BOARD_SIZE):
                with self.subTest(a=i, b=j):
                    self.assertFalse(rects[i].colliderect(rects[j]))

    def test_the_ring_is_gapless(self) -> None:
        """Consecutive spaces touch, and the ring closes at Go."""
        for index in ALL:
            following = space_rect((index + 1) % BOARD_SIZE)
            with self.subTest(index=index):
                self.assertTrue(space_rect(index).inflate(2, 2).colliderect(following))

    def test_the_ring_covers_the_border_of_the_board(self) -> None:
        ring = sum(space_rect(i).width * space_rect(i).height for i in ALL)
        centre = BOARD_PIXELS - 2 * CORNER_SIZE
        self.assertEqual(ring, BOARD_PIXELS**2 - centre**2)

    def test_board_order_runs_anticlockwise_from_go(self) -> None:
        """Go bottom right, then leftwards along the bottom and up the left."""
        self.assertLess(space_rect(1).left, space_rect(0).left)
        self.assertLess(space_rect(9).left, space_rect(1).left)
        self.assertLess(space_rect(19).top, space_rect(11).top)
        self.assertGreater(space_rect(29).left, space_rect(21).left)
        self.assertGreater(space_rect(39).top, space_rect(31).top)

    def test_labels_turn_to_face_the_centre(self) -> None:
        self.assertEqual(rotation_of(1), 0)
        self.assertEqual(rotation_of(11), -90)
        self.assertEqual(rotation_of(21), 180)
        self.assertEqual(rotation_of(31), 90)


class TestStripsAndBodies(unittest.TestCase):
    def test_strip_sits_on_the_inner_edge(self) -> None:
        for index in ALL:
            rect, strip = space_rect(index), strip_rect(index)
            with self.subTest(index=index):
                self.assertTrue(rect.contains(strip))
                # Of the strip's two long edges, the one nearer the board
                # centre is the space's own edge.
                self.assertLess(
                    _distance_to_centre(strip.center), _distance_to_centre(rect.center)
                )

    def test_owner_pip_sits_on_the_outer_edge(self) -> None:
        for index in ALL:
            rect, pip = space_rect(index), owner_pip_rect(index)
            with self.subTest(index=index):
                self.assertTrue(rect.contains(pip))
                self.assertGreater(
                    _distance_to_centre(pip.center), _distance_to_centre(rect.center)
                )

    def test_body_is_what_the_strip_leaves(self) -> None:
        for index in ALL:
            rect, strip, body = space_rect(index), strip_rect(index), body_rect(index)
            with self.subTest(index=index):
                self.assertTrue(rect.contains(body))
                self.assertFalse(body.colliderect(strip))
                self.assertEqual(
                    body.width * body.height + strip.width * strip.height,
                    rect.width * rect.height,
                )

    def test_a_space_without_a_deed_uses_its_whole_body(self) -> None:
        self.assertEqual(body_rect(7, strip=False), space_rect(7))

    def test_strip_depth_is_uniform(self) -> None:
        for index in ALL:
            with self.subTest(index=index):
                self.assertEqual(min(strip_rect(index).size), STRIP_DEPTH)


class TestSpaceAtPoint(unittest.TestCase):
    def test_each_space_is_found_at_its_own_centre(self) -> None:
        for index in ALL:
            with self.subTest(index=index):
                self.assertEqual(space_at_point(space_rect(index).center), index)

    def test_the_middle_of_the_board_is_no_space(self) -> None:
        self.assertIsNone(space_at_point(BOARD_CENTRE))

    def test_off_the_board_is_no_space(self) -> None:
        self.assertIsNone(space_at_point((BOARD_PIXELS + 40, 10)))
        self.assertIsNone(space_at_point((-5, -5)))

    def test_corner_pixels_belong_to_the_corner_spaces(self) -> None:
        self.assertEqual(space_at_point((0, 0)), 20)
        self.assertEqual(space_at_point((BOARD_PIXELS - 1, BOARD_PIXELS - 1)), 0)


class TestTokenPositions(unittest.TestCase):
    def test_no_players_no_tokens(self) -> None:
        self.assertEqual(token_positions(0, 0), [])

    def test_one_token_sits_in_the_middle_of_the_body(self) -> None:
        self.assertEqual(token_positions(0, 1), [body_rect(0).center])

    def test_tokens_never_share_a_spot(self) -> None:
        for index in ALL:
            for count in range(1, 7):
                with self.subTest(index=index, count=count):
                    spots = token_positions(index, count)
                    self.assertEqual(len(spots), count)
                    self.assertEqual(len(set(spots)), count)

    def test_tokens_stay_inside_the_space(self) -> None:
        for index in ALL:
            for count in range(1, 7):
                body = body_rect(index)
                for x, y in token_positions(index, count):
                    with self.subTest(index=index, count=count, spot=(x, y)):
                        token = pygame.Rect(
                            x - TOKEN_RADIUS,
                            y - TOKEN_RADIUS,
                            2 * TOKEN_RADIUS,
                            2 * TOKEN_RADIUS,
                        )
                        self.assertTrue(body.contains(token))

    def test_tokens_stack_onto_a_second_row(self) -> None:
        spots = token_positions(0, 6)
        rows = {y for _, y in spots}
        self.assertEqual(len(rows), 2)
        self.assertEqual(len({x for x, _ in spots}), 3)


class TestBuildingRects(unittest.TestCase):
    def test_nothing_built_draws_nothing(self) -> None:
        self.assertEqual(building_rects(1, 0, False), [])

    def test_houses_line_up_on_the_strip(self) -> None:
        for index in (1, 11, 21, 31):
            for houses in range(1, 5):
                with self.subTest(index=index, houses=houses):
                    rects = building_rects(index, houses, False)
                    self.assertEqual(len(rects), houses)
                    strip = strip_rect(index)
                    for rect in rects:
                        self.assertEqual(rect.size, (HOUSE_SIZE, HOUSE_SIZE))
                        self.assertTrue(strip.contains(rect))
                    for a, b in zip(rects, rects[1:]):
                        self.assertFalse(a.colliderect(b))

    def test_a_hotel_replaces_the_houses(self) -> None:
        rects = building_rects(1, 4, True)
        self.assertEqual(len(rects), 1)
        self.assertTrue(strip_rect(1).contains(rects[0]))

    def test_markers_follow_the_strip_orientation(self) -> None:
        bottom = building_rects(1, 4, True)[0]
        left = building_rects(11, 4, True)[0]
        self.assertGreater(bottom.width, bottom.height)
        self.assertGreater(left.height, left.width)


class TestLabels(unittest.TestCase):
    def setUp(self) -> None:
        self.spaces = load_spaces()

    def test_every_space_has_a_title(self) -> None:
        for space in self.spaces:
            with self.subTest(index=space["index"]):
                title, _ = space_label(space)
                self.assertTrue(title.strip())

    def test_deeds_are_labelled_with_their_price(self) -> None:
        self.assertEqual(space_label(self.spaces[1]), ("Mediterranean Avenue", "$60"))
        self.assertEqual(space_label(self.spaces[5]), ("Reading RR", "$200"))
        self.assertEqual(space_label(self.spaces[12]), ("Electric Co.", "$150"))

    def test_tax_shows_what_it_costs(self) -> None:
        self.assertEqual(space_label(self.spaces[4]), ("Income Tax", "PAY $200"))
        self.assertEqual(space_label(self.spaces[38]), ("Luxury Tax", "PAY $100"))

    def test_special_spaces_are_labelled(self) -> None:
        self.assertEqual(space_label(self.spaces[0])[0], "GO")
        self.assertEqual(space_label(self.spaces[10])[0], "JAIL")
        self.assertEqual(space_label(self.spaces[20])[0], "FREE PARKING")
        self.assertEqual(space_label(self.spaces[30])[0], "GO TO JAIL")
        self.assertEqual(space_label(self.spaces[7])[0], "CHANCE")
        self.assertEqual(space_label(self.spaces[2])[0], "COMMUNITY CHEST")

    def test_only_long_deed_names_are_abbreviated(self) -> None:
        self.assertEqual(display_name(self.spaces[15]), "Penn. RR")
        self.assertEqual(display_name(self.spaces[28]), "Water Works")
        self.assertEqual(display_name(self.spaces[39]), "Boardwalk")

    def test_strip_colour_comes_from_the_group(self) -> None:
        self.assertEqual(group_color(self.spaces[1]), GROUP_COLORS["brown"])
        self.assertEqual(group_color(self.spaces[5]), GROUP_COLORS["railroad"])
        self.assertEqual(group_color(self.spaces[12]), GROUP_COLORS["utility"])
        for index in (0, 2, 4, 7, 10, 20, 30):
            with self.subTest(index=index):
                self.assertIsNone(group_color(self.spaces[index]))


class TestTextFitting(unittest.TestCase):
    """The helpers that squeeze a property name into a 64px space."""

    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        clear_font_cache()

    def test_wrapping_breaks_on_spaces(self) -> None:
        font = get_font(12)
        lines = wrap_text("St. Charles Place", font, font.size("St. Charles")[0])
        self.assertEqual(lines, ["St. Charles", "Place"])

    def test_a_word_too_long_for_the_line_is_split(self) -> None:
        font = get_font(12)
        lines = wrap_text("Mediterranean", font, font.size("Medi")[0])
        self.assertGreater(len(lines), 1)
        self.assertEqual("".join(lines), "Mediterranean")

    def test_empty_text_wraps_to_nothing(self) -> None:
        self.assertEqual(wrap_text("   ", get_font(12), 100), [])

    def test_fitting_shrinks_until_whole_words_fit(self) -> None:
        font, lines = fit_text("Mediterranean Avenue", 58, 80)
        self.assertEqual(lines, ["Mediterranean", "Avenue"])
        self.assertLessEqual(font.size("Mediterranean")[0], 58)

    def test_fitting_keeps_short_names_large(self) -> None:
        big, _ = fit_text("Go", 58, 80)
        small, _ = fit_text("Mediterranean Avenue", 58, 80)
        self.assertGreater(big.get_height(), small.get_height())

    def test_an_impossible_box_still_returns_a_font(self) -> None:
        font, lines = fit_text("Boardwalk", 4, 4)
        self.assertIsNotNone(font)
        self.assertTrue(lines)

    # ``ellipsize`` moved here from the HUD in Phase 9, so the build screen
    # could cut a lot's name the same way the deed list does.
    def test_a_name_that_fits_is_left_alone(self) -> None:
        font = get_font(16)
        self.assertEqual(ellipsize("Boardwalk", font, 500), "Boardwalk")

    def test_a_name_that_does_not_fit_is_cut_short(self) -> None:
        font = get_font(16)
        width = font.size("Mediterranean")[0]
        cut = ellipsize("Mediterranean Avenue", font, width)
        self.assertTrue(cut.endswith("..."))
        self.assertLessEqual(font.size(cut)[0], width)

    def test_no_room_at_all_prints_nothing(self) -> None:
        self.assertEqual(ellipsize("Boardwalk", get_font(16), 0), "")
        self.assertEqual(ellipsize("Boardwalk", get_font(16), 1), "")


class BoardSurfaceTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        pygame.init()
        clear_font_cache()

    def setUp(self) -> None:
        self.board = Board()
        self.properties = build_properties()
        self.deeds = {p.index: p for p in self.properties}
        self.ada = Player("Ada", 1500, "red")
        self.bob = Player("Bob", 1500, "blue")


class TestBoardSurface(BoardSurfaceTestCase):
    def test_board_needs_forty_spaces(self) -> None:
        with self.assertRaises(ValueError):
            Board(load_spaces()[:39])

    def test_surface_is_the_planned_size(self) -> None:
        self.assertEqual(self.board.size, (BOARD_PIXELS, BOARD_PIXELS))
        self.assertEqual(self.board.base_surface.get_size(), self.board.size)
        self.assertEqual(self.board.render().get_size(), self.board.size)

    def test_space_lookup(self) -> None:
        self.assertEqual(self.board.space(39)["name"], "Boardwalk")
        with self.assertRaises(ValueError):
            self.board.space(40)

    def test_strips_are_painted_in_group_colours(self) -> None:
        surface = self.board.base_surface
        for index, group in ((1, "brown"), (39, "dark_blue"), (5, "railroad")):
            with self.subTest(index=index):
                self.assertIn(
                    GROUP_COLORS[group], colors_in(surface, strip_rect(index))
                )

    def test_spaces_without_deeds_have_no_strip_colour(self) -> None:
        surface = self.board.base_surface
        strip_colours = colors_in(surface, strip_rect(4))
        for colour in GROUP_COLORS.values():
            with self.subTest(colour=colour):
                self.assertNotIn(colour, strip_colours)


class TestCaching(BoardSurfaceTestCase):
    def test_the_static_board_is_drawn_once(self) -> None:
        for _ in range(5):
            self.board.base_surface
            self.board.render([self.ada], self.properties)
        self.assertEqual(self.board.base_builds, 1)

    def test_an_unchanged_frame_is_reused(self) -> None:
        first = self.board.render([self.ada], self.properties)
        second = self.board.render([self.ada], self.properties)
        self.assertIs(first, second)
        self.assertEqual(self.board.composite_builds, 1)

    def test_moving_a_token_redraws(self) -> None:
        self.board.render([self.ada], self.properties)
        self.ada.position = 24
        self.board.render([self.ada], self.properties)
        self.assertEqual(self.board.composite_builds, 2)

    def test_building_a_house_redraws(self) -> None:
        self.board.render([self.ada], self.properties)
        self.deeds[1].houses = 1
        self.board.render([self.ada], self.properties)
        self.assertEqual(self.board.composite_builds, 2)

    def test_mortgaging_redraws(self) -> None:
        self.board.render([self.ada], self.properties)
        self.deeds[1].mortgaged = True
        self.board.render([self.ada], self.properties)
        self.assertEqual(self.board.composite_builds, 2)

    def test_a_deed_changing_hands_redraws(self) -> None:
        self.board.render([self.ada], self.properties)
        self.ada.add_property(self.deeds[1])
        self.board.render([self.ada], self.properties)
        self.assertEqual(self.board.composite_builds, 2)

    def test_a_player_joining_redraws(self) -> None:
        self.board.render([self.ada], self.properties)
        self.board.render([self.ada, self.bob], self.properties)
        self.assertEqual(self.board.composite_builds, 2)

    def test_mark_dirty_forces_a_redraw(self) -> None:
        self.board.render([self.ada], self.properties)
        self.board.mark_dirty()
        self.board.render([self.ada], self.properties)
        self.assertEqual(self.board.composite_builds, 2)
        # ...but the static art survives it.
        self.assertEqual(self.board.base_builds, 1)


class TestOccupants(BoardSurfaceTestCase):
    def test_players_group_by_space(self) -> None:
        self.bob.position = 24
        self.assertEqual(
            Board.occupants([self.ada, self.bob]), {0: [self.ada], 24: [self.bob]}
        )

    def test_players_on_one_space_share_an_entry(self) -> None:
        self.assertEqual(
            Board.occupants([self.ada, self.bob]), {0: [self.ada, self.bob]}
        )

    def test_bankrupt_players_have_left_the_board(self) -> None:
        self.bob.is_bankrupt = True
        self.assertEqual(Board.occupants([self.ada, self.bob]), {0: [self.ada]})


class TestDynamicLayer(BoardSurfaceTestCase):
    def test_a_token_is_drawn_where_it_stands(self) -> None:
        self.ada.position = 24
        surface = self.board.render([self.ada], self.properties)
        self.assertEqual(
            rgb(surface, token_positions(24, 1)[0]), TOKEN_RGB["red"]
        )

    def test_players_sharing_a_space_both_show(self) -> None:
        self.ada.position = self.bob.position = 20
        surface = self.board.render([self.ada, self.bob], self.properties)
        first, second = token_positions(20, 2)
        self.assertEqual(rgb(surface, first), TOKEN_RGB["red"])
        self.assertEqual(rgb(surface, second), TOKEN_RGB["blue"])

    def test_a_bankrupt_player_is_not_drawn(self) -> None:
        self.ada.position = 24
        self.ada.is_bankrupt = True
        surface = self.board.render([self.ada], self.properties)
        self.assertNotIn(TOKEN_RGB["red"], colors_in(surface, space_rect(24)))

    def test_an_owner_pip_marks_the_deed(self) -> None:
        self.ada.add_property(self.deeds[1])
        surface = self.board.render([self.ada], self.properties)
        self.assertIn(TOKEN_RGB["red"], colors_in(surface, owner_pip_rect(1)))

    def test_an_unowned_deed_has_no_pip(self) -> None:
        surface = self.board.render([self.ada], self.properties)
        self.assertNotIn(TOKEN_RGB["red"], colors_in(surface, owner_pip_rect(1)))

    def test_houses_appear_on_the_strip(self) -> None:
        self.ada.add_property(self.deeds[1])
        self.deeds[1].houses = 3
        surface = self.board.render([self.ada], self.properties)
        for rect in building_rects(1, 3, False):
            with self.subTest(rect=rect):
                self.assertEqual(rgb(surface, rect.center), HOUSE_COLOR)

    def test_a_hotel_is_drawn_in_its_own_colour(self) -> None:
        self.ada.add_property(self.deeds[3])
        self.deeds[3].has_hotel = True
        surface = self.board.render([self.ada], self.properties)
        self.assertEqual(rgb(surface, building_rects(3, 0, True)[0].center), HOTEL_COLOR)

    def test_a_mortgaged_strip_is_greyed_out(self) -> None:
        self.ada.add_property(self.deeds[1])
        self.deeds[1].mortgaged = True
        surface = self.board.render([self.ada], self.properties)
        colours = colors_in(surface, strip_rect(1))
        self.assertIn(MORTGAGE_TINT, colours)
        self.assertNotIn(GROUP_COLORS["brown"], colours)

    def test_the_static_board_is_never_scribbled_on(self) -> None:
        """The dynamic layer draws onto a copy, so tokens do not accumulate."""
        self.ada.position = 24
        self.board.render([self.ada], self.properties)
        self.assertNotIn(TOKEN_RGB["red"], colors_in(self.board.base_surface, space_rect(24)))


def _distance_to_centre(point) -> float:
    dx = point[0] - BOARD_CENTRE[0]
    dy = point[1] - BOARD_CENTRE[1]
    return (dx * dx + dy * dy) ** 0.5


if __name__ == "__main__":
    unittest.main()
