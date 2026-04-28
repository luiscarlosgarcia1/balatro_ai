# Balaitro Headless Runner

This repo contains the Balatro game source in `Balatro/` plus a headless harness in `headless/` for booting the game, starting a run, and playing scripted actions without a LÖVE window.

Current features:
- Run a single headless Balatro instance with `luajit`.
- Run a managed pool of headless instances with Python.
- Write separate save data and log files per headless instance.

## Getting Started

### Prerequisites

- `luajit`
- `python3`

### Installation

No install step is currently required beyond having `luajit` and `python3` available on your `PATH`.

### Configuration

The headless runtime supports:

- `BALATRO_SAVE_DIR`: Optional override for the instance save directory.
- `BALATRO_HEADLESS_OS`: Optional OS name override used by the LÖVE stub.

### Troubleshooting

- If `python3 headless/pool.py status` shows instances as `"dead"` with `"last_event": "exited"`, that is expected with the current `headless/run.lua` flow because each instance completes its scripted work and exits.
- Per-instance logs are written to `headless/logs/instance_{i}.log`.
- Pool manager state is written to `headless/.pool/status.json`.

## Running the Project

### Single Instance

Run one headless Balatro instance from the project root:

```bash
luajit headless/run.lua
```

### Pool Commands

Start a background pool manager with `N` headless instances:

```bash
python3 headless/pool.py start --n 8
```

Show the current manager and instance status:

```bash
python3 headless/pool.py status
```

Stop the background pool manager cleanly:

```bash
python3 headless/pool.py stop
```

Restart one managed instance by index:

```bash
python3 headless/pool.py restart --index 3
```

Run the pool manager in the foreground for debugging or one-terminal workflows:

```bash
python3 headless/pool.py run --n 8
```

The pool manager behavior is:

- Each instance runs `luajit headless/run.lua`.
- Each instance gets its own save directory at `headless/.save/instance_{i}`.
- Each instance writes logs to `headless/logs/instance_{i}.log`.
- The manager PID and status files live in `headless/.pool/`.

## Project Structure

```text
Balatro/              Game source files
headless/run.lua      Single-instance headless runner
headless/start_run.lua
headless/actions.lua
headless/love_stub.lua
headless/pool.py      Multi-instance pool manager and CLI
```

## Game State Reference

The canonical top-level state enum lives in `Balatro/globals.lua` as `G.STATES`.
For headless work, the most important distinction is:

- Top-level `G.STATE` values drive the game loop.
- Some user-visible screens are overlays, not standalone states.

### Core Run States

| State | Kind | Meaning | Typical entry | Typical exit |
| --- | --- | --- | --- | --- |
| `BLIND_SELECT` | top-level state | Blind choice screen before a round starts | Start run, finish shop, skip/select next blind | `DRAW_TO_HAND`, `GAME_OVER` |
| `DRAW_TO_HAND` | top-level state | Draw/refill transition before the player can act | New round, after discard, after incomplete hand resolution | `SELECTING_HAND`, `GAME_OVER` |
| `SELECTING_HAND` | top-level state | Main play screen with hand selection and play/discard buttons | After draw completes | `HAND_PLAYED`, `DRAW_TO_HAND`, `NEW_ROUND` |
| `HAND_PLAYED` | top-level state | Immediate post-play resolution state | Press Play with a valid selection | `DRAW_TO_HAND`, `NEW_ROUND` |
| `NEW_ROUND` | top-level state | End-of-blind transition state | Hand scored enough chips or ran out of hands | `ROUND_EVAL`, `GAME_OVER` via round-end flow |
| `ROUND_EVAL` | top-level state | Round results / cash-out screen | Winning a blind | `SHOP`, win overlay |
| `SHOP` | top-level state | Shop screen with jokers, vouchers, and boosters | Cash out from round eval | `BLIND_SELECT`, pack states, `PLAY_TAROT` |
| `TAROT_PACK` | top-level state | Arcana booster pack screen | Open Arcana pack | Previous screen or pack close flow |
| `PLANET_PACK` | top-level state | Celestial booster pack screen | Open Celestial pack | Previous screen or pack close flow |
| `SPECTRAL_PACK` | top-level state | Spectral booster pack screen | Open Spectral pack | Previous screen or pack close flow |
| `STANDARD_PACK` | top-level state | Standard booster pack screen | Open Standard pack | Previous screen or pack close flow |
| `BUFFOON_PACK` | top-level state | Buffoon booster pack screen | Open Buffoon pack | Previous screen or pack close flow |
| `PLAY_TAROT` | top-level interrupt state | Temporary consumeable-use interrupt outside pack-local use | Use a Tarot/Planet/Spectral/etc. from a normal screen | Returns to previous state |
| `GAME_OVER` | top-level state | Loss state | Bust / failed round / forced loss | Game-over overlay menu |

### Menu and Non-Run States

| State | Kind | Meaning | Notes |
| --- | --- | --- | --- |
| `SPLASH` | top-level state | Startup splash screen | Precedes the main menu unless skipped |
| `MENU` | top-level state | Main menu | Standard non-run landing state |
| `DEMO_CTA` | top-level state | Demo call-to-action screen | Demo-specific main-menu-like state |
| `SANDBOX` | top-level state | Developer sandbox mode | Debug/dev-only mode |
| `TUTORIAL` | enum value only | Defined in `G.STATES` but appears unused as a real entered state | Tutorial behavior is implemented as an overlay instead |

### Important Non-State Screens

These are valid game/UI situations that matter, but they are not separate `G.STATE` values.

| Screen | Kind | Trigger | Notes |
| --- | --- | --- | --- |
| Win screen | overlay menu | Win the boss blind at the win ante during `ROUND_EVAL` | Important special case: this is a full-screen overlay, not a `WIN` state |
| Game over screen | overlay menu | Enter `GAME_OVER` | Opened by the `GAME_OVER` state handler |
| Deck preview | submode inside `SELECTING_HAND` | Hover/inspect the deck while selecting a hand | Not a separate top-level state |
| Tutorial overlay | overlay | Tutorial events during normal run states | Uses `G.OVERLAY_TUTORIAL`, not `G.STATE = TUTORIAL` |

### Source Pointers

- State enum: `Balatro/globals.lua`
- Main state dispatch and handlers: `Balatro/game.lua`
- Pack opening: `Balatro/card.lua`
- Consumeable interrupt handling: `Balatro/functions/button_callbacks.lua`
- Win/round-end flow: `Balatro/functions/state_events.lua`

## Collaboration

Contributions are currently `TBD`.

## License

License information is `TBD`.

## Credits

- [stable-baselines3-contrib](https://github.com/Stable-Baselines-Team/stable-baselines3-contrib) — contributed RL algorithm implementations used for training
- [balatro-gym](https://github.com/cassiusfive/balatro-gym) — OpenAI Gym environment for Balatro
- [balatrobot](https://github.com/coder/balatrobot) — headless Balatro bot framework
