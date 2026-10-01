"""Phase 5: two six-sided dice, with a short roll animation.

Two layers live here:

* the pure functions :func:`roll` and :func:`is_doubles`, which the rules need
  and which do not care about frames or clocks, and
* :class:`Dice`, a tiny state machine that spends
  :data:`ROLL_MS` milliseconds showing random faces before settling on the
  result. Phase 7's ``ROLLING`` state drives it: :meth:`Dice.start` once, then
  :meth:`Dice.update` every frame until it reports that the roll has settled.

The outcome is decided the moment the roll starts, not when the animation
ends, so how many frames the game manages to draw can never change what comes
up. The flicker faces are drawn from a *separate* generator for the same
reason: a seeded ``rng`` produces the same sequence of rolls whether the
animation ran for six frames or six hundred.
"""

from __future__ import annotations

import random
from typing import Optional

#: Faces on one die.
SIDES = 6

#: How long the roll animation lasts, in milliseconds.
ROLL_MS = 400

#: How long each set of random faces is shown during the animation.
FLICKER_MS = 60

#: What :attr:`Dice.faces` shows before the first roll of the game.
RESTING_FACES = (1, 1)


def roll(rng: Optional[random.Random] = None) -> tuple[int, int]:
    """Roll two dice, each 1--6.

    ``rng`` defaults to the :mod:`random` module's shared generator; pass a
    :class:`random.Random` to make a sequence of rolls reproducible.
    """
    source = rng if rng is not None else random
    return (source.randint(1, SIDES), source.randint(1, SIDES))


def is_doubles(d1: int, d2: int) -> bool:
    """Whether the two dice show the same face."""
    return d1 == d2


class Dice:
    """A pair of dice that animates before showing its result.

    Typical use from the game loop::

        dice.start(pygame.time.get_ticks())
        ...
        if dice.update(pygame.time.get_ticks()):
            move(dice.total)

    :meth:`update` returns ``True`` exactly once per roll -- on the frame the
    animation settles -- so the caller does not need its own "have I handled
    this roll yet" flag.

    A ``roll_ms`` of ``0`` settles on the first :meth:`update`, which is the
    instant (un-animated) mode.
    """

    def __init__(
        self,
        rng: Optional[random.Random] = None,
        *,
        roll_ms: int = ROLL_MS,
        flicker_ms: int = FLICKER_MS,
    ) -> None:
        if roll_ms < 0:
            raise ValueError("roll_ms cannot be negative")
        if flicker_ms <= 0:
            raise ValueError("flicker_ms must be positive")
        self.rng = rng if rng is not None else random.Random()
        self.roll_ms = roll_ms
        self.flicker_ms = flicker_ms
        #: Faces shown mid-roll come from their own generator, so consuming
        #: them never shifts the sequence :attr:`rng` produces.
        self._flicker_rng = random.Random()
        self._rolling = False
        self._start_ms = 0
        self._now = 0
        self._result: Optional[tuple[int, int]] = None
        self._flicker: list[tuple[int, int]] = []

    # --- state --------------------------------------------------------------
    @property
    def rolling(self) -> bool:
        """Whether the animation is still running."""
        return self._rolling

    @property
    def settled(self) -> bool:
        """Whether a finished roll is available to read."""
        return self._result is not None and not self._rolling

    @property
    def result(self) -> tuple[int, int]:
        """The two settled faces.

        Raises :class:`RuntimeError` before the first roll and while one is
        still in the air -- reading a result mid-animation is a bug in the
        caller, not a value worth inventing.
        """
        if not self.settled:
            raise RuntimeError("no settled roll to read")
        assert self._result is not None
        return self._result

    @property
    def total(self) -> int:
        """The settled roll's total; raises like :attr:`result`."""
        return sum(self.result)

    @property
    def doubles(self) -> bool:
        """Whether the settled roll was doubles; raises like :attr:`result`."""
        return is_doubles(*self.result)

    @property
    def faces(self) -> tuple[int, int]:
        """What to draw right now.

        Random faces while rolling, the result once settled, and
        :data:`RESTING_FACES` before the first roll of the game. Always safe
        to call -- unlike :attr:`result`, this is for the renderer.
        """
        if self._rolling:
            return self._flicker_face(self.elapsed)
        if self._result is not None:
            return self._result
        return RESTING_FACES

    @property
    def elapsed(self) -> int:
        """Milliseconds since :meth:`start`, clamped at zero."""
        return max(0, self._now - self._start_ms)

    @property
    def progress(self) -> float:
        """How far the animation has run, ``0.0``--``1.0``."""
        if not self._rolling or self.roll_ms <= 0:
            return 1.0
        return min(1.0, self.elapsed / self.roll_ms)

    # --- rolling ------------------------------------------------------------
    def start(self, now_ms: int = 0) -> None:
        """Begin a roll at ``now_ms`` (``pygame.time.get_ticks()``).

        The result is chosen here. Raises :class:`RuntimeError` if a roll is
        already in the air, so a double-fired Roll Dice button is caught
        rather than silently throwing a roll away.
        """
        if self._rolling:
            raise RuntimeError("a roll is already in progress")
        self._rolling = True
        self._start_ms = now_ms
        self._now = now_ms
        self._result = roll(self.rng)
        self._flicker = self._build_flicker()

    def update(self, now_ms: int) -> bool:
        """Advance the animation clock; ``True`` on the frame it settles.

        Returns ``False`` when no roll is in flight, so it is harmless to call
        every frame.
        """
        self._now = now_ms
        if not self._rolling:
            return False
        if self.elapsed < self.roll_ms:
            return False
        self._rolling = False
        return True

    def finish(self) -> bool:
        """Settle an in-flight roll immediately; ``True`` if one was skipped.

        Lets a click cut the animation short without disturbing the result.
        """
        if not self._rolling:
            return False
        self._rolling = False
        return True

    def reset(self) -> None:
        """Forget the current roll and any result (used by "Play Again")."""
        self._rolling = False
        self._result = None
        self._flicker = []
        self._start_ms = 0
        self._now = 0

    # --- animation ----------------------------------------------------------
    def _build_flicker(self) -> list[tuple[int, int]]:
        """Pre-draw one face pair per flicker step of the animation.

        Pre-drawing keeps :attr:`faces` a pure function of elapsed time -- the
        same millisecond always shows the same dice, however often the frame
        is redrawn. Consecutive steps are forced to differ so the animation
        never looks frozen.
        """
        steps = max(1, -(-self.roll_ms // self.flicker_ms))
        frames: list[tuple[int, int]] = []
        previous: Optional[tuple[int, int]] = None
        for _ in range(steps):
            faces = roll(self._flicker_rng)
            while faces == previous:
                faces = roll(self._flicker_rng)
            frames.append(faces)
            previous = faces
        return frames

    def _flicker_face(self, elapsed_ms: int) -> tuple[int, int]:
        if not self._flicker:
            return RESTING_FACES
        step = min(elapsed_ms // self.flicker_ms, len(self._flicker) - 1)
        return self._flicker[step]
