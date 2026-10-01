"""Phase 1 tests: the project scaffold and runtime environment.

These are cheap smoke tests that catch a broken checkout or a test run
launched outside the pygame environment (the ``angry_goodall`` container).
"""

from __future__ import annotations

import importlib
import json
import unittest
from pathlib import Path

from monopoly.data_loader import DATA_DIR

PROJECT_ROOT = Path(__file__).resolve().parent.parent

EXPECTED_DIRS = (
    "monopoly",
    "monopoly/data",
    "monopoly/ui",
    "monopoly/assets/tokens",
    "tests",
)

DATA_FILES = ("spaces.json", "chance.json", "community_chest.json")


class TestScaffold(unittest.TestCase):
    def test_expected_directories_exist(self) -> None:
        for relative in EXPECTED_DIRS:
            with self.subTest(directory=relative):
                self.assertTrue((PROJECT_ROOT / relative).is_dir())

    def test_packages_are_importable(self) -> None:
        for module in ("monopoly", "monopoly.ui", "monopoly.data_loader"):
            with self.subTest(module=module):
                self.assertIsNotNone(importlib.import_module(module))

    def test_data_files_exist_and_are_valid_json(self) -> None:
        for filename in DATA_FILES:
            path = DATA_DIR / filename
            with self.subTest(file=filename):
                self.assertTrue(path.is_file())
                with open(path, encoding="utf-8") as handle:
                    self.assertIsInstance(json.load(handle), list)


class TestEnvironment(unittest.TestCase):
    def test_pygame_is_available(self) -> None:
        try:
            import pygame
        except ImportError:  # pragma: no cover - environment failure path
            self.fail(
                "pygame is not importable. Run the tests inside the project's "
                "pygame container: ./run_tests.sh"
            )
        self.assertTrue(pygame.version.ver)

    def test_pygame_can_initialise_headless(self) -> None:
        import os

        import pygame

        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        pygame.display.init()
        try:
            surface = pygame.display.set_mode((1280, 800))
            self.assertEqual(surface.get_size(), (1280, 800))
        finally:
            pygame.display.quit()

    def test_font_module_works(self) -> None:
        import pygame

        from monopoly.ui import theme

        pygame.font.init()
        try:
            font = pygame.font.SysFont("monospace", 16)
            self.assertGreater(font.size("Boardwalk")[0], 0)
        finally:
            pygame.font.quit()
            # Shutting the font module down frees every Font object with it,
            # including any the UI theme cached for a later test module.
            theme.clear_font_cache()


if __name__ == "__main__":
    unittest.main()
