# Usage

Operating guide for the bot — first-time setup, configuration, run, and deployment. For the slash command reference and per-feature behavior see [FEATURES.md](./FEATURES.md); for internal architecture see [CLAUDE.md](../CLAUDE.md); for domain language see [CONTEXT.md](./CONTEXT.md).

## Prerequisites

- A Discord account with **Manage Server** rights on the server you'll add the bot to.
- For local development: [`uv`](https://docs.astral.sh/uv/) ≥ 0.11. Python 3.14 is auto-fetched by `uv`.
- For deployment: Docker + Docker Compose on any always-on Linux host. The image is multi-arch — same `Dockerfile` works on x86_64 and ARM64 (Oracle Ampere, Raspberry Pi, etc.).

## 1. Create the Discord application

1. Open https://discord.com/developers/applications → **New Application**.
2. **Bot** tab:
   - Click **Reset Token**, copy the token immediately (it's shown once). This is `DISCORD_TOKEN` later.
   - Under **Privileged Gateway Intents**, enable **Message Content Intent**. (Required for the archive cog to see message text and the link embedder to detect tracked URLs.)
3. **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`.
   - Bot Permissions:
     - View Channels, Send Messages, Embed Links, Read Message History, Add Reactions
     - **Send Messages in Threads** — both archive notices and the link embedder need this if any chat happens inside Discord threads
     - **Manage Messages** — the link embedder deletes the user's original to repost a cleaned version
     - **Manage Webhooks** — the link embedder creates a `<botname> Link Embedder` webhook per channel
   - Copy the generated URL, open it, pick your server, **Authorize**.

## 2. Configure

1. Copy the example env file:
   ```sh
   cp .env.example .env
   ```
2. Fill in `.env`. To get any Discord ID, enable **Settings → Advanced → Developer Mode**, then right-click a user / channel and **Copy ID**.

   | Variable | Required | What it does |
   |---|---|---|
   | `DISCORD_TOKEN` | yes | From step 1 |
   | `TIME_ZONE` | recommended | IANA name (e.g. `Asia/Taipei`). Drives the 09:00 birthday announcement and the 03:00 archive purge |
   | `BIRTHDAY_ENABLED` / `ARCHIVE_ENABLED` / `LINK_EMBEDDER_ENABLED` | optional | Per-cog feature toggle. Default: enabled. Set to `false` (also: `no`/`0`/`off`) to skip the cog at startup — its commands, listeners, and task loops won't register. Restart the bot to flip |
   | `BIRTHDAY_CHANNEL_ID` | for birthday | Channel where the daily birthday message is posted |
   | `MOD_LOG_CHANNEL_ID` | for archive / link embedder | Channel where edit / delete notices land. Auto-excluded from both the archive and the link embedder (no recursion) |
   | `ARCHIVE_EXCLUDED_CHANNELS` | optional | Channels the archive should completely ignore. Comma-separated. Listing a parent channel implicitly excludes all of its Discord threads |
   | `LINK_EMBEDDER_EXCLUDED_CHANNELS` | optional | Channels where the link embedder shouldn't run. Comma-separated. Listing a parent channel implicitly excludes all of its Discord threads. The mod-log channel is auto-excluded |
   | `PREVIEW_SERVICE_URL` | optional | URL of the Playwright preview sidecar. Set automatically inside `docker-compose.yml` (`http://preview:3000`); leave blank when running the bot locally without the sidecar to fall back to no custom embed |

   Authorization for `/archive` is **role-based** and configured in Discord's UI, not via an env var — see step 4 below.

## 3. Run

### Docker (recommended for keeping the bot alive)

```sh
docker compose up -d --build
docker compose logs -f
```

State persists in `./data/` on the host (mounted into the container at `/app/data`). Stop with `docker compose down`. Update with `git pull && docker compose up -d --build` — no data loss.

### Locally (for iterating on code)

```sh
uv sync
uv run python bot.py
```

`Ctrl-C` to stop. Same `data/` directory is used.

## 4. Grant moderator access to `/archive` (one-time)

`/archive` ships **hidden from every member by default** (the command sets `default_permissions=Permissions()` so Discord won't display it to anyone). After the bot is online, grant access via **Server Settings → Integrations → your bot**.

Discord's Integrations UI exposes **two levels** of permission, and the per-command override on `/archive` only takes effect once `@everyone` has been explicitly toggled at **both** levels — adding a per-command member/role override on its own is silently ignored.

1. **Application-level** (top of the page, **Command Permissions**) → under **Roles & Members**, set `@everyone` to ✅ **Allow**. This keeps the rest of the bot (e.g. `/birthday`) open to everyone.
2. **Per-command level** → scroll to **Commands**, click `/archive`, and in the **Modify Command Permissions** dialog:
   - Set `@everyone` to ❌ **Deny**.
   - Click **Add Roles or Members**, add your `@Moderators` role, and set it to ✅ **Allow**.
3. **Click Save** in each dialog (the Save button is highlighted while changes are pending).

Discord enforces this server-side — users without the role can't see or invoke the command, so this is the sole authorization gate. The override persists across bot restarts. Repeat per server if you ever invite the bot somewhere else.

Users with the **Administrator** server permission bypass these overrides and can always run every command — that's a Discord built-in, not something the bot can restrict.

> The mirror-image setup also works (app-level `@everyone` ❌, `/archive` override `@everyone` ✅), but it locks down the bot's other commands too. The setup above is the right one for keeping `/birthday` public while restricting `/archive`.

## Deployment notes

The bot is gateway-based (outbound websocket only) — no inbound ports, no public IP needed. Anywhere it can reach Discord works.

For a step-by-step bring-up on Oracle Cloud Always Free (the recommended zero-cost path), see **[DEPLOY.md](./DEPLOY.md)**. The general shape on any Linux host with Docker:

```sh
git clone <repo>
cd discord-bot
cp .env.example .env  # then edit
docker compose up -d --build
```

Updates: `git pull && docker compose up -d --build`. The bind-mounted `./data` directory is what persists; the container itself is disposable. The Dockerfile is multi-arch (`python:3.14-slim`), so x86_64 and ARM64 hosts both work without changes.

## Reset

Wipe all persisted state (birthdays, archived messages, attachments, webhook-repost tracking) and start fresh:

```sh
docker compose down
rm -rf data/bot.db data/attachments
docker compose up -d
```

## Inspect the database

State lives in a single SQLite file at `data/bot.db` (bind-mounted from the host even when running under Docker). The bot opens it in WAL mode, so read-only queries are safe to run while the bot is up.

```sh
sqlite3 data/bot.db
```

Useful starting points:

```sql
.tables                                       -- list tables
.schema birthdays                             -- show one table's columns
SELECT * FROM birthdays;
SELECT id, author_id, deleted_at FROM messages
  WHERE deleted_at IS NOT NULL
  ORDER BY deleted_at DESC LIMIT 20;
SELECT * FROM webhook_reposts;
```

Tables: `birthdays`, `messages`, `message_edits`, `attachments`, `webhook_reposts` (full schema in `db.py`).

## Troubleshooting

- **Slash commands not appearing**: Discord caches the per-guild command tree for up to an hour. Wait, or remove + re-invite the bot.
- **`Mod-log channel … not in cache`**: the bot is starting up. Resolves once the gateway connection is fully ready (a few seconds).
- **`Missing Manage Webhooks` / `Missing Manage Messages`**: grant the permission to the bot's role; the next message will pick it up. No restart needed.
- **Archive shows 0 results for a known deleted message**: check whether the channel is in `ARCHIVE_EXCLUDED_CHANNELS`, whether the message was older than 90 days, or whether the bot was offline when the message was originally sent (only messages the bot has seen via `on_message` are tracked).
