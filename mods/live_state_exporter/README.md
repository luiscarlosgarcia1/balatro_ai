# Live State Exporter

This folder is a minimal Steamodded-compatible mod scaffold that exports compact Balatro state snapshots to `AppData/Roaming/Balatro/ai/live_state.json`.

## What It Does

- Hooks a frequent game update path when the mod loads.
- Reads a compact live snapshot from in-memory Balatro state.
- Writes JSON into Balatro's save directory under `ai/live_state.json`.
- Rate-limits writes so the file does not get spammed every frame.
- Emits the high-level fields the Python live parser converts into `GameObservation`.
- Keeps the payload small by exporting only the state needed by the typed observer flow.

## Install

1. Copy the `live_state_exporter/` folder into your Balatro `Mods` directory.
2. Make sure Steamodded is installed and loading mods normally.
3. Launch Balatro and check for `C:/Users/<you>/AppData/Roaming/Balatro/ai/live_state.json`.
4. Point `BalatroObserver` at your Balatro root and confirm Python can parse the exported file into `GameObservation`.

## Notes

- This is intentionally a scaffold, not a complete live telemetry system.
- If Steamodded or Balatro changes the update hook order, the wrapping logic may need a small adjustment.
- The exported file is meant to be consumed directly by the Python live parser and observer service.
