# discord-bot

A personal Discord bot for one server. Features are added one cog at a time — no upfront spec, no pre-built abstractions. Built on [discord.py](https://discordpy.readthedocs.io/) and [aiosqlite](https://aiosqlite.omnilib.dev/), packaged for Docker.

## Features

- **Birthday** — `/birthday` to register a month/day; the bot announces it once a year at 09:00 in a configured channel.
- **Deleted-message archive** — full-logging archive with a live mod-log channel for every edit and delete, plus moderator-only `/archive` queries to look anything up after the fact. 90-day retention.
- **Link embedder** — automatically rewrites tracked links from supported platforms (`threads.com` / `threads.net`, `instagram.com` URLs carrying an `?igsh=…` share tracker, and `dcard.tw` URLs carrying a `?cid=…` campaign tracker), reposts a cleaned version via webhook with a custom embed built from a Playwright sidecar, then offers the original poster a confirm/retract via reactions.

## Quick start

```sh
cp .env.example .env   # fill in DISCORD_TOKEN and channel/user IDs
docker compose up -d --build
docker compose logs -f
```

For the full setup (Discord application + privileged intents + bot permissions, env vars, deployment options), see **[docs/USAGE.md](./docs/USAGE.md)**.

For the slash command reference and per-feature behavior, see **[docs/FEATURES.md](./docs/FEATURES.md)**.

## Project docs

| File | For whom | What |
|---|---|---|
| `README.md` | newcomer | This file — orientation and pointers |
| `docs/USAGE.md` | operator | Discord app setup, env config, run + deploy, troubleshooting |
| `docs/FEATURES.md` | end user / mod | Slash commands and automatic behaviors, per cog |
| `docs/CONTEXT.md` | contributor | Domain language (Archive vs Mod-log, Moderator vs Admin, etc.) |
| `docs/adr/` | contributor | Architecture decision records — *why*, not *what* |
| `CLAUDE.md` | Claude Code (also human-readable) | Internal architecture, cross-cog handshakes, gotchas |

## Repository layout

```
.
├── bot.py              # entry point — commands.Bot subclass
├── db.py               # shared aiosqlite connection + schema
├── mod_log.py          # shared edit/delete embed builders
├── utils.py            # tiny cross-cog helpers (parse_id_set)
├── cogs/
│   ├── birthday.py
│   ├── archive.py
│   └── link_embedder.py
├── preview/            # sidecar: Node + Playwright link-preview service
│   ├── server.cjs
│   ├── package.json
│   └── Dockerfile
├── tests/              # pytest suite (pure-logic + cog-level)
├── data/               # runtime state (gitignored): bot.db, attachments/
├── docs/
│   ├── USAGE.md
│   ├── FEATURES.md
│   ├── CONTEXT.md
│   └── adr/            # architecture decision records
├── CLAUDE.md           # AI-facing internal architecture (kept at root)
├── README.md
├── Dockerfile
└── docker-compose.yml
```

To add a feature, create `cogs/<name>.py`, add `"cogs.<name>"` to `EXTENSIONS` in `bot.py`, and document it in [docs/FEATURES.md](./docs/FEATURES.md).
