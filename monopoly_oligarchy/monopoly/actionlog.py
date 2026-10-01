"""Action logging: a written record of everything that happens to the board.

The HUD's :attr:`monopoly.game.Game.log` is a *narration* -- a couple of
hundred lines of prose for the player to read. This module is the other kind
of log: a full, timestamped, machine-greppable transcript of every action, on
disk, that survives the window closing. It exists so a question like "where
did that player's houses go?" has an answer that does not depend on anybody
having been watching at the time.

Three things live here.

* :func:`configure` opens the log file. ``main.py`` calls it once at startup;
  until it is called nothing is written anywhere, so the test suite and any
  importing script stay silent by default.
* :func:`event` writes one structured line -- ``category.action`` plus
  ``key=value`` fields. Every module that changes the board calls it.
* :func:`audit` is the safety net. It walks every deed and every wallet,
  compares them against the last time it looked, and writes down *every*
  difference it finds, whether or not anything logged it. A change that shows
  up in an audit with no matching ``event`` line above it is a change nothing
  in the code admits to making -- which is exactly the shape of a bug like
  "the houses disappeared". It also checks the two conservation laws the box
  imposes (32 houses and 12 hotels, on the board or in the bank, never any
  other number) and shouts at ``ERROR`` level when they are broken.

Nothing here raises. A logging call that fails must never take the game down
with it, so the audit reports what it finds and returns.
"""

from __future__ import annotations

import datetime as _dt
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

#: The root of this package's logger tree. Everything written goes under it.
LOGGER_NAME = "monopoly"

#: Buildings the box holds; the numbers :func:`audit` checks against.
HOUSE_SUPPLY = 32
HOTEL_SUPPLY = 12

#: Where logs go when nothing says otherwise, relative to the project root.
DEFAULT_LOG_DIR = "logs"

#: Environment overrides, so a log can be turned on without editing anything.
ENV_DIR = "MONOPOLY_LOG_DIR"
ENV_LEVEL = "MONOPOLY_LOG_LEVEL"
ENV_CONSOLE = "MONOPOLY_LOG_CONSOLE"

_LOG = logging.getLogger(LOGGER_NAME)
_LOG.addHandler(logging.NullHandler())

#: The file currently being written, or ``None`` before :func:`configure`.
_log_path: Optional[Path] = None
_configured = False

#: What the board looked like the last time :func:`audit` walked it, so the
#: next walk can report the difference. Keyed by deed index and player name.
_deed_census: dict[int, tuple[Optional[str], int, bool]] = {}
_purse_census: dict[str, tuple[int, int, bool]] = {}
_audit_count = 0


# --- opening the log --------------------------------------------------------
def configure(
    path: Optional[str | Path] = None,
    *,
    level: Optional[int | str] = None,
    console: Optional[bool] = None,
    directory: Optional[str | Path] = None,
) -> Optional[Path]:
    """Start writing the transcript; returns the file it landed in.

    Called once, from ``main.py``. Calling it again is a no-op -- the second
    call keeps the first call's file rather than opening a rival one.

    ``path`` names the file outright. Without one, a fresh timestamped file is
    opened in ``directory`` (default ``logs/`` beside the package, overridable
    with ``$MONOPOLY_LOG_DIR``). ``level`` defaults to ``$MONOPOLY_LOG_LEVEL``
    or ``DEBUG``; ``console`` mirrors everything at ``WARNING`` and above to
    stderr unless ``$MONOPOLY_LOG_CONSOLE`` says otherwise.

    Returns ``None`` -- and leaves logging switched off -- if the file cannot
    be opened. A read-only disk is not a reason to refuse to play.
    """
    global _configured, _log_path
    if _configured:
        return _log_path

    if level is None:
        level = os.environ.get(ENV_LEVEL, "DEBUG")
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.DEBUG)
    if console is None:
        console = _truthy(os.environ.get(ENV_CONSOLE))

    if path is None:
        base = Path(
            directory
            if directory is not None
            else os.environ.get(ENV_DIR) or _project_root() / DEFAULT_LOG_DIR
        )
        stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        path = base / f"monopoly-{stamp}.log"
    path = Path(path)

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.FileHandler(path, encoding="utf-8")
    except OSError as exc:  # pragma: no cover - depends on the filesystem
        print(f"[actionlog] could not open {path}: {exc}", file=sys.stderr)
        return None

    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s.%(msecs)03d %(levelname)-7s %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    _LOG.addHandler(handler)
    _LOG.setLevel(level)
    _LOG.propagate = False

    if console:
        stream = logging.StreamHandler(sys.stderr)
        stream.setLevel(logging.WARNING)
        stream.setFormatter(logging.Formatter("[monopoly] %(levelname)s %(message)s"))
        _LOG.addHandler(stream)

    _configured = True
    _log_path = path
    _LOG.info(
        "session.start file=%s level=%s pid=%s",
        path,
        logging.getLevelName(_LOG.level),
        os.getpid(),
    )
    return path


def log_path() -> Optional[Path]:
    """The file being written, or ``None`` while logging is off."""
    return _log_path


def is_configured() -> bool:
    """Whether :func:`configure` has opened a file."""
    return _configured


def reset_for_tests() -> None:
    """Forget every handler and every census. Only the test suite calls this."""
    global _configured, _log_path, _audit_count
    for handler in list(_LOG.handlers):
        if not isinstance(handler, logging.NullHandler):
            _LOG.removeHandler(handler)
            handler.close()
    _LOG.addHandler(logging.NullHandler())
    _configured = False
    _log_path = None
    _audit_count = 0
    _deed_census.clear()
    _purse_census.clear()


# --- writing a line ---------------------------------------------------------
def event(category: str, action: str, /, _level: int = logging.INFO, **fields: Any) -> None:
    """Write one ``category.action key=value ...`` line.

    ``fields`` are rendered in the order they are given; ``None`` values are
    dropped, so a caller can pass an optional creditor without branching. The
    severity argument is spelled ``_level`` -- and ``category`` / ``action``
    are positional-only -- so that a field may be called ``level`` (several
    are: a lot's building level) without colliding with it.
    """
    if not _LOG.isEnabledFor(_level):
        return
    _LOG.log(_level, "%-22s %s", f"{category}.{action}", _render(fields))


def debug(category: str, action: str, /, **fields: Any) -> None:
    """:func:`event` at ``DEBUG`` -- the fine-grained, high-volume detail."""
    event(category, action, logging.DEBUG, **fields)


def warn(category: str, action: str, /, **fields: Any) -> None:
    """:func:`event` at ``WARNING`` -- something happened that should not."""
    event(category, action, logging.WARNING, **fields)


def error(category: str, action: str, /, **fields: Any) -> None:
    """:func:`event` at ``ERROR`` -- an invariant is broken."""
    event(category, action, logging.ERROR, **fields)


def exception(category: str, action: str, /, **fields: Any) -> None:
    """An ``ERROR`` line with the current traceback under it."""
    if not _LOG.isEnabledFor(logging.ERROR):
        return
    _LOG.error("%-22s %s", f"{category}.{action}", _render(fields), exc_info=True)


def where(depth: int = 2, frames: int = 3) -> str:
    """``"file:line > file:line"`` for the callers above this one.

    Handed to :func:`audit` so an unexplained change carries the code path
    that noticed it. Cheap enough to call on every commit, not on every step.
    """
    stack = traceback.extract_stack()[:-1]  # drop this frame
    picked = stack[max(0, len(stack) - depth - frames) : len(stack) - depth + 1]
    return " > ".join(f"{Path(f.filename).name}:{f.lineno}" for f in picked)


# --- the safety net ---------------------------------------------------------
def deed_state(deed: Any) -> str:
    """One deed in a field: ``"Boardwalk[owner=Ada level=3 mortgaged=no]"``."""
    owner = getattr(deed.owner, "name", None)
    return (
        f"{deed.name}[owner={owner or '-'} "
        f"level={_level_of(deed)} mortgaged={'yes' if deed.mortgaged else 'no'}]"
    )


def census(properties: Iterable[Any]) -> str:
    """Every built lot on the board, in board order, as one field value.

    Bare lots are left out: a census of a mid-game board is a handful of
    entries, not forty, and a lot that vanishes from it is what a reader is
    looking for.
    """
    built = [
        f"{deed.name}={_level_name(deed)}@{getattr(deed.owner, 'name', '-')}"
        for deed in sorted(properties, key=lambda d: d.index)
        if _level_of(deed) > 0
    ]
    return ", ".join(built) if built else "(none)"


def buildings_of(player: Any) -> str:
    """One player's built lots, for the per-turn snapshot."""
    built = [
        f"{deed.name}={_level_name(deed)}"
        for deed in sorted(player.properties, key=lambda d: d.index)
        if _level_of(deed) > 0
    ]
    return ", ".join(built) if built else "(none)"


def standing(properties: Iterable[Any]) -> tuple[int, int]:
    """``(houses, hotels)`` standing on ``properties`` right now."""
    props = list(properties)
    houses = sum(_level_of(d) for d in props if _level_of(d) < 5)
    hotels = sum(1 for d in props if _level_of(d) == 5)
    return houses, hotels


def audit(
    bank: Any,
    properties: Sequence[Any],
    at: str,
    players: Optional[Sequence[Any]] = None,
    *,
    trace: bool = False,
) -> list[str]:
    """Walk the whole board, report every change since the last walk.

    Returns the list of differences found, and writes them to the log:

    * a deed whose owner, building level or mortgage flag moved since the
      previous audit -- at ``INFO``, so it can be read against the ``event``
      lines above it. **A building change here with no matching
      ``build.*`` / ``bankruptcy.*`` / ``trade.*`` event above it is a bug**;
    * a wallet whose cash moved, likewise;
    * either conservation law broken -- at ``ERROR``.

    ``at`` says where the walk was made from ("turn.start", "build.commit"),
    which is what turns "a house went missing" into "a house went missing
    between these two points". ``trace=True`` attaches the call stack.
    """
    global _audit_count
    if not _LOG.isEnabledFor(logging.INFO):
        return []
    _audit_count += 1
    changes: list[str] = []

    try:
        for deed in sorted(properties, key=lambda d: d.index):
            now = (
                getattr(deed.owner, "name", None),
                _level_of(deed),
                bool(deed.mortgaged),
            )
            was = _deed_census.get(deed.index)
            _deed_census[deed.index] = now
            if was is None or was == now:
                continue
            changes.append(f"{deed.name}: {_describe(was)} -> {_describe(now)}")

        for player in players or []:
            now = (
                int(player.cash),
                int(len(player.properties)),
                bool(player.is_bankrupt),
            )
            was = _purse_census.get(player.name)
            _purse_census[player.name] = now
            if was is None or was == now:
                continue
            changes.append(
                f"{player.name}: cash ${was[0]:,}->${now[0]:,} "
                f"deeds {was[1]}->{now[1]}"
                + (" BANKRUPT" if now[2] and not was[2] else "")
            )

        houses, hotels = standing(properties)
        bank_houses = int(getattr(bank, "houses", 0))
        bank_hotels = int(getattr(bank, "hotels", 0))

        if changes:
            event(
                "audit",
                "changed",
                at=at,
                n=len(changes),
                changes="; ".join(changes),
                trace=where() if trace else None,
            )
        else:
            debug("audit", "clean", at=at, seq=_audit_count)

        debug(
            "audit",
            "stock",
            at=at,
            board_houses=houses,
            board_hotels=hotels,
            bank_houses=bank_houses,
            bank_hotels=bank_hotels,
        )

        if houses + bank_houses != HOUSE_SUPPLY:
            error(
                "audit",
                "house_supply_broken",
                at=at,
                expected=HOUSE_SUPPLY,
                found=houses + bank_houses,
                on_board=houses,
                in_bank=bank_houses,
                census=census(properties),
                trace=where(),
            )
        if hotels + bank_hotels != HOTEL_SUPPLY:
            error(
                "audit",
                "hotel_supply_broken",
                at=at,
                expected=HOTEL_SUPPLY,
                found=hotels + bank_hotels,
                on_board=hotels,
                in_bank=bank_hotels,
                census=census(properties),
                trace=where(),
            )
    except Exception:  # pragma: no cover - the audit never breaks the game
        exception("audit", "failed", at=at)

    return changes


def forget_board() -> None:
    """Drop the remembered census, so a new game starts from a blank slate."""
    _deed_census.clear()
    _purse_census.clear()


# --- helpers ----------------------------------------------------------------
def _level_of(deed: Any) -> int:
    return 5 if deed.has_hotel else int(deed.houses)


def _level_name(deed: Any) -> str:
    level = _level_of(deed)
    return "hotel" if level == 5 else f"{level}h"


def _describe(state: tuple[Optional[str], int, bool]) -> str:
    owner, level, mortgaged = state
    label = "hotel" if level == 5 else f"{level}h"
    return f"({owner or '-'}, {label}{', mortgaged' if mortgaged else ''})"


def _render(fields: dict[str, Any]) -> str:
    return " ".join(
        f"{key}={_value(val)}" for key, val in fields.items() if val is not None
    )


def _value(val: Any) -> str:
    if isinstance(val, bool):
        return "yes" if val else "no"
    if isinstance(val, int):
        return f"{val:,}"
    text = str(val)
    return f"{text!r}" if " " in text and not text.startswith("(") else text


def _truthy(text: Optional[str]) -> bool:
    return bool(text) and text.strip().lower() not in {"0", "false", "no", "off"}


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent
