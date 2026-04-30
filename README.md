# discord-bot

A personal Discord bot for one server. Features are added one cog at a time — no upfront spec, no pre-built abstractions. Built on [discord.py](https://discordpy.readthedocs.io/) and [aiosqlite](https://aiosqlite.omnilib.dev/), packaged for Docker.

## Features

- **Birthday** — `/birthday` to register a month/day; the bot announces it once a year at 09:00 in a configured channel.
- **Deleted-message archive** — full-logging archive with a live mod-log channel for every edit and delete, plus moderator-only `/archive` queries to look anything up after the fact. 90-day retention.
- **Threads.com link embedder** — automatically rewrites `threads.com` / `threads.net` links so Discord renders the embed, then offers the original poster a confirm/retract via reactions.

## Quick start

```sh
cp .env.example .env   # fill in DISCORD_TOKEN and channel/user IDs
docker compose up -d --build
docker compose logs -f
```

For the full setup (Discord application + privileged intents + bot permissions, env vars, deployment options), see **[USAGE.md](./USAGE.md)**.

For the slash command reference and per-feature behavior, see **[FEATURES.md](./FEATURES.md)**.

## Project docs

| File | For whom | What |
|---|---|---|
| `README.md` | newcomer | This file — orientation and pointers |
| `USAGE.md` | operator | Discord app setup, env config, run + deploy, troubleshooting |
| `FEATURES.md` | end user / mod | Slash commands and automatic behaviors, per cog |
| `CONTEXT.md` | contributor | Domain language (Archive vs Mod-log, Moderator vs Admin, etc.) |
| `CLAUDE.md` | Claude Code (also human-readable) | Internal architecture, cross-cog handshakes, gotchas |
| `docs/adr/` | contributor | Architecture decision records — *why*, not *what* |

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
├── data/               # runtime state (gitignored): bot.db, attachments/
├── docs/adr/           # architecture decision records
├── Dockerfile
└── docker-compose.yml
```

To add a feature, create `cogs/<name>.py`, add `"cogs.<name>"` to `EXTENSIONS` in `bot.py`, and document it in [FEATURES.md](./FEATURES.md).
