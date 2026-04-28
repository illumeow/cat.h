# Usage

Operating guide for the bot — first-time setup, day-to-day commands, and deployment. For internal architecture see `CLAUDE.md`; for domain language see `CONTEXT.md`.

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

## Day-to-day commands

After the bot connects for the first time it runs `tree.sync()`; Discord can take up to an hour to refresh the slash command list in your client. If commands are missing, give it time or kick + re-invite the bot.

### Birthday

| Command | Who | Effect |
|---|---|---|
| `/birthday set month:<1-12> day:<1-31>` | anyone | Register your birthday (overwrites any existing) |
| `/birthday show [user]` | anyone | Show yours, or another user's |
| `/birthday remove` | anyone | Remove your own |
| `/birthday remove user:<member>` | **Admin** (Administrator or Manage Server) | Remove someone else's |

The bot wishes you happy birthday at **09:00 in `TIME_ZONE`** in `BIRTHDAY_CHANNEL_ID`. Feb 29 entries fire on Feb 28 in non-leap years.

### Archive (Moderator only)

`MODERATOR_IDS` is a static allowlist — **not** a Discord permission. Only IDs listed there can run these commands.

| Command | Effect |
|---|---|
| `/archive deleted [user] [channel] [limit]` | List recent deleted messages, optionally filtered. Default limit 10, max 25. Ephemeral output |
| `/archive show <message_id>` | Full detail: original content, every edit revision, deletion timestamp, attachment status. Ephemeral output |

Independent of the commands, the bot posts a **live notice** in `MOD_LOG_CHANNEL_ID` every time a tracked message is edited (showing prior → new) or deleted (showing the final content + any attachments).

Retention: **90 days from message creation**. The archive purges nightly at 03:00 in `TIME_ZONE` and removes both DB rows (cascading to edits and attachment metadata) and the on-disk attachment files at `data/attachments/<message_id>/`.

### Threads embedder

No commands. When someone posts a `threads.com` or `threads.net` link, the bot:

1. Strips tracking query params (`?xmt=…` etc.)
2. Deletes the original message
3. Reposts the cleaned link via a per-channel webhook, using the original poster's username and avatar — so Discord renders an embed preview
4. Adds ✅ and ❌ reactions on the repost

The **original poster** (and only the original poster) can:
- ✅ → confirm the repost. Bot clears all reactions; message stays as-is.
- ❌ → retract. Bot deletes the repost and posts a "Deleted" notice in `MOD_LOG_CHANNEL_ID`.

After **7 days** the tracking row expires and the reactions stop being interactive — the message itself stays in chat indefinitely.

If the bot is missing **Manage Messages** in a channel, it falls back to keeping the original alongside the webhook repost (you'll see duplicates — that's the signal to fix the permission). If it's missing **Manage Webhooks**, the embedder is silently disabled in that channel.

The embedder also works **inside Discord threads** — the webhook is created on the parent channel and the cleaned message is posted into the thread via `webhook.send(thread=...)`. This requires **Send Messages in Threads** in addition to the permissions above.

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

## Troubleshooting

- **Slash commands not appearing**: Discord caches the per-guild command tree for up to an hour. Wait, or remove + re-invite the bot.
- **`Mod-log channel … not in cache`**: the bot is starting up. Resolves once the gateway connection is fully ready (a few seconds).
- **`Missing Manage Webhooks` / `Missing Manage Messages`**: grant the permission to the bot's role; the next message will pick it up. No restart needed.
- **Archive shows 0 results for a known deleted message**: check whether the channel is in `ARCHIVE_EXCLUDED_CHANNELS`, whether the message was older than 90 days, or whether the bot was offline when the message was originally sent (only messages the bot has seen via `on_message` are tracked).
- **Reset everything**: `docker compose down`, `rm -rf data/bot.db data/attachments`, `docker compose up -d`.
