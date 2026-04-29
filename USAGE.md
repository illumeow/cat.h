# Usage

Operating guide for the bot — first-time setup, configuration, run, and deployment. For the slash command reference and per-feature behavior see [FEATURES.md](./FEATURES.md); for internal architecture see [CLAUDE.md](./CLAUDE.md); for domain language see [CONTEXT.md](./CONTEXT.md).

## Prerequisites

- A Discord account with **Manage Server** rights on the server you'll add the bot to.
- For local development: [`uv`](https://docs.astral.sh/uv/) ≥ 0.11. Python 3.14 is auto-fetched by `uv`.
- For deployment: Docker + Docker Compose on any always-on Linux host. The image is multi-arch — same `Dockerfile` works on x86_64 and ARM64 (Oracle Ampere, Raspberry Pi, etc.).

## 1. Create the Discord application

1. Open https://discord.com/developers/applications → **New Application**.
2. **Bot** tab:
   - Click **Reset Token**, copy the token immediately (it's shown once). This is `DISCORD_TOKEN` later.
   - Under **Privileged Gateway Intents**, enable **Message Content Intent**. (Required for the archive cog to see message text and the threads cog to detect links.)
3. **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`.
   - Bot Permissions:
     - View Channels, Send Messages, Embed Links, Read Message History, Add Reactions
     - **Send Messages in Threads** — both archive notices and the threads embedder need this if any chat happens inside Discord threads
     - **Manage Messages** — threads cog deletes the user's original to repost a cleaned version
     - **Manage Webhooks** — threads cog creates a `<botname> Link Embedder` webhook per channel
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
   | `MODERATOR_IDS` | for archive | Comma-separated user IDs allowed to use `/archive`. Empty = command is disabled for everyone |
   | `BIRTHDAY_CHANNEL_ID` | for birthday | Channel where the daily birthday message is posted |
   | `MOD_LOG_CHANNEL_ID` | for archive / threads | Channel where edit / delete notices land. Auto-excluded from the archive (no recursion) |
   | `ARCHIVE_EXCLUDED_CHANNELS` | optional | Channels the archive should completely ignore. Comma-separated. Listing a parent channel implicitly excludes all of its Discord threads |
   | `THREADS_EXCLUDED_CHANNELS` | optional | Channels where the threads.com embedder shouldn't run. Comma-separated. Listing a parent channel implicitly excludes all of its Discord threads |

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

## Deployment notes

The bot is gateway-based (outbound websocket only) — no inbound ports, no public IP needed. Anywhere it can reach Discord works.

**Free tiers that fit comfortably:**
- **Oracle Cloud Always Free.** 4× ARM Ampere cores + 24 GB RAM (or 2× AMD x86 micros). Most generous free option, capacity occasionally tight.
- **Google Cloud Always Free.** 1× `e2-micro` in `us-west1`/`us-central1`/`us-east1`. 1 GB RAM. Reliably available.

Either is roughly 10–100× the resources this bot needs. The Dockerfile builds for both architectures automatically (`python:3.14-slim` is multi-arch).

**On the host:**
```sh
git clone <repo>
cd discord-bot
cp .env.example .env  # then edit
docker compose up -d --build
```

**Updates:**
```sh
git pull
docker compose up -d --build
```

The bind-mounted `./data` directory is what persists; the container itself is disposable.

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
