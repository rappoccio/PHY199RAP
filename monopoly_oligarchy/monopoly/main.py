"""Entry point: the Game Manager setup screen, then the game.

    python3 -m monopoly.main

The loop carries six modal surfaces -- the popup, the build screen, an
auction, a trade, the mortgage screen and Phase 14's win screen -- and the game
guarantees at most one of them is up at a time, so :func:`_modal` hands the
renderer whichever is showing.

:func:`play` is the outer loop around all of it: setup screen, game, win
screen, and round again whenever Play Again is pressed.

Phase 7 replaced the board *preview* with the real turn loop. This module owns
the window and the pygame event loop and nothing else: events go into
:class:`monopoly.game.Game` (as an :class:`~monopoly.game.Action`, or as the
key of a :class:`~monopoly.game.Prompt` choice) and the frame is drawn from
what the game reports back. Every rule lives in ``game.py``.

Keyboard shortcuts for the two common actions: space rolls, Enter ends the
turn, Esc quits.
"""

from __future__ import annotations

import sys
from typing import Optional

import pygame

from monopoly import actionlog, game_manager
from monopoly.board import Board
from monopoly.game import Action, Game, State
from monopoly.headless import bot_step
from monopoly.player import Player
from monopoly.ui.auction_screen import BID, AuctionScreen
from monopoly.ui.build_screen import CONFIRM, BuildScreen
from monopoly.ui.hud import Hud, HudState
from monopoly.ui.mortgage_screen import CONFIRM as MORTGAGE_CONFIRM
from monopoly.ui.mortgage_screen import MortgageScreen
from monopoly.ui.popup import Popup
from monopoly.ui.renderer import HUD_RECT, Renderer
from monopoly.ui.theme import SCREEN_SIZE
from monopoly.ui.trade_screen import ACCEPT, PROPOSE, REJECT, TradeScreen
from monopoly.ui.win_screen import PLAY_AGAIN, WinScreen, WinState, describe_result

FPS = 60
#: Milliseconds between consecutive bot actions so a human can follow the game.
BOT_DELAY_MS = 700

#: Keys that stand in for the two primary buttons.
KEY_ACTIONS = {
    pygame.K_SPACE: Action.ROLL,
    pygame.K_RETURN: Action.END_TURN,
    pygame.K_KP_ENTER: Action.END_TURN,
}


def describe(players: list[Player]) -> str:
    """A one-line-per-player summary of the roster the operator entered."""
    return "\n".join(
        f"  {i + 1}. {p.name:<16} ${p.cash:,}  ({p.token_color})"
        for i, p in enumerate(players)
    )


def hud_state(game: Game) -> HudState:
    """The panel's view of the game this frame.

    The HUD knows no rules and the game knows no pixels; this is the whole of
    the join between them.
    """
    return HudState(
        players=game.players,
        current=game.current,
        properties=game.properties,
        dice=game.dice,
        message=game.message,
        available=game.available_actions(),
    )


def win_state(game: Game) -> Optional[WinState]:
    """The finished game, or ``None`` while it is still being played.

    The other half of the join :func:`hud_state` makes: the overlay is handed
    the winner and the roster, and works out nothing for itself.
    """
    if game.state is not State.GAME_OVER:
        return None
    return WinState(winner=game.winner, players=game.players)


def _modal(*screens):
    """Whichever of ``screens`` is showing, or the last one as a fallback.

    Every modal surface draws nothing when it is holding nothing, so handing
    the renderer an idle one is the same as handing it none.
    """
    for screen in screens:
        if screen.visible:
            return screen
    return screens[-1]


def bot_act(game: "Game", now_ms: int, _state: list) -> bool:
    """Perform one action for the current bot player if the timer has elapsed.

    The decision itself belongs to :func:`monopoly.headless.bot_step`, which
    the headless simulator drives flat out; all this adds is the pacing a
    human watching the board needs. ``_state`` is a one-element list holding
    the timestamp (ms) after which the next bot action is allowed; the caller
    passes ``[0]`` once and reuses it each frame. Returns ``True`` when an
    action was taken.
    """
    if now_ms < _state[0]:
        return False
    if not bot_step(game, now_ms=now_ms):
        return False
    _state[0] = now_ms + BOT_DELAY_MS
    return True


def run_game(
    surface: pygame.Surface,
    players: list[Player],
    *,
    game: Optional[Game] = None,
    clock: Optional[pygame.time.Clock] = None,
    win: Optional[WinScreen] = None,
) -> Game:
    """Play until the game ends or the window closes; returns the game.

    The loop drops out three ways: a QUIT or Esc, and either button on the
    win screen. ``win`` is accepted so the caller can read
    :attr:`~monopoly.ui.win_screen.WinScreen.choice` afterwards and know
    whether to set the table up again.
    """
    game = game if game is not None else Game(players)
    renderer = Renderer(surface, Board())
    hud = Hud(HUD_RECT)
    popup = Popup()
    build = BuildScreen()
    auction = AuctionScreen()
    trade = TradeScreen()
    mortgage = MortgageScreen()
    win = win if win is not None else WinScreen()
    clock = clock if clock is not None else pygame.time.Clock()
    actionlog.event(
        "session", "run_game", players=len(game.players),
        state=game.state.value,
    )
    if game.state is State.SETUP:
        game.start()

    def sync_modals() -> None:
        """Point the six modal surfaces at whatever the game is holding."""
        result = win_state(game)
        if result is None:
            if win.visible:
                win.result = None
        elif win.result != result:
            win.result = result
        if popup.prompt is not game.prompt:
            popup.prompt = game.prompt
        if build.plan is not game.build:
            build.plan = game.build
        if auction.auction is not game.auction:
            auction.auction = game.auction
        elif auction.visible:
            # The same sale, but the turn may have moved on under it.
            auction.sync()
        if trade.trade is not game.trade:
            trade.trade = game.trade
        elif trade.visible:
            # The same deal, but Propose may have moved it on to its review.
            trade.sync()
        if mortgage.ledger is not game.mortgage:
            mortgage.ledger = game.mortgage

    _bot_timer = [0]  # next allowed bot action timestamp
    running = True
    while running:
        now = pygame.time.get_ticks()
        game.update(now)
        sync_modals()
        if bot_act(game, now, _bot_timer):
            sync_modals()
        auction.update(now)
        trade.update(now)
        # Sync the panel *before* the events, or a button clicked on the very
        # first frame would still be sitting there disabled.
        hud.state = hud_state(game)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                continue
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
                continue
            # The game is over: the overlay is the only thing left to click,
            # and either of its buttons drops out of the loop.
            if win.visible:
                if win.handle_event(event) is not None:
                    running = False
                continue
            # A prompt is modal: it gets every event, and the panel gets none.
            if popup.visible:
                key = popup.handle_event(event)
                if key is not None:
                    actionlog.event("ui", "popup", key=key)
                    game.choose(key)
                    sync_modals()
                continue
            # So is the build screen, and it closes on its own two buttons.
            if build.visible:
                key = build.handle_event(event)
                if key is not None:
                    actionlog.event("ui", "build_screen", key=key)
                    game.close_build(commit=key == CONFIRM)
                    sync_modals()
                continue
            # And so is an auction, which closes itself once it settles.
            if auction.visible:
                key = auction.handle_event(event)
                if key is not None:
                    actionlog.event(
                        "ui", "auction_screen", key=key, amount=auction.amount
                    )
                    if key == BID:
                        game.bid(auction.amount)
                    else:
                        game.pass_bid()
                    sync_modals()
                continue
            # And a trade, which walks its own three phases before closing.
            if trade.visible:
                key = trade.handle_event(event)
                if key is not None:
                    actionlog.event("ui", "trade_screen", key=key)
                    if key == PROPOSE:
                        game.propose_trade()
                    elif key == ACCEPT:
                        game.accept_trade()
                    else:
                        game.close_trade(rejected=key == REJECT)
                    sync_modals()
                continue
            # And the mortgage screen, which closes on its own two buttons.
            if mortgage.visible:
                key = mortgage.handle_event(event)
                if key is not None:
                    actionlog.event("ui", "mortgage_screen", key=key)
                    game.close_mortgage(commit=key == MORTGAGE_CONFIRM)
                    sync_modals()
                continue
            action = hud.handle_event(event)
            if action is None and event.type == pygame.KEYDOWN:
                action = KEY_ACTIONS.get(event.key)
            if action is not None:
                actionlog.event(
                    "ui", "hud", key=action.value, player=game.current.name
                )
                game.perform(action, now)
                sync_modals()

        # ...and again afterwards, so the frame shows what those events did.
        hud.state = hud_state(game)
        # At most one modal is ever up: the game raises no prompt while a
        # build screen, an auction, a trade or the mortgage screen is open,
        # and opens none of them while a prompt is waiting. The win screen
        # comes first regardless -- once the game is over, it covers whatever
        # the last turn left on the board.
        modal = _modal(win, popup, auction, trade, mortgage, build)
        renderer.draw(game.players, game.properties, hud=hud, popup=modal)
        pygame.display.flip()
        clock.tick(FPS)
    actionlog.event(
        "session", "loop_exit", state=game.state.value,
        winner=game.winner.name if game.winner is not None else None,
    )
    actionlog.audit(game.bank, game.properties, "session.exit", game.players)
    return game


def main() -> int:
    path = actionlog.configure()
    if path is not None:
        print(f"Action log: {path}")
    pygame.init()
    try:
        surface = pygame.display.set_mode(SCREEN_SIZE)
        pygame.display.set_caption(f"{game_manager.TITLE} - {game_manager.SUBTITLE}")
        return play(surface)
    finally:
        pygame.quit()


def play(
    surface: pygame.Surface, manager: Optional[game_manager.GameManager] = None
) -> int:
    """Setup, game, win screen -- and round again while Play Again is pressed.

    One :class:`~monopoly.game_manager.GameManager` is reused across games and
    ``reset()`` between them, so Play Again lands back on a blank player-count
    screen. Every game gets a fresh :class:`~monopoly.game.Game`, and with it
    fresh deeds, decks and a full box of houses.
    """
    manager = manager if manager is not None else game_manager.GameManager()
    first = True
    while True:
        if not first:
            manager.reset()
        first = False
        players = game_manager.run(surface, manager=manager)
        if players is None:
            print("Setup cancelled.")
            return 1
        print(f"Starting game with {len(players)} players:")
        print(describe(players))
        actionlog.event(
            "session", "roster",
            players="; ".join(
                f"{p.name}(${p.cash:,}{', bot' if p.is_bot else ''})"
                for p in players
            ),
        )
        win = WinScreen()
        run_game(surface, players, win=win)
        if win.result is not None:
            print(describe_result(win.result))
        if win.choice != PLAY_AGAIN:
            return 0


if __name__ == "__main__":
    sys.exit(main())
