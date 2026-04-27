# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project intent

A personal Discord bot the owner is writing for their own server. **Features will be added one at a time, incrementally** — there is no master spec to design against, so don't pre-build framework/abstraction layers in anticipation of future commands. Add scaffolding only when the next concrete feature requires it, and let architecture emerge from the second or third similar feature, not the first.

## Environment

- Python **3.14** (CPython, aarch64 macOS), pinned in `.venv/pyvenv.cfg`.
- The venv is managed by [`uv`](https://docs.astral.sh/uv/) (v0.11.7). Activate with `source .venv/bin/activate` or invoke tools via `uv run …`.
- When dependencies are added, prefer `uv add <pkg>` (writes to `pyproject.toml`) over `pip install` so the lockfile stays authoritative.

## Bot

- Library: **discord.py** (slash commands via `app_commands`, daily jobs via `discord.ext.tasks`).
- Entry point: `bot.py` — a thin `commands.Bot` subclass that calls `load_extension(...)` for each cog in `EXTENSIONS` and runs `tree.sync()` once in `setup_hook`. Run with `uv run python bot.py`. Syntax check with `uv run python -m py_compile bot.py cogs/*.py`.
- Features live in `cogs/<feature>.py`. Each cog defines a `commands.Cog` subclass and an async `setup(bot)` function so `load_extension` can pick it up. **To add a new feature: create a new cog file, add its dotted path to the `EXTENSIONS` tuple in `bot.py`.** Don't grow `bot.py` itself.
- Slash command groups belong as **class attributes** on the cog (e.g. `birthday = app_commands.Group(...)`), with subcommands decorated `@birthday.command(...)`. Tasks (`@tasks.loop`) are methods; start them in `__init__` and cancel in `cog_unload`.
- Config is read from `.env` at startup via `load_dotenv()` in `bot.py` (see `.env.example`). Required: `DISCORD_TOKEN`. Feature-scoped vars (e.g. `BIRTHDAY_CHANNEL_ID`) are read at the top of the cog that uses them. Cross-cutting vars are named generically (e.g. `TIME_ZONE`, default `UTC`) so future cogs can share them — name new env vars accordingly.
- State files live under `data/` (git-ignored, created on first write). Current: `data/birthdays.json`, keyed by Discord user ID.
- Birthday cog: `/birthday` group (`set` / `remove` / `show`, all `guild_only`) + daily `tasks.loop` at 09:00 in `TIME_ZONE`. `/birthday remove <user>` requires `Administrator` or `Manage Server` to target someone other than the caller. Feb-29 birthdays fall back to Feb 28 in non-leap years.
- Discord caches the slash command tree per-guild for up to an hour after `tree.sync()`; if a renamed/removed command still shows in the client, that's expected and resolves on its own.
