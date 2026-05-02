# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project intent

A personal Discord bot the owner is writing for their own server. **Features will be added one at a time, incrementally** — there is no master spec to design against, so don't pre-build framework/abstraction layers in anticipation of future commands. Add scaffolding only when the next concrete feature requires it, and let architecture emerge from the second or third similar feature, not the first.

For an at-a-glance overview see `README.md`; for operator setup see `docs/USAGE.md`; for end-user / mod command reference see `docs/FEATURES.md`. For domain language (Archive, Mod-log, Moderator vs. Admin, etc.), see `docs/CONTEXT.md`. For load-bearing technical decisions, see `docs/adr/`.

## Workflow

For substantial work — new cogs, deepening refactors, anything touching multiple files or worth a plan — use the superpowers workflow rather than ad-hoc edits. This is the pattern the recent Birthday calendar / Archive / Webhook reposts module extractions used. Invoke skills via the `Skill` tool (do not `Read` the SKILL.md files).

**Skills, in the order you typically reach for them:**
- `superpowers:brainstorming` — for net-new features, before any plan exists.
- `superpowers:improve-codebase-architecture` — for refactors. Surfaces deepening candidates (shallow modules → deep ones), grills the chosen one, then hands off to `writing-plans`.
- `superpowers:writing-plans` — turns an agreed design into a numbered task plan. Plans go in `docs/superpowers/plans/YYYY-MM-DD-<name>.md`.
- `superpowers:using-git-worktrees` — REQUIRED before implementing a plan. The project uses `.worktrees/` (already gitignored).
- `superpowers:subagent-driven-development` — executes the plan task-by-task: per task, dispatch implementer subagent → spec-compliance reviewer → code-quality reviewer; loop until both approve, then move on. One commit per task. Final review of the whole branch at the end.
- `superpowers:finishing-a-development-branch` — fast-forward merge to `main`, delete the branch, remove the worktree.

**End-to-end pattern:**
1. Brainstorm (new feature) or `improve-codebase-architecture` (refactor) → user picks the candidate.
2. `writing-plans` produces a plan; user approves.
3. `using-git-worktrees` creates `.worktrees/<branch>`.
4. `subagent-driven-development` runs each task to completion before moving to the next.
5. `finishing-a-development-branch` merges to `main` and cleans up.
6. **Wait for the user to explicitly say "ship it"** before running `scripts/deploy.sh`. Merging is not deploying.

**Subagent prompts MUST pin the working directory.** Every `Bash` command in implementer/reviewer prompts — especially every `git` command — has to start with `cd /Users/illumeow/Developer/discord-bot/.worktrees/<branch> &&`. Without this, fast/cheap models occasionally commit to `main` from the parent CWD even when file paths were absolute. Recovery is cherry-pick + reset of `main`; the prompt-level guard prevents the mistake in the first place.

**One feature/task per commit.** Don't pile several tasks into one commit. (See also `feedback_commit_per_feature.md` in auto-memory.)

**When the workflow is overkill:** typo fixes, single-line tweaks, env-var renames, doc-only edits, one-cog one-line bug fixes. Just edit and commit. The Project-intent rule still holds — don't extract a `core/` module on the first appearance of a pattern; wait for the second or third.

## Environment

- Python **3.14** (CPython, aarch64 macOS), pinned in `.venv/pyvenv.cfg`.
- The venv is managed by [`uv`](https://docs.astral.sh/uv/) (v0.11.7). Activate with `source .venv/bin/activate` or invoke tools via `uv run …`.
- When dependencies are added, prefer `uv add <pkg>` (writes to `pyproject.toml`) over `pip install` so the lockfile stays authoritative.

## Bot

- Library: **discord.py** with the `message_content` privileged intent enabled (also requires the toggle in the Discord developer portal). Slash commands via `app_commands`, scheduled jobs via `discord.ext.tasks`.
- Entry point: `bot.py` — a thin `commands.Bot` subclass that initializes the SQLite connection (`db.init_db()`), then calls `load_extension(...)` for each cog in `EXTENSIONS` and runs `tree.sync()` once in `setup_hook`. Run with `uv run python bot.py`. Syntax check with `uv run python -m py_compile bot.py core/*.py cogs/*.py`.
- Features live in `cogs/<feature>.py`. Each cog defines a `commands.Cog` subclass and an async `setup(bot)` function so `load_extension` can pick it up. **To add a new feature: create a new cog file, add a `(dotted-path, "<FEATURE>_ENABLED")` entry to the `EXTENSIONS` tuple in `bot.py`, and add `<FEATURE>_ENABLED=true` to `.env.example`.** Don't grow `bot.py` itself.
- Per-cog feature toggles live in `EXTENSIONS` as `(dotted-path, env-var-name)` pairs. `bot.setup_hook` checks each via `parse_bool_env(..., default=True)` before `load_extension`; setting the var to `false` (case-insensitive) skips the cog entirely (no commands, listeners, or task loops register). Default-enabled by design — an upgrader who doesn't set the new var keeps existing behavior. Flipping a toggle requires a bot restart.
- Slash command groups belong as **class attributes** on the cog (e.g. `birthday = app_commands.Group(...)`), with subcommands decorated `@birthday.command(...)`. Tasks (`@tasks.loop`) are methods; start them in `__init__` and cancel in `cog_unload`.
- Config is read from `.env` at startup via `load_dotenv()` in `bot.py` (see `.env.example`). Required: `DISCORD_TOKEN`. Feature-scoped vars (e.g. `BIRTHDAY_CHANNEL_ID`) are read at the top of the cog that uses them. Cross-cutting vars are named generically (e.g. `TIME_ZONE`, default `UTC`; `MOD_LOG_CHANNEL_ID`) so cogs can share them — name new env vars accordingly.

## Sidecars

- **`preview/`** — Node.js + Playwright service that returns OG metadata (title, description, image, video) for a URL. Built and run as a separate container in `docker-compose.yml` on the internal compose network; the bot reaches it at `http://preview:3000` via `PREVIEW_SERVICE_URL`. The bot tolerates the sidecar being unreachable — it falls back to no custom embed. Source: `preview/server.cjs` (single file, plain Node `http` + a long-lived Chromium); image: `mcr.microsoft.com/playwright:vX-jammy` so we don't have to install Chromium dependencies ourselves. **Why a sidecar instead of in-process Playwright**: keeps the Python image small, isolates the heavy/crash-prone browser from the bot's gateway connection, and the same service is reusable for future link-preview needs.
- Anti-bot handling: some sites (Dcard) sit behind Cloudflare. The sidecar detects when `document.title` starts as a CF challenge ("Just a moment...") and waits up to `CHALLENGE_WAIT_MS` (default 8s) for the title to clear before extracting metadata. This handles the basic JS challenge tier. For more aggressive tiers (Dcard's current setup), the title doesn't change in time and the sidecar returns the challenge metadata as-is — the bot's `_build_preview_embeds` then recognizes the pattern (via `CHALLENGE_TITLE_RE`) and suppresses the embed rather than rendering a misleading "Just a moment..." in chat. Net effect: the URL is still rewritten/cleaned, the user just doesn't get a custom embed for that one. The challenge-detection regex in `preview/server.cjs` mirrors the Python one in `cogs/link_embedder.py` and they should be kept in sync.

## Persistence

- One SQLite file: `data/bot.db`, accessed via `aiosqlite`. The schema lives in `core/db.py` (`CREATE TABLE IF NOT EXISTS …`); no migration framework — add `ALTER TABLE` statements directly when needed. See `docs/adr/0001-sqlite-for-all-state.md`.
- The connection is opened in `Bot.setup_hook` and exposed as `bot.db` for cogs to use (`self.bot.db.execute(...)`).
- Downloaded attachments live at `data/attachments/<message_id>/<filename>` (created on demand by the archive cog).
- Everything under `data/` is git-ignored.

## Cross-cog handshakes

- `bot.suppressed_deletes: set[int]` — the link embedder cog adds a message ID before deleting the original (URL rewrite). The archive cog checks the set in `on_raw_message_delete` and **leaves the row's `deleted_at` NULL** because the webhook repost is now the user-facing message — the *intentional* deletion is whenever the repost itself is removed (❌ press, an admin deleting it via Discord's UI, etc.), at which point the link embedder's own listeners run `_finalize_repost(...)` to stamp `deleted_at` on the original (via the `original_message_id` it stored in `webhook_reposts`) and post the mod-log "Deleted" notice. The original `content` (the user's text with the un-cleaned URL) stays in the row so `/archive show` still reads it. The archive also skips the attachment download (URL rewrites are text-only) and the mod-log notice (the bot, not the user, caused this delete) — a `log.info` is emitted instead for terminal-level debugging. The set is in-memory only; bot restarts clear it (acceptable since suppression only matters within a single delete event).
- `bot.recent_edit_mod_logs: dict[int, int]` — when the archive cog posts an "Edited" mod-log notice, it stores `original_message_id → mod_log_message_id` here. The link embedder pops the entry post-rewrite and re-targets the embed's jump URL at the webhook repost (the original is gone by then). Bounded to ~200 entries by archive's own oldest-first eviction; entries that the link embedder doesn't claim simply age out. Best-effort: if the archive's task hasn't inserted yet by the time the link embedder looks (rare scheduling order), the original URL stays stale — same fallback as no link embedder.
- The mod-log embed builders live in `core/mod_log.py` so any cog can `from core import mod_log` and call `post_deleted` / `post_edited` with the same visual format. `post_edited` returns the sent `Message` so callers can update the embed later.
- Cross-cog parsing helpers (currently just `parse_id_set` for comma-separated env-var ID lists) live in `core/utils.py`.

## Cogs

- **Birthday** (`cogs/birthday.py`): `/birthday` group (`set` / `remove` / `show`, `guild_only`) + daily 09:00 announcement in `BIRTHDAY_CHANNEL_ID`. `/birthday remove <user>` requires Discord-permission **Admin** (`Administrator` or `Manage Server`) to target someone else. State and the leap-year rule (Feb-29 falls back to Feb 28 in non-leap years) live in the **Birthday calendar** (`core/birthday_calendar.py`); the cog is the Discord-side handler only.
- **Archive** (`cogs/archive.py`): full-logging archive of every visible message (`messages` table) with edit history (`message_edits`) and downloaded attachments (`attachments`). Deletions / edits get a live notice posted to `MOD_LOG_CHANNEL_ID`. Skips DMs, system messages, webhook messages, channels in `ARCHIVE_EXCLUDED_CHANNELS`, and the mod-log channel itself (auto-excluded). On delete, attachments under 25 MB are downloaded to `data/attachments/<message_id>/`. Edit-time attachment removal is also detected (Discord delivers it as `MESSAGE_UPDATE`, not `MESSAGE_DELETE`) — when the bot sees an attachment that was in our DB but is no longer in the payload, it eagerly downloads the bytes from the still-hot CDN URL and posts an "Attachment removed" mod-log notice. The download helper (`_download_attachments`) is idempotent (filters on `local_path IS NULL AND skipped_reason IS NULL`), so the subsequent full-message delete won't re-fetch what was already saved. Daily 03:00 TTL purge drops anything older than 90 days. State (the `messages` / `message_edits` / `attachments` table interface, on-disk attachment vault under `data/attachments/`, and the 90-day TTL rule) lives in `core/archive.py`; the cog is the Discord-side handler — listeners, slash commands, mod-log integration, and the cross-cog handshakes for `suppressed_deletes` / `recent_edit_mod_logs`. The `/archive` group is registered with `default_permissions=Permissions()` so it's hidden from every member by default; the server admin grants a moderator role access once via Server Settings → Integrations, and Discord enforces that gate at invocation time (no in-handler authorization check). See `docs/adr/0002-full-logging-archive.md`.
- **Link embedder** (`cogs/link_embedder.py`, class `LinkEmbedderCog`): rewrites tracked links from supported platforms via the `URL_RULES` list at module top. Each rule is `(name, pattern, cleaner, preview)`; matching the pattern is what triggers a repost, so `threads.com` (every URL → strip whole query), `instagram.com` URLs with `?igsh=…` (only `igsh` removed, other params kept), and `dcard.tw` URLs with `?cid=…` (only `cid` removed) coexist cleanly. The `preview` flag controls whether the cog asks the sidecar for OG metadata and emits a custom embed (`True` for threads/IG, `False` for Dcard — Cloudflare blocks the sidecar there reliably enough that we'd just get "Just a moment..."; the URL stays bare so Discord's native auto-embed can try). Adding a platform = appending a row. Both `on_message` (initial post) and `on_raw_message_edit` (edits that *add* a tracked link to a previously plain message) feed `_process_message`, which is the single shared path. The edit listener pre-checks the partial payload's `content` against the rule patterns before fetching the full Message — so embed/pin/etc. updates stay free. The repost flow itself is platform-agnostic: per-channel webhook (cached, named `<bot> Link Embedder`) sends under the original poster's name and avatar; ✅ / ❌ reactions from the original poster commit / delete; ❌ also posts a mod-log "Deleted" notice. For each rewritten URL the cog calls the **preview sidecar** (`preview/`) for OG metadata and attaches a custom `discord.Embed` to the webhook send. To stop Discord from rendering its own (broken) native embed for the same URL alongside ours, the cog wraps each rewritten URL in `<…>` in the message body — that's Discord's per-URL escape for "don't auto-preview this link." (Don't be tempted to use `suppress_embeds=True`: that flag sets the message-level SUPPRESS_EMBEDS bit, which hides every embed including our own.) If `PREVIEW_SERVICE_URL` is empty or the sidecar fails, the embeds list is empty, no `<…>` wrapping is applied, and the post falls back to a plain cleaned URL with whatever native embed Discord can produce. Tracking lives in `webhook_reposts` with the same 90-day TTL as the archive (✅/❌ both delete the row immediately; the TTL only governs the rare case where the user never reacts). Excluded channels: `LINK_EMBEDDER_EXCLUDED_CHANNELS`, plus the mod-log channel itself (auto-excluded so the bot leaves it as a plain audit feed). The `webhook_reposts` table interface lives in `core/webhook_reposts.py`; the cog is the Discord-side handler — listeners, the preview-sidecar client, webhook lookup/cache, and the cross-cog handshakes for `suppressed_deletes` / `recent_edit_mod_logs`.

## Permissions the bot needs in Discord

- Read Messages, Send Messages (everywhere it's expected to function)
- **Send Messages in Threads** (so the archive cog can post mod-log notices about thread activity, and the link embedder can post webhook reposts inside Discord threads)
- **Manage Messages** (link embedder deletes original messages; without it, the original is left alongside the webhook repost as a fallback signal)
- **Manage Webhooks** (link embedder creates/looks up the per-channel `<bot> Link Embedder` webhook on the parent channel)
- Add Reactions (link embedder seeds ✅/❌)
- Read Message History (archive cog needs to fetch messages by ID for `/archive show`)

## Discord threads (sub-channels)

Don't confuse these with `threads.com` URLs (the Meta product) — different things; we handle Discord-thread sub-channels transparently across the codebase:
- Archive logs messages from Discord threads like any other channel; `ARCHIVE_EXCLUDED_CHANNELS` matches against either the thread's own ID or its parent's ID (so listing a parent excludes all its threads).
- The link embedder also runs inside Discord threads — it gets the webhook from the *parent* channel (`message.channel.parent`) and posts back via `webhook.send(thread=message.channel)`. `LINK_EMBEDDER_EXCLUDED_CHANNELS` follows the same parent-or-self matching as the archive.

## Deployment

- Containerized via the project `Dockerfile` (multi-stage with `uv sync --frozen --no-install-project --no-dev`) and `docker-compose.yml` (one `bot` service, `./data:/app/data` volume, `env_file: .env`, `restart: unless-stopped`).
- The base image (`python:3.14-slim`) is multi-arch — the same Dockerfile builds for both `linux/amd64` and `linux/arm64`. Whatever VM you `docker compose build` on picks the right arch automatically (no buildx required for personal use).
- Standard run: `docker compose up -d` from the project root after creating a `.env` from `.env.example`.

## Misc gotchas

- Discord caches the slash command tree per-guild for up to an hour after `tree.sync()`; if a renamed/removed command still shows in the client, that's expected and resolves on its own.
- `discord.RawMessageUpdateEvent.data` is the raw gateway dict; `"content"` is only present on content edits, so the archive cog gates on `if "content" not in payload.data: return` to avoid logging embed/pin/etc. updates.
- Tasks decorated with `@tasks.loop(time=...)` are evaluated at class definition time — meaning `TZ` and any time constants must be available at module import. We read them at module top-level, so anything depending on env vars must already be set in the process before importing the cog (which `load_dotenv()` in `bot.py` ensures).
