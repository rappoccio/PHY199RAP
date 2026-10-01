# Monopoly (Custom Stake Edition) — Implementation Plan for Claude Code

## Project Summary

A faithful Monopoly board game in Python + pygame, for 2–6 players. The only rules
modification: a **Game Manager setup phase** lets a human operator assign each player's
starting cash before the game begins (instead of the standard fixed amount).

---

## File Structure

```
monopoly/
├── main.py
├── game_manager.py
├── game.py
├── board.py
├── player.py
├── dice.py
├── cards.py
├── property.py
├── trade.py
├── auction.py
├── actionlog.py
├── headless.py
├── simulate.py
├── ui/
│   ├── __init__.py
│   ├── renderer.py
│   ├── hud.py
│   ├── popup.py
│   └── button.py
├── data/
│   ├── spaces.json
│   ├── chance.json
│   └── community_chest.json
└── assets/
    └── tokens/          # 6 small colored circle PNGs, or draw procedurally
```

---

## Phase 1 — Project Scaffold & Data Files ✅ DONE

> **Status:** complete — 60 unit tests green (`./run_tests.sh`, runs inside the
> `angry_goodall` pygame container; pygame 2.6.1 / Python 3.12, stdlib `unittest`).
>
> **Deviations from this plan, carried forward:**
> - Added card action `"move_to_nearest"` (`"group": "railroad" | "utility"`, with
>   `"rent_multiplier": 2` / `"roll_multiplier": 10`). The three "advance to nearest
>   Railroad/Utility" Chance cards cannot be expressed with the nine listed action
>   types — **Phase 7's card executor needs a branch for it.**
> - Added `monopoly/data_loader.py` (not in the file tree above): the single entry
>   point for reading the JSON, holding `BOARD_SIZE`, `SPACE_TYPES`, `CARD_ACTIONS`,
>   `DEED_TYPES`, `COLOR_GROUPS`. Returns fresh copies per call.
> - Railroads carry `"rent": [25, 50, 100, 200]` and utilities `"multipliers": [4, 10]`
>   so Phase 2's `current_rent` reads its numbers from data rather than hardcoding.
> - Colour keys are snake_case: `light_blue`, `dark_blue`.
>
> **Tests:** `tests/test_spaces_data.py` (all 28 deeds locked to canonical values),
> `tests/test_cards_data.py` (both decks against the action schema),
> `tests/test_scaffold.py` (dirs, imports, JSON validity, headless pygame init).

**`data/spaces.json`** — define all 40 board spaces in order (index 0 = Go).
Each space object:
```json
{
  "index": 1,
  "name": "Mediterranean Avenue",
  "type": "property",
  "color": "brown",
  "price": 60,
  "mortgage": 30,
  "house_cost": 50,
  "rent": [2, 10, 30, 90, 160, 250],
  "group_size": 2
}
```
Types: `"go"`, `"property"`, `"railroad"`, `"utility"`, `"tax"`, `"chance"`,
`"community_chest"`, `"jail"`, `"go_to_jail"`, `"free_parking"`.

For `"tax"` spaces include `"amount"` (200 for Income Tax, 100 for Luxury Tax).
For `"railroad"` include `"price": 200`, `"mortgage": 100`. No color.
For `"utility"` include `"price": 150`, `"mortgage": 75`.

**`data/chance.json`** and **`data/community_chest.json`** — 16 cards each.
Each card:
```json
{
  "text": "Advance to Go (Collect $200)",
  "action": "move_to",
  "destination": 0,
  "collect_go": true
}
```
Action types: `"move_to"`, `"move_relative"`, `"collect"`, `"pay"`,
`"pay_per_building"`, `"get_out_of_jail"`, `"go_to_jail"`, `"collect_from_players"`, `"pay_to_players"`.

---

## Phase 2 — Core Data Classes ✅ DONE

> **Status:** complete — 70 unit tests green (`tests/test_property.py` 34,
> `tests/test_player.py` 36).
>
> **Deviations from this plan, carried forward:**
> - Both classes are `@dataclass(eq=False)`, so players and deeds compare by
>   **identity**. `Property.owner` points at a `Player` and `Player.properties`
>   holds `Property` objects without the dataclass machinery recursing.
> - `Property` reads a `group` key (`"brown"`, …, plus `"railroad"` /
>   `"utility"`) instead of `color`, so the three deed types share one code
>   path. Built with `Property.from_space(space)` / `build_properties()`.
> - Payment is split three ways, to keep the Phase 13 forced-sale rules in one
>   place: `can_pay` / `pay` look at **cash only** (`pay` returns `False` and
>   leaves the balance alone), while `can_raise` / `liquidation_value` answer
>   the wider "could this be met after selling every building and mortgaging
>   every deed?" question. The plan's single `pay()` does not attempt
>   liquidation itself.
> - Extra members beyond the plan: `add_property` / `remove_property` (keep
>   both sides of the ownership link in step), `monopolies()`,
>   `building_level`, `buildings_value`, `building_sale_value`, `house_count`,
>   `hotel_count`.
> - `current_rent(owner=None, dice_total=0)` defaults to the deed's own owner;
>   it **raises** for a utility called without a dice total.

**`property.py`**
- `Property` dataclass: holds all fields from spaces.json
- `owner` (Player | None), `houses` (0–4), `has_hotel` (bool), `mortgaged` (bool)
- Methods:
  - `current_rent(owner, dice_total) -> int` — handles base/monopoly bonus/houses/hotel, railroad formula, utility formula
  - `mortgage_value -> int`
  - `unmortgage_cost -> int` (110% of mortgage value)
  - `build_cost -> int`

**`player.py`**
- `Player`: name, cash, token color, position (0–39), properties (list), goojf_cards (int), in_jail (bool), jail_turns (int), is_bankrupt (bool), doubles_streak (int)
- Methods:
  - `pay(amount) -> bool` — returns False if cannot pay even after forced asset liquidation check
  - `receive(amount)`
  - `net_worth() -> int` — cash + property values + building values (for tiebreak/display)
  - `can_pay(amount) -> bool` — checks cash only (caller decides whether to force mortgage)
  - `owned_in_group(color, all_properties) -> list`
  - `has_monopoly(color, all_properties) -> bool`

---

## Phase 3 — Game Manager Setup Screen ✅ DONE

> **Status:** complete — 83 new unit tests green (`tests/test_game_manager.py` 55,
> `tests/test_ui_widgets.py` 28); **213 tests green overall** (`./run_tests.sh`).
> Run the screen with `python3 -m monopoly.main`.
>
> **Deviations from this plan, carried forward:**
> - **`monopoly/ui/theme.py` added** (not in the file tree): the palette,
>   `SCREEN_SIZE`, the six `TOKEN_COLORS` and a cached `get_font()`. Phase 4's
>   `renderer.py` should import these rather than define its own palette.
> - **`ui/button.py` landed here**, not in Phase 6 — the setup screen needs it
>   first. `Button(rect, label, enabled=, primary=, on_click=)` with `.draw()`,
>   `.is_clicked(event)` and `.handle_event(event)` (hover tracking).
> - **`ui/text_input.py` added** for the `TextInput` widget (the plan left it
>   unplaced): blinking caret with left/right/home/end/delete editing,
>   `digits_only` mode, `max_length`, click-to-focus.
> - **`monopoly/main.py` is a stub entry point** — it runs setup and prints the
>   roster. **Phase 7 must wire the returned `list[Player]` into `game.py`;**
>   `game_manager.run()` does not launch the game itself.
> - Screen is a `Stage.COUNT → DETAILS → DONE` state machine on `GameManager`,
>   driven purely through `handle_event` / `update` / `draw`, so the tests
>   script it with synthesised pygame events. `GameManager.players` is the
>   whole output; `reset()` returns to a blank count screen for Phase 14's
>   "Play Again".
> - Extras beyond the UI flow below: number keys 2–6 also pick the count;
>   Esc and a **Back** button return to the count screen, keeping what was
>   already typed; cash fields are pre-filled with `DEFAULT_CASH = 1500`;
>   names are capped at 16 characters and stakes at 7 digits; tokens are handed
>   out by seat in order red, blue, green, yellow, purple, orange.
>
> **Bug fixed while testing:** the full suite segfaulted (exit 139) because
> `tests/test_scaffold.py` calls `pygame.font.quit()`, which frees every
> `Font` object — including ones `theme` had cached — so the next module's
> `draw()` rendered into freed memory. `get_font()` now drops the cache when it
> finds the font module shut down, and `theme.clear_font_cache()` is called by
> anything that quits it.

**`game_manager.py`** — rendered before any board appears.

UI flow:
1. Screen: "How many players? (2–6)" — clickable number buttons
2. Screen: for each player index, show two text input fields — Name and Starting Cash
   - Tab moves between fields; Enter confirms and advances to next player
   - Validate: name non-empty, cash is a positive integer
3. "Start Game" button — constructs Player objects with the entered cash and launches `game.py`

Render using pygame's event loop, with a simple `TextInput` widget (cursor blink, backspace, digit-only mode for cash field).

---

## Phase 4 — Board Rendering ✅ DONE

> **Status:** complete — 80 new unit tests green (`tests/test_board.py` 65,
> `tests/test_renderer.py` 15); **293 tests green overall** (`./run_tests.sh`).
> Run it with `python3 -m monopoly.main`: setup, then the board.
>
> **Deviations from this plan, carried forward:**
> - **"10 per side, excluding corners" is wrong** — that would make 44 spaces.
>   The board is 4 corners + 4x9 side spaces. Geometry is exact:
>   `CORNER_SIZE = 112`, `SPACE_WIDTH = 64`, and 2*112 + 9*64 = 800.
> - **The palette lives in `ui/theme.py`, not `renderer.py`** (continuing
>   Phase 3's note). `GROUP_COLORS` is keyed by `Property.group`, so the
>   railroads and utilities get strips from the same dict as the eight colours.
> - **Two cached layers, not one.** The *base* surface (outlines, colour
>   strips, names, prices) is drawn exactly once; the *composite* (owner pips,
>   mortgage tint, houses/hotels, tokens) is rebuilt only when a state
>   signature — every token position plus every deed's owner, houses, hotel and
>   mortgage flag — actually changes. `Board.base_builds` /
>   `Board.composite_builds` are public so the tests can assert that contract,
>   and `mark_dirty()` forces the dynamic layer to redraw.
> - **Added an owner pip**: a thin bar in the owner's token colour along each
>   deed's *outer* edge, so ownership reads off the board itself. Labels
>   reserve that lane, so prices never collide with it.
> - **`DISPLAY_NAMES`** abbreviates long deed names *on the board only*
>   ("Penn. RR", "Electric Co."); the deeds keep their full names. `fit_text`
>   refuses a font size that would hyphenate a word, so a long name shrinks
>   rather than breaking mid-word.
> - **Labels rotate to face the centre** — bottom 0 deg, left -90, top 180,
>   right +90 — matching a real board. A label is always drawn upright and
>   rotated into place, so its bottom edge is the space's outer edge.
> - **`Renderer` takes an injected `hud` and `popup`** (anything with
>   `draw(surface)`). Until Phase 6 exists it falls back to
>   `draw_placeholder_panel`, a roster listing — **Phase 6 should delete that
>   method and pass a real HUD.**
> - **`main.py` no longer stops at printing the roster:** `preview()` opens the
>   board with the roster's tokens and walks player 1 around with the arrow
>   keys. **Phase 7 replaces `preview()` with the real game loop.**
>
> **Geometry API** (all pure, no display needed, all unit-tested): `space_rect`,
> `strip_rect`, `body_rect`, `owner_pip_rect`, `token_positions`,
> `building_rects`, `space_at_point`, `side_of`, `rotation_of`, `is_corner`,
> `space_label`, `display_name`, `group_color`. Phase 6/7 hit-testing goes
> through `Renderer.space_at(screen_pos)` / `Renderer.board_point`.

**`board.py`**

Draw the board procedurally (no image asset required):
- Outer ring of 40 rectangles on a square canvas
  - Corners are larger squares
  - Side spaces are rectangles (10 per side, excluding corners)
- Each property space: filled color strip at the appropriate edge, property name text
- Railroad spaces: small train icon or "RR" text
- Utility spaces: icon or abbreviation
- Tax, Chance, Community Chest, special spaces: labeled with abbreviated text
- Player tokens: small filled circles drawn at each occupied space, stacked/offset if multiple players present
- House/hotel markers: small green squares (houses) or red rectangle (hotel) on owned properties

Board is drawn to a pygame `Surface` once and cached; re-draw only when building state or token positions change.

**`renderer.py`** — composes: board surface + HUD panel + any active popup.

---

## Phase 5 — Dice Module ✅ DONE

> **Status:** complete — 78 new unit tests green (`tests/test_dice.py` 65,
> `tests/test_dice_view.py` 13); **371 tests green overall** (`./run_tests.sh`).
> Run it with `python3 -m monopoly.main`: space rolls, the dice animate in the
> panel, and player 1 walks forward by the total.
>
> **Deviations from this plan, carried forward:**
> - **`monopoly/ui/dice_view.py` added** (not in the file tree): `draw_die`,
>   `draw_dice`, `die_rects`, `pip_centers`, `dice_size`. `dice.py` stays pure
>   Python — no pygame import — so the rules are testable without a surface,
>   and Phase 6's HUD drops the dice anywhere by handing `draw_dice` a corner.
> - **The result is decided by `Dice.start()`, not when the animation ends**,
>   and the mid-roll flicker faces come from a *separate*, unseeded generator.
>   Together those mean a seeded `rng` plays out the same sequence of rolls
>   however many frames got drawn — worth keeping when Phase 7 wants a
>   reproducible game.
> - **`Dice.result` / `.total` / `.doubles` raise `RuntimeError`** before the
>   first roll and while one is in the air; **`Dice.faces` never raises** and
>   is what the renderer reads (flicker mid-roll, the result once settled,
>   `RESTING_FACES = (1, 1)` before the first roll of the game).
> - **`Dice.update(now_ms)` returns `True` exactly once per roll** — on the
>   frame it settles — so Phase 7's `ROLLING` state needs no "have I handled
>   this roll yet" flag of its own. `Dice.start()` raises if a roll is already
>   in flight, catching a double-fired Roll Dice button.
> - Extras beyond the plan: `finish()` cuts the animation short without
>   disturbing the result (a click can skip it), `reset()` for Phase 14's
>   "Play Again", and `elapsed` / `progress` for anything that wants to ease
>   on the roll. `roll_ms=0` is the instant, un-animated mode.
> - `is_doubles(d1, d2)` is a module-level function as planned; `Dice.doubles`
>   is the same check on the settled roll. Phase 8 reads it for jail, Phase 7
>   for the three-doubles rule — neither is implemented here.
> - **`main.preview()` now rolls**: space starts a roll and the settled total
>   moves player 1 (arrows still step one space). It is still a preview — no
>   rent, no jail, no turn order. **Phase 7 replaces it.**

**`dice.py`**
- `roll() -> tuple[int, int]` — returns two values 1–6
- Track doubles: `is_doubles(d1, d2) -> bool`
- Animate: brief 0.4s display of "rolling…" with random face numbers before settling — use a simple timer in the game loop

---

## Phase 6 — HUD ✅ DONE

> **Status:** complete — 58 new unit tests green (`tests/test_hud.py`);
> **429 tests green overall** (`./run_tests.sh`). Run it with
> `python3 -m monopoly.main`: setup, then the board with a live panel.
>
> **Deviations from this plan, carried forward:**
> - **The HUD knows no rules.** It is handed a `HudState` dataclass
>   (`players`, `current`, `properties`, `dice`, `message`, `available`) and
>   draws exactly that; **deciding which actions are legal is Phase 7's job.**
>   `Hud.state = HudState(...)` is a setter — assigning it syncs every
>   button's `enabled` flag and clamps the deed-list scroll.
> - **Clicks come back out as an `Action` enum** (`ROLL`, `BUILD`,
>   `MORTGAGE`, `TRADE`, `END_TURN`; the enum *value* is the button label),
>   both as `Hud.handle_event(event)`'s return value and through the optional
>   `on_action` callback. `handle_event` returns `None` for anything else.
> - **`ui/button.py` already existed** (it landed in Phase 3 for the setup
>   screen), so this phase only added `ui/hud.py`.
> - **The dice moved into the HUD.** `main` no longer parks them itself;
>   `Hud` draws them in `dice_rect` via `dice_view.draw_dice`. `main.DICE_TOPLEFT`
>   is gone, and `tests/test_dice_view.py`'s wiring test now checks the HUD's
>   block instead.
> - **`Renderer.draw_placeholder_panel` is gone**, as Phase 4 asked. Without a
>   HUD the renderer now calls `draw_empty_panel()` — panel chrome and nothing
>   else.
> - **Fixed 480x800 layout, computed in `Hud._layout()`** and exposed as public
>   rects (`header_rect`, `dice_rect`, `message_rect`, `list_title_rect`,
>   `property_list_rect`, `buttons_rect`, `roster_rect`, plus `row_rect(i)` /
>   `chip_rect(i)`), so the tests assert the geometry without a display. The
>   roster always reserves room for `MAX_OTHER_PLAYERS = 5`, which keeps the
>   button positions identical whatever the player count.
> - **The deed list scrolls** (`scroll`, `max_scroll`, `scroll_by`,
>   `visible_rows` — 6 rows visible, 28 deeds possible). A `MOUSEWHEEL` event
>   reaching the HUD scrolls it; pygame puts no position on wheel events, so a
>   caller that wants the wheel to mean something else elsewhere simply does
>   not pass it on. A "1-6 of 9" counter appears beside the list title.
> - Extras beyond the plan: net worth under the current player's cash, a
>   white outline on a chip whose colour group is a **monopoly**, houses drawn
>   as green squares / a hotel as a red bar in each row, an `MTG` badge for a
>   mortgaged deed, and a deed count plus `BANKRUPT` state in the roster.
>   Long names abbreviate through `board.DISPLAY_NAMES` (`deed_label`) and any
>   over-long text is ellipsized rather than spilling out of the panel.
> - **`main.preview()` now drives the real HUD** — Roll Dice / space rolls and
>   moves the current player, End Turn / Enter passes the panel to the next
>   seat, arrows still step one space. `main.preview_state()` is the throwaway
>   "which actions are legal" stub; **Phase 7 replaces it with `game.py`'s
>   answer and drops `preview()`.**

**`hud.py`** — right-side panel, always visible:
- Current player name + cash
- Owned properties list with mortgage/building status
- Available actions as buttons (enabled/disabled contextually):
  - **Roll Dice** (only before roll this turn)
  - **Build** (if player owns a complete color group, post-roll)
  - **Mortgage / Unmortgage** (post-roll or pre-roll)
  - **Trade** (pre-roll or post-roll, before End Turn)
  - **End Turn** (after roll and all actions resolved)
- All other players shown below with name + cash summary

**`button.py`** — `Button(rect, label, enabled)` with `.draw(surface)` and `.is_clicked(event) -> bool`.

---

## Phase 7 — Game State Machine ✅ DONE

> **Status:** complete — 172 new unit tests green (`tests/test_game.py` 114,
> `tests/test_cards.py` 28, `tests/test_popup.py` 27, `tests/test_main.py` 16
> — the counts overlap because `test_main` opens a real dummy-driver display);
> **601 tests green overall** (`./run_tests.sh`). Run it with
> `python3 -m monopoly.main`: setup, then a playable game.
>
> **Deviations from this plan, carried forward:**
> - **`monopoly/cards.py` added** (it was in the plan's file tree but Phase 1
>   only shipped the JSON): `Card.from_dict` validates against
>   `data_loader.CARD_ACTIONS`, and `Deck` cycles — draw from the top, discard
>   to the bottom. A **Get Out of Jail Free card leaves the pile** while a
>   player holds it and comes back through `Game.return_goojf(player)`, which
>   is what **Phase 8's "Use GOOJF Card" button should call**.
> - **`monopoly/ui/popup.py` added**: draws a `Prompt` over a dimmed board and
>   turns a click back into that choice's key. Like the HUD it decides nothing.
>   `Renderer` already took a `popup=`; it is now fed a real one.
> - **`Action` moved from `ui/hud.py` to `game.py`** — *which* actions exist is
>   a rules question. `hud.py` re-exports it, so every existing import still
>   works, and the value is still the button label. **`game.py` imports no
>   pygame**, so (like `dice.py`) a whole game plays out without a surface.
> - **Build / Mortgage / Trade are not merely disabled — they are absent.**
>   `available_actions()` only offers one once a later phase registers a
>   callable in `game.action_handlers[Action.BUILD]`, so **Phases 9, 11 and 12
>   plug in without editing `game.py`.**
> - **Modal questions are data, not UI.** `Game.prompt` is a `Prompt`
>   (`kind` + `title` + `text` + `Choice` buttons, plus the `deed` or `card` in
>   question) answered with `Game.choose(key)`. While one is up
>   `available_actions()` is empty — that is what makes it modal. Kinds:
>   `PROMPT_BUY`, `PROMPT_CARD`, `PROMPT_INFO`.
> - **The three-doubles path lands in `PLAYER_ACTIONS`, not straight in
>   `END_TURN`.** `MOVING`/`LAND_ACTION` are skipped as the plan says, but the
>   player still presses End Turn — so there is one exit from a turn, and a
>   jailed player can still build/mortgage, which the real rules allow. Same
>   for every other jail path.
> - **Phase 8's roll-for-doubles branch is implemented here** (`_jail_roll`):
>   without it a jailed player could never leave and the loop would deadlock.
>   Doubles free them (no extra turn); a third failure forces the $50. **Phase 8
>   still owes the Pay $50 and Use GOOJF *buttons* at `PLAYER_TURN_START`.**
> - **Auction and bankruptcy are hooks, not stubs**: `Game.on_auction(game,
>   deed)` for Phase 10 and `Game.on_shortfall(game, debt)` for Phase 13. Until
>   Phase 13 lands, an unpayable debt takes every dollar the payer had, credits
>   it to the creditor, and records the rest in `Game.debt` (a `Debt`
>   dataclass). Nobody is marked bankrupt yet, but `_advance_turn` already
>   skips `is_bankrupt` seats and declares a `winner` / `GAME_OVER` when one
>   player is left — **Phase 14 hangs the win screen off that.**
> - **The nearest-Utility card throws the dice again** for its ×10, as the real
>   rules say, and reports the throw in the message; the displayed dice keep
>   showing the roll that moved the player.
> - Movement is **one space per `step_ms` (default 90ms)**, awarding the Go
>   salary as the token crosses index 0; backwards moves ("Go Back 3") never
>   pay it. `step_ms=0` teleports, and with `Dice(roll_ms=0)` a whole turn
>   resolves inside a single `Game.update()` — that is how the tests run.
> - `Game.update(now_ms)` is the only clock. It returns `True` on any frame
>   that progressed, and `Game.message` / `Game.log` carry the commentary.
> - **`main.preview()` is gone**, replaced by `run_game()`. `main.hud_state()`
>   is the whole join between a game that knows no pixels and a panel that
>   knows no rules.
>
> **Bug fixed while testing:** `run_game` synced `hud.state` *after* the event
> loop, so on a frame where an action first became legal its button was still
> disabled and the click was dropped (visible as a dead Roll Dice button on the
> very first frame). The panel is now synced before events *and* before the
> draw.

**`game.py`** — central game loop.

States:
```
SETUP → PLAYER_TURN_START → ROLLING → MOVING → LAND_ACTION → PLAYER_ACTIONS → END_TURN
```

`PLAYER_TURN_START`:
- Reset per-turn flags (rolled this turn = False)
- If in jail: show jail options (Pay $50 / Use GOOJF card / Roll for doubles)

`ROLLING`:
- Roll dice; animate
- Check: 3 doubles in a row → go to jail, skip to END_TURN
- Advance position by dice total (handle Go passing: +$200)
- Transition to MOVING

`MOVING`:
- Animate token sliding space by space (or instant, configurable)
- On arrival, transition to LAND_ACTION

`LAND_ACTION` (dispatches by space type):
- **property / railroad / utility**:
  - Unowned → show Buy popup ($X) with Buy / Auction buttons
  - Owned by self, mortgaged → nothing
  - Owned by self, unmortgaged → nothing
  - Owned by another → PAY_RENT sub-state: calculate rent, deduct from current player, credit owner; handle bankruptcy chain
- **chance / community_chest** → draw card, show card popup, execute action
- **go_to_jail** → send to jail
- **tax** → deduct amount; handle bankruptcy
- **go** → already handled (passed logic); just display "You landed on Go!"
- **free_parking / jail** → nothing (standard rules; Free Parking does nothing)
- Transition to PLAYER_ACTIONS

`PLAYER_ACTIONS`:
- Player may Build, Mortgage, Trade (any order, any number of times)
- Roll Dice button is now disabled
- End Turn button is enabled

`END_TURN`:
- If doubles were rolled (and player not in jail): go back to PLAYER_TURN_START for same player
- Otherwise: advance to next non-bankrupt player, go to PLAYER_TURN_START

---

## Phase 8 — Jail Logic ✅ DONE

When sent to jail:
- Position set to space index 10 (Jail)
- `in_jail = True`, `jail_turns = 0`, doubles_streak reset to 0

On `PLAYER_TURN_START` while in jail:
- Show three buttons: **Pay $50 & Roll**, **Use GOOJF Card** (disabled if none), **Roll for Doubles**
- Pay $50 & Roll: deduct $50, `in_jail = False`, roll normally
- Use GOOJF card: consume card, `in_jail = False`, roll normally
- Roll for Doubles:
  - Roll dice; if doubles → `in_jail = False`, move as normal (no extra turn for these doubles)
  - If not doubles and `jail_turns < 2`: increment `jail_turns`, end turn (no movement)
  - If not doubles and `jail_turns == 2` (third failed roll): pay $50 forced, `in_jail = False`, move

---

## Phase 9 — Building System ✅ DONE

> **Status:** complete — 148 new unit tests green (`tests/test_building.py` 58,
> `tests/test_build_game.py` 32, `tests/test_build_screen.py` 48, plus 6 new
> `run_game` tests in `test_main.py` and 3 in `test_board.py`);
> **820 tests green overall** (`./run_tests.sh`).
>
> **Deviations from this plan, carried forward:**
> - **`monopoly/building.py` added** (not in the plan's file tree), and it
>   imports no pygame — like `game.py` and `dice.py`, a whole build is planned,
>   priced and committed in a test without a surface. It holds `Bank` (the
>   board's 32 houses and 12 hotels) and `BuildPlan`.
> - **The build screen edits a draft, not the board.** `BuildPlan` is created
>   from the board, edited with `add` / `remove`, and either thrown away or
>   handed to `commit()`, which moves deeds, bank and wallet together. That is
>   what makes the plan's "Confirm executes all queued changes atomically"
>   real, and it is why every rule — even building, the supply, the player's
>   cash — is asked of the *draft* rather than of the board.
> - **`+` then `-` on the same lot is a free undo, not a half-price sale.**
>   The draft is priced *net against the board*, so only a building that was
>   really standing when the screen opened ever sells at half price.
> - **Selling a hotel returns the lot to four houses**, taking four out of the
>   box — so a hotel refunds *one* half-price house payment, not five. This is
>   the standard rule, and the only reading under which this plan's "if supply
>   exhausted, hotel cannot be sold until supply replenishes" means anything;
>   the same bullet's "hotels sell for half hotel_cost (which equals 4× half
>   house cost)" contradicts itself and was not followed.
> - **`Action.BUILD` came off `DEFERRED_ACTIONS`.** It is live whenever
>   `Game.can_build()` is true — that is, whenever the current player holds a
>   colour group whole and unmortgaged, which is one question and not two: a
>   group carrying buildings is always one its owner may also sell from.
>   A handler registered in `action_handlers[Action.BUILD]` still overrides.
>   **This changed one Phase 7 test**, which now makes its point with
>   `Action.MORTGAGE`.
> - **`Game.build` is the second modal thing, beside `Game.prompt`.**
>   `open_build()` / `close_build(commit=)` are the whole API; while a draft is
>   open `available_actions()` is empty, so the turn cannot move on underneath
>   it, and `main` routes every event to the screen exactly as it does for a
>   popup. **Phase 13 returns buildings to `Game.bank`.**
> - **`monopoly/ui/build_screen.py` added**: group blocks, one row per lot with
>   `-` / `+`, a running total and Confirm / Cancel, over a dimmed board. Like
>   the HUD and the popup it decides nothing — it only asks `can_add` /
>   `can_remove` which buttons to draw live. The list scrolls, and **buttons
>   exist only for visible rows**, so a row scrolled out of sight cannot be
>   clicked by accident.
> - **`_ellipsize` moved from `ui/hud.py` to `ui/theme.py` as `ellipsize`**, so
>   the build screen can cut a long lot name the same way the deed list does.
>   `hud.py` uses the shared one; nothing else referenced the private name.
>
> **Bug fixed while testing:** the first build screen drew each lot's name and
> its houses from the same left edge, so "Mediterranean Avenue" was painted
> straight over its own buildings. Rows now have fixed name / building columns
> (`NAME_W`, `BUILDINGS_X`) and the name is ellipsized into its column.
>
> **Two soak tests** (`WholeGameTest`) play 400 turns of a real game with a bot
> that builds whenever it can, asserting after *every* turn that buildings are
> conserved (board + box = starting stock), that no group is unevenly built,
> and that nobody overdraws. One variant starts the box nearly empty: it drains
> to zero houses and correctly strands the dark blues at 3/3 — which is the
> case the supply rules exist for.

Triggered from Build button in PLAYER_ACTIONS.

**Build screen** (popup or side panel):
- List all color groups the player owns completely (all properties unmortgaged)
- For each group, show each property with current house count and a +/- button
- Enforce even-build rule: cannot add to a property if another in the group has fewer houses
- Enforce supply limits: global house count ≤ 32, hotel count ≤ 12
- Hotel: place when all properties in group would go from 4 houses to hotel; remove 4 houses from supply, add 1 hotel
- Sell buildings: any time (pre or post roll); houses sell at half house_cost; hotels sell for half hotel_cost (which equals 4× half house cost); returned houses go back to supply (if supply exhausted, hotel cannot be sold until supply replenishes)
- Confirm button executes all queued +/- changes atomically and charges/refunds cash

---

## Phase 10 — Auction ✅ DONE

> **Status:** complete — 134 new unit tests green (`tests/test_auction.py` 44,
> `tests/test_auction_game.py` 39, `tests/test_auction_screen.py` 42, plus 9
> new `run_game` tests in `test_main.py`); **954 tests green overall**
> (`./run_tests.sh`).
>
> **Deviations from this plan, carried forward:**
> - **`monopoly/auction.py` added** (it was in the plan's file tree), and it
>   imports no pygame — like `game.py`, `dice.py` and `building.py`, a whole
>   sale runs in a test without a surface.
> - **The sale decides; the game settles.** `Auction` never moves a deed or a
>   dollar: it says who won and at what price, and `Game._settle_auction` is
>   what charges the winner and hands the deed over — the same split
>   `BuildPlan` / `commit()` uses. Every `Auction` test asserts the board is
>   untouched.
> - **`Game.auction` is the third modal thing**, beside `Game.prompt` and
>   `Game.build`. While a sale runs `available_actions()` is empty, so the
>   turn cannot move on underneath it, and `main` routes every event to the
>   screen exactly as it does for a popup or a build draft. The turn sits in
>   `LAND_ACTION` until the hammer falls, then enters `PLAYER_ACTIONS`.
> - **Phase 7's `on_auction` hook still wins.** It is only when nothing is
>   registered that the bank holds the built-in sale, so a caller that wants
>   its own auction — or none at all — keeps that.
> - **No borrowing: a bid is capped at the bidder's cash in hand.** That is
>   what makes the plan's "winner pays their bid to the bank" unable to fail;
>   mortgaging mid-auction to raise a bid is deliberately not offered (Phase
>   12 owns mortgaging, and it is not reachable from a modal sale).
> - **A bidder who cannot reach the asking price drops out automatically**,
>   with a line in the transcript. Nothing useful can be asked of a player
>   with $0 in a sale that has already passed them, and without this rule a
>   table that cannot afford $1 would never settle at all.
> - **The leader is never asked to outbid themselves.** The round skips past
>   the standing high bidder, so "all but one have passed" resolves to that
>   bidder winning; a lone *remaining* player who has not yet bid is still
>   asked, which is what keeps the plan's "if all players pass, the property
>   remains unowned" reachable.
> - **`monopoly/ui/auction_screen.py` added**: the deed under the hammer,
>   where the bidding stands, one row per bidder (cash, `passed` / `in` /
>   `high $n`, a `>` beside whoever is on turn), and — for that one player —
>   a cash field, `+1` / `+10` / `+50` quick raises, **Bid** and **Pass**.
>   The plan's "each player sees a bid input" is **one hot-seat field that
>   follows the turn**, refilled with the new asking price each time the
>   round moves on, rather than six fields on screen at once. Like the HUD,
>   the popup and the build screen it decides nothing: it asks
>   `Auction.can_bid` which buttons to draw live and reports `BID` / `PASS`.
>   Enter is the Bid button's shortcut.
> - **`answer()` in `tests/test_game.py` now settles any sale it opens** by
>   passing everybody. Declining used to end the landing outright, so the
>   helper keeps the ~8 older tests that decline a deed saying what they
>   always said. The two soak loops (`JailSoakTest`, `WholeGameTest`) grew a
>   bidding branch instead, so both now play through real auctions.
>
> **Bug fixed while testing:** the auction screen's footer stacked the quick-
> raise row and the Bid / Pass row 6px into each other, so a click near the
> `+50` button landed on two live buttons at once. The footer is taller and
> the two rows are now checked for overlap by a test.
>
> **Three soak tests** (`WholeGameTest`) play 300 turns of a real
> three-handed game — one bidding on everything, one on nothing, one at
> random — re-checking after every step that each deed is either the bank's
> or in exactly one hand, that nobody overdraws, and that a winner's payment
> matches the price that was struck.

Triggered when a player declines to buy an unowned property.

**`auction.py`**
- All players (including the one who declined) may bid
- Minimum bid: $1 (or current high bid + $1)
- Each player sees a bid input and a "Bid" button; "Pass" to drop out
- Auction ends when all but one player have passed
- Winner pays their bid to the bank; takes the property deed
- If all players pass (no one bids): property remains unowned (no deed changes hands)

---

## Phase 11 — Trading ✅ DONE

**`trade.py`** — current player initiates a trade with one other player.

UI:
- Select trade partner from list
- Two columns: "You Offer" / "They Offer"
- Each column has: cash input, checkboxes for each owned property (name, mortgage status shown), GOOJF card checkbox
- "Propose" sends offer to partner
- Partner sees the same panel read-only + Accept / Reject buttons
- On Accept: atomically swap all offered items; update ownership; re-check for monopoly status

---

## Phase 12 — Mortgage & Unmortgage ✅ DONE

Available in PLAYER_ACTIONS.

- Show list of all owned properties with status
- Mortgage: only if no buildings on any property in that group; flip property; receive mortgage_value from bank
- Unmortgage: pay 110% of mortgage value to bank; property becomes active again
- If player receives a mortgaged property (via trade or bankruptcy): may unmortgage at 110%, or leave mortgaged (but cannot collect rent)

---

## Phase 13 — Bankruptcy Resolution ✅ DONE

> **Status:** complete — 103 new unit tests green (`tests/test_bankruptcy.py` 56,
> `tests/test_bankruptcy_game.py` 47); **1330 tests green overall**
> (`./run_tests.sh`).
>
> **Deviations from this plan, carried forward:**
> - **`monopoly/bankruptcy.py` added** (not in the plan's file tree), and like
>   `game.py`, `building.py`, `auction.py` and `trade.py` it imports no pygame
>   — a whole wind-up runs in a test without a surface. It holds both halves
>   of a debt that outruns the cash: `sell_all_buildings` / `mortgage` /
>   `raise_cash` for the forced sale, and `settle` → a frozen `Settlement`
>   record for the bankruptcy itself. It touches no game, no turn order and no
>   win condition; `is_bankrupt` is the one flag it sets.
> - **Phase 13 added nothing modal.** The plan specifies no UI for it, so the
>   rules answer a debt on the spot and the transcript narrates it; Phase 14's
>   win screen is what shows the ending. `Game.last_settlement` keeps the last
>   wind-up for it.
> - **The forced sale is automatic, and all-or-nothing on buildings.** The
>   plan's trigger ("cannot pay *after* selling all buildings and mortgaging
>   all properties") presumes the liquidation has already happened, so
>   `Game.settle_debt` performs it rather than asking. Mortgaging *does* stop
>   the moment the debt is covered (board order, cheap lots first), but every
>   building comes down at once — which is exactly what keeps `raise_cash`
>   consistent with `Player.liquidation_value()`, so a debt `can_raise` says is
>   reachable is always reached.
> - **A hotel goes back in the box as a hotel**, needing no houses in stock to
>   stand back up: the lot is being cleared, not stepped down to four houses,
>   so Phase 9's supply rule for *selling* one does not apply here.
> - **A deed returned to the bank is unmortgaged on the way.** The plan says
>   properties become unowned again; a deed on the bank's shelf is for sale at
>   its list price, so the flag cannot be left set.
> - **No 10% interest on a mortgaged deed inherited by a creditor.** The plan
>   says the deeds transfer "as-is", so that official-rules wrinkle is left
>   out.
> - **"Pay each player" stops at the bankruptcy.** Whoever was being paid when
>   the money ran out takes everything; the players further round the table
>   simply go unpaid, because there is nothing left to pay them with.
> - **`on_shortfall` still wins**, the way `on_auction` does: a registered hook
>   holds the debt open, and may call `Game.settle_debt()` itself.
> - **`Game._charge` takes nothing from an already-bankrupt player** — they
>   have nothing to take, and their debts died with their game.
> - Three Phase 7/8 placeholder tests were updated to the new behaviour:
>   `ShortfallTest` now registers a hook so it can still look at a live `Debt`,
>   and the forced-jail-fine test asserts the bankruptcy it now causes.
>
> **Four soak tests** (`SoakTest`) play whole games with bots that buy, bid
> **and build** — building is what makes rents lethal enough to bankrupt a
> table at all — re-checking after every step that nobody overdraws, that a
> bankrupt player holds no cash, deeds or jail cards, that every deed is the
> bank's or in exactly one *live* hand, and that every house and hotel is
> either standing on the board or back in the box. One runs six-handed down to
> a single winner.

When a player cannot pay a debt after selling all buildings and mortgaging all properties:

- **Owed to another player**: all remaining cash + all deeds (as-is, mortgaged or not) transfer to the creditor. If hotels/houses must be sold because creditor doesn't want to assume building costs: sell all buildings first, credit proceeds to the bankrupt player's balance, then transfer.
- **Owed to the bank** (tax, card): all assets return to the bank. Properties become unowned again. Buildings return to supply.
- Player is marked `is_bankrupt = True` and removed from turn order.

**Win condition**: only one non-bankrupt player remains → show win screen with final stats (name, net worth at time of win).

---

## Phase 14 — Win Screen ✅ DONE

> **Status:** complete — 61 new unit tests green (`tests/test_win_screen.py` 43,
> `tests/test_main.py` +18); **1575 tests green overall** (`./run_tests.sh`).
>
> **Deviations from this plan, carried forward:**
> - **`monopoly/ui/win_screen.py` added** (not in the plan's file tree). It
>   holds `WinScreen` and the frozen `WinState` record it is handed, and like
>   every other surface in `ui/` it decides nothing: `main.win_state(game)`
>   builds the record from `Game.winner` and `Game.players`, the screen draws
>   exactly that, and `handle_event` reports `PLAY_AGAIN` / `QUIT`.
> - **`result = None` is what means "the game is still on."** A `WinState` with
>   `winner=None` is a real state, not an absent one — a one-handed game whose
>   player goes bankrupt to the bank leaves nobody standing, and the overlay
>   says "Nobody wins" rather than freezing on the board. Phase 7's `_end_game`
>   already allowed for that ending; this is the screen for it.
> - **Final stats are cash *and* net worth**, per Phase 13's win condition, plus
>   a `N players -- M bankrupt` tally in the heading.
> - **The deed list is three columns, filled top to bottom.** 33 rows fit, so
>   all 28 deeds of a swept board show without scrolling; a shorter card
>   reports the remainder as "+N more" rather than cutting silently. Rows carry
>   the group chip, house/hotel marks and a `mortgaged` badge, as the HUD's do.
> - **`Game.last_settlement` is not shown.** Phase 13 kept it for this screen,
>   but the ending that matters is who is left standing; the wind-up details
>   are already in the transcript.
> - **`main.run_game` takes an optional `win` screen** and still returns the
>   game. That is how the caller learns which button was pressed
>   (`WinScreen.choice`) without the loop growing a second return value or the
>   `Game` growing a UI flag.
> - **`main.play(surface, manager)` added**, and `main()` delegates to it:
>   setup → game → win screen, and round again on Play Again. One
>   `GameManager` is reused and `reset()` between games (what Phase 3 left that
>   method for), while every game gets a fresh `Game` — and with it fresh
>   deeds, decks and a full box of houses.
> - **The overlay is the loop's sixth modal and outranks the other five.** Once
>   the game is over it covers whatever the last turn left on the board,
>   swallows every click and key, and either of its buttons ends `run_game`
>   with no QUIT — the panel and the space bar are dead.
>
> The two button tests post no QUIT at all, so a broken exit would hang the
> suite; a `CountingClock` fails them after four frames instead.

Full-screen overlay:
- Winner's name and token color
- Final cash amount
- Properties owned at end
- "Play Again" button → returns to Game Manager setup screen
- "Quit" button → exits

---

## Phase 15 — Action Log ✅ DONE

> **Status:** complete — 19 new unit tests green (`tests/test_actionlog.py`);
> **1595 tests green overall** (`./run_tests.sh`).

`Game.log` is a *narration*: two hundred lines of prose, in memory, for the
player to read. `monopoly/actionlog.py` is the other kind of log — a
timestamped, machine-greppable transcript of every action, on disk, that
outlives the window. It exists because "somehow a player's houses disappeared
mid-game" is not answerable from a HUD that has already scrolled past it.

**Turning it on.** `main()` calls `actionlog.configure()` once at startup and
prints the path it opened; it lands in `logs/monopoly-YYYYmmdd-HHMMSS.log`
(gitignored). Nothing is written until that call, so the test suite and any
importing script stay silent by default. `$MONOPOLY_LOG_DIR`,
`$MONOPOLY_LOG_LEVEL` and `$MONOPOLY_LOG_CONSOLE` override the three choices
without editing anything.

**What one line looks like.** `category.action` and then `key=value` fields:

```
turn.begin        player=Cy seat=2 cash=619 position=24 in_jail=no deeds=12 ...
build.commit      player=Cy charge=1,300 moves='Park Place 3->5; Boardwalk 3->5' ...
audit.changed     at=build.commit n=6 changes='Park Place: (Cy, 3h) -> (Cy, hotel); ...'
```

The categories are `session`, `game`, `turn`, `action`, `dice`, `move`,
`jail`, `deed`, `rent`, `money`, `cash`, `card`, `goojf`, `build`, `mortgage`,
`trade`, `auction`, `bank`, `debt`, `bankruptcy`, `bot`, `ui`, `narrate` and
`audit`. `INFO` is the game's own actions; `DEBUG` adds every draft click,
every refused move, every wallet movement and a mirror of the HUD narration;
`WARNING` and `ERROR` are for things that should not have happened.

**`audit()` is the safety net, and the reason this phase exists.** Every
`event` call only records what the code *admits* to doing. The audit records
what actually changed: it walks all 28 deeds and every wallet, compares them
against the last time it looked, and writes down every difference — owner,
building level, mortgage flag, cash, deed count — whether or not anything
announced it. **A building change in an `audit.changed` line with no matching
`build.*` / `bankruptcy.*` / `trade.*` event above it is a bug**, and that is
exactly the shape of a house that disappears. It runs at `turn.begin`,
`turn.end`, `build.commit`, `mortgage.commit`, `trade.accept`, `debt.settled`,
`bankruptcy.settled`, `game.new`, `game.over` and on the way out of
`run_game`.

It also checks the two conservation laws the box imposes — 32 houses and 12
hotels, on the board or in the bank and nowhere else — and logs
`audit.house_supply_broken` / `audit.hotel_supply_broken` at `ERROR` with a
full census and a stack trace when either is violated. A player's houses
vanishing *without* tripping that check means they went back to the bank
legitimately; the three ways that happens are all logged in full:
`bankruptcy.sell_all_buildings` (a forced sale — note it sells **every**
building the player owns, even for a $1 shortfall), `build.commit` with a
refund, and `bankruptcy.settle`.

> **Deviations from the rest of the plan, carried forward:**
> - **`monopoly/actionlog.py` added** (not in the plan's file tree). It imports
>   nothing from the rest of the package, so every module may import it
>   without a cycle — `player.py`, the lowest layer, does.
> - **Nothing here raises.** `audit()` catches everything and logs
>   `audit.failed`; `configure()` returns `None` rather than refusing to play
>   when the file cannot be opened. A logging bug must never end a game.
> - **`event()` spells its severity `_level`** and takes `category` / `action`
>   positionally only, because `level` is a *building* level throughout this
>   codebase and has to stay usable as a field name.
> - **`bankruptcy.sell_all_buildings` now skips bare lots** rather than adding
>   zero to the bank for each one. Behaviour is unchanged; it keeps the log
>   line to the lots that really came down.
> - **`BotStrategy.choose_action` split**, with the decision itself in
>   `_pick_action`, so the choice can be logged in one place.

---

## Phase 16 — Headless Simulation ✅ DONE

> **Status:** complete — 49 new unit tests green (`tests/test_headless.py`,
> `tests/test_simulate.py`); **1644 tests green overall** (`./run_tests.sh`).

The question this edition was built to ask — *what does a bigger opening
stake actually buy you?* — is a statistics question, and statistics need
thousands of games, not one game watched at 60 frames a second. Two modules
answer it, and **neither imports pygame**: `game.py` was always pure rules, so
a game can be played with no window, no SDL and no display at all.

**`monopoly/headless.py` — the engine.**

* `bot_step(game)` performs exactly **one** bot decision against whatever the
  game is holding: an open auction (whose bidder is often not the player on
  turn), a prompt, the build or mortgage screen, or the plain action list.
  This is now the single source of truth for what a bot does next —
  `main.bot_act` is this function plus the 700 ms delay a human watcher needs,
  and nothing else.
* `play(cash, seed=..., max_turns=...)` plays one whole game of bots and
  returns a `Result`: winner, turns, rounds, closing net worths, who went
  bankrupt, and a `status` of `win`, `timeout` or `stalled`. A game is driven
  by alternating the only two things that can move it — `Game.update` and one
  `bot_step` — with `step_ms=0` and `roll_ms=0` so neither waits for a frame.
* One `random.Random(seed)` seeds the dice and both decks, so a seed fixes the
  whole game: the same seed and stakes replay it move for move.
* `Result.turns` counts **player turns** (a doubles re-roll is part of the
  turn that earned it, not a new one); `Result.rounds` counts circuits of the
  table. `TrackedGame` overrides `start` and `_advance_turn` to count them,
  because a turn is not a loop iteration.

**`monopoly/simulate.py` — the command line.**

```
python3 -m monopoly.simulate 1500 1500
python3 -m monopoly.simulate 3000 1000 1000 1000 -n 500 -j 8
python3 -m monopoly.simulate 2500 2000 500 -n 2000 --csv runs.csv --json
```

The positional arguments are the stakes, in seat order — 2 to 6 of them,
summing to $1,500 per player, which is the house rule this edition adds and
the whole point of the experiment: **the pot is fixed and only its division
changes**. `--any-total` turns the check off. One game prints one line (the
winner and the turns it took); many print a per-seat table of win rate with a
binomial error, plus the turn distribution of the games that were won.
`--csv` writes a row per game for a plotting script, `--json` the summary.
Game *i* is seeded `--seed + i`, so a run is reproducible whatever `--jobs`
is set to, and any single game in it can be replayed from the seed the CSV
records. About 100–120 games a second on eight cores.

**Not every game ends, and that is a real result, not a bug.** Bots do not
trade, so a monopoly forms only when the dice hand somebody a whole colour
group; a board where nobody holds one can run forever. At the default 2,000
turn cap, equal stakes decide 78 % of two-player games and 28 % of six-player
games — and raising the cap to 20,000 moves the two-player number by nothing
at all, so those boards are genuinely stuck rather than merely slow. They are
reported as `timeout` and counted separately, never silently credited to the
player who happened to be ahead; `--decide-timeouts leader` asks for that
convention explicitly when a study needs every game to have a winner.

> **Deviations from the rest of the plan, carried forward:**
> - **`main.bot_act` no longer contains the strategy plumbing.** It was
>   duplicated the moment a second driver existed, so the decision moved to
>   `headless.bot_step` and `bot_act` kept only the timer. The `bot.act` debug
>   lines moved with it, so the transcript of a windowed game is unchanged.
> - **`headless.py` re-states `TOKEN_COLORS`** rather than importing it from
>   `ui.theme`, which would drag pygame into a module whose whole point is not
>   needing it.
> - **A stalled game is reported, not raised.** If the driver ever wedges —
>   neither the game nor any bot moving for `STALL_LIMIT` iterations — the
>   result comes back with `status="stalled"` so one bad game cannot take a
>   ten-thousand-game study down with it. Nothing has produced one yet.

---

## Implementation Notes for Claude Code

1. **Start with data files first** (`spaces.json`, `chance.json`, `community_chest.json`) — all game logic reads from these; getting them right before writing logic prevents rework.

2. **Build and test phases in order** — each phase should be runnable before the next begins:
   - Phase 1–2: data + classes (no pygame yet, unit-testable)
   - Phase 3: setup screen (pygame window, no board)
   - Phase 4–5: board draws, tokens place, dice roll (no game logic)
   - Phase 6–7: full turn loop with basic buy/rent/tax
   - Phase 8–13: features layered on

3. **pygame event loop** lives entirely in `main.py`. Each module exposes a `draw(surface)` and `handle_event(event)` interface; `game.py` orchestrates which ones are active.

4. **No external dependencies** beyond `pygame` and Python stdlib. Install with `pip install pygame`.

5. **Screen size**: target 1280×800. Board occupies ~800×800 on the left; HUD panel is 480×800 on the right.

6. **Font**: use `pygame.font.SysFont("monospace", size)` — no font files needed.

7. **Color constants**: define a palette dict at the top of `renderer.py` — board background (cream), property colors (8 standard groups), UI chrome (dark gray), text (near-black).
