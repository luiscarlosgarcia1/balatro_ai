> **Future work: SMODS (Steamodded) support in headless mode**
>
> Currently, headless instances run Balatro's game logic directly under LuaJIT, bypassing the Love2D binary entirely. This means **lovely** (the native DLL/SO that patches Love2D at runtime to inject Steamodded) never runs, so the `SMODS` global and mod loading pipeline don't exist in headless mode.
>
> Why it matters: training on modded content (modded jokers, decks, challenges) requires SMODS to be present so that Steamodded can scan `Mods/` and load them. Without it, only vanilla Balatro is available to the agent.
>
> Likely approach: instead of loading raw `Balatro/main.lua`, point the headless boot script at the lovely-patched entry point (`Balatro/Mods/lovely/dump/main.lua`), which already has the Steamodded bootstrap baked in. Steamodded would then set up `SMODS` and load mods naturally. The main prerequisite is making `love.filesystem` in `love_stub.lua` functional (backed by real Lua `io`/`lfs`) so Steamodded can actually scan directories and read mod files.
>
> Note: game speed for training is a separate concern — headless already runs uncapped (no 60 FPS limit), and animation timer speed can be controlled by adjusting `FIXED_DT` in `headless/run.lua` without needing any mod.

<div align="center">
  <h1>BalatroBot</h1>
  <p align="center">
    <a href="https://github.com/coder/balatrobot/releases">
      <img alt="GitHub release" src="https://img.shields.io/github/v/release/coder/balatrobot?include_prereleases&sort=semver&style=for-the-badge&logo=github"/>
    </a>
    <a href="https://discord.gg/TPn6FYgGPv">
      <img alt="Discord" src="https://img.shields.io/badge/discord-server?style=for-the-badge&logo=discord&logoColor=%23FFFFFF&color=%235865F2"/>
    </a>
  </p>
  <div><img src="./docs/assets/balatrobot.svg" alt="balatrobot" width="170" height="170"></div>
  <p><em>API for developing Balatro bots</em></p>
</div>

---

BalatroBot is a mod for Balatro that serves a JSON-RPC 2.0 HTTP API, exposing game state and controls for external program interaction. The API provides endpoints for complete game control, including card selection, shop transactions, blind selection, and state management. External clients connect via HTTP POST to execute game actions programmatically.

## 📚 Documentation

https://coder.github.io/balatrobot/

## 🚀 Related Projects

- [**BalatroBot**](https://github.com/coder/balatrobot): API for developing Balatro bots
- [**BalatroLLM**](https://github.com/coder/balatrollm): Play Balatro with LLMs
- [**BalatroBench**](https://github.com/coder/balatrobench): Benchmark LLMs playing Balatro

## Headless Mode

Run a single headless instance with `luajit headless/run.lua`. This requires the Balatro game source to be present at `balatrobot/Balatro/`, and `BALATRO_MOD_ROOT` must point to the BalatroBot mod directory.

Run a pool of parallel headless instances with `python headless/pool.py --n <count>`. Each instance gets its own port, save directory, and log file, and the HTTP JSON-RPC API is identical in headless and windowed modes.

## 🙏 Acknowledgments

This project is a fork of the original [balatrobot](https://github.com/besteon/balatrobot) repository. We would like to acknowledge and thank the original contributors who laid the foundation for this framework:

- [@phughesion](https://github.com/phughesion)
- [@besteon](https://github.com/besteon)
- [@giewev](https://github.com/giewev)

The original repository provided the initial API and botting framework that this project has evolved from. We appreciate their work in creating the foundation for Balatro bot development.
