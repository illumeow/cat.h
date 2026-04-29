# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project intent

A personal Discord bot the owner is writing for their own server. **Features will be added one at a time, incrementally** — there is no master spec to design against, so don't pre-build framework/abstraction layers in anticipation of future commands. Add scaffolding only when the next concrete feature requires it, and let architecture emerge from the second or third similar feature, not the first.

For an at-a-glance overview see `README.md`; for operator setup see `USAGE.md`; for end-user / mod command reference see `FEATURES.md`. For domain language (Archive, Mod-log, Moderator vs. Admin, etc.), see `CONTEXT.md`. For load-bearing technical decisions, see `docs/adr/`.

## Environment

- Python **3.14** (CPython, aarch64 macOS), pinned in `.venv/pyvenv.cfg`.
- The venv is managed by [`uv`](https://docs.astral.sh/uv/) (v0.11.7). Activate with `source .venv/bin/activate` or invoke tools via `uv run …`.
- When dependencies are added, prefer `uv add <pkg>` (writes to `pyproject.toml`) over `pip install` so the lockfile stays authoritative.

## Bot

- Library: **discord.py** with the `message_content` privileged intent enabled (also requires the toggle in the Discord developer portal). Slash commands via `app_commands`, scheduled jobs via `discord.ext.tasks`.
- Entry point: `bot.py` — a thin `commands.Bot` subclass that initializes the SQLite connection (`db.init_db()`), then calls `load_extension(...)` for each cog in `EXTENSIONS` and runs `tree.sync()` once in `setup_hook`. Run with `uv run python bot.py`. Syntax check with `uv run python -m py_compile bot.py db.py mod_log.py cogs/*.py`.
- Features live in `cogs/<feature>.py`. Each cog defines a `commands.Cog` subclass and an async `setup(bot)` function so `load_extension` can pick it up. **To add a new feature: create a new cog file, add its dotted path to the `EXTENSIONS` tuple in `bot.py`.** Don't grow `bot.py` itself.
- Slash command groups belong as **class attributes** on the cog (e.g. `birthday = app_commands.Group(...)`), with subcommands decorated `@birthday.command(...)`. Tasks (`@tasks.loop`) are methods; start them in `__init__` and cancel in `cog_unload`.
- Config is read from `.env` at startup via `load_dotenv()` in `bot.py` (see `.env.example`). Required: `DISCORD_TOKEN`. Feature-scoped vars (e.g. `BIRTHDAY_CHANNEL_ID`) are read at the top of the cog that uses them. Cross-cutting vars are named generically (e.g. `TIME_ZONE`, default `UTC`; `MOD_LOG_CHANNEL_ID`) so cogs can share them — name new env vars accordingly.

## Persistence

- One SQLite file: `data/bot.db`, accessed via `aiosqlite`. The schema lives in `db.py` (`CREATE TABLE IF NOT EXISTS …`); no migration framework — add `ALTER TABLE` statements directly when needed. See `docs/adr/0001-sqlite-for-all-state.md`.
- The connection is opened in `Bot.setup_hook` and exposed as `bot.db` for cogs to use (`self.bot.db.execute(...)`).
- Downloaded attachments live at `data/attachments/<message_id>/<filename>` (created on demand by the archive cog).
- Everything under `data/` is git-ignored.

## Cross-cog handshakes

- `bot.suppressed_deletes: set[int]` — the threads cog adds a message ID before deleting the original (link rewrite). The archive cog checks the set in `on_raw_message_delete` and **still marks the row deleted + downloads attachments** (preserves the audit trail of the original uncleaned URL), but **skips the mod-log notice** — the bot caused the delete, not the user. The set is in-memory only; bot restarts clear it (acceptable since suppression only matters within a single delete event).
- The mod-log embed builders live in `mod_log.py` so any cog can `import mod_log` and call `post_deleted` / `post_edited` with the same visual format.

## Cogs

- **Birthday** (`cogs/birthday.py`): `/birthday` group (`set` / `remove` / `show`, `guild_only`) + daily 09:00 announcement in `BIRTHDAY_CHANNEL_ID`. `/birthday remove <user>` requires Discord-permission **Admin** (`Administrator` or `Manage Server`) to target someone else. Feb-29 falls back to Feb 28 in non-leap years. State in `birthdays` table.
- **Archive** (`cogs/archive.py`): full-logging archive of every visible message (`messages` table) with edit history (`message_edits`) and downloaded attachments (`attachments`). Deletions / edits get a live notice posted to `MOD_LOG_CHANNEL_ID`. Skips DMs, system messages, webhook messages, channels in `ARCHIVE_EXCLUDED_CHANNELS`, and the mod-log channel itself (auto-excluded). On delete, attachments under 25 MB are downloaded to `data/attachments/<message_id>/`. Daily 03:00 TTL purge drops anything older than 90 days. The `/archive` group is registered with `default_permissions=Permissions()` so it's hidden from every member by default; the server admin grants a moderator role access once via Server Settings → Integrations, and Discord enforces that gate at invocation time (no in-handler authorization check). See `docs/adr/0002-full-logging-archive.md`.
- **Threads** (`cogs/threads.py`): rewrites `threads.com` / `threads.net` links by stripping the query string, deletes the original, and reposts via a per-channel webhook (cached, named `<bot> Link Embedder`) under the original poster's name and avatar. Adds ✅ / ❌ reactions; the original poster's ✅ clears state, ❌ deletes the repost and posts a mod-log "Deleted" notice. Tracking lives in `webhook_reposts` with a 7-day TTL. Excluded channels: `THREADS_EXCLUDED_CHANNELS`.

## Permissions the bot needs in Discord

- Read Messages, Send Messages (everywhere it's expected to function)
- **Send Messages in Threads** (so the archive cog can post mod-log notices about thread activity, and the threads cog can post webhook reposts inside Discord threads)
- **Manage Messages** (threads cog deletes original messages; without it, the original is left alongside the webhook repost as a fallback signal)
- **Manage Webhooks** (threads cog creates/looks up the per-channel link embedder webhook on the parent channel)
- Add Reactions (threads cog seeds ✅/❌)
- Read Message History (archive cog needs to fetch messages by ID for `/archive show`)

## Discord threads vs. threads.com

The two share a name but are unrelated. **Discord threads** (sub-channels) are handled transparently:
- Archive logs messages from Discord threads like any other channel; `ARCHIVE_EXCLUDED_CHANNELS` matches against either the thread's own ID or its parent's ID (so listing a parent excludes all its threads).
- The threads.com link rewriter also runs inside Discord threads — it gets the webhook from the *parent* channel (`message.channel.parent`) and posts back via `webhook.send(thread=message.channel)`.

## Deployment

- Containerized via the project `Dockerfile` (multi-stage with `uv sync --frozen --no-install-project --no-dev`) and `docker-compose.yml` (one `bot` service, `./data:/app/data` volume, `env_file: .env`, `restart: unless-stopped`).
- The base image (`python:3.14-slim`) is multi-arch — the same Dockerfile builds for both `linux/amd64` and `linux/arm64`. Whatever VM you `docker compose build` on picks the right arch automatically (no buildx required for personal use).
- Standard run: `docker compose up -d` from the project root after creating a `.env` from `.env.example`.

## Misc gotchas

- Discord caches the slash command tree per-guild for up to an hour after `tree.sync()`; if a renamed/removed command still shows in the client, that's expected and resolves on its own.
- `discord.RawMessageUpdateEvent.data` is the raw gateway dict; `"content"` is only present on content edits, so the archive cog gates on `if "content" not in payload.data: return` to avoid logging embed/pin/etc. updates.
- Tasks decorated with `@tasks.loop(time=...)` are evaluated at class definition time — meaning `TZ` and any time constants must be available at module import. We read them at module top-level, so anything depending on env vars must already be set in the process before importing the cog (which `load_dotenv()` in `bot.py` ensures).
